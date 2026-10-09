"""PLC-backed conveyor and reject spur controller."""

from __future__ import annotations

from typing import Any
from camerainspection.core.logging import get_logger
from camerainspection.hardware.conveyor.base import BaseConveyor
from camerainspection.hardware.plc.base import BasePLC

logger = get_logger("hardware.conveyor.plc")


class PLCConveyor(BaseConveyor):
    """Conveyor implementation driven through industrial PLC coils and bits."""

    def __init__(
        self,
        plc: BasePLC,
        start_coil: int = 20,
        stop_coil: int = 21,
        running_input: int = 22,
        divert_coil: int = 23,
    ) -> None:
        self.plc = plc
        self.start_coil = start_coil
        self.stop_coil = stop_coil
        self.running_input = running_input
        self.divert_coil = divert_coil
        self._running_state: bool = False

    def start(self) -> bool:
        if not self.plc.is_connected():
            return False
        # If PLC supports coil write
        if hasattr(self.plc, "write_coil"):
            self.plc.write_coil(self.start_coil, True)
        self._running_state = True
        return True

    def stop(self) -> bool:
        if not self.plc.is_connected():
            return False
        if hasattr(self.plc, "write_coil"):
            self.plc.write_coil(self.stop_coil, True)
            self.plc.write_coil(self.start_coil, False)
        self._running_state = False
        return True

    def is_running(self) -> bool:
        if hasattr(self.plc, "read_discrete_input"):
            return bool(self.plc.read_discrete_input(self.running_input))
        return self._running_state

    def divert_to_reject(self, seat_id: str) -> bool:
        logger.warning(f"Diverting seat {seat_id} to reject spur via PLC coil {self.divert_coil}")
        if hasattr(self.plc, "write_coil"):
            self.plc.write_coil(self.divert_coil, True)
        return True

    def release_to_mainline(self, seat_id: str) -> bool:
        logger.info(f"Releasing seat {seat_id} to mainline packaging")
        if hasattr(self.plc, "write_coil"):
            self.plc.write_coil(self.divert_coil, False)
        return True
