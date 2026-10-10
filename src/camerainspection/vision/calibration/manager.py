"""Camera dimensional calibration management, expiration validation, and storage."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from camerainspection.core.logging import get_logger
from camerainspection.core.models import Outcome

logger = get_logger("vision.calibration")

# Default calibration directory
DEFAULT_CALIBRATION_DIR = Path("configs/calibrations")

# Target ranges from Phase 2
RESOLUTION_TARGETS: dict[str, tuple[float, float]] = {
    "stitch": (0.08, 0.10),
    "leather": (0.15, 0.20),
    "plastic": (0.15, 0.25),
    "mechanism": (0.12, 0.22),
}


class CalibrationRecord(BaseModel):
    """Immutable record of camera pixel-to-millimetre physical calibration."""

    camera_name: str
    pixel_size_mm: float
    calibrated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    operator_id: str = "OPERATOR_DEFAULT"
    image_path: str = ""
    pattern_type: str = "checkerboard"
    target_dimension_mm: float = 20.0
    category: str = "generic"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_expired(self, max_age_days: float = 30.0) -> bool:
        """Check whether calibration age exceeds expiration threshold."""
        now = datetime.now(UTC)
        cal_time = self.calibrated_at
        if cal_time.tzinfo is None:
            cal_time = cal_time.replace(tzinfo=UTC)
        age_seconds = (now - cal_time).total_seconds()
        return age_seconds > (max_age_days * 86400.0)


class CalibrationManager:
    """Manages loading, verifying, and enforcing camera calibration status."""

    def __init__(
        self,
        calibrations_dir: Path | str = DEFAULT_CALIBRATION_DIR,
        max_age_days: float = 30.0,
        strict_fail: bool = False,
    ) -> None:
        self.calibrations_dir = Path(calibrations_dir)
        self.calibrations_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_days = max_age_days
        self.strict_fail = strict_fail
        self._cache: dict[str, CalibrationRecord] = {}

    def get_calibration_path(self, camera_name: str) -> Path:
        clean_name = camera_name.replace("/", "_").replace("\\", "_")
        return self.calibrations_dir / f"{clean_name}.json"

    def save_calibration(self, record: CalibrationRecord) -> Path:
        """Persist calibration record to JSON."""
        path = self.get_calibration_path(record.camera_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record.model_dump(mode="json"), f, indent=2)
        self._cache[record.camera_name] = record
        logger.info(
            f"Saved calibration for '{record.camera_name}': {record.pixel_size_mm:.4f} mm/px "
            f"(operator: {record.operator_id})"
        )
        return path

    def load_calibration(self, camera_name: str) -> CalibrationRecord | None:
        """Load calibration record from disk or memory cache."""
        if camera_name in self._cache:
            return self._cache[camera_name]

        path = self.get_calibration_path(camera_name)
        if not path.exists():
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            record = CalibrationRecord.model_validate(data)
            self._cache[camera_name] = record
            return record
        except Exception as e:
            logger.error(f"Failed to read calibration for '{camera_name}' at {path}: {e}")
            return None

    def validate_calibration(
        self,
        camera_name: str,
        category: str = "generic",
    ) -> tuple[bool, Outcome, str]:
        """Validate presence, age, and resolution target compliance.

        Returns:
            tuple[is_valid, enforced_outcome, message]
            If invalid -> returns (False, FAIL or REVIEW, reason).
        """
        rec = self.load_calibration(camera_name)
        default_error_outcome = Outcome.FAIL if self.strict_fail else Outcome.REVIEW

        if rec is None:
            msg = (
                f"Missing camera calibration for '{camera_name}'. "
                "Millimetre checks require affirmative physical calibration."
            )
            logger.warning(msg)
            return False, default_error_outcome, msg

        if rec.is_expired(self.max_age_days):
            msg = (
                f"Camera calibration for '{camera_name}' expired "
                f"(calibrated {rec.calibrated_at.isoformat()}, max age {self.max_age_days} days)."
            )
            logger.warning(msg)
            return False, default_error_outcome, msg

        # Target range check from Phase 2
        target_range = RESOLUTION_TARGETS.get(category)
        if target_range:
            low, high = target_range
            if not (low <= rec.pixel_size_mm <= high):
                logger.warning(
                    f"Calibrated pixel size {rec.pixel_size_mm:.4f} mm/px for '{camera_name}' "
                    f"is outside recommended {category} target range [{low:.3f}, {high:.3f}] mm/px."
                )

        return True, Outcome.PASS, f"Calibration valid ({rec.pixel_size_mm:.4f} mm/px)."
