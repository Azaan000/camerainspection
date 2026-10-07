"""Integration tests for BaseStation lifecycle and fail-safe behaviors."""

from pathlib import Path
from typing import Any
import numpy as np
import pytest

from camerainspection.core.config import load_station_config
from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.models import DefectDetail, Outcome
from camerainspection.hardware.camera.synthetic import SyntheticCamera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.station.base_station import BaseStation
from camerainspection.storage.db import DatabaseManager


class ConcreteTestStation(BaseStation):
    """Test station implementation for lifecycle verification."""

    def __init__(self, *args: Any, should_detect_defect: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.should_detect_defect = should_detect_defect

    def inspect_image(
        self,
        image: np.ndarray,
        variant_id: str,
        evaluator: LimitsEvaluator,
        variant_nominals: dict[str, Any],
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        if self.should_detect_defect:
            # Simulate a broken thread failure
            defect = evaluator.evaluate_check("stitch", "broken_thread", True)
            return [defect], {"defects_found": 1.0}, image
        else:
            # Clean pass
            check = evaluator.evaluate_check("stitch", "broken_thread", False)
            return [check], {"defects_found": 0.0}, image


def test_station_cycle_pass(
    configs_dir: Path,
    variants_dir: Path,
    in_memory_db: DatabaseManager,
    plc_sim: PLCSimulator,
    synthetic_camera: SyntheticCamera,
) -> None:
    st_cfg = load_station_config(configs_dir / "stations" / "station_2_stitch.yaml")
    station = ConcreteTestStation(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=synthetic_camera,
        plc=plc_sim,
        db_manager=in_memory_db,
        should_detect_defect=False,
    )

    # Simulate pallet arrival
    plc_sim.simulate_arrival("STATION_2", "SEAT-101_FRONT_LH_BLACK")

    result = station.run_cycle()
    assert result.outcome == Outcome.PASS
    assert result.seat_id == "SEAT-101"
    assert result.variant_id == "FRONT_LH_BLACK"
    assert plc_sim.is_pallet_held("STATION_2") is False


def test_station_cycle_fail_holds_pallet(
    configs_dir: Path,
    variants_dir: Path,
    in_memory_db: DatabaseManager,
    plc_sim: PLCSimulator,
    synthetic_camera: SyntheticCamera,
) -> None:
    st_cfg = load_station_config(configs_dir / "stations" / "station_2_stitch.yaml")
    station = ConcreteTestStation(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=synthetic_camera,
        plc=plc_sim,
        db_manager=in_memory_db,
        should_detect_defect=True,
    )

    plc_sim.simulate_arrival("STATION_2", "SEAT-102_FRONT_LH_BLACK")

    result = station.run_cycle()
    assert result.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_2") is True


def test_station_fail_safe_on_trigger_timeout(
    configs_dir: Path,
    variants_dir: Path,
    in_memory_db: DatabaseManager,
    plc_sim: PLCSimulator,
    synthetic_camera: SyntheticCamera,
) -> None:
    st_cfg = load_station_config(configs_dir / "stations" / "station_2_stitch.yaml")
    st_cfg.trigger.timeout_s = 0.05  # Short timeout for test
    station = ConcreteTestStation(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=synthetic_camera,
        plc=plc_sim,
        db_manager=in_memory_db,
    )

    # Do NOT simulate arrival -> trigger times out
    result = station.run_cycle()
    assert result.outcome == Outcome.FAIL
    assert "PLCTriggerTimeoutError" in result.defects[0].description
    assert plc_sim.is_pallet_held("STATION_2") is True


def test_station_fail_safe_on_unknown_variant(
    configs_dir: Path,
    variants_dir: Path,
    in_memory_db: DatabaseManager,
    plc_sim: PLCSimulator,
    synthetic_camera: SyntheticCamera,
) -> None:
    st_cfg = load_station_config(configs_dir / "stations" / "station_2_stitch.yaml")
    station = ConcreteTestStation(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=synthetic_camera,
        plc=plc_sim,
        db_manager=in_memory_db,
    )

    plc_sim.simulate_arrival("STATION_2", "SEAT-103_NON_EXISTENT_TRIM")
    result = station.run_cycle()
    assert result.outcome == Outcome.FAIL
    assert "UnknownVariantError" in result.defects[0].description
    assert plc_sim.is_pallet_held("STATION_2") is True


def test_shadow_mode_does_not_hold_pallet(
    configs_dir: Path,
    variants_dir: Path,
    in_memory_db: DatabaseManager,
    plc_sim: PLCSimulator,
    synthetic_camera: SyntheticCamera,
) -> None:
    st_cfg = load_station_config(configs_dir / "stations" / "station_2_stitch.yaml")
    station = ConcreteTestStation(
        station_config=st_cfg,
        variants_root=variants_dir,
        camera=synthetic_camera,
        plc=plc_sim,
        db_manager=in_memory_db,
        should_detect_defect=True,
        shadow_mode=True,  # Shadow mode active!
    )

    plc_sim.simulate_arrival("STATION_2", "SEAT-104_FRONT_LH_BLACK")
    # Pre-release pallet on PLC
    plc_sim.hold_pallet("STATION_2", hold=False)

    result = station.run_cycle()
    # Even though result is FAIL, shadow mode did NOT control PLC
    assert result.outcome == Outcome.FAIL
    assert plc_sim.is_pallet_held("STATION_2") is False
