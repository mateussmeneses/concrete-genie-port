"""Tests for scripts/state_anchored_run.py.

The driver exists to stop a class of mistake that already happened twice: applying input at a
frame index that is not the state the test assumes. These tests cover the parts that can silently
get that wrong - the incremental log reader and the state-run counter - plus the guard that catches
a pad path mismatch, which makes a run look successful while no input reaches the guest.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import frame_states  # noqa: E402,F401 (imported for the docstring's contract; the watcher uses it)

_spec = importlib.util.spec_from_file_location("state_anchored_run",
                                               ROOT / "scripts" / "state_anchored_run.py")
assert _spec is not None and _spec.loader is not None
state_anchored_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(state_anchored_run)

# Real lines, so the format under test is the one the presenter writes.
SCENE = "FrameMap: frame {f} grid=[[77.8,163.9,50.7],[96.0,166.3,79.2],[36.8,79.5,23.6]]" \
        " draws=36162 submissions=0\n"
BLACK = "FrameMap: frame {f} grid=[[0.0,0.0,0.0],[0.0,0.0,0.0],[0.0,0.0,0.0]]" \
        " draws=5 submissions=0\n"
BRIGHT = "FrameMap: frame {f} grid=[[250.4,255.0,251.8],[252.2,239.1,254.2],[253.1,220.2,253.2]]" \
         " draws=36100 submissions=0\n"


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "run.log"
        self.log.write_text("")

    def tearDown(self):
        self.tmp.cleanup()

    def append(self, text: str) -> None:
        with self.log.open("a") as handle:
            handle.write(text)

    def test_counts_a_contiguous_run_and_reports_its_first_frame(self):
        watcher = state_anchored_run.StateWatcher(self.log)
        self.append(BLACK.format(f=1) + BLACK.format(f=6))
        watcher.poll()
        self.assertEqual(watcher.run_state, "black")
        self.assertEqual(watcher.run_length, 2)
        self.append(SCENE.format(f=11) + SCENE.format(f=16) + SCENE.format(f=21))
        watcher.poll()
        self.assertEqual(watcher.run_state, "scene")
        self.assertEqual(watcher.run_start, 11)
        self.assertEqual(watcher.run_length, 3)

    def test_state_change_resets_the_run(self):
        watcher = state_anchored_run.StateWatcher(self.log)
        self.append(SCENE.format(f=1) + SCENE.format(f=6))
        watcher.poll()
        self.assertEqual(watcher.run_length, 2)
        self.append(BRIGHT.format(f=11))
        watcher.poll()
        self.assertEqual(watcher.run_state, "bright")
        self.assertEqual(watcher.run_length, 1)
        self.assertEqual(watcher.run_start, 11)

    def test_reads_incrementally_without_recounting(self):
        watcher = state_anchored_run.StateWatcher(self.log)
        self.append(SCENE.format(f=1))
        watcher.poll()
        self.assertEqual(watcher.run_length, 1)
        watcher.poll()  # no new data: must not add to the run
        self.assertEqual(watcher.run_length, 1)
        self.append(SCENE.format(f=6))
        watcher.poll()
        self.assertEqual(watcher.run_length, 2)

    def test_partial_trailing_line_is_held_until_complete(self):
        watcher = state_anchored_run.StateWatcher(self.log)
        line = SCENE.format(f=1)
        self.append(line[:40])
        watcher.poll()
        self.assertEqual(watcher.run_length, 0)
        self.append(line[40:])
        watcher.poll()
        self.assertEqual(watcher.run_state, "scene")
        self.assertEqual(watcher.run_length, 1)

    def test_missing_log_is_not_an_error(self):
        watcher = state_anchored_run.StateWatcher(Path(self.tmp.name) / "absent.log")
        self.assertIsNone(watcher.poll())
        self.assertEqual(watcher.run_length, 0)


class PadPathGuardTests(unittest.TestCase):
    """A pad path mismatch makes every pad read show zero buttons while the run looks fine."""

    def run_main(self, argv, env_pad=None):
        import os

        old = os.environ.get("GOW3_PAD_FILE")
        if env_pad is None:
            os.environ.pop("GOW3_PAD_FILE", None)
        else:
            os.environ["GOW3_PAD_FILE"] = env_pad
        try:
            return state_anchored_run.main(argv)
        finally:
            if old is None:
                os.environ.pop("GOW3_PAD_FILE", None)
            else:
                os.environ["GOW3_PAD_FILE"] = old

    def test_mismatched_pad_path_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            apply_file = tmp_dir / "apply.txt"
            apply_file.write_text("cross\n")
            log = tmp_dir / "run.log"
            argv = ["state_anchored_run.py", "--log", str(log),
                    "--pad-file", str(tmp_dir / "live.txt"),
                    "--apply", str(apply_file), "--", "runtime.exe"]
            code = self.run_main(argv, env_pad=str(tmp_dir / "other.txt"))
            self.assertEqual(code, 2)

    def test_unset_pad_env_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            apply_file = tmp_dir / "apply.txt"
            apply_file.write_text("cross\n")
            argv = ["state_anchored_run.py", "--log", str(tmp_dir / "run.log"),
                    "--pad-file", str(tmp_dir / "live.txt"),
                    "--apply", str(apply_file), "--", "runtime.exe"]
            self.assertEqual(self.run_main(argv, env_pad=None), 2)

    def test_empty_apply_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            apply_file = tmp_dir / "apply.txt"
            apply_file.write_text("   \n")
            live = tmp_dir / "live.txt"
            argv = ["state_anchored_run.py", "--log", str(tmp_dir / "run.log"),
                    "--pad-file", str(live), "--apply", str(apply_file), "--", "runtime.exe"]
            self.assertEqual(self.run_main(argv, env_pad=str(live)), 2)

    def test_missing_separator_is_refused(self):
        self.assertEqual(state_anchored_run.main(["state_anchored_run.py", "--log", "x.log"]), 2)


if __name__ == "__main__":
    unittest.main()
