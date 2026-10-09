"""Rule-based short-cover and foam show-through detection algorithm (no ML)."""

from __future__ import annotations

import cv2
import numpy as np
from pydantic import BaseModel

from camerainspection.core.models import BoundingBox


class FoamDefect(BaseModel):
    exposed_area_mm2: float
    max_dimension_mm: float
    bounding_box: BoundingBox
    mean_foam_intensity: float


class FoamShowthroughEngine:
    """Detects exposed polyurethane seat foam at edges, tucks, and short covers."""

    @classmethod
    def detect_foam(
        cls,
        roi_bgr: np.ndarray,
        pixel_size_mm: float = 0.15,
        min_area_mm2: float = 2.0,
    ) -> list[FoamDefect]:
        """Detect exposed yellow/cream foam regions.

        Args:
            roi_bgr: BGR crop around seams, bottom skirts, or shield borders.
            pixel_size_mm: Scale factor in mm/pixel.
            min_area_mm2: Minimum area threshold to flag as defect.
        """
        if roi_bgr.size == 0:
            return []

        # Convert to HSV to detect characteristic yellow/light cream foam color
        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)

        # Polyurethane foam color band in HSV:
        # Hue: 15 to 40 (yellow to light orange/tan)
        # Saturation: 30 to 220 (moderate saturation)
        # Value: 120 to 255 (high brightness)
        lower_foam = np.array([12, 30, 110], dtype=np.uint8)
        upper_foam = np.array([45, 220, 255], dtype=np.uint8)

        mask = cv2.inRange(hsv, lower_foam, upper_foam)

        # Clean small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        clean_mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        clean_mask = cv2.morphologyEx(clean_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        defects: list[FoamDefect] = []

        area_scale = pixel_size_mm ** 2
        for cnt in contours:
            area_px = cv2.contourArea(cnt)
            area_mm2 = area_px * area_scale
            if area_mm2 >= min_area_mm2:
                x, y, w, h = cv2.boundingRect(cnt)
                max_dim_mm = max(w, h) * pixel_size_mm
                mean_val = float(cv2.mean(hsv[:, :, 2], mask=clean_mask)[0])

                defects.append(
                    FoamDefect(
                        exposed_area_mm2=round(area_mm2, 2),
                        max_dimension_mm=round(max_dim_mm, 2),
                        bounding_box=BoundingBox(x=x, y=y, w=w, h=h),
                        mean_foam_intensity=round(mean_val, 1),
                    )
                )

        return defects
