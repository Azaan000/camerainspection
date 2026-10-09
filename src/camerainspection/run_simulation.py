"""Interactive line simulation runner: runs simulated seats through Stations 1 to 4."""

from __future__ import annotations

import time
from pathlib import Path
from camerainspection.core.config import load_station_config, load_system_config
from camerainspection.core.models import Outcome
from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.hardware.camera.replay import FolderReplayCamera
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
import cv2


def setup_simulation_data(data_root: Path, variants_dir: Path) -> None:
    """Prepare simulated replay frames for each station."""
    # Station 1
    generate_station1_replay_frames(data_root / "station_1" / "replay")

    # Station 2
    generate_station2_replay_frames(data_root / "station_2" / "replay")

    # Station 3
    s3_dir = data_root / "station_3" / "replay"
    s3_dir.mkdir(parents=True, exist_ok=True)
    f_pass = generate_station3_test_scene(variants_dir, variant_id="FRONT_LH_BLACK")
    cv2.imwrite(str(s3_dir / "01_pass_scene.png"), f_pass)

    # Station 4
    generate_station4_replay_frames(data_root / "station_4" / "replay")


def run_line_simulation(seats_to_run: int = 5) -> None:
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

    coordinator = InspectionCoordinator(plc=plc, db_manager=db)

    # Initialize all 4 station services
    st1 = Station1Service(
        station_config=load_station_config(Path("configs/stations/station_1_leather.yaml")),
        variants_root=variants_dir,
        camera=FolderReplayCamera(data_root / "station_1" / "replay", loop=True),
        plc=plc, db_manager=db,
    )
    st2 = Station2Service(
        station_config=load_station_config(Path("configs/stations/station_2_stitch.yaml")),
        variants_root=variants_dir,
        camera=FolderReplayCamera(data_root / "station_2" / "replay", loop=True),
        plc=plc, db_manager=db,
    )
    st3 = Station3Service(
        station_config=load_station_config(Path("configs/stations/station_3_plastic.yaml")),
        variants_root=variants_dir,
        camera=FolderReplayCamera(data_root / "station_3" / "replay", loop=True),
        plc=plc, db_manager=db,
    )
    st4 = Station4Service(
        station_config=load_station_config(Path("configs/stations/station_4_complete.yaml")),
        variants_root=variants_dir,
        camera=FolderReplayCamera(data_root / "station_4" / "replay", loop=True),
        plc=plc, db_manager=db,
    )

    stations = [("STATION_1", st1), ("STATION_2", st2), ("STATION_3", st3), ("STATION_4", st4)]

    print(f"Line active. Running {seats_to_run} seats through all 4 stations...\n")

    for i in range(1, seats_to_run + 1):
        seat_id = f"SEAT-{1000 + i}"
        barcode = f"{seat_id}_FRONT_LH_BLACK"
        print(f"--------------------------------------------------")
        print(f"[*] Pallet Arrived: {seat_id} (Variant: FRONT_LH_BLACK)")

        for st_name, st_service in stations:
            plc.simulate_arrival(st_name, barcode)
            res = st_service.run_cycle()
            overall = coordinator.register_station_result(res)
            print(f"    - {st_name:10s} -> {res.outcome.value:6s} (Cycle: {res.cycle_time_ms:.1f}ms, Defects: {len(res.defects)})")

        if overall:
            print(f"[*] FINAL DECISION for {seat_id}: {overall.outcome.value}")
            print(f"    -> OEM Label Printer Enabled: {overall.label_printer_enabled}")
            print(f"    -> Mechanism Lock Confirmed:  {overall.lock_sensor_confirmed}")
        print()

    print("--- SIMULATION BATCH COMPLETE ---")
    print("Database populated! Launch the server to view dashboard stats.\n")


if __name__ == "__main__":
    run_line_simulation()
