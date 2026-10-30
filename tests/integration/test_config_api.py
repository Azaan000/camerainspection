"""Integration tests for Configuration Management REST API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from camerainspection.api.app import create_app
from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.storage.db import DatabaseManager

_VALID_KEY = "test_secret_inspection_key_32_characters_long_min!"
_AUTH_HEADERS = {"X-API-Key": _VALID_KEY}


@pytest.fixture
def config_api_client(in_memory_db: DatabaseManager, plc_sim: PLCSimulator) -> TestClient:
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db)
    app = create_app(db_manager=in_memory_db, coordinator=coord)
    return TestClient(app)


def test_get_all_station_configs_api(config_api_client: TestClient) -> None:
    res = config_api_client.get("/api/v1/config/stations", headers=_AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "stations" in data
    assert "STATION_2" in data["stations"]
    assert data["stations"]["STATION_2"]["station_id"] == "STATION_2"


def test_get_specific_station_config_api(config_api_client: TestClient) -> None:
    res = config_api_client.get("/api/v1/config/stations/STATION_2", headers=_AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["station_id"] == "STATION_2"
    assert "model" in data


def test_update_station_config_api(config_api_client: TestClient) -> None:
    get_res = config_api_client.get("/api/v1/config/stations/STATION_2", headers=_AUTH_HEADERS)
    assert get_res.status_code == 200
    cfg = get_res.json()

    orig_desc = cfg.get("description", "")
    cfg["description"] = "Updated via API test"

    try:
        put_res = config_api_client.put(
            "/api/v1/config/stations/STATION_2",
            json=cfg,
            headers=_AUTH_HEADERS,
        )
        assert put_res.status_code == 200
        data = put_res.json()
        assert data["success"] is True
        assert data["config"]["description"] == "Updated via API test"
    finally:
        cfg["description"] = orig_desc
        config_api_client.put("/api/v1/config/stations/STATION_2", json=cfg, headers=_AUTH_HEADERS)


def test_get_and_update_limits_api(config_api_client: TestClient) -> None:
    res = config_api_client.get("/api/v1/config/limits", headers=_AUTH_HEADERS)
    assert res.status_code == 200
    limits_data = res.json()
    assert "limits" in limits_data

    orig_fail_at = limits_data["limits"]["stitch"]["skip_length_mm"]["fail_at"]
    limits_data["limits"]["stitch"]["skip_length_mm"]["fail_at"] = 5.5

    try:
        put_res = config_api_client.put(
            "/api/v1/config/limits",
            json=limits_data,
            headers=_AUTH_HEADERS,
        )
        assert put_res.status_code == 200
        assert put_res.json()["success"] is True
        assert put_res.json()["limits"]["limits"]["stitch"]["skip_length_mm"]["fail_at"] == 5.5
    finally:
        limits_data["limits"]["stitch"]["skip_length_mm"]["fail_at"] = orig_fail_at
        config_api_client.put("/api/v1/config/limits", json=limits_data, headers=_AUTH_HEADERS)
