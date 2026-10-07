"""Sub-millimeter dimension and flash measurement for plastic trim parts."""

from __future__ import annotations

import cv2
import numpy as np


class PlasticDimensionEngine:
    """Measures component gap distances and plastic flash protrusions in millimeters."""

    @classmethod
    def measure_gap_mm(
        cls,
        gap_roi: np.ndarray,
        pixel_size_mm: float = 0.10,
        axis: str = "horizontal",
    ) -> float:
        """Measure gap between two plastic edges in mm.

        If axis == 'horizontal', finds the distance between two vertical step edges.
        If axis == 'vertical', finds distance between two horizontal step edges.
        """
        if gap_roi.size == 0 or pixel_size_mm <= 0:
            return 0.0

        gray = cv2.cvtColor(gap_roi, cv2.COLOR_BGR2GRAY) if len(gap_roi.shape) == 3 else gap_roi
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        if axis == "horizontal":
            profile = np.mean(blurred, axis=0)
            gradient = np.diff(profile)
            # Find strongest negative step (drop) and positive step (rise)
            drop_idx = int(np.argmin(gradient))
            rise_idx = int(np.argmax(gradient))
            if drop_idx != rise_idx:
                gap_pixels = float(abs(rise_idx - drop_idx))
                return gap_pixels * pixel_size_mm
        else:
            profile = np.mean(blurred, axis=1)
            gradient = np.diff(profile)
            drop_idx = int(np.argmin(gradient))
            rise_idx = int(np.argmax(gradient))
            if drop_idx != rise_idx:
                gap_pixels = float(abs(rise_idx - drop_idx))
                return gap_pixels * pixel_size_mm

        return 0.0

    @classmethod
    def measure_flash_mm(
        cls,
        part_roi: np.ndarray,
        expected_edge_coord: int,
        pixel_size_mm: float = 0.10,
        direction: str = "bottom",
    ) -> float:
        """Measure maximum plastic flash (burr) protruding beyond expected mold parting line in mm.

        direction: 'bottom', 'top', 'right', 'left'
        """
        if part_roi.size == 0 or pixel_size_mm <= 0:
            return 0.0

        gray = cv2.cvtColor(part_roi, cv2.COLOR_BGR2GRAY) if len(part_roi.shape) == 3 else part_roi
        _, binary = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0.0

        # Find largest contour representing the molded part
        largest_c = max(contours, key=cv2.contourArea)
        pts = largest_c.reshape(-1, 2)  # [x, y] coordinates

        max_protrusion_px = 0.0
        if direction == "bottom":
            # Max Y extending below expected_edge_coord
            actual_max_y = float(np.max(pts[:, 1]))
            if actual_max_y > expected_edge_coord:
                max_protrusion_px = actual_max_y - expected_edge_coord
        elif direction == "top":
            actual_min_y = float(np.min(pts[:, 1]))
            if actual_min_y < expected_edge_coord:
                max_protrusion_px = expected_edge_coord - actual_min_y
        elif direction == "right":
            actual_max_x = float(np.max(pts[:, 0]))
            if actual_max_x > expected_edge_coord:
                max_protrusion_px = actual_max_x - expected_edge_coord
        elif direction == "left":
            actual_min_x = float(np.min(pts[:, 0]))
            if actual_min_x < expected_edge_coord:
                max_protrusion_px = expected_edge_coord - actual_min_x

        return max_protrusion_px * pixel_size_mm
