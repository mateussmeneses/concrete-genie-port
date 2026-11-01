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
    # Measured at eboot 0x40c762a: leaq -0x398(%rbp),%rbx ; mov %rbx,%rdi ; call ctor
    # and at eboot 0x40c76c1: leaq -0x260(%rbp),%rdi  (next object).
    INIT_PARAMS_BASE = 0x398
    NEXT_OBJECT_BASE = 0x260
    EXPECTED_SIZE = 0x138          # 312 bytes

    def test_measured_size_matches_the_constant(self):
        match = re.search(r'#define NP_INIT_PARAMS_SIZE (\d+)', source())
        if match is None:
            self.fail('NP_INIT_PARAMS_SIZE must stay defined')
        self.assertEqual(int(match.group(1)), self.EXPECTED_SIZE)

    def test_size_equals_the_frame_gap(self):
        self.assertEqual(self.INIT_PARAMS_BASE - self.NEXT_OBJECT_BASE, self.EXPECTED_SIZE)

    def test_object_stays_clear_of_the_stack_canary(self):
        # Canary lives at rbp-0x30; the object ends at rbp-0x260, i.e. 560 bytes below it.
        canary_offset = 0x30
        self.assertGreater(self.NEXT_OBJECT_BASE - canary_offset, 0)
        self.assertEqual(self.NEXT_OBJECT_BASE - canary_offset, 560)

    def test_constructor_rejects_a_null_object(self):
        text = source()
        self.assertIn('if (!self) return;', text)
        self.assertIn('memset(self, 0, NP_INIT_PARAMS_SIZE)', text)


class OnlyConstructorsAreProvided(unittest.TestCase):
    """A service that needs a real answer must still reach the unresolved trap."""

    def test_no_service_entry_is_registered(self):
        text = source()
        # Core::init is a service, not a constructor: it must not be answered blindly.
        self.assertNotIn('4Core4initE', text)

    def test_exports_are_constructor_symbols_only(self):
        names = re.findall(r'\{"(_Z[^"]+)"', source())
        self.assertTrue(names, 'the export table must not be empty')
        for name in names:
            self.assertTrue(name.endswith('C1Ev') or name.endswith('C2Ev'),
                            f'{name} is not a constructor symbol')

    def test_resolver_is_wired_into_the_runtime(self):
        runtime = (ROOT / 'runtime' / 'src' / 'runtime.c').read_text(encoding='utf-8', errors='replace')
        self.assertIn('runtime_np_resolve', runtime)


if __name__ == '__main__':
    unittest.main()
