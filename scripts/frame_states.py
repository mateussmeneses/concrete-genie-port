"""Read the per-frame state map emitted by GOW3_FRAME_MAP=1.

The map exists because a capture index alone does not identify the game state: the same input
script reaches the 3D scene at different frame numbers on different runs, so a test that compares
"frame 2600 with paint" against "frame 2600 without paint" can silently compare a scene against a
UI screen. This tool turns the raw ``FrameMap:`` lines into a state timeline, so a test picks its
frames from an observed state instead of assuming one.

Grid definition (must match ``FrameMap::SampleGrid`` in vk_presenter.cpp): the presented image is
split into a 3x3 partition; each cell's value is the mean of ``(r + g + b) / 3`` over the pixels
sampled every 8 px. These are the same numbers the paint/pause investigations recorded by hand, so
a frame classified here is comparable with those measurements.

Usage:
    python scripts/frame_states.py <log> [--list] [--frames A,B,C]

States are named from the luminance profile plus the spread across cells, not from any game
knowledge:
    black   the frame is essentially empty (no content)
    fade    a uniform fill brighter than black (loading screens, colour transitions)
    bright  a structured mostly-light image (the UI screens measured here are ~92-98% white)
    scene   a structured mostly-dark image (the 3D scene measured here is ~86 mean luminance)

Spread is what separates ``fade`` from ``scene``: the OPTIONS transition passes through the same
mean luminance as the 3D scene, but as a flat wash instead of a structured image.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# FrameMap line written by vk_presenter.cpp.
LINE = re.compile(
    r"FrameMap: frame (\d+) grid="
    r"\[\[([-\d.]+),([-\d.]+),([-\d.]+)\],"
    r"\[([-\d.]+),([-\d.]+),([-\d.]+)\],"
    r"\[([-\d.]+),([-\d.]+),([-\d.]+)\]\]"
    r" draws=(\d+) submissions=(\d+)"
)

# Thresholds are wide on purpose: they separate "the screen is mostly empty", "a uniform fill"
# (fades and loading screens), "a light UI screen" and "a structured rendered image". Mean
# luminance alone cannot do this: the OPTIONS transition passes through 71.7 mean, which is also
# the 3D scene's mean, but as a uniform fill (spread 1.3 across cells) rather than a scene
# (spread > 80). Structure, not brightness, is what tells a rendered image from a flat wash.
BLACK_BELOW = 5.0
BRIGHT_ABOVE = 200.0
STRUCTURED_SPREAD_ABOVE = 80.0


def parse(text: str) -> list[dict]:
    """Every FrameMap sample in the log, in the order written."""
    samples = []
    for match in LINE.finditer(text):
        grid = [[float(match.group(2 + row * 3 + col)) for col in range(3)] for row in range(3)]
        flat = [v for row in grid for v in row]
        samples.append(
            {
                "frame": int(match.group(1)),
                "grid": grid,
                "mean": sum(flat) / 9.0,
                "draws": int(match.group(11)),
                "submissions": int(match.group(12)),
            }
        )
    return samples


def spread(grid: list[list[float]]) -> float:
    """Difference between the brightest and darkest cell of the 3x3 grid."""
    flat = [v for row in grid for v in row]
    return max(flat) - min(flat)


def mean_of(grid: list[list[float]]) -> float:
    """Mean luminance of the nine cells."""
    flat = [v for row in grid for v in row]
    return sum(flat) / len(flat)


def classify(mean: float, spread_value: float) -> str:
    """Name the state from mean luminance and cell spread.

    Neither signal alone is enough. Brightness cannot separate a flat wash from a rendered scene
    (the OPTIONS fade and the 3D scene both sit at ~72-86 mean). Structure alone cannot separate
    a UI screen from a fade either: the UI screens measured here are 92-98% white with a spread
    of only ~35 across cells, because a mostly-white screen is mostly uniform.

    So the order is: empty, then clearly light (a UI fill), then structure decides between a
    rendered image and a uniform wash. All three boundaries come from measurements.
    """
    if mean < BLACK_BELOW:
        return "black"
    if mean > BRIGHT_ABOVE:
        return "bright"
    if spread_value < STRUCTURED_SPREAD_ABOVE:
        return "fade"
    return "scene"


def regions(samples: list[dict]) -> list[dict]:
    """Contiguous runs of the same state, with the first and last frame of each."""
    out: list[dict] = []
    for sample in samples:
        state = classify(sample["mean"], spread(sample["grid"]))
        if not out or out[-1]["state"] != state:
            out.append({"state": state, "first": sample["frame"], "last": sample["frame"],
                        "samples": 1})
        else:
            out[-1]["last"] = sample["frame"]
            out[-1]["samples"] += 1
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log", type=Path, help="runtime stderr log with GOW3_FRAME_MAP=1")
    parser.add_argument("--list", action="store_true", help="print one line per sample")
    parser.add_argument("--frames", help="report the state of these frames (comma separated)")
    args = parser.parse_args(argv[1:])

    if not args.log.is_file():
        print(f"ERROR: {args.log} does not exist", file=sys.stderr)
        return 1
    samples = parse(args.log.read_text(errors="replace"))
    if not samples:
        print(f"ERROR: no 'FrameMap:' lines in {args.log}", file=sys.stderr)
        print("Hint: run the runtime with GOW3_FRAME_MAP=1.", file=sys.stderr)
        return 1

    print(f"{args.log.name}: {len(samples)} samples, frames "
          f"{samples[0]['frame']}..{samples[-1]['frame']}")
    print("\nstate regions (frame numbers are the sampled ones):")
    for region in regions(samples):
        print(f"  {region['state']:6s} frames {region['first']:5d}..{region['last']:5d} "
              f"({region['samples']} samples)")

    if args.list:
        print("\nper sample:")
        for s in samples:
            print(f"  {s['frame']:6d} mean={s['mean']:6.1f} {classify(s['mean'], spread(s['grid'])):6s} "
                  f"draws={s['draws']}")

    if args.frames:
        wanted = [int(part) for part in args.frames.split(",") if part.strip()]
        by_frame = {s["frame"]: s for s in samples}
        print("\nrequested frames:")
        missing = 0
        for frame in wanted:
            sample = by_frame.get(frame)
            if sample is None:
                # Nearest sample, so a caller does not need to know the sampling stride.
                nearest = min(samples, key=lambda s: abs(s["frame"] - frame))
                print(f"  {frame:6d} not sampled; nearest is {nearest['frame']} "
                      f"({nearest['frame'] - frame:+d}) -> "
                      f"{classify(nearest['mean'], spread(nearest['grid']))}")
                missing += 1
                continue
            print(f"  {frame:6d} -> {classify(sample['mean'], spread(sample['grid'])):6s} "
                  f"mean={sample['mean']:.1f} grid={sample['grid']}")
        if missing:
            print(f"  ({missing} of {len(wanted)} frames were not sampled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
