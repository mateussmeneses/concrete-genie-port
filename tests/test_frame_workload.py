"""Tests for scripts/frame_workload.py.

The tool exists to stop a specific misreading: a screen that is white but costs full scene work is
a frozen present, not a loading screen or a menu. These tests pin that distinction, because a
regression here would let the wrong conclusion back into the docs.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import frame_workload  # noqa: E402

SCENE_GRID = "[[77.8,163.9,50.7],[96.0,166.3,79.2],[36.8,79.5,23.6]]"
WHITE_GRID = "[[255.0,255.0,255.0],[252.5,239.1,254.2],[253.2,220.2,253.2]]"


def line(frame: int, grid: str, draws: int) -> str:
    return (f"FrameMap: frame {frame} grid={grid} draws={draws} submissions=0\n")


def samples(text: str) -> list[dict]:
    import frame_states

    return frame_states.parse(text)


class WorkloadTests(unittest.TestCase):
    def test_scene_with_changing_images_is_live_rendering(self):
        # Vary one cell per sample: a live scene never repeats the exact same grid.
        text = "".join(
            line(10 * i, f"[[77.8,163.9,{50.0 + i}],[96.0,166.3,79.2],[36.8,79.5,23.6]]", 36000)
            for i in range(20)
        )
        rows = frame_workload.report(samples(text))
        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0]["distinct"], 3)
        self.assertEqual(frame_workload.verdict(rows[0]), "live rendering")

    def test_white_screen_with_scene_workload_is_a_frozen_present(self):
        # The measured boot-140 signature: full scene draw count, one identical image.
        text = "".join(line(10 * i, WHITE_GRID, 36148) for i in range(20))
        rows = frame_workload.report(samples(text))
        self.assertEqual(rows[0]["distinct"], 1)
        self.assertEqual(frame_workload.verdict(rows[0]),
                         "FROZEN PRESENT: full scene workload, one image repeated")

    def test_quiet_white_screen_is_not_called_frozen(self):
        # A real loading screen does little GPU work; it must not be reported as a frozen present.
        text = "".join(line(10 * i, WHITE_GRID, 5) for i in range(20))
        rows = frame_workload.report(samples(text))
        self.assertEqual(frame_workload.verdict(rows[0]), "quiet screen: little GPU work")

    def test_frozen_verdict_needs_enough_samples(self):
        text = "".join(line(10 * i, WHITE_GRID, 36148) for i in range(3))
        rows = frame_workload.report(samples(text))
        self.assertNotIn("FROZEN PRESENT", frame_workload.verdict(rows[0]))

    def test_draws_mean_matches_the_measured_values(self):
        text = line(0, WHITE_GRID, 36000) + line(10, WHITE_GRID, 36296)
        rows = frame_workload.report(samples(text))
        self.assertAlmostEqual(rows[0]["draws_mean"], 36148, places=0)

    def test_missing_log_fails_loudly(self):
        self.assertEqual(frame_workload.main(["frame_workload.py", str(ROOT / "absent.log")]), 1)

    def test_log_without_samples_fails(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.log"
            path.write_text("nothing\n")
            self.assertEqual(frame_workload.main(["frame_workload.py", str(path)]), 1)


if __name__ == "__main__":
    unittest.main()
