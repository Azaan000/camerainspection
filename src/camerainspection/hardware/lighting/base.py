"""Abstract interface for illumination and stroboscopic controllers."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

from camerainspection.core.logging import get_logger

logger = get_logger("hardware.lighting.base")


class BaseLightController(ABC):
    """Abstract lighting controller managing multiple intensity channels per station."""

    @abstractmethod
    def set_intensity(self, channel: str, pct: float) -> None:
        """Set lighting channel intensity (0.0 to 100.0 percent)."""

    @abstractmethod
    def read_back(self, channel: str) -> float:
        """Read actual measured light intensity or PWM duty cycle (0.0 to 100.0 percent)."""

    def apply_and_verify(
        self,
        channel: str,
        target_pct: float,
        tolerance_pct: float = 5.0,
        retries: int = 2,
        retry_delay_s: float = 0.05,
    ) -> bool:
        """Apply channel intensity and verify read-back within tolerance, with retries."""
        for attempt in range(1, retries + 2):
            self.set_intensity(channel, target_pct)
            time.sleep(retry_delay_s)
            actual = self.read_back(channel)
            if abs(actual - target_pct) <= tolerance_pct:
                logger.info(
                    f"Light channel '{channel}' verified at {actual:.1f}% (target {target_pct:.1f}%)"
                )
                return True
            logger.warning(
                f"Light read-back mismatch on '{channel}': got {actual:.1f}%, expected {target_pct:.1f}% "
                f"(attempt {attempt}/{retries + 1})"
            )

        logger.error(
            f"Light channel '{channel}' failed read-back verification after {retries} retries."
        )
        return False
