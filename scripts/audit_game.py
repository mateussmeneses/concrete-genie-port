#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Audit a local Concrete Genie PS4 dump and write a JSON manifest.

Read-only: the dump is never modified, and no game binary is copied into the repository.
The manifest records only what this build actually contains -- nothing is inferred.

    python scripts/audit_game.py <game dir> [--out manifest.json]

Without a dump the module still imports cleanly and the tests exercise it against
synthetic fixtures. Exit codes: 0 = manifest written, 1 = dump missing/unreadable,
2 = usage error.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

# The audited upstream parsers. Kept as imports (not copies) so a fix in one place
# serves both the manifest and the preparation pipeline.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runtime' / 'scripts'))
from prepare import parse_self, sfo, span, unpack  # noqa: E402
from link_modules import module  # noqa: E402

SCHEMA = 'concrete-genie-audit/1'

# PS4 SELF header type. 0x0001 = encrypted/fake-signed; 0x0480 = plain (decrypted).
SELF_ENCRYPTED = 0x0001


def sha256_file(path, chunk=1024 * 1024):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(chunk), b''):
            digest.update(block)
    return digest.hexdigest()


def read_sfo_fields(game):
    """Verified fields only. Returns None for keys the file does not carry."""
    path = game / 'sce_sys' / 'param.sfo'
    if not path.is_file():
        raise ValueError(f'missing {path}')
    fields = sfo(path.read_bytes())
    wanted = ('TITLE_ID', 'TITLE', 'APP_VER', 'VERSION', 'CONTENT_ID', 'CATEGORY',
              'APP_TYPE', 'SYSTEM_VER', 'ATTRIBUTE', 'PARENTAL_LEVEL')
    return {key: fields[key] for key in wanted if key in fields}


def self_header(data):
    """SELF-level facts, independent of the ELF payload."""
    if len(data) < 32 or data[:4] != b'O\x15=\x1d':
        raise ValueError('eboot.bin is not a PS4 SELF container')
    header_type, meta, declared_size = unpack('<HHI', data, 12)
    count, = unpack('<H', data, 24)
    segments = []
    for i in range(count):
        flags, offset, size, mem = unpack('<QQQQ', data, 32 + i * 32)
        segments.append({
            'index': i,
            'flags': f'0x{flags:x}',
            'file_offset': offset,
            'file_size': size,
            'memory_size': mem,
            # Bit 1 = compressed, bit 3 = encrypted. Either makes the payload unreadable
            # without console-derived keys; record it instead of guessing.
            'compressed': bool(flags & 2),
            'encrypted': bool(flags & 8),
            'blocked': bool(flags & 0x800),
        })
    return {
        'header_type': f'0x{header_type:04x}',
        'metadata': f'0x{meta:04x}',
        'declared_file_size': declared_size,
        'declared_matches_actual': declared_size == len(data),
        'segment_count': count,
        'encrypted': header_type == SELF_ENCRYPTED or any(s['encrypted'] for s in segments),
        'compressed': any(s['compressed'] for s in segments),
        'segments': segments,
    }


def elf_summary(parsed):
    _, header, ph, _, missing = parsed
    return {
        'machine': header[2],
        'entry': header[6],
        'program_headers': [
            {'type': f'0x{p["type"]:x}', 'flags': f'0x{p["flags"]:x}',
             'file_offset': p['offset'], 'vaddr': p['vaddr'],
             'file_size': p['filesz'], 'memory_size': p['memsz']}
            for p in ph
        ],
        'unavailable_segments': missing,
    }


