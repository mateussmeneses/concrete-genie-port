"""Bink plugin resolution and honest "no video" semantics.

The game resolves 23 Bink entry points with sceKernelDlsym(0, "BinkPlugin...", &slot) and calls
those slots from the render path WITHOUT a null check. Two separate defects used to make every
lookup fail, and both are frozen here:

1. sceKernelDlsym was bound to a zero-argument stub, so the out-pointer was never written.
2. runtime_lookup() maps a NID through the import-name table before comparing, so a plain name
   such as "BinkPluginInit" could never match. Plain names need a direct comparison.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BINK = ROOT / "runtime" / "src" / "runtime_bink.c"
EXTRA = ROOT / "runtime" / "src" / "runtime_extra.c"


def bink_source():
    return BINK.read_text(encoding="utf-8", errors="replace")


def extra_source():
    return EXTRA.read_text(encoding="utf-8", errors="replace")


class BinkNamesAreFrozen(unittest.TestCase):
    """Every name the guest asks for at runtime must exist in the export table."""

    # Measured from the Dlsym trace (docs/evidence/prompt04/boot-37-dlsym-slots.txt).
    REQUESTED = (
        "BinkPluginInit", "BinkPluginShutdown", "BinkPluginOpen", "BinkPluginClose",
        "BinkPluginInfo", "BinkPluginGoto", "BinkPluginProcessBinks", "BinkPluginLimitSpeakers",
        "BinkPluginLoop", "BinkPluginPause", "BinkPluginDraw", "BinkPluginSetPerFrameInfo",
        "BinkPluginScheduleToTexture", "BinkPluginScheduleOverlay", "BinkPluginAllScheduled",
        "BinkPluginIOPause", "BinkPluginTurnOnGPUAssist", "BinkPluginError", "BinkPluginVolume",
        "BinkPluginSpeakerVolumes", "BinkPluginSetHdrSettings", "BinkPluginSetAlphaSettings",
        "BinkPluginSetPath",
    )

    def test_all_23_requested_names_are_exported(self):
        text = bink_source()
        exported = set(re.findall(r'\{"(BinkPlugin[A-Za-z]+)"', text))
        missing = [n for n in self.REQUESTED if n not in exported]
        self.assertEqual(missing, [], f"these names would still fault: {missing}")
        self.assertEqual(len(self.REQUESTED), 23, "the measured request count changed")

    def test_no_name_is_exported_twice(self):
        exported = re.findall(r'\{"(BinkPlugin[A-Za-z]+)"', bink_source())
        self.assertEqual(len(exported), len(set(exported)), "duplicate export would shadow one")


class PlainNamesNeedDirectMatch(unittest.TestCase):
    def test_bink_lookup_does_not_use_the_nid_macro(self):
        # RUNTIME_LOOKUP -> runtime_lookup(), which resolves a NID first and returns 0 for a
        # plain name before comparing. That is exactly the bug.
        body = bink_source().split("uintptr_t runtime_bink_resolve")[1]
        self.assertNotIn("RUNTIME_LOOKUP", body,
                         "plain names must be compared directly, not through the NID table")
        self.assertIn("strcmp", bink_source())

    def test_dlsym_consults_the_name_table_first(self):
        body = extra_source().split("static ABI int32_t kernel_dlsym")[1].split("\n}")[0]
        self.assertIn("runtime_bink_resolve", body,
                      "dlsym must check plain-name tables before the NID chain")


class NoVideoIsNotFakeSuccess(unittest.TestCase):
    def test_opening_a_video_reports_no_video(self):
        text = bink_source()
        open_body = text.split("static ABI int32_t plugin_open")[1].split("\n}")[0]
        self.assertIn("BINK_NO_VIDEO", open_body,
                      "a fabricated handle would make the game believe a movie loaded")
        self.assertNotIn("return 1;", open_body)

    def test_opening_is_reported_in_the_log(self):
        # A silent refusal would leave an empty screen with no explanation in the log.
        open_body = bink_source().split("static ABI int32_t plugin_open")[1].split("\n}")[0]
        self.assertIn("fprintf", open_body)

    def test_frame_scheduling_does_not_claim_a_frame(self):
        body = bink_source().split("static ABI int32_t plugin_set_per_frame_info")[1].split("\n}")[0]
        self.assertNotIn("return 0;", body,
                         "claiming 0 here would assert a frame was scheduled with no video")


class SupportsFilesTheRuntimeClaims(unittest.TestCase):
    def test_bink_source_is_present(self):
        self.assertTrue(BINK.exists(), "runtime_bink.c must exist")
        self.assertIn("runtime_bink_resolve", bink_source())


if __name__ == "__main__":
    unittest.main()
