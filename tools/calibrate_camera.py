#!/usr/bin/env python3
"""CLI entrypoint for camera calibration tool."""

import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from camerainspection.tools.calibrate_camera import main

if __name__ == "__main__":
    main()
