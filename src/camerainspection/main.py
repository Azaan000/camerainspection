"""Main entrypoint to run the Automated Camera Inspection System service & dashboard."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import threading
import time
import uvicorn

from camerainspection.api.app import create_app
from camerainspection.core.config import load_system_config
from camerainspection.core.logging import get_logger
from camerainspection.line.builder import build_line, build_plc
from camerainspection.line.controller import LineController

logger = get_logger("app.main")

# Background line runner thread handle
_station_runner_thread: threading.Thread | None = None
_stop_runner_event = threading.Event()


def _station_worker_loop(controller: LineController, stop_event: threading.Event) -> None:
    """Simulated background line processor checking triggers and processing arrived pallets."""
    logger.info("Background station runner worker started.")
    pallet_counter = 1
    while not stop_event.is_set():
        try:
            # Check for simulated arrival on line every 3 seconds if in development
            if controller.runtime.config.environment == "development" and not controller.is_emergency_stopped():
                seat_id = f"AUTO_SEAT_{pallet_counter:04d}"
                controller.run_seat_cycle(seat_id=seat_id, variant_id="FRONT_LH_BLACK")
                pallet_counter += 1
        except Exception as e:
            logger.error(f"Error in background station worker loop: {e}")
        time.sleep(3.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated Camera Inspection System Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload")
    parser.add_argument("--config", type=Path, default=Path("configs/system.yaml"), help="Path to system config")
    parser.add_argument("--plc-adapter", default=None, help="Override PLC adapter (simulator, modbus, snap7, opcua)")
    parser.add_argument("--lock-sensor", action="store_true", default=None, help="Force lock sensor state in simulator")
    parser.add_argument(
        "--camera-adapter",
        default=None,
        help="Override camera adapter (replay, synthetic, webcam, basler, hikrobot)",
    )
    parser.add_argument("--camera-url", default=None, help="Stream / IP URL for webcam/phone camera adapter")
    parser.add_argument("--camera-id", default=None, help="Device ID index for webcam adapter")
    parser.add_argument(
        "--run-worker",
        action="store_true",
        default=False,
        help="Run background station pallet worker thread",
    )
    args = parser.parse_args()

    # Load system settings
    sys_cfg = load_system_config(args.config)
    logger.info(
        f"Loaded system configuration: env={sys_cfg.environment}, "
        f"operating_mode={sys_cfg.operating_mode}, shadow_mode={sys_cfg.shadow_mode}, "
        f"config_version={sys_cfg.config_version}"
    )

    overrides = {
        "plc_adapter": args.plc_adapter,
        "simulate_lock": True if args.lock_sensor is None else args.lock_sensor,
        "camera_adapter": args.camera_adapter,
        "camera_url": args.camera_url,
        "camera_id": args.camera_id,
    }

    # Build entire line hardware & runtime container using line builder
    line_runtime = build_line(sys_cfg, overrides=overrides)
    controller = LineController(runtime=line_runtime)

    # Build FastAPI app with dashboard and APIs
    app = create_app(db_manager=line_runtime.db_manager, coordinator=line_runtime.coordinator)

    if args.run_worker:
        global _station_runner_thread
        _stop_runner_event.clear()
        _station_runner_thread = threading.Thread(
            target=_station_worker_loop,
            args=(controller, _stop_runner_event),
            daemon=True,
            name="line-station-worker",
        )
        _station_runner_thread.start()

    @app.on_event("shutdown")
    def shutdown_event() -> None:
        logger.info("Server shutting down. Terminating worker and coordinator watchdog...")
        _stop_runner_event.set()
        line_runtime.coordinator.shutdown()

    print("\n" + "=" * 60)
    print("   AUTOMATED CAMERA INSPECTION SYSTEM - LINE SERVER")
    print("=" * 60)
    print(f" -> Interactive API / Swagger:  http://{args.host}:{args.port}/docs")
    print(f" -> Live Line 20-Seat Strip:   http://{args.host}:{args.port}/api/v1/dashboard/live")
    print(f" -> Quality Trends & Pareto:   http://{args.host}:{args.port}/api/v1/dashboard/quality-trends")
    print(f" -> Defect Gallery:            http://{args.host}:{args.port}/api/v1/dashboard/defect-gallery")
    print(f" -> Review Queue:              http://{args.host}:{args.port}/api/v1/reviews/pending")
    print(f" -> System Health:             http://{args.host}:{args.port}/api/v1/dashboard/system-health")
    print("=" * 60 + "\n")

    try:
        uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
    finally:
        _stop_runner_event.set()
        line_runtime.coordinator.shutdown()


if __name__ == "__main__":
    main()
