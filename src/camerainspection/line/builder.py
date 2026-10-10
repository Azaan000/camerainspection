"""Line hardware and service builder constructing all industrial components from configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from camerainspection.coordinator.service import InspectionCoordinator
from camerainspection.core.config import (
    SystemConfig,
    load_station_config,
)
from camerainspection.core.logging import get_logger
from camerainspection.hardware.camera.factory import build_camera
from camerainspection.hardware.conveyor.base import BaseConveyor
from camerainspection.hardware.conveyor.factory import build_conveyor
from camerainspection.hardware.fixture.simulator import SimulatedFixture
from camerainspection.hardware.lighting.simulator import SimulatedLightController
from camerainspection.hardware.operator_panel.base import BaseOperatorPanel
from camerainspection.hardware.operator_panel.factory import build_operator_panel
from camerainspection.hardware.plc.base import BasePLC
from camerainspection.hardware.plc.modbus import ModbusPLC
from camerainspection.hardware.plc.opcua import OPCUAPLC
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.hardware.plc.snap7 import SiemensSnap7PLC
from camerainspection.hardware.rfid.base import BaseRFIDReader
from camerainspection.hardware.rfid.factory import build_rfid_reader
from camerainspection.station.base_station import BaseStation
from camerainspection.station.station_1 import Station1Service
from camerainspection.station.station_2 import Station2Service
from camerainspection.station.station_3 import Station3Service
from camerainspection.station.station_4 import Station4Service
from camerainspection.storage.db import DatabaseManager
from camerainspection.vision.calibration.manager import CalibrationManager

logger = get_logger("line.builder")


@dataclass
class LineRuntime:
    """Encapsulates all instantiated hardware adapters, database, coordinator, and stations for the line."""

    config: SystemConfig
    db_manager: DatabaseManager
    plc: BasePLC
    coordinator: InspectionCoordinator
    conveyor: BaseConveyor
    rfid: BaseRFIDReader
    operator_panel: BaseOperatorPanel
    stations: dict[str, BaseStation] = field(default_factory=dict)
    calibration_manager: CalibrationManager | None = None


def build_plc(
    sys_cfg: SystemConfig,
    adapter_override: str | None = None,
    simulate_lock: bool = True,
) -> BasePLC:
    """Instantiate and connect line PLC interface."""
    adapter = (adapter_override or sys_cfg.plc.adapter).lower().strip()
    if adapter == "modbus":
        plc: BasePLC = ModbusPLC(
            host=sys_cfg.plc.host,
            port=sys_cfg.plc.port,
            expected_stations=sys_cfg.coordinator.expected_stations,
        )
    elif adapter == "snap7":
        plc = SiemensSnap7PLC(
            host=sys_cfg.plc.host,
            rack=sys_cfg.plc.rack,
            slot=sys_cfg.plc.slot,
            expected_stations=sys_cfg.coordinator.expected_stations,
        )
    elif adapter == "opcua":
        plc = OPCUAPLC(
            endpoint=f"opc.tcp://{sys_cfg.plc.host}:{sys_cfg.plc.port}",
            expected_stations=sys_cfg.coordinator.expected_stations,
        )
    else:
        sim = PLCSimulator(expected_stations=sys_cfg.coordinator.expected_stations)
        if simulate_lock:
            sim.simulate_mechanism_sensor(locked=True)
            sim.simulate_mechanism_metrics(torque_nm=22.0, actuator_pos_mm=240.0, slip_back_mm=0.0)
        plc = sim

    plc.connect()
    return plc


def build_line(
    sys_cfg: SystemConfig,
    overrides: dict[str, Any] | None = None,
    variants_root: Path | None = None,
    stations_dir: Path | None = None,
) -> LineRuntime:
    """Build and wire entire physical/simulated line according to system configuration and CLI overrides."""
    overrides = overrides or {}
    v_root = variants_root or Path("configs/variants")
    st_dir = stations_dir or Path("configs/stations")

    # 1. Database
    db_url = overrides.get("db_url") or os.getenv("DATABASE_URL") or sys_cfg.database.url
    db = DatabaseManager(db_url=db_url, echo=sys_cfg.database.echo_sql)
    db.init_tables()

    # 2. PLC
    plc_override = overrides.get("plc_adapter")
    simulate_lock = overrides.get("simulate_lock", True)
    plc = build_plc(sys_cfg, adapter_override=plc_override, simulate_lock=simulate_lock)

    # 3. Conveyor, RFID, Operator Panel
    conveyor_cfg = overrides.get("conveyor") or {"adapter": overrides.get("conveyor_adapter", "simulator")}
    conveyor = build_conveyor(conveyor_cfg, plc=plc)

    rfid_cfg = overrides.get("rfid") or {"adapter": overrides.get("rfid_adapter", "simulator")}
    rfid = build_rfid_reader(rfid_cfg)
    if hasattr(rfid, "connect"):
        rfid.connect()

    panel_cfg = overrides.get("operator_panel") or {"adapter": overrides.get("operator_panel_adapter", "simulator")}
    panel = build_operator_panel(panel_cfg, plc=plc)

    # 4. Calibration Manager
    cal_dir = overrides.get("calibrations_dir", Path("configs/calibrations"))
    cal_mgr = CalibrationManager(calibrations_dir=Path(cal_dir))

    # 5. Coordinator
    coordinator = InspectionCoordinator(
        plc=plc,
        db_manager=db,
        expected_stations=sys_cfg.coordinator.expected_stations,
        shadow_mode=sys_cfg.shadow_mode,
        cycle_timeout_s=sys_cfg.coordinator.cycle_timeout_s,
    )

    # 6. Build 4 Stations
    camera_adapter_override = overrides.get("camera_adapter")
    camera_url_override = overrides.get("camera_url")
    camera_id_override = overrides.get("camera_id")

    station_configs = {
        "STATION_1": (st_dir / "station_1_leather.yaml", Station1Service),
        "STATION_2": (st_dir / "station_2_stitch.yaml", Station2Service),
        "STATION_3": (st_dir / "station_3_plastic.yaml", Station3Service),
        "STATION_4": (st_dir / "station_4_complete.yaml", Station4Service),
    }

    built_stations: dict[str, BaseStation] = {}
    for st_id, (cfg_path, svc_cls) in station_configs.items():
        if not cfg_path.exists():
            continue
        st_cfg = load_station_config(cfg_path)

        # Build cameras with CLI overrides if specified
        st_cameras: dict[str, Any] = {}
        for cam_cfg in st_cfg.cameras:
            if not cam_cfg.enabled:
                continue
            # Apply overrides to camera config if supplied
            if camera_url_override:
                cam_cfg.camera_id = camera_url_override
            elif camera_id_override is not None:
                cam_cfg.camera_id = camera_id_override

            st_cameras[cam_cfg.name] = build_camera(
                cam_cfg, adapter_override=camera_adapter_override
            )

        fixture = SimulatedFixture()
        lighting = SimulatedLightController()

        svc = svc_cls(
            station_config=st_cfg,
            variants_root=v_root,
            cameras=st_cameras,
            plc=plc,
            db_manager=db,
            fixture=fixture,
            lighting_controller=lighting,
            calibration_manager=cal_mgr,
            shadow_mode=sys_cfg.shadow_mode,
            config_version=sys_cfg.config_version,
            require_all_hardware=sys_cfg.hardware.require_all,
        )
        built_stations[st_id] = svc

    return LineRuntime(
        config=sys_cfg,
        db_manager=db,
        plc=plc,
        coordinator=coordinator,
        conveyor=conveyor,
        rfid=rfid,
        operator_panel=panel,
        stations=built_stations,
        calibration_manager=cal_mgr,
    )
