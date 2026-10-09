"""Automated line acceptance test harness simulating known-good and seeded defect seats."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import numpy as np

from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.config import load_system_config
from camerainspection.core.models import Outcome, StationInspectionResult
from camerainspection.hardware.camera.synthetic import SyntheticCamera
from camerainspection.hardware.conveyor.simulator import ConveyorSimulator
from camerainspection.hardware.operator_panel.simulator import OperatorPanelSimulator
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.hardware.rfid.simulator import RFIDSimulator
from camerainspection.storage.db import DatabaseManager


def run_acceptance_test(num_clean_seats: int = 100) -> bool:
    """Run full automated line acceptance test."""
    print("=" * 70)
    print("      AUTOMATED INSPECTION LINE - ACCEPTANCE TEST SUITE")
    print("=" * 70)
    print(f"Simulating {num_clean_seats} known-good seats + 6 seeded safety defect seats...\n")

    # In-memory clean DB and hardware simulators
    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()

    plc = PLCSimulator()
    plc.connect()
    conveyor = ConveyorSimulator()
    rfid = RFIDSimulator()
    coord = InspectionCoordinator(plc=plc, db_manager=db, enable_watchdog=False)

    passed_clean = 0
    clean_printer_enabled = 0

    # Ensure lock sensor and metrics are confirmed for standard passes
    plc.simulate_mechanism_sensor(locked=True)
    plc.simulate_mechanism_metrics(torque_nm=42.0, actuator_pos_mm=240.0, slip_back_mm=0.0)

    clean_measurements = {
        "STATION_1": {"seating_face.defect_count": 0.0},
        "STATION_2": {"seam.stitch_count": 120.0},
        "STATION_3": {"buckle.present": 1.0},
        "STATION_4": {"recliner_angle_deg": 22.0},
    }

    # 1. Run N clean seats
    for i in range(num_clean_seats):
        sid = f"ACCEPT_CLEAN_{i:04d}"
        rfid.write_tag(sid)
        plc.set_label_printer_enable(False, seat_id=sid)

        overall = None
        for st_id in ["STATION_1", "STATION_2", "STATION_3", "STATION_4"]:
            res = StationInspectionResult(
                seat_id=sid,
                station_id=st_id,
                variant_id="FRONT_LH_BLACK",
                outcome=Outcome.PASS,
                cycle_time_ms=105.0,
                measurements=clean_measurements[st_id],
            )
            overall = coord.register_station_result(res)

        assert overall is not None
        if overall.outcome == Outcome.PASS and overall.label_printer_enabled:
            passed_clean += 1
            clean_printer_enabled += 1
            conveyor.release_to_mainline(sid)
            coord.mark_seat_printed(sid)

    print(f"  [OK] Clean Seats Passed: {passed_clean} / {num_clean_seats}")
    print(f"  [OK] Printer Interlock Engaged for Clean Seats: {clean_printer_enabled} / {num_clean_seats}")

    # 2. Seeded Defect Test Cases
    seeded_cases = [
        {
            "id": "DEFECT_01_BROKEN_THREAD",
            "station": "STATION_2",
            "defect_type": "broken_thread",
            "measurements": {"thread.broken_count": 2.0},
            "desc": "Station 2 Broken Thread",
        },
        {
            "id": "DEFECT_02_SKIP_STITCH",
            "station": "STATION_2",
            "defect_type": "skip_stitch",
            "measurements": {"seam.skip_gap_mm": 12.5},
            "desc": "Station 2 Skip Stitch",
        },
        {
            "id": "DEFECT_03_WRONG_HAND_BUCKLE",
            "station": "STATION_3",
            "defect_type": "wrong_hand_variant",
            "measurements": {"buckle.orientation_deg": 180.0},
            "desc": "Station 3 Wrong Hand Buckle",
        },
        {
            "id": "DEFECT_04_UNCONFIRMED_RECLINER",
            "station": "STATION_4",
            "defect_type": "unconfirmed_lock_torque",
            "measurements": {"recliner_angle_deg": 22.0, "recliner.lock_torque_nm": 12.0},  # Low torque
            "desc": "Station 4 Unconfirmed Recliner Lock",
        },
        {
            "id": "DEFECT_05_LEATHER_SCRATCH",
            "station": "STATION_1",
            "defect_type": "leather_scratch",
            "measurements": {"leather.scratch_len_mm": 25.0},
            "desc": "Station 1 Leather Scratch",
        },
        {
            "id": "DEFECT_06_LOCK_SENSOR_UNLOCKED",
            "station": "STATION_4",
            "defect_type": "lock_sensor_unconfirmed",
            "measurements": {"recliner_angle_deg": 22.0, "mechanism.sensor_state": 0.0},
            "desc": "Station 4 Lock Sensor Unlocked",
        },
    ]

    detected_defects = 0
    escaped_defects = 0

    print("\nExecuting Seeded Safety Defect Tests:")
    for tc in seeded_cases:
        sid = tc["id"]
        rfid.write_tag(sid)
        plc.set_label_printer_enable(False, seat_id=sid)

        if tc["defect_type"] == "lock_sensor_unconfirmed":
            plc.simulate_mechanism_sensor(locked=False)
        else:
            plc.simulate_mechanism_sensor(locked=True)

        overall = None
        for st_id in ["STATION_1", "STATION_2", "STATION_3", "STATION_4"]:
            if st_id == tc["station"]:
                res = StationInspectionResult(
                    seat_id=sid,
                    station_id=st_id,
                    variant_id="FRONT_LH_BLACK",
                    outcome=Outcome.FAIL,
                    cycle_time_ms=110.0,
                    measurements=tc["measurements"],
                )
            else:
                res = StationInspectionResult(
                    seat_id=sid,
                    station_id=st_id,
                    variant_id="FRONT_LH_BLACK",
                    outcome=Outcome.PASS,
                    cycle_time_ms=100.0,
                    measurements=clean_measurements[st_id],
                )
            overall = coord.register_station_result(res)

        assert overall is not None

        # CRITICAL SAFETY ASSERTIONS
        if overall.outcome == Outcome.FAIL and not overall.label_printer_enabled and not plc.is_label_printer_enabled():
            detected_defects += 1
            conveyor.divert_to_reject(sid)
            print(f"  [OK] BLOCKED & DIVERTED TO REJECT: {tc['desc']} ({sid})")
        else:
            escaped_defects += 1
            print(f"  [FAIL] SAFETY ESCAPE DETECTED! Seat: {sid}, Printer: {overall.label_printer_enabled}")

    # Summary
    total_tested = num_clean_seats + len(seeded_cases)
    print("\n" + "=" * 70)
    print("                    ACCEPTANCE TEST SUMMARY")
    print("=" * 70)
    print(f"Total Seats Processed:          {total_tested}")
    print(f"Known-Good Seats Passed:        {passed_clean} / {num_clean_seats} ({passed_clean / num_clean_seats * 100:.1f}%)")
    print(f"Seeded Defects Intercepted:     {detected_defects} / {len(seeded_cases)} ({detected_defects / len(seeded_cases) * 100:.1f}%)")
    print(f"Escaped Defects:                {escaped_defects}")
    print(f"Mainline Conveyor Released:     {len(conveyor.mainline_seats)}")
    print(f"Reject Spur Diverted:           {len(conveyor.diverted_seats)}")
    print("=" * 70)

    success = (passed_clean == num_clean_seats) and (detected_defects == len(seeded_cases)) and (escaped_defects == 0)
    if success:
        print("\n>>> ACCEPTANCE TEST PASSED: All safety and line criteria satisfied. <<<\n")
    else:
        print("\n>>> ACCEPTANCE TEST FAILED! Safety criteria violated. <<<\n")

    return success


def main() -> None:
    parser = argparse.ArgumentParser(description="Seat Inspection Automated Acceptance Test")
    parser.add_argument("--clean-seats", type=int, default=100, help="Number of clean seats to simulate (default: 100)")
    args = parser.parse_args()

    ok = run_acceptance_test(num_clean_seats=args.clean_seats)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
