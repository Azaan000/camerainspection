"""Heuristic broken thread detection via color continuity analysis."""

import cv2
import numpy as np


class BrokenThreadDetector:
    """Heuristic broken thread detection via gap analysis in stitch sequence."""

    def __init__(self, min_gap_mm: float = 5.0):
        self.min_gap_mm = min_gap_mm

    def detect_breaks(
        self,
        stitch_centers: list[tuple[int, int]],
        pixel_size_mm: float,
    ) -> list[tuple[int, int, float]]:
        """Return list of (x, y, gap_mm) for detected breaks.

        Args:
            stitch_centers: List of (x, y) pixel coordinates of detected stitches
            pixel_size_mm: Calibration factor (mm per pixel)

        Returns:
            List of (center_x, center_y, gap_mm) tuples for detected breaks
        """
        if len(stitch_centers) < 3:
            return []

        # Sort by X coordinate (assumes horizontal seam)
        sorted_centers = sorted(stitch_centers, key=lambda c: c[0])
        breaks = []

        for i in range(len(sorted_centers) - 1):
            x1, y1 = sorted_centers[i]
            x2, y2 = sorted_centers[i + 1]
            gap_px = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            gap_mm = gap_px * pixel_size_mm

            # Calculate expected pitch from neighboring stitches
            if i > 0:
                x0, y0 = sorted_centers[i - 1]
                expected_pitch = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
            elif i < len(sorted_centers) - 2:
                x3, y3 = sorted_centers[i + 2]
                expected_pitch = np.sqrt((x3 - x2) ** 2 + (y3 - y2) ** 2)
            else:
                expected_pitch = gap_px

            # Flag as break if gap > 3x expected pitch AND > min_gap_mm
            if gap_px > 3 * expected_pitch and gap_mm > self.min_gap_mm:
                breaks.append((int((x1 + x2) / 2), int((y1 + y2) / 2), gap_mm))

        return breaks
