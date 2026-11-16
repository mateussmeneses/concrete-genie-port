"""Title-press experiment: hold nothing until the title (bright) is on screen, then press cross.

Hypothesis under test: the guest's title screen advances on a cross PRESS EDGE. The white-loop
runs hold cross from pad read #1, so by the time the title appears the button has been down the
whole time and no new press edge exists. If releasing and re-pressing cross at the title advances
the game, the white screen is the title waiting for input, not a presentation defect.

Run: python scripts/title_press_test.py <out-dir> [--timeout 350]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import frame_states  # noqa: E402

RUNTIME = ROOT / ".cg/audit/run-bundle/cg-runtime.exe"
BOOT = ROOT / ".cg/audit/prepared/boot-linked.bin"
CONTENT = ROOT / ".cg/audit/prepared/content.bin"
DUMP = ROOT / "gamedump/CUSA11875"
USER = ROOT / ".cg/audit/run/user-white"


def classify_samples(log: Path) -> list[dict]:
    text = log.read_text(errors="replace") if log.is_file() else ""
    samples = frame_states.parse(text)
    for s in samples:
        s["state"] = frame_states.classify(s["mean"], frame_states.spread(s["grid"]))
    return samples


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--timeout", type=float, default=350.0)
    ap.add_argument("--settle", type=int, default=15,
                    help="bright samples required before pressing cross")
    args = ap.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    pad_live = out / "pad_live.txt"
    pad_live.write_text("")  # nothing held at boot: the title must see no button down
    press_file = out / "pad_press.txt"
    press_file.write_text("cross\n")

    env = dict(os.environ)
    env.update({
        "GOW3_FRAME_MAP": "1",
        "GOW3_FRAME_MAP_EVERY": "20",
        "GOW3_DUMP_DIR": str(out).replace("\\", "/"),
        "GOW3_PAD_FILE": str(pad_live),
    })
    msys2_bin = Path(os.environ.get("MSYS2_ROOT", "C:/msys64")) / "clang64/bin"
    if msys2_bin.is_dir():
        env["PATH"] = str(msys2_bin) + os.pathsep + env.get("PATH", "")

    log_path = out / "run.log"
    started = time.monotonic()
    pressed = False
    last_press_frame = None
    with log_path.open("w", errors="replace") as log:
        proc = subprocess.Popen([str(RUNTIME), str(BOOT), "--content-profile", str(CONTENT),
                                 "--app0", str(DUMP).replace("\\", "/"), "--user", str(USER),
                                 "--timeout", str(int(args.timeout))],
                                stdout=log, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT))
        offset = 0
        buffer = ""
        run_state, run_len = None, 0
        while time.monotonic() - started < args.timeout + 60:
            if proc.poll() is not None:
                break
            if not pressed and log_path.is_file():
                # Watch the runtime's own FrameMap lines in the log, not the pad file:
                # the pad file is what this script writes and never contains samples.
                with log_path.open("r", errors="replace") as h:
                    h.seek(offset)
                    chunk = h.read()
                    offset = h.tell()
                data = buffer + chunk
                cut = data.rfind("\n")
                if cut >= 0:
                    buffer = data[cut + 1:]
                    samples_now = frame_states.parse(data[:cut])
                    for sample in samples_now:
                        cur = frame_states.classify(sample["mean"], frame_states.spread(sample["grid"]))
                        if cur != run_state:
                            run_state, run_len = cur, 1
                        else:
                            run_len += 1
                        last_press_frame = sample["frame"]
                    if run_state == "bright" and run_len >= args.settle and samples_now:
                        pad_live.write_text(press_file.read_text())
                        pressed = True
                        print(f"pressed cross at frame ~{last_press_frame} "
                              f"({time.monotonic() - started:.0f}s), state bright held {run_len} samples")
            time.sleep(0.25)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
    elapsed = time.monotonic() - started
    samples = classify_samples(log_path)
    states: dict[str, list[int]] = {}
    for s in samples:
        states.setdefault(s["state"], []).append(s["frame"])
    summary = {k: [v[0], v[-1], len(v)] for k, v in states.items()}
    manifest = {
        "out_dir": str(out),
        "pad": "empty until bright settled, then cross held",
        "pressed": pressed,
        "elapsed_s": round(elapsed, 1),
        "state_regions": summary,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
