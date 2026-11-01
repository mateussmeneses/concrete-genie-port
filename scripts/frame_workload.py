"""Compare the presented image against the GPU workload for every FrameMap sample in a log.

Why: a "white screen" run was twice read as a loading screen or a menu, and once blamed on OPTIONS.
The measurement that settles it is cheap - a real 3D scene costs tens of thousands of draws per
frame, a loading screen or a menu does not. Reading luminance alone cannot tell "a different screen
that draws a lot" from "the same screen rendered over and over".

This reports, per state region:
    draws/sample      GPU work being done while that image is on screen
    distinct grids    how many different images appear (1 means a frozen picture)
    mean lum, spread  what the image looks like

A region with scene-level draws and one distinct image is a frozen present, not a quiet screen.

Usage:
    python scripts/frame_workload.py <log> [--min-frame N]
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import frame_states  # noqa: E402


def grid_key(sample: dict) -> tuple[float, ...]:
    return tuple(round(v, 1) for row in sample["grid"] for v in row)


def report(samples: list[dict]) -> list[dict]:
    rows = []
    for region in frame_states.regions(samples):
        members = [s for s in samples if region["first"] <= s["frame"] <= region["last"]]
        if not members:
            continue
        draws = [s["draws"] for s in members]
        rows.append(
            {
                "state": region["state"],
                "first": region["first"],
                "last": region["last"],
                "samples": len(members),
                "draws_mean": statistics.mean(draws),
                "distinct": len({grid_key(s) for s in members}),
                "lum": statistics.mean(frame_states.mean_of(s["grid"]) for s in members),
                "spread": statistics.mean(frame_states.spread(s["grid"]) for s in members),
            }
        )
    return rows


def verdict(row: dict) -> str:
    """Name what the numbers imply, without claiming a cause the numbers cannot show."""
    busy = row["draws_mean"] >= 1000
    frozen = row["distinct"] <= 3
    if busy and frozen and row["samples"] >= 10:
        return "FROZEN PRESENT: full scene workload, one image repeated"
    if not busy and frozen:
        return "quiet screen: little GPU work"
    if busy:
        return "live rendering"
    return "low workload"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="FrameMap state vs GPU workload.")
    parser.add_argument("log", type=Path)
    parser.add_argument("--min-frame", type=int, default=0,
                        help="ignore samples before this frame (skips the boot)")
    args = parser.parse_args(argv[1:])

    if not args.log.is_file():
        print(f"ERROR: {args.log} does not exist", file=sys.stderr)
        return 1
    samples = [s for s in frame_states.parse(args.log.read_text(errors="replace"))
               if s["frame"] >= args.min_frame]
    if not samples:
        print(f"ERROR: no 'FrameMap:' samples in {args.log}", file=sys.stderr)
        print("Hint: run the runtime with GOW3_FRAME_MAP=1.", file=sys.stderr)
        return 1

    print(f"{args.log.name}: {len(samples)} samples, frames "
          f"{samples[0]['frame']}..{samples[-1]['frame']}")
    print(f"\n{'state':7s} {'frames':>15s} {'n':>5s} {'draws/sample':>13s} "
          f"{'distinct':>9s} {'lum':>6s} {'spread':>7s}  verdict")
    for row in report(samples):
        print(f"{row['state']:7s} {row['first']:6d}..{row['last']:<7d} {row['samples']:5d} "
              f"{row['draws_mean']:13.0f} {row['distinct']:9d} {row['lum']:6.1f} "
              f"{row['spread']:7.1f}  {verdict(row)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
