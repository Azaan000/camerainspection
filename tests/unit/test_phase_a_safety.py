"""Unit tests for Phase A safety fixes: hardware requirements, connect failures, and DB write failure handling."""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from camerainspection.core.config import CameraConfig, StationConfig
from camerainspection.core.exceptions import ConfigurationError
from camerainspection.core.models import Outcome
from camerainspection.hardware.camera.base import BaseCamera
from camerainspection.hardware.camera.factory import build_camera
from camerainspection.hardware.camera.synthetic import SyntheticCamera
from camerainspection.hardware.fixture.simulator import SimulatedFixture
from camerainspection.hardware.lighting.simulator import SimulatedLightController
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.station.base_station import BaseStation
from camerainspection.storage.db import DatabaseManager
from camerainspection.vision.calibration.manager import CalibrationManager


class MinimalTestStation(BaseStation):
    def inspect_image(self, image, variant_id, evaluator, variant_nominals):
        return [], {"test_metric": 1.0}, None

    def get_required_measurements(self):
        return ["test_metric"]


def test_unknown_camera_adapter_raises_configuration_error() -> None:
    """Problem 6 / A3: Unknown camera adapter must raise ConfigurationError at factory & config load time."""
    with pytest.raises(ConfigurationError, match="Unknown camera adapter"):
        build_camera(CameraConfig(adapter="synthetic"), adapter_override="unknown_alien_cam")

    with pytest.raises(ConfigurationError, match="Unknown camera adapter"):
        CameraConfig(adapter="nonexistent_adapter_xyz")


def test_hardware_missing_returns_fail_when_required(tmp_path: Path) -> None:
    """Problem 1 / A1: Missing hardware when require_all_hardware is True must return FAIL with hardware.not_configured."""
    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text("variant_id: FRONT_LH_BLACK\n")

    cfg = StationConfig(
        station_id="ST_HW",
        name="Hardware Test Station",
        camera=CameraConfig(adapter="synthetic"),
    )

    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()
    plc = PLCSimulator()
    plc.connect()

    # Station missing fixture, lighting, and calibration
    station = MinimalTestStation(
        station_config=cfg,
        variants_root=variants_root,
        camera=SyntheticCamera(),
        plc=plc,
        db_manager=db,
        require_all_hardware=True,
    )

    plc.simulate_arrival("ST_HW", "SEAT-HW:FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert any("hardware.not_configured" in d.defect_type for d in res.defects)


def test_hardware_present_allows_pass(tmp_path: Path) -> None:
    """Problem 1 / A1: All hardware objects present allows normal PASS cycle."""
    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text("variant_id: FRONT_LH_BLACK\n")

    cfg = StationConfig(
        station_id="ST_HW_OK",
        name="Hardware OK Station",
        camera=CameraConfig(adapter="synthetic"),
    )

    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()
    plc = PLCSimulator()
    plc.connect()
    fixture = SimulatedFixture()
    lighting = SimulatedLightController()
    cal_mgr = CalibrationManager(calibrations_dir=tmp_path / "cals")

    station = MinimalTestStation(
        station_config=cfg,
        variants_root=variants_root,
        camera=SyntheticCamera(),
        plc=plc,
        db_manager=db,
        fixture=fixture,
        lighting_controller=lighting,
        calibration_manager=cal_mgr,
        require_all_hardware=True,
    )

    plc.simulate_arrival("ST_HW_OK", "SEAT-HW-OK:FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.PASS


def test_db_write_failure_forces_fail_and_holds_pallet(tmp_path: Path) -> None:
    """Problem 2 / A2: DB write failure must downgrade result to FAIL, hold pallet, and prevent PLC PASS."""
    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text("variant_id: FRONT_LH_BLACK\n")

    cfg = StationConfig(
        station_id="ST_DB_FAIL",
        name="DB Fail Station",
        camera=CameraConfig(adapter="synthetic"),
    )

    # Mock DB that raises an exception on record_station_result
    bad_db = MagicMock(spec=DatabaseManager)
    bad_db.record_station_result.side_effect = RuntimeError("Disk full / DB connection lost")

    plc = PLCSimulator()
    plc.connect()

    station = MinimalTestStation(
        station_config=cfg,
        variants_root=variants_root,
        camera=SyntheticCamera(),
        plc=plc,
        db_manager=bad_db,
        require_all_hardware=False,
    )

    plc.simulate_arrival("ST_DB_FAIL", "SEAT-DB-FAIL:FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert any("storage.db_write_failure" in d.defect_type for d in res.defects)
    # Verify PLC state: pallet must be held, and station outcome in shared results must be FAIL
    assert plc.is_pallet_held("ST_DB_FAIL") is True
    assert plc._shared_station_results["ST_DB_FAIL"] == Outcome.FAIL


class FailingConnectCamera(BaseCamera):
    def connect(self) -> None:
        raise ConnectionRefusedError("GigE Vision connection timeout / camera offline")

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return False

    def capture(self):
        raise NotImplementedError

    def get_metadata(self):
        return {"adapter": "failing_mock"}


def test_camera_connect_failure_records_defect_and_continues(tmp_path: Path) -> None:
    """Problem 8 / A5: Camera connect failure is recorded as camera.connect_failure without unhandled crash."""
    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text("variant_id: FRONT_LH_BLACK\n")

    cfg = StationConfig(
        station_id="ST_CONN",
        name="Connect Test Station",
        camera=CameraConfig(adapter="synthetic"),
    )

    station = MinimalTestStation(
        station_config=cfg,
        variants_root=variants_root,
        camera=FailingConnectCamera(),
        require_all_hardware=False,
    )

    res = station.run_cycle()
    assert res.outcome == Outcome.FAIL
    assert any("camera.connect_failure" in d.defect_type for d in res.defects)
