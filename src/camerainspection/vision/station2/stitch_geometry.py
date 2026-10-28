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
    def locate_seam_band(
        cls,
        seam_roi: np.ndarray,
        band_half: int = 50,
    ) -> tuple[np.ndarray, float, float]:
        """Find the seam line and return a tight band around it.

        Strategy: Hough line detection first (works on continuous seam edges).
        Fallback: variance projection along each axis — the row/column with the
        highest local contrast is where stitch dots sit. Works on both vertical
        and horizontal seams regardless of orientation.

        Returns:
            (band_crop, seam_cx, seam_cy) in full-ROI pixel coordinates.
            Falls back to full ROI + centre if neither method finds a seam.
        """
        gray = cv2.cvtColor(seam_roi, cv2.COLOR_BGR2GRAY) if len(seam_roi.shape) == 3 else seam_roi
        h, w = gray.shape

        # --- Attempt 1: Hough line ---
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 90)
        min_len = max(30, min(w, h) // 6)  # relaxed: 1/6 of shorter dimension
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=40,
            minLineLength=min_len,
            maxLineGap=40,
        )

        if lines is not None and len(lines) > 0:
            lines_flat = lines.reshape(-1, 4)
            lengths = np.hypot(lines_flat[:, 2] - lines_flat[:, 0], lines_flat[:, 3] - lines_flat[:, 1])
            x1, y1, x2, y2 = lines_flat[int(np.argmax(lengths))]
            seam_cx = float((x1 + x2) / 2)
            seam_cy = float((y1 + y2) / 2)
            dx, dy = abs(x2 - x1), abs(y2 - y1)
            if dy >= dx:
                cx = int(seam_cx)
                band = seam_roi[:, max(0, cx - band_half):min(w, cx + band_half)]
            else:
                cy = int(seam_cy)
                band = seam_roi[max(0, cy - band_half):min(h, cy + band_half), :]
            if band.size > 0:
                return band, seam_cx, seam_cy

        # --- Fallback: variance projection ---
        # Column variance peaks where a vertical seam's stitch dots sit.
        # Row variance peaks where a horizontal seam's stitch dots sit.
        col_var = np.array([float(np.std(gray[:, c])) for c in range(w)])
        row_var = np.array([float(np.std(gray[r, :])) for r in range(h)])

        col_smooth = np.convolve(col_var, np.ones(15) / 15, mode="same")
        row_smooth = np.convolve(row_var, np.ones(15) / 15, mode="same")

        best_col_score = float(col_smooth.max())
        best_row_score = float(row_smooth.max())

        if best_col_score >= best_row_score:
            # Vertical seam
            cx = int(np.argmax(col_smooth))
            seam_cx, seam_cy = float(cx), float(h / 2)
            band = seam_roi[:, max(0, cx - band_half):min(w, cx + band_half)]
        else:
            # Horizontal seam
            cy = int(np.argmax(row_smooth))
            seam_cx, seam_cy = float(w / 2), float(cy)
            band = seam_roi[max(0, cy - band_half):min(h, cy + band_half), :]

        if band.size == 0:
            return seam_roi, float(w / 2), float(h / 2)

        return band, seam_cx, seam_cy

    @classmethod
    def segment_stitches(
        cls,
        seam_roi: np.ndarray,
        min_area: int = 12,
        max_area: int = 700,
    ) -> tuple[np.ndarray, list[dict[str, object]]]:
        """Segment individual thread stitch penetrations from the seam band.

        Uses adaptive thresholding after local background subtraction so it
        works across both dark leather and light grey/patterned fabrics without
        parameter re-tuning.

        Returns:
            tuple[binary_mask, list_of_stitch_features]
        """
        gray = cv2.cvtColor(seam_roi, cv2.COLOR_BGR2GRAY) if len(seam_roi.shape) == 3 else seam_roi

        # Remove large-scale illumination gradient
        background = cv2.GaussianBlur(gray, (31, 31), 0)
        diff = cv2.subtract(gray, background)

        # Adaptive threshold handles varying local contrast across fabric types.
        # Block size 21 works for stitch dots ~5-15px across at 0.08 mm/px.
        adaptive = cv2.adaptiveThreshold(
            diff, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=21,
            C=-4,
        )

        # Morphological open with 3×3 removes weave texture fragments
        clean_bin = cv2.morphologyEx(
            adaptive, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        )

        contours, _ = cv2.findContours(clean_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if not (min_area <= area <= max_area):
                continue
            m = cv2.moments(c)
            if m["m00"] <= 0:
                continue
            cx = float(m["m10"] / m["m00"])
            cy = float(m["m01"] / m["m00"])
            x, y, w, h = cv2.boundingRect(c)
            aspect = max(w, h) / max(min(w, h), 1)
            if aspect > 6.0:
                continue
            if h > seam_roi.shape[0] * 0.6:
                continue
            candidates.append({"cx": cx, "cy": cy, "x": x, "y": y, "w": w, "h": h, "area": area})

        # Suppress weave-texture noise: real stitches lie along the seam line, so
        # their Y-coords cluster tightly. Keep only candidates within ±8px of the
        # median Y. Texture blobs scatter across the full band height (std > 20px)
        # so this eliminates them while leaving real stitches (std < 2px) intact.
        if len(candidates) >= 4:
            cy_vals = np.array([s["cy"] for s in candidates])
            med_cy = float(np.median(cy_vals))
            candidates = [s for s in candidates if abs(s["cy"] - med_cy) <= 8.0]

        # Suppress dense weave-texture blobs: real stitches have a minimum pitch.
        # Sort by X and enforce that consecutive candidates are at least min_pitch_px
        # apart. If the median X-spacing is < min_pitch_px, the candidates are texture
        # noise — discard until spacing is plausible (≥ 8px at 0.05mm/px ≈ 2 SPI max).
        candidates = sorted(candidates, key=lambda s: s["cx"])
        if len(candidates) >= 4:
            x_vals = np.array([s["cx"] for s in candidates])
            spacings = np.diff(x_vals)
            med_spacing = float(np.median(spacings))
            # If typical spacing is < 8px, too dense to be real stitches; apply NMS-style
            # suppression: keep a candidate only if it is ≥ 8px from the previous kept one.
            if med_spacing < 8.0:
                kept: list[dict] = []
                last_x = -999.0
                for s in candidates:
                    if s["cx"] - last_x >= 8.0:
                        kept.append(s)
                        last_x = s["cx"]
                candidates = kept

        stitches = sorted(candidates, key=lambda s: s["cx"])
        return clean_bin, stitches  # type: ignore[return-value]

    @classmethod
    def analyze_seam(
        cls,
        seam_roi: np.ndarray,
        pixel_size_mm: float = 0.05,
        reference_style_line_y: float | None = None,
        double_seam_threshold_mm: float = 0.7,
    ) -> StitchMeasurementResult:
        """Calculate stitches per inch, skip length, and seam distance to style line.

        pixel_size_mm: Spatial calibration target (e.g., 0.08 mm/pixel).
        """
        if seam_roi.size == 0 or pixel_size_mm <= 0:
            return StitchMeasurementResult()

        # Locate seam band — orientation-agnostic, handles vertical and horizontal seams.
        # band_offset_{x,y} track how much the band is shifted vs the full ROI so we can
        # map band-local stitch coordinates back to full-ROI space for callers.
        band, seam_cx, seam_cy = cls.locate_seam_band(seam_roi)

        h_roi, w_roi = seam_roi.shape[:2]
        h_band, w_band = band.shape[:2]
        # Derive band offsets from seam centre + band dimensions
        band_offset_x = max(0, int(seam_cx) - w_band // 2) if w_band < w_roi else 0
        band_offset_y = max(0, int(seam_cy) - h_band // 2) if h_band < h_roi else 0

        _, stitches = cls.segment_stitches(band)
        if len(stitches) < 2:
            return StitchMeasurementResult(stitch_count=len(stitches))

        # Band-local centers used for pitch/skip/double-seam calculations
        centers_local = np.array([[s["cx"], s["cy"]] for s in stitches])
        x_coords = centers_local[:, 0]
        y_coords = centers_local[:, 1]

        # Full-ROI centers returned to callers (thread color, broken thread detector)
        centers_global = centers_local + np.array([band_offset_x, band_offset_y])

        # Pitch distances between consecutive stitches
        dx = np.diff(x_coords)
        dy = np.diff(y_coords)
        pitches_px = np.sqrt(dx**2 + dy**2)
        pitches_mm = pitches_px * pixel_size_mm

        median_pitch_mm = float(np.median(pitches_mm))
        mean_pitch_mm = float(np.mean(pitches_mm)) if len(pitches_mm) > 0 else 0.0

        # Stitches Per Inch (1 inch = 25.4 mm)
        spi = (25.4 / mean_pitch_mm) if mean_pitch_mm > 0 else 0.0

        # Detect skipped stitches: gap significantly larger than median pitch.
        # Uses median (not mean) so a single large defect gap doesn't skew the baseline.
        max_skip_mm = 0.0
        for p in pitches_mm:
            if p > (median_pitch_mm * 1.5):
                skip_len = p - median_pitch_mm
                if skip_len > max_skip_mm:
                    max_skip_mm = float(skip_len)

        # Seam position: absolute deviation from expected style line in full-ROI coordinates.
        # seam_cy comes from locate_seam_band and is already in full-ROI space.
        if reference_style_line_y is not None:
            seam_pos_mm = abs(seam_cy - reference_style_line_y) * pixel_size_mm
        else:
            seam_pos_mm = seam_cy * pixel_size_mm

        # Double seam: bimodal Y distribution within the band.
        # Fix #4: threshold in mm, converted to pixels using pixel_size_mm, so it
        # fires consistently regardless of camera resolution.
        has_double_seam = False
        if len(y_coords) >= 4:
            y_std = float(np.std(y_coords))
            double_seam_threshold_px = double_seam_threshold_mm / pixel_size_mm
            if y_std > double_seam_threshold_px:
                has_double_seam = True

        return StitchMeasurementResult(
            stitch_count=len(stitches),
            stitches_per_inch=float(round(spi, 2)),
            mean_pitch_mm=float(round(mean_pitch_mm, 2)),
            max_skip_length_mm=float(round(max_skip_mm, 2)),
            seam_position_mm=float(round(seam_pos_mm, 2)),
            has_double_seam=has_double_seam,
            has_open_end=False,
            stitch_centers=centers_global.tolist(),
        )
