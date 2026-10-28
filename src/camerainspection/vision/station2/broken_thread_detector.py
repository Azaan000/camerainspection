"""Heuristic broken thread detection via gap analysis in stitch sequence."""

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

        Uses the global median pitch as the baseline so a single noisy
        neighbour pair cannot skew the threshold. Only fires when a gap
        exceeds 2.5× the median AND exceeds min_gap_mm — reducing false
        positives on fabric texture contours.

        Args:
            stitch_centers: List of (x, y) pixel coordinates of detected stitches
            pixel_size_mm: Calibration factor (mm per pixel)

        Returns:
            List of (center_x, center_y, gap_mm) tuples for detected breaks
        """
        if len(stitch_centers) < 3:
            return []

        sorted_centers = sorted(stitch_centers, key=lambda c: c[0])

        # Compute all inter-stitch gaps
        gaps_px = []
        for i in range(len(sorted_centers) - 1):
            x1, y1 = sorted_centers[i]
            x2, y2 = sorted_centers[i + 1]
            gaps_px.append(float(np.hypot(x2 - x1, y2 - y1)))

        median_gap_px = float(np.median(gaps_px))
        min_gap_px = self.min_gap_mm / pixel_size_mm

        # A break is a gap that is both physically large AND anomalously wide
        # relative to the median pitch of this specific seam.
        breaks = []
        for i, gap_px in enumerate(gaps_px):
            gap_mm = gap_px * pixel_size_mm
            # Fire when gap is BOTH anomalously wide vs nearby stitches (2.5× median)
            # AND physically meaningful (> min_gap_mm).
            # Also fire on absolute gap > 3× min_gap_mm regardless of median —
            # catches the case where so few stitches are found that median skews high.
            is_relative_break = gap_px > (median_gap_px * 2.5) and gap_mm > self.min_gap_mm
            is_absolute_break = gap_mm > (self.min_gap_mm * 3.0)
            if is_relative_break or is_absolute_break:
                x1, y1 = sorted_centers[i]
                x2, y2 = sorted_centers[i + 1]
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                breaks.append((cx, cy, float(gap_mm)))

        return breaks
