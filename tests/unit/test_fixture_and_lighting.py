"""Unit tests for Phase 3 fixture control and Phase 4 lighting controller."""

from pathlib import Path

from camerainspection.core.config import CameraConfig, StationConfig
from camerainspection.core.models import Outcome
from camerainspection.hardware.camera.synthetic import SyntheticCamera
from camerainspection.hardware.fixture.plc_fixture import PLCFixture
from camerainspection.hardware.fixture.simulator import SimulatedFixture
from camerainspection.hardware.lighting.simulator import SimulatedLightController
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.station.base_station import BaseStation
from camerainspection.storage.db import DatabaseManager


class FixtureTestStation(BaseStation):
    def inspect_image(self, image, variant_id, evaluator, variant_nominals):
        return [], {"dummy": 1.0}, image

    def get_required_measurements(self):
        return ["dummy"]


def test_simulated_fixture_movement() -> None:
    fix = SimulatedFixture(auto_in_position=True)
    fix.clamp()
    assert fix.is_clamped() is True

    fix.move_to("left")
    assert fix.is_in_position() is True

    fix.move_arm_to("bolster_seam_pose")
    assert fix.is_in_position() is True

    fix.release()
    assert fix.is_clamped() is False


def test_plc_fixture_commands() -> None:
    plc = PLCSimulator()
    plc.connect()
    fix = PLCFixture(plc=plc)

    fix.clamp()
    assert plc.read_tag("FIXTURE_CLAMP_CMD") is True
    assert fix.is_clamped() is True

    fix.move_to("rear")
    assert plc.read_tag("FIXTURE_TARGET_POSITION") == "rear"

    fix.move_arm_to("pose_1")
    assert plc.read_tag("ARM_TARGET_POSE") == "pose_1"


def test_station_fails_closed_when_fixture_clamp_unconfirmed(tmp_path: Path) -> None:
    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()
    plc = PLCSimulator()
    plc.connect()

    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text("variant_id: FRONT_LH_BLACK\n")

    cfg = StationConfig(
        station_id="ST_FIX_FAIL",
        name="Fixture Fail Station",
        camera=CameraConfig(adapter="synthetic"),
    )

    # Fixture configured with clamp fault
    faulty_fixture = SimulatedFixture(simulate_clamp_success=False)

    station = FixtureTestStation(
        station_config=cfg,
        variants_root=variants_root,
        camera=SyntheticCamera(),
        plc=plc,
        db_manager=db,
        fixture=faulty_fixture,
    )

    plc.simulate_arrival("ST_FIX_FAIL", "SEAT-FIX:FRONT_LH_BLACK")
    res = station.run_cycle()

    # Safety rule: unconfirmed clamp must fail closed
    assert res.outcome == Outcome.FAIL
    assert any("Fixture clamp confirmation sensor failed" in d.description for d in res.defects)


def test_station_fails_closed_when_fixture_not_in_position(tmp_path: Path) -> None:
    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()
    plc = PLCSimulator()
    plc.connect()

    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text("variant_id: FRONT_LH_BLACK\n")

    cfg = StationConfig(
        station_id="ST_POS_FAIL",
        name="Position Fail Station",
        trigger={"timeout_s": 0.1},
        cameras=[CameraConfig(name="main", view="main", adapter="synthetic")],
        capture_sequence=[{"position": "left", "camera": "main"}],
    )

    # Fixture never reaches in-position
    stuck_fixture = SimulatedFixture(auto_in_position=False)

    station = FixtureTestStation(
        station_config=cfg,
        variants_root=variants_root,
        camera=SyntheticCamera(),
        plc=plc,
        db_manager=db,
        fixture=stuck_fixture,
    )

    plc.simulate_arrival("ST_POS_FAIL", "SEAT-POS:FRONT_LH_BLACK")
    res = station.run_cycle()

    # Safety rule: no acquisition if fixture not in position
    assert res.outcome == Outcome.FAIL
    assert any("Fixture not in position" in d.description for d in res.defects)


def test_simulated_lighting_verification() -> None:
    light = SimulatedLightController()
    verified = light.apply_and_verify("dome", 80.0, tolerance_pct=2.0)
    assert verified is True
    assert light.read_back("dome") == 80.0


def test_station_fails_closed_when_lighting_readback_fails(tmp_path: Path) -> None:
    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()
    plc = PLCSimulator()
    plc.connect()

    variants_root = tmp_path / "variants"
    var_dir = variants_root / "FRONT_LH_BLACK"
    var_dir.mkdir(parents=True)
    (var_dir / "config.yaml").write_text("variant_id: FRONT_LH_BLACK\n")

    cfg = StationConfig(
        station_id="ST_LIGHT_FAIL",
        name="Lighting Fail Station",
        lighting={"dome_intensity_pct": 80},
        camera=CameraConfig(adapter="synthetic"),
    )

    # Lighting controller with hardware fault
    faulty_light = SimulatedLightController(simulate_hardware_fault=True)

    station = FixtureTestStation(
        station_config=cfg,
        variants_root=variants_root,
        camera=SyntheticCamera(),
        plc=plc,
        db_manager=db,
        lighting_controller=faulty_light,
    )

    plc.simulate_arrival("ST_LIGHT_FAIL", "SEAT-LIGHT:FRONT_LH_BLACK")
    res = station.run_cycle()

    # Safety rule: lighting verification failure fails safe
    assert res.outcome == Outcome.FAIL
    assert any("Light channel 'dome' failed read-back verification" in d.description for d in res.defects)
