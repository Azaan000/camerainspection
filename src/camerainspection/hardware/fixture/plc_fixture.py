"""PLC-backed fixture controller communicating via line PLC tags."""

from __future__ import annotations

import json
from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.hardware.fixture.base import BaseFixture
from camerainspection.hardware.plc.base import BasePLC

logger = get_logger("hardware.fixture.plc")


class PLCFixture(BaseFixture):
    """Fixture controller sending commands and reading sensor feedback via line PLC."""

    def __init__(self, plc: BasePLC) -> None:
        self.plc = plc
        self._target_position = "front"
        self._target_arm_pose: Any = "home"

    def clamp(self) -> None:
        logger.info("PLCFixture: issuing CLAMP command to PLC.")
        self.plc.write_tag("FIXTURE_CLAMP_CMD", True)

    def release(self) -> None:
        logger.info("PLCFixture: issuing UNCLAMP command to PLC.")
        self.plc.write_tag("FIXTURE_CLAMP_CMD", False)

    def is_clamped(self) -> bool:
        val = self.plc.read_tag("FIXTURE_CLAMPED_SENSOR")
        if val is None:
            # Fallback to command state if sensor tag not mapped
            val = self.plc.read_tag("FIXTURE_CLAMP_CMD")
        return bool(val)

    def move_to(self, position: str) -> None:
        pos_clean = position.lower().strip()
        if pos_clean not in self.VALID_POSITIONS:
            raise ValueError(f"Invalid position '{position}'. Must be one of {self.VALID_POSITIONS}")
        self._target_position = pos_clean
        logger.info(f"PLCFixture: commanding turntable position '{pos_clean}' on PLC.")
        self.plc.write_tag("FIXTURE_TARGET_POSITION", pos_clean)

    def move_arm_to(self, pose: dict[str, Any] | str) -> None:
        self._target_arm_pose = pose
        pose_str = json.dumps(pose) if isinstance(pose, dict) else str(pose)
        logger.info(f"PLCFixture: commanding robot arm pose '{pose_str}' on PLC.")
        self.plc.write_tag("ARM_TARGET_POSE", pose_str)

    def is_in_position(self) -> bool:
        in_pos = self.plc.read_tag("FIXTURE_IN_POSITION")
        if in_pos is not None:
            return bool(in_pos)
        # Check actual vs target position
        actual_pos = self.plc.read_tag("FIXTURE_ACTUAL_POSITION")
        if actual_pos is not None:
            return str(actual_pos).lower().strip() == self._target_position
        return True
