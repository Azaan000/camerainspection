"""End-to-end integration tests for Station 4: complete seat, mechanism, and sensor interlock."""

from __future__ import annotations

from pathlib import Path
import pytest

from camerainspection.core.config import load_station_config
from camerainspection.core.models import BoundingBox, Outcome
from camerainspection.hardware.camera.replay import FolderReplayCamera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.inference.base import ModelDetection
from camerainspection.inference.mock import MockInferenceEngine
from camerainspection.station.station_4 import Station4Service
from camerainspection.storage.db import DatabaseManager
from camerainspection.vision.station4.fixtures_gen import generate_station4_replay_frames


@pytest.fixture
def station4_replay_dir(tmp_path: Path) -> Path:
    frames_dir = tmp_path / "station4_frames"
    generate_station4_replay_frames(frames_dir)
    return frames_dir


def _make_station(
    configs_dir: Path,
    variants_dir: Path,
    replay_dir: Path,
    db: DatabaseManager,
    plc: PLCSimulator,
    inference_engine: MockInferenceEngine | None = None,
) -> Station4Service:
    st_cfg = load_station_config(configs_dir / "stations" / "station_4_complete.yaml")
    cam = FolderReplayCamera(folder_path=replay_dir, loop=False)
    return Station4Service(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=cam,
        plc=plc,
        db_manager=db,
        inference_engine=inference_engine,
    )


# Test 1: Full Nominal PASS (optical nominal + sensor locked)
def test_station4_e2e_pass_cycle(
    configs_dir: Path, variants_dir: Path,
    station4_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    # Assert lock confirmation sensor from PLC
    plc_sim.simulate_mechanism_sensor(locked=True)

    station = _make_station(configs_dir, variants_dir, station4_replay_dir, in_memory_db, plc_sim)
    plc_sim.simulate_arrival("STATION_4", "SEAT-401_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.PASS
    assert res.seat_id == "SEAT-401"
    assert plc_sim.is_pallet_held("STATION_4") is False
    assert res.measurements["lock_sensor_confirmed"] == 1.0


# Test 2: CRITICAL SAFETY RULE — Missing hardware lock sensor confirmation fails safe
# "take the lock confirmation from a sensor signal, never from the image"
def test_station4_fail_safe_on_unlocked_sensor(
    configs_dir: Path, variants_dir: Path,
    station4_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    # Sensor NOT confirmed (unlocked)
    plc_sim.simulate_mechanism_sensor(locked=False)

    station = _make_station(configs_dir, variants_dir, station4_replay_dir, in_memory_db, plc_sim)
    plc_sim.simulate_arrival("STATION_4", "SEAT-402_FRONT_LH_BLACK")
    res = station.run_cycle()

    # Must FAIL and pallet must be held
    assert res.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_4") is True
    assert any("lock_sensor_confirmed" in d.defect_type for d in res.defects)


# Test 3: Optical Recliner Angle failure
def test_station4_fail_on_recliner_angle(
    configs_dir: Path, variants_dir: Path,
    station4_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    station = _make_station(configs_dir, variants_dir, station4_replay_dir, in_memory_db, plc_sim)

    # Advance past frame 1
    plc_sim.simulate_arrival("STATION_4", "SKIP1_FRONT_LH_BLACK")
    station.run_cycle()

    # Frame 2 has 93.0 deg (+2.8 deg dev > fail_tol=2.0)
    plc_sim.simulate_arrival("STATION_4", "SEAT-403_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome in (Outcome.FAIL, Outcome.REVIEW)
    assert plc_sim.is_pallet_held("STATION_4") is True
    assert any("recliner_angle" in d.defect_type for d in res.defects)


# Test 4: Optical Track Position failure
def test_station4_fail_on_track_position(
    configs_dir: Path, variants_dir: Path,
    station4_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    station = _make_station(configs_dir, variants_dir, station4_replay_dir, in_memory_db, plc_sim)

    # Advance past frames 1 and 2
    for s in ["SKIP1_FRONT_LH_BLACK", "SKIP2_FRONT_LH_BLACK"]:
        plc_sim.simulate_arrival("STATION_4", s)
        station.run_cycle()

    # Frame 3 has 236.0 mm (-4.0 mm dev > fail_tol=2.0)
    plc_sim.simulate_arrival("STATION_4", "SEAT-404_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_4") is True
    assert any("track_end_position" in d.defect_type for d in res.defects)


# Test 5: Cosmetic Wrinkle / Puckering -> REVIEW
def test_station4_cosmetic_wrinkle_review(
    configs_dir: Path, variants_dir: Path,
    station4_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    mock_ai = MockInferenceEngine(preset_detections=[
        ModelDetection(
            class_name="wrinkle",
            confidence=0.78,
            bounding_box=BoundingBox(x=500, y=500, w=150, h=80),
        )
    ])
    station = _make_station(
        configs_dir, variants_dir, station4_replay_dir, in_memory_db, plc_sim, mock_ai
    )

    plc_sim.simulate_arrival("STATION_4", "SEAT-405_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.REVIEW
    assert plc_sim.is_pallet_held("STATION_4") is True
    assert any("wrinkle" in d.defect_type for d in res.defects)


# Test 6: Missing Critical Component -> FAIL
def test_station4_missing_component_fail(
    configs_dir: Path, variants_dir: Path,
    station4_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    plc_sim.simulate_mechanism_sensor(locked=True)
    mock_ai = MockInferenceEngine(preset_detections=[
        ModelDetection(
            class_name="missing_airbag",
            confidence=0.92,
            bounding_box=BoundingBox(x=700, y=700, w=100, h=100),
        )
    ])
    station = _make_station(
        configs_dir, variants_dir, station4_replay_dir, in_memory_db, plc_sim, mock_ai
    )

    plc_sim.simulate_arrival("STATION_4", "SEAT-406_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_4") is True
    assert any("missing_airbag" in d.defect_type for d in res.defects)
