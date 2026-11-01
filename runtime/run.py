#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Legacy path: use the project launcher and its CG configuration boundary."""
from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    runpy.run_path(str(root / "run.py"), run_name="__main__")
