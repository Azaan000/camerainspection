"""Factory for building conveyor controllers."""

from __future__ import annotations

from typing import Any
from camerainspection.hardware.conveyor.base import BaseConveyor
from camerainspection.hardware.conveyor.plc_conveyor import PLCConveyor
from camerainspection.hardware.conveyor.simulator import ConveyorSimulator
from camerainspection.hardware.plc.base import BasePLC


def build_conveyor(config: dict[str, Any] | None = None, plc: BasePLC | None = None) -> BaseConveyor:
    """Build conveyor controller instance."""
    if not config:
        return ConveyorSimulator()

    adapter = str(config.get("adapter", "simulator")).lower()
    if adapter in ("plc", "industrial") and plc is not None:
        return PLCConveyor(
            plc=plc,
            start_coil=int(config.get("start_coil", 20)),
            stop_coil=int(config.get("stop_coil", 21)),
            running_input=int(config.get("running_input", 22)),
            divert_coil=int(config.get("divert_coil", 23)),
        )
    return ConveyorSimulator()
