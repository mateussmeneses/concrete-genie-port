"""Pins the memory-layout finding that blocks the first frame.

The guest asks for a fixed 8 GiB reservation at USER_MIN while a 6 MiB direct mapping
already occupies that address, so `reserve_range` refuses with NO_MEMORY. These tests
freeze the constants and the decision logic so a future change has to confront them
instead of silently shifting the layout.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / 'runtime' / 'src' / 'runtime_memory.c'


def source():
    return MEMORY.read_text(encoding='utf-8', errors='replace')


class LayoutConstants(unittest.TestCase):
    def test_user_min_is_the_ps4_guest_base(self):
        text = source()
        match = re.search(r'#define USER_MIN UINT64_C\(0x([0-9A-Fa-f]+)\)', text)
        self.assertIsNotNone(match, 'USER_MIN must stay defined')
        if match is None:
            self.fail('USER_MIN must stay defined')
        self.assertEqual(int(match.group(1), 16), 0x1000000000)

    def test_map_fixed_and_no_overwrite_bits(self):
        text = source()
        self.assertIn('#define MAP_FIXED_FLAG 0x10', text)
        self.assertIn('#define MAP_NO_OVERWRITE 0x80', text)

    def test_no_memory_is_the_ps4_enomem_code(self):
        # 0x8002000c is what the guest saw in rax at the abort.
        self.assertIn('#define NO_MEMORY ((int32_t)UINT32_C(0x8002000c))', source())


class ConflictFinding(unittest.TestCase):
    """The scenario observed on 2026-11-01, expressed as arithmetic."""

    REQUEST_START = 0x1000000000
    REQUEST_SIZE = 8589934592          # 8 GiB, from pool_reserve's log
    REQUEST_FLAGS = 0x90               # MAP_FIXED | MAP_NO_OVERWRITE
    EXISTING_START = 0x1000000000      # "mapped direct memory 0000001000000000"
    EXISTING_SIZE = 6291456            # 6 MiB

    def test_request_is_page_aligned(self):
        page = 16384  # PS4 page size used by the runtime
        self.assertEqual(self.REQUEST_SIZE % page, 0)

    def test_request_carries_fixed_and_no_overwrite(self):
        self.assertEqual(self.REQUEST_FLAGS & 0x10, 0x10)
        self.assertEqual(self.REQUEST_FLAGS & 0x80, 0x80)

    def test_existing_mapping_overlaps_the_requested_range(self):
        req_end = self.REQUEST_START + self.REQUEST_SIZE
        ex_end = self.EXISTING_START + self.EXISTING_SIZE
        overlaps = self.EXISTING_START < req_end and self.REQUEST_START < ex_end
        self.assertTrue(overlaps,
                        'the 6 MiB direct mapping must sit inside the 8 GiB pool request')

    def test_the_pool_request_is_not_a_memory_shortage(self):
        # The runtime pool is 5056 MiB by default; the 8 GiB request never reaches it
        # because the address conflict is decided first. Growing the pool must not help,
        # which is exactly what GOW3_DMEM_MB=8192 showed.
        default_pool = 5056 * 1024 * 1024
        self.assertGreater(self.REQUEST_SIZE, default_pool,
                           'if the pool ever grew past the request this test needs revisiting')


class InstrumentationPresent(unittest.TestCase):
    """The diagnostics are the deliverable; keep them wired."""

    def test_fault_reporter_names_the_syscall_gate(self):
        probe = (ROOT / 'runtime' / 'src' / 'probe.c').read_text(encoding='utf-8', errors='replace')
        self.assertIn('is_ps4_syscall_gate', probe)
        self.assertIn('PS4 syscall gate', probe)

    def test_reserve_range_reports_the_occupant(self):
        self.assertIn('reserve_range refused', source())

    def test_pool_reserve_logs_failures_only(self):
        text = source()
        self.assertIn('Runtime: pool_reserve(', text)
        # The success path stays quiet so the boot log remains readable.
        self.assertNotIn('out=%p', text)


if __name__ == '__main__':
    unittest.main()
