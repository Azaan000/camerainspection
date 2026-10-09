"""Main entrypoint to run the Automated Camera Inspection System service & dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path
import uvicorn

from camerainspection.api.app import create_app
from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.config import load_system_config
from camerainspection.core.logging import get_logger
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.storage.db import DatabaseManager

logger = get_logger("app.main")


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated Camera Inspection System Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload")
    parser.add_argument("--config", type=Path, default=Path("configs/system.yaml"), help="Path to system config")
    args = parser.parse_args()

    # Load system settings
    sys_cfg = load_system_config(args.config)
    logger.info(f"Loaded system configuration: env={sys_cfg.environment}, shadow_mode={sys_cfg.shadow_mode}")

    # Initialize Database
    db = DatabaseManager(db_url=sys_cfg.database.url, echo=sys_cfg.database.echo_sql)
    db.init_tables()
    logger.info(f"Database initialized at: {sys_cfg.database.url}")

    # Initialize PLC interface (simulator default)
    plc = PLCSimulator()
    plc.connect()
    # Confirm mechanism sensor in dev simulator by default
    plc.simulate_mechanism_sensor(locked=True)
    logger.info("PLC Simulator connected with mechanism sensor confirmed.")

    # Initialize Inspection Coordinator
    coordinator = InspectionCoordinator(
        plc=plc,
        db_manager=db,
        expected_stations=sys_cfg.coordinator.expected_stations,
        shadow_mode=sys_cfg.shadow_mode,
    )
    logger.info(f"Coordinator active for stations: {sys_cfg.coordinator.expected_stations}")

    # Build FastAPI app with dashboard and APIs
    app = create_app(db_manager=db, coordinator=coordinator)

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

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
