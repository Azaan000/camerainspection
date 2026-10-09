"""Station 2 Service: Stitching inspection across bolster, headrest, and arm views."""

from __future__ import annotations

from typing import Any
import cv2
import numpy as np

from camerainspection.core.config import CameraConfig
from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.logging import get_logger
from camerainspection.core.models import BoundingBox, DefectDetail, Outcome
from camerainspection.station.base_station import BaseStation
from camerainspection.vision.station2.stitch_geometry import StitchGeometryEngine
from camerainspection.vision.station2.thread_color import ThreadColorEngine, _NO_REFERENCE_SENTINEL

logger = get_logger("station.2")


class Station2Service(BaseStation):
    """Station 2: Stitching inspection on sewing jig across multiple camera views.

    Supported views:
      - left_bolster: left bolster stitch line and surface
      - right_bolster: right bolster stitch line and surface
      - headrest: headrest position, surface, and seams
      - seam_arm: robot-arm camera scanning bolster stitch line
    """

    def get_required_measurements(self) -> list[str]:
        return ["spi", "max_skip_mm", "seam_position_mm", "stitch_count"]

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
        """Inspect specific stitching view (bolsters, headrest, or arm scan)."""
        # Look for seam ROI in camera-specific ROIs first, then station fallback
        roi_cfg = (
            camera_config.regions_of_interest.get("main_seam")
            or camera_config.regions_of_interest.get(f"{view}_seam")
            or next(iter(camera_config.regions_of_interest.values()), None)
            or self.config.regions_of_interest.get("main_seam")
        )
        pixel_size = camera_config.pixel_size_mm or self.config.camera.pixel_size_mm
        return self._inspect_seam(
            image=image,
            seam_roi_cfg=roi_cfg,
            pixel_size_mm=pixel_size,
            variant_nominals=variant_nominals,
            evaluator=evaluator,
            camera_name=camera_name,
        )

    def inspect_image(
        self,
        image: np.ndarray,
        variant_id: str,
        evaluator: LimitsEvaluator,
        variant_nominals: dict[str, Any],
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        """Legacy single-image inspection covering main seam."""
        roi_cfg = self.config.regions_of_interest.get("main_seam")
        return self._inspect_seam(
            image=image,
            seam_roi_cfg=roi_cfg,
            pixel_size_mm=self.config.camera.pixel_size_mm,
            variant_nominals=variant_nominals,
            evaluator=evaluator,
            camera_name="main",
        )

    def _inspect_seam(
        self,
        image: np.ndarray,
        seam_roi_cfg: Any,
        pixel_size_mm: float,
        variant_nominals: dict[str, Any],
        evaluator: LimitsEvaluator,
        camera_name: str,
    ) -> tuple[list[DefectDetail], dict[str, float], np.ndarray | None]:
        defects: list[DefectDetail] = []
        measurements: dict[str, float] = {}
        annotated = image.copy()

        # Pull stitch nominals from variant config
        nominal_spi: float = float(
            variant_nominals.get("stitch", {}).get("stitches_per_inch", 6.0)
        )

        # Thread color reference
        thread_ref_raw = variant_nominals.get("stitch", {}).get("thread_color_bgr")
        thread_ref_bgr: np.ndarray | None = None
        if thread_ref_raw is not None:
            arr = np.array(thread_ref_raw, dtype=np.uint8).reshape(1, 1, 3)
            thread_ref_bgr = arr

        # 1. Extract main seam ROI
        if seam_roi_cfg is None:
            defects.append(
                DefectDetail(
                    defect_type="station.config",
                    outcome=Outcome.FAIL,
                    description=f"No seam ROI configured for Station 2 view '{camera_name}'.",
                )
            )
            return defects, measurements, annotated

        y1 = max(0, seam_roi_cfg.y)
        y2 = min(image.shape[0], seam_roi_cfg.y + seam_roi_cfg.h)
        x1 = max(0, seam_roi_cfg.x)
        x2 = min(image.shape[1], seam_roi_cfg.x + seam_roi_cfg.w)
        seam_roi = image[y1:y2, x1:x2]
        if seam_roi.size == 0:
            defects.append(
                DefectDetail(
                    defect_type="station.invalid_roi",
                    outcome=Outcome.FAIL,
                    roi_name="main_seam",
                    description=(
                        f"Seam ROI is out-of-bounds or zero-sized "
                        f"({seam_roi_cfg.w}x{seam_roi_cfg.h} at {seam_roi_cfg.x},{seam_roi_cfg.y})."
                    ),
                )
            )
            return defects, measurements, annotated

        # Style line is the centre of the ROI height
        style_line_y_px = float(seam_roi.shape[0] / 2)

        # 2. Geometry measurement
        meas = StitchGeometryEngine.analyze_seam(
            seam_roi=seam_roi,
            pixel_size_mm=pixel_size_mm,
            reference_style_line_y=style_line_y_px,
        )
        measurements["spi"] = meas.stitches_per_inch
        measurements["mean_pitch_mm"] = meas.mean_pitch_mm
        measurements["max_skip_mm"] = meas.max_skip_length_mm
        measurements["seam_position_mm"] = meas.seam_position_mm
        measurements["stitch_count"] = float(meas.stitch_count)

        # Annotate seam ROI border
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 255, 0), 2)
        cv2.putText(
            annotated,
            f"SPI:{meas.stitches_per_inch:.1f}  skip:{meas.max_skip_length_mm:.2f}mm",
            (x1, max(0, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 0),
            2,
        )

        # 3. Rule-based limit checks
        skip_d = evaluator.evaluate_check("stitch", "skip_length_mm", meas.max_skip_length_mm)
        skip_d.roi_name = "main_seam"
        if skip_d.outcome != Outcome.PASS:
            defects.append(skip_d)

        spi_d = evaluator.evaluate_check(
            "stitch", "stitches_per_inch", meas.stitches_per_inch, nominal=nominal_spi
        )
        spi_d.roi_name = "main_seam"
        if spi_d.outcome != Outcome.PASS:
            defects.append(spi_d)

        seam_pos_d = evaluator.evaluate_check(
            "stitch", "seam_position_mm", meas.seam_position_mm, nominal=0.0
        )
        seam_pos_d.roi_name = "main_seam"
        if seam_pos_d.outcome != Outcome.PASS:
            defects.append(seam_pos_d)

        if meas.has_double_seam:
            defects.append(
                DefectDetail(
                    defect_type="stitch.double_seam",
                    outcome=Outcome.FAIL,
                    roi_name="main_seam",
                    description="Double seam detected (bimodal Y distribution).",
                )
            )

        # 4. Thread color check
        thread_de = ThreadColorEngine.compute_thread_delta_e(
            seam_roi=seam_roi,
            stitch_centers=meas.stitch_centers,
            reference_bgr=thread_ref_bgr,
        )
        if thread_de != _NO_REFERENCE_SENTINEL:
            measurements["thread_color_delta_e"] = thread_de
            color_d = evaluator.evaluate_check("stitch", "thread_color_delta_e", thread_de)
            color_d.defect_type = "stitch.thread_color"
            color_d.roi_name = "main_seam"
            if color_d.outcome != Outcome.PASS:
                defects.append(color_d)

        # 5. AI model — broken thread and loose end
        if self.inference_engine is not None:
            ai_dets = self.inference_engine.predict(seam_roi)
            for det in ai_dets:
                if det.class_name == "broken_thread":
                    broken_d = evaluator.evaluate_check("stitch", "broken_thread", True)
                    broken_d.defect_type = "stitch.broken_thread"
                    broken_d.confidence = det.confidence
                    if det.bounding_box:
                        broken_d.bounding_box = BoundingBox(
                            x=det.bounding_box.x + x1,
                            y=det.bounding_box.y + y1,
                            w=det.bounding_box.w,
                            h=det.bounding_box.h,
                        )
                    broken_d.roi_name = "main_seam"
                    broken_d.description = (
                        f"AI detected broken thread with confidence {det.confidence:.2f}"
                    )
                    defects.append(broken_d)
                    if det.bounding_box:
                        bx, by = det.bounding_box.x + x1, det.bounding_box.y + y1
                        cv2.rectangle(
                            annotated,
                            (bx, by),
                            (bx + det.bounding_box.w, by + det.bounding_box.h),
                            (0, 0, 255),
                            3,
                        )
                        cv2.putText(
                            annotated,
                            "BROKEN THREAD",
                            (bx, max(0, by - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 0, 255),
                            2,
                        )

                elif det.class_name == "loose_end":
                    loose_mm = (det.bounding_box.w * pixel_size_mm) if det.bounding_box else 0.0
                    measurements["loose_end_mm"] = loose_mm
                    loose_d = evaluator.evaluate_check("stitch", "loose_end_mm", loose_mm)
                    loose_d.defect_type = "stitch.loose_end"
                    loose_d.confidence = det.confidence
                    if det.bounding_box:
                        loose_d.bounding_box = BoundingBox(
                            x=det.bounding_box.x + x1,
                            y=det.bounding_box.y + y1,
                            w=det.bounding_box.w,
                            h=det.bounding_box.h,
                        )
                    loose_d.roi_name = "main_seam"
                    loose_d.description = (
                        f"AI detected loose end {loose_mm:.1f}mm confidence {det.confidence:.2f}"
                    )
                    if loose_d.outcome != Outcome.PASS:
                        defects.append(loose_d)

        return defects, measurements, annotated