def import_table(parsed):
    """Imports grouped by the library that must provide them.

    Names come from the symbol table as `NID#library#module`; the library id is resolved
    with the same tables the linker uses, so this matches what linking will do.
    """
    libraries = parsed['libraries']
    modules = parsed['modules']

    def library_name(key):
        return libraries.get(key, (key,))[0]

    def module_name(key):
        return modules.get(key, (key,))[0]

    by_library = {}
    unresolved = []
    for symbol in parsed['symbols']:
        if symbol['section'] or not symbol['identity']:
            continue
        nid, lib_ident, mod_ident = symbol['identity']
        lib_id = next((k for k, v in libraries.items() if v == lib_ident), None)
        mod_id = next((k for k, v in modules.items() if v == mod_ident), None)
        if lib_id is None or mod_id is None:
            unresolved.append(symbol['name'])
            continue
        by_library.setdefault(library_name(lib_id), []).append({
            'name': symbol['name'],
            'nid': nid,
            'module': module_name(mod_id),
        })
    for entry in by_library.values():
        entry.sort(key=lambda e: e['name'])
    return {
        'import_count': sum(len(v) for v in by_library.values()),
        'library_count': len(by_library),
        'by_library': dict(sorted(by_library.items())),
        'unresolved_symbol_names': sorted(unresolved),
    }


def dump_tree(game, limit=400):
    """Relative paths and sizes of the dump, no file contents."""
    entries = []
    for path in sorted(game.rglob('*')):
        if len(entries) >= limit:
            break
        if path.is_file():
            entries.append({'path': path.relative_to(game).as_posix(),
                            'size': path.stat().st_size})
    return entries


def module_files(game):
    directory = game / 'sce_module'
    if not directory.is_dir():
        return []
    return [{'name': p.name, 'size': p.stat().st_size,
             'sha256': sha256_file(p)}
            for p in sorted(directory.iterdir()) if p.is_file()]


def codec_signals(game):
    """Middleware presence, by the files the dump actually ships."""
    found = []
    for pattern, label in (
        ('**/bink*.prx', 'Bink video (PS4 module)'),
        ('**/*.bk2', 'Bink video (.bk2 stream)'),
        ('**/libSceAjm.prx', 'SceAjm (ATRAC9/MP3 decode)'),
        ('**/*.at9', 'ATRAC9 audio (.at9)'),
        ('**/*.wem', 'Wwise audio (.wem)'),
        ('**/*.bnk', 'Wwise sound bank (.bnk)'),
        ('**/*.pak', 'UE4 pak (.pak)'),
        ('**/*.uproject', 'Unreal project descriptor'),
    ):
        hits = [p.relative_to(game).as_posix() for p in game.glob(pattern)][:5]
        if hits:
            found.append({'signal': label, 'evidence': hits})
    return found


def input_signals(game, parsed):
    """Camera / gyro / VR related libraries, from the imports actually requested."""
    wanted = ('libSceCamera', 'libSceVrTracker', 'libSceMove', 'libSceHmd',
              'libScePad', 'libSceMouse', 'libSceFace', 'libSceHand')
    table = import_table(parsed)
    present = {}
    for library in table['by_library']:
        for name in wanted:
            if library.startswith(name) or name in library:
                present.setdefault(name, []).append(library)
    return {
        'libraries_referenced': {k: sorted(set(v)) for k, v in sorted(present.items())},
        'note': 'Presence of an import is not evidence that the game uses the feature.',
    }


def ue4_signals(game, sfo_fields, parsed):
    commandline = game / 'ue4commandline.txt'
    return {
        'command_line': (commandline.read_text(encoding='utf-8', errors='replace').strip()
                         if commandline.is_file() else None),
        'category': sfo_fields.get('CATEGORY'),
        'content_id': sfo_fields.get('CONTENT_ID'),
        'imports_libc': any(k.startswith('libc') for k in import_table(parsed)['by_library']),
        'note': 'UE4-specific behaviour must be discovered per build; no MediEvil policy applies.',
    }


