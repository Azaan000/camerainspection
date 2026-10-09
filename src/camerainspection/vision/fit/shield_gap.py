"""Rule-based shield-to-cover gap measurement algorithm (no ML)."""

from __future__ import annotations

import cv2
import numpy as np
from pydantic import BaseModel


class ShieldGapMeasurement(BaseModel):
    mean_gap_mm: float
    min_gap_mm: float
    max_gap_mm: float
    gap_points: list[list[float]] = []


class ShieldGapEngine:
    """Measures physical spacing between rigid plastic shield and upholstered fabric/leather."""

    @classmethod
    def measure_gap(
        cls,
        roi_bgr: np.ndarray,
        pixel_size_mm: float = 0.15,
        axis: str = "vertical",
    ) -> ShieldGapMeasurement:
        """Measure gap profile along the given axis across ROI.

        Args:
            roi_bgr: BGR crop containing shield edge and cover edge.
            pixel_size_mm: Scaling factor in mm/pixel.
            axis: Direction of gap measurement ('horizontal' or 'vertical').
        """
        if roi_bgr.size == 0:
            return ShieldGapMeasurement(mean_gap_mm=0.0, min_gap_mm=0.0, max_gap_mm=0.0)

        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY) if len(roi_bgr.shape) == 3 else roi_bgr
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny edge detection
        edges = cv2.Canny(blurred, 40, 120)

        gap_measurements_px: list[float] = []
        pts: list[list[float]] = []

        if axis == "horizontal":
            # For each scan row, find distance between first edge (shield) and second edge (cover)
            h, w = gray.shape
            for y in range(5, h - 5, 2):
                row = edges[y, :]
                edge_indices = np.where(row > 0)[0]
                if len(edge_indices) >= 2:
                    dist = float(edge_indices[1] - edge_indices[0])
                    if dist > 2.0:
                        gap_measurements_px.append(dist)
                        pts.append([float(edge_indices[0]), float(y)])
        else:
            # Vertical scan columns
            h, w = gray.shape
            for x in range(5, w - 5, 2):
                col = edges[:, x]
                edge_indices = np.where(col > 0)[0]
                if len(edge_indices) >= 2:
                    dist = float(edge_indices[1] - edge_indices[0])
                    if dist > 2.0:
                        gap_measurements_px.append(dist)
                        pts.append([float(x), float(edge_indices[0])])

        if not gap_measurements_px:
            # Fallback using threshold valley
            _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
            profile = np.mean(thresh, axis=0 if axis == "horizontal" else 1)
            valley_width_px = float(np.sum(profile > 100))
            gap_mm = valley_width_px * pixel_size_mm
            return ShieldGapMeasurement(mean_gap_mm=gap_mm, min_gap_mm=gap_mm, max_gap_mm=gap_mm)

        gaps_mm = [g * pixel_size_mm for g in gap_measurements_px]
        return ShieldGapMeasurement(
            mean_gap_mm=float(np.mean(gaps_mm)),
            min_gap_mm=float(np.min(gaps_mm)),
            max_gap_mm=float(np.max(gaps_mm)),
            gap_points=pts[:20],
        )
