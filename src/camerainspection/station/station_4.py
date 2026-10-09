"""Station 4 Service: Complete Seat & Mechanism Cycle Test.

Requirements:
1. Cosmetic checks (wrinkle, puckering, foam show-through) via AI model / rules.
   - Any wrinkle/puckering flagged as REVIEW per default limits.
2. Component presence (motor, sensor, airbag module, connector clicked) via AI model.
   - Any missing component flagged as FAIL.
3. Mechanism cycle test:
   - Recliner angle measurement by camera vs nominal (90.0 deg ± 1.5 pass, ± 2.0 fail).
   - Track end position measurement by camera vs nominal (240.0 mm ± 1.5 pass, ± 2.0 fail).
   - Lock confirmation MUST be read from PLC sensor signal, NEVER from camera.
   - Passes ONLY if:
     1) Actuator reached commanded position
     2) Lock torque/current reached threshold
     3) Position did not slip back
     4) Lock sensor confirmed
     5) Vision confirms lever angle and track end position
     (Vision alone can NEVER pass a mechanism check).
"""

from __future__ import annotations

from typing import Any
import cv2
import numpy as np

from camerainspection.core.config import CameraConfig
from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.logging import get_logger
from camerainspection.core.models import BoundingBox, DefectDetail, Outcome
from camerainspection.station.base_station import BaseStation
from camerainspection.vision.station4.mechanism import MechanismVisionEngine

logger = get_logger("station.4")


