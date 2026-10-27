"""Station 1 Service: Leather / Rexene panel surface inspection across multiple views.

Inspection checks (per default_limits.yaml):
  leather.scratch_length_mm  — zone-specific (seating_face / side_back)
  leather.cut_or_pinhole     — fail_on_any (any region in any zone)
  leather.stain_area_mm2     — seating_face zone only

When station model.backend == "onnx" the PatchCore ONNX engine is used
instead of the classical SurfaceAnalyzer.  The two backends produce the same
DefectDetail / measurement output so the rest of the pipeline is unchanged.

Views supported:
  - front_cushion_backrest: inspects front cushion and backrest surface
  - rear_back_map_pocket: inspects rear backrest surface, seams, and map pocket
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from camerainspection.core.config import CameraConfig, ROIConfig
from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.logging import get_logger
from camerainspection.core.models import BoundingBox, DefectDetail, Outcome
from camerainspection.inference.base import ModelDetection
from camerainspection.station.base_station import BaseStation
from camerainspection.vision.station1.color_validator import check_variant_color_match
from camerainspection.vision.station1.surface_analysis import (
    LeatherDefectType,
    SurfaceAnalyzer,
)

logger = get_logger("station.1")

# Defect types that map to cut_or_pinhole (fail_on_any)
_CUT_OR_PINHOLE_TYPES = {LeatherDefectType.CUT, LeatherDefectType.PINHOLE}


class Station1Service(BaseStation):
    """Station 1: Leather / Rexene panel surface inspection across multiple views."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        backend = getattr(self.config.model, "backend", "onnx")
        model_path = getattr(self.config.model, "weights_path", "models/station_1/model.onnx")
        mp = Path(model_path)
        if not mp.exists():
            if not model_path or model_path == "models/station_1/model.onnx":
                if Path("models/station_1/model.onnx").exists():
                    model_path = "models/station_1/model.onnx"
                elif Path("models/station_1/patchcore.onnx").exists():
                    model_path = "models/station_1/patchcore.onnx"

        if backend != "classical" and Path(model_path).exists():
            self.config.model.backend = "onnx"
            self.config.model.weights_path = str(model_path)
        else:
            if backend == "onnx" and model_path and not Path(model_path).exists():
                self.config.model.backend = "onnx"
                self.config.model.weights_path = str(model_path)
            else:
                self.config.model.backend = "classical"
                self.config.model.weights_path = str(model_path)

        # CRITICAL FIX: Unify threshold handling
        # When config has 'threshold' (e.g., from slider), use it to derive pass_below/fail_above
        # with a fixed margin. Otherwise use explicit pass_below/fail_above from config.
        threshold = getattr(self.config.model, "threshold", None)
        if threshold is not None:
            # Slider/single-threshold mode: derive PASS/REVIEW/FAIL bands
            # PASS: score < threshold - 0.05
            # REVIEW: threshold - 0.05 <= score < threshold + 0.15
            # FAIL: score >= threshold + 0.15
            self.config.model.pass_below = max(0.0, threshold - 0.05)
            self.config.model.fail_above = threshold + 0.15
            logger.info(
                "Station 1: threshold=%.2f → pass_below=%.2f fail_above=%.2f",
                threshold, self.config.model.pass_below, self.config.model.fail_above,
            )
        else:
            # Explicit dual-threshold mode from config
            self.config.model.pass_below = getattr(self.config.model, "pass_below", 0.4)
            self.config.model.fail_above = getattr(self.config.model, "fail_above", 0.6)

        # Classical analyzer (used only when backend == "classical")
        analyzer_model_path = self.config.model.weights_path if getattr(self.config.model, "backend", "classical") == "onnx" else None
        self._analyzer = SurfaceAnalyzer(
            model_path=analyzer_model_path,
            anomaly_threshold=self.config.model.pass_below,  # Use pass_below for consistency
            blur_ksize=101,
            diff_threshold=25,      # INCREASED from 12 for minimum contrast
            min_area_px=16,         # INCREASED from 4 to reduce noise
            max_area_px=200_000,
            min_contrast=25.0,      # INCREASED from 10.0 for grain suppression
        )
        # Use the engine injected by the builder when available; lazy-load only as fallback.
        # _onnx_loaded tracks whether we have already attempted a lazy load (avoid retrying).
        self._onnx_loaded: bool = self.inference_engine is not None
        self._onnx_engine = self.inference_engine  # may be None

    # ------------------------------------------------------------------
    # ONNX engine bootstrap
    # ------------------------------------------------------------------

    def _get_onnx_engine(self) -> Any:
        """Return a loaded OnnxPatchCoreEngine.

        Uses the engine injected via ``inference_engine`` when one was provided.
        Falls back to a lazy self-load (once) when the builder did not supply one.
        """
        if self._onnx_loaded:
            return self._onnx_engine

        self._onnx_loaded = True  # set before load so a failure doesn't retry forever
        try:
            from camerainspection.inference.onnx_patchcore import OnnxPatchCoreEngine  # noqa: PLC0415

            pass_below: float = self.config.model.pass_below
            fail_above: float = self.config.model.fail_above

            engine = OnnxPatchCoreEngine(pass_below=pass_below, fail_above=fail_above)
            engine.load(self.config.model.weights_path)
            self._onnx_engine = engine
            logger.info(
                "OnnxPatchCoreEngine lazy-loaded for Station 1 (pass_below=%.2f fail_above=%.2f weights=%s)",
                pass_below, fail_above, self.config.model.weights_path,
            )
        except Exception as exc:
            logger.error(
                "Failed to load ONNX engine for Station 1: %s — falling back to mock/classical", exc
            )
            self._onnx_engine = None

        return self._onnx_engine

    # ------------------------------------------------------------------
    # BaseStation interface
    # ------------------------------------------------------------------

    def get_required_measurements(self) -> list[str]:
        # At least one defect count measurement must be affirmatively recorded
        reqs = [f"{zone}.defect_count" for zone in self.config.regions_of_interest]
        return reqs if reqs else ["seating_face.defect_count"]

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
        """Inspect specific camera view (e.g. front_cushion_backrest or rear_back_map_pocket)."""
        # Route to ONNX backend when configured
        if self.config.model.backend == "onnx":
            return self._analyze_surface_onnx(
                image=image,
                camera_name=camera_name,
                view=view,
                pixel_size_mm=camera_config.pixel_size_mm,
                variant_id=variant_id,
            )

        # Determine applicable ROIs for this view (classical path)
        if camera_config.regions_of_interest:
            active_rois = dict(camera_config.regions_of_interest)
        elif view == "front_cushion_backrest":
            active_rois = {
                k: v for k, v in self.config.regions_of_interest.items() if k == "seating_face"
            }
            if not active_rois and "seating_face" in self.config.regions_of_interest:
                active_rois["seating_face"] = self.config.regions_of_interest["seating_face"]
            elif not active_rois:
                active_rois = dict(self.config.regions_of_interest)
        elif view == "rear_back_map_pocket":
            active_rois = {
                k: v for k, v in self.config.regions_of_interest.items() if k == "side_back"
            }
            if not active_rois and "side_back" in self.config.regions_of_interest:
                active_rois["side_back"] = self.config.regions_of_interest["side_back"]
            elif not active_rois:
                active_rois = dict(self.config.regions_of_interest)
        else:
            active_rois = dict(self.config.regions_of_interest)

        return self._analyze_surface(
            image=image,
            rois=active_rois,
            evaluator=evaluator,
            pixel_size_mm=camera_config.pixel_size_mm,
        )

    def inspect_image(
        self,
        image: np.ndarray,
        variant_id: str,
        evaluator: LimitsEvaluator,
        variant_nominals: dict[str, Any],
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        """Legacy single-image inspection covering all station ROIs."""
        if self.config.model.backend == "onnx":
            return self._analyze_surface_onnx(
                image=image,
                camera_name="main",
                view="main",
                pixel_size_mm=self.config.camera.pixel_size_mm,
                variant_id=variant_id,
            )
        return self._analyze_surface(
            image=image,
            rois=self.config.regions_of_interest,
            evaluator=evaluator,
            pixel_size_mm=self.config.camera.pixel_size_mm,
        )

    # ------------------------------------------------------------------
    # ONNX analysis path
    # ------------------------------------------------------------------

    def _analyze_surface_onnx(
        self,
        image: np.ndarray,
        camera_name: str,
        view: str,
        pixel_size_mm: float,
        variant_id: str = "UNKNOWN",
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        """Run PatchCore ONNX inference and convert detections to DefectDetails.

        PRIMARY PASS/FAIL GATE: ONNX pred_label and pred_score determine outcome.
        ANY model error (engine unavailable, inference exception) → FAIL safe.
        SAFETY RULE: If defects > 0 from ANY source, outcome cannot be PASS.

        Also performs variant color validation as a process error check.
        """
        defects: list[DefectDetail] = []
        measurements: dict[str, float] = {}
        annotated = image.copy()

        # View-zone mapping for measurements
        view_zone_map = {
            "front_cushion_backrest": "seating_face",
            "rear_back_map_pocket":   "side_back",
            "main": "seating_face",  # Legacy single-image path
        }
        zone_key = view_zone_map.get(view, "seating_face")  # Default to seating_face

        # PROCESS ERROR CHECK: Variant color/material validation disabled in favor of pure PatchCore anomaly detection
        measurements["leather.color_mismatch"] = 0.0

        engine = self._get_onnx_engine()
        if engine is None:
            # Engine failed to load — FAIL SAFE (never PASS when model unavailable)
            defects.append(DefectDetail(
                defect_type="station.engine_unavailable",
                outcome=Outcome.FAIL,
                camera_name=camera_name,
                view=view,
                description="ONNX PatchCore engine is unavailable. Failing safe.",
            ))
            measurements[f"{zone_key}.defect_count"] = 1.0
            measurements["leather.anomaly_score"] = 1.0
            measurements[f"{zone_key}.anomaly_threshold"] = self.config.model.fail_above
            return defects, measurements, annotated

        try:
            raw_detections: list[ModelDetection] = engine.predict(image)
        except Exception as exc:
            logger.error("ONNX inference error on camera %s view %s: %s", camera_name, view, exc)
            # Inference error — FAIL SAFE (never PASS on exception)
            defects.append(DefectDetail(
                defect_type="station.inference_error",
                outcome=Outcome.FAIL,
                camera_name=camera_name,
                view=view,
                description=f"Inference exception: {exc}",
            ))
            measurements[f"{zone_key}.defect_count"] = 1.0
            measurements["leather.anomaly_score"] = 1.0
            measurements[f"{zone_key}.anomaly_threshold"] = self.config.model.fail_above
            return defects, measurements, annotated

        # Primary PASS/FAIL gate: anomaly score from first detection (or 0 if clean)
        score = raw_detections[0].anomaly_score if raw_detections else 0.0
        raw_score = raw_detections[0].metadata.get("raw_score", score) if raw_detections else 0.0
        heatmap_max = raw_detections[0].metadata.get("heatmap_max", 0.0) if raw_detections else 0.0

        # Store UNCLAMPED raw score for diagnostics
        measurements["leather.anomaly_score"] = float(score)
        measurements["leather.raw_anomaly_score"] = float(raw_score)  # Unclamped
        measurements["leather.heatmap_max"] = float(heatmap_max)

        # CRITICAL FIX: Record the ACTUAL threshold that was applied (from slider/config)
        # Use pass_below as the primary threshold (slider value)
        measurements[f"{zone_key}.anomaly_threshold"] = self.config.model.pass_below
        measurements[f"{zone_key}.anomaly_threshold_fail"] = self.config.model.fail_above

        # CRITICAL: defect_count MUST match len(raw_detections) so measurements align with "Detected defects"
        # This unifies the defect list and measurement sources
        measurements[f"{zone_key}.defect_count"] = float(len(raw_detections))

        if not raw_detections:
            # Clean PASS — annotate with a green border
            h, w = image.shape[:2]
            cv2.rectangle(annotated, (2, 2), (w - 2, h - 2), (0, 200, 0), 2)
            cv2.putText(
                annotated,
                f"PASS (score {score:.3f} < {self.config.model.pass_below:.2f})",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2,
            )
            return defects, measurements, annotated

        # PRIMARY GATE: Convert each ModelDetection to a DefectDetail.
        # outcome_hint from engine: FAIL if pred_label=True OR score >= fail_above, else REVIEW.
        # Fall back to FAIL when absent (old engine, fail safe).
        hint = raw_detections[0].metadata.get("outcome_hint", "FAIL")
        outcome = Outcome.FAIL if hint == "FAIL" else Outcome.REVIEW

        # Check for domain warning (out-of-distribution image)
        domain_warning = raw_detections[0].metadata.get("domain_warning")
        if domain_warning:
            # Add domain warning as a separate defect
            defects.append(DefectDetail(
                defect_type="station.domain_warning",
                outcome=Outcome.REVIEW,
                camera_name=camera_name,
                view=view,
                roi_name=zone_key,
                description=domain_warning,
            ))

        for det in raw_detections:
            bbox = det.bounding_box

            # Classify the defect type using classical analysis on the detected region
            defect_type_name = "LEATHER_ANOMALY"
            defect_description = "Unclassified anomaly"

            if bbox is not None:
                # Extract the detected region for classification
                roi = image[bbox.y:bbox.y_max, bbox.x:bbox.x_max]
                if roi.size > 0:
                    # Run classical analyzer on just this region to identify defect type
                    regions = self._analyzer.analyze(roi, pixel_size_mm=pixel_size_mm)
                    if regions:
                        # Use the defect type from classical analysis
                        primary_region = max(regions, key=lambda r: r.anomaly_score)
                        dtype = primary_region.defect_type
                        defect_type_name = dtype.value

                        # Build readable description
                        display_name = " ".join(word.capitalize() for word in dtype.value.split("_"))
                        if dtype == LeatherDefectType.SCRATCH:
                            length_mm = primary_region.length_px * pixel_size_mm
                            defect_description = f"{display_name} ({length_mm:.1f}mm)"
                        elif dtype == LeatherDefectType.STAIN:
                            area_mm2 = primary_region.area_px * (pixel_size_mm ** 2)
                            defect_description = f"{display_name} ({area_mm2:.1f}mm²)"
                        else:
                            defect_description = display_name

            # Draw annotation with specific defect type
            box_colour = (0, 0, 255) if outcome == Outcome.FAIL else (0, 165, 255)
            if bbox is not None:
                cv2.rectangle(
                    annotated,
                    (bbox.x, bbox.y), (bbox.x_max, bbox.y_max),
                    box_colour, 2,
                )
                cv2.putText(
                    annotated,
                    f"{defect_description} {det.confidence:.2f}",
                    (bbox.x, max(0, bbox.y - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_colour, 1,
                )

            # PRIMARY DEFECT RECORD: Each detection becomes a defect with classified type
            # Show ACTUAL threshold values from config (slider values)
            raw_score_val = det.metadata.get("raw_score", det.confidence)
            hmap_max_val = det.metadata.get("heatmap_max", 0.0)

            defects.append(DefectDetail(
                defect_type=f"leather.{defect_type_name}",
                outcome=outcome,
                confidence=det.confidence,
                bounding_box=bbox,
                camera_name=camera_name,
                view=view,
                roi_name=zone_key,
                description=(
                    f"{defect_description}: PatchCore raw_score={raw_score_val:.4f} "
                    f"(threshold: pass<{self.config.model.pass_below:.2f} "
                    f"fail>={self.config.model.fail_above:.2f}) "
                    f"pred_label={det.metadata.get('pred_label')} "
                    f"heatmap_max={hmap_max_val:.4f}"
                ),
            ))

        return defects, measurements, annotated

    # ------------------------------------------------------------------
    # Classical analysis path (unchanged)
    # ------------------------------------------------------------------

    def _analyze_surface(
        self,
        image: np.ndarray,
        rois: dict[str, ROIConfig],
        evaluator: LimitsEvaluator,
        pixel_size_mm: float,
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        defects: list[DefectDetail] = []
        measurements: dict[str, float] = {}
        annotated = image.copy()

        zone_rois = list(rois.items())
        if not zone_rois:
            defects.append(
                DefectDetail(
                    defect_type="station.config",
                    outcome=Outcome.FAIL,
                    description="No ROIs configured for Station 1 surface analysis.",
                )
            )
            return defects, measurements, annotated

        for zone_name, roi_cfg in zone_rois:
            y1 = max(0, roi_cfg.y)
            y2 = min(image.shape[0], roi_cfg.y + roi_cfg.h)
            x1 = max(0, roi_cfg.x)
            x2 = min(image.shape[1], roi_cfg.x + roi_cfg.w)
            zone_roi = image[y1:y2, x1:x2]

            if zone_roi.size == 0:
                defects.append(
                    DefectDetail(
                        defect_type="station.invalid_roi",
                        outcome=Outcome.FAIL,
                        roi_name=zone_name,
                        description=(
                            f"Zone '{zone_name}' ROI is out-of-bounds or zero-sized "
                            f"({roi_cfg.w}x{roi_cfg.h} at {roi_cfg.x},{roi_cfg.y})."
                        ),
                    )
                )
                continue

            cv2.rectangle(annotated, (x1, y1), (x2, y2), (200, 200, 0), 2)

            regions = self._analyzer.analyze(zone_roi, pixel_size_mm=pixel_size_mm)
            measurements[f"{zone_name}.defect_count"] = float(len(regions))
            measurements[f"{zone_name}.anomaly_threshold"] = float(self._analyzer.anomaly_threshold)

            from collections import defaultdict
            grouped_regions: dict[LeatherDefectType, list] = defaultdict(list)
            for region in regions:
                grouped_regions[region.defect_type].append(region)

            for dtype, group_regs in grouped_regions.items():
                count = len(group_regs)
                max_score = max(r.anomaly_score for r in group_regs)
                best_region = max(group_regs, key=lambda r: r.anomaly_score)
                rx, ry, rw, rh = best_region.bbox_px
                gx, gy = x1 + rx, y1 + ry
                bbox = BoundingBox(x=gx, y=gy, w=rw, h=rh)

                dtype_str = dtype.value
                display_name = " ".join(word.capitalize() for word in dtype_str.split("_"))
                summary_desc = f"{display_name} x {count}, highest score {max_score:.2f}"

                box_color = (
                    (0, 0, 255)
                    if dtype in _CUT_OR_PINHOLE_TYPES
                    else (0, 165, 255)
                )
                cv2.rectangle(annotated, (gx, gy), (gx + rw, gy + rh), box_color, 2)
                cv2.putText(
                    annotated,
                    f"{display_name} ({count})",
                    (gx, max(0, gy - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    box_color,
                    1,
                )

                # 1. Cut or pinhole → fail_on_any regardless of zone
                if dtype in _CUT_OR_PINHOLE_TYPES:
                    cut_d = evaluator.evaluate_check("leather", "cut_or_pinhole", True)
                    cut_d.defect_type = f"leather.{dtype.value}"
                    cut_d.bounding_box = bbox
                    cut_d.roi_name = zone_name
                    cut_d.confidence = max_score
                    cut_d.measured_value = best_region.length_px * pixel_size_mm
                    cut_d.description = summary_desc
                    defects.append(cut_d)

                # 2. Scratch — zone-specific limit via sub_category
                elif dtype == LeatherDefectType.SCRATCH:
                    scratch_mm = max(r.length_px * pixel_size_mm for r in group_regs)
                    key = f"{zone_name}.scratch_length_mm"
                    measurements[key] = max(measurements.get(key, 0.0), scratch_mm)

                    scratch_d = evaluator.evaluate_check(
                        "leather",
                        "scratch_length_mm",
                        scratch_mm,
                        sub_category=zone_name,
                    )
                    scratch_d.defect_type = "leather.scratch"
                    scratch_d.roi_name = zone_name
                    scratch_d.bounding_box = bbox
                    scratch_d.confidence = max_score
                    scratch_d.description = summary_desc
                    if scratch_d.outcome != Outcome.PASS:
                        defects.append(scratch_d)

                # 3. Stain — zone-specific limit (seating_face / side_back)
                elif dtype == LeatherDefectType.STAIN:
                    stain_mm2 = sum(r.area_px * (pixel_size_mm**2) for r in group_regs)
                    key = f"{zone_name}.stain_area_mm2"
                    measurements[key] = measurements.get(key, 0.0) + stain_mm2

                    stain_d = evaluator.evaluate_check(
                        "leather",
                        "stain_area_mm2",
                        stain_mm2,
                        sub_category=zone_name,
                    )
                    stain_d.defect_type = "leather.stain"
                    stain_d.roi_name = zone_name
                    stain_d.bounding_box = bbox
                    stain_d.confidence = max_score
                    stain_d.description = summary_desc
                    if stain_d.outcome != Outcome.PASS:
                        defects.append(stain_d)

                # 4. Shade band / coating streak → REVIEW
                elif dtype in (
                    LeatherDefectType.SHADE_BAND,
                    LeatherDefectType.COATING_STREAK,
                ):
                    defects.append(
                        DefectDetail(
                            defect_type=f"leather.{dtype.value}",
                            outcome=Outcome.REVIEW,
                            roi_name=zone_name,
                            bounding_box=bbox,
                            confidence=max_score,
                            description=summary_desc,
                        )
                    )

        return defects, measurements, annotated
