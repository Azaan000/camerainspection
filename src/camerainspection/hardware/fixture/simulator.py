"""Simulated fixture controller for test and offline development."""

from __future__ import annotations

import threading
import time
from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.hardware.fixture.base import BaseFixture

logger = get_logger("hardware.fixture.simulator")


class SimulatedFixture(BaseFixture):
    """Thread-safe simulated clamping fixture, turntable, and robot arm."""

    def __init__(
        self,
        auto_in_position: bool = True,
        simulate_clamp_success: bool = True,
        travel_delay_s: float = 0.0,
    ) -> None:
        self._lock = threading.Lock()
        self._clamped = False
        self._current_position = "front"
        self._target_position = "front"
        self._current_arm_pose: Any = "home"
        self._target_arm_pose: Any = "home"
        self._auto_in_position = auto_in_position
        self._simulate_clamp_success = simulate_clamp_success
        self.travel_delay_s = travel_delay_s
        self._in_position_event = threading.Event()
        if auto_in_position:
            self._in_position_event.set()

    def clamp(self) -> None:
        with self._lock:
            if self._simulate_clamp_success:
                self._clamped = True
                logger.info("SimulatedFixture: clamped successfully.")
            else:
                self._clamped = False
                logger.warning("SimulatedFixture: clamp failed (simulated fault).")

    def release(self) -> None:
        with self._lock:
            self._clamped = False
            logger.info("SimulatedFixture: unclamped.")

    def is_clamped(self) -> bool:
        with self._lock:
            return self._clamped

    def move_to(self, position: str) -> None:
        pos_clean = position.lower().strip()
        if pos_clean not in self.VALID_POSITIONS:
            raise ValueError(f"Invalid turntable position '{position}'. Must be one of {self.VALID_POSITIONS}")

        with self._lock:
            self._target_position = pos_clean
            if self.travel_delay_s > 0:
                self._in_position_event.clear()
                threading.Thread(target=self._simulate_travel, daemon=True).start()
            else:
                self._current_position = pos_clean
                if self._auto_in_position:
                    self._in_position_event.set()
            logger.info(f"SimulatedFixture: commanding move to '{pos_clean}'")

    def _simulate_travel(self) -> None:
        time.sleep(self.travel_delay_s)
        with self._lock:
            self._current_position = self._target_position
            self._current_arm_pose = self._target_arm_pose
            self._in_position_event.set()

    def move_arm_to(self, pose: dict[str, Any] | str) -> None:
        with self._lock:
            self._target_arm_pose = pose
            if self.travel_delay_s > 0:
                self._in_position_event.clear()
                threading.Thread(target=self._simulate_travel, daemon=True).start()
            else:
                self._current_arm_pose = pose
                if self._auto_in_position:
                    self._in_position_event.set()
            logger.info(f"SimulatedFixture: commanding arm to pose '{pose}'")

    def is_in_position(self) -> bool:
        with self._lock:
            return (
                self._in_position_event.is_set()
                and self._current_position == self._target_position
                and self._current_arm_pose == self._target_arm_pose
            )

    # Simulation control helpers
    def set_in_position(self, in_pos: bool) -> None:
        with self._lock:
            if in_pos:
                self._in_position_event.set()
            else:
                self._in_position_event.clear()
