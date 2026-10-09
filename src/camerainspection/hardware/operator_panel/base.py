"""Abstract base class for operator station physical pushbutton panels."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseOperatorPanel(ABC):
    """Interface for physical line pushbuttons: Start, Stop, Reset, Emergency-Stop."""

    @abstractmethod
    def read_start(self) -> bool:
        """Read green START pushbutton."""
        pass

    @abstractmethod
    def read_stop(self) -> bool:
        """Read red STOP pushbutton."""
        pass

    @abstractmethod
    def read_reset(self) -> bool:
        """Read blue RESET / fault-clear pushbutton."""
        pass

    @abstractmethod
    def read_e_stop(self) -> bool:
        """Read physical Emergency-Stop button state (True = E-Stop engaged/tripped)."""
        pass

    @abstractmethod
    def set_indicator(self, color: str, active: bool) -> None:
        """Set stack light or panel indicator LED (red, amber, green, blue)."""
        pass
