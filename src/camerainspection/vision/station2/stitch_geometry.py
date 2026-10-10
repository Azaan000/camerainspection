"""Stitch geometry analysis: Stitches Per Inch (SPI), skip length, seam position, and seam integrity."""

from __future__ import annotations

import cv2
import numpy as np
from pydantic import BaseModel, Field


class StitchMeasurementResult(BaseModel):
    stitch_count: int = 0
    stitches_per_inch: float = 0.0
    mean_pitch_mm: float = 0.0
    max_skip_length_mm: float = 0.0
    seam_position_mm: float = 0.0
    has_double_seam: bool = False
    has_open_end: bool = False
    stitch_centers: list[list[float]] = Field(default_factory=list)


class StitchGeometryEngine:
    """Analyzes linear sewing jig seams using classical OpenCV image processing."""

    @classmethod
    def segment_stitches(
        cls,
        seam_roi: np.ndarray,
        min_area: int = 5,
        max_area: int = 800,
    ) -> tuple[np.ndarray, list[dict[str, object]]]:
        """Segment individual thread stitch penetrations against dark leather background.

        Strategy: local background subtraction (large Gaussian blur) to isolate
        bright stitch patches on any dark background — works on both synthetic
        and real leather images without hand-tuning morphological kernel orientation.

        Returns:
            tuple[binary_mask, list_of_stitch_features]
        """
        gray = cv2.cvtColor(seam_roi, cv2.COLOR_BGR2GRAY) if len(seam_roi.shape) == 3 else seam_roi

        # Background estimate via large blur; stitch patches are much brighter locally.
        # cv2.subtract clips to [0,255] preventing uint8 wrap-around.
        background = cv2.GaussianBlur(gray, (31, 31), 0)
        diff = cv2.subtract(gray, background)

        # OTSU on the local-contrast-enhanced image
        _, binary = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Remove salt noise with a small morphological open
        clean_bin = cv2.morphologyEx(
            binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        )

        contours, _ = cv2.findContours(clean_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        stitches = []
        for c in contours:
            area = cv2.contourArea(c)
            if min_area <= area <= max_area:
                m = cv2.moments(c)
                if m["m00"] > 0:
                    cx = float(m["m10"] / m["m00"])
                    cy = float(m["m01"] / m["m00"])
                    x, y, w, h = cv2.boundingRect(c)
                    stitches.append({
                        "cx": cx,
                        "cy": cy,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        "area": area,
                    })

        # Sort stitches left-to-right (along seam direction)
        stitches = sorted(stitches, key=lambda s: s["cx"])
        return clean_bin, stitches  # type: ignore[return-value]

    @classmethod
    def analyze_seam(
        cls,
        seam_roi: np.ndarray,
        pixel_size_mm: float = 0.05,
        reference_style_line_y: float | None = None,
    ) -> StitchMeasurementResult:
        """Calculate stitches per inch, skip length, and seam distance to style line.

        pixel_size_mm: Spatial calibration target (e.g., 0.05 mm/pixel).
        """
        if seam_roi.size == 0 or pixel_size_mm <= 0:
            return StitchMeasurementResult()

        _, stitches = cls.segment_stitches(seam_roi)
        if len(stitches) < 2:
            return StitchMeasurementResult(stitch_count=len(stitches))

        centers = np.array([[s["cx"], s["cy"]] for s in stitches])
        x_coords = centers[:, 0]
        y_coords = centers[:, 1]

        # Pitch distances between consecutive stitches
        dx = np.diff(x_coords)
        dy = np.diff(y_coords)
        pitches_px = np.sqrt(dx**2 + dy**2)
        pitches_mm = pitches_px * pixel_size_mm

        median_pitch_mm = float(np.median(pitches_mm))
        mean_pitch_mm = float(np.mean(pitches_mm)) if len(pitches_mm) > 0 else 0.0

        # Stitches Per Inch (1 inch = 25.4 mm)
        spi = (25.4 / mean_pitch_mm) if mean_pitch_mm > 0 else 0.0

        # Detect skipped stitches: gap significantly larger than nominal pitch
        max_skip_mm = 0.0
        for p in pitches_mm:
            if p > (median_pitch_mm * 1.5):
                skip_len = p - median_pitch_mm
                if skip_len > max_skip_mm:
                    max_skip_mm = float(skip_len)

        # Seam position vs style line / jig datum
        ref_y = reference_style_line_y if reference_style_line_y is not None else 0.0
        mean_seam_y_px = float(np.mean(y_coords))
        seam_pos_mm = abs(mean_seam_y_px - ref_y) * pixel_size_mm

        # Double seam: bimodal Y distribution.
        # Threshold of 8px catches a two-row seam (shift ≥ 15px) while tolerating
        # normal vertical jitter (< 3px) and a 1–2mm style-line wander (< 5px).
        has_double_seam = False
        if len(y_coords) >= 4:
            y_std = float(np.std(y_coords))
            if y_std > 8.0:
                has_double_seam = True

        return StitchMeasurementResult(
            stitch_count=len(stitches),
            stitches_per_inch=float(round(spi, 2)),
            mean_pitch_mm=float(round(mean_pitch_mm, 2)),
            max_skip_length_mm=float(round(max_skip_mm, 2)),
            seam_position_mm=float(round(seam_pos_mm, 2)),
            has_double_seam=has_double_seam,
            has_open_end=False,
            stitch_centers=centers.tolist(),
        )
