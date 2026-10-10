"""Unit and integration tests for Phase 6 hardware adapters, training, and dashboard views."""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from camerainspection.api.app import create_app
from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.models import Outcome, StationInspectionResult
from camerainspection.hardware.camera.basler import BaslerCamera
from camerainspection.hardware.camera.hikrobot import HikrobotCamera
from camerainspection.hardware.plc.modbus import ModbusPLC
from camerainspection.hardware.plc.opcua import OPCUAPLC
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.hardware.plc.snap7 import SiemensSnap7PLC
from camerainspection.storage.db import DatabaseManager
from camerainspection.training.train_anomalib import train_anomalib_patchcore
from camerainspection.training.train_yolo import train_yolo_model


# -------------------------------------------------------------
# 1. Camera Adapters
# -------------------------------------------------------------

def test_basler_camera_lifecycle() -> None:
    cam = BaslerCamera(serial_number="21894123", exposure_us=12000)
    cam.connect()
    assert cam.is_connected() is True
    meta = cam.get_metadata()
    assert meta["adapter"] == "basler"
    assert meta["exposure_us"] == 12000

    frame = cam.capture()
    assert frame is not None
    assert frame.shape == (1944, 2592, 3)

    cam.disconnect()
    assert cam.is_connected() is False


def test_hikrobot_camera_lifecycle() -> None:
    cam = HikrobotCamera(serial_number="DA12345678", exposure_us=10000)
    cam.connect()
    assert cam.is_connected() is True
    meta = cam.get_metadata()
    assert meta["adapter"] == "hikrobot"

    frame = cam.capture()
    assert frame is not None
    assert frame.shape == (1944, 2592, 3)

    cam.disconnect()
    assert cam.is_connected() is False


# -------------------------------------------------------------
# 2. PLC Adapters (Modbus, Snap7, OPC UA)
# -------------------------------------------------------------

def test_modbus_plc_adapter() -> None:
    plc = ModbusPLC(host="127.0.0.1", port=502)
    plc.connect()
    assert plc.is_connected() is True
    assert plc.wait_for_trigger("STATION_1") is True
    barcode = plc.read_barcode("STATION_1")
    assert "PALLET_MODBUS" in barcode

    plc.set_station_result("STATION_1", Outcome.FAIL)
    assert plc._pallet_holds.get("STATION_1") is True

    # Shared Safety Interlock: Must reject printer enable while STATION_1 is FAIL
    plc.set_label_printer_enable(True)
    assert plc.is_label_printer_enabled() is False

    # When all stations pass and lock sensor is confirmed, printer can be enabled
    for st in ["STATION_1", "STATION_2", "STATION_3", "STATION_4"]:
        plc.set_station_result(st, Outcome.PASS)
    plc.simulate_mechanism_sensor(locked=True)
    plc.set_label_printer_enable(True)
    assert plc.is_label_printer_enabled() is True

    plc.disconnect()
    assert plc.is_connected() is False


def test_siemens_snap7_plc_adapter() -> None:
    plc = SiemensSnap7PLC(host="127.0.0.1", rack=0, slot=1)
    plc.connect()
    assert plc.is_connected() is True
    barcode = plc.read_barcode("STATION_2")
    assert "PALLET_SNAP7" in barcode

    plc.simulate_mechanism_sensor(locked=True)
    assert plc.is_mechanism_locked() is True
    plc.disconnect()


def test_opcua_plc_adapter() -> None:
    plc = OPCUAPLC(endpoint="opc.tcp://127.0.0.1:4840")
    plc.connect()
    assert plc.is_connected() is True
    barcode = plc.read_barcode("STATION_3")
    assert "PALLET_OPCUA" in barcode
    plc.disconnect()


# -------------------------------------------------------------
# 3. Training & Evaluation Scripts
# -------------------------------------------------------------

def test_yolo_training_pipeline(tmp_path: Path) -> None:
    dummy_yaml = tmp_path / "data.yaml"
    dummy_yaml.write_text("names: [stitch_defect, loose_end]", encoding="utf-8")

    out_dir = tmp_path / "yolo_run"
    report = train_yolo_model(data_yaml=dummy_yaml, epochs=1, output_dir=out_dir, export_onnx=True)

    assert report["onnx_exported"] is True
    assert "metrics" in report
    assert (out_dir / "evaluation_report.json").exists()


def test_anomalib_training_pipeline(tmp_path: Path) -> None:
    data_dir = tmp_path / "leather_data"
    data_dir.mkdir()
    out_dir = tmp_path / "anomalib_run"

    report = train_anomalib_patchcore(dataset_dir=data_dir, output_dir=out_dir, export_onnx=True)

    assert report["model_architecture"] == "PatchCore"
    assert report["onnx_exported"] is True
    assert (out_dir / "anomalib_report.json").exists()


# -------------------------------------------------------------
# 4. Live Dashboard Views API
# -------------------------------------------------------------

_AUTH_HEADERS = {"X-API-Key": "test_secret_inspection_key_32_characters_long_min!"}


def test_dashboard_api_views(in_memory_db: DatabaseManager, plc_sim: PLCSimulator) -> None:
    coord = InspectionCoordinator(plc=plc_sim, db_manager=in_memory_db)
    app = create_app(db_manager=in_memory_db, coordinator=coord)
    client = TestClient(app)

    # 1. Ingest dummy result to populate data
    st_res = StationInspectionResult(
        seat_id="SEAT-DASH-01",
        station_id="STATION_1",
        variant_id="FRONT_LH_BLACK",
        outcome=Outcome.PASS,
    )
    coord.register_station_result(st_res)

    # View 1: Live line strip
    v1 = client.get("/api/v1/dashboard/live", headers=_AUTH_HEADERS)
    assert v1.status_code == 200
    assert "recent_strip" in v1.json()

    # View 2: Quality trends
    v2 = client.get("/api/v1/dashboard/quality-trends", headers=_AUTH_HEADERS)
    assert v2.status_code == 200
    assert "pass_rate" in v2.json()

    # View 3: Defect gallery
    v3 = client.get("/api/v1/dashboard/defect-gallery", headers=_AUTH_HEADERS)
    assert v3.status_code == 200

    # View 4: Shadow mode
    v4 = client.get("/api/v1/dashboard/shadow-mode", headers=_AUTH_HEADERS)
    assert v4.status_code == 200

    # View 6: System health
    v6 = client.get("/api/v1/dashboard/system-health", headers=_AUTH_HEADERS)
    assert v6.status_code == 200
    assert v6.json()["database_status"] == "healthy"
