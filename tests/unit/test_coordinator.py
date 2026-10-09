"""Unit and integration tests for InspectionCoordinator and label printer safety interlock."""

from __future__ import annotations

import pytest

from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.models import DefectDetail, Outcome, StationInspectionResult
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import HumanReviewRecord, SeatInspectionRecord


def _make_dummy_result(station_id: str, outcome: Outcome, seat_id: str = "SEAT-100") -> StationInspectionResult:
    return StationInspectionResult(
        seat_id=seat_id,
        station_id=station_id,
        variant_id="FRONT_LH_BLACK",
        outcome=outcome,
        measurements={"recliner_angle_deg": 90.0} if station_id == "STATION_4" else {},
    )


# Test 1: All 4 stations PASS + mechanism lock sensor confirmed -> OEM Label Printer ENABLED
def test_coordinator_enables_label_printer_when_all_pass(
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db)

    # Ingest stations 1, 2, 3
    for st in ["STATION_1", "STATION_2", "STATION_3"]:
        res = coord.register_station_result(_make_dummy_result(st, Outcome.PASS))
        assert res is None  # Partial, waiting for all stations

    # Ingest station 4 -> Finalizes
    overall = coord.register_station_result(_make_dummy_result("STATION_4", Outcome.PASS))
    assert overall is not None
    assert overall.outcome == Outcome.PASS
    assert overall.label_printer_enabled is True
    assert plc_sim.is_label_printer_enabled() is True


# Test 2: Any station FAIL -> Label printer DISABLED, pallet holds
def test_coordinator_disables_label_printer_on_single_failure(
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db)

    coord.register_station_result(_make_dummy_result("STATION_1", Outcome.PASS))
    coord.register_station_result(_make_dummy_result("STATION_2", Outcome.FAIL))  # Fails here
    coord.register_station_result(_make_dummy_result("STATION_3", Outcome.PASS))
    overall = coord.register_station_result(_make_dummy_result("STATION_4", Outcome.PASS))

    assert overall is not None
    assert overall.outcome == Outcome.FAIL
    assert overall.label_printer_enabled is False
    assert plc_sim.is_label_printer_enabled() is False


# Test 3: Unlocked mechanism sensor blocks label printer even if all vision stations PASS
def test_coordinator_blocks_label_printer_when_lock_sensor_unconfirmed(
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=False)  # UNLOCKED
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db)

    overall = None
    for st in ["STATION_1", "STATION_2", "STATION_3", "STATION_4"]:
        overall = coord.register_station_result(_make_dummy_result(st, Outcome.PASS))

    assert overall is not None
    assert overall.label_printer_enabled is False
    assert plc_sim.is_label_printer_enabled() is False


# Test 4: REVIEW outcome enqueues item into human review queue
def test_coordinator_enqueues_review_outcome(
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db)

    seat_id = "SEAT-REV-01"
    coord.register_station_result(_make_dummy_result("STATION_1", Outcome.PASS, seat_id=seat_id))
    coord.register_station_result(_make_dummy_result("STATION_2", Outcome.REVIEW, seat_id=seat_id))
    coord.register_station_result(_make_dummy_result("STATION_3", Outcome.PASS, seat_id=seat_id))
    overall = coord.register_station_result(_make_dummy_result("STATION_4", Outcome.PASS, seat_id=seat_id))

    assert overall is not None
    assert overall.outcome == Outcome.REVIEW

    # Check review queue in database
    with in_memory_db.session_scope() as session:
        queue_item = session.query(HumanReviewRecord).filter_by(seat_id=seat_id).first()
        assert queue_item is not None
        assert queue_item.status == "PENDING"
