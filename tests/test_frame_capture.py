"""Frame-capture knobs must stay usable, and captured frames must be classifiable.

The capture path failed three times for reasons that had nothing to do with the renderer, so the
parts that are checkable without the game are frozen here:

1. `GOW3_FRAME_DUMP_AT=N` is required, because the cooperation-free capture is the only one that
   works in an automated run.
2. The decision to dump must not depend on the dump counter itself (that was a circular condition
   which kept the index at 0 forever).
3. The branch that actually presents (the upscaled display) must contain dump code; it had none.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESENTER = ROOT / "runtime" / "gpu" / "shadps4" / "video_core" / "renderer_vulkan" / "vk_presenter.cpp"


def source():
    return PRESENTER.read_text(encoding="utf-8", errors="replace")


class CaptureKnobsExist(unittest.TestCase):
    def test_direct_index_capture_is_available(self):
        text = source()
        self.assertIn("GOW3_FRAME_DUMP_AT", text,
                      "an automated run needs a capture trigger that needs no cooperating process")

    def test_sync_write_is_available(self):
        self.assertIn("GOW3_DUMP_SYNC", source(),
                      "deferred writes never run when the process is ended by a timeout")

    def test_capture_decision_uses_a_presented_frame_counter(self):
        text = source()
        # The trigger must be compared against a counter that advances on every presented frame,
        # not against frame_dump_index (which only advances after a dump already happened).
        match = re.search(r"if \(frame_dump_at > 0 && ([A-Za-z_]+)", text)
        self.assertIsNotNone(match, "the capture trigger comparison must exist")
        assert match is not None
        self.assertEqual(match.group(1), "presented_frames",
                         "comparing against frame_dump_index is circular and never fires")

    def test_presented_frames_increments_unconditionally(self):
        text = source()
        # The increment must not sit inside a `if (frame_dump)` block.
        idx = text.index("++presented_frames;")
        preceding = text[:idx].rsplit("\n", 40)
        window = "\n".join(preceding)
        self.assertNotIn("if (frame_dump) {", window.split("static u64 presented_frames")[-1],
                         "the counter must count every frame, not only dumped ones")


class UpscaledBranchHasCapture(unittest.TestCase):
    def test_upscaled_branch_dumps(self):
        text = source()
        start = text.index("if (upscaled) {")
        # The upscaled branch ends before the post-process pass.
        end = text.index("pp_pass.Render", start)
        branch = text[start:end]
        self.assertIn("frame_dump", branch,
                      "the upscaled display is what the swapchain blits; it had no capture code")
        self.assertIn("DumpRaw", branch)


class FrameAnalysisTool(unittest.TestCase):
    def test_analyser_reports_content_and_animation(self):
        """The analysis helpers must classify a frame without an image library."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "frame_stats", ROOT / "scripts" / "frame_stats.py")
        if spec is None or spec.loader is None:
            self.skipTest("scripts/frame_stats.py is absent")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # A frame that is entirely black except one white pixel.
        w = h = 4
        data = bytearray(w * h * 4)
        data[0:4] = b"\xff\xff\xff\xff"
        stats = module.analyse(bytes(data), w, h)
        self.assertEqual(stats["non_black_pixels"], 1)
        self.assertEqual(stats["width"], w)
        self.assertIn("top_colours", stats)


if __name__ == "__main__":
    unittest.main()
