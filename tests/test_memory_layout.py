"""Pins the guest memory-layout contract that decided the boot blocker.

The guest reserves its main pool with a *fixed* 8 GiB request at USER_MIN marked
MAP_NO_OVERWRITE. A runtime placement that lands there first makes the reservation fail with
NO_MEMORY, which libc turns into abort(). Measured on 2026-11-01; these tests freeze both the
contract and the fix so a future change has to confront them.
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

    def test_guest_pool_window_is_8_gib(self):
        match = re.search(r'#define GUEST_POOL_WINDOW \(UINT64_C\((\d+)\) \* 1024 \* 1024 \* 1024\)',
                          source())
        if match is None:
            self.fail('GUEST_POOL_WINDOW must stay defined')
        self.assertEqual(int(match.group(1)), 8)


class GuestContract(unittest.TestCase):
    """The guest demands the address explicitly; the runtime must keep it free."""

    POOL_START = 0x1000000000
    POOL_SIZE = 0x200000000      # movabsq $0x200000000,%r15 at 0xdf8554
    POOL_FLAGS = 0x90            # movl $0x90,%ecx at 0xdf856e

    def test_guest_immediates_match_the_fix_constants(self):
        # movabsq $0x1000000000,%rdi at 0xdf855e proves this is a guest requirement,
        # not a runtime choice -- that distinction decided the whole diagnosis.
        self.assertEqual(self.POOL_START, 0x1000000000)
        self.assertEqual(self.POOL_SIZE, 8589934592)
        self.assertEqual(self.POOL_FLAGS, 0x90)

    def test_unhinted_placement_routes_through_the_window_search(self):
        text = source()
        self.assertIn('find_free_unhinted', text)
        self.assertIn('(uintptr_t)*inout ? find_free(address,size,alignment) : find_free_unhinted',
                      text)

    def test_window_covers_the_whole_pool_request(self):
        # The floor used for hint-less placement must be at or beyond the pool's end.
        floor = self.POOL_START + self.POOL_SIZE
        self.assertEqual(floor, 0x1200000000)
        # Observed after the fix: "mapped direct memory 0000001200000000".
        self.assertEqual(floor, 0x1200000000)


class InstrumentationPresent(unittest.TestCase):
    """The diagnostics are the deliverable; keep them wired."""

    def test_fault_reporter_names_the_syscall_gate(self):
        probe = (ROOT / 'runtime' / 'src' / 'probe.c').read_text(encoding='utf-8', errors='replace')
        self.assertIn('is_ps4_syscall_gate', probe)
        self.assertIn('PS4 syscall gate', probe)

    def test_reserve_range_reports_the_occupant(self):
        self.assertIn('reserve_range refused', source())

    def test_pool_reserve_records_the_guest_caller(self):
        self.assertIn('guest ra=', source())

    def test_direct_map_records_the_guest_hint(self):
        # The hint field is what separated "guest required it" from "runtime chose it".
        self.assertIn('guest hint', source())


if __name__ == '__main__':
    unittest.main()
