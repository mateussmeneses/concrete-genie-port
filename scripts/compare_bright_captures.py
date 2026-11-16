"""Compare the bright (white) captures against scene captures with the same metrics.

Writes PNGs and prints a metrics table. Run: python scripts/compare_bright_captures.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 1920, 1080


def load(path: str | Path) -> np.ndarray:
    """Decode a raw RGBA8 dump to an (H, W, 4) uint8 array."""
    data = Path(path).read_bytes()
    if len(data) != W * H * 4:
        raise ValueError(f"{path}: {len(data)} bytes, expected {W * H * 4}")
    return np.frombuffer(data, dtype=np.uint8).reshape(H, W, 4)


def sha16(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def metrics(arr: np.ndarray) -> dict:
    rgb = arr[..., :3].astype(np.uint32)
    lum = (rgb[..., 0] + rgb[..., 1] + rgb[..., 2]) / 3.0
    flat = arr[..., :3].reshape(-1, 3)
    packed = (flat[:, 0].astype(np.uint32) << 16) | (flat[:, 1].astype(np.uint32) << 8) | flat[:, 2]
    hist = np.bincount(lum.astype(np.uint8).ravel(), minlength=256)
    # 3x3 luminance grid, every 8 px (matches FrameMap::SampleGrid)
    grid = np.zeros((3, 3))
    ys = np.arange(0, H, 8)
    xs = np.arange(0, W, 8)
    sub = lum[ys][:, xs]
    cy = np.minimum(2, (ys * 3) // H)
    cx = np.minimum(2, (xs * 3) // W)
    for iy in range(3):
        for ix in range(3):
            sel = sub[(cy == iy)[: len(ys)][:, None] & (cx == ix)[None, : len(xs)]]
            grid[iy, ix] = sel.mean()
    return {
        "mean": float(lum.mean()),
        "nonblack_pct": float((lum > 8).mean() * 100),
        "nonwhite_pct": float((lum < 247).mean() * 100),
        "n_colors": int(np.unique(packed).size),
        "hist_top": [(int(i), int(hist[i])) for i in np.argsort(hist)[-4:][::-1]],
        "grid": grid.round(1).tolist(),
        "spread": float(grid.max() - grid.min()),
    }


def main() -> int:
    out = Path(".cg/audit/analysis")
    out.mkdir(parents=True, exist_ok=True)
    groups = {
        "bright(pbc)": ".cg/audit/pbc",
        "scene(g1)": ".cg/audit/g1",
        "scene(map)": ".cg/audit/map",
    }
    results = {}
    for label, d in groups.items():
        arr = load(Path(d) / "display_000_1920x1080.raw")
        m = metrics(arr)
        results[label] = m
        img = Image.fromarray(arr[..., :3])
        img.save(out / f"{label.replace('(', '_').replace(')', '')}_display000.png")
        print(f"{label}: display_000 sha={sha16(Path(d) / 'display_000_1920x1080.raw')}")
        for k, v in m.items():
            print(f"    {k}: {v}")
        print()

    # absolute pixel difference between the bright capture and a scene capture
    a = load(".cg/audit/pbc/display_000_1920x1080.raw")[..., :3].astype(np.int16)
    b = load(".cg/audit/g1/display_000_1920x1080.raw")[..., :3].astype(np.int16)
    diff = np.abs(a - b)
    per_channel = diff.reshape(-1, 3).mean(axis=0)
    print(f"abs diff bright(pbc) vs scene(g1): mean per channel (r,g,b) = "
          f"{per_channel[0]:.2f}, {per_channel[1]:.2f}, {per_channel[2]:.2f}; "
          f"pixels differing >2 = {(diff.max(axis=2) > 2).mean() * 100:.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
