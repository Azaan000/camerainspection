"""Abstract base class for main line conveyor and reject spur control."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseConveyor(ABC):
    """Abstract interface for conveyor line transport and reject diverter gates."""

    @abstractmethod
    def start(self) -> bool:
        """Start mainline conveyor movement."""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """Stop mainline conveyor movement."""
        pass

    @abstractmethod
    def is_running() -> bool:
        """Return True if mainline conveyor motor is actively driving."""
        pass

    @abstractmethod
    def divert_to_reject(self, seat_id: str) -> bool:
        """Actuate diverter gate to push failed/rework seat to the reject spur."""
        pass

    @abstractmethod
    def release_to_mainline(self, seat_id: str) -> bool:
        """Allow verified PASS seat to continue down packaging/shipping mainline."""
        pass
