"""Integration tests for Phase C Line builder, controller, E-Stop, and operating modes."""

from pathlib import Path

from camerainspection.core.config import SystemConfig
from camerainspection.core.models import Outcome
from camerainspection.line.builder import build_line
from camerainspection.line.controller import LineController


def test_line_builder_and_controller_processes_pallets(tmp_path: Path) -> None:
    """Problem 9 / C1, C2: build_line creates all hardware and processes pallets end-to-end."""
    sys_cfg = SystemConfig(
        system={
            "environment": "development",
            "operating_mode": "camera_leads_with_audit",
            "shadow_mode": False,
        }
    )

    overrides = {
        "db_url": "sqlite:///:memory:",
        "camera_adapter": "synthetic",
        "simulate_lock": True,
    }

    runtime = build_line(sys_cfg, overrides=overrides)
    assert len(runtime.stations) == 4
    assert runtime.plc.is_connected() is True

    controller = LineController(runtime)

    # Process 3 consecutive pallets
    for i in range(1, 4):
        sid = f"PALLET_{i:03d}"
        res = controller.run_seat_cycle(seat_id=sid, variant_id="FRONT_LH_BLACK")
        assert res["seat_id"] == sid
        assert res["outcome"] in (Outcome.PASS, Outcome.FAIL, Outcome.REVIEW)


def test_line_controller_emergency_stop_aborts_and_stops_line() -> None:
    """Problem 14 / C4: Emergency stop engages immediately, blocks start, stops conveyor, and disables printer."""
    sys_cfg = SystemConfig()
    overrides = {
        "db_url": "sqlite:///:memory:",
        "camera_adapter": "synthetic",
        "simulate_lock": True,
    }

    runtime = build_line(sys_cfg, overrides=overrides)
    controller = LineController(runtime)

    assert controller.is_emergency_stopped() is False

    # Trigger E-stop
    controller.trigger_emergency_stop()
    assert controller.is_emergency_stopped() is True
    assert runtime.conveyor.is_running() is False
    assert runtime.plc.is_label_printer_enabled() is False

    # Cycle initiation while stopped is immediately rejected
    res = controller.run_seat_cycle(seat_id="SEAT-ESTOP-01")
    assert res["status"] == "ABORTED_ESTOP"

    # Reset E-stop allows normal operation
    controller.reset_emergency_stop()
    assert controller.is_emergency_stopped() is False


def test_line_reject_diversion_routing() -> None:
    """Problem 14 / C4: Failing pallet is diverted to reject spur."""
    sys_cfg = SystemConfig()
    overrides = {
        "db_url": "sqlite:///:memory:",
        "camera_adapter": "synthetic",
        "simulate_lock": False,  # Unlocked lock sensor causes failure
    }

    runtime = build_line(sys_cfg, overrides=overrides)
    controller = LineController(runtime)

    res = controller.run_seat_cycle(seat_id="SEAT-REJECT-01")
    assert res["outcome"] != Outcome.PASS
    assert "SEAT-REJECT-01" in runtime.conveyor.diverted_seats
