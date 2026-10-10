"""SQLAlchemy ORM models for seat inspections, station results, defects, audit logs, and human review queue."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SeatInspectionRecord(Base):
    """Top-level record for an inspected seat."""

    __tablename__ = "seat_inspections"

    seat_id = Column(String(64), primary_key=True, index=True)
    variant_id = Column(String(64), nullable=False, index=True)
    outcome = Column(String(16), nullable=False, index=True)  # PASS, REVIEW, FAIL
    shadow_mode = Column(Boolean, default=False, nullable=False)
    label_printer_enabled = Column(Boolean, default=False, nullable=False)
    mechanism_cycle_passed = Column(Boolean, default=False, nullable=False)
    lock_sensor_confirmed = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    completed_at = Column(DateTime, nullable=True)

    station_results = relationship(
        "StationResultRecord", back_populates="seat", cascade="all, delete-orphan"
    )
    reviews = relationship(
        "HumanReviewRecord", back_populates="seat", cascade="all, delete-orphan"
    )
    shadow_decisions = relationship(
        "ShadowDecisionRecord", back_populates="seat", cascade="all, delete-orphan"
    )
    audit_samples = relationship(
        "AuditSampleRecord", back_populates="seat", cascade="all, delete-orphan"
    )


class StationResultRecord(Base):
    """Inspection outcome and metrics from an individual station aggregating all camera views."""

    __tablename__ = "station_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seat_id = Column(
        String(64), ForeignKey("seat_inspections.seat_id"), nullable=False, index=True
    )
    station_id = Column(String(32), nullable=False, index=True)
    outcome = Column(String(16), nullable=False, index=True)  # PASS, REVIEW, FAIL
    cycle_time_ms = Column(Float, default=0.0, nullable=False)
    model_version = Column(String(32), default="v0.0.0")
    config_version = Column(String(32), default="v0.0.0")
    raw_image_path = Column(String(512), nullable=True)
    annotated_image_path = Column(String(512), nullable=True)
    camera_results_json = Column(Text, nullable=True)
    camera_image_paths_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    seat = relationship("SeatInspectionRecord", back_populates="station_results")
    defects = relationship(
        "DefectRecord", back_populates="station_result", cascade="all, delete-orphan"
    )
    camera_results = relationship(
        "CameraResultRecord", back_populates="station_result", cascade="all, delete-orphan"
    )


class CameraResultRecord(Base):
    """Per-camera view inspection outcome within a station inspection."""

    __tablename__ = "camera_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_result_id = Column(
        Integer, ForeignKey("station_results.id"), nullable=False, index=True
    )
    camera_name = Column(String(64), nullable=False, index=True)
    view = Column(String(64), nullable=False)
    outcome = Column(String(16), nullable=False)
    pixel_size_mm = Column(Float, default=0.08)
    raw_image_path = Column(String(512), nullable=True)
    annotated_image_path = Column(String(512), nullable=True)
    measurements_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    station_result = relationship("StationResultRecord", back_populates="camera_results")


class DefectRecord(Base):
    """Detailed out-of-spec measurement or AI defect detection."""

    __tablename__ = "defects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_result_id = Column(
        Integer, ForeignKey("station_results.id"), nullable=False, index=True
    )
    defect_type = Column(String(64), nullable=False, index=True)
    outcome = Column(String(16), nullable=False)  # PASS, REVIEW, FAIL
    measured_value = Column(Float, nullable=True)
    nominal_value = Column(Float, nullable=True)
    unit = Column(String(16), default="mm")
    confidence = Column(Float, nullable=True)
    bbox_x = Column(Integer, nullable=True)
    bbox_y = Column(Integer, nullable=True)
    bbox_w = Column(Integer, nullable=True)
    bbox_h = Column(Integer, nullable=True)
    roi_name = Column(String(64), nullable=True)
    camera_name = Column(String(64), nullable=True)
    view = Column(String(64), nullable=True)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    station_result = relationship("StationResultRecord", back_populates="defects")


class HumanReviewRecord(Base):
    """Human inspector decision on items in the REVIEW band.

    Stores inspector adjudication and acts as newly labeled dataset feedback.
    """

    __tablename__ = "human_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seat_id = Column(
        String(64), ForeignKey("seat_inspections.seat_id"), nullable=False, index=True
    )
    station_id = Column(String(32), nullable=True, index=True)
    inspector_id = Column(String(64), nullable=False, index=True)
    status = Column(String(16), default="PENDING", nullable=False, index=True)  # PENDING, RESOLVED
    decision = Column(String(16), nullable=True, index=True)  # PASS, REWORK, SCRAP
    notes = Column(Text, default="")
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    reviewed_at = Column(DateTime, nullable=True)

    seat = relationship("SeatInspectionRecord", back_populates="reviews")


class ShadowDecisionRecord(Base):
    """Inspector decision recorded in shadow mode for comparison against camera verdicts."""

    __tablename__ = "shadow_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seat_id = Column(
        String(64), ForeignKey("seat_inspections.seat_id"), nullable=False, index=True
    )
    inspector_id = Column(String(64), nullable=False, index=True)
    decision = Column(String(16), nullable=False)  # PASS, FAIL
    notes = Column(Text, default="")
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    seat = relationship("SeatInspectionRecord", back_populates="shadow_decisions")


class AuditSampleRecord(Base):
    """Quality auditor random sample check against a master reference."""

    __tablename__ = "audit_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seat_id = Column(
        String(64), ForeignKey("seat_inspections.seat_id"), nullable=False, index=True
    )
    auditor_id = Column(String(64), nullable=False, index=True)
    status = Column(String(16), default="PENDING", nullable=False)  # PENDING, COMPLETED
    decision = Column(String(16), nullable=True)  # PASS, FAIL
    discrepancy_details = Column(Text, default="")
    sampled_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    completed_at = Column(DateTime, nullable=True)

    seat = relationship("SeatInspectionRecord", back_populates="audit_samples")


class AuditLogRecord(Base):
    """Immutable audit trail for OEM compliance and failure investigation."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seat_id = Column(String(64), nullable=True, index=True)
    station_id = Column(String(32), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    details = Column(Text, nullable=False)
    timestamp = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )


class SchemaVersionRecord(Base):
    """Tracks applied schema migration versions."""

    __tablename__ = "schema_version"

    version = Column(Integer, primary_key=True)
    applied_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    description = Column(String(256), nullable=False)
