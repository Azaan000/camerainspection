"""Modbus TCP PLC adapter for industrial communications."""

from __future__ import annotations

import threading
from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome
from camerainspection.hardware.plc.base import BasePLC

logger = get_logger("hardware.plc.modbus")


class ModbusPLC(BasePLC):
    """Adapter for Modbus TCP line controllers (e.g. Schneider, Omron, Advantech).

    Gracefully falls back to mock simulation if pymodbus is not installed or PLC is offline.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 502,
        unit_id: int = 1,
        expected_stations: list[str] | None = None,
        printer_coil_address: int = 100,
    ) -> None:
        super().__init__(expected_stations=expected_stations)
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.printer_coil_address = printer_coil_address
        self._connected = False
        self._client: Any = None
        self._lock = threading.Lock()

        # Simulated state when running in dev/test mode
        self._pallet_holds: dict[str, bool] = {}
        self._station_results: dict[str, Outcome] = {}
        self._mechanism_locked = False

    def connect(self) -> None:
        try:
            from pymodbus.client import ModbusTcpClient
            self._client = ModbusTcpClient(self.host, port=self.port)
            self._connected = bool(self._client.connect())
            if self._connected:
                logger.info(f"Connected to Modbus TCP PLC at {self.host}:{self.port}")
            else:
                logger.warning(f"Could not connect to Modbus PLC at {self.host}. Operating in simulator mode.")
                self._connected = True
        except ImportError:
            logger.info("pymodbus not installed. ModbusPLC running in simulator mode.")
            self._connected = True

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
        self._connected = False
        logger.info("Modbus PLC disconnected.")

    def is_connected(self) -> bool:
        return self._connected

    def wait_for_trigger(self, station_id: str, timeout_s: float = 5.0) -> bool:
        return True

    def read_barcode(self, station_id: str) -> str:
        return f"PALLET_MODBUS_{station_id}_FRONT_LH_BLACK"

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
        """Physical Modbus coil write for label printer interlock."""
        with self._lock:
            if self._client is not None and getattr(self._client, "connected", False):
                try:
                    self._client.write_coil(
                        address=self.printer_coil_address,
                        value=enable,
                        slave=self.unit_id,
                    )
                    logger.info(
                        f"Modbus coil {self.printer_coil_address} written: {enable}"
                    )
                except Exception as e:
                    logger.error(f"Failed to write Modbus printer coil {self.printer_coil_address}: {e}")
            else:
                logger.debug(f"Modbus simulated coil {self.printer_coil_address} state: {enable}")

    def simulate_mechanism_sensor(self, locked: bool) -> None:
        with self._lock:
            self._mechanism_locked = locked

    def read_tag(self, tag_name: str) -> Any:
        return 0

    def write_tag(self, tag_name: str, value: Any) -> None:
        pass
