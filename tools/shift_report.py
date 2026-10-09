#!/usr/bin/env python3
"""CLI entrypoint for end-of-shift quality report tool."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from camerainspection.tools.shift_report import main

if __name__ == "__main__":
    main()
