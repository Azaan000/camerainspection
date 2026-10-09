"""Core data models and enums for inspection results and outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Outcome(str, Enum):
    """Inspection outcome state.

    Safety rule: When aggregating outcomes:
    FAIL takes precedence over REVIEW, which takes precedence over PASS.
    """

    PASS = "PASS"
    REVIEW = "REVIEW"
    FAIL = "FAIL"

    @classmethod
    def aggregate(cls, outcomes: list[Outcome]) -> Outcome:
        """Aggregate multiple check outcomes into a single fail-safe verdict.

        If any is FAIL -> FAIL.
        Else if any is REVIEW -> REVIEW.
        Else if outcomes is not empty and all are PASS -> PASS.
        Else (empty or unhandled) -> FAIL (fail safe).
        """
        if not outcomes:
            return cls.FAIL
        if cls.FAIL in outcomes:
            return cls.FAIL
        if cls.REVIEW in outcomes:
            return cls.REVIEW
        if all(o == cls.PASS for o in outcomes):
            return cls.PASS
        return cls.FAIL


class BoundingBox(BaseModel):
    """Defect bounding box in pixel coordinates."""

    x: int = Field(description="Top-left X coordinate in pixels")
    y: int = Field(description="Top-left Y coordinate in pixels")
    w: int = Field(description="Width in pixels")
    h: int = Field(description="Height in pixels")

    @property
    def x_max(self) -> int:
        return self.x + self.w

    @property
    def y_max(self) -> int:
        return self.y + self.h


class DefectDetail(BaseModel):
    """Detailed record of an individual defect or out-of-spec measurement."""

    defect_type: str
    outcome: Outcome
    measured_value: float | None = None
    nominal_value: float | None = None
    unit: str = "mm"
    confidence: float | None = None
    bounding_box: BoundingBox | None = None
    roi_name: str | None = None
    camera_name: str | None = None
    view: str | None = None
    description: str = ""


class CameraInspectionResult(BaseModel):
    """Structured inspection outcome from an individual camera view on a station."""

    camera_name: str
    view: str
    outcome: Outcome
    defects: list[DefectDetail] = Field(default_factory=list)
    measurements: dict[str, float] = Field(default_factory=dict)
    raw_image_path: str | None = None
    annotated_image_path: str | None = None
    pixel_size_mm: float = 0.08
    metadata: dict[str, Any] = Field(default_factory=dict)


class StationInspectionResult(BaseModel):
    """Structured inspection outcome from a single station aggregating all camera views."""

    model_config = ConfigDict(protected_namespaces=())

    seat_id: str
    station_id: str
    variant_id: str
    outcome: Outcome
    defects: list[DefectDetail] = Field(default_factory=list)
    measurements: dict[str, float] = Field(default_factory=dict)
    camera_results: dict[str, CameraInspectionResult] = Field(default_factory=dict)
    camera_image_paths: dict[str, str] = Field(default_factory=dict)
    raw_image_path: str | None = None
    annotated_image_path: str | None = None
    model_version: str = "v0.0.0"
    config_version: str = "v0.0.0"
    cycle_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class OverallSeatInspectionResult(BaseModel):
    """Combined inspection result across all stations for a seat ID."""

    seat_id: str
    variant_id: str
    outcome: Outcome
    station_results: dict[str, StationInspectionResult] = Field(default_factory=dict)
    mechanism_cycle_passed: bool = False
    lock_sensor_confirmed: bool = False
    label_printer_enabled: bool = False
    shadow_mode: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
