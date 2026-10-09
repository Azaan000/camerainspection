"""Tests for FastAPI service endpoints (results ingestion, seat query, review queue, audit logs)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from camerainspection.api.app import create_app
from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.models import Outcome, StationInspectionResult
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.storage.db import DatabaseManager


@pytest.fixture
def api_client(in_memory_db: DatabaseManager, plc_sim: PLCSimulator) -> TestClient:
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db)
    app = create_app(db_manager=in_memory_db, coordinator=coord)
    return TestClient(app)


def test_api_health(api_client: TestClient) -> None:
    res = api_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_api_submit_result_and_query_seat(api_client: TestClient) -> None:
    payload = {
        "result": {
            "seat_id": "SEAT-API-01",
            "station_id": "STATION_1",
            "variant_id": "FRONT_LH_BLACK",
            "outcome": "PASS",
            "cycle_time_ms": 120.0,
            "defects": [],
            "measurements": {"seating_face.defect_count": 0.0},
        }
    }
    post_res = api_client.post("/api/v1/stations/result", json=payload)
    assert post_res.status_code == 201
    assert post_res.json()["recorded"] is True

    # Query seat
    get_res = api_client.get("/api/v1/seats/SEAT-API-01")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["seat_id"] == "SEAT-API-01"
    assert len(data["station_results"]) == 1
    assert data["station_results"][0]["station_id"] == "STATION_1"


def test_api_review_queue_workflow(api_client: TestClient, in_memory_db: DatabaseManager) -> None:
    # Queue a seat for review
    rev_id = in_memory_db.queue_for_review("SEAT-TO-REVIEW", "STATION_2")

    # Fetch pending
    pending_res = api_client.get("/api/v1/reviews/pending")
    assert pending_res.status_code == 200
    pending_items = pending_res.json()
    assert any(item["seat_id"] == "SEAT-TO-REVIEW" for item in pending_items)

    dec_payload = {
        "inspector_id": "OPERATOR_42",
        "decision": "PASS",
        "notes": "Reviewed boundary stitch sample under magnification. Acceptable.",
    }
    dec_res = api_client.post(
        f"/api/v1/reviews/{rev_id}/decision",
        json=dec_payload,
        headers={"X-API-Key": "inspector_secret_token_123"},
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["resolved"] is True

    # Audit log entry created
    audit_res = api_client.get("/api/v1/audit?seat_id=SEAT-TO-REVIEW")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 1
    assert "HUMAN_REVIEW_RESOLVED" in logs[0]["event_type"]
