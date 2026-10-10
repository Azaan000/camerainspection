"""SQLAlchemy ORM models for seat inspections, station results, defects, audit logs, and human review queue."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SeatInspectionRecord(Base):
    """Top-level record for an inspected seat."""

    __tablename__ = "seat_inspections"

    seat_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    variant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # PASS, REVIEW, FAIL
    shadow_mode: Mapped[bool] = mapped_column(default=False, nullable=False)
    label_printer_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    mechanism_cycle_passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    lock_sensor_confirmed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    station_results: Mapped[list[StationResultRecord]] = relationship(
        "StationResultRecord", back_populates="seat", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[HumanReviewRecord]] = relationship(
        "HumanReviewRecord", back_populates="seat", cascade="all, delete-orphan"
    )
    shadow_decisions: Mapped[list[ShadowDecisionRecord]] = relationship(
        "ShadowDecisionRecord", back_populates="seat", cascade="all, delete-orphan"
    )
    audit_samples: Mapped[list[AuditSampleRecord]] = relationship(
        "AuditSampleRecord", back_populates="seat", cascade="all, delete-orphan"
    )


class StationResultRecord(Base):
    """Inspection outcome and metrics from an individual station aggregating all camera views."""

    __tablename__ = "station_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seat_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("seat_inspections.seat_id"), nullable=False, index=True
    )
    station_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # PASS, REVIEW, FAIL
    cycle_time_ms: Mapped[float] = mapped_column(default=0.0, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), default="v0.0.0")
    config_version: Mapped[str] = mapped_column(String(32), default="v0.0.0")
    raw_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    annotated_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    camera_results_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    camera_image_paths_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    seat: Mapped[SeatInspectionRecord] = relationship(
        "SeatInspectionRecord", back_populates="station_results"
    )
    defects: Mapped[list[DefectRecord]] = relationship(
        "DefectRecord", back_populates="station_result", cascade="all, delete-orphan"
    )
    camera_results: Mapped[list[CameraResultRecord]] = relationship(
        "CameraResultRecord", back_populates="station_result", cascade="all, delete-orphan"
    )


class CameraResultRecord(Base):
    """Per-camera view inspection outcome within a station inspection."""

    __tablename__ = "camera_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    station_result_id: Mapped[int] = mapped_column(
        ForeignKey("station_results.id"), nullable=False, index=True
    )
    camera_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    view: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    pixel_size_mm: Mapped[float] = mapped_column(default=0.08)
    raw_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    annotated_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    measurements_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False
    )

    station_result: Mapped[StationResultRecord] = relationship(
        "StationResultRecord", back_populates="camera_results"
    )


class DefectRecord(Base):
    """Detailed out-of-spec measurement or AI defect detection."""

    __tablename__ = "defects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    station_result_id: Mapped[int] = mapped_column(
        ForeignKey("station_results.id"), nullable=False, index=True
    )
    defect_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)  # PASS, REVIEW, FAIL
    measured_value: Mapped[float | None] = mapped_column(nullable=True)
    nominal_value: Mapped[float | None] = mapped_column(nullable=True)
    unit: Mapped[str] = mapped_column(String(16), default="mm")
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    bbox_x: Mapped[int | None] = mapped_column(nullable=True)
    bbox_y: Mapped[int | None] = mapped_column(nullable=True)
    bbox_w: Mapped[int | None] = mapped_column(nullable=True)
    bbox_h: Mapped[int | None] = mapped_column(nullable=True)
    roi_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    camera_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    view: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False
    )

    station_result: Mapped[StationResultRecord] = relationship(
        "StationResultRecord", back_populates="defects"
    )


class HumanReviewRecord(Base):
    """Human inspector decision on items in the REVIEW band.

    Stores inspector adjudication and acts as newly labeled dataset feedback.
    """

    __tablename__ = "human_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seat_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("seat_inspections.seat_id"), nullable=False, index=True
    )
    station_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    inspector_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), default="PENDING", nullable=False, index=True
    )  # PENDING, RESOLVED
    decision: Mapped[str | None] = mapped_column(
        String(16), nullable=True, index=True
    )  # PASS, REWORK, SCRAP
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    seat: Mapped[SeatInspectionRecord] = relationship(
        "SeatInspectionRecord", back_populates="reviews"
    )


class ShadowDecisionRecord(Base):
    """Inspector decision recorded in shadow mode for comparison against camera verdicts."""

    __tablename__ = "shadow_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seat_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("seat_inspections.seat_id"), nullable=False, index=True
    )
    inspector_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)  # PASS, FAIL
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    seat: Mapped[SeatInspectionRecord] = relationship(
        "SeatInspectionRecord", back_populates="shadow_decisions"
    )


class AuditSampleRecord(Base):
    """Quality auditor random sample check against a master reference."""

    __tablename__ = "audit_samples"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seat_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("seat_inspections.seat_id"), nullable=False, index=True
    )
    auditor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)  # PENDING, COMPLETED
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)  # PASS, FAIL
    discrepancy_details: Mapped[str] = mapped_column(Text, default="")
    sampled_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    seat: Mapped[SeatInspectionRecord] = relationship(
        "SeatInspectionRecord", back_populates="audit_samples"
    )


class AuditLogRecord(Base):
    """Immutable audit trail for OEM compliance and failure investigation."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seat_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    station_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False, index=True
    )


class SchemaVersionRecord(Base):
    """Tracks applied schema migration versions."""

    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False
    )
    description: Mapped[str] = mapped_column(String(256), nullable=False)
