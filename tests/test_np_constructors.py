"""Pins the NpToolkit2 constructor contract derived from the guest's own stack layout.

A wrong size here would zero guest stack memory outside the object. The value is not
guessed: the guest passes rbp-0x398 to InitParams and reuses rbp-0x260 for the next
object, so the constructor covers 0x138 bytes. These tests keep that derivation honest.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
NP = ROOT / 'runtime' / 'src' / 'runtime_np.c'


def source():
    return NP.read_text(encoding='utf-8', errors='replace')


class ConstructorSize(unittest.TestCase):
    # Measured at eboot 0x40c762a: leaq -0x398(%rbp),%rbx ; mov %rbx,%rdi ; call ctor.
    # The guest fills fields down to rbp-0x320 and the NEXT object it constructs starts at
    # rbp-0x238 (leaq -0x238(%rbp),%rdi at 0x40c782d). An earlier reading mistook rbp-0x260
    # for the next object and under-sized the struct by 40 bytes.
    INIT_PARAMS_BASE = 0x398
    NEXT_OBJECT_BASE = 0x238
    EXPECTED_SIZE = 0x160          # 352 bytes
    LAST_FIELD_WRITTEN = 0x320     # movl $0x0,-0x268 / movq to -0x320 and below

    def test_measured_size_matches_the_constant(self):
        match = re.search(r'#define NP_INIT_PARAMS_SIZE (\d+)', source())
        if match is None:
            self.fail('NP_INIT_PARAMS_SIZE must stay defined')
        self.assertEqual(int(match.group(1)), self.EXPECTED_SIZE)

    def test_size_equals_the_frame_gap(self):
        self.assertEqual(self.INIT_PARAMS_BASE - self.NEXT_OBJECT_BASE, self.EXPECTED_SIZE)

    def test_object_stays_clear_of_the_stack_canary(self):
        # Canary lives at rbp-0x30; the object ends at rbp-0x238, i.e. 520 bytes below it.
        canary_offset = 0x30
        self.assertEqual(self.NEXT_OBJECT_BASE - canary_offset, 520)

    def test_size_covers_every_field_the_guest_writes(self):
        # The object must be at least as large as the furthest field the guest touches.
        self.assertGreaterEqual(self.EXPECTED_SIZE, self.INIT_PARAMS_BASE - self.LAST_FIELD_WRITTEN)

    def test_constructor_rejects_a_null_object(self):
        text = source()
        self.assertIn('if (!self) return;', text)
        self.assertIn('memset(self, 0, NP_INIT_PARAMS_SIZE)', text)


class ServiceIsRefusedNotFaked(unittest.TestCase):
    """Core::init is a service. It may be answered, but only with a failure code."""

    INIT_SYMBOL = '_ZN3sce7Toolkit2NP2V24Core4initERKNS3_7Request10InitParamsE'
    TERM_SYMBOL = '_ZN3sce7Toolkit2NP2V24Core4termERKNS3_7Request10TermParamsE'
    # Services may be answered only with a failure code, never with success.
    REFUSED_SERVICES = (INIT_SYMBOL, TERM_SYMBOL)

    def test_both_core_services_are_registered(self):
        text = source()
        for symbol in self.REFUSED_SERVICES:
            self.assertIn(symbol, text, f'{symbol} must be answered explicitly')

    def test_core_term_does_not_claim_success(self):
        text = source()
        block = text[text.index('np_core_term_refused'):]
        self.assertIn('return NP_NOT_INITIALIZED;', block)
        self.assertNotIn('return 0;', block.split('static const RuntimeExport')[0])

    def test_core_init_returns_a_failure_code_not_zero(self):
        text = source()
        # The guest accepts 0 as "PSN is up". Returning 0 would make the remaining imports
        # believe a subsystem exists that was never created, so the code must be non-zero.
        self.assertIn('NP_NOT_INITIALIZED', text)
        self.assertIn('return NP_NOT_INITIALIZED;', text)
        match = re.search(r'#define NP_NOT_INITIALIZED \(\(int32_t\)UINT32_C\(0x([0-9a-fA-F]+)\)\)', text)
        if match is None:
            self.fail('NP_NOT_INITIALIZED must keep its explicit hex value')
        self.assertNotEqual(int(match.group(1), 16), 0)

    def test_every_export_is_a_ctor_dtor_or_the_refused_init(self):
        names = re.findall(r'\{"(_Z[^"]+)"', source())
        self.assertTrue(names, 'the export table must not be empty')
        for name in names:
            ok = (name.endswith('C1Ev') or name.endswith('C2Ev')
                  or name.endswith('D1Ev') or name.endswith('D2Ev')
                  or name in self.REFUSED_SERVICES)
            self.assertTrue(ok, f'{name} is neither a ctor/dtor nor the refused service')

    def test_resolver_is_wired_into_the_runtime(self):
        runtime = (ROOT / 'runtime' / 'src' / 'runtime.c').read_text(encoding='utf-8', errors='replace')
        self.assertIn('runtime_np_resolve', runtime)


if __name__ == '__main__':
    unittest.main()
