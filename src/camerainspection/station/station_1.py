"""Station 1 Service: Leather / Rexene panel surface inspection.

Inspection checks (per default_limits.yaml):
  leather.scratch_length_mm  — zone-specific (seating_face / side_back)
  leather.cut_or_pinhole     — fail_on_any (any region in any zone)
  leather.stain_area_mm2     — seating_face zone only

Zone logic:
  Each ROI from config is treated as either "seating_face" or "side_back".
  LimitsEvaluator.evaluate_check accepts `sub_category` for nested zone limits.
  Example: evaluate_check("leather", "scratch_length_mm", value,
                           sub_category="seating_face")
  resolves to limits["leather"]["scratch_length_mm"]["seating_face"]
  → {"pass_max": 0.0, "fail_at": 2.0}

Thread-safe: SurfaceAnalyzer is instantiated once per Station1Service.
"""

from __future__ import annotations

from typing import Any
import cv2
import numpy as np

from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.logging import get_logger
from camerainspection.core.models import BoundingBox, DefectDetail, Outcome
from camerainspection.station.base_station import BaseStation
from camerainspection.vision.station1.surface_analysis import (
    LeatherDefectType,
    SurfaceAnalyzer,
)

logger = get_logger("station.1")

# Defect types that map to cut_or_pinhole (fail_on_any)
_CUT_OR_PINHOLE_TYPES = {LeatherDefectType.CUT, LeatherDefectType.PINHOLE}


class Station1Service(BaseStation):
    """Station 1: Leather / Rexene panel surface inspection.

    Surface analysis uses `SurfaceAnalyzer` (local contrast anomaly detection).
    In production the same interface is fulfilled by an Anomalib PatchCore model
    compiled to ONNX; switching is controlled by the station config backend field.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._analyzer = SurfaceAnalyzer(
            blur_ksize=51,
            diff_threshold=14,
            min_area_px=4,
            max_area_px=200_000,
        )

    def inspect_image(
        self,
        image: np.ndarray,
        variant_id: str,
        evaluator: LimitsEvaluator,
        variant_nominals: dict[str, Any],
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        defects: list[DefectDetail] = []
        measurements: dict[str, float] = {}
        annotated = image.copy()
        pixel_size_mm: float = self.config.camera.pixel_size_mm

        zone_rois = list(self.config.regions_of_interest.items())
        if not zone_rois:
            defects.append(DefectDetail(
                defect_type="station.config",
                outcome=Outcome.FAIL,
                description="No ROIs configured for Station 1.",
            ))
            return defects, measurements, annotated

        for zone_name, roi_cfg in zone_rois:
            y1 = max(0, roi_cfg.y)
            y2 = min(image.shape[0], roi_cfg.y + roi_cfg.h)
            x1 = max(0, roi_cfg.x)
            x2 = min(image.shape[1], roi_cfg.x + roi_cfg.w)
            zone_roi = image[y1:y2, x1:x2]

            if zone_roi.size == 0:
                defects.append(DefectDetail(
                    defect_type="station.invalid_roi",
                    outcome=Outcome.FAIL,
                    roi_name=zone_name,
                    description=f"Zone '{zone_name}' ROI is out-of-bounds or zero-sized ({roi_cfg.w}x{roi_cfg.h} at {roi_cfg.x},{roi_cfg.y}).",
                ))
                continue

            # Draw zone boundary on annotated image
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (200, 200, 0), 2)

            regions = self._analyzer.analyze(zone_roi)
            measurements[f"{zone_name}.defect_count"] = float(len(regions))

            for region in regions:
                rx, ry, rw, rh = region.bbox_px
                # Convert to global image coords
                gx, gy = x1 + rx, y1 + ry
                bbox = BoundingBox(x=gx, y=gy, w=rw, h=rh)

                # Annotate detected defect
                box_color = (0, 0, 255) if region.defect_type in _CUT_OR_PINHOLE_TYPES else (0, 165, 255)
                cv2.rectangle(annotated, (gx, gy), (gx + rw, gy + rh), box_color, 2)
                cv2.putText(
                    annotated, region.defect_type.value,
                    (gx, max(0, gy - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 1,
                )

                # ---- Limit checks ----

                # 1. Cut or pinhole → fail_on_any regardless of zone
                if region.defect_type in _CUT_OR_PINHOLE_TYPES:
                    cut_d = evaluator.evaluate_check("leather", "cut_or_pinhole", True)
                    cut_d.defect_type = f"leather.{region.defect_type.value}"
                    cut_d.bounding_box = bbox
                    cut_d.roi_name = zone_name
                    cut_d.confidence = region.anomaly_score
                    cut_d.measured_value = region.length_px * pixel_size_mm
                    cut_d.description = (
                        f"{region.defect_type.value} in zone '{zone_name}', "
                        f"length {region.length_px * pixel_size_mm:.2f}mm"
                    )
                    defects.append(cut_d)

                # 2. Scratch — zone-specific limit via sub_category
                elif region.defect_type == LeatherDefectType.SCRATCH:
                    scratch_mm = region.length_px * pixel_size_mm
                    key = f"{zone_name}.scratch_length_mm"
                    measurements[key] = max(measurements.get(key, 0.0), scratch_mm)

                    scratch_d = evaluator.evaluate_check(
                        "leather", "scratch_length_mm", scratch_mm,
                        sub_category=zone_name,
                    )
                    scratch_d.defect_type = "leather.scratch"
                    scratch_d.roi_name = zone_name
                    scratch_d.bounding_box = bbox
                    scratch_d.confidence = region.anomaly_score
                    if scratch_d.outcome != Outcome.PASS:
                        defects.append(scratch_d)

                # 3. Stain — zone-specific limit (seating_face only; side_back has no stain limit)
                elif region.defect_type == LeatherDefectType.STAIN:
                    stain_mm2 = region.area_px * (pixel_size_mm ** 2)
                    key = f"{zone_name}.stain_area_mm2"
                    measurements[key] = measurements.get(key, 0.0) + stain_mm2

                    stain_d = evaluator.evaluate_check(
                        "leather", "stain_area_mm2", stain_mm2,
                        sub_category=zone_name,
                    )
                    stain_d.defect_type = "leather.stain"
                    stain_d.roi_name = zone_name
                    stain_d.bounding_box = bbox
                    stain_d.confidence = region.anomaly_score
                    if stain_d.outcome != Outcome.PASS:
                        defects.append(stain_d)

                # 4. Shade band / coating streak → REVIEW (no numeric OEM limit yet)
                elif region.defect_type in (
                    LeatherDefectType.SHADE_BAND, LeatherDefectType.COATING_STREAK
                ):
                    defects.append(DefectDetail(
                        defect_type=f"leather.{region.defect_type.value}",
                        outcome=Outcome.REVIEW,
                        roi_name=zone_name,
                        bounding_box=bbox,
                        confidence=region.anomaly_score,
                        description=(
                            f"{region.defect_type.value} in zone '{zone_name}' "
                            f"(area {region.area_px:.0f}px²). Flagged for human review."
                        ),
                    ))

        return defects, measurements, annotated
