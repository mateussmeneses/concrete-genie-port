"""Tests for scripts/audit_game.py against synthetic fixtures.

No game data is used: the SELF/ELF/SFO fixtures are built here, byte by byte, so the
parser contract is pinned without shipping (or requiring) the dump.
"""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'runtime' / 'scripts'))

import audit_game  # noqa: E402


def sfo_bytes(fields):
    keys, values, entries = b'', b'', b''
    for key, value in fields.items():
        data = value.encode() + b'\0'
        entries += struct.pack('<HHIII', len(keys), 0x204, len(data), len(data), len(values))
        keys += key.encode() + b'\0'
        values += data
    return struct.pack('<4sIIII', b'\0PSF', 0x101, 20 + len(entries),
                       20 + len(entries) + len(keys), len(fields)) + entries + keys + values


class SelfHeaderTests(unittest.TestCase):
    def test_rejects_non_self(self):
        with self.assertRaisesRegex(ValueError, 'not a PS4 SELF'):
            audit_game.self_header(b'not a self container at all, definitely')

    def test_short_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not a PS4 SELF'):
            audit_game.self_header(b'O\x15=\x1d')

    def test_zero_segment_self_reports_no_encryption(self):
        # magic + zeroed fields + segment_count 0
        raw = b'O\x15=\x1d' + bytes(20) + struct.pack('<H', 0) + bytes(6)
        header = audit_game.self_header(raw)
        self.assertEqual(header['segment_count'], 0)
        self.assertFalse(header['encrypted'])
        self.assertFalse(header['compressed'])
        self.assertEqual(header['header_type'], '0x0000')

    def test_encrypted_header_type_is_flagged(self):
        raw = b'O\x15=\x1d' + bytes(8) + struct.pack('<H', 0x0001) + bytes(10) + struct.pack('<H', 0) + bytes(6)
        self.assertTrue(audit_game.self_header(raw)['encrypted'])

    def test_encrypted_segment_is_flagged(self):
        # one segment whose flags carry the encrypted bit (0x8)
        header = b'O\x15=\x1d' + bytes(8) + struct.pack('<H', 0x0480) + bytes(10) + struct.pack('<H', 1)
        segment = struct.pack('<QQQQ', 0x8, 0, 16, 16)
        header = header.ljust(32, b'\0') + segment
        result = audit_game.self_header(header)
        self.assertTrue(result['encrypted'])
        self.assertTrue(result['segments'][0]['encrypted'])

    def test_compressed_segment_is_flagged(self):
        header = b'O\x15=\x1d' + bytes(8) + struct.pack('<H', 0x0480) + bytes(10) + struct.pack('<H', 1)
        header = header.ljust(32, b'\0') + struct.pack('<QQQQ', 0x2, 0, 16, 16)
        self.assertTrue(audit_game.self_header(header)['compressed'])


class SfoFieldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name) / 'CUSA00000'
        (self.game / 'sce_sys').mkdir(parents=True)

    def write_sfo(self, fields):
        (self.game / 'sce_sys' / 'param.sfo').write_bytes(sfo_bytes(fields))

    def test_reads_known_fields_only(self):
        self.write_sfo({'TITLE_ID': 'CUSA11875', 'APP_VER': '01.07',
                        'CONTENT_ID': 'EP9000-CUSA11875_00-CONCRETEGENIE000',
                        'TITLE': 'Concrete Genie', 'UNRELATED': 'x'})
        fields = audit_game.read_sfo_fields(self.game)
        self.assertEqual(fields['TITLE_ID'], 'CUSA11875')
        self.assertEqual(fields['APP_VER'], '01.07')
        self.assertEqual(fields['CONTENT_ID'], 'EP9000-CUSA11875_00-CONCRETEGENIE000')
        self.assertNotIn('UNRELATED', fields)

    def test_missing_sfo_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            audit_game.read_sfo_fields(self.game)

    def test_bad_magic_is_an_error(self):
        (self.game / 'sce_sys' / 'param.sfo').write_bytes(b'XXXX' + bytes(60))
        with self.assertRaises(ValueError):
            audit_game.read_sfo_fields(self.game)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name) / 'CUSA11875'

    def test_missing_directory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not a directory'):
            audit_game.audit(self.game)

    def test_missing_eboot_is_actionable(self):
        self.game.mkdir()
        with self.assertRaisesRegex(ValueError, 'no eboot.bin'):
            audit_game.audit(self.game)

    def test_encrypted_payload_stops_at_manifest_stage_without_inventing_data(self):
        (self.game / 'sce_sys').mkdir(parents=True)
        (self.game / 'sce_sys' / 'param.sfo').write_bytes(
            sfo_bytes({'TITLE_ID': 'CUSA11875', 'APP_VER': '01.07'}))
        raw = b'O\x15=\x1d' + bytes(8) + struct.pack('<H', 0x0001) + bytes(10) + struct.pack('<H', 0) + bytes(6)
        (self.game / 'eboot.bin').write_bytes(raw)
        manifest = audit_game.audit(self.game)
        self.assertEqual(manifest['stage'], 'manifest')
        self.assertIn('error', manifest['payload'])
        self.assertFalse(manifest['validated'])
        self.assertNotIn('imports', manifest)

    def test_cli_exit_codes(self):
        missing = Path(self.temp.name) / 'nope'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'audit_game.py'), str(missing)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 1)
        self.assertIn('not a directory', result.stderr)

    def test_cli_writes_manifest_json(self):
        (self.game / 'sce_sys').mkdir(parents=True)
        (self.game / 'sce_sys' / 'param.sfo').write_bytes(
            sfo_bytes({'TITLE_ID': 'CUSA11875', 'APP_VER': '01.07', 'TITLE': 'Concrete Genie'}))
        raw = b'O\x15=\x1d' + bytes(8) + struct.pack('<H', 0x0001) + bytes(10) + struct.pack('<H', 0) + bytes(6)
        (self.game / 'eboot.bin').write_bytes(raw)
        out = Path(self.temp.name) / 'manifest.json'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'audit_game.py'),
                                 str(self.game), '--out', str(out)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(manifest['build']['title_id'], 'CUSA11875')
        self.assertEqual(manifest['schema'], audit_game.SCHEMA)
        self.assertIn('eboot_sha256', manifest['build'])
        self.assertFalse(manifest['validated'])


class AbortFindingTests(unittest.TestCase):
    """The first observed blocking call must stay documented and testable.

    libc's abort() is `push rbp; mov rbp,rsp; int 0x44; ...; ud2`. The runtime has no
    int 0x44 gate, so the guest faults in abort() instead of reporting why it was called.
    This test pins the decoding used in docs/HANDOFF.md so the claim cannot drift.
    """

    ABORT_BYTES = bytes.fromhex('554889e5cd44bacccccccc')

    def test_abort_opcode_contains_int44_gate(self):
        self.assertEqual(self.ABORT_BYTES[:2], b'\x55\x48')     # push rbp; (Rex.W) mov
        self.assertIn(b'\xcd\x44', self.ABORT_BYTES,
                      'PS4 syscall gate INT 0x44 must be present in abort()')


if __name__ == '__main__':
    unittest.main()
