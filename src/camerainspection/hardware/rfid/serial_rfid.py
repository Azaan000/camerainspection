"""Serial/RS-232/USB interface for industrial RFID readers."""

from __future__ import annotations

import time
from typing import Any
from camerainspection.core.logging import get_logger
from camerainspection.hardware.rfid.base import BaseRFIDReader

logger = get_logger("hardware.rfid.serial")


class SerialRFIDReader(BaseRFIDReader):
    """Hardware driver for ASCII/Modbus RTU serial RFID readers (e.g. Balluff BIS, Sick RFH)."""

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 9600,
        timeout_s: float = 1.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout_s = timeout_s
        self._serial: Any = None
        self._connected: bool = False

    def connect(self) -> bool:
        try:
            import serial
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout_s,
            )
            self._connected = self._serial.is_open
            logger.info(f"Connected to Serial RFID reader on port {self.port}")
            return self._connected
        except Exception as e:
            logger.warning(f"Failed to connect to Serial RFID reader on {self.port}: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._serial and hasattr(self._serial, "close"):
            try:
                self._serial.close()
            except Exception:
                pass
        self._connected = False

    def is_connected(self) -> bool:
        return bool(self._connected and self._serial and getattr(self._serial, "is_open", False))

    def read_tag(self, timeout_s: float = 1.0) -> str | None:
        if not self.is_connected():
            return None
        try:
            # Standard ASCII line-based RFID scan
            line = self._serial.readline().decode("utf-8", errors="ignore").strip()
            if line:
                return line
            return None
        except Exception as e:
            logger.warning(f"Error reading RFID tag on {self.port}: {e}")
            return None

    def write_tag(self, tag_id: str, timeout_s: float = 1.0) -> bool:
        if not self.is_connected():
            return False
        try:
            self._serial.write(f"{tag_id}\r\n".encode("utf-8"))
            self._serial.flush()
            return True
        except Exception as e:
            logger.warning(f"Error writing RFID tag on {self.port}: {e}")
            return False
