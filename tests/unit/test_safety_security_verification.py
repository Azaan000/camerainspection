"""Comprehensive verification tests for safety logic, printer interlocks, security auth, and measurement validity."""

from __future__ import annotations

import math
import time
import pytest
from fastapi.testclient import TestClient

from camerainspection.api.app import create_app
from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.models import DefectDetail, Outcome, StationInspectionResult
from camerainspection.hardware.plc.modbus import ModbusPLC
from camerainspection.hardware.plc.opcua import OPCUAPLC
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.hardware.plc.snap7 import SiemensSnap7PLC
from camerainspection.station.base_station import BaseStation
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import HumanReviewRecord, SeatInspectionRecord, StationResultRecord


def build_plc_adapter(adapter: str):
    """Compatibility shim: build a PLC adapter by short name (simulator/modbus/snap7/opcua)."""
    adapter = adapter.lower().strip()
    if adapter == "modbus":
        plc = ModbusPLC(host="127.0.0.1", port=502, expected_stations=["STATION_1", "STATION_2", "STATION_3", "STATION_4"])
    elif adapter == "snap7":
        plc = SiemensSnap7PLC(host="127.0.0.1", rack=0, slot=1, expected_stations=["STATION_1", "STATION_2", "STATION_3", "STATION_4"])
    elif adapter == "opcua":
        plc = OPCUAPLC(endpoint="opc.tcp://127.0.0.1:4840", expected_stations=["STATION_1", "STATION_2", "STATION_3", "STATION_4"])
    else:
        plc = PLCSimulator(expected_stations=["STATION_1", "STATION_2", "STATION_3", "STATION_4"])
        plc.simulate_mechanism_sensor(locked=True)
    plc.connect()
    return plc


def _make_st_res(
    station_id: str,
    outcome: Outcome,
    seat_id: str = "SEAT-100",
    recliner_angle: float = 90.0,
) -> StationInspectionResult:
    measurements = {}
    if station_id == "STATION_4":
        measurements["recliner_angle_deg"] = recliner_angle
        measurements["track_end_position_mm"] = 240.0
        measurements["lock_sensor_confirmed"] = 1.0

    return StationInspectionResult(
        seat_id=seat_id,
        station_id=station_id,
        variant_id="FRONT_LH_BLACK",
        outcome=outcome,
        measurements=measurements,
    )


# ----------------------------------------------------------------------
# 1. Printer Sequence Across Two Seats (Seat A Passes, Seat B Fails)
# ----------------------------------------------------------------------

def test_two_seat_printer_sequence_interlock(
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db, enable_watchdog=False)

    # 1. Seat A runs all 4 stations and PASSES
    for st in ["STATION_1", "STATION_2", "STATION_3", "STATION_4"]:
        coord.register_station_result(_make_st_res(st, Outcome.PASS, seat_id="SEAT_A"))

    # Printer MUST be enabled for Seat A
    assert plc_sim.is_label_printer_enabled() is True
    assert coord._currently_printing_seat_id == "SEAT_A"

    # 2. Seat B arrives at Station 1 -> Printer must be IMMEDIATELY shut off
    coord.register_station_result(_make_st_res("STATION_1", Outcome.PASS, seat_id="SEAT_B"))
    assert plc_sim.is_label_printer_enabled() is False
    assert coord._currently_printing_seat_id is None

    # 3. Seat B fails Station 2
    coord.register_station_result(_make_st_res("STATION_2", Outcome.FAIL, seat_id="SEAT_B"))
    assert plc_sim.is_label_printer_enabled() is False

    # 4. Seat B finishes remaining stations -> Printer stays OFF
    coord.register_station_result(_make_st_res("STATION_3", Outcome.PASS, seat_id="SEAT_B"))
    overall_b = coord.register_station_result(_make_st_res("STATION_4", Outcome.PASS, seat_id="SEAT_B"))

    assert overall_b is not None
    assert overall_b.outcome == Outcome.FAIL
    assert overall_b.label_printer_enabled is False
    assert plc_sim.is_label_printer_enabled() is False


def test_mark_seat_printed_clears_printer_output(
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db, enable_watchdog=False)

    for st in ["STATION_1", "STATION_2", "STATION_3", "STATION_4"]:
        coord.register_station_result(_make_st_res(st, Outcome.PASS, seat_id="SEAT_APPLY"))

    assert plc_sim.is_label_printer_enabled() is True
    assert coord._currently_printing_seat_id == "SEAT_APPLY"

    # Applicator confirms application
    coord.mark_seat_printed("SEAT_APPLY")

    assert plc_sim.is_label_printer_enabled() is False
    assert coord._currently_printing_seat_id is None
    assert "SEAT_APPLY" not in coord._seat_printer_eligible


