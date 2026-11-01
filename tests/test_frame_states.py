"""Tests for scripts/frame_states.py (the GOW3_FRAME_MAP log reader).

These lock in the parts that make the map trustworthy: the line format written by
vk_presenter.cpp, and the state thresholds that the paint/pause tests depend on. Nothing here
needs a game dump.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import frame_states  # noqa: E402

# Lines copied from a real run so the parser is tested against the format the presenter writes,
# not a convenient re-imagining of it.
REAL_LINES = """\
GPU [Render.Vulkan] <Warning> vk_instance.cpp:309 operator(): Extension VK_AMD_gcn_shader unavailable.
Present: PrepareFrame #1 (addr=0x4000000000, 1920x1080, pitch=1920)
FrameMap: frame 1 grid=[[0.0,0.0,0.0],[0.0,0.0,0.0],[0.0,0.0,0.0]] draws=5 submissions=0
FrameMap: frame 601 grid=[[17.2,36.4,11.3],[21.2,37.0,17.6],[7.9,14.2,4.8]] draws=36199 submissions=0
FrameMap: frame 1201 grid=[[77.8,163.9,50.7],[96.0,166.3,79.2],[36.8,79.5,23.6]] draws=36162 submissions=0
FrameMap: 1800 samples, mean cost 3.09 ms/sample (readback included)
FrameMap: frame 9001 grid=[[250.4,255.0,251.8],[252.2,239.1,254.2],[253.1,220.2,253.2]] draws=36131 submissions=0
"""


class ParseTests(unittest.TestCase):
    def test_parses_every_sample_and_ignores_other_lines(self):
        samples = frame_states.parse(REAL_LINES)
        self.assertEqual([s["frame"] for s in samples], [1, 601, 1201, 9001])

    def test_summary_line_is_not_mistaken_for_a_sample(self):
        # "FrameMap: 1800 samples, mean cost ..." has no grid; a loose regex would swallow it.
        samples = frame_states.parse(REAL_LINES)
        self.assertNotIn(1800, [s["frame"] for s in samples])

    def test_grid_is_read_row_major(self):
        sample = frame_states.parse(REAL_LINES)[2]
        self.assertEqual(sample["grid"][0], [77.8, 163.9, 50.7])
        self.assertEqual(sample["grid"][1], [96.0, 166.3, 79.2])
        self.assertEqual(sample["grid"][2], [36.8, 79.5, 23.6])
        self.assertAlmostEqual(sample["mean"], 86.0, places=1)
        self.assertEqual(sample["draws"], 36162)

    def test_empty_log_yields_no_samples(self):
        self.assertEqual(frame_states.parse("GPU: nothing here\n"), [])


class ClassifyTests(unittest.TestCase):
    """The thresholds must keep the three states measured so far apart.

    The grid fixtures are the real values measured in the runs recorded in docs/TEST_MATRIX.md.
    """

    # 3D scene, top row 77.8/163.9/50.7 and bottom row 36.8/79.5/23.6: structured, ~86 mean.
    SCENE = [[77.8, 163.9, 50.7], [96.0, 166.3, 79.2], [36.8, 79.5, 23.6]]
    # OPTIONS screen: 92.6% white, top row 250.4/255.0/251.8.
    UI = [[250.4, 255.0, 251.8], [252.2, 239.1, 254.2], [253.1, 220.2, 253.2]]
    # A loading fade: uniform to within 1.3 across the whole grid.
    FADE = [[70.7, 72.0, 71.1], [71.9, 72.0, 72.0], [72.0, 72.0, 72.0]]

    def test_black_boot_frames(self):
        self.assertEqual(frame_states.classify(0.0, 0.0), "black")
        self.assertEqual(frame_states.classify(4.9, 0.0), "black")

    def test_dark_scene_from_the_paint_runs(self):
        self.assertEqual(frame_states.classify(frame_states.mean_of(self.SCENE),
                                               frame_states.spread(self.SCENE)), "scene")

    def test_bright_ui_from_the_options_run(self):
        self.assertEqual(frame_states.classify(frame_states.mean_of(self.UI),
                                               frame_states.spread(self.UI)), "bright")

    def test_uniform_fill_is_not_a_scene(self):
        # This is the case the first version of the classifier got wrong: 71.7 mean is also the
        # scene's mean, and only the spread says it is a flat wash.
        grid = self.FADE
        self.assertAlmostEqual(frame_states.mean_of(grid), 71.7, places=1)
        self.assertEqual(frame_states.classify(frame_states.mean_of(grid),
                                               frame_states.spread(grid)), "fade")

    def test_scene_and_fade_share_a_mean_but_not_a_state(self):
        scene = frame_states.mean_of(self.SCENE)
        fade = frame_states.mean_of(self.FADE)
        self.assertLess(abs(scene - fade), 20.0)  # close in brightness
        self.assertNotEqual(frame_states.classify(scene, frame_states.spread(self.SCENE)),
                            frame_states.classify(fade, frame_states.spread(self.FADE)))


class RegionTests(unittest.TestCase):
    def test_regions_collapse_runs_and_keep_bounds(self):
        samples = frame_states.parse(REAL_LINES)
        regions = frame_states.regions(samples)
        # Frame 601 is a dim uniform wash, so it reads as a fade rather than a scene.
        self.assertEqual([r["state"] for r in regions], ["black", "fade", "scene", "bright"])
        self.assertEqual((regions[0]["first"], regions[0]["last"]), (1, 1))
        self.assertEqual((regions[2]["first"], regions[2]["last"]), (1201, 1201))
        self.assertEqual(regions[3]["samples"], 1)


class CommandLineTests(unittest.TestCase):
    def test_missing_log_fails_loudly(self):
        code = frame_states.main(["frame_states.py", str(ROOT / "does-not-exist.log")])
        self.assertEqual(code, 1)

    def test_log_without_samples_fails_with_a_hint(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.log"
            path.write_text("GPU: no map here\n")
            self.assertEqual(frame_states.main(["frame_states.py", str(path)]), 1)

    def test_frames_report_uses_the_nearest_sample(self):
        import contextlib
        import io
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.log"
            path.write_text(REAL_LINES)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = frame_states.main(["frame_states.py", str(path), "--frames", "1199"])
        self.assertEqual(code, 0)
        # 1199 is between samples 601 and 1201; 1201 is nearer and must be named as such.
        self.assertIn("nearest is 1201", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
