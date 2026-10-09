"""Database engine, session management, and persistence helpers."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from camerainspection.core.logging import get_logger
from camerainspection.core.models import (
    OverallSeatInspectionResult,
    StationInspectionResult,
)
from camerainspection.storage.entities import (
    AuditLogRecord,
    Base,
    CameraResultRecord,
    DefectRecord,
    SeatInspectionRecord,
    StationResultRecord,
)

logger = get_logger("storage.db")


class DatabaseManager:
    """Manages database connection and lifecycle."""

    def __init__(self, db_url: str = "sqlite:///./data/inspection.db", echo: bool = False) -> None:
        self.db_url = db_url

        # Ensure directory exists if using SQLite
        if db_url.startswith("sqlite:///"):
            path_str = db_url.replace("sqlite:///", "")
            if path_str and path_str != ":memory:":
                db_path = Path(path_str).resolve()
                db_path.parent.mkdir(parents=True, exist_ok=True)

        if db_url in ("sqlite:///:memory:", "sqlite://"):
            from sqlalchemy.pool import StaticPool
            self.engine = create_engine(
                self.db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=echo,
            )
        else:
            self.engine = create_engine(self.db_url, echo=echo)

        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def init_tables(self) -> None:
        """Create all tables in database if they don't already exist."""
        Base.metadata.create_all(self.engine)
        logger.info(f"Database tables initialized at {self.db_url}")

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database transaction error: {e}")
            raise
        finally:
            session.close()

    def record_station_result(self, res: StationInspectionResult) -> int:
        """Persist a single station result, per-camera results, and defect records."""
        with self.session_scope() as session:
            # Ensure seat record exists
            seat_rec = session.query(SeatInspectionRecord).filter_by(seat_id=res.seat_id).first()
            if not seat_rec:
                seat_rec = SeatInspectionRecord(
                    seat_id=res.seat_id,
                    variant_id=res.variant_id,
                    outcome=res.outcome.value,
                )
                session.add(seat_rec)

            cam_json = (
                json.dumps(
                    {k: v.model_dump() for k, v in res.camera_results.items()},
                    default=str,
                )
                if res.camera_results
                else None
            )
            paths_json = json.dumps(res.camera_image_paths) if res.camera_image_paths else None

            st_rec = StationResultRecord(
                seat_id=res.seat_id,
                station_id=res.station_id,
                outcome=res.outcome.value,
                cycle_time_ms=res.cycle_time_ms,
                model_version=res.model_version,
                config_version=res.config_version,
                raw_image_path=res.raw_image_path,
                annotated_image_path=res.annotated_image_path,
                camera_results_json=cam_json,
                camera_image_paths_json=paths_json,
            )
            session.add(st_rec)
            session.flush()

            # Record per-camera view records
            for cam_name, cam_res in res.camera_results.items():
                cam_rec = CameraResultRecord(
                    station_result_id=st_rec.id,
                    camera_name=cam_res.camera_name,
                    view=cam_res.view,
                    outcome=cam_res.outcome.value,
                    pixel_size_mm=cam_res.pixel_size_mm,
                    raw_image_path=cam_res.raw_image_path,
                    annotated_image_path=cam_res.annotated_image_path,
                    measurements_json=json.dumps(cam_res.measurements) if cam_res.measurements else None,
                )
                session.add(cam_rec)

            for d in res.defects:
                def_rec = DefectRecord(
                    station_result_id=st_rec.id,
                    defect_type=d.defect_type,
                    outcome=d.outcome.value,
                    measured_value=d.measured_value,
                    nominal_value=d.nominal_value,
                    unit=d.unit,
                    confidence=d.confidence,
                    bbox_x=d.bounding_box.x if d.bounding_box else None,
                    bbox_y=d.bounding_box.y if d.bounding_box else None,
                    bbox_w=d.bounding_box.w if d.bounding_box else None,
                    bbox_h=d.bounding_box.h if d.bounding_box else None,
                    roi_name=d.roi_name,
                    camera_name=d.camera_name,
                    view=d.view,
                    description=d.description,
                )
                session.add(def_rec)

            return int(st_rec.id)

    def record_overall_result(self, res: OverallSeatInspectionResult) -> None:
        """Update or create complete seat result record."""
        with self.session_scope() as session:
            seat_rec = session.query(SeatInspectionRecord).filter_by(seat_id=res.seat_id).first()
            if not seat_rec:
                seat_rec = SeatInspectionRecord(
                    seat_id=res.seat_id,
                    variant_id=res.variant_id,
                    outcome=res.outcome.value,
                )
                session.add(seat_rec)

            seat_rec.outcome = res.outcome.value
            seat_rec.shadow_mode = res.shadow_mode
            seat_rec.label_printer_enabled = res.label_printer_enabled
            seat_rec.mechanism_cycle_passed = res.mechanism_cycle_passed
            seat_rec.lock_sensor_confirmed = res.lock_sensor_confirmed
            seat_rec.completed_at = res.timestamp

    def log_audit(
        self,
        event_type: str,
        details: str,
        seat_id: str | None = None,
        station_id: str | None = None,
    ) -> None:
        """Store immutable audit record."""
        with self.session_scope() as session:
            audit = AuditLogRecord(
                seat_id=seat_id,
                station_id=station_id,
                event_type=event_type,
                details=details,
            )
            session.add(audit)

    def queue_for_review(self, seat_id: str, station_id: str | None = None) -> int:
        """Enqueue an inspection that requires human adjudication."""
        from datetime import datetime, timezone
        from camerainspection.storage.entities import HumanReviewRecord

        with self.session_scope() as session:
            rev = HumanReviewRecord(
                seat_id=seat_id,
                station_id=station_id,
                inspector_id="SYSTEM",
                status="PENDING",
            )
            session.add(rev)
            session.flush()
            return int(rev.id)

    def resolve_review(
        self,
        review_id: int,
        inspector_id: str,
        decision: str,
        notes: str = "",
    ) -> None:
        """Resolve a human review record (decision: PASS, REWORK, SCRAP)."""
        from datetime import datetime, timezone
        from camerainspection.storage.entities import HumanReviewRecord

        with self.session_scope() as session:
            rev = session.query(HumanReviewRecord).filter_by(id=review_id).first()
            if rev:
                rev.inspector_id = inspector_id
                rev.status = "RESOLVED"
                rev.decision = decision
                rev.notes = notes
                rev.reviewed_at = datetime.now(timezone.utc)
