"""Basler industrial camera adapter using pypylon SDK."""

from __future__ import annotations

from typing import Any

import numpy as np

from camerainspection.core.exceptions import (
    CameraOfflineError,
    CameraTimeoutError,
    CorruptImageError,
)
from camerainspection.core.logging import get_logger
from camerainspection.hardware.camera.base import BaseCamera

logger = get_logger("hardware.camera.basler")


class BaslerCamera(BaseCamera):
    """Adapter for Basler GigE / USB3 Vision cameras via pypylon.

    Gracefully falls back to mock simulation if pypylon SDK is not installed on the system.
    """

    def __init__(
        self,
        serial_number: str | None = None,
        exposure_us: int = 15000,
        gain_db: float = 0.0,
        timeout_ms: int = 3000,
    ) -> None:
        self.serial_number = serial_number
        self.exposure_us = exposure_us
        self.gain_db = gain_db
        self.timeout_ms = timeout_ms
        self._camera: Any = None
        self._connected = False
        self._pylon_available = False

        try:
            import pypylon.pylon as pylon
            self._pylon = pylon
            self._pylon_available = True
        except ImportError:
            self._pylon = None
            logger.warning("pypylon not installed. BaslerCamera operating in simulator mode.")

    def connect(self) -> None:
        if self._pylon_available:
            try:
                tl_factory = self._pylon.TlFactory.GetInstance()
                if self.serial_number:
                    info = self._pylon.CDeviceInfo()
                    info.SetSerialNumber(self.serial_number)
                    self._camera = self._pylon.InstantCamera(tl_factory.CreateDevice(info))
                else:
                    self._camera = self._pylon.InstantCamera(tl_factory.CreateFirstDevice())

                self._camera.Open()
                self._camera.ExposureTime.SetValue(float(self.exposure_us))
                if hasattr(self._camera, "Gain"):
                    self._camera.Gain.SetValue(float(self.gain_db))
                self._connected = True
                logger.info(f"Connected to Basler camera (SN: {self.serial_number or 'default'})")
            except Exception as e:
                self._connected = False
                logger.error(f"Failed to connect to Basler camera: {e}")
                raise CameraOfflineError(f"Basler camera connection failed: {e}") from e
        else:
            # Stand-in simulation for environments without hardware SDK
            self._connected = True
            logger.info("Basler camera simulator online.")

    def disconnect(self) -> None:
        if self._pylon_available and self._camera and self._camera.IsOpen():
            self._camera.Close()
        self._connected = False
        logger.info("Basler camera disconnected.")

    def is_connected(self) -> bool:
        if self._pylon_available and self._camera:
            return bool(self._camera.IsOpen())
        return self._connected

    def capture(self) -> np.ndarray:
        if not self.is_connected():
            raise CameraOfflineError("Cannot capture: Basler camera is offline.")

        if self._pylon_available and self._camera:
            try:
                grab = self._camera.GrabOne(self.timeout_ms)
                if not grab.GrabSucceeded():
                    raise CameraTimeoutError("Basler camera acquisition timed out.")
                img: np.ndarray = grab.Array
                grab.Release()
                if img is None or img.size == 0:
                    raise CorruptImageError("Empty frame received from Basler camera.")
                return img
            except Exception as e:
                raise CameraTimeoutError(f"Basler grab failed: {e}") from e
        else:
            # Synthetic fallback for mock hardware integration test
            img = np.full((1944, 2592, 3), 35, dtype=np.uint8)
            return img

    def get_metadata(self) -> dict[str, Any]:
        return {
            "adapter": "basler",
            "pypylon_available": self._pylon_available,
            "serial_number": self.serial_number,
            "exposure_us": self.exposure_us,
            "gain_db": self.gain_db,
            "timeout_ms": self.timeout_ms,
            "connected": self.is_connected(),
        }
