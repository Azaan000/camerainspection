"""Webcam and network stream camera adapter using OpenCV VideoCapture."""

from __future__ import annotations

import time
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
    """Acquires frames from a standard USB webcam, integrated camera, or IP/RTSP network stream.

    Supports:
        - Device index: integer (e.g. 0, 1)
        - Stream URL: string (e.g. "http://192.168.1.50:8080/video", "rtsp://...")
    """

    def __init__(
        self,
        camera_id: int | str = 0,
        width: int = 1920,
        height: int = 1080,
        max_reconnect_attempts: int = 3,
        reconnect_delay_s: float = 0.2,
    ) -> None:
        self.camera_id: int | str = camera_id
        self.width = width
        self.height = height
        self.max_reconnect_attempts = max(1, max_reconnect_attempts)
        self.reconnect_delay_s = reconnect_delay_s
        self._cap: cv2.VideoCapture | None = None
        self._connected = False

    def connect(self) -> None:
        """Connect to device index or stream URL and configure dimensions."""
        logger.warning(
            "Non-industrial camera (webcam/phone) in use: exposure_us and gain_db are ignored "
            "by hardware, and millimetre measurements are uncalibrated."
        )
        try:
            # If camera_id is a numeric string (e.g. "0"), convert to int for OpenCV device index
            dev_id: int | str = self.camera_id
            if isinstance(dev_id, str) and dev_id.isdigit():
                dev_id = int(dev_id)

            self._cap = cv2.VideoCapture(dev_id)
            if not self._cap.isOpened():
                self._connected = False
                raise CameraOfflineError(f"Could not open webcam/stream device '{self.camera_id}'")

            if self.width > 0:
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.width))
            if self.height > 0:
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.height))

            self._connected = True
            logger.info(
                f"WebcamCamera connected on device '{self.camera_id}' ({self.width}x{self.height})"
            )
        except Exception as e:
            self._connected = False
            raise CameraOfflineError(f"Error connecting to webcam '{self.camera_id}': {e}") from e

    def disconnect(self) -> None:
        """Release underlying VideoCapture handle."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._connected = False
        logger.info(f"WebcamCamera disconnected device '{self.camera_id}'")

    def is_connected(self) -> bool:
        """Check if camera stream is active and readable."""
        return self._connected and self._cap is not None and self._cap.isOpened()

    def _attempt_reconnect(self) -> bool:
        """Bounded retry to reconnect to the stream or camera device."""
        logger.warning(f"Attempting to reconnect webcam/stream '{self.camera_id}'...")
        for attempt in range(1, self.max_reconnect_attempts + 1):
            try:
                self.disconnect()
                time.sleep(self.reconnect_delay_s)
                self.connect()
                if self.is_connected():
                    logger.info(f"Webcam/stream '{self.camera_id}' reconnected on attempt {attempt}")
                    return True
            except Exception as e:
                logger.warning(f"Reconnect attempt {attempt}/{self.max_reconnect_attempts} failed: {e}")
        return False

    def capture(self) -> np.ndarray:
        """Acquire a single frame with bounded reconnect-on-failure."""
        if not self.is_connected() and not self._attempt_reconnect():
            raise CameraOfflineError(f"Webcam device '{self.camera_id}' is offline and reconnect failed")

        assert self._cap is not None
        ret, frame = self._cap.read()
        if not ret or frame is None or frame.size == 0:
            logger.warning(f"Frame grab failed on device '{self.camera_id}'. Triggering reconnect...")
            if self._attempt_reconnect():
                assert self._cap is not None
                ret, frame = self._cap.read()

        if not ret or frame is None:
            raise CameraTimeoutError(f"Failed to grab frame from webcam/stream '{self.camera_id}'")

        if frame.size == 0:
            raise CorruptImageError(f"Grabbed empty frame from webcam '{self.camera_id}'")

        return frame

    def get_metadata(self) -> dict[str, Any]:
        return {
            "adapter": "WebcamCamera",
            "camera_id": self.camera_id,
            "width": self.width,
            "height": self.height,
            "connected": self.is_connected(),
            "max_reconnect_attempts": self.max_reconnect_attempts,
        }
