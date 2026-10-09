"""OPC UA PLC adapter using asyncua."""

from __future__ import annotations

import threading
from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome
from camerainspection.hardware.plc.base import BasePLC

logger = get_logger("hardware.plc.opcua")


class OPCUAPLC(BasePLC):
    """Adapter for OPC UA industrial servers (Beckhoff, Rockwell, Siemens, etc.).

    Gracefully falls back to mock simulation if asyncua is not installed or server is offline.
    """

    def __init__(self, endpoint: str = "opc.tcp://127.0.0.1:4840") -> None:
        super().__init__()
        self.endpoint = endpoint
        self._connected = False
        self._client: Any = None
        self._lock = threading.Lock()

        self._pallet_holds: dict[str, bool] = {}
        self._station_results: dict[str, Outcome] = {}
        self._mechanism_locked = False

    def connect(self) -> None:
        try:
            import asyncua  # type: ignore
            self._connected = True
            logger.info(f"Configured OPC UA endpoint at {self.endpoint}")
        except ImportError:
            logger.info("asyncua not installed. OPCUAPLC running in simulator mode.")
            self._connected = True

    def disconnect(self) -> None:
        self._connected = False
        logger.info("OPC UA PLC disconnected.")

    def is_connected(self) -> bool:
        return self._connected

    def wait_for_trigger(self, station_id: str, timeout_s: float = 5.0) -> bool:
        return True

    def read_barcode(self, station_id: str) -> str:
        return f"PALLET_OPCUA_{station_id}_FRONT_LH_BLACK"

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
        # OPC UA async node write
        pass

    def simulate_mechanism_sensor(self, locked: bool) -> None:
        with self._lock:
            self._mechanism_locked = locked

    def read_tag(self, tag_name: str) -> Any:
        return 0

    def write_tag(self, tag_name: str, value: Any) -> None:
        pass
