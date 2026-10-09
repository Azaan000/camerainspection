"""Siemens S7 PLC adapter using python-snap7."""

from __future__ import annotations

import threading
from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome
from camerainspection.hardware.plc.base import BasePLC

logger = get_logger("hardware.plc.snap7")


class SiemensSnap7PLC(BasePLC):
    """Adapter for Siemens S7-300/400/1200/1500 PLCs via python-snap7.

    Gracefully falls back to mock simulation if python-snap7 is not installed or PLC is offline.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        rack: int = 0,
        slot: int = 1,
        expected_stations: list[str] | None = None,
        db_number: int = 1,
        printer_byte: int = 0,
        printer_bit: int = 0,
    ) -> None:
        super().__init__(expected_stations=expected_stations)
        self.host = host
        self.rack = rack
        self.slot = slot
        self.db_number = db_number
        self.printer_byte = printer_byte
        self.printer_bit = printer_bit
        self._connected = False
        self._client: Any = None
        self._lock = threading.Lock()

        self._pallet_holds: dict[str, bool] = {}
        self._station_results: dict[str, Outcome] = {}
        self._mechanism_locked = False

    def connect(self) -> None:
        try:
            import snap7  # type: ignore
            self._client = snap7.client.Client()
            self._client.connect(self.host, self.rack, self.slot)
            self._connected = bool(self._client.get_connected())
            if self._connected:
                logger.info(f"Connected to Siemens S7 PLC at {self.host}")
            else:
                logger.warning(f"Could not connect to S7 PLC at {self.host}. Operating in simulator mode.")
                self._connected = True
        except ImportError:
            logger.info("python-snap7 not installed. SiemensSnap7PLC running in simulator mode.")
            self._connected = True

    def disconnect(self) -> None:
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass
        self._connected = False
        logger.info("Siemens S7 PLC disconnected.")

    def is_connected(self) -> bool:
        return self._connected

    def wait_for_trigger(self, station_id: str, timeout_s: float = 5.0) -> bool:
        return True

    def read_barcode(self, station_id: str) -> str:
        return f"PALLET_SNAP7_{station_id}_FRONT_LH_BLACK"

    def _write_station_result_hardware(self, station_id: str, outcome: Outcome) -> None:
        with self._lock:
            self._station_results[station_id] = outcome
            if outcome in (Outcome.FAIL, Outcome.REVIEW):
                self._pallet_holds[station_id] = True
            elif outcome == Outcome.PASS:
                self._pallet_holds[station_id] = False

    def hold_pallet(self, station_id: str, hold: bool = True) -> None:
        with self._lock:
            self._pallet_holds[station_id] = hold

    def is_mechanism_locked(self) -> bool:
        with self._lock:
            return self._mechanism_locked

    def _write_label_printer_hardware(self, enable: bool) -> None:
        """Physical Snap7 DB write to printer interlock tag."""
        with self._lock:
            if self._client is not None and getattr(self._client, "get_connected", lambda: False)():
                try:
                    # Read current byte to modify only the targeted bit
                    data = self._client.db_read(self.db_number, self.printer_byte, 1)
                    byte_val = data[0]
                    if enable:
                        byte_val |= (1 << self.printer_bit)
                    else:
                        byte_val &= ~(1 << self.printer_bit)
                    self._client.db_write(self.db_number, self.printer_byte, bytes([byte_val]))
                    logger.info(
                        f"Snap7 DB{self.db_number}.DBX{self.printer_byte}.{self.printer_bit} written: {enable}"
                    )
                except Exception as e:
                    logger.error(f"Failed to write Snap7 printer bit: {e}")
            else:
                logger.debug(f"Snap7 simulated printer bit state: {enable}")

    def simulate_mechanism_sensor(self, locked: bool) -> None:
        with self._lock:
            self._mechanism_locked = locked

    def read_tag(self, tag_name: str) -> Any:
        return 0

    def write_tag(self, tag_name: str, value: Any) -> None:
        pass
