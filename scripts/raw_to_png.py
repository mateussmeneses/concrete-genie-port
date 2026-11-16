"""Decode a raw 1920x1080 RGBA8 dump to PNG (downscaled) for visual inspection.

Run: python scripts/raw_to_png.py <file.raw> <out.png> [--half]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 1920, 1080


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--half", action="store_true", help="save at half resolution")
    args = ap.parse_args()
    data = args.src.read_bytes()
    if len(data) != W * H * 4:
        print(f"ERROR: {args.src} is {len(data)} bytes, expected {W*H*4}", file=sys.stderr)
        return 1
    arr = np.frombuffer(data, dtype=np.uint8).reshape(H, W, 4)[..., :3]
    img = Image.fromarray(arr)
    if args.half:
        img = img.resize((W // 2, H // 2), Image.BILINEAR)
    img.save(args.dst)
    print(f"{args.dst} written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
