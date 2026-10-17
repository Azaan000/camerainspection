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


def test_static_mounts_storage_data_configs(api_client: TestClient) -> None:
    """Verify /storage, /data, and /configs are mounted and servable."""
    res_data = api_client.get("/data/station_1/replay/01_pass_clean.png")
    assert res_data.status_code == 200
    assert res_data.headers["content-type"].startswith("image/")

    res_configs = api_client.get("/configs/variants/FRONT_LH_BLACK/golden_images/side_shield.png")
    assert res_configs.status_code == 200
    assert res_configs.headers["content-type"].startswith("image/")

    res_404 = api_client.get("/storage/captures/NONEXISTENT/image.png")
    assert res_404.status_code == 404


def test_defect_gallery_joined_station_result(api_client: TestClient) -> None:
    """Verify defect-gallery returns seat_id, station_id, image_url, bbox, and delta."""
    payload = {
        "seat_id": "SEAT-GALLERY-TEST",
        "station_id": "STATION_2",
        "variant_id": "FRONT_LH_BLACK",
        "outcome": "FAIL",
        "cycle_time_ms": 140.0,
        "defects": [
            {
                "defect_type": "stitch.broken_thread",
                "outcome": "FAIL",
                "measured_value": 0.0,
                "nominal_value": 6.0,
                "unit": "spi",
                "confidence": 0.94,
                "bounding_box": {"x": 120, "y": 80, "w": 40, "h": 30},
                "camera_name": "seam_arm",
                "view": "seam_arm",
                "description": "Broken thread detected along seam boundary",
            }
        ],
        "camera_image_paths": {"seam_arm": "data/station_2/replay/03_fail_broken_thread.png"},
    }
    submit_res = api_client.post("/api/v1/stations/result", json=payload, headers=_AUTH_HEADERS)
    assert submit_res.status_code == 201

    # Query gallery
    gallery_res = api_client.get("/api/v1/dashboard/defect-gallery", headers=_AUTH_HEADERS)
    assert gallery_res.status_code == 200
    items = gallery_res.json()
    assert len(items) >= 1
    defect_item = next(it for it in items if it["seat_id"] == "SEAT-GALLERY-TEST")
    assert defect_item["station_id"] == "STATION_2"
    assert defect_item["bbox"] == [120, 80, 40, 30]
    assert defect_item["delta"] == -6.0
    assert defect_item["image_url"].endswith(".png")

    # Test station filter query param
    st2_res = api_client.get("/api/v1/dashboard/defect-gallery?station_id=STATION_2", headers=_AUTH_HEADERS)
    assert st2_res.status_code == 200
    assert all(it["station_id"] == "STATION_2" for it in st2_res.json())


def test_live_companion_endpoint(api_client: TestClient) -> None:
    """Verify live-companion returns latest snapshots, stations map, and golden references."""
    res = api_client.get("/api/v1/dashboard/live-companion", headers=_AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "seat_id" in data
    assert "variant_id" in data
    assert "latest_inspection" in data
    assert "stations" in data["latest_inspection"]
    assert "golden_reference" in data
    assert "images" in data["golden_reference"]

