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
from camerainspection.vision.station1.surface_analysis import (
    LeatherDefectType,
    SurfaceAnalyzer,
    suppress_glare,
)

logger = get_logger("station.1")

# Defect types that map to cut_or_pinhole (fail_on_any)
_CUT_OR_PINHOLE_TYPES = {LeatherDefectType.CUT, LeatherDefectType.PINHOLE}


class Station1Service(BaseStation):
    """Station 1: Leather / Rexene panel surface inspection across multiple views."""

    # Maps camera view names → zone key used in measurements and required checks.
    # Single source of truth shared by get_required_measurements() and _analyze_surface_onnx().
    _VIEW_ZONE_MAP: dict[str, str] = {
        "front_cushion_backrest": "seating_face",
        "rear_back_map_pocket": "side_back",
        "main": "seating_face",
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        backend = getattr(self.config.model, "backend", "onnx")
        model_path = getattr(self.config.model, "weights_path", "models/station_1/model.onnx")

        # T4: Remove silent model file substitution. If the configured file is missing,
        # log an ERROR and leave the path/backend as-is so _get_onnx_engine() fails and
        # the existing "station.engine_unavailable" FAIL path triggers. Never switch to
        # a different file or to "classical" silently.
        mp = Path(model_path)
        if not mp.exists():
            logger.error(
                "Station 1: model file not found at '%s' — engine will be unavailable "
                "and every frame will produce station.engine_unavailable (FAIL).",
                model_path,
            )
            # Keep backend="onnx" and weights_path as configured so the lazy-load
            # attempt surfaces the FileNotFoundError through the normal fail-safe path.
            self.config.model.backend = "onnx"
            self.config.model.weights_path = str(model_path)
        elif backend != "classical":
            self.config.model.backend = "onnx"
            self.config.model.weights_path = str(model_path)
        else:
            self.config.model.backend = "classical"
            self.config.model.weights_path = str(model_path)

        # Threshold handling: explicit pass_below/fail_above win; 'threshold' is a fallback
        # for configs that only supply a single slider value.
        cfg_pass_below = getattr(self.config.model, "pass_below", None)
        cfg_fail_above = getattr(self.config.model, "fail_above", None)

        if cfg_pass_below is not None and cfg_fail_above is not None:
            # Explicit dual-threshold mode — use as-is
            self.config.model.pass_below = cfg_pass_below
            self.config.model.fail_above = cfg_fail_above
            logger.info(
                "Station 1: explicit pass_below=%.2f fail_above=%.2f",
                cfg_pass_below, cfg_fail_above,
            )
        else:
            # Fallback to single-threshold slider mode if explicit values absent
            threshold = getattr(self.config.model, "threshold", None)
            if threshold is not None:
                # Slider mode: derive PASS/REVIEW/FAIL bands with a fixed margin
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
                self.config.model.pass_below = 0.4
                self.config.model.fail_above = 0.6
                logger.info("Station 1: using default thresholds pass_below=0.40 fail_above=0.60")

        # Defect-type classifier for the PatchCore bbox crop.
        # Always force the heuristic path (model_path=None) even in ONNX mode:
        #  - The bbox is already confirmed anomalous by PatchCore, so the analyzer only
        #    classifies the defect type (scratch / pinhole / cut / stain).
        #  - The heuristic path respects the relaxed=True flag (dropping thresholds to
        #    ~33% so subtle defects inside the crop are not discarded).
        #  - SurfaceAnalyzer's own ONNX path uses ImageNet normalisation, which the model
        #    export docstring states is "confirmed broken"; it also ignores `relaxed`.
        analyzer_model_path = None
        enable_glare_filter = getattr(self.config.model, "enable_glare_filter", True)
        glare_lightness_threshold = getattr(self.config.model, "glare_lightness_threshold", 240)

        self._analyzer = SurfaceAnalyzer(
            model_path=analyzer_model_path,
            anomaly_threshold=self.config.model.pass_below,  # Use pass_below for consistency
            blur_ksize=101,
            diff_threshold=25,      # INCREASED from 12 for minimum contrast
            min_area_px=16,         # INCREASED from 4 to reduce noise
            max_area_px=200_000,
            min_contrast=25.0,      # INCREASED from 10.0 for grain suppression
            enable_glare_filter=enable_glare_filter,
            glare_lightness_threshold=glare_lightness_threshold,
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
        # T1: derive required keys from what the enabled cameras actually emit,
        # not from the station-level ROI dict which may contain zones no camera produces.
        # Use self.cameras (actual hardware) not self.config.cameras (config) because
        # integration tests may provide fewer cameras than the config specifies.
        if self.config.model.backend == "onnx":
            # ONNX path: each camera maps its view through _VIEW_ZONE_MAP → zone.defect_count
            zones: list[str] = []
            seen: set[str] = set()
            for cam_cfg in self.config.cameras:
                if not cam_cfg.enabled:
                    continue
                # Only require measurement if camera has hardware built
                if cam_cfg.name not in self.cameras:
                    continue
                zone = self._VIEW_ZONE_MAP.get(cam_cfg.view, cam_cfg.view)
                if zone not in seen:
                    zones.append(zone)
                    seen.add(zone)
            return [f"{z}.defect_count" for z in zones] if zones else ["seating_face.defect_count"]
        else:
            # Classical path: each camera contributes its own ROI names → zone.defect_count
            zones_cl: list[str] = []
            seen_cl: set[str] = set()
            for cam_cfg in self.config.cameras:
                if not cam_cfg.enabled:
                    continue
                # Only require measurement if camera has hardware built
                if cam_cfg.name not in self.cameras:
                    continue
                roi_names = list(cam.regions_of_interest.keys()) or list(self.config.regions_of_interest.keys())
                for roi in roi_names:
                    if roi not in seen_cl:
                        zones_cl.append(roi)
                        seen_cl.add(roi)
            return [f"{z}.defect_count" for z in zones_cl] if zones_cl else ["seating_face.defect_count"]

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

        # View-zone mapping for measurements — shared with get_required_measurements()
        zone_key = self._VIEW_ZONE_MAP.get(view, view)  # default to view name if not mapped

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
            working_image = image
            if getattr(self.config.model, "enable_glare_filter", True):
                working_image = suppress_glare(
                    image,
                    threshold=getattr(self.config.model, "glare_lightness_threshold", 240),
                )
            raw_detections: list[ModelDetection] = engine.predict(working_image)
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
            # Clean PASS — annotate with a green border and draw ROI outline (#11)
            h, w = image.shape[:2]
            cv2.rectangle(annotated, (2, 2), (w - 2, h - 2), (0, 200, 0), 2)
            cv2.putText(
                annotated,
                f"PASS (score {score:.3f} < {self.config.model.pass_below:.2f})",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2,
            )
            return defects, measurements, annotated

        # Fix #11: draw inspection ROI border in the ONNX path so operators can see
        # which region was inspected (the classical path already does this at line ~529).
        h_img, w_img = image.shape[:2]
        cv2.rectangle(annotated, (2, 2), (w_img - 2, h_img - 2), (200, 200, 0), 2)
        cv2.putText(
            annotated,
            f"{zone_key} ONNX  score:{score:.3f}",
            (6, 22),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 0), 1,
        )

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

            # Classify defect type.  Three layers, each one a fallback for the previous:
            #   1. Classical analyzer on the PatchCore bbox crop (most accurate)
            #   2. Bbox geometry heuristic (shape-based, no pixel data needed)
            #   3. Score-based heuristic (last resort — at least avoids "LEATHER_ANOMALY")
            dtype: LeatherDefectType | None = None
            primary_region = None
            classification_source: str = "layer3"  # T11: track which layer classified

            if bbox is not None:
                roi = image[
                    max(0, bbox.y):min(image.shape[0], bbox.y_max),
                    max(0, bbox.x):min(image.shape[1], bbox.x_max),
                ]
                if roi.size > 0:
                    regions = self._analyzer.analyze(roi, pixel_size_mm=pixel_size_mm, relaxed=True)
                    logger.debug(
                        "[classify] bbox=%dx%d  classical regions=%d",
                        bbox.w, bbox.h, len(regions),
                    )
                    for r in regions:
                        logger.debug(
                            "[classify]   %s aspect=%.2f score=%.3f",
                            r.defect_type.value, r.aspect_ratio, r.anomaly_score,
                        )

                    # Prefer specific defect types; treat shade_band and unknown as noise
                    specific = [
                        r for r in regions
                        if r.defect_type not in (LeatherDefectType.SHADE_BAND, LeatherDefectType.UNKNOWN)
                    ]
                    if specific:
                        primary_region = max(specific, key=lambda r: r.anomaly_score)
                        dtype = primary_region.defect_type
                        classification_source = "layer1"
                    elif regions:
                        # All regions are shade_band / unknown — still better than nothing
                        primary_region = max(regions, key=lambda r: r.anomaly_score)
                        if primary_region.defect_type not in (LeatherDefectType.SHADE_BAND, LeatherDefectType.UNKNOWN):
                            dtype = primary_region.defect_type
                            classification_source = "layer1"
                        # else fall through to geometry heuristic below

            # Layer 2: geometry heuristic using the PatchCore bbox shape
            if dtype is None and bbox is not None:
                bbox_aspect = max(bbox.w, bbox.h) / max(min(bbox.w, bbox.h), 1)
                bbox_area = bbox.w * bbox.h
                if bbox_area <= 2_000:
                    dtype = LeatherDefectType.PINHOLE
                elif bbox_aspect >= 4.0 and max(bbox.w, bbox.h) <= 300:
                    dtype = LeatherDefectType.SCRATCH
                elif bbox_aspect >= 2.5 and bbox.w * bbox.h <= 30_000:
                    dtype = LeatherDefectType.SCRATCH
                else:
                    dtype = LeatherDefectType.STAIN
                classification_source = "layer2"
                logger.debug(
                    "[classify] geometry fallback aspect=%.2f area=%d → %s",
                    bbox_aspect, bbox_area, dtype.value,
                )

            # Layer 3: score heuristic (no bbox at all — very rare)
            if dtype is None:
                score_for_hint = det.anomaly_score or 0.0
                dtype = LeatherDefectType.SCRATCH if score_for_hint > 0.7 else LeatherDefectType.STAIN
                classification_source = "layer3"
                logger.debug("[classify] score fallback score=%.3f → %s", score_for_hint, dtype.value)

            # T11: only report specific type + mm values when Layer 1 (real pixel measurement).
            # Layer 2/3 use geometry or score heuristics — label as unclassified to avoid
            # printing spurious mm values that have no pixel-measurement backing.
            if classification_source == "layer1":
                defect_type_name = dtype.value  # e.g. "scratch", "stain"
                display_name = " ".join(word.capitalize() for word in dtype.value.split("_"))
                if dtype == LeatherDefectType.SCRATCH:
                    length_mm = primary_region.length_px * pixel_size_mm  # type: ignore[union-attr]
                    defect_description = f"{display_name} ({length_mm:.1f}mm)"
                elif dtype == LeatherDefectType.STAIN:
                    area_mm2 = primary_region.area_px * (pixel_size_mm ** 2)  # type: ignore[union-attr]
                    defect_description = f"{display_name} ({area_mm2:.1f}mm²)"
                else:
                    defect_description = display_name
            else:
                # Layer 2 or 3: defect type classified from bbox geometry / anomaly distribution
                defect_type_name = dtype.value if dtype is not None else "defect"
                display_name = " ".join(word.capitalize() for word in defect_type_name.split("_"))
                if bbox is not None and pixel_size_mm > 0:
                    approx_mm = max(bbox.w, bbox.h) * pixel_size_mm
                    defect_description = f"{display_name} (~{approx_mm:.1f}mm)"
                elif bbox is not None:
                    defect_description = f"{display_name} [{bbox.w}x{bbox.h}px]"
                else:
                    defect_description = display_name

            # Draw annotation with prominent rectangle and clear label
            box_colour = (0, 0, 255) if outcome == Outcome.FAIL else (0, 165, 255)
            if bbox is not None:
                cv2.rectangle(
                    annotated,
                    (bbox.x, bbox.y), (bbox.x_max, bbox.y_max),
                    box_colour, 3,
                )
                cv2.putText(
                    annotated,
                    f"{defect_description} {det.confidence:.2f}",
                    (bbox.x, max(20, bbox.y - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_colour, 2,
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

                # Fix #10: annotate EVERY region, not only the best-scored one.
                # Previously only one bbox was drawn per defect type per zone, hiding
                # the others on the annotated image.
                for r_idx, reg in enumerate(group_regs):
                    rx_r, ry_r, rw_r, rh_r = reg.bbox_px
                    gx_r, gy_r = x1 + rx_r, y1 + ry_r
                    cv2.rectangle(annotated, (gx_r, gy_r), (gx_r + rw_r, gy_r + rh_r), box_color, 2)
                    # Label only the first (best-scored) region to avoid clutter; mark
                    # subsequent ones with a small index so they are identifiable.
                    if r_idx == 0:
                        cv2.putText(
                            annotated,
                            f"{display_name} ({count})",
                            (gx_r, max(0, gy_r - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,
                            box_color,
                            1,
                        )
                    else:
                        cv2.putText(
                            annotated,
                            f"+{r_idx}",
                            (gx_r, max(0, gy_r - 3)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.35,
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
