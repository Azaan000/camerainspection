"""Folder-replay camera adapter for development, simulation, and regression tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import cv2
import numpy as np

from camerainspection.core.exceptions import (
    CameraOfflineError,
    CameraTimeoutError,
    CorruptImageError,
)
from camerainspection.core.logging import get_logger
from camerainspection.hardware.camera.base import BaseCamera

logger = get_logger("camera.replay")


class FolderReplayCamera(BaseCamera):
    """Replays images from a local directory in alphabetical order."""

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}

    def __init__(
        self,
        folder_path: str | Path,
        loop: bool = True,
        simulate_delay_s: float = 0.0,
    ) -> None:
        self.folder_path = Path(folder_path)
        self.loop = loop
        self.simulate_delay_s = simulate_delay_s
        self._connected = False
        self._image_files: list[Path] = []
        self._current_index = 0
        self._last_image_path: Path | None = None

    def connect(self) -> None:
        """Scan directory and prepare image file queue."""
        if not self.folder_path.exists():
            # If folder doesn't exist, create it so development doesn't crash, but mark empty
            self.folder_path.mkdir(parents=True, exist_ok=True)

        files = sorted(
            [
                p
                for p in self.folder_path.iterdir()
                if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTENSIONS
            ]
        )
        self._image_files = files
        self._current_index = 0
        self._connected = True
        logger.info(
            f"FolderReplayCamera connected to {self.folder_path} "
            f"with {len(self._image_files)} images (loop={self.loop})"
        )

    def disconnect(self) -> None:
        self._connected = False
        logger.info("FolderReplayCamera disconnected.")

    def is_connected(self) -> bool:
        return self._connected

    def capture(self) -> np.ndarray:
        if not self._connected:
            raise CameraOfflineError("Cannot capture: FolderReplayCamera is offline.")

        if not self._image_files:
            raise CameraTimeoutError(
                f"No images found in replay folder {self.folder_path} for acquisition."
            )

        if self._current_index >= len(self._image_files):
            if self.loop:
                self._current_index = 0
            else:
                raise CameraTimeoutError(
                    f"FolderReplayCamera reached end of sequence ({len(self._image_files)} frames) with loop=False."
                )

        target_file = self._image_files[self._current_index]
        self._last_image_path = target_file
        self._current_index += 1

        img = cv2.imread(str(target_file))
        if img is None or img.size == 0:
            raise CorruptImageError(f"Failed to read image or image is empty: {target_file}")

        return img

    def get_metadata(self) -> dict[str, Any]:
        return {
            "adapter": "FolderReplayCamera",
            "folder_path": str(self.folder_path),
            "total_images": len(self._image_files),
            "current_index": self._current_index,
            "last_image_path": str(self._last_image_path) if self._last_image_path else None,
            "connected": self._connected,
        }
