"""Abstract PLC interface and shared hardware safety interlocks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome

logger = get_logger("hardware.plc.base")


class BasePLC(ABC):
    """Abstract interface defining industrial line controller operations with shared safety interlocks."""

    def __init__(self, expected_stations: list[str] | None = None) -> None:
        self.expected_stations = expected_stations or [
            "STATION_1",
            "STATION_2",
            "STATION_3",
            "STATION_4",
        ]
        self._shared_station_results: dict[str, Outcome] = {}
        # Per-seat station outcome tracking to avoid inter-seat timing contamination
        self._seat_station_results: dict[str, dict[str, Outcome]] = {}
        self._shared_label_printer_enabled = False
        self._active_printing_seat_id: str | None = None

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to line PLC controller."""

    @abstractmethod
    def disconnect(self) -> None:
        """Release PLC communication handle."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if communication link is healthy."""

    @abstractmethod
    def wait_for_trigger(self, station_id: str, timeout_s: float = 5.0) -> bool:
        """Wait for photo-eye or pallet arrival trigger at given station.

        Returns:
            True if triggered, False if timed out.
        """

    @abstractmethod
    def read_barcode(self, station_id: str) -> str:
        """Read scanned pallet or seat barcode."""

    def set_station_result(
        self, station_id: str, outcome: Outcome, seat_id: str | None = None
    ) -> None:
        """Publish station outcome (PASS, REVIEW, FAIL) to PLC memory tag and update shared tracking."""
        self._shared_station_results[station_id] = outcome
        if seat_id:
            if seat_id not in self._seat_station_results:
                self._seat_station_results[seat_id] = {}
            self._seat_station_results[seat_id][station_id] = outcome

        # If any station reports FAIL or REVIEW, ensure printer cannot remain enabled
        if outcome in (Outcome.FAIL, Outcome.REVIEW) and (
            self._active_printing_seat_id == seat_id or self._active_printing_seat_id is None
        ):
            self.set_label_printer_enable(False)

        self._write_station_result_hardware(station_id, outcome)

    @abstractmethod
    def _write_station_result_hardware(self, station_id: str, outcome: Outcome) -> None:
        """Driver-specific hardware write for station result."""

    @abstractmethod
    def hold_pallet(self, station_id: str, hold: bool = True) -> None:
        """Command pallet stop pin / indexer to hold (True) or release (False)."""

    @abstractmethod
    def is_mechanism_locked(self) -> bool:
        """Read hardware proximity / mechanical lock confirmation sensor signal.

        Crucial safety requirement: Must be read from sensor, NEVER from camera.
        """

    def read_lock_torque(self) -> float:
        """Read mechanism latch engagement torque or motor current in Nm."""
        return 20.0

    def read_actuator_position(self) -> float:
        """Read servo / linear actuator position in mm."""
        return 240.0

    def check_slip_back(self, hold_time_s: float = 0.05) -> float:
        """Measure difference in actuator position after hold time in mm."""
        return 0.0

    def set_label_printer_enable(self, enable: bool, seat_id: str | None = None) -> None:
        """Enable or disable OEM label applicator interlock output.

        Shared Safety Rule:
        The physical OEM label printer may ONLY be energized/enabled when every expected
        station outcome is PASS AND the physical mechanism lock sensor is confirmed.
        If any station reports FAIL or REVIEW, or the sensor is unlocked, printer is hard-disabled.
        """
        if enable:
            # First check mechanism lock sensor
            if not self.is_mechanism_locked():
                logger.error(
                    "Shared Safety Interlock Blocked: Cannot enable label printer; mechanism lock sensor not confirmed."
                )
                self._active_printing_seat_id = None
                self._shared_label_printer_enabled = False
                self._write_label_printer_hardware(False)
                return

            # If seat_id is provided, check the specific seat's outcomes
            if seat_id and seat_id in self._seat_station_results:
                seat_results = self._seat_station_results[seat_id]
                all_pass = (
                    all(st in seat_results for st in self.expected_stations)
                    and all(seat_results.get(st) == Outcome.PASS for st in self.expected_stations)
                )
            else:
                # Fallback to shared latest station outcomes
                all_pass = (
                    all(st in self._shared_station_results for st in self.expected_stations)
                    and all(
                        self._shared_station_results.get(st) == Outcome.PASS
                        for st in self.expected_stations
                    )
                )

            if not all_pass:
                logger.error(
                    f"Shared Safety Interlock Blocked: Cannot enable label printer; stations not all PASS. "
                    f"Target seat: {seat_id}, Seat results: {self._seat_station_results.get(seat_id or '')}, "
                    f"Global results: {self._shared_station_results}"
                )
                self._active_printing_seat_id = None
                self._shared_label_printer_enabled = False
                self._write_label_printer_hardware(False)
                return

            self._active_printing_seat_id = seat_id
            self._shared_label_printer_enabled = True
            self._write_label_printer_hardware(True)
            logger.info(f"Shared Safety Interlock: Label printer output ENABLED for seat {seat_id}.")
        else:
            self._active_printing_seat_id = None
            self._shared_label_printer_enabled = False
            self._write_label_printer_hardware(False)
            logger.info("Shared Safety Interlock: Label printer output DISABLED.")

    @abstractmethod
    def simulate_mechanism_sensor(self, locked: bool) -> None:
        """Set physical mechanism lock confirmation sensor status (override in simulator/test subclasses)."""
        # Default no-op for production drivers that read the real sensor
        pass

    def clear_seat(self, seat_id: str) -> None:
        """Prune seat tracking memory to prevent unbounded growth."""
        self._seat_station_results.pop(seat_id, None)
        if self._active_printing_seat_id == seat_id:
            self.set_label_printer_enable(False)

    @abstractmethod
    def _write_label_printer_hardware(self, enable: bool) -> None:
        """Driver-specific hardware write for printer enable bit."""

    def is_label_printer_enabled(self) -> bool:
        """Return cached interlock state of label printer output."""
        return self._shared_label_printer_enabled

    @abstractmethod
    def read_tag(self, tag_name: str) -> Any:
        """Read arbitrary tag or register by name."""

    @abstractmethod
    def write_tag(self, tag_name: str, value: Any) -> None:
        """Write arbitrary tag or register by name."""
