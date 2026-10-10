"""Common base class for inspection stations orchestrating hardware, vision, and fail-safe logic."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from camerainspection.core.config import (
    CameraConfig,
    StationConfig,
    load_variant_config,
)
from camerainspection.core.exceptions import (
    CameraOfflineError,
    HardwareError,
    InvalidBarcodeError,
    PLCTriggerTimeoutError,
)
from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.logging import get_logger
from camerainspection.core.models import (
    CameraInspectionResult,
    DefectDetail,
    Outcome,
    StationInspectionResult,
)
from camerainspection.hardware.camera.base import BaseCamera
from camerainspection.hardware.camera.factory import build_camera
from camerainspection.hardware.plc.base import BasePLC
from camerainspection.inference.base import BaseInferenceEngine
from camerainspection.storage.db import DatabaseManager

logger = get_logger("station.base")


class BaseStation(ABC):
    """Abstract station service implementing trigger-capture-inspect-interlock lifecycle."""

    def __init__(
        self,
        station_config: StationConfig,
        variants_root: Path,
        camera: BaseCamera | None = None,
        cameras: dict[str, BaseCamera] | None = None,
        plc: BasePLC | None = None,
        db_manager: DatabaseManager | None = None,
        inference_engine: BaseInferenceEngine | None = None,
        default_limits_path: Path | None = None,
        shadow_mode: bool = False,
        config_version: str = "v0.1.0",
        fixture: Any = None,
        lighting_controller: Any = None,
        calibration_manager: Any = None,
        require_all_hardware: bool | None = None,
    ) -> None:
        self.config = station_config
        self.variants_root = Path(variants_root)
        self.plc = plc
        self.db_manager = db_manager
        self.inference_engine = inference_engine
        self.default_limits_path = default_limits_path
        self.shadow_mode = shadow_mode
        self._config_version = config_version
        self.fixture = fixture
        self.lighting_controller = lighting_controller
        self.calibration_manager = calibration_manager

        # Hardware presence enforcement (A1 / #1)
        # When require_all_hardware is True, station fails safe if any fixture/lighting/calibration is missing
        self.require_all_hardware = bool(require_all_hardware)

        # Initialize multi-camera dictionary
        self.cameras: dict[str, BaseCamera] = {}
        if cameras is not None:
            self.cameras = dict(cameras)
            self.camera = next(iter(self.cameras.values())) if self.cameras else camera
        elif camera is not None:
            # Explicit single camera override takes precedence over config
            self.cameras = {"main": camera}
            self.camera = camera
        elif self.config.cameras:
            for cam_cfg in self.config.cameras:
                if cam_cfg.enabled:
                    self.cameras[cam_cfg.name] = build_camera(cam_cfg)
            self.camera = next(iter(self.cameras.values())) if self.cameras else build_camera(self.config.camera)
        else:
            self.camera = build_camera(self.config.camera)
            self.cameras = {"main": self.camera}

    @property
    def station_id(self) -> str:
        return self.config.station_id

    def parse_barcode(self, raw_barcode: str) -> tuple[str, str]:
        """Extract seat ID and variant ID from barcode string.

        Resolution order:
        1. Colon separator — ``<SEAT_ID>:<VARIANT_ID>`` — unambiguous.
        2. Known-variant suffix matching — walks variant dirs and strips the longest
           ``_<VARIANT_ID>`` suffix that matches a known directory.
        3. Bare variant barcode — if the whole barcode is a known variant ID.
        4. Fallback underscore split (first ``_``).
        """
        barcode = raw_barcode.strip()
        if not barcode:
            raise InvalidBarcodeError("Barcode is blank or unreadable.")

        # 1. Colon separator
        if ":" in barcode:
            seat_id, _, variant_id = barcode.partition(":")
            return seat_id.strip(), variant_id.strip()

        # Discover known variant IDs from the filesystem
        known_variants: list[str] = []
        if self.variants_root.is_dir():
            known_variants = sorted(
                (p.name for p in self.variants_root.iterdir() if p.is_dir()),
                key=len,
                reverse=True,
            )

        # 2. Suffix-match against known variants
        for vid in known_variants:
            suffix = f"_{vid}"
            if barcode.endswith(suffix):
                seat_id = barcode[: -len(suffix)]
                return seat_id, vid

        # 3. Bare variant barcode
        if barcode in known_variants:
            seat_id = f"SEAT-{int(time.time())}"
            return seat_id, barcode

        # 4. Fallback: split on first underscore
        if "_" in barcode:
            seat_id, _, variant_id = barcode.partition("_")
            return seat_id, variant_id

        # No separator at all — treat whole barcode as seat_id with unknown variant
        raise InvalidBarcodeError(
            f"Cannot resolve variant from barcode '{barcode}'. "
            "Expected '<SEAT_ID>_<VARIANT_ID>' or '<SEAT_ID>:<VARIANT_ID>'."
        )

    def inspect_camera_view(
        self,
        camera_name: str,
        view: str,
        image: np.ndarray,
        variant_id: str,
        evaluator: LimitsEvaluator,
        variant_nominals: dict[str, Any],
        camera_config: CameraConfig,
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        """Inspect a single camera view. Subclasses can override or fall back to inspect_image."""
        return self.inspect_image(
            image=image,
            variant_id=variant_id,
            evaluator=evaluator,
            variant_nominals=variant_nominals,
        )

    @abstractmethod
    def inspect_image(
        self,
        image: np.ndarray,
        variant_id: str,
        evaluator: LimitsEvaluator,
        variant_nominals: dict[str, Any],
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        """Execute legacy single-image inspection pipeline."""

    def get_required_measurements(self) -> list[str]:
        """Return list of measurement keys that must affirmatively be produced by this station."""
        return []

    def is_valid_measurement(self, key: str, value: Any) -> bool:
        """Affirmatively validate that a measurement value is numeric and finite (not None, NaN, Inf)."""
        import math
        if value is None:
            return False
        if not isinstance(value, (int, float)):
            return False
        return not (math.isnan(value) or math.isinf(value))

    def run_cycle(self) -> StationInspectionResult:
        """Execute one complete inspection cycle with multi-camera acquisition and fail-safe guarantees."""
        start_time = time.perf_counter()
        cycle_timestamp = datetime.now(UTC)
        seat_id = "UNKNOWN"
        variant_id = "UNKNOWN"

        try:
            # 0. Hardware presence pre-check (Problem 1 / A1)
            if self.require_all_hardware:
                missing_hw: list[str] = []
                if self.fixture is None:
                    missing_hw.append("fixture")
                if self.lighting_controller is None:
                    missing_hw.append("lighting_controller")
                if self.calibration_manager is None:
                    missing_hw.append("calibration_manager")

                if missing_hw:
                    err_desc = f"Required hardware objects not configured at {self.station_id}: {missing_hw}"
                    logger.error(err_desc)
                    raise HardwareError(f"hardware.not_configured: {missing_hw}")

            # 1. Wait for trigger
            if self.plc is not None:
                triggered = self.plc.wait_for_trigger(
                    self.station_id, timeout_s=self.config.trigger.timeout_s
                )
                if not triggered:
                    raise PLCTriggerTimeoutError(
                        f"Trigger timed out after {self.config.trigger.timeout_s}s at {self.station_id}"
                    )
                raw_barcode = self.plc.read_barcode(self.station_id)
            else:
                raw_barcode = "SEAT-MOCK:FRONT_LH_BLACK"

            # 2. Read barcode & resolve variant
            seat_id, variant_id = self.parse_barcode(raw_barcode)

            logger.info(
                f"Starting inspection for seat {seat_id} (variant {variant_id}) at {self.station_id}",
                extra={"seat_id": seat_id, "station_id": self.station_id, "variant_id": variant_id},
            )

            # 3. Load variant config and active limits
            variant_cfg, merged_limits = load_variant_config(
                variant_id=variant_id,
                variants_root=self.variants_root,
                default_limits_path=self.default_limits_path,
            )
            evaluator = LimitsEvaluator(merged_limits)

            # 4. Fixture Clamping Interlock (Phase 3)
            # Confirm clamp before any movement or acquisition; fail closed if unconfirmed
            if self.fixture is not None:
                self.fixture.clamp()
                if not self.fixture.is_clamped():
                    raise HardwareError(
                        f"Fixture clamp confirmation sensor failed at {self.station_id}. Pallet unconfirmed."
                    )

            # 5. Determine enabled cameras to capture
            if list(self.cameras.keys()) == ["main"]:
                # Single camera override mode (backwards compatible for callers passing camera=...)
                enabled_cameras = [
                    CameraConfig(
                        name="main",
                        view="main",
                        adapter="synthetic",
                        pixel_size_mm=self.config.camera.pixel_size_mm,
                    )
                ]
            else:
                enabled_cameras = [c for c in self.config.cameras if c.enabled]
                if not enabled_cameras:
                    enabled_cameras = [self.config.camera]

            if not enabled_cameras:
                raise CameraOfflineError(f"No enabled cameras configured for {self.station_id}")

            # Build sequence steps: respect capture_sequence if configured, otherwise camera order
            if self.config.capture_sequence:
                sequence_steps = []
                for seq_entry in self.config.capture_sequence:
                    cam_name = seq_entry.get("camera") or seq_entry.get("camera_name")
                    matching_cam = next((c for c in enabled_cameras if c.name == cam_name), None)
                    if matching_cam is not None:
                        sequence_steps.append((seq_entry, matching_cam))
            else:
                sequence_steps = [
                    ({"position": getattr(c, "position", "front"), "camera": c.name}, c)
                    for c in enabled_cameras
                ]

            all_defects: list[DefectDetail] = []
            all_measurements: dict[str, float] = {}
            camera_results: dict[str, CameraInspectionResult] = {}
            camera_image_paths: dict[str, str] = {}
            primary_annotated_img: np.ndarray | None = None
            primary_raw_path: str | None = None
            primary_annotated_path: str | None = None

            # 6. Execute capture sequence
            for step_cfg, cam_cfg in sequence_steps:
                cam_name = cam_cfg.name or "main"
                cam_view = cam_cfg.view or cam_name

                # Fixture positioning hook (Phase 3)
                if self.fixture is not None:
                    target_pos = step_cfg.get("position", "front")
                    arm_pose = step_cfg.get("arm_pose") or getattr(cam_cfg, "arm_pose", None)

                    self.fixture.move_to(target_pos)
                    if arm_pose:
                        self.fixture.move_arm_to(arm_pose)

                    # Strict fail-closed: No capture if fixture not confirmed in position!
                    if not self.fixture.wait_in_position(timeout_s=self.config.trigger.timeout_s):
                        raise HardwareError(
                            f"Fixture not in position '{target_pos}' (arm_pose={arm_pose}) "
                            f"at {self.station_id}. Acquisition refused."
                        )

                # Lighting controller hook (Phase 4)
                if self.lighting_controller is not None:
                    active_lighting = dict(self.config.lighting)
                    if cam_cfg.lighting:
                        active_lighting.update(cam_cfg.lighting)
                    for ch_name, intensity_val in active_lighting.items():
                        clean_ch = ch_name.replace("_intensity_pct", "").replace("_pct", "")
                        verified = self.lighting_controller.apply_and_verify(
                            channel=clean_ch,
                            target_pct=float(intensity_val),
                            tolerance_pct=5.0,
                        )
                        if not verified:
                            raise HardwareError(
                                f"Light channel '{clean_ch}' failed read-back verification at {self.station_id}."
                            )
                        all_measurements[f"light_{clean_ch}_pct"] = float(intensity_val)

                # Camera acquisition
                cam_obj = self.cameras.get(cam_name)
                if cam_obj is None:
                    cam_obj = build_camera(cam_cfg)
                    self.cameras[cam_name] = cam_obj

                # Camera connection failure handling (Problem 8 / A5)
                if not cam_obj.is_connected():
                    try:
                        cam_obj.connect()
                    except Exception as conn_err:
                        logger.error(f"Camera {cam_name} failed to connect at {self.station_id}: {conn_err}")
                        conn_defect = DefectDetail(
                            defect_type="camera.connect_failure",
                            outcome=Outcome.FAIL,
                            camera_name=cam_name,
                            view=cam_view,
                            description=f"Connect failed on camera '{cam_name}': {conn_err}",
                        )
                        camera_results[cam_name] = CameraInspectionResult(
                            camera_name=cam_name,
                            view=cam_view,
                            outcome=Outcome.FAIL,
                            defects=[conn_defect],
                            pixel_size_mm=cam_cfg.pixel_size_mm,
                        )
                        all_defects.append(conn_defect)
                        continue

                try:
                    image = cam_obj.capture()
                except Exception as cap_err:
                    logger.error(f"Camera {cam_name} capture failed at {self.station_id}: {cap_err}")
                    cap_defect = DefectDetail(
                        defect_type="camera.capture_failure",
                        outcome=Outcome.FAIL,
                        camera_name=cam_name,
                        view=cam_view,
                        description=f"Capture failed on camera '{cam_name}': {cap_err}",
                    )
                    camera_results[cam_name] = CameraInspectionResult(
                        camera_name=cam_name,
                        view=cam_view,
                        outcome=Outcome.FAIL,
                        defects=[cap_defect],
                        pixel_size_mm=cam_cfg.pixel_size_mm,
                    )
                    all_defects.append(cap_defect)
                    continue

                # Run vision inspection for this camera view
                cam_defects, cam_measurements, cam_annotated = self.inspect_camera_view(
                    camera_name=cam_name,
                    view=cam_view,
                    image=image,
                    variant_id=variant_id,
                    evaluator=evaluator,
                    variant_nominals=variant_cfg.nominals,
                    camera_config=cam_cfg,
                )

                # Enforce physical calibration on dimensional checks (Phase 5 / A4)
                has_mm_check = any(k.endswith(("_mm", "_mm2", "_deg")) for k in cam_measurements)
                if has_mm_check:
                    if self.calibration_manager is not None:
                        cat = getattr(self.config, "category", "generic")
                        cal_ok, cal_outcome, cal_msg = self.calibration_manager.validate_calibration(
                            cam_name, category=cat
                        )
                        if not cal_ok:
                            cal_defect = DefectDetail(
                                defect_type="camera.uncalibrated",
                                outcome=cal_outcome,
                                camera_name=cam_name,
                                view=cam_view,
                                description=cal_msg,
                            )
                            cam_defects.append(cal_defect)
                    elif self.require_all_hardware:
                        cal_defect = DefectDetail(
                            defect_type="camera.uncalibrated",
                            outcome=Outcome.FAIL,
                            camera_name=cam_name,
                            view=cam_view,
                            description=(
                                f"Dimensional measurements present on camera '{cam_name}' "
                                "but no calibration manager configured."
                            ),
                        )
                        cam_defects.append(cal_defect)

                # Tag defects with camera context
                for d in cam_defects:
                    if not d.camera_name:
                        d.camera_name = cam_name
                    if not d.view:
                        d.view = cam_view

                # Determine camera outcome
                cam_outcomes = [d.outcome for d in cam_defects] if cam_defects else [Outcome.PASS]
                cam_outcome = Outcome.aggregate(cam_outcomes)

                cam_res = CameraInspectionResult(
                    camera_name=cam_name,
                    view=cam_view,
                    outcome=cam_outcome,
                    defects=cam_defects,
                    measurements=cam_measurements,
                    pixel_size_mm=cam_cfg.pixel_size_mm,
                )
                camera_results[cam_name] = cam_res
                all_defects.extend(cam_defects)
                all_measurements.update(cam_measurements)

                if primary_annotated_img is None and cam_annotated is not None:
                    primary_annotated_img = cam_annotated

            # 7. Safety check: every enabled camera must have produced a result
            missing_cameras = [c.name for c in enabled_cameras if c.name not in camera_results]
            if missing_cameras:
                missing_cam_defect = DefectDetail(
                    defect_type="station.missing_camera_result",
                    outcome=Outcome.FAIL,
                    description=f"Enabled cameras {missing_cameras} produced no result at {self.station_id}.",
                )
                all_defects.append(missing_cam_defect)

            # 8. Affirmative verification: check required measurements
            required = self.get_required_measurements()
            invalid_or_missing = [
                req for req in required
                if req not in all_measurements or not self.is_valid_measurement(req, all_measurements.get(req))
            ]
            if invalid_or_missing:
                all_defects.append(
                    DefectDetail(
                        defect_type="station.incomplete_checks",
                        outcome=Outcome.FAIL,
                        description=(
                            f"Station {self.station_id} omitted or produced"
                            f" invalid measurements for: {invalid_or_missing}."
                        ),
                    )
                )

            if not all_defects and not all_measurements:
                no_check_defect = DefectDetail(
                    defect_type="station.no_checks_performed",
                    outcome=Outcome.FAIL,
                    description=f"Station {self.station_id} performed zero checks or measurements on image.",
                )
                all_defects.append(no_check_defect)

            # 9. Overall station outcome aggregation (worst result wins: FAIL > REVIEW > PASS)
            check_outcomes = [d.outcome for d in all_defects] if all_defects else [Outcome.PASS]
            overall_outcome = Outcome.aggregate(check_outcomes)

            # Build result
            cycle_time_ms = (time.perf_counter() - start_time) * 1000.0
            result = StationInspectionResult(
                seat_id=seat_id,
                station_id=self.station_id,
                variant_id=variant_id,
                outcome=overall_outcome,
                defects=all_defects,
                measurements=all_measurements,
                camera_results=camera_results,
                camera_image_paths=camera_image_paths,
                raw_image_path=primary_raw_path,
                annotated_image_path=primary_annotated_path,
                model_version=self.config.model.version,
                config_version=self._config_version,
                cycle_time_ms=cycle_time_ms,
                timestamp=cycle_timestamp,
            )

        except Exception as e:
            # ANY failure MUST fail safe to FAIL or REVIEW, and hold pallet
            cycle_time_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"Station cycle error at {self.station_id} for seat {seat_id}: {e}",
                exc_info=True,
                extra={"seat_id": seat_id, "station_id": self.station_id},
            )

            defect_type_str = "hardware.not_configured" if "hardware.not_configured" in str(e) else "SYSTEM_ERROR"
            fail_defect = DefectDetail(
                defect_type=defect_type_str,
                outcome=Outcome.FAIL,
                description=f"Fail-Safe triggered due to exception: {type(e).__name__} - {e}",
            )
            result = StationInspectionResult(
                seat_id=seat_id,
                station_id=self.station_id,
                variant_id=variant_id,
                outcome=Outcome.FAIL,
                defects=[fail_defect],
                cycle_time_ms=cycle_time_ms,
                timestamp=cycle_timestamp,
            )

        # 10. Persist to DB and Audit Log BEFORE notifying PLC (Problem 2 / A2)
        # If DB write fails, result becomes FAIL, pallet is held, and PLC NEVER receives PASS!
        db_write_successful = True
        if self.db_manager is not None:
            try:
                self.db_manager.record_station_result(result)
                self.db_manager.log_audit(
                    event_type="STATION_CYCLE_COMPLETE",
                    details=(
                        f"Outcome: {result.outcome.value}, "
                        f"Defects: {len(result.defects)}, "
                        f"Cameras: {len(result.camera_results)}, "
                        f"CycleTime: {result.cycle_time_ms:.1f}ms, "
                        f"ShadowMode: {self.shadow_mode}"
                    ),
                    seat_id=result.seat_id,
                    station_id=self.station_id,
                )
            except Exception as db_err:
                logger.error(f"Failed to record station result to DB: {db_err}")
                db_write_successful = False
                # Downgrade result to FAIL
                result.outcome = Outcome.FAIL
                result.defects.append(
                    DefectDetail(
                        defect_type="storage.db_write_failure",
                        outcome=Outcome.FAIL,
                        description=f"DB write failed: {db_err}",
                    )
                )

        # 11. Fixture release: if pass AND DB persisted ok, unclamp fixture
        if self.fixture is not None and result.outcome == Outcome.PASS and db_write_successful:
            self.fixture.release()

        # 12. Apply PLC interlock (only after successful DB write, unless in shadow mode)
        if not self.shadow_mode and self.plc is not None:
            if not db_write_successful:
                # Force pallet hold and notify FAIL to PLC
                self.plc.set_station_result(self.station_id, Outcome.FAIL, seat_id=result.seat_id)
                self.plc.hold_pallet(self.station_id, hold=True)
            else:
                self.plc.set_station_result(self.station_id, result.outcome, seat_id=result.seat_id)
        else:
            logger.info(f"Shadow mode active: PLC interlock skipped for outcome {result.outcome}")

        return result
