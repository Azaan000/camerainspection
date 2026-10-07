"""Repeatability test verifying deterministic consistency across repeated cycles."""

from pathlib import Path
import numpy as np

from camerainspection.core.config import load_station_config
from camerainspection.hardware.camera.base import BaseCamera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.station.station_3 import Station3Service
from camerainspection.storage.db import DatabaseManager
from camerainspection.vision.station3.fixtures_gen import generate_station3_test_scene


class StaticFrameCamera(BaseCamera):
    """Feeds the exact same static frame repeatedly for repeatability benchmarking."""

    def __init__(self, frame: np.ndarray) -> None:
        self.frame = frame
        self._connected = True

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def capture(self) -> np.ndarray:
        return self.frame.copy()

    def get_metadata(self) -> dict:
        return {"adapter": "StaticFrameCamera"}


def test_station3_repeatability_10_runs(
    configs_dir: Path,
    variants_dir: Path,
    in_memory_db: DatabaseManager,
) -> None:
    st_cfg = load_station_config(configs_dir / "stations" / "station_3_plastic.yaml")
    plc = PLCSimulator()
    plc.connect()

    # Generate fixed standard scene
    scene = generate_station3_test_scene(
        variants_root=variants_dir,
        variant_id="FRONT_LH_BLACK",
        shield_gap_offset_px=25,
        add_flash_px=0,
    )

    cam = StaticFrameCamera(scene)
    station = Station3Service(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=cam,
        plc=plc,
        db_manager=in_memory_db,
    )

    outcomes = []
    gap_measurements = []
    flash_measurements = []

    # Run 10 consecutive cycles
    for cycle in range(10):
        plc.simulate_arrival("STATION_3", f"SEAT-REP-{cycle}_FRONT_LH_BLACK")
        result = station.run_cycle()
        outcomes.append(result.outcome)
        gap_measurements.append(result.measurements.get("shield_gap_mm"))
        flash_measurements.append(result.measurements.get("flash_mm"))

    # Assert 100% identical outcomes
    assert len(set(outcomes)) == 1, f"Outcomes varied across runs: {outcomes}"

    # Assert 100% identical measurements
    assert len(set(gap_measurements)) == 1, f"Gap varied across runs: {gap_measurements}"
    assert len(set(flash_measurements)) == 1, f"Flash varied across runs: {flash_measurements}"
