"""Simulated light controller for test environments and headless execution."""

from __future__ import annotations

import threading
from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.hardware.lighting.base import BaseLightController

logger = get_logger("hardware.lighting.simulator")


class SimulatedLightController(BaseLightController):
    """Thread-safe simulated light controller tracking channel intensities."""

    def __init__(self, simulate_hardware_fault: bool = False) -> None:
        self._lock = threading.Lock()
        self._channels: dict[str, float] = {
            "dome": 80.0,
            "low_angle": 60.0,
            "direct": 90.0,
            "diffuse": 85.0,
            "ambient": 100.0,
        }
        self.simulate_hardware_fault = simulate_hardware_fault

    def set_intensity(self, channel: str, pct: float) -> None:
        with self._lock:
            clamped = max(0.0, min(100.0, float(pct)))
            self._channels[channel.lower().strip()] = clamped
            logger.info(f"SimulatedLightController: set '{channel}' to {clamped:.1f}%")

    def read_back(self, channel: str) -> float:
        with self._lock:
            if self.simulate_hardware_fault:
                return -1.0  # Force verification failure
            return self._channels.get(channel.lower().strip(), 0.0)

    def get_all_channels(self) -> dict[str, float]:
        with self._lock:
            return dict(self._channels)
