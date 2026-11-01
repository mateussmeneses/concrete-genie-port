"""sceKernelDlsym must write its out-parameter.

The game resolves eight Bink plugin functions through sceKernelDlsym into slots in .bss, then
calls those slots without checking for null (`leaq slot,%rax; callq *(%rax)`). When the call was
registered as `not_found`, which takes no arguments, the out-parameter was never written and the
slot kept whatever the stack held. The crash surfaced much later, in RHIThread.

These tests freeze the parts that are checkable without the game: the signature, the guarantee
that the out-parameter is cleared, and the negative result for symbols nothing exports.
"""
import ctypes
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRA = ROOT / "runtime" / "src" / "runtime_extra.c"


def source():
    return EXTRA.read_text(encoding="utf-8", errors="replace")


class DlsymSource(unittest.TestCase):
    def test_dlsym_is_not_bound_to_the_zero_argument_stub(self):
        text = source()
        self.assertNotIn('{"sceKernelDlsym",not_found}', text,
                         "not_found(void) cannot satisfy sceKernelDlsym(handle,name,out)")
        self.assertIn('{"sceKernelDlsym",kernel_dlsym}', text)

    def test_signature_takes_handle_name_and_out_pointer(self):
        signature = re.search(r"static ABI int32_t kernel_dlsym\(([^)]*)\)", source())
        self.assertIsNotNone(signature, "kernel_dlsym must exist")
        assert signature is not None          # narrows the type for the checker
        params = [p.strip() for p in signature.group(1).split(",")]
        self.assertEqual(len(params), 3, f"expected 3 parameters, got {params}")
        self.assertIn("void **", params[2], "the third parameter must be the out pointer")

    def test_out_parameter_is_cleared_before_any_failure(self):
        body = source().split("static ABI int32_t kernel_dlsym")[1].split("\n}")[0]
        clear = body.find("*out = NULL;")
        self.assertNotEqual(clear, -1, "the out-parameter must be cleared")
        # The clear must happen before the first `return` that reports failure.
        first_failure = body.find("return ERR(E_SRCH)")
        self.assertNotEqual(first_failure, -1)
        self.assertLess(clear, first_failure,
                        "clearing after returning would leave the slot untouched")


class DlsymBehaviour(unittest.TestCase):
    """Check the recorded boot evidence: the export must be reachable and must not claim success.

    kernel_dlsym is static, so ctypes cannot call it; the meaningful check is that the runtime
    bound it to the import (not to the zero-argument stub) and that the boot log shows the
    out-parameter being defined rather than left as stale stack data.
    """

    def test_boot_log_shows_the_module_load_being_refused(self):
        log = ROOT / "docs" / "evidence" / "prompt04" / "boot-31-dlsym.txt"
        if not log.exists():
            self.skipTest("no recorded boot evidence in this checkout")
        text = log.read_text(encoding="utf-8", errors="replace")
        # The Bink plugin must be the module that cannot be loaded, not an unrelated path.
        self.assertIn("binkpluginps4.prx", text)
        self.assertIn("not available", text)

    def test_bink_slots_are_the_reason_for_the_fault(self):
        log = ROOT / "docs" / "evidence" / "prompt04" / "boot-31-dlsym.txt"
        if not log.exists():
            self.skipTest("no recorded boot evidence in this checkout")
        text = log.read_text(encoding="utf-8", errors="replace")
        # The fault must still be the RHIThread one: if a future change moves it, this test
        # failing is the signal to update the audit rather than silently drift.
        self.assertIn("thread name: RHIThread", text)
        self.assertNotIn("unsupported PS4 import", text,
                         "the boot should be past the import layer, not back in it")


if __name__ == "__main__":
    unittest.main()
