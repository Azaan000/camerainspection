"""Common base class for inspection stations orchestrating hardware, vision, and fail-safe logic."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any
import numpy as np

from camerainspection.core.config import (
    StationConfig,
    load_variant_config,
)
from camerainspection.core.exceptions import (
    CameraOfflineError,
    CameraTimeoutError,
    CorruptImageError,
    InvalidBarcodeError,
    PLCTriggerTimeoutError,
    UnknownVariantError,
)
from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.logging import get_logger
from camerainspection.core.models import (
    DefectDetail,
    Outcome,
    StationInspectionResult,
)
from camerainspection.hardware.camera.base import BaseCamera
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
        camera: BaseCamera,
        plc: BasePLC,
        db_manager: DatabaseManager,
        inference_engine: BaseInferenceEngine | None = None,
        default_limits_path: Path | None = None,
        shadow_mode: bool = False,
    ) -> None:
        self.config = station_config
        self.variants_root = Path(variants_root)
        self.camera = camera
        self.plc = plc
        self.db_manager = db_manager
        self.inference_engine = inference_engine
        self.default_limits_path = default_limits_path
        self.shadow_mode = shadow_mode

    @property
    def station_id(self) -> str:
        return self.config.station_id

    def parse_barcode(self, raw_barcode: str) -> tuple[str, str]:
        """Extract seat ID and variant ID from barcode string.

        Conventions supported:
        - '<SEAT_ID>_<VARIANT_ID>' (e.g. 'SEAT123_FRONT_LH_BLACK')
        - '<SEAT_ID>:<VARIANT_ID>'
        - If just a known variant ID is scanned, uses barcode as variant ID and generates seat ID.
        """
        barcode = raw_barcode.strip()
        if not barcode:
            raise InvalidBarcodeError("Barcode is blank or unreadable.")

        if "_" in barcode:
            parts = barcode.split("_", 1)
            seat_id = parts[0]
            variant_id = parts[1]
        elif ":" in barcode:
            parts = barcode.split(":", 1)
            seat_id = parts[0]
            variant_id = parts[1]
        else:
            seat_id = f"SEAT-{int(time.time())}"
            variant_id = barcode

        return seat_id, variant_id

    @abstractmethod
    def inspect_image(
        self,
        image: np.ndarray,
        variant_id: str,
        evaluator: LimitsEvaluator,
        variant_nominals: dict[str, Any],
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        """Execute station-specific vision inspection pipeline.

        Returns:
            tuple[defects_list, measurements_dict, annotated_image_optional]
        """

    def run_cycle(self) -> StationInspectionResult:
        """Execute one complete inspection cycle with strict fail-safe guarantees."""
        start_time = time.perf_counter()
        cycle_timestamp = datetime.now(timezone.utc)
        seat_id = "UNKNOWN"
        variant_id = "UNKNOWN"

        try:
            # 1. Wait for trigger
            triggered = self.plc.wait_for_trigger(
                self.station_id, timeout_s=self.config.trigger.timeout_s
            )
            if not triggered:
                raise PLCTriggerTimeoutError(
                    f"Trigger timed out after {self.config.trigger.timeout_s}s at {self.station_id}"
                )

            # 2. Read barcode & resolve variant
            raw_barcode = self.plc.read_barcode(self.station_id)
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

            # 4. Acquire frame
            if not self.camera.is_connected():
                self.camera.connect()
            image = self.camera.capture()

            # 5. Execute vision inspection
            defects, measurements, annotated_img = self.inspect_image(
                image=image,
                variant_id=variant_id,
                evaluator=evaluator,
                variant_nominals=variant_cfg.nominals,
            )

            # 6. Aggregate check outcomes
            check_outcomes = [d.outcome for d in defects] if defects else [Outcome.PASS]
            overall_outcome = Outcome.aggregate(check_outcomes)

            # Build result
            cycle_time_ms = (time.perf_counter() - start_time) * 1000.0
            result = StationInspectionResult(
                seat_id=seat_id,
                station_id=self.station_id,
                variant_id=variant_id,
                outcome=overall_outcome,
                defects=defects,
                measurements=measurements,
                model_version=self.config.model.version,
                config_version="v0.1.0",
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

            fail_defect = DefectDetail(
                defect_type="SYSTEM_ERROR",
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

        # 7. Apply PLC interlock (unless in shadow mode)
        if not self.shadow_mode:
            self.plc.set_station_result(self.station_id, result.outcome)
        else:
            logger.info(f"Shadow mode active: PLC interlock skipped for outcome {result.outcome}")

        # 8. Persist to DB and Audit Log
        try:
            self.db_manager.record_station_result(result)
            self.db_manager.log_audit(
                event_type="STATION_CYCLE_COMPLETE",
                details=(
                    f"Outcome: {result.outcome.value}, "
                    f"Defects: {len(result.defects)}, "
                    f"CycleTime: {result.cycle_time_ms:.1f}ms, "
                    f"ShadowMode: {self.shadow_mode}"
                ),
                seat_id=result.seat_id,
                station_id=self.station_id,
            )
        except Exception as db_err:
            logger.error(f"Failed to record station result to DB: {db_err}")
            # If DB error occurs, ensure PLC holds pallet if not shadow mode
            if not self.shadow_mode:
                self.plc.hold_pallet(self.station_id, hold=True)

        return result
