"""Rule-based wrinkle and puckering detection algorithm at seat radii (no ML)."""

from __future__ import annotations

import cv2
import numpy as np
from pydantic import BaseModel

from camerainspection.core.models import BoundingBox


class WrinkleDetection(BaseModel):
    length_mm: float
    depth_contrast: float
    bounding_box: BoundingBox
    is_puckering: bool = False


class WrinkleDetectionEngine:
    """Detects creases, folds, and puckering along leather and fabric bolster radii."""

    @classmethod
    def detect_wrinkles(
        cls,
        roi_bgr: np.ndarray,
        pixel_size_mm: float = 0.15,
        contrast_threshold: float = 18.0,
        min_length_mm: float = 4.0,
    ) -> list[WrinkleDetection]:
        """Detect wrinkle and pucker formations.

        Args:
            roi_bgr: Input BGR image patch around bolster or radius.
            pixel_size_mm: Scale factor.
            contrast_threshold: Minimum intensity contrast across the fold shadow.
            min_length_mm: Minimum continuous crease length to report.
        """
        if roi_bgr.size == 0:
            return []

        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY) if len(roi_bgr.shape) == 3 else roi_bgr

        # Morphological black top-hat to highlight dark valleys/shadows of creases
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
        tophat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)

        # Threshold to identify fold candidates
        _, thresh = cv2.threshold(tophat, int(contrast_threshold), 255, cv2.THRESH_BINARY)

        # Clean noise
        clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[WrinkleDetection] = []

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # Crease length is the maximum bounding dimension
            length_px = max(w, h)
            length_mm = length_px * pixel_size_mm

            if length_mm >= min_length_mm:
                mask = np.zeros_like(gray)
                cv2.drawContours(mask, [cnt], -1, 255, -1)
                contrast = float(cv2.mean(tophat, mask=mask)[0])

                # Puckering typically has a wave-like cluster pattern (aspect ratio closer to 1)
                aspect = float(w) / float(max(1, h))
                is_puckering = 0.5 < aspect < 2.0 and w * h > 100

                detections.append(
                    WrinkleDetection(
                        length_mm=round(length_mm, 2),
                        depth_contrast=round(contrast, 1),
                        bounding_box=BoundingBox(x=x, y=y, w=w, h=h),
                        is_puckering=is_puckering,
                    )
                )

        return detections