class Station4Service(BaseStation):
    """Station 4: Complete Seat Inspection & Mechanism Travel / Sensor Interlock."""

    def get_required_measurements(self) -> list[str]:
        return ["recliner_angle_deg", "track_end_position_mm", "lock_sensor_confirmed"]

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
        """Inspect recliner_track camera view."""
        pixel_size = camera_config.pixel_size_mm or self.config.camera.pixel_size_mm
        return self._inspect_complete_seat(
            image=image,
            variant_id=variant_id,
            evaluator=evaluator,
            variant_nominals=variant_nominals,
            pixel_size_mm=pixel_size,
        )

    def inspect_image(
        self,
        image: np.ndarray,
        variant_id: str,
        evaluator: LimitsEvaluator,
        variant_nominals: dict[str, Any],
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        """Legacy single-image inspection."""
        return self._inspect_complete_seat(
            image=image,
            variant_id=variant_id,
            evaluator=evaluator,
            variant_nominals=variant_nominals,
            pixel_size_mm=self.config.camera.pixel_size_mm,
        )

    def _inspect_complete_seat(
        self,
        image: np.ndarray,
        variant_id: str,
        evaluator: LimitsEvaluator,
        variant_nominals: dict[str, Any],
        pixel_size_mm: float,
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        defects: list[DefectDetail] = []
        measurements: dict[str, float] = {}
        annotated = image.copy()

        # Mechanism nominals from variant config
        mech_nominals = variant_nominals.get("mechanism", {})
        nom_recliner_deg = float(mech_nominals.get("recliner_angle_deg", 90.0))
        nom_track_pos_mm = float(mech_nominals.get("track_end_position_mm", 240.0))

        # -------------------------------------------------------------
        # 1. Mechanism Optical Measurements (Lever Angle & Track End)
        # -------------------------------------------------------------
        recliner_roi_cfg = self.config.regions_of_interest.get("recliner_pivot")
        if recliner_roi_cfg is not None:
            rx1, ry1 = max(0, recliner_roi_cfg.x), max(0, recliner_roi_cfg.y)
            rx2 = min(image.shape[1], recliner_roi_cfg.x + recliner_roi_cfg.w)
            ry2 = min(image.shape[0], recliner_roi_cfg.y + recliner_roi_cfg.h)
            recliner_crop = image[ry1:ry2, rx1:rx2]

            if recliner_crop.size == 0:
                defects.append(
                    DefectDetail(
                        defect_type="station.invalid_roi",
                        outcome=Outcome.FAIL,
                        roi_name="recliner_pivot",
                        description=(
                            f"Recliner ROI is out-of-bounds or empty "
                            f"({recliner_roi_cfg.w}x{recliner_roi_cfg.h} at {recliner_roi_cfg.x},{recliner_roi_cfg.y})."
                        ),
                    )
                )
            else:
                measured_angle = MechanismVisionEngine.measure_recliner_angle(recliner_crop)
                measurements["recliner_angle_deg"] = measured_angle

                angle_d = evaluator.evaluate_check(
                    "mechanism",
                    "recliner_angle_deg",
                    measured_angle,
                    nominal=nom_recliner_deg,
                )
                angle_d.roi_name = "recliner_pivot"
                if angle_d.outcome != Outcome.PASS:
                    defects.append(angle_d)

                cv2.rectangle(annotated, (rx1, ry1), (rx2, ry2), (255, 200, 0), 2)
                cv2.putText(
                    annotated,
                    f"Angle: {measured_angle:.1f} deg",
                    (rx1, max(0, ry1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 200, 0),
                    2,
                )
        else:
            defects.append(
                DefectDetail(
                    defect_type="station.config",
                    outcome=Outcome.FAIL,
                    roi_name="recliner_pivot",
                    description="Missing 'recliner_pivot' ROI configuration in Station 4.",
                )
            )

        track_roi_cfg = self.config.regions_of_interest.get("track_travel")
        if track_roi_cfg is not None:
            tx1, ty1 = max(0, track_roi_cfg.x), max(0, track_roi_cfg.y)
            tx2 = min(image.shape[1], track_roi_cfg.x + track_roi_cfg.w)
            ty2 = min(image.shape[0], track_roi_cfg.y + track_roi_cfg.h)
            track_crop = image[ty1:ty2, tx1:tx2]

            if track_crop.size == 0:
                defects.append(
                    DefectDetail(
                        defect_type="station.invalid_roi",
                        outcome=Outcome.FAIL,
                        roi_name="track_travel",
                        description=(
                            f"Track travel ROI is out-of-bounds or empty "
                            f"({track_roi_cfg.w}x{track_roi_cfg.h} at {track_roi_cfg.x},{track_roi_cfg.y})."
                        ),
                    )
                )
            else:
                measured_pos = MechanismVisionEngine.measure_track_position_mm(
                    track_crop, pixel_size_mm=pixel_size_mm, reference_datum_x=0.0
                )
                measurements["track_end_position_mm"] = measured_pos

                pos_d = evaluator.evaluate_check(
                    "mechanism",
                    "track_end_position_mm",
                    measured_pos,
                    nominal=nom_track_pos_mm,
                )
                pos_d.roi_name = "track_travel"
                if pos_d.outcome != Outcome.PASS:
                    defects.append(pos_d)

                cv2.rectangle(annotated, (tx1, ty1), (tx2, ty2), (255, 200, 0), 2)
                cv2.putText(
                    annotated,
                    f"Track: {measured_pos:.1f} mm",
                    (tx1, max(0, ty1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 200, 0),
                    2,
                )
        else:
            defects.append(
                DefectDetail(
                    defect_type="station.config",
                    outcome=Outcome.FAIL,
                    roi_name="track_travel",
                    description="Missing 'track_travel' ROI configuration in Station 4.",
                )
            )

        # -------------------------------------------------------------
        # 2. Hardware Lock Sensor & Cycle Inputs (CRITICAL SAFETY RULE)
        # -------------------------------------------------------------
        if self.plc is not None:
            # 2a. Commanded position check on actuator
            actuator_pos = self.plc.read_actuator_position()
            measurements["actuator_position_mm"] = actuator_pos
            actuator_d = evaluator.evaluate_check(
                "mechanism",
                "track_end_position_mm",
                actuator_pos,
                nominal=nom_track_pos_mm,
            )
            if actuator_d.outcome != Outcome.PASS:
                actuator_d.defect_type = "mechanism.actuator_position_error"
                actuator_d.description = (
                    f"Actuator did not reach commanded position ({actuator_pos:.1f}mm vs {nom_track_pos_mm:.1f}mm)."
                )
                defects.append(actuator_d)

            # 2b. Torque / current threshold check
            torque = self.plc.read_lock_torque()
            min_torque = float(self.config.mechanism.get("min_lock_torque_nm", 15.0))
            measurements["lock_torque_nm"] = torque
            if torque < min_torque:
                defects.append(
                    DefectDetail(
                        defect_type="mechanism.insufficient_torque",
                        outcome=Outcome.FAIL,
                        measured_value=torque,
                        description=f"Lock torque {torque:.1f}Nm below required threshold {min_torque:.1f}Nm.",
                    )
                )

            # 2c. Slip-back check
            slip_back = self.plc.check_slip_back()
            max_slip = float(self.config.mechanism.get("max_slip_back_mm", 1.0))
            measurements["slip_back_mm"] = slip_back
            if slip_back > max_slip:
                defects.append(
                    DefectDetail(
                        defect_type="mechanism.slip_back_detected",
                        outcome=Outcome.FAIL,
                        measured_value=slip_back,
                        description=f"Actuator slipped back {slip_back:.2f}mm after lock engagement (limit {max_slip:.2f}mm).",
                    )
                )

        # 2d. Mechanical proximity lock sensor
        lock_confirmed = self.plc.is_mechanism_locked() if self.plc is not None else False
        measurements["lock_sensor_confirmed"] = 1.0 if lock_confirmed else 0.0

        lock_d = evaluator.evaluate_check(
            "mechanism", "lock_sensor_confirmed", lock_confirmed
        )
        lock_d.defect_type = "mechanism.lock_sensor_confirmed"
        if lock_d.outcome != Outcome.PASS:
            lock_d.description = (
                "Hardware mechanism lock confirmation sensor signal not asserted by PLC! "
                "CRITICAL: Sensor confirmation missing."
            )
            defects.append(lock_d)

        # -------------------------------------------------------------
        # 3. Cosmetics & Component Presence via AI Inference Engine
        # -------------------------------------------------------------
        if self.inference_engine is not None:
            detections = self.inference_engine.predict(image)
            for det in detections:
                if det.class_name in ("wrinkle", "puckering", "wrinkle_puckering"):
                    wrinkle_d = evaluator.evaluate_check("fit", "wrinkle_puckering", True)
                    wrinkle_d.defect_type = f"fit.{det.class_name}"
                    wrinkle_d.confidence = det.confidence
                    wrinkle_d.bounding_box = det.bounding_box
                    wrinkle_d.description = (
                        f"Cosmetic {det.class_name} detected (confidence: {det.confidence:.2f}). "
                        "Flagged for human review."
                    )
                    defects.append(wrinkle_d)

                elif det.class_name.startswith("missing_") or det.class_name in (
                    "missing_motor",
                    "missing_airbag",
                    "missing_sensor",
                    "unclicked_connector",
                ):
                    comp_d = DefectDetail(
                        defect_type=f"component.{det.class_name}",
                        outcome=Outcome.FAIL,
                        confidence=det.confidence,
                        bounding_box=det.bounding_box,
                        description=f"Critical component defect: {det.class_name}",
                    )
                    defects.append(comp_d)

                elif det.class_name in ("foam_showthrough", "short_cover"):
                    cosmetic_d = DefectDetail(
                        defect_type=f"cosmetic.{det.class_name}",
                        outcome=Outcome.FAIL,
                        confidence=det.confidence,
                        bounding_box=det.bounding_box,
                        description=f"Cosmetic assembly failure: {det.class_name}",
                    )
                    defects.append(cosmetic_d)

        return defects, measurements, annotated