def save_signals(game):
    """Save format is not guessed: only directories and file extensions are listed."""
    wanted = ('savedata', 'sce_sys', 'concretegenie/Saved', 'ConcreteGenie/Saved')
    found = []
    for name in wanted:
        path = game / name
        if path.exists():
            found.append({'path': name, 'kind': 'dir' if path.is_dir() else 'file'})
    extensions = {}
    for path in game.rglob('*'):
        if path.is_file() and len(extensions) < 40:
            suffix = path.suffix.lower()
            if suffix:
                extensions[suffix] = extensions.get(suffix, 0) + 1
    return {
        'save_directories_present': found,
        'note': 'Save format is UNKNOWN until save files from a real run are inspected.',
        'top_file_extensions': dict(sorted(extensions.items(), key=lambda kv: -kv[1])[:15]),
    }


def audit(game, include_tree=True):
    game = Path(game)
    if not game.is_dir():
        raise ValueError(f'not a directory: {game}')
    eboot = game / 'eboot.bin'
    if not eboot.is_file():
        raise ValueError(f'no eboot.bin in {game}; point at the folder that contains it')

    raw = eboot.read_bytes()
    sfo_fields = read_sfo_fields(game)
    header = self_header(raw)

    manifest = {
        'schema': SCHEMA,
        'game_dir_name': game.name,
        'build': {
            'title_id': sfo_fields.get('TITLE_ID'),
            'title': sfo_fields.get('TITLE'),
            'app_ver': sfo_fields.get('APP_VER'),
            'version': sfo_fields.get('VERSION'),
            'content_id': sfo_fields.get('CONTENT_ID'),
            'category': sfo_fields.get('CATEGORY'),
            'eboot_size': len(raw),
            'eboot_sha256': hashlib.sha256(raw).hexdigest(),
            'param_sfo_sha256': sha256_file(game / 'sce_sys' / 'param.sfo'),
        },
        'container': header,
        'validated': False,
        'validation_note': ('Identified, not validated. Boot, imports and gameplay remain '
                            'unproven until a run is logged.'),
    }

    # A decrypted build is the only one whose payload can be inspected at all.
    if header['encrypted']:
        manifest['payload'] = {'error': 'encrypted SELF: payload not inspectable'}
        manifest['stage'] = 'manifest'
        return manifest

    parsed = module(eboot)
    manifest['payload'] = {
        'elf': elf_summary(parse_self(raw)),
        'libraries': {k: {'name': v[0], 'version': v[1]}
                      for k, v in sorted(parsed['libraries'].items())},
        'modules': {k: {'name': v[0], 'version': v[1]}
                    for k, v in sorted(parsed['modules'].items())},
        'symbol_count': len(parsed['symbols']),
        'unavailable_segments': parsed['missing'],
    }
    manifest['imports'] = import_table(parsed)
    manifest['modules_on_disk'] = module_files(game)
    manifest['codecs'] = codec_signals(game)
    manifest['input'] = input_signals(game, parsed)
    manifest['engine'] = ue4_signals(game, sfo_fields, parsed)
    manifest['saves'] = save_signals(game)
    if include_tree:
        manifest['files'] = dump_tree(game)
    manifest['stage'] = 'manifest'
    return manifest


def main(argv=None):
    description = (__doc__ or 'Audit a local Concrete Genie PS4 dump').splitlines()[0]
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('game', help='folder containing eboot.bin and sce_sys/')
    parser.add_argument('--out', help='write the manifest here (default: stdout)')
    parser.add_argument('--no-tree', action='store_true',
                        help='omit the file listing (large dumps)')
    args = parser.parse_args(argv)
    try:
        manifest = audit(args.game, include_tree=not args.no_tree)
    except (OSError, ValueError, IndexError, KeyError, struct.error) as error:
        print(f'audit_game: {error}', file=sys.stderr)
        return 1
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
        print(f'wrote {args.out}')
        print(f"title_id={manifest['build']['title_id']} "
              f"app_ver={manifest['build']['app_ver']} "
              f"sha256={manifest['build']['eboot_sha256']}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
