"""Run the runtime and apply scripted input at a *state*, not at a frame index.

Why this exists: the frame a state begins on differs between runs (the boot stops at a different
point each time), so "press R2 at frame 3000" can land in a menu, a loading fade or the 3D scene.
Two earlier investigations were misread that way. This driver watches the ``FrameMap:`` samples the
runtime already writes, waits until the requested state is actually on screen, holds for a settle
margin, and only then writes the pad file. Every run then applies the input at the same observed
state, which is what makes the comparison meaningful.

It does not interpret the game. "scene" is a luminance-profile description of the presented image
(see scripts/frame_states.py), not a claim that the player controls anything.

Usage:
    python scripts/state_anchored_run.py --log run.log -- \
        runtime/out/gpu/cg-runtime.exe boot-linked.bin --app0 <dump> [...]

    python scripts/state_anchored_run.py --log run.log --pad-file pad_live.txt \
        --at-state scene --settle 40 --before pad_idle.txt --apply pad_pause.txt \
        -- runtime/out/gpu/cg-runtime.exe ...

Options must come before the ``--``; everything after it is the runtime command line.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import frame_states  # noqa: E402


class StateWatcher:
    """Incremental reader of a running runtime log.

    Kept as an object because the state counter must survive across polls: re-parsing from the
    start each time would also re-count a run of samples that is no longer contiguous, which is
    exactly what ``settle`` is supposed to prevent.
    """

    def __init__(self, log_path: Path) -> None:
        self.path = log_path
        self.offset = 0
        self.buffer = ""
        self.run_state: str | None = None
        self.run_start: int | None = None
        self.run_length = 0

    def poll(self) -> int | None:
        """Read new samples; return the first frame of a settled run, or None."""
        if not self.path.is_file():
            return None
        with self.path.open("r", errors="replace") as handle:
            handle.seek(self.offset)
            chunk = handle.read()
            self.offset = handle.tell()
        # Keep any partial trailing line for the next poll instead of dropping it.
        data = self.buffer + chunk
        cut = data.rfind("\n")
        if cut < 0:
            self.buffer = data
            return None
        self.buffer = data[cut + 1:]
        for sample in frame_states.parse(data[:cut]):
            current = frame_states.classify(sample["mean"], frame_states.spread(sample["grid"]))
            if current != self.run_state:
                self.run_state = current
                self.run_start = sample["frame"]
                self.run_length = 1
            else:
                self.run_length += 1
        return None


def write_pad(path: Path, text: str) -> None:
    """Replace the pad file. The runtime re-reads it when the size or mtime changes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n")


def main(argv: list[str]) -> int:
    if "--" not in argv:
        print(__doc__, file=sys.stderr)
        return 2
    split = argv.index("--")
    parser = argparse.ArgumentParser(description="Apply input at an observed game state.")
    parser.add_argument("--log", type=Path, required=True, help="runtime stderr goes here")
    parser.add_argument("--at-state", default="scene",
                        help="state to anchor to: black, fade, bright or scene (default scene)")
    parser.add_argument("--settle", type=int, default=40,
                        help="samples of the state required before acting (default 40)")
    parser.add_argument("--pad-file", type=Path, required=True,
                        help="the live pad file; must be the path GOW3_PAD_FILE points to")
    parser.add_argument("--before", type=Path,
                        help="text held before the anchor is reached (default: empty input)")
    parser.add_argument("--apply", type=Path, required=True, dest="apply_path",
                        help="text written to --pad-file once the state is reached")
    parser.add_argument("--timeout", type=float, default=300.0,
                        help="seconds to wait for the state before giving up (default 300)")
    args = parser.parse_args(argv[1:split])
    command = argv[split + 1:]
    if not command:
        print("ERROR: nothing after '--': give the runtime command line", file=sys.stderr)
        return 2

    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text("")  # start clean so the poller cannot read a stale run
    pad_path = args.pad_file
    # Read the two texts before touching the pad file: it is the live channel, so writing the
    # "before" text to it would otherwise destroy the text meant to be applied later.
    before_text = args.before.read_text() if args.before else ""
    after_text = args.apply_path.read_text()
    if not after_text.strip():
        print(f"ERROR: {args.apply_path} is empty; it must list the input to apply", file=sys.stderr)
        return 2
    expected = str(pad_path.resolve())
    actual = os.environ.get("GOW3_PAD_FILE", "")
    if not actual or Path(actual).resolve() != Path(expected):
        # Without this the run looks successful while no input ever reaches the guest: the script
        # writes one file and the runtime reads another, so every pad read shows zero buttons.
        print(f"ERROR: GOW3_PAD_FILE is '{actual or '<unset>'}' but this script writes "
              f"'{expected}'.\nSet GOW3_PAD_FILE to the same path.", file=sys.stderr)
        return 2
    write_pad(pad_path, before_text)

    def note(text: str) -> None:
        """Append a decision to the log so the evidence carries its own provenance."""
        print(text, file=sys.stderr)
        with args.log.open("a", errors="replace") as handle:
            handle.write(text + "\n")

    print(f"state-anchored run: waiting for state '{args.at_state}' "
          f"({args.settle} samples) in {args.log}", file=sys.stderr)
    started = time.monotonic()
    with args.log.open("w", errors="replace") as log_handle:
        process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT)
        deadline = started + args.timeout
        watcher = StateWatcher(args.log)
        anchor = None
        died = False
        while time.monotonic() < deadline:
            watcher.poll()
            if watcher.run_state == args.at_state and watcher.run_length >= args.settle:
                anchor = watcher.run_start
                break
            # A process that has already exited cannot reach the state; reporting a timeout
            # would hide a crash behind a plausible-sounding message.
            if process.poll() is not None:
                died = True
                break
            time.sleep(0.25)
        if anchor is None:
            if died:
                note(f"ERROR: runtime exited with {process.returncode} before reaching state "
                     f"'{args.at_state}'; input NOT applied")
            else:
                note(f"ERROR: state '{args.at_state}' not reached within {args.timeout:.0f}s "
                     f"(last state '{watcher.run_state}' after {watcher.run_length} samples); "
                     f"input NOT applied")
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
            return 1
        elapsed = time.monotonic() - started
        note(f"ANCHOR: state '{args.at_state}' reached at frame {anchor} "
             f"({elapsed:.1f}s), applying {args.apply_path}")
        write_pad(pad_path, after_text)
        code = process.wait()
        note(f"ANCHOR: runtime exited with {code}")
        return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