# ----------------------------------------------------------------------
# 2. Station 4 Review Approval Enables Printer & Mechanism Cycle
# ----------------------------------------------------------------------

def test_station_4_review_approval_enables_printer(
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db, enable_watchdog=False)
    app = create_app(db_manager=in_memory_db, coordinator=coord)
    client = TestClient(app)

    seat_id = "SEAT_ST4_REV"
    for st in ["STATION_1", "STATION_2", "STATION_3"]:
        coord.register_station_result(_make_st_res(st, Outcome.PASS, seat_id=seat_id))

    # Station 4 flagged as REVIEW
    overall = coord.register_station_result(_make_st_res("STATION_4", Outcome.REVIEW, seat_id=seat_id))
    assert overall is not None
    assert overall.outcome == Outcome.REVIEW
    assert overall.label_printer_enabled is False
    assert plc_sim.is_label_printer_enabled() is False

    # Get review ID
    with in_memory_db.session_scope() as session:
        rev = session.query(HumanReviewRecord).filter_by(seat_id=seat_id).first()
        assert rev is not None
        rev.station_id = "STATION_4"
        review_id = rev.id

    # Human inspector approves as PASS
    res = client.post(
        f"/api/v1/reviews/{review_id}/decision",
        json={"inspector_id": "INSP_01", "decision": "PASS", "notes": "Recliner angle within boundary."},
        headers={"X-API-Key": "test_secret_inspection_key_32_characters_long_min!"},
    )
    assert res.status_code == 200
    assert res.json()["resolved"] is True

    # Verification: Printer is now enabled, mechanism cycle confirmed, and seat outcome is PASS
    assert plc_sim.is_label_printer_enabled() is True
    with in_memory_db.session_scope() as session:
        rec = session.query(SeatInspectionRecord).filter_by(seat_id=seat_id).first()
        assert rec is not None
        assert rec.outcome == "PASS"
        assert rec.label_printer_enabled is True
        assert rec.mechanism_cycle_passed is True


# ----------------------------------------------------------------------
# 3. Affirmative Measurement Validation (NaN, Inf, Null)
# ----------------------------------------------------------------------

class DummyStation(BaseStation):
    def inspect_image(self, image, variant_id, evaluator, variant_nominals):
        return [], {}, None

    def get_required_measurements(self) -> list[str]:
        return ["crit_len_mm", "crit_angle_deg"]


def test_measurement_validity_filters_nan_and_inf() -> None:
    st = DummyStation.__new__(DummyStation)
    assert st.is_valid_measurement("crit_len_mm", 12.5) is True
    assert st.is_valid_measurement("crit_len_mm", 0.0) is True
    assert st.is_valid_measurement("crit_len_mm", None) is False
    assert st.is_valid_measurement("crit_len_mm", float("nan")) is False
    assert st.is_valid_measurement("crit_len_mm", float("inf")) is False
    assert st.is_valid_measurement("crit_len_mm", "not_a_number") is False


# ----------------------------------------------------------------------
# 4. Watchdog Printer Pulse Auto-Disable
# ----------------------------------------------------------------------

def test_watchdog_pulse_timeout_disables_printer(
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    # Configure tiny 0.1s pulse duration for unit test
    coord = InspectionCoordinator(
        plc=plc_sim,
        db_manager=in_memory_db,
        print_pulse_timeout_s=0.1,
        enable_watchdog=False,
    )

    for st in ["STATION_1", "STATION_2", "STATION_3", "STATION_4"]:
        coord.register_station_result(_make_st_res(st, Outcome.PASS, seat_id="SEAT_PULSE"))

    assert plc_sim.is_label_printer_enabled() is True
    time.sleep(0.15)
    # Trigger watchdog enforcement
    coord._enforce_printer_timeout_unlocked()

    assert plc_sim.is_label_printer_enabled() is False
    assert coord._currently_printing_seat_id is None


# ----------------------------------------------------------------------
# 5. Build PLC Adapters Factory
# ----------------------------------------------------------------------

def test_build_plc_adapters_factory() -> None:
    sim_plc = build_plc_adapter("simulator")
    assert sim_plc.is_connected() is True
    assert sim_plc.is_mechanism_locked() is True

    modbus_plc = build_plc_adapter("modbus")
    assert modbus_plc.is_connected() is True

    snap7_plc = build_plc_adapter("snap7")
    assert snap7_plc.is_connected() is True

    opcua_plc = build_plc_adapter("opcua")
    assert opcua_plc.is_connected() is True
