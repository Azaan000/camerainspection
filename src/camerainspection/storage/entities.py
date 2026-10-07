"""SQLAlchemy ORM models for seat inspections, station results, defects, and audit logs."""

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


class StationResultRecord(Base):
    """Inspection outcome and metrics from an individual station."""

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
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    seat = relationship("SeatInspectionRecord", back_populates="station_results")
    defects = relationship(
        "DefectRecord", back_populates="station_result", cascade="all, delete-orphan"
    )


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
    description = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    station_result = relationship("StationResultRecord", back_populates="defects")


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
