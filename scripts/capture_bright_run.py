"""Capture the guest display surfaces inside a bright (white) run, with early exit.

Runs the runtime with GOW3_FRAME_MAP=1 (20-frame sampling), raw surface dumps at fixed
presented-frame indices, and a `cross` pad file held from the start. The runtime is killed
early once the dump files are confirmed on disk, because the interesting frames (700/1500/2500)
all pass within the first minutes; waiting for the full 350 s adds nothing.

Writes one manifest.json per attempt under the attempt directory. Never reuses directories:
an existing attempt dir aborts instead of overwriting.

Usage:
    python scripts/capture_bright_run.py <attempt-dir> [--timeout 350] [--dump-frames 700,1500,2500]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import frame_states  # noqa: E402

RUNTIME = ROOT / ".cg/audit/run-bundle/cg-runtime.exe"  # self-contained DLL bundle (see make_runtime_bundle.py)
BOOT = ROOT / ".cg/audit/prepared/boot-linked.bin"
CONTENT = ROOT / ".cg/audit/prepared/content.bin"
DUMP = ROOT / "gamedump/CUSA11875"
ISOLATED_USER = ROOT / ".cg/audit/run/user-white"


def classify_samples(log: Path) -> list[dict]:
    text = log.read_text(errors="replace") if log.is_file() else ""
    samples = frame_states.parse(text)
    for s in samples:
        s["state"] = frame_states.classify(s["mean"], frame_states.spread(s["grid"]))
    return samples


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("attempt_dir", type=Path)
    ap.add_argument("--timeout", type=float, default=350.0)
    ap.add_argument("--dump-frames", default="700,1500,2500")
    ap.add_argument("--exit-after-last-dump", type=float, default=25.0,
                    help="seconds to wait after the last dump file lands before killing")
    args = ap.parse_args()

    out = args.attempt_dir
    if out.exists() and any(out.iterdir()):
        print(f"ERROR: {out} already exists and is not empty; not reusing evidence dirs", file=sys.stderr)
        return 2
    out.mkdir(parents=True)
    for p in (RUNTIME, BOOT, CONTENT):
        if not p.is_file():
            print(f"ERROR: missing {p}", file=sys.stderr)
            return 2
    if not DUMP.is_dir():
        print(f"ERROR: missing dump {DUMP}", file=sys.stderr)
        return 2

    dir_abs = str(out).replace("\\", "/")
    pad_apply = out / "pad_cross.txt"
    pad_apply.write_text("cross\n")
    pad_live = out / "pad_live.txt"
    pad_live.write_text("cross\n")  # held from the start, like capture_white_state.sh

    dump_at = ",".join(x for x in args.dump_frames.split(",") if x.strip())
    cmd = [
        str(RUNTIME),
        str(BOOT),
        "--content-profile", str(CONTENT),
        "--app0", str(DUMP).replace("\\", "/"),
        "--user", str(ISOLATED_USER),
        "--timeout", str(int(args.timeout)),
    ]
    env = dict(os.environ)
    env.update({
        "GOW3_FRAME_MAP": "1",
        "GOW3_FRAME_MAP_EVERY": "20",
        "GOW3_FRAME_DUMP_AT": dump_at,
        "GOW3_DUMP_SYNC": "1",
        "GOW3_DUMP_DIR": dir_abs,
        "GOW3_PAD_FILE": str(pad_live),
    })
    # The runtime links against the MSYS2 CLANG64 DLLs: without them on PATH it dies before
    # writing anything (measured: 0xC0000135 STATUS_DLL_NOT_FOUND, empty log, 1 s runtime).
    # The exe was built against ffmpeg ABI 62 (libavcodec 62.28.101, docs/BASELINE.md) but the
    # system since moved to ffmpeg 9 (ABI 63), so the ABI-62 DLLs are restored from the pacman
    # cache into .cg/audit/ffmpeg-abi62 and prepended; nothing under /c/msys64 is touched.
    msys2_bin = Path(os.environ.get("MSYS2_ROOT", "C:/msys64")) / "clang64/bin"
    abi62 = ROOT / ".cg/audit/ffmpeg-abi62"
    prepend = [p for p in (abi62, msys2_bin) if p.is_dir()]
    if prepend:
        env["PATH"] = os.pathsep.join(str(p) for p in prepend) + os.pathsep + env.get("PATH", "")

    log_path = out / "run.log"
    started = time.monotonic()
    with log_path.open("w", errors="replace") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT))
        dump_frames = [int(x) for x in dump_at.split(",") if x.strip()]
        deadline = started + args.timeout + 60.0
        early_exit_at = None
        while True:
            now = time.monotonic()
            if early_exit_at is None:
                produced = sorted(out.glob("*.raw"))
                if len(produced) >= 2 * len(dump_frames) and all(f.stat().st_size > 0 for f in produced):
                    early_exit_at = now + args.exit_after_last_dump
            elif now >= early_exit_at:
                break
            if proc.poll() is not None:
                break
            if now > deadline:
                break
            time.sleep(1.0)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=30)
    elapsed = time.monotonic() - started

    # The log is the record; never guess the state from exit codes.
    samples = classify_samples(log_path)
    states: dict[str, list[int]] = {}
    for s in samples:
        states.setdefault(s["state"], []).append(s["frame"])
    summary = {k: [v[0], v[-1], len(v)] for k, v in states.items()}

    dumps = sorted(out.glob("*.raw"))
    manifest = {
        "attempt_dir": str(out),
        "runtime": str(RUNTIME),
        "boot": str(BOOT),
        "boot_sha256": sha256(BOOT),
        "content": str(CONTENT),
        "game": "CUSA11875 (EU), APP_VER 01.07, eboot 06f143de...33e51",
        "user_profile": str(ISOLATED_USER) + " (isolated; .cg/audit/run/user untouched)",
        "env": {k: env[k] for k in ("GOW3_FRAME_MAP", "GOW3_FRAME_MAP_EVERY",
                                     "GOW3_FRAME_DUMP_AT", "GOW3_DUMP_SYNC", "GOW3_DUMP_DIR",
                                     "GOW3_PAD_FILE")},
        "pad_held": "cross (from pad read #1)",
        "timeout_s": args.timeout,
        "elapsed_s": round(elapsed, 1),
        "log": str(log_path),
        "state_regions": summary,
        "dumps": [
            {
                "file": d.name,
                "bytes": d.stat().st_size,
                "sha256": sha256(d),
            }
            for d in dumps
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(json.dumps(manifest, indent=2))
    final = samples[-1]["state"] if samples else "<none>"
    print(f"final state: {final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
