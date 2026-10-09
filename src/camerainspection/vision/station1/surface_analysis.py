"""Surface anomaly analysis for leather / rexene panel inspection (Station 1).

Algorithm (development / mock mode — no Anomalib dependency):
  1. Large-kernel Gaussian blur on raw gray → background luminance estimate.
  2. Signed difference → bright/dark anomaly map (sign preserved for classification).
  3. CLAHE-enhanced abs-diff for threshold — captures low-contrast defects.
  4. Absolute-value threshold + morphological clean-up → candidate mask.
  5. Connected-component analysis + geometric classifier.

Priority order in classifier:
  pinhole (tiny dark) → cut (dark + elongated) → scratch (bright + elongated)
  → shade_band (large area, any sign) → coating_streak (bright + long)
  → stain (dark blob) → unknown
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np


class LeatherDefectType(str, Enum):
    SCRATCH = "scratch"
    CUT = "cut"
    PINHOLE = "pinhole"
    STAIN = "stain"
    SHADE_BAND = "shade_band"
    COATING_STREAK = "coating_streak"
    UNKNOWN = "unknown"


@dataclass
class LeatherDefectRegion:
    defect_type: LeatherDefectType
    bbox_px: tuple[int, int, int, int]   # x, y, w, h in ROI-local coords
    area_px: float
    length_px: float
    aspect_ratio: float
    anomaly_score: float                  # normalised 0–1 (confidence proxy)


class SurfaceAnalyzer:
    """Detect and classify surface defects on dark leather/rexene panels."""

    def __init__(
        self,
        blur_ksize: int = 51,
        diff_threshold: int = 14,
        min_area_px: int = 4,
        max_area_px: int = 200_000,
    ) -> None:
        self.blur_ksize = blur_ksize | 1  # ensure odd
        self.diff_threshold = diff_threshold
        self.min_area_px = min_area_px
        self.max_area_px = max_area_px

    def analyze(self, roi_bgr: np.ndarray) -> list[LeatherDefectRegion]:
        """Run detection-classification pipeline on a single ROI image."""
        if roi_bgr is None or roi_bgr.size == 0:
            return []

        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY) if len(roi_bgr.shape) == 3 else roi_bgr.copy()
        h, w = gray.shape[:2]

        # 1. Global / macroscopic shade band detection via 1D profile analysis
        shade_regions: list[LeatherDefectRegion] = []
        down_w, down_h = min(w, 64), min(h, 48)
        if down_w >= 16 and down_h >= 16:
            small = cv2.resize(gray, (down_w, down_h))
            col_means = small.mean(axis=0)
            row_means = small.mean(axis=1)
            col_range = float(col_means.max() - col_means.min())
            row_range = float(row_means.max() - row_means.min())

            if col_range > 15.0:
                mid = float(col_means.min() + 0.5 * col_range)
                band_cols = np.where(col_means > mid)[0]
                if len(band_cols) >= max(3, int(down_w * 0.15)):
                    x_min = int(band_cols[0] * w / down_w)
                    x_max = int((band_cols[-1] + 1) * w / down_w)
                    bw = max(1, x_max - x_min)
                    shade_regions.append(LeatherDefectRegion(
                        defect_type=LeatherDefectType.SHADE_BAND,
                        bbox_px=(x_min, 0, bw, h),
                        area_px=float(bw * h),
                        length_px=float(max(bw, h)),
                        aspect_ratio=float(max(bw, h)) / max(float(min(bw, h)), 1.0),
                        anomaly_score=min(1.0, col_range / 60.0),
                    ))
            elif row_range > 15.0:
                mid = float(row_means.min() + 0.5 * row_range)
                band_rows = np.where(row_means > mid)[0]
                if len(band_rows) >= max(3, int(down_h * 0.15)):
                    y_min = int(band_rows[0] * h / down_h)
                    y_max = int((band_rows[-1] + 1) * h / down_h)
                    bh = max(1, y_max - y_min)
                    shade_regions.append(LeatherDefectRegion(
                        defect_type=LeatherDefectType.SHADE_BAND,
                        bbox_px=(0, y_min, w, bh),
                        area_px=float(w * bh),
                        length_px=float(max(w, bh)),
                        aspect_ratio=float(max(w, bh)) / max(float(min(w, bh)), 1.0),
                        anomaly_score=min(1.0, row_range / 60.0),
                    ))

        if shade_regions:
            return shade_regions

        # 2. Local anomaly detection via Gaussian background subtraction
        bg = cv2.GaussianBlur(gray.astype(np.float32), (self.blur_ksize, self.blur_ksize), 0)

        # Signed diff (raw, for sign classification)
        signed_diff = gray.astype(np.float32) - bg

        # Absolute diff for detection threshold
        abs_diff = np.abs(signed_diff).astype(np.uint8)
        _, candidate_mask = cv2.threshold(abs_diff, self.diff_threshold, 255, cv2.THRESH_BINARY)

        # Clean mask: open removes noise, close fills gaps
        k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_OPEN, k3)
        candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_CLOSE, k5)

        return self._extract_regions(candidate_mask, signed_diff)

    def _extract_regions(
        self, mask: np.ndarray, signed_diff: np.ndarray
    ) -> list[LeatherDefectRegion]:
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        regions: list[LeatherDefectRegion] = []

        for i in range(1, num_labels):
            x, y, w, h, area = (
                int(stats[i, cv2.CC_STAT_LEFT]),
                int(stats[i, cv2.CC_STAT_TOP]),
                int(stats[i, cv2.CC_STAT_WIDTH]),
                int(stats[i, cv2.CC_STAT_HEIGHT]),
                int(stats[i, cv2.CC_STAT_AREA]),
            )
            if area < self.min_area_px or area > self.max_area_px:
                continue

            mean_dev = float(signed_diff[labels == i].mean())
            anomaly_score = min(1.0, abs(mean_dev) / 60.0)
            defect_type = self._classify(w, h, area, mean_dev)

            regions.append(LeatherDefectRegion(
                defect_type=defect_type,
                bbox_px=(x, y, w, h),
                area_px=float(area),
                length_px=float(max(w, h)),
                aspect_ratio=float(max(w, h)) / max(float(min(w, h)), 1.0),
                anomaly_score=anomaly_score,
            ))
        return regions

    @staticmethod
    def _classify(w: int, h: int, area: float, mean_dev: float) -> LeatherDefectType:
        """Classify by sign + shape, strict priority order."""
        aspect = float(max(w, h)) / max(float(min(w, h)), 1.0)
        is_dark = mean_dev < 0   # negative signed diff → darker than background
        max_dim = max(w, h)

        # 1. Pinhole: tiny dark spot (radius ≤ ~5px → area ≤ 80)
        if is_dark and area < 80 and aspect < 2.5:
            return LeatherDefectType.PINHOLE

        # 2. Large area (shade band - wide region from step-edge or material variation)
        if area > 10_000 or (max_dim > 200 and area > 3_000):
            return LeatherDefectType.SHADE_BAND

        # 3. Cut: dark + elongated (aspect ≥ 2.5, not too long for streak)
        if is_dark and aspect >= 2.5 and max_dim <= 300:
            return LeatherDefectType.CUT

        # 4. Coating streak: bright + very long
        if not is_dark and max_dim > 150 and aspect >= 4.0:
            return LeatherDefectType.COATING_STREAK

        # 5. Scratch: bright + elongated (shorter)
        if not is_dark and aspect >= 3.0:
            return LeatherDefectType.SCRATCH

        # 6. Stain: dark blob (non-pinhole, non-elongated)
        if is_dark and area >= 80:
            return LeatherDefectType.STAIN

        return LeatherDefectType.UNKNOWN
