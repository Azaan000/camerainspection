"""Abstract PLC interface and shared hardware safety interlocks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome

logger = get_logger("hardware.plc.base")


class BasePLC(ABC):
    """Abstract interface defining industrial line controller operations with shared safety interlocks."""

    def __init__(self) -> None:
        self._shared_station_results: dict[str, Outcome] = {}
        self._shared_label_printer_enabled = False

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

    def set_station_result(self, station_id: str, outcome: Outcome) -> None:
        """Publish station outcome (PASS, REVIEW, FAIL) to PLC memory tag and update shared tracking."""
        self._shared_station_results[station_id] = outcome
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

    def set_label_printer_enable(self, enable: bool) -> None:
        """Enable or disable OEM label applicator interlock output.

        Shared Safety Rule:
        The physical OEM label printer may ONLY be energized/enabled when every expected
        station outcome is PASS AND the physical mechanism lock sensor is confirmed.
        If any station reports FAIL or REVIEW, or the sensor is unlocked, printer is hard-disabled.
        """
        if enable:
            expected_stations = ["STATION_1", "STATION_2", "STATION_3", "STATION_4"]
            all_pass = all(
                self._shared_station_results.get(st) == Outcome.PASS for st in expected_stations
            )
            if not all_pass:
                logger.error(
                    f"Shared Safety Interlock Blocked: Cannot enable label printer; stations not all PASS: {self._shared_station_results}"
                )
                self._shared_label_printer_enabled = False
                self._write_label_printer_hardware(False)
                return

            if not self.is_mechanism_locked():
                logger.error(
                    "Shared Safety Interlock Blocked: Cannot enable label printer; mechanism lock sensor not confirmed."
                )
                self._shared_label_printer_enabled = False
                self._write_label_printer_hardware(False)
                return

            self._shared_label_printer_enabled = True
            self._write_label_printer_hardware(True)
            logger.info("Shared Safety Interlock: Label printer output ENABLED.")
        else:
            self._shared_label_printer_enabled = False
            self._write_label_printer_hardware(False)
            logger.info("Shared Safety Interlock: Label printer output DISABLED.")

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
