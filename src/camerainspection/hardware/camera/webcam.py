"""Webcam camera adapter using OpenCV VideoCapture."""

from __future__ import annotations

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

logger = get_logger("camera.webcam")


class WebcamCamera(BaseCamera):
    """Acquires frames from a standard USB or integrated webcam."""

    def __init__(
        self,
        camera_id: int = 0,
        width: int = 1920,
        height: int = 1080,
    ) -> None:
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self._cap: cv2.VideoCapture | None = None
        self._connected = False

    def connect(self) -> None:
        try:
            self._cap = cv2.VideoCapture(self.camera_id)
            if not self._cap.isOpened():
                self._connected = False
                raise CameraOfflineError(f"Could not open webcam device ID {self.camera_id}")

            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._connected = True
            logger.info(f"WebcamCamera connected on device {self.camera_id} ({self.width}x{self.height})")
        except Exception as e:
            self._connected = False
            raise CameraOfflineError(f"Error connecting to webcam {self.camera_id}: {e}") from e

    def disconnect(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._connected = False
        logger.info(f"WebcamCamera disconnected device {self.camera_id}")

    def is_connected(self) -> bool:
        return self._connected and self._cap is not None and self._cap.isOpened()

    def capture(self) -> np.ndarray:
        if not self.is_connected() or self._cap is None:
            raise CameraOfflineError(f"Webcam device {self.camera_id} is offline")

        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise CameraTimeoutError(f"Failed to grab frame from webcam {self.camera_id}")

        if frame.size == 0:
            raise CorruptImageError(f"Grabbed empty frame from webcam {self.camera_id}")

        return frame

    def get_metadata(self) -> dict[str, Any]:
        return {
            "adapter": "WebcamCamera",
            "camera_id": self.camera_id,
            "width": self.width,
            "height": self.height,
            "connected": self.is_connected(),
        }
