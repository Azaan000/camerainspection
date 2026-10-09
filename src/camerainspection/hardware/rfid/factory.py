"""Factory function for instantiating RFID reader adapters."""

from __future__ import annotations

from typing import Any
from camerainspection.hardware.rfid.base import BaseRFIDReader
from camerainspection.hardware.rfid.serial_rfid import SerialRFIDReader
from camerainspection.hardware.rfid.simulator import RFIDSimulator


def build_rfid_reader(config: dict[str, Any] | None = None) -> BaseRFIDReader:
    """Build RFID reader instance based on configuration dictionary."""
    if not config:
        return RFIDSimulator()

    adapter = str(config.get("adapter", "simulator")).lower()
    if adapter in ("simulator", "sim", "mock"):
        initial_tag = config.get("initial_tag")
        return RFIDSimulator(initial_tag=initial_tag)
    elif adapter in ("serial", "com", "rs232", "usb"):
        port = str(config.get("port", "COM3"))
        baudrate = int(config.get("baudrate", 9600))
        timeout_s = float(config.get("timeout_s", 1.0))
        return SerialRFIDReader(port=port, baudrate=baudrate, timeout_s=timeout_s)
    else:
        return RFIDSimulator()
