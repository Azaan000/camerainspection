"""Unit tests for Phase 8 (Shadow mode, shift report, audit sampling, and trace export)."""

from __future__ import annotations

import io
import json
import zipfile
import pytest
from fastapi.testclient import TestClient

from camerainspection.api.app import create_app
from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import (
    SeatInspectionRecord,
    ShadowDecisionRecord,
)
from camerainspection.tools.shift_report import generate_shift_report_dict

_AUTH_HEADERS = {"X-API-Key": "inspector_secret_token_123"}


@pytest.fixture
def client(in_memory_db: DatabaseManager, plc_sim: PLCSimulator) -> TestClient:
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db, enable_watchdog=False)
    app = create_app(db_manager=in_memory_db, coordinator=coord)
    return TestClient(app)


def test_shadow_decision_recording_and_api(client: TestClient, in_memory_db: DatabaseManager) -> None:
    """Test recording inspector shadow mode verdict via API."""
    payload = {
        "seat_id": "SEAT-SHADOW-001",
        "inspector_id": "OP_ALPHA",
        "decision": "PASS",
        "notes": "Looks clean on visual pass.",
    }
    res = client.post("/api/v1/shadow-mode/decision", json=payload, headers=_AUTH_HEADERS)
    assert res.status_code == 200
    assert res.json()["recorded"] is True

    # Bad decision
    bad_res = client.post(
        "/api/v1/shadow-mode/decision",
        json={"seat_id": "SEAT-SHADOW-001", "inspector_id": "OP_ALPHA", "decision": "MAYBE"},
        headers=_AUTH_HEADERS,
    )
    assert bad_res.status_code == 400


def test_shift_report_calculation_and_alert(in_memory_db: DatabaseManager, client: TestClient) -> None:
    """Test false-reject, escape rate, and alert when false rejects exceed 3%."""
    with in_memory_db.session_scope() as session:
        # 100 seats in total
        for i in range(100):
            sid = f"SEAT_{i:03d}"
            # Camera outcome: 90 PASS, 10 FAIL
            cam_outcome = "FAIL" if i < 10 else "PASS"
            seat_rec = SeatInspectionRecord(
                seat_id=sid,
                variant_id="FRONT_LH_BLACK",
                outcome=cam_outcome,
                shadow_mode=True,
                label_printer_enabled=(cam_outcome == "PASS"),
                mechanism_cycle_passed=True,
                lock_sensor_confirmed=True,
            )
            session.add(seat_rec)

            # Inspector reviewed some:
            # For 5 of the 10 camera FAILs, human inspector says PASS (false rejects: 5 / 11 = ~45% > 3%)
            if i < 5:
                session.add(ShadowDecisionRecord(
                    seat_id=sid,
                    inspector_id="AUDITOR_01",
                    decision="PASS",
                ))
            elif i < 10:
                session.add(ShadowDecisionRecord(
                    seat_id=sid,
                    inspector_id="AUDITOR_01",
                    decision="FAIL",
                ))
            elif i == 11:
                # 1 camera PASS where inspector found defect (escape: 1)
                session.add(ShadowDecisionRecord(
                    seat_id=sid,
                    inspector_id="AUDITOR_01",
                    decision="FAIL",
                ))

    # Test shift report via direct function
    with in_memory_db.session_scope() as session:
        rep = generate_shift_report_dict(session, false_reject_threshold_pct=3.0)
        assert rep["total_inspected"] == 100
        assert rep["human_decisions_count"] == 11
        assert rep["compared_sample_size"] == 11
        assert rep["false_reject_count"] == 5
        assert rep["escape_count"] == 1
        assert rep["flagged_false_reject_warning"] is True

    # Test API endpoint
    res = client.get("/api/v1/dashboard/shift-report?threshold_pct=3.0")
    assert res.status_code == 200
    data = res.json()
    assert data["flagged_false_reject_warning"] is True
    assert data["false_reject_count"] == 5


def test_audit_sampling_workflow(client: TestClient, in_memory_db: DatabaseManager) -> None:
    """Test auditor sampling 1-in-N or random PASS seats."""
    # Seed 10 PASS seats
    with in_memory_db.session_scope() as session:
        for i in range(10):
            session.add(SeatInspectionRecord(
                seat_id=f"AUDIT_SEAT_{i}",
                variant_id="FRONT_LH_BLACK",
                outcome="PASS",
                shadow_mode=False,
                label_printer_enabled=True,
                mechanism_cycle_passed=True,
                lock_sensor_confirmed=True,
            ))

    # Trigger audit sampling of 3 seats
    sample_res = client.post("/api/v1/audit/sample?count=3", headers=_AUTH_HEADERS)
    assert sample_res.status_code == 200
    sampled = sample_res.json()["seats"]
    assert len(sampled) == 3

    # List samples
    list_res = client.get("/api/v1/audit/samples")
    assert list_res.status_code == 200
    samples = list_res.json()
    assert len(samples) == 3
    sample_id = samples[0]["id"]
    assert samples[0]["status"] == "PENDING"

    # Submit auditor verdict
    dec_res = client.post(
        f"/api/v1/audit/sample/{sample_id}/decision",
        json={"auditor_id": "QA_LEAD", "decision": "PASS", "discrepancy_details": "Confirmed no defects."},
        headers=_AUTH_HEADERS,
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "COMPLETED"


def test_seat_trace_export_zip(client: TestClient, in_memory_db: DatabaseManager) -> None:
    """Test exporting complete seat inspection trace as a ZIP package."""
    seat_id = "TRACE_SEAT_99"
    with in_memory_db.session_scope() as session:
        session.add(SeatInspectionRecord(
            seat_id=seat_id,
            variant_id="FRONT_LH_BLACK",
            outcome="PASS",
            shadow_mode=False,
            label_printer_enabled=True,
            mechanism_cycle_passed=True,
            lock_sensor_confirmed=True,
        ))
    in_memory_db.log_audit("TEST_EVENT", "Trace export test audit entry", seat_id=seat_id)

    res = client.get(f"/api/v1/seats/{seat_id}/export")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"

    # Inspect zip contents
    zip_bytes = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert "audit_trace.json" in namelist
        trace_data = json.loads(zf.read("audit_trace.json").decode("utf-8"))
        assert trace_data["seat_id"] == seat_id
        assert trace_data["outcome"] == "PASS"
        assert len(trace_data["audit_logs"]) >= 1
