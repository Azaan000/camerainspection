"""Unit tests for Phase 5 camera calibration tool and enforcement logic."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from camerainspection.core.config import CameraConfig, StationConfig
from camerainspection.core.models import Outcome
from camerainspection.hardware.camera.synthetic import SyntheticCamera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.station.base_station import BaseStation
from camerainspection.storage.db import DatabaseManager
from camerainspection.tools.calibrate_camera import (
    compute_pixel_size_from_checkerboard,
    compute_pixel_size_from_two_marks,
)
from camerainspection.vision.calibration.fixtures_gen import (
    generate_checkerboard_image,
    generate_two_dot_target_image,
)
from camerainspection.vision.calibration.manager import (
    CalibrationManager,
    CalibrationRecord,
)


def test_checkerboard_calibration_known_answer() -> None:
    # 40px squares, 10.0mm physical -> pixel_size_mm = 10.0 / 40.0 = 0.25 mm/px
    img = generate_checkerboard_image(rows=6, cols=8, square_size_px=40)
    mm_per_px = compute_pixel_size_from_checkerboard(
        img, inner_corners=(5, 7), square_size_mm=10.0
    )
    assert abs(mm_per_px - 0.25) < 0.01


def test_two_marks_calibration_known_answer() -> None:
    # 200px distance, 20.0mm physical -> 0.10 mm/px
    img = generate_two_dot_target_image(distance_px=200)
    mm_per_px = compute_pixel_size_from_two_marks(img, known_distance_mm=20.0)
    assert abs(mm_per_px - 0.10) < 0.005


def test_calibration_manager_expiration_and_persistence(tmp_path: Path) -> None:
    mgr = CalibrationManager(calibrations_dir=tmp_path, max_age_days=10.0)

    # 1. Fresh calibration
    fresh = CalibrationRecord(
        camera_name="test_cam",
        pixel_size_mm=0.08,
        calibrated_at=datetime.now(UTC),
    )
    mgr.save_calibration(fresh)

    valid, outcome, _ = mgr.validate_calibration("test_cam")
    assert valid is True
    assert outcome == Outcome.PASS

    # 2. Expired calibration (15 days old)
    expired = CalibrationRecord(
        camera_name="old_cam",
        pixel_size_mm=0.08,
        calibrated_at=datetime.now(UTC) - timedelta(days=15),
    )
    mgr.save_calibration(expired)

    valid_exp, outcome_exp, msg = mgr.validate_calibration("old_cam")
    assert valid_exp is False
    assert outcome_exp == Outcome.REVIEW  # default non-pass
    assert "expired" in msg

    # 3. Missing calibration
    valid_miss, outcome_miss, msg_miss = mgr.validate_calibration("nonexistent_cam")
    assert valid_miss is False
    assert outcome_miss == Outcome.REVIEW


class DimensionalCheckStation(BaseStation):
    def inspect_image(self, image, variant_id, evaluator, variant_nominals):
        # Produces a dimensional measurement in mm
        return [], {"seam_width_mm": 2.5}, image

    def get_required_measurements(self):
        return ["seam_width_mm"]


def test_station_fails_pass_when_calibration_is_missing(tmp_path: Path) -> None:
    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()
    plc = PLCSimulator()
    plc.connect()

    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text("variant_id: FRONT_LH_BLACK\n")

    cfg = StationConfig(
        station_id="ST_DIM",
        name="Dimensional Station",
        camera=CameraConfig(adapter="synthetic"),
    )

    empty_cal_mgr = CalibrationManager(calibrations_dir=tmp_path / "empty_cals")

    station = DimensionalCheckStation(
        station_config=cfg,
        variants_root=variants_root,
        camera=SyntheticCamera(),
        plc=plc,
        db_manager=db,
        calibration_manager=empty_cal_mgr,
    )

    plc.simulate_arrival("ST_DIM", "SEAT-DIM:FRONT_LH_BLACK")
    res = station.run_cycle()

    # Safety rule: Missing calibration means mm check can NEVER return PASS
    assert res.outcome != Outcome.PASS
    assert any("camera.uncalibrated" in d.defect_type for d in res.defects)
