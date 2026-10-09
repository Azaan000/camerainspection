"""Simulator for physical operator panel pushbuttons and indicators."""

from __future__ import annotations

from camerainspection.hardware.operator_panel.base import BaseOperatorPanel


class OperatorPanelSimulator(BaseOperatorPanel):
    """Software simulation of operator pushbuttons."""

    def __init__(self) -> None:
        self._start_pressed: bool = False
        self._stop_pressed: bool = False
        self._reset_pressed: bool = False
        self._e_stop_engaged: bool = False
        self._indicators: dict[str, bool] = {
            "green": False,
            "amber": False,
            "red": False,
            "blue": False,
        }

    def read_start(self) -> bool:
        val = self._start_pressed
        self._start_pressed = False  # Momentary pushbutton
        return val

    def read_stop(self) -> bool:
        val = self._stop_pressed
        self._stop_pressed = False
        return val

    def read_reset(self) -> bool:
        val = self._reset_pressed
        self._reset_pressed = False
        return val

    def read_e_stop(self) -> bool:
        return self._e_stop_engaged  # Maintained contact

    def set_indicator(self, color: str, active: bool) -> None:
        self._indicators[color.lower()] = active

    def get_indicator(self, color: str) -> bool:
        return self._indicators.get(color.lower(), False)

    # Simulation control helpers
    def press_start(self) -> None:
        self._start_pressed = True

    def press_stop(self) -> None:
        self._stop_pressed = True

    def press_reset(self) -> None:
        self._reset_pressed = True

    def trigger_e_stop(self, engaged: bool = True) -> None:
        self._e_stop_engaged = engaged
