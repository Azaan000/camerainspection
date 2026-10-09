"""Abstract base class for RFID and barcode pallet/seat tracking readers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseRFIDReader(ABC):
    """Abstract interface for hardware RFID readers mounted at stations or rework benches."""

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to RFID reader hardware."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect and release hardware communication ports."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if reader is online and responsive."""
        pass

    @abstractmethod
    def read_tag(self, timeout_s: float = 1.0) -> str | None:
        """Read seat or pallet RFID transponder tag ID in field. Returns None if no tag present."""
        pass

    @abstractmethod
    def write_tag(self, tag_id: str, timeout_s: float = 1.0) -> bool:
        """Write seat or pallet tracking data to RFID transponder tag. Returns True on success."""
        pass
