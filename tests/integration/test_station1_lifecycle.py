"""Integration tests for Station 1 end-to-end lifecycle with replay camera and PLC simulator."""

from __future__ import annotations

from pathlib import Path

import pytest

from camerainspection.core.config import load_station_config
from camerainspection.core.models import Outcome
from camerainspection.hardware.camera.replay import FolderReplayCamera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.station.station_1 import Station1Service
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import DefectRecord
from camerainspection.vision.station1.fixtures_gen import generate_station1_replay_frames


@pytest.fixture
def station1_replay_dir(tmp_path: Path) -> Path:
    frames_dir = tmp_path / "station1_frames"
    generate_station1_replay_frames(frames_dir)
    return frames_dir


def _make_station(
    configs_dir: Path,
    variants_dir: Path,
    replay_dir: Path,
    db: DatabaseManager,
    plc: PLCSimulator,
) -> Station1Service:
    st_cfg = load_station_config(configs_dir / "stations" / "station_1_leather.yaml")
    cam = FolderReplayCamera(folder_path=replay_dir, loop=False)
    return Station1Service(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=cam,
        plc=plc,
        db_manager=db,
    )


def _advance(station: Station1Service, plc: PLCSimulator, n: int) -> None:
    """Burn through n replay frames to advance the camera sequence."""
    for i in range(n):
        plc.simulate_arrival("STATION_1", f"SKIP{i}_FRONT_LH_BLACK")
        station.run_cycle()


# Frame 1: clean leather → PASS
def test_station1_e2e_pass_clean_leather(
    configs_dir: Path, variants_dir: Path,
    station1_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    station = _make_station(configs_dir, variants_dir, station1_replay_dir, in_memory_db, plc_sim)
    plc_sim.simulate_arrival("STATION_1", "SEAT-101_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.PASS
    assert res.seat_id == "SEAT-101"
    assert plc_sim.is_pallet_held("STATION_1") is False


# Frame 2: scratch → FAIL (seating_face scratch > pass_max=0, < fail_at=2 so REVIEW on short scratch;
#   but the fixture scratch is ~6.4mm >> fail_at=2.0mm so FAIL)
def test_station1_e2e_fail_scratch(
    configs_dir: Path, variants_dir: Path,
    station1_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    station = _make_station(configs_dir, variants_dir, station1_replay_dir, in_memory_db, plc_sim)
    _advance(station, plc_sim, 1)  # skip frame 1 (clean)

    plc_sim.simulate_arrival("STATION_1", "SEAT-102_FRONT_LH_BLACK")
    res = station.run_cycle()

    # scratch_length_mm on seating_face: pass_max=0, fail_at=2. 80px*0.08=6.4mm → FAIL
    assert res.outcome in (Outcome.FAIL, Outcome.REVIEW)
    assert plc_sim.is_pallet_held("STATION_1") is True
    assert any("scratch" in d.defect_type.lower() for d in res.defects)


# Frame 3: cut → FAIL (cut_or_pinhole, fail_on_any)
def test_station1_e2e_fail_cut(
    configs_dir: Path, variants_dir: Path,
    station1_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    station = _make_station(configs_dir, variants_dir, station1_replay_dir, in_memory_db, plc_sim)
    _advance(station, plc_sim, 2)  # skip frames 1-2

    plc_sim.simulate_arrival("STATION_1", "SEAT-103_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_1") is True
    assert any("cut" in d.defect_type.lower() for d in res.defects)

    # Verify stored in DB
    with in_memory_db.session_scope() as session:
        rec = session.query(DefectRecord).filter(
            DefectRecord.defect_type.like("leather.cut%")
        ).first()
        assert rec is not None


# Frame 4: pinhole → FAIL (cut_or_pinhole, fail_on_any)
def test_station1_e2e_fail_pinhole(
    configs_dir: Path, variants_dir: Path,
    station1_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    station = _make_station(configs_dir, variants_dir, station1_replay_dir, in_memory_db, plc_sim)
    _advance(station, plc_sim, 3)

    plc_sim.simulate_arrival("STATION_1", "SEAT-104_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_1") is True
    assert any("pinhole" in d.defect_type.lower() for d in res.defects)


# Frame 5: stain → REVIEW / FAIL (stain_area_mm2 on seating_face: pass_max=0, fail_at=1mm²)
def test_station1_e2e_review_or_fail_stain(
    configs_dir: Path, variants_dir: Path,
    station1_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    station = _make_station(configs_dir, variants_dir, station1_replay_dir, in_memory_db, plc_sim)
    _advance(station, plc_sim, 4)

    plc_sim.simulate_arrival("STATION_1", "SEAT-105_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome in (Outcome.REVIEW, Outcome.FAIL)
    assert plc_sim.is_pallet_held("STATION_1") is True
    assert any("stain" in d.defect_type.lower() for d in res.defects)


# Repeatability: same clean image 5x → same outcome
def test_station1_repeatability(
    configs_dir: Path, variants_dir: Path,
    in_memory_db: DatabaseManager,
) -> None:
    import numpy as np
    from camerainspection.hardware.camera.base import BaseCamera
    from camerainspection.vision.station1.fixtures_gen import make_clean_leather

    frame = make_clean_leather(640, 480)

    class StaticCam(BaseCamera):
        def connect(self) -> None: pass
        def disconnect(self) -> None: pass
        def is_connected(self) -> bool: return True
        def capture(self) -> np.ndarray: return frame.copy()
        def get_metadata(self) -> dict: return {}

    st_cfg = load_station_config(configs_dir / "stations" / "station_1_leather.yaml")
    plc = PLCSimulator()
    plc.connect()

    station = Station1Service(
        station_config=st_cfg,
        variants_root=configs_dir / "variants",
        camera=StaticCam(),
        plc=plc,
        db_manager=in_memory_db,
    )

    outcomes = []
    for i in range(5):
        plc.simulate_arrival("STATION_1", f"SEAT-REP-{i}_FRONT_LH_BLACK")
        res = station.run_cycle()
        outcomes.append(res.outcome)

    assert len(set(outcomes)) == 1, f"Non-deterministic outcomes: {set(outcomes)}"
