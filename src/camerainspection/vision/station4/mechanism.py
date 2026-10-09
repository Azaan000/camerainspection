"""Vision measurement engines for Station 4: recliner lever angle and track end position."""

from __future__ import annotations

import math
import cv2
import numpy as np


class MechanismVisionEngine:
    """Optical measurement of mechanical positions: recliner lever angle & track travel end mark."""

    @classmethod
    def measure_recliner_angle(cls, recliner_roi: np.ndarray) -> float:
        """Measure the recliner lever angle in degrees from ROI.

        Convention:
            Finds the prominent lever arm / centerline in the ROI.
            Returns angle in degrees (0..180), where 90 deg represents vertical upright nominal.
            Uses Hough Lines or oriented bounding box / principal component analysis.
        """
        if recliner_roi is None or recliner_roi.size == 0:
            return 0.0

        gray = cv2.cvtColor(recliner_roi, cv2.COLOR_BGR2GRAY) if len(recliner_roi.shape) == 3 else recliner_roi
        # Threshold to find lever arm
        _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0.0

        # Find largest contour (the lever)
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) < 50:
            return 0.0

        # Fit line to determine orientation: returns normalized direction vector (vx, vy)
        line_params = cv2.fitLine(c, cv2.DIST_L2, 0, 0.01, 0.01)
        vx = float(line_params[0][0]) if hasattr(line_params[0], "__len__") else float(line_params[0])
        vy = float(line_params[1][0]) if hasattr(line_params[1], "__len__") else float(line_params[1])

        # Angle of lever relative to horizontal x-axis (with image y flipped so up is positive y)
        angle_rad = math.atan2(-vy, vx)
        angle_deg = float(math.degrees(angle_rad) % 180.0)

        return round(angle_deg, 2)

    @classmethod
    def measure_track_position_mm(
        cls,
        track_roi: np.ndarray,
        pixel_size_mm: float = 0.15,
        reference_datum_x: float = 0.0,
    ) -> float:
        """Measure linear position of track travel mark in millimeters.

        Args:
            track_roi: Crop containing the track mark / pointer indicator.
            pixel_size_mm: Spatial calibration factor.
            reference_datum_x: Pixel X coordinate of zero travel datum in ROI.
        """
        if track_roi is None or track_roi.size == 0:
            return 0.0

        gray = cv2.cvtColor(track_roi, cv2.COLOR_BGR2GRAY) if len(track_roi.shape) == 3 else track_roi
        # Track pointer/fiducial mark is high-contrast
        _, binary = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0.0

        # Filter candidate marks by area
        valid = [c for c in contours if 20 < cv2.contourArea(c) < 5000]
        if not valid:
            valid = contours

        # Pick pointer mark (most distinct indicator)
        best = max(valid, key=cv2.contourArea)
        M = cv2.moments(best)
        if M["m00"] > 0:
            mark_x = float(M["m10"] / M["m00"])
        else:
            x, _, w, _ = cv2.boundingRect(best)
            mark_x = float(x + w / 2)

        travel_mm = (mark_x - reference_datum_x) * pixel_size_mm
        return round(float(travel_mm), 2)
