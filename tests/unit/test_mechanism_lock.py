"""Unit tests for Phase 6 mechanism lock confirmation and multi-signal safety validation."""

from pathlib import Path
import pytest

from camerainspection.core.config import CameraConfig, ROIConfig, StationConfig
from camerainspection.core.models import Outcome
from camerainspection.hardware.camera.synthetic import SyntheticCamera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.station.station_4 import Station4Service
from camerainspection.storage.db import DatabaseManager
from camerainspection.vision.station4.fixtures_gen import generate_station4_test_scene


def _build_test_station4(tmp_path: Path, plc: PLCSimulator) -> Station4Service:
    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()

    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text(
        "variant_id: FRONT_LH_BLACK\n"
        "hand: LH\n"
        "nominals:\n"
        "  mechanism:\n"
        "    recliner_angle_deg: 90.0\n"
        "    track_end_position_mm: 240.0\n"
    )

    cfg = StationConfig(
        station_id="STATION_4",
        name="Mechanism Safety Station",
        regions_of_interest={
            "recliner_pivot": ROIConfig(x=400, y=800, w=500, h=500),
            "track_travel": ROIConfig(x=200, y=1400, w=2000, h=400),
        },
        mechanism={
            "min_lock_torque_nm": 15.0,
            "max_slip_back_mm": 1.0,
        },
        camera=CameraConfig(adapter="synthetic", pixel_size_mm=0.15),
    )

    # Frame with nominal 90.0 deg angle and 240.0 mm position
    good_frame = generate_station4_test_scene(recliner_angle_deg=90.0, track_end_pos_mm=240.0)

    class PerfectImageCamera(SyntheticCamera):
        def capture(self):
            return good_frame.copy()

    cam = PerfectImageCamera()
    return Station4Service(
        station_config=cfg,
        variants_root=variants_root,
        camera=cam,
        plc=plc,
        db_manager=db,
        default_limits_path=Path("configs/variants/default_limits.yaml"),
    )


def test_unlocked_sensor_fails_even_when_vision_passes(tmp_path: Path) -> None:
    plc = PLCSimulator()
    plc.connect()
    # Image is 100% nominal, torque is 20Nm, actuator is 240mm, but physical lock sensor is FALSE
    plc.simulate_mechanism_sensor(locked=False)
    plc.simulate_mechanism_metrics(torque_nm=20.0, actuator_pos_mm=240.0, slip_back_mm=0.0)

    station = _build_test_station4(tmp_path, plc)
    plc.simulate_arrival("STATION_4", "SEAT-M601:FRONT_LH_BLACK")

    res = station.run_cycle()

    # Crucial safety rule: Vision alone CAN NEVER pass a mechanism check!
    assert res.outcome == Outcome.FAIL
    assert any("lock_sensor_confirmed" in d.defect_type for d in res.defects)
    assert plc.is_pallet_held("STATION_4") is True


def test_insufficient_torque_fails(tmp_path: Path) -> None:
    plc = PLCSimulator()
    plc.connect()
    plc.simulate_mechanism_sensor(locked=True)
    # Torque 11.5 Nm < 15.0 Nm threshold
    plc.simulate_mechanism_metrics(torque_nm=11.5, actuator_pos_mm=240.0, slip_back_mm=0.0)

    station = _build_test_station4(tmp_path, plc)
    plc.simulate_arrival("STATION_4", "SEAT-M602:FRONT_LH_BLACK")

    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert any("insufficient_torque" in d.defect_type for d in res.defects)


def test_slip_back_detected_fails(tmp_path: Path) -> None:
    plc = PLCSimulator()
    plc.connect()
    plc.simulate_mechanism_sensor(locked=True)
    # Slip-back 2.3 mm > 1.0 mm threshold
    plc.simulate_mechanism_metrics(torque_nm=20.0, actuator_pos_mm=240.0, slip_back_mm=2.3)

    station = _build_test_station4(tmp_path, plc)
    plc.simulate_arrival("STATION_4", "SEAT-M603:FRONT_LH_BLACK")

    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert any("slip_back_detected" in d.defect_type for d in res.defects)


def test_actuator_position_mismatch_fails(tmp_path: Path) -> None:
    plc = PLCSimulator()
    plc.connect()
    plc.simulate_mechanism_sensor(locked=True)
    # Actuator position 215.0mm vs nominal 240.0mm
    plc.simulate_mechanism_metrics(torque_nm=20.0, actuator_pos_mm=215.0, slip_back_mm=0.0)

    station = _build_test_station4(tmp_path, plc)
    plc.simulate_arrival("STATION_4", "SEAT-M604:FRONT_LH_BLACK")

    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert any("actuator_position_error" in d.defect_type for d in res.defects)


def test_mechanism_all_conditions_met_passes(tmp_path: Path) -> None:
    plc = PLCSimulator()
    plc.connect()
    plc.simulate_mechanism_sensor(locked=True)
    plc.simulate_mechanism_metrics(torque_nm=22.0, actuator_pos_mm=240.0, slip_back_mm=0.0)

    station = _build_test_station4(tmp_path, plc)
    plc.simulate_arrival("STATION_4", "SEAT-M605:FRONT_LH_BLACK")

    res = station.run_cycle()

    assert res.outcome == Outcome.PASS
    assert len(res.defects) == 0
    assert plc.is_pallet_held("STATION_4") is False
