"""End-to-end integration tests for Station 3 using FolderReplayCamera and PLCSimulator."""

from pathlib import Path

import cv2
import pytest

from camerainspection.core.config import load_station_config
from camerainspection.core.models import BoundingBox, Outcome
from camerainspection.hardware.camera.replay import FolderReplayCamera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.inference.base import ModelDetection
from camerainspection.inference.mock import MockInferenceEngine
from camerainspection.station.station_3 import Station3Service
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import DefectRecord
from camerainspection.vision.station3.fixtures_gen import generate_station3_test_scene


@pytest.fixture
def station3_replay_dir(tmp_path: Path, variants_dir: Path) -> Path:
    """Create directory containing test scenarios for replay camera."""
    dir_path = tmp_path / "station3_frames"
    dir_path.mkdir()

    # 1. Good normal seat
    f1 = generate_station3_test_scene(variants_dir, variant_id="FRONT_LH_BLACK")
    cv2.imwrite(str(dir_path / "01_pass_normal.png"), f1)

    # 2. Missing side shield
    f2 = generate_station3_test_scene(variants_dir, variant_id="FRONT_LH_BLACK", missing_shield=True)
    cv2.imwrite(str(dir_path / "02_fail_missing_shield.png"), f2)

    # 3. Wrong hand (RH shield on LH seat)
    f3 = generate_station3_test_scene(variants_dir, variant_id="FRONT_LH_BLACK", wrong_hand_shield=True)
    cv2.imwrite(str(dir_path / "03_fail_wrong_hand.png"), f3)

    # 4. Discolored plastic
    f4 = generate_station3_test_scene(variants_dir, variant_id="FRONT_LH_BLACK", discolored_shield=True)
    cv2.imwrite(str(dir_path / "04_fail_discolored.png"), f4)

    return dir_path


def test_station3_e2e_pass_cycle(
    configs_dir: Path,
    variants_dir: Path,
    station3_replay_dir: Path,
    in_memory_db: DatabaseManager,
    plc_sim: PLCSimulator,
) -> None:
    st_cfg = load_station_config(configs_dir / "stations" / "station_3_plastic.yaml")
    cam = FolderReplayCamera(folder_path=station3_replay_dir, loop=False)

    station = Station3Service(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=cam,
        plc=plc_sim,
        db_manager=in_memory_db,
    )

    # Test Frame 1: Normal PASS
    plc_sim.simulate_arrival("STATION_3", "SEAT-301_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.PASS
    assert res.seat_id == "SEAT-301"
    assert plc_sim.is_pallet_held("STATION_3") is False


def test_station3_e2e_missing_component(
    configs_dir: Path,
    variants_dir: Path,
    station3_replay_dir: Path,
    in_memory_db: DatabaseManager,
    plc_sim: PLCSimulator,
) -> None:
    st_cfg = load_station_config(configs_dir / "stations" / "station_3_plastic.yaml")
    cam = FolderReplayCamera(folder_path=station3_replay_dir, loop=False)

    station = Station3Service(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=cam,
        plc=plc_sim,
        db_manager=in_memory_db,
    )

    # Advance past frame 1
    plc_sim.simulate_arrival("STATION_3", "SEAT-DUMMY_FRONT_LH_BLACK")
    _ = station.run_cycle()

    # Test Frame 2: Missing component
    plc_sim.simulate_arrival("STATION_3", "SEAT-302_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_3") is True
    assert any("MISSING COMPONENT" in d.description for d in res.defects)


def test_station3_e2e_wrong_hand_detection(
    configs_dir: Path,
    variants_dir: Path,
    station3_replay_dir: Path,
    in_memory_db: DatabaseManager,
    plc_sim: PLCSimulator,
) -> None:
    st_cfg = load_station_config(configs_dir / "stations" / "station_3_plastic.yaml")
    cam = FolderReplayCamera(folder_path=station3_replay_dir, loop=False)

    station = Station3Service(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=cam,
        plc=plc_sim,
        db_manager=in_memory_db,
    )

    # Advance past frames 1 and 2
    plc_sim.simulate_arrival("STATION_3", "D1_FRONT_LH_BLACK")
    _ = station.run_cycle()
    plc_sim.simulate_arrival("STATION_3", "D2_FRONT_LH_BLACK")
    _ = station.run_cycle()

    # Test Frame 3: Wrong Hand (RH shield on LH seat)
    plc_sim.simulate_arrival("STATION_3", "SEAT-303_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_3") is True
    assert any("WRONG HAND ASSEMBLED" in d.description for d in res.defects)


def test_station3_ai_crack_detection(
    configs_dir: Path,
    variants_dir: Path,
    station3_replay_dir: Path,
    in_memory_db: DatabaseManager,
    plc_sim: PLCSimulator,
) -> None:
    st_cfg = load_station_config(configs_dir / "stations" / "station_3_plastic.yaml")
    cam = FolderReplayCamera(folder_path=station3_replay_dir, loop=True)

    # Mock inference engine injecting AI crack detection
    crack_det = ModelDetection(
        class_name="crack",
        confidence=0.91,
        bounding_box=BoundingBox(x=1520, y=550, w=40, h=60),
    )
    mock_ai = MockInferenceEngine(preset_detections=[crack_det])

    station = Station3Service(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=cam,
        plc=plc_sim,
        db_manager=in_memory_db,
        inference_engine=mock_ai,
    )

    plc_sim.simulate_arrival("STATION_3", "SEAT-305_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_3") is True

    # Verify defect recorded in DB
    with in_memory_db.session_scope() as session:
        def_rec = (
            session.query(DefectRecord)
            .filter_by(defect_type="plastic.crack")
            .first()
        )
        assert def_rec is not None
        assert def_rec.confidence == 0.91
        assert def_rec.bbox_x == 1520
