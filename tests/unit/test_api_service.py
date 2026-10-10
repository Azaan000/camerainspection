"""Tests for FastAPI service endpoints (results ingestion, seat query, review queue, audit logs)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from camerainspection.api.app import create_app
from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.storage.db import DatabaseManager

_VALID_KEY = "test_secret_inspection_key_32_characters_long_min!"
_AUTH_HEADERS = {"X-API-Key": _VALID_KEY}
_BEARER_HEADERS = {"Authorization": f"Bearer {_VALID_KEY}"}


@pytest.fixture
def api_client(in_memory_db: DatabaseManager, plc_sim: PLCSimulator) -> TestClient:
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db)
    app = create_app(db_manager=in_memory_db, coordinator=coord)
    return TestClient(app)


def test_api_health(api_client: TestClient) -> None:
    res = api_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_api_auth_validation(api_client: TestClient) -> None:
    """Validate that unauthenticated calls are rejected and both X-API-Key and Bearer succeed."""
    # Unauthenticated call to protected endpoint
    res_no_auth = api_client.get("/api/v1/reviews/pending")
    assert res_no_auth.status_code == 401

    # Bad token
    res_bad_auth = api_client.get("/api/v1/reviews/pending", headers={"X-API-Key": "wrong_token"})
    assert res_bad_auth.status_code == 401

    # Good X-API-Key
    res_x_api = api_client.get("/api/v1/reviews/pending", headers=_AUTH_HEADERS)
    assert res_x_api.status_code == 200

    # Good Bearer token
    res_bearer = api_client.get("/api/v1/reviews/pending", headers=_BEARER_HEADERS)
    assert res_bearer.status_code == 200


def test_api_submit_result_and_query_seat_details(api_client: TestClient) -> None:
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
    # Submission without auth fails
    res_unauth = api_client.post("/api/v1/stations/result", json=payload)
    assert res_unauth.status_code == 401

    # Submission with auth succeeds
    post_res = api_client.post("/api/v1/stations/result", json=payload, headers=_AUTH_HEADERS)
    assert post_res.status_code == 201
    assert post_res.json()["recorded"] is True

    # Query seat - verify detail fields (auth required)
    get_res = api_client.get("/api/v1/seats/SEAT-API-01", headers=_AUTH_HEADERS)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["seat_id"] == "SEAT-API-01"
    assert "mechanism_cycle_passed" in data
    assert "lock_sensor_confirmed" in data
    assert "shadow_mode" in data
    assert "label_printer_enabled" in data
    assert len(data["station_results"]) == 1
    assert data["station_results"][0]["station_id"] == "STATION_1"
    assert "defects" in data["station_results"][0]


def test_api_review_queue_workflow(api_client: TestClient, in_memory_db: DatabaseManager) -> None:
    # Queue a seat for review
    rev_id = in_memory_db.queue_for_review("SEAT-TO-REVIEW", "STATION_2")

    # Fetch pending (with auth)
    pending_res = api_client.get("/api/v1/reviews/pending", headers=_AUTH_HEADERS)
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
        headers=_AUTH_HEADERS,
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["resolved"] is True

    # Audit log entry created (query with auth)
    audit_res = api_client.get("/api/v1/audit?seat_id=SEAT-TO-REVIEW", headers=_AUTH_HEADERS)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 1
