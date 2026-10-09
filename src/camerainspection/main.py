"""Main entrypoint to run the Automated Camera Inspection System service & dashboard."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import uvicorn

from camerainspection.api.app import create_app
from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.config import load_system_config
from camerainspection.core.logging import get_logger
from camerainspection.hardware.plc.base import BasePLC
from camerainspection.hardware.plc.modbus import ModbusPLC
from camerainspection.hardware.plc.opcua import OPCUAPLC
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.hardware.plc.snap7 import SiemensSnap7PLC
from camerainspection.storage.db import DatabaseManager

logger = get_logger("app.main")


def build_plc_adapter(
    adapter_name: str,
    host: str = "127.0.0.1",
    port: int = 502,
    rack: int = 0,
    slot: int = 1,
    expected_stations: list[str] | None = None,
    simulate_lock: bool = True,
) -> BasePLC:
    """Instantiate line PLC interface based on system configuration."""
    adapter_lower = adapter_name.lower().strip()
    if adapter_lower == "modbus":
        plc: BasePLC = ModbusPLC(host=host, port=port, expected_stations=expected_stations)
    elif adapter_lower == "snap7":
        plc = SiemensSnap7PLC(host=host, rack=rack, slot=slot, expected_stations=expected_stations)
    elif adapter_lower == "opcua":
        plc = OPCUAPLC(endpoint=f"opc.tcp://{host}:{port}", expected_stations=expected_stations)
    else:
        sim = PLCSimulator(expected_stations=expected_stations)
        if simulate_lock:
            sim.simulate_mechanism_sensor(locked=True)
        plc = sim

    plc.connect()
    return plc


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated Camera Inspection System Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload")
    parser.add_argument("--config", type=Path, default=Path("configs/system.yaml"), help="Path to system config")
    parser.add_argument("--plc-adapter", default=None, help="Override PLC adapter (simulator, modbus, snap7, opcua)")
    parser.add_argument("--lock-sensor", action="store_true", default=None, help="Force lock sensor state in simulator")
    args = parser.parse_args()

    # Load system settings
    sys_cfg = load_system_config(args.config)
    logger.info(
        f"Loaded system configuration: env={sys_cfg.environment}, "
        f"shadow_mode={sys_cfg.shadow_mode}, config_version={sys_cfg.config_version}"
    )

    # Initialize Database: read DATABASE_URL env var (e.g. from Docker) or fallback to config
    db_url = os.getenv("DATABASE_URL") or sys_cfg.database.url
    db = DatabaseManager(db_url=db_url, echo=sys_cfg.database.echo_sql)
    db.init_tables()
    logger.info(f"Database initialized at: {db_url}")

    # Initialize PLC interface (configurable adapter)
    adapter_to_use = args.plc_adapter or sys_cfg.plc.adapter
    simulate_lock = True if args.lock_sensor is None else args.lock_sensor
    plc = build_plc_adapter(
        adapter_name=adapter_to_use,
        host=sys_cfg.plc.host,
        port=sys_cfg.plc.port,
        rack=sys_cfg.plc.rack,
        slot=sys_cfg.plc.slot,
        expected_stations=sys_cfg.coordinator.expected_stations,
        simulate_lock=simulate_lock,
    )
    logger.info(f"PLC interface active: adapter={adapter_to_use}, connected={plc.is_connected()}")

    # Initialize Inspection Coordinator
    coordinator = InspectionCoordinator(
        plc=plc,
        db_manager=db,
        expected_stations=sys_cfg.coordinator.expected_stations,
        shadow_mode=sys_cfg.shadow_mode,
        cycle_timeout_s=sys_cfg.coordinator.cycle_timeout_s,
    )
    logger.info(
        f"Coordinator active for stations: {sys_cfg.coordinator.expected_stations}, "
        f"timeout={sys_cfg.coordinator.cycle_timeout_s}s, config_version={sys_cfg.config_version}"
    )

    # Build FastAPI app with dashboard and APIs
    app = create_app(db_manager=db, coordinator=coordinator)

    @app.on_event("shutdown")
    def shutdown_event() -> None:
        logger.info("Server shutting down. Terminating coordinator watchdog...")
        coordinator.shutdown()

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
        coordinator.shutdown()


if __name__ == "__main__":
    main()
