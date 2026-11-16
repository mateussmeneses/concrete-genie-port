"""Fork-distribution experiment: N short identical runs (no input), record where each ends up.

The title-vs-scene fork happens around frame ~1500; a 130 s window covers it. All runs use the
isolated profile and empty pad. Output: per-run state regions, one line each.

Run: python scripts/fork_distribution.py <base-dir> [runs]
"""
from __future__ import annotations

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


def main() -> int:
    base = Path(sys.argv[1] if len(sys.argv) > 1 else ".cg/audit/fork-dist")
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    base.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({"GOW3_FRAME_MAP": "1", "GOW3_FRAME_MAP_EVERY": "20",
                "GOW3_PAD_FILE": str(base / "pad_empty.txt"),
                "GOW3_DUMP_DIR": str(base).replace("\\", "/")})
    msys = Path("C:/msys64/clang64/bin")
    if msys.is_dir():
        env["PATH"] = str(msys) + os.pathsep + env.get("PATH", "")
    (base / "pad_empty.txt").write_text("")
    summary = []
    for i in range(1, runs + 1):
        out = base / f"run{i}"
        out.mkdir(exist_ok=True)
        log_path = out / "run.log"
        started = time.monotonic()
        with log_path.open("w", errors="replace") as log:
            proc = subprocess.Popen([str(RUNTIME), str(BOOT), "--content-profile", str(CONTENT),
                                     "--app0", str(DUMP).replace("\\", "/"), "--user", str(USER),
                                     "--timeout", "110"],
                                    stdout=log, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT))
            # The fork lands around frame ~1500 (~55 s at 30 FPS). The guest does not honour
            # --timeout reliably, so bound by wall time: kill at 80 s and read the log. The fork
            # decision is already visible well before that.
            deadline = started + 80.0
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                time.sleep(0.5)
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=30)
        samples = frame_states.parse(log_path.read_text(errors="replace"))
        regions = {}
        for s in samples:
            st = frame_states.classify(s["mean"], frame_states.spread(s["grid"]))
            r = regions.setdefault(st, [s["frame"], s["frame"], 0])
            r[1] = s["frame"]
            r[2] += 1
        final = samples[-1] if samples else None
        verdict = frame_states.classify(final["mean"], frame_states.spread(final["grid"])) if final else "none"
        reached = "scene" if any(k == "scene" for k in regions) else verdict
        line = {"run": str(out), "elapsed_s": round(time.monotonic() - started, 1),
                "regions": regions, "outcome": reached}
        summary.append(line)
        print(json.dumps(line))
    (base / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    titles = sum(1 for s in summary if s["outcome"] == "bright")
    scenes = sum(1 for s in summary if s["outcome"] == "scene")
    print(f"DISTRIBUTION: {scenes} scene / {titles} title / {len(summary) - scenes - titles} other, of {len(summary)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
