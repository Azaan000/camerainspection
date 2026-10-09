"""Modbus / RS-485 serial lighting controller driver."""

from __future__ import annotations

from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.hardware.lighting.base import BaseLightController

logger = get_logger("hardware.lighting.modbus")

# Channel-to-holding-register mapping
_CHANNEL_REGISTERS: dict[str, int] = {
    "dome": 100,
    "low_angle": 101,
    "direct": 102,
    "diffuse": 103,
    "ambient": 104,
}


class ModbusLightController(BaseLightController):
    """Controls multi-channel industrial LED power controllers via Modbus RTU / TCP."""

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 19200,
        slave_id: int = 1,
        plc_adapter: Any = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.slave_id = slave_id
        self.plc_adapter = plc_adapter
        self._cache: dict[str, float] = {}

    def set_intensity(self, channel: str, pct: float) -> None:
        clamped = max(0.0, min(100.0, float(pct)))
        reg = _CHANNEL_REGISTERS.get(channel.lower().strip(), 100)
        self._cache[channel] = clamped
        logger.info(
            f"ModbusLightController: write register {reg} = {int(clamped * 10)} (channel '{channel}' {clamped}%)"
        )
        if self.plc_adapter is not None:
            self.plc_adapter.write_tag(f"LIGHT_{channel.upper()}_CMD", clamped)

    def read_back(self, channel: str) -> float:
        if self.plc_adapter is not None:
            val = self.plc_adapter.read_tag(f"LIGHT_{channel.upper()}_FEEDBACK")
            if val is not None:
                return float(val)
        return self._cache.get(channel, 0.0)
