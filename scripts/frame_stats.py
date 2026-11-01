"""Classify a raw RGBA frame captured with GOW3_FRAME_DUMP_AT.

Answers the only question that matters about a capture: is there image content, where is it, and
does it change between frames? Pure stdlib so it runs anywhere the port builds.

Usage:
    python scripts/frame_stats.py <frame.raw> [<width> <height>] [--diff <other.raw>]

The width/height default to 1920x1080 and are checked against the file size, because a wrong
guess would silently report "no content" on a valid capture. They can also be parsed from the
file name written by the port (``output_000_1920x1080.raw``).
"""
from __future__ import annotations

import collections
import hashlib
import re
import sys
from pathlib import Path

DEFAULT_SIZE = (1920, 1080)
# Sampling stride for the whole-frame statistics: every Nth pixel keeps a 1080p frame fast while
# still covering the screen. The bounding box uses the same stride.
STRIDE = 4


def size_from_name(path: Path) -> tuple[int, int] | None:
    match = re.search(r"_(\d+)x(\d+)\.raw$", path.name)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def analyse(data: bytes, width: int, height: int) -> dict:
    """Return non-black pixel count, bounding box and dominant colours."""
    expected = width * height * 4
    if len(data) < expected:
        raise ValueError(f"frame is {len(data)} bytes, need {expected} for {width}x{height} RGBA")
    counts: collections.Counter[bytes] = collections.Counter()
    non_black = 0
    min_x, max_x, min_y, max_y = width, -1, height, -1
    for y in range(0, height, STRIDE):
        row = y * width * 4
        for x in range(0, width, STRIDE):
            at = row + x * 4
            rgb = data[at:at + 3]
            counts[rgb] += 1
            if rgb != b"\x00\x00\x00":
                non_black += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    sampled = counts.total()
    box = None if max_x < 0 else (min_x, min_y, max_x, max_y)
    return {
        "width": width,
        "height": height,
        "sampled_pixels": sampled,
        "non_black_pixels": non_black,
        "non_black_percent": 100.0 * non_black / sampled if sampled else 0.0,
        "content_box": box,
        "top_colours": [(rgb.hex(), count) for rgb, count in counts.most_common(6)],
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def differing_pixels(a: bytes, b: bytes) -> tuple[int, float]:
    limit = min(len(a), len(b))
    diff = 0
    total = limit // 4
    for at in range(0, limit, 4):
        if a[at:at + 3] != b[at:at + 3]:
            diff += 1
    return diff, (100.0 * diff / total if total else 0.0)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    diff_path = None
    if "--diff" in argv:
        index = argv.index("--diff")
        if index + 1 >= len(argv):
            print("--diff needs a path", file=sys.stderr)
            return 2
        diff_path = Path(argv[index + 1])
    if not args:
        print(__doc__, file=sys.stderr)
        return 2

    path = Path(args[0])
    if len(args) >= 3:
        width, height = int(args[1]), int(args[2])
    elif (guessed := size_from_name(path)) is not None:
        width, height = guessed
    else:
        width, height = DEFAULT_SIZE
    data = path.read_bytes()

    try:
        stats = analyse(data, width, height)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Hint: pass the real width and height as arguments.", file=sys.stderr)
        return 1

    print(f"{path}: {stats['width']}x{stats['height']}  sha256={stats['sha256'][:16]}")
    print(f"  non-black: {stats['non_black_pixels']} of {stats['sampled_pixels']} sampled "
          f"({stats['non_black_percent']:.2f}%)")
    box = stats["content_box"]
    print(f"  content box: {box if box else 'none (frame is entirely black)'}")
    for rgb, count in stats["top_colours"]:
        print(f"    #{rgb}  {count}")

    if diff_path is not None:
        other = diff_path.read_bytes()
        count, percent = differing_pixels(data, other)
        print(f"  vs {diff_path.name}: {count} pixels differ ({percent:.2f}%)")
        print("  => the image changes between frames" if count else "  => identical frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
