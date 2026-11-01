#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Concrete Genie bootstrap launcher. No game build has been validated yet."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import sys

from profiles import inspect_build

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime" / "out" / "gpu" / "cg-runtime.exe"
# MSYS2 users paste /c/... paths from the CLANG64 shell; Python on Windows reads that as a
# relative "c/..." segment. Translate it so --game-dir and friends behave as pasted.
MSYS_PATH = re.compile(r"^/([A-Za-z])/(.*)$")


def windows_path(value):
    match = MSYS_PATH.match(str(value))
    return f"{match.group(1)}:/{match.group(2)}" if match else str(value)


def configuration(args, environ):
    explicit = args.config or environ.get("CG_CONFIG")
    path = Path(explicit or ROOT / "concrete-genie.json").resolve()
    values = {}
    if explicit or path.exists():
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError(f"Cannot read config {path}: {error}") from error
        if not isinstance(values, dict) or set(values) - {"game_dir", "data_dir"}:
            raise ValueError("Config must be an object with only game_dir and data_dir")
        if any(not isinstance(v, str) or not v.strip() for v in values.values()):
            raise ValueError("Config paths must be nonempty strings")
    resolved = {}
    for key, default in (("game_dir", None), ("data_dir", str(ROOT / ".cg"))):
        value = getattr(args, key) or environ.get("CG_" + key.upper()) or values.get(key, default)
        if value is None:
            resolved[key] = None
        else:
            candidate = Path(windows_path(value)).expanduser()
            resolved[key] = (path.parent / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    game, data = resolved["game_dir"], resolved["data_dir"]
    if data == ROOT or any(data.is_relative_to(ROOT / d) for d in ("runtime", "references")):
        raise ValueError("data_dir must be separate from project sources and references")
    if game and (data.is_relative_to(game) or game.is_relative_to(data)):
        raise ValueError("game_dir and data_dir must not overlap; the dump stays read-only")
    return resolved


def runtime_environment(data, environ):
    # Inherited knobs can force legacy patches, paths and hooks; expose only the CG interface.
    env = {k: v for k, v in environ.items() if not k.upper().startswith("GOW3_")}
    env.update(GOW3_CONFIG=str(data / "runtime.ini"),
               GOW3_GPU_USER_DIR=str(data / "gpu"), GOW3_USER_DIR=str(data / "user"),
               GOW3_UPSCALER="none")
    msys = Path(environ.get("CG_MSYS2_ROOT", "C:/msys64")) / "clang64" / "bin"
    if os.name == "nt" and msys.is_dir():
        env["PATH"] = str(msys) + os.pathsep + env.get("PATH", "")
    return env


def launch_runtime(arguments, data, environ):
    if not RUNTIME.is_file():
        raise ValueError(f"Runtime not built: {RUNTIME}. Run bash build.sh in MSYS2 CLANG64.")
    data.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(RUNTIME), *map(str, arguments)], cwd=data,
                            env=runtime_environment(data, environ),
                            stdin=subprocess.DEVNULL)
    return result.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="JSON config (CG_CONFIG); relative paths use its directory")
    parser.add_argument("--game-dir", help="Local dump folder (CG_GAME_DIR)")
    parser.add_argument("--data-dir", help="Isolated output/cache/save directory (CG_DATA_DIR; default .cg)")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check-config", action="store_true", help="Validate configuration without a dump or build")
    modes.add_argument("--audit-runtime", action="store_true", help="Audit native resolver without guest execution")
    modes.add_argument("--vulkan-smoke", action="store_true", help="Submit and read back a Vulkan buffer, without a game")
    args = parser.parse_args(argv)
    try:
        config = configuration(args, os.environ)
        data, game = config["data_dir"], config["game_dir"]
        if args.check_config:
            print(json.dumps({k: str(v) if v is not None else None for k, v in config.items()}, indent=2))
            print("Configuration valid; game support NOT VALIDATED.")
            return 0
        if args.audit_runtime or args.vulkan_smoke:
            return launch_runtime(["--audit-runtime" if args.audit_runtime else "--vulkan-only"],
                                  data / "diagnostics", os.environ)
        if game is None:
            raise ValueError("No game configured. Set CG_GAME_DIR or --game-dir to your local dump; see --help.")
        title, version, digest, modules = inspect_build(game)
        if not RUNTIME.is_file():
            raise ValueError("Runtime not built; run bash build.sh in MSYS2 CLANG64.")
        # Build-specific images/caches; saves persist across verified updates of the same title.
        state = data / title
        work = state / digest
        out = work / "prepared"
        from prepare import prepare
        from link_modules import link
        from content_profile import prepare as prepare_content
        prepare(game, out)
        link(game, out, module_names=modules)
        prepare_content(game, out)
        from save_backup import backup
        backup(state / "user")
        env = runtime_environment(work, os.environ)
        env["GOW3_USER_DIR"] = str(state / "user")
        work.mkdir(parents=True, exist_ok=True)
        print(f"Starting verified build {title} {version}; no game patches enabled.", flush=True)
        return subprocess.run([str(RUNTIME), str(out / "boot-linked.bin"),
                               "--content-profile", str(out / "content.bin"),
                               "--app0", str(game), "--user", str(state / "user"), "--timeout", "0"],
                              cwd=work, env=env, stdin=subprocess.DEVNULL).returncode
    except (OSError, ValueError, KeyError, IndexError, StopIteration, struct.error) as error:
        print(f"Concrete Genie: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
