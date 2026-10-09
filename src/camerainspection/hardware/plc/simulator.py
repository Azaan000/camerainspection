"""In-memory PLC simulator for automated line testing and local development."""

from __future__ import annotations

import threading
import time
from typing import Any

from camerainspection.core.exceptions import PLCCommunicationError
from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome
from camerainspection.hardware.plc.base import BasePLC

logger = get_logger("plc.simulator")


class PLCSimulator(BasePLC):
    """Thread-safe PLC simulator replicating line indexers, barcode scanners, and printer interlocks."""

    def __init__(self, expected_stations: list[str] | None = None) -> None:
        super().__init__(expected_stations=expected_stations)
        self._lock = threading.Lock()
        self._connected = False
        self._tags: dict[str, Any] = {}

        # Station state
        self._station_triggers: dict[str, threading.Event] = {}
        self._station_barcodes: dict[str, str] = {}
        self._station_outcomes: dict[str, Outcome] = {}
        self._pallet_held: dict[str, bool] = {}

        # Mechanism and printer safety interlocks
        self._mechanism_locked = False
        self._lock_torque_nm = 20.0
        self._actuator_position_mm = 240.0
        self._slip_back_mm = 0.0

    def connect(self) -> None:
        with self._lock:
            self._connected = True
            logger.info("PLCSimulator connected.")

    def disconnect(self) -> None:
        with self._lock:
            self._connected = False
            logger.info("PLCSimulator disconnected.")

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise PLCCommunicationError("PLCSimulator is disconnected.")

    def wait_for_trigger(self, station_id: str, timeout_s: float = 5.0) -> bool:
        self._ensure_connected()
        with self._lock:
            if station_id not in self._station_triggers:
                self._station_triggers[station_id] = threading.Event()
            ev = self._station_triggers[station_id]

        triggered = ev.wait(timeout=timeout_s)
        if triggered:
            with self._lock:
                ev.clear()
        return triggered

    def read_barcode(self, station_id: str) -> str:
        self._ensure_connected()
        with self._lock:
            return self._station_barcodes.get(station_id, "")

    def _write_station_result_hardware(self, station_id: str, outcome: Outcome) -> None:
        self._ensure_connected()
        with self._lock:
            self._station_outcomes[station_id] = outcome
            self._tags[f"{station_id}_OUTCOME"] = outcome.value
            logger.info(f"PLC tag {station_id}_OUTCOME updated to {outcome.value}")

            # Safety rule: If FAIL or REVIEW, hold pallet
            if outcome in (Outcome.FAIL, Outcome.REVIEW):
                self._pallet_held[station_id] = True
                self._tags[f"{station_id}_PALLET_HELD"] = True
            elif outcome == Outcome.PASS:
                self._pallet_held[station_id] = False
                self._tags[f"{station_id}_PALLET_HELD"] = False

    def hold_pallet(self, station_id: str, hold: bool = True) -> None:
        self._ensure_connected()
        with self._lock:
            self._pallet_held[station_id] = hold
            self._tags[f"{station_id}_PALLET_HELD"] = hold
            logger.info(f"Pallet at {station_id} hold state set to {hold}")

    def is_mechanism_locked(self) -> bool:
        self._ensure_connected()
        with self._lock:
            return self._mechanism_locked

    def read_lock_torque(self) -> float:
        self._ensure_connected()
        with self._lock:
            return self._lock_torque_nm

    def read_actuator_position(self) -> float:
        self._ensure_connected()
        with self._lock:
            return self._actuator_position_mm

    def check_slip_back(self, hold_time_s: float = 0.05) -> float:
        self._ensure_connected()
        if hold_time_s > 0:
            time.sleep(hold_time_s)
        with self._lock:
            return self._slip_back_mm

    def simulate_mechanism_metrics(
        self,
        torque_nm: float = 20.0,
        actuator_pos_mm: float = 240.0,
        slip_back_mm: float = 0.0,
    ) -> None:
        """Configure simulated load cell, actuator travel, and slip-back values."""
        with self._lock:
            self._lock_torque_nm = torque_nm
            self._actuator_position_mm = actuator_pos_mm
            self._slip_back_mm = slip_back_mm
            self._tags["LOCK_TORQUE_NM"] = torque_nm
            self._tags["ACTUATOR_POS_MM"] = actuator_pos_mm
            self._tags["SLIP_BACK_MM"] = slip_back_mm

    def _write_label_printer_hardware(self, enable: bool) -> None:
        self._ensure_connected()
        with self._lock:
            self._tags["LABEL_PRINTER_ENABLE"] = enable

    def read_tag(self, tag_name: str) -> Any:
        self._ensure_connected()
        with self._lock:
            return self._tags.get(tag_name)

    def write_tag(self, tag_name: str, value: Any) -> None:
        self._ensure_connected()
        with self._lock:
            self._tags[tag_name] = value

    # Testing & simulation helpers
    def simulate_arrival(self, station_id: str, barcode: str) -> None:
        """Simulate physical pallet arrival with barcode scan."""
        with self._lock:
            if station_id not in self._station_triggers:
                self._station_triggers[station_id] = threading.Event()
            self._station_barcodes[station_id] = barcode
            self._station_triggers[station_id].set()

    def simulate_mechanism_sensor(self, locked: bool) -> None:
        """Set physical mechanism lock confirmation sensor status."""
        with self._lock:
            self._mechanism_locked = locked
            self._tags["MECHANISM_LOCK_SENSOR"] = locked

    def is_pallet_held(self, station_id: str) -> bool:
        """Query if pallet is currently held by indexer pin."""
        with self._lock:
            return self._pallet_held.get(station_id, True)
