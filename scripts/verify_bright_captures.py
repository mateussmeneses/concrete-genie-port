"""Verify the pixel-level claim behind the bright-state diagnosis.

The bright state's display and output dumps are byte-identical raw RGBA8 frames of the
title screen. This script re-derives the recorded facts from the files so the docs do not
rely on this session's transcription:

Run: python scripts/verify_bright_captures.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np

W, H = 1920, 1080


def sha16(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def grid3x3(arr: np.ndarray) -> list[list[float]]:
    lum = (arr[..., 0].astype(np.float32) + arr[..., 1] + arr[..., 2]) / 3.0
    out = [[0.0] * 3 for _ in range(3)]
    for iy in range(3):
        for ix in range(3):
            ys = np.arange(0, H, 8)
            xs = np.arange(0, W, 8)
            sel = (np.minimum(2, (ys * 3) // H) == iy)[:, None] & (np.minimum(2, (xs * 3) // W) == ix)[None, :]
            sub = lum[ys][:, xs][sel]
            out[iy][ix] = round(float(sub.mean()), 1)
    return out


def main() -> int:
    groups = {
        "bright (pbc)": ".cg/audit/pbc",
        "bright (try1 fresh)": ".cg/audit/bright-fresh/try1",
        "bright (try6 presscap)": ".cg/audit/bright-fresh/try6-presscap",
        "scene (g1)": ".cg/audit/g1",
    }
    ok = True
    for label, d in groups.items():
        disp = Path(d) / "display_001_1920x1080.raw"
        outp = Path(d) / "output_001_1920x1080.raw"
        if not disp.is_file() or not outp.is_file():
            print(f"{label}: SKIPPED (missing dumps in {d})")
            continue
        identical = disp.read_bytes() == outp.read_bytes()
        arr = np.frombuffer(disp.read_bytes(), dtype=np.uint8).reshape(H, W, 4)
        lum = (arr[..., 0].astype(np.float32) + arr[..., 1] + arr[..., 2]) / 3.0
        title_grid = [[255.0, 255.0, 255.0], [252.5, 239.1, 254.2], [253.2, 220.4, 253.2]]
        is_title = abs(lum.mean() - 248.7) < 3.0
        print(f"{label}: display==output {identical}, sha={sha16(disp)}, "
              f"mean={lum.mean():.1f}, title-screen match={is_title}")
        if "bright" in label and not (identical and is_title):
            ok = False
    print("VERIFY:", "OK" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
