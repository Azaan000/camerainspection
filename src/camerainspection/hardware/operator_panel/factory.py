"""Factory for building operator panel drivers."""

from __future__ import annotations

from typing import Any
from camerainspection.hardware.operator_panel.base import BaseOperatorPanel
from camerainspection.hardware.operator_panel.plc_panel import PLCOperatorPanel
from camerainspection.hardware.operator_panel.simulator import OperatorPanelSimulator
from camerainspection.hardware.plc.base import BasePLC


def build_operator_panel(config: dict[str, Any] | None = None, plc: BasePLC | None = None) -> BaseOperatorPanel:
    """Build operator panel instance."""
    if not config:
        return OperatorPanelSimulator()

    adapter = str(config.get("adapter", "simulator")).lower()
    if adapter in ("plc", "industrial") and plc is not None:
        return PLCOperatorPanel(
            plc=plc,
            start_input=int(config.get("start_input", 30)),
            stop_input=int(config.get("stop_input", 31)),
            reset_input=int(config.get("reset_input", 32)),
            e_stop_input=int(config.get("e_stop_input", 33)),
        )
    return OperatorPanelSimulator()
