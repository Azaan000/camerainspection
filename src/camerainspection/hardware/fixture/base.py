"""Abstract interface for clamping fixtures, rotary turntables, and robot arms."""

from __future__ import annotations

from abc import ABC, abstractmethod
import time
from typing import Any

from camerainspection.core.logging import get_logger

logger = get_logger("hardware.fixture.base")


class BaseFixture(ABC):
    """Abstract fixture controller ensuring seat stability and positioning."""

    VALID_POSITIONS = {"front", "left", "right", "rear"}

    @abstractmethod
    def clamp(self) -> None:
        """Actuate pneumatic/hydraulic clamps to secure seat pallet."""

    @abstractmethod
    def release(self) -> None:
        """Release clamping mechanism."""

    @abstractmethod
    def is_clamped(self) -> bool:
        """Read hardware clamp confirmation proximity sensor."""

    @abstractmethod
    def move_to(self, position: str) -> None:
        """Command turntable indexer to target position ('front', 'left', 'right', 'rear')."""

    @abstractmethod
    def move_arm_to(self, pose: dict[str, Any] | str) -> None:
        """Command robot-arm joint controller to target trajectory pose."""

    @abstractmethod
    def is_in_position(self) -> bool:
        """Affirmatively verify that indexer and arm have arrived at target."""

    def wait_in_position(self, timeout_s: float = 5.0, poll_interval_s: float = 0.05) -> bool:
        """Poll until fixture is in position or timeout expires."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.is_in_position():
                return True
            time.sleep(poll_interval_s)
        logger.error(f"Fixture timeout ({timeout_s}s) waiting for in-position confirmation.")
        return False
