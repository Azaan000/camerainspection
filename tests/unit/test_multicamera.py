"""Unit tests for Phase 2 multi-camera configuration, execution, and fail-safe aggregation."""

from pathlib import Path
import numpy as np
import pytest

from camerainspection.core.config import CameraConfig, ROIConfig, StationConfig
from camerainspection.core.models import Outcome
from camerainspection.hardware.camera.synthetic import SyntheticCamera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.station.base_station import BaseStation
from camerainspection.storage.db import DatabaseManager


class DummyMultiCameraStation(BaseStation):
    """Concrete station for testing multi-camera aggregation lifecycle."""

    def inspect_image(self, image, variant_id, evaluator, variant_nominals):
        return [], {"test_metric": 1.0}, image

    def get_required_measurements(self):
        return ["test_metric"]


def test_station_config_multi_camera_backward_compatibility() -> None:
    # 1. Legacy single camera
    raw_legacy = {
        "station_id": "ST_TEST",
        "name": "Test Station",
        "camera": {"adapter": "synthetic", "resolution": [640, 480]},
    }
    cfg1 = StationConfig.model_validate(raw_legacy)
    assert len(cfg1.cameras) == 1
    assert cfg1.cameras[0].name == "main"
    assert cfg1.camera.adapter == "synthetic"

    # 2. Multi-camera list
    raw_multi = {
        "station_id": "ST_TEST",
        "name": "Test Station",
        "cameras": [
            {"name": "cam_a", "view": "view_a", "adapter": "synthetic"},
            {"name": "cam_b", "view": "view_b", "enabled": False, "adapter": "synthetic"},
        ],
    }
    cfg2 = StationConfig.model_validate(raw_multi)
    assert len(cfg2.cameras) == 2
    assert cfg2.camera.name == "cam_a"
    assert cfg2.cameras[1].enabled is False


def test_multicamera_cycle_execution_and_aggregation(tmp_path: Path) -> None:
    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()
    plc = PLCSimulator()
    plc.connect()

    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text("variant_id: FRONT_LH_BLACK\nhand: LH\n")

    cfg = StationConfig(
        station_id="ST_MULTI",
        name="Multi Camera Test Station",
        cameras=[
            CameraConfig(name="cam1", view="view1", adapter="synthetic"),
            CameraConfig(name="cam2", view="view2", adapter="synthetic"),
            CameraConfig(name="cam3", view="view3", enabled=False, adapter="synthetic"),
        ],
    )

    cam1 = SyntheticCamera(width=320, height=240, pattern="solid_black")
    cam2 = SyntheticCamera(width=320, height=240, pattern="solid_black")
    cam3 = SyntheticCamera(width=320, height=240, pattern="solid_black")

    station = DummyMultiCameraStation(
        station_config=cfg,
        variants_root=variants_root,
        cameras={"cam1": cam1, "cam2": cam2, "cam3": cam3},
        plc=plc,
        db_manager=db,
    )

    plc.simulate_arrival("ST_MULTI", "SEAT-100:FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.PASS
    # Enabled cameras captured
    assert "cam1" in res.camera_results
    assert "cam2" in res.camera_results
    # Disabled camera skipped without error
    assert "cam3" not in res.camera_results
    assert res.camera_results["cam1"].outcome == Outcome.PASS
    assert res.camera_results["cam2"].outcome == Outcome.PASS


def test_multicamera_fails_closed_when_camera_capture_fails(tmp_path: Path) -> None:
    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()
    plc = PLCSimulator()
    plc.connect()

    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text("variant_id: FRONT_LH_BLACK\nhand: LH\n")

    cfg = StationConfig(
        station_id="ST_MULTI_FAIL",
        name="Multi Camera Fail Test Station",
        cameras=[
            CameraConfig(name="cam_ok", view="view_ok", adapter="synthetic"),
            CameraConfig(name="cam_failing", view="view_failing", adapter="replay", replay_dir="nonexistent/dir"),
        ],
    )

    station = DummyMultiCameraStation(
        station_config=cfg,
        variants_root=variants_root,
        plc=plc,
        db_manager=db,
    )

    plc.simulate_arrival("ST_MULTI_FAIL", "SEAT-101:FRONT_LH_BLACK")
    res = station.run_cycle()

    # Safety rule: A camera that fails to capture produces FAIL, worst result wins
    assert res.outcome == Outcome.FAIL
    assert res.camera_results["cam_failing"].outcome == Outcome.FAIL
