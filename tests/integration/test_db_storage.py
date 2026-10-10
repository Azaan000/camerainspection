"""Integration tests for database persistence and audit logs."""

from camerainspection.core.models import (
    BoundingBox,
    DefectDetail,
    Outcome,
    OverallSeatInspectionResult,
    StationInspectionResult,
)
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import (
    AuditLogRecord,
    SeatInspectionRecord,
    StationResultRecord,
)


def test_station_result_and_defect_storage(in_memory_db: DatabaseManager) -> None:
    defect = DefectDetail(
        defect_type="stitch.broken_thread",
        outcome=Outcome.FAIL,
        measured_value=1.0,
        unit="count",
        confidence=0.95,
        bounding_box=BoundingBox(x=100, y=150, w=30, h=40),
        roi_name="main_seam",
        description="Broken stitch detected along upper boundary.",
    )

    res = StationInspectionResult(
        seat_id="SEAT-9988",
        station_id="STATION_2",
        variant_id="FRONT_LH_BLACK",
        outcome=Outcome.FAIL,
        defects=[defect],
        measurements={"spi": 6.1},
        model_version="v1.0.0",
        config_version="v0.1.0",
        cycle_time_ms=120.5,
    )

    rec_id = in_memory_db.record_station_result(res)
    assert rec_id > 0

    with in_memory_db.session_scope() as session:
        seat = session.query(SeatInspectionRecord).filter_by(seat_id="SEAT-9988").first()
        assert seat is not None
        assert seat.variant_id == "FRONT_LH_BLACK"
        assert seat.outcome == "FAIL"

        st_rec = session.query(StationResultRecord).filter_by(id=rec_id).first()
        assert st_rec is not None
        assert st_rec.station_id == "STATION_2"
        assert len(st_rec.defects) == 1

        d_rec = st_rec.defects[0]
        assert d_rec.defect_type == "stitch.broken_thread"
        assert d_rec.bbox_x == 100
        assert d_rec.confidence == 0.95


def test_overall_inspection_record(in_memory_db: DatabaseManager) -> None:
    overall = OverallSeatInspectionResult(
        seat_id="SEAT-5555",
        variant_id="FRONT_RH_BLACK",
        outcome=Outcome.PASS,
        mechanism_cycle_passed=True,
        lock_sensor_confirmed=True,
        label_printer_enabled=True,
        shadow_mode=False,
    )
    in_memory_db.record_overall_result(overall)

    with in_memory_db.session_scope() as session:
        rec = session.query(SeatInspectionRecord).filter_by(seat_id="SEAT-5555").first()
        assert rec is not None
        assert rec.outcome == "PASS"
        assert rec.label_printer_enabled is True
        assert rec.lock_sensor_confirmed is True


def test_audit_log_recording(in_memory_db: DatabaseManager) -> None:
    in_memory_db.log_audit(
        event_type="EMERGENCY_STOP",
        details="Safety curtain broken at station 3",
        seat_id="SEAT-1234",
        station_id="STATION_3",
    )

    with in_memory_db.session_scope() as session:
        log = session.query(AuditLogRecord).first()
        assert log is not None
        assert log.event_type == "EMERGENCY_STOP"
        assert log.seat_id == "SEAT-1234"
