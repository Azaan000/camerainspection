"""Security and authentication route iterator test ensuring fail-closed API policies."""

import os
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from camerainspection.api.app import create_app, validate_seat_id
from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.storage.db import DatabaseManager


def test_app_refuses_to_start_with_weak_or_missing_api_key(in_memory_db: DatabaseManager) -> None:
    """Problem 4 / B2: Server must refuse to start if key is missing, empty, default placeholder, or < 32 chars."""
    with patch.dict(os.environ, {"INSPECTION_API_KEY": ""}):
        with pytest.raises(RuntimeError, match="INSPECTION_API_KEY must be set"):
            create_app(db_manager=in_memory_db)

    with patch.dict(os.environ, {"INSPECTION_API_KEY": "inspector_secret_token_123"}):
        with pytest.raises(RuntimeError, match="must not use default placeholder"):
            create_app(db_manager=in_memory_db)

    with patch.dict(os.environ, {"INSPECTION_API_KEY": "short_key_1234"}):
        with pytest.raises(RuntimeError, match="at least 32 characters long"):
            create_app(db_manager=in_memory_db)


def test_all_routes_require_authentication_except_health(
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator
) -> None:
    """Problem 3 / B1: Route-iterator test asserting 401 on every endpoint except GET /health."""
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db, enable_watchdog=False)
    app = create_app(db_manager=in_memory_db, coordinator=coord)
    client = TestClient(app)

    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        # Skip FastAPI documentation / swagger routes
        if path.startswith(("/docs", "/openapi.json", "/redoc")):
            continue

        for method in methods:
            if method in ("OPTIONS", "HEAD"):
                continue

            # Route resolution: replace path parameters with mock test values
            test_path = path.replace("{seat_id}", "SEAT-TEST-001").replace("{review_id}", "1").replace("{sample_id}", "1")

            # GET /health is explicitly public
            if path == "/health" and method == "GET":
                res = client.get("/health")
                assert res.status_code == 200, f"/health returned {res.status_code}"
                continue

            # Call without authentication headers
            if method == "POST":
                res = client.post(test_path, json={})
            else:
                res = client.get(test_path)

            assert res.status_code == 401, (
                f"Route {method} {test_path} allowed unauthenticated access (status={res.status_code}, body={res.text})"
            )


def test_seat_id_validation_rejects_malicious_inputs() -> None:
    """Problem 5 / B4: Validate seat ID regex to prevent injection or traversal."""
    from fastapi import HTTPException

    # Valid seat IDs
    assert validate_seat_id("SEAT-100") == "SEAT-100"
    assert validate_seat_id("SEAT_100:VARIANT_A") == "SEAT_100:VARIANT_A"
    assert validate_seat_id("PALLET.01-SEAT") == "PALLET.01-SEAT"

    # Invalid seat IDs (traversal, scripting, excessive length)
    with pytest.raises(HTTPException):
        validate_seat_id("../../../etc/passwd")

    with pytest.raises(HTTPException):
        validate_seat_id("<script>alert(1)</script>")

    with pytest.raises(HTTPException):
        validate_seat_id("a" * 65)  # > 64 chars


def test_rate_limiter_blocks_excessive_post_requests(
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator
) -> None:
    """Problem 5 / B3: Rapid bursts exceeding rate limits produce HTTP 429 with Retry-After."""
    from camerainspection.api.app import write_limiter
    # Temporarily set tiny capacity
    orig_cap = write_limiter.capacity
    write_limiter.capacity = 2.0
    write_limiter.buckets.clear()

    try:
        coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db, enable_watchdog=False)
        app = create_app(db_manager=in_memory_db, coordinator=coord)
        client = TestClient(app)

        test_key = os.environ["INSPECTION_API_KEY"]
        headers = {"X-API-Key": test_key}

        payload = {
            "result": {
                "seat_id": "SEAT-BURST-1",
                "station_id": "STATION_1",
                "variant_id": "FRONT_LH_BLACK",
                "outcome": "PASS",
                "cycle_time_ms": 10.0,
            }
        }

        # First request succeeds
        res1 = client.post("/api/v1/stations/result", json=payload, headers=headers)
        assert res1.status_code == 201

        # Second request succeeds
        res2 = client.post("/api/v1/stations/result", json=payload, headers=headers)
        assert res2.status_code == 201

        # Third request exceeds burst limit -> HTTP 429
        res3 = client.post("/api/v1/stations/result", json=payload, headers=headers)
        assert res3.status_code == 429
        assert "Retry-After" in res3.headers
    finally:
        write_limiter.capacity = orig_cap
        write_limiter.buckets.clear()
