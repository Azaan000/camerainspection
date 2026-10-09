"""PLC-backed operator pushbutton panel driver."""

from __future__ import annotations

from typing import Any
from camerainspection.core.logging import get_logger
from camerainspection.hardware.operator_panel.base import BaseOperatorPanel
from camerainspection.hardware.plc.base import BasePLC

logger = get_logger("hardware.operator_panel.plc")


class PLCOperatorPanel(BaseOperatorPanel):
    """Operator panel mapped to PLC digital inputs and outputs."""

    def __init__(
        self,
        plc: BasePLC,
        start_input: int = 30,
        stop_input: int = 31,
        reset_input: int = 32,
        e_stop_input: int = 33,
        green_light_coil: int = 40,
        amber_light_coil: int = 41,
        red_light_coil: int = 42,
        blue_light_coil: int = 43,
    ) -> None:
        self.plc = plc
        self.start_input = start_input
        self.stop_input = stop_input
        self.reset_input = reset_input
        self.e_stop_input = e_stop_input
        self._light_coils = {
            "green": green_light_coil,
            "amber": amber_light_coil,
            "red": red_light_coil,
            "blue": blue_light_coil,
        }

    def read_start(self) -> bool:
        if hasattr(self.plc, "read_discrete_input"):
            return bool(self.plc.read_discrete_input(self.start_input))
        return False

    def read_stop(self) -> bool:
        if hasattr(self.plc, "read_discrete_input"):
            return bool(self.plc.read_discrete_input(self.stop_input))
        return False

    def read_reset(self) -> bool:
        if hasattr(self.plc, "read_discrete_input"):
            return bool(self.plc.read_discrete_input(self.reset_input))
        return False

    def read_e_stop(self) -> bool:
        if hasattr(self.plc, "read_discrete_input"):
            # Typically normally-closed (NC) circuit: input LOW indicates tripped
            return not bool(self.plc.read_discrete_input(self.e_stop_input))
        return False

    def set_indicator(self, color: str, active: bool) -> None:
        coil = self._light_coils.get(color.lower())
        if coil is not None and hasattr(self.plc, "write_coil"):
            self.plc.write_coil(coil, active)
