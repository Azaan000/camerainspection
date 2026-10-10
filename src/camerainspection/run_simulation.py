"""Interactive line simulation runner: runs simulated seats through Stations 1 to 4."""

from __future__ import annotations

import argparse
from pathlib import Path
import time
import cv2
import numpy as np

from camerainspection.core.config import load_system_config
from camerainspection.core.models import Outcome
from camerainspection.line.builder import build_line
from camerainspection.line.controller import LineController

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

    # Add README in data/replay folder explaining directory structure
    replay_readme = data_root / "README.md"
    if not replay_readme.exists():
        replay_readme.write_text(
            "# Simulation Replay Data Directory\n\n"
            "Contains organized replay frames categorized by station and multi-camera perspectives:\n"
            "- station_1/replay: front_cushion_backrest, rear_back_map_pocket\n"
            "- station_2/replay: left_bolster, right_bolster, headrest, seam_arm\n"
            "- station_3/replay: side_shield_handle_lever, underside\n"
            "- station_4/replay: recliner_track\n"
        )


def run_line_simulation(
    seats_to_run: int = 5,
    camera_adapter: str | None = None,
    camera_url: str | None = None,
    camera_id: str | None = None,
    scenario: str = "clean",
) -> None:
    print("\n--- INITIALIZING CAR SEAT INSPECTION LINE SIMULATION ---")
    data_root = Path("data")
    variants_dir = Path("configs/variants")
    setup_simulation_data(data_root, variants_dir)

    sys_cfg = load_system_config(Path("configs/system.yaml"))

    overrides = {
        "camera_adapter": camera_adapter,
        "camera_url": camera_url,
        "camera_id": camera_id,
        "simulate_lock": True,
    }

    line_runtime = build_line(sys_cfg, overrides=overrides)
    controller = LineController(runtime=line_runtime)

    print(f"Line active. Running {seats_to_run} seats through line (Scenario: {scenario})...\n")
    print(f"{'Seat ID':<16} {'Variant':<16} {'Outcome':<8} {'Printer':<8} {'Diverted':<10}")
    print("-" * 62)

    passed_count = 0
    fail_count = 0

    for i in range(1, seats_to_run + 1):
        seat_id = f"SEAT-{1000 + i}"
        var_id = "FRONT_LH_BLACK"

        # In mixed scenario, simulate periodic defect/rework seats
        if scenario == "mixed" and (i % 3 == 0):
            # Simulate defective mechanism sensor state on every 3rd seat
            line_runtime.plc.simulate_mechanism_sensor(locked=False)
        else:
            line_runtime.plc.simulate_mechanism_sensor(locked=True)

        res = controller.run_seat_cycle(seat_id=seat_id, variant_id=var_id)
        outcome_str = res["outcome"].value if hasattr(res["outcome"], "value") else str(res["outcome"])
        printer_str = "ARMED" if res.get("label_printed") else "OFF"
        divert_str = "REJECT" if outcome_str != "PASS" else "MAINLINE"

        if outcome_str == "PASS":
            passed_count += 1
        else:
            fail_count += 1

        print(f"{seat_id:<16} {var_id:<16} {outcome_str:<8} {printer_str:<8} {divert_str:<10}")

    print("-" * 62)
    print(f"BATCH SUMMARY: Total={seats_to_run}, Passed={passed_count}, Failed/Held={fail_count}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Car seat inspection line simulation runner")
    parser.add_argument("--seats", type=int, default=5, help="Number of seats to simulate")
    parser.add_argument(
        "--camera-adapter",
        default=None,
        help="Override camera adapter (replay, synthetic, webcam, basler, hikrobot)",
    )
    parser.add_argument("--camera-url", default=None, help="Stream or RTSP URL for camera")
    parser.add_argument("--camera-id", default=None, help="Camera device index")
    parser.add_argument(
        "--scenario",
        choices=["clean", "mixed"],
        default="clean",
        help="Simulation scenario: clean (all pass) or mixed (seeded defects)",
    )
    args = parser.parse_args()
    run_line_simulation(
        seats_to_run=args.seats,
        camera_adapter=args.camera_adapter,
        camera_url=args.camera_url,
        camera_id=args.camera_id,
        scenario=args.scenario,
    )


if __name__ == "__main__":
    main()
