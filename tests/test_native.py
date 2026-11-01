"""Requires bash build.sh; missing binaries fail rather than silently skip the smoke gate."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import run


class NativeSmokeTests(unittest.TestCase):
    def test_help_and_runtime_audit(self):
        self.assertTrue(run.RUNTIME.is_file(), "Run bash build.sh before native smoke tests")
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            for flag, expected in (("--help", "Usage: cg-runtime"),
                                   ("--audit-runtime", "Runtime audit PASS")):
                with self.subTest(flag=flag):
                    result = subprocess.run([str(run.RUNTIME), flag], cwd=data,
                                            env=run.runtime_environment(data, os.environ),
                                            capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn(expected, result.stdout)
                    self.assertFalse((data / "user").exists())
                    self.assertFalse((data / "medievil.ini").exists())


if __name__ == '__main__':
    unittest.main()
