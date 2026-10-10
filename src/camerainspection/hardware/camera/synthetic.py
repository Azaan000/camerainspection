"""Synthetic camera generator for headless unit and integration testing."""

from __future__ import annotations

from typing import Any

import numpy as np

from camerainspection.core.exceptions import CameraOfflineError
from camerainspection.hardware.camera.base import BaseCamera


class SyntheticCamera(BaseCamera):
    """Generates synthetic test patterns without disk or video hardware dependencies."""

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        pattern: str = "solid_black",
    ) -> None:
        self.width = width
        self.height = height
        self.pattern = pattern
        self._connected = False
        self._frame_count = 0

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def capture(self) -> np.ndarray:
        if not self._connected:
            raise CameraOfflineError("SyntheticCamera is offline.")

        self._frame_count += 1
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        if self.pattern == "solid_black":
            img[:] = 30  # Dark dark grey / leather base
        elif self.pattern == "stitch_line":
            img[:] = 30
            # Draw synthetic white stitching line with regular stitch dots
            y_seam = self.height // 2
            for x in range(50, self.width - 50, 20):
                img[y_seam - 2 : y_seam + 2, x : x + 12] = 220
        elif self.pattern == "grid":
            img[:] = 50
            for r in range(0, self.height, 40):
                img[r : r + 2, :] = 180
            for c in range(0, self.width, 40):
                img[:, c : c + 2] = 180
        else:
            img[:] = 128

        return img

    def get_metadata(self) -> dict[str, Any]:
        return {
            "adapter": "SyntheticCamera",
            "pattern": self.pattern,
            "width": self.width,
            "height": self.height,
            "frame_count": self._frame_count,
            "connected": self._connected,
        }
