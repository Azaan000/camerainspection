"""Abstract PLC interface for car seat inspection line."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from camerainspection.core.models import Outcome


class BasePLC(ABC):
    """Abstract interface defining industrial line controller operations."""

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

    @abstractmethod
    def set_station_result(self, station_id: str, outcome: Outcome) -> None:
        """Publish station outcome (PASS, REVIEW, FAIL) to PLC memory tag."""

    @abstractmethod
    def hold_pallet(self, station_id: str, hold: bool = True) -> None:
        """Command pallet stop pin / indexer to hold (True) or release (False)."""

    @abstractmethod
    def is_mechanism_locked(self) -> bool:
        """Read hardware proximity / mechanical lock confirmation sensor signal.

        Crucial safety requirement: Must be read from sensor, NEVER from camera.
        """

    @abstractmethod
    def set_label_printer_enable(self, enable: bool) -> None:
        """Enable or disable OEM label applicator interlock output.

        Safety interlock: Allowed ONLY when all stations & mechanism cycle test PASS.
        """

    @abstractmethod
    def read_tag(self, tag_name: str) -> Any:
        """Read arbitrary tag or register by name."""

    @abstractmethod
    def write_tag(self, tag_name: str, value: Any) -> None:
        """Write arbitrary tag or register by name."""
