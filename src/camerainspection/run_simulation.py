"""Interactive line simulation runner: runs simulated seats through Stations 1 to 4."""

from __future__ import annotations

import argparse
from pathlib import Path
import time
import cv2
import numpy as np

from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.config import load_station_config, load_system_config
from camerainspection.core.models import Outcome
from camerainspection.hardware.camera.factory import build_camera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.station.station_1 import Station1Service
from camerainspection.station.station_2 import Station2Service
from camerainspection.station.station_3 import Station3Service
from camerainspection.station.station_4 import Station4Service
from camerainspection.storage.db import DatabaseManager

# Fixture generators
from camerainspection.vision.station1.fixtures_gen import generate_station1_replay_frames
from camerainspection.vision.station2.fixtures_gen import generate_station2_replay_frames
from camerainspection.vision.station3.fixtures_gen import generate_station3_test_scene
from camerainspection.vision.station4.fixtures_gen import generate_station4_replay_frames


def setup_simulation_data(data_root: Path, variants_dir: Path) -> None:
    """Prepare simulated replay frames for each station and individual camera view."""
    # Root folders for legacy single camera
    generate_station1_replay_frames(data_root / "station_1" / "replay")
    generate_station2_replay_frames(data_root / "station_2" / "replay")
    s3_dir = data_root / "station_3" / "replay"
    s3_dir.mkdir(parents=True, exist_ok=True)
    f_pass = generate_station3_test_scene(variants_dir, variant_id="FRONT_LH_BLACK")
    cv2.imwrite(str(s3_dir / "01_pass_scene.png"), f_pass)
    generate_station4_replay_frames(data_root / "station_4" / "replay")

    # Multi-camera sub-folders
    generate_station1_replay_frames(data_root / "station_1" / "replay" / "front_cushion_backrest")
    generate_station1_replay_frames(data_root / "station_1" / "replay" / "rear_back_map_pocket")

    generate_station2_replay_frames(data_root / "station_2" / "replay" / "left_bolster")
    generate_station2_replay_frames(data_root / "station_2" / "replay" / "right_bolster")
    generate_station2_replay_frames(data_root / "station_2" / "replay" / "headrest")
    generate_station2_replay_frames(data_root / "station_2" / "replay" / "seam_arm")

    s3_side = data_root / "station_3" / "replay" / "side_shield_handle_lever"
    s3_side.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(s3_side / "01_pass_scene.png"), f_pass)

    s3_under = data_root / "station_3" / "replay" / "underside"
    s3_under.mkdir(parents=True, exist_ok=True)
    under_img = np.full((1944, 2592, 3), 40, dtype=np.uint8)
    cv2.imwrite(str(s3_under / "01_pass_underside.png"), under_img)

    generate_station4_replay_frames(data_root / "station_4" / "replay" / "recliner_track")


def run_line_simulation(seats_to_run: int = 5, camera_adapter: str | None = None) -> None:
    print("\n--- INITIALIZING CAR SEAT INSPECTION LINE SIMULATION ---")
    data_root = Path("data")
    variants_dir = Path("configs/variants")
    setup_simulation_data(data_root, variants_dir)

    sys_cfg = load_system_config(Path("configs/system.yaml"))
    db = DatabaseManager(sys_cfg.database.url)
    db.init_tables()

    plc = PLCSimulator()
    plc.connect()
    plc.simulate_mechanism_sensor(locked=True)

    coordinator = InspectionCoordinator(
        plc=plc,
        db_manager=db,
        expected_stations=sys_cfg.coordinator.expected_stations,
        shadow_mode=sys_cfg.shadow_mode,
        cycle_timeout_s=sys_cfg.coordinator.cycle_timeout_s,
    )

    st1_cfg = load_station_config(Path("configs/stations/station_1_leather.yaml"))
    st2_cfg = load_station_config(Path("configs/stations/station_2_stitch.yaml"))
    st3_cfg = load_station_config(Path("configs/stations/station_3_plastic.yaml"))
    st4_cfg = load_station_config(Path("configs/stations/station_4_complete.yaml"))

    # Helper to construct station cameras with optional CLI override
    def make_station_cameras(cfg: Any) -> dict[str, Any] | None:
        if camera_adapter:
            return {cam.name: build_camera(cam, adapter_override=camera_adapter) for cam in cfg.cameras}
        return None

    st1 = Station1Service(
        station_config=st1_cfg,
        variants_root=variants_dir,
        cameras=make_station_cameras(st1_cfg),
        plc=plc,
        db_manager=db,
        config_version=sys_cfg.config_version,
    )
    st2 = Station2Service(
        station_config=st2_cfg,
        variants_root=variants_dir,
        cameras=make_station_cameras(st2_cfg),
        plc=plc,
        db_manager=db,
        config_version=sys_cfg.config_version,
    )
    st3 = Station3Service(
        station_config=st3_cfg,
        variants_root=variants_dir,
        cameras=make_station_cameras(st3_cfg),
        plc=plc,
        db_manager=db,
        config_version=sys_cfg.config_version,
    )
    st4 = Station4Service(
        station_config=st4_cfg,
        variants_root=variants_dir,
        cameras=make_station_cameras(st4_cfg),
        plc=plc,
        db_manager=db,
        config_version=sys_cfg.config_version,
    )

    stations = [("STATION_1", st1), ("STATION_2", st2), ("STATION_3", st3), ("STATION_4", st4)]

    print(f"Line active. Running {seats_to_run} seats through all 4 stations...\n")

    for i in range(1, seats_to_run + 1):
        seat_id = f"SEAT-{1000 + i}"
        barcode = f"{seat_id}_FRONT_LH_BLACK"
        print("--------------------------------------------------")
        print(f"[*] Pallet Arrived: {seat_id} (Variant: FRONT_LH_BLACK)")

        for st_name, st_service in stations:
            plc.simulate_arrival(st_name, barcode)
            res = st_service.run_cycle()
            overall = coordinator.register_station_result(res)
            print(
                f"    - {st_name:10s} -> {res.outcome.value:6s} "
                f"(Cameras: {len(res.camera_results)}, Cycle: {res.cycle_time_ms:.1f}ms, Defects: {len(res.defects)})"
            )

        if overall:
            print(f"[*] FINAL DECISION for {seat_id}: {overall.outcome.value}")
            print(f"    -> OEM Label Printer Enabled: {overall.label_printer_enabled}")
            print(f"    -> Mechanism Lock Confirmed:  {overall.lock_sensor_confirmed}")
        print()

    print("--- SIMULATION BATCH COMPLETE ---")
    print("Database populated! Launch the server to view dashboard stats.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Car seat inspection line simulation runner")
    parser.add_argument("--seats", type=int, default=5, help="Number of seats to simulate")
    parser.add_argument(
        "--camera-adapter",
        default=None,
        help="Override camera adapter (replay, synthetic, webcam, basler, hikrobot)",
    )
    args = parser.parse_args()
    run_line_simulation(seats_to_run=args.seats, camera_adapter=args.camera_adapter)


if __name__ == "__main__":
    main()
