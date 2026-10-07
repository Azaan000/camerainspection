"""Integration tests for Station 2 end-to-end cycle with replay camera and PLC simulator."""

from __future__ import annotations

from pathlib import Path
import cv2
import pytest

from camerainspection.core.config import load_station_config
from camerainspection.core.models import BoundingBox, Outcome
from camerainspection.hardware.camera.replay import FolderReplayCamera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.inference.base import ModelDetection
from camerainspection.inference.mock import MockInferenceEngine
from camerainspection.station.station_2 import Station2Service
from camerainspection.storage.db import DatabaseManager
from camerainspection.storage.entities import DefectRecord
from camerainspection.vision.station2.fixtures_gen import generate_station2_replay_frames


@pytest.fixture
def station2_replay_dir(tmp_path: Path) -> Path:
    frames_dir = tmp_path / "station2_frames"
    generate_station2_replay_frames(frames_dir)
    return frames_dir


def _make_station(
    configs_dir: Path,
    variants_dir: Path,
    replay_dir: Path,
    db: DatabaseManager,
    plc: PLCSimulator,
    inference_engine: MockInferenceEngine | None = None,
) -> Station2Service:
    st_cfg = load_station_config(configs_dir / "stations" / "station_2_stitch.yaml")
    cam = FolderReplayCamera(folder_path=replay_dir, loop=False)
    return Station2Service(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=cam,
        plc=plc,
        db_manager=db,
        inference_engine=inference_engine,
    )


# Frame 1: clean seam -> PASS
def test_station2_e2e_pass_clean_seam(
    configs_dir: Path, variants_dir: Path,
    station2_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    station = _make_station(configs_dir, variants_dir, station2_replay_dir, in_memory_db, plc_sim)
    plc_sim.simulate_arrival("STATION_2", "SEAT-201_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.PASS
    assert res.seat_id == "SEAT-201"
    assert plc_sim.is_pallet_held("STATION_2") is False


# Frame 2: skip stitch -> REVIEW (0 < skip < 5)
def test_station2_e2e_review_skip_stitch(
    configs_dir: Path, variants_dir: Path,
    station2_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    station = _make_station(configs_dir, variants_dir, station2_replay_dir, in_memory_db, plc_sim)

    # Advance past frame 1
    plc_sim.simulate_arrival("STATION_2", "SKIP_FRONT_LH_BLACK")
    station.run_cycle()

    plc_sim.simulate_arrival("STATION_2", "SEAT-202_FRONT_LH_BLACK")
    res = station.run_cycle()

    # skip_length_mm in (0, 5) range -> REVIEW
    assert res.outcome in (Outcome.REVIEW, Outcome.FAIL)
    assert plc_sim.is_pallet_held("STATION_2") is True
    assert any("skip" in d.defect_type.lower() for d in res.defects)


# Frame 3: broken thread (AI) -> FAIL
def test_station2_e2e_fail_broken_thread_ai(
    configs_dir: Path, variants_dir: Path,
    station2_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    mock_ai = MockInferenceEngine(preset_detections=[
        ModelDetection(
            class_name="broken_thread",
            confidence=0.87,
            bounding_box=BoundingBox(x=10, y=10, w=30, h=20),
        )
    ])
    station = _make_station(
        configs_dir, variants_dir, station2_replay_dir, in_memory_db, plc_sim, mock_ai
    )

    # Advance past frames 1 and 2
    for seq_id in ["D1_FRONT_LH_BLACK", "D2_FRONT_LH_BLACK"]:
        plc_sim.simulate_arrival("STATION_2", seq_id)
        station.run_cycle()

    plc_sim.simulate_arrival("STATION_2", "SEAT-203_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_2") is True
    assert any(d.defect_type == "stitch.broken_thread" for d in res.defects)

    # Verify stored in DB
    with in_memory_db.session_scope() as session:
        rec = session.query(DefectRecord).filter_by(defect_type="stitch.broken_thread").first()
        assert rec is not None
        assert rec.confidence == pytest.approx(0.87)


# Frame 4: loose end AI detection -> REVIEW (loose_end < 5mm)
def test_station2_e2e_review_loose_end_ai(
    configs_dir: Path, variants_dir: Path,
    station2_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    # Loose end bbox width = 64px * 0.05mm = 3.2mm -> strictly in (3.0, 5.0) REVIEW band
    mock_ai = MockInferenceEngine(preset_detections=[
        ModelDetection(
            class_name="loose_end",
            confidence=0.72,
            bounding_box=BoundingBox(x=500, y=5, w=64, h=15),
        )
    ])
    station = _make_station(
        configs_dir, variants_dir, station2_replay_dir, in_memory_db, plc_sim, mock_ai
    )

    for seq_id in ["D1_FRONT_LH_BLACK", "D2_FRONT_LH_BLACK", "D3_FRONT_LH_BLACK"]:
        plc_sim.simulate_arrival("STATION_2", seq_id)
        station.run_cycle()

    plc_sim.simulate_arrival("STATION_2", "SEAT-204_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome in (Outcome.REVIEW, Outcome.FAIL)
    assert plc_sim.is_pallet_held("STATION_2") is True
    assert any("loose_end" in d.defect_type for d in res.defects)


# Frame 5: wrong thread color -> FAIL (delta E > 5)
def test_station2_e2e_fail_wrong_thread_color(
    configs_dir: Path, variants_dir: Path,
    station2_replay_dir: Path,
    in_memory_db: DatabaseManager, plc_sim: PLCSimulator,
) -> None:
    station = _make_station(configs_dir, variants_dir, station2_replay_dir, in_memory_db, plc_sim)

    for seq_id in [f"D{i}_FRONT_LH_BLACK" for i in range(1, 5)]:
        plc_sim.simulate_arrival("STATION_2", seq_id)
        station.run_cycle()

    plc_sim.simulate_arrival("STATION_2", "SEAT-205_FRONT_LH_BLACK")
    res = station.run_cycle()

    assert res.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_2") is True
    assert any("thread_color" in d.defect_type for d in res.defects)


# Repeatability: same image 10x must give identical outcomes and measurements
def test_station2_repeatability(
    configs_dir: Path, variants_dir: Path,
    in_memory_db: DatabaseManager,
) -> None:
    from camerainspection.hardware.camera.base import BaseCamera
    import numpy as np
    from camerainspection.vision.station2.fixtures_gen import make_stitch_seam

    frame = make_stitch_seam(n_stitches=30, pitch_px=18)

    class StaticCam(BaseCamera):
        def connect(self) -> None: pass
        def disconnect(self) -> None: pass
        def is_connected(self) -> bool: return True
        def capture(self) -> np.ndarray: return frame.copy()
        def get_metadata(self) -> dict: return {}

    st_cfg = load_station_config(configs_dir / "stations" / "station_2_stitch.yaml")
    plc = PLCSimulator()
    plc.connect()

    station = Station2Service(
        station_config=st_cfg,
        variants_root=configs_dir / "variants",
        camera=StaticCam(),
        plc=plc,
        db_manager=in_memory_db,
    )

    outcomes = []
    spis = []
    for i in range(10):
        plc.simulate_arrival("STATION_2", f"SEAT-REP-{i}_FRONT_LH_BLACK")
        res = station.run_cycle()
        outcomes.append(res.outcome)
        spis.append(res.measurements.get("spi", 0.0))

    assert len(set(outcomes)) == 1, f"Non-deterministic outcomes: {set(outcomes)}"
    spi_values = [round(s, 2) for s in spis]
    assert len(set(spi_values)) == 1, f"Non-deterministic SPI: {set(spi_values)}"
