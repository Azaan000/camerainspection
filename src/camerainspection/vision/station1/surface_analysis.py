"""Surface anomaly analysis for leather / rexene panel inspection (Station 1).

Two modes (selected automatically at construction time):

  ONNX mode (preferred):
    Loads models/station_1/model.onnx — an Anomalib PatchCore export.
    Input : float32 [2, 3, H, W]  (image duplicated along batch dim, normalised)
    Outputs: pred_score [2], pred_label [2], anomaly_map [2,1,256,256],
             pred_mask [2,1,256,256]
    The anomaly_map is upscaled to the ROI size, thresholded, and connected
    components are labelled with defect types via the same geometric classifier
    as the heuristic path.

  Heuristic mode (fallback — no model file):
    Gaussian background-subtraction + morphological clean-up, same as before.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Default model path relative to project root (two levels up from this file's package)
_DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "station_1" / "model.onnx"


class LeatherDefectType(StrEnum):
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
    """Detect and classify surface defects on dark leather/rexene panels.

    Pass ``model_path`` to use the trained ONNX model (Anomalib PatchCore).
    Omit it (or point to a missing file) to fall back to the heuristic pipeline.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        anomaly_threshold: float = 0.45,   # pred_score threshold for PASS/FAIL
        map_threshold: float = 0.4,        # normalised anomaly_map threshold for mask
        # heuristic fallback params
        blur_ksize: int = 101,             # increased for texture suppression
        diff_threshold: int = 25,          # increased for minimum contrast
        min_area_px: int = 4,
        max_area_px: int = 200_000,
        min_contrast: float = 25.0,
        min_area_mm2: float = 0.02,        # minimum area in mm² using pixel size
        max_defects_per_roi: int = 10,     # cap reported defects per ROI
    ) -> None:
        self.anomaly_threshold = anomaly_threshold
        self.map_threshold = map_threshold
        self.blur_ksize = blur_ksize | 1
        self.diff_threshold = diff_threshold
        self.min_area_px = min_area_px
        self.max_area_px = max_area_px
        self.min_contrast = min_contrast
        self.min_area_mm2 = min_area_mm2
        self.max_defects_per_roi = max_defects_per_roi

        self._session = None
        self._input_name: str = "input"

        if model_path is not None:
            mp = Path(model_path)
            if mp.exists():
                try:
                    import onnxruntime as rt
                    self._session = rt.InferenceSession(
                        str(mp), providers=["CPUExecutionProvider"]
                    )
                    self._input_name = self._session.get_inputs()[0].name
                    logger.info("SurfaceAnalyzer: loaded ONNX model from %s", mp)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("SurfaceAnalyzer: could not load ONNX model (%s) — using heuristic", exc)
            else:
                logger.warning("SurfaceAnalyzer: model not found at %s — using heuristic", mp)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, roi_bgr: np.ndarray, pixel_size_mm: float = 0.18, relaxed: bool = False) -> list[LeatherDefectRegion]:
        """Run detection-classification pipeline on a single ROI image.

        Args:
            roi_bgr: ROI image in BGR format
            pixel_size_mm: Pixel size in mm for area/length calculations
            relaxed: If True, use lower thresholds (for regions already flagged by PatchCore)
        """
        if roi_bgr is None or roi_bgr.size == 0:
            return []

        if self._session is not None:
            # Fix #7: pass pixel_size_mm so ONNX path uses the correct calibration
            return self._analyze_onnx(roi_bgr, pixel_size_mm=pixel_size_mm)
        return self._analyze_heuristic(roi_bgr, pixel_size_mm=pixel_size_mm, relaxed=relaxed)

    # ------------------------------------------------------------------
    # ONNX inference path
    # ------------------------------------------------------------------

    def _analyze_onnx(self, roi_bgr: np.ndarray, pixel_size_mm: float = 0.18) -> list[LeatherDefectRegion]:
        h, w = roi_bgr.shape[:2]

        # Normalise to float32 [0,1], RGB, resize to 256×256
        rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (256, 256)).astype(np.float32) / 255.0

        # ImageNet normalisation (standard for Anomalib PatchCore)
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        normalised = (resized - mean) / std                          # [256,256,3]
        chw = normalised.transpose(2, 0, 1)                          # [3,256,256]
        batch = np.stack([chw, chw], axis=0)                         # [2,3,256,256]

        outputs = self._session.run(None, {self._input_name: batch})
        # outputs: pred_score[2], pred_label[2], anomaly_map[2,1,256,256], pred_mask[2,1,256,256]
        pred_score  = float(outputs[0][0])
        anomaly_map = outputs[2][0, 0]   # [256,256] float32
        pred_mask   = outputs[3][0, 0]   # [256,256] bool

        # Fix #8: per-image min-max normalisation makes the score relative to the image's
        # own range, not an absolute anomaly scale.  A uniformly anomalous image still
        # peaks at 1.0 somewhere; a real defect in a textured image compresses to a low
        # score.  We preserve the raw map values for the fallback threshold path, and
        # apply the per-image normalisation only when the model's pred_mask is empty
        # (i.e. the model gave no spatial signal at all).  This way, on a truly clean
        # image, the near-zero absolute values stay near zero instead of normalising up.
        a_min, a_max = anomaly_map.min(), anomaly_map.max()
        # Absolute scale: normalise only relative to the anomaly_threshold so scores
        # retain meaning across images.
        if a_max > 0:
            # Clip to [0, 2× threshold] then scale, so hot pixels don't crush the rest.
            clip_max = max(a_max, self.anomaly_threshold * 2)
            norm_map = np.clip(anomaly_map / clip_max, 0.0, 1.0)
        else:
            norm_map = np.zeros_like(anomaly_map)

        # Build mask: use model's pred_mask OR threshold the normalised map
        mask_256 = pred_mask.astype(np.uint8) * 255
        if mask_256.sum() == 0:
            mask_256 = (norm_map >= self.map_threshold).astype(np.uint8) * 255

        # Upscale mask back to original ROI size
        if (h, w) != (256, 256):
            mask_roi = cv2.resize(mask_256, (w, h), interpolation=cv2.INTER_NEAREST)
        else:
            mask_roi = mask_256

        # Morphological cleanup
        k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask_roi = cv2.morphologyEx(mask_roi, cv2.MORPH_OPEN,  k3)
        mask_roi = cv2.morphologyEx(mask_roi, cv2.MORPH_CLOSE, k5)

        # For defect type classification we still need signed_diff from gray
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        bg   = cv2.GaussianBlur(gray, (self.blur_ksize, self.blur_ksize), 0)
        signed_diff = gray - bg

        # Fix #7: pass pixel_size_mm so area_mm2 filtering and size-based classification
        # use the actual camera calibration rather than the hardcoded 0.18 default.
        regions = self._extract_regions(mask_roi, signed_diff, pixel_size_mm=pixel_size_mm)

        # Attach the global anomaly score to every region (overrides per-region score
        # only when the model fired overall; keeps per-region score otherwise)
        if pred_score >= self.anomaly_threshold:
            for r in regions:
                r.anomaly_score = max(r.anomaly_score, pred_score)

        return regions

    # ------------------------------------------------------------------
    # Heuristic fallback path (original algorithm)
    # ------------------------------------------------------------------

    def _analyze_heuristic(self, roi_bgr: np.ndarray, pixel_size_mm: float = 0.18, relaxed: bool = False) -> list[LeatherDefectRegion]:
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY) if len(roi_bgr.shape) == 3 else roi_bgr.copy()
        h, w = gray.shape[:2]

        # Use much lower thresholds when analyzing a PatchCore-flagged region
        # PatchCore already confirmed an anomaly exists, so we're just classifying it
        if relaxed:
            diff_thresh = max(8, self.diff_threshold // 3)  # Drop to ~33% (min 8)
            min_contrast = max(8.0, self.min_contrast / 3.0)  # Drop to ~33% (min 8.0)
        else:
            diff_thresh = self.diff_threshold
            min_contrast = self.min_contrast

        # 1. Global / macroscopic shade band detection via 1D profile analysis
        shade_regions: list[LeatherDefectRegion] = []
        down_w, down_h = min(w, 64), min(h, 48)
        if down_w >= 16 and down_h >= 16:
            small = cv2.resize(gray, (down_w, down_h))
            col_means = small.mean(axis=0)
            row_means = small.mean(axis=1)
            col_range = float(np.max(col_means) - np.min(col_means))
            row_range = float(np.max(row_means) - np.min(row_means))

            if col_range > 25.0:
                mid = float(np.min(col_means) + 0.5 * col_range)
                band_cols = np.where(col_means > mid)[0]
                if len(band_cols) >= max(3, int(down_w * 0.15)):
                    x_min = int(band_cols[0] * w / down_w)
                    x_max = int((band_cols[-1] + 1) * w / down_w)
                    bw = max(1, x_max - x_min)
                    score = min(1.0, col_range / 60.0)
                    if score >= self.anomaly_threshold:
                        shade_regions.append(LeatherDefectRegion(
                            defect_type=LeatherDefectType.SHADE_BAND,
                            bbox_px=(x_min, 0, bw, h),
                            area_px=float(bw * h),
                            length_px=float(max(bw, h)),
                            aspect_ratio=float(max(bw, h)) / max(float(min(bw, h)), 1.0),
                            anomaly_score=score,
                        ))
            elif row_range > 25.0:
                mid = float(np.min(row_means) + 0.5 * row_range)
                band_rows = np.where(row_means > mid)[0]
                if len(band_rows) >= max(3, int(down_h * 0.15)):
                    y_min = int(band_rows[0] * h / down_h)
                    y_max = int((band_rows[-1] + 1) * h / down_h)
                    bh = max(1, y_max - y_min)
                    score = min(1.0, row_range / 60.0)
                    if score >= self.anomaly_threshold:
                        shade_regions.append(LeatherDefectRegion(
                            defect_type=LeatherDefectType.SHADE_BAND,
                            bbox_px=(0, y_min, w, bh),
                            area_px=float(w * bh),
                            length_px=float(max(w, bh)),
                            aspect_ratio=float(max(w, bh)) / max(float(min(w, bh)), 1.0),
                            anomaly_score=score,
                        ))

        # 2. Local anomaly detection via box filter background estimation
        # Clamp blur kernel to odd value <= min(h, w) so it doesn't dwarf a small ROI crop
        # (a 101px kernel on a 50px ROI makes signed_diff ≈ 0 everywhere → no regions found)
        safe_blur = min(self.blur_ksize, h - 1 if h % 2 == 0 else h, w - 1 if w % 2 == 0 else w)
        safe_blur = max(3, safe_blur)
        if safe_blur % 2 == 0:
            safe_blur -= 1  # keep it odd
        bg = cv2.blur(gray.astype(np.float32), (safe_blur, safe_blur))

        # Signed diff (raw, for sign classification)
        signed_diff = gray.astype(np.float32) - bg

        # Absolute diff for detection threshold
        abs_diff = np.abs(signed_diff).astype(np.uint8)
        _, candidate_mask = cv2.threshold(abs_diff, diff_thresh, 255, cv2.THRESH_BINARY)

        # Clean mask: open removes noise, close fills gaps
        k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_OPEN, k3)
        candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_CLOSE, k5)

        local_regions = self._extract_regions(candidate_mask, signed_diff, pixel_size_mm, min_contrast, relaxed=relaxed)
        all_regs = shade_regions + local_regions

        # Sort by anomaly score descending and cap at max_defects_per_roi
        all_regs.sort(key=lambda r: r.anomaly_score, reverse=True)
        if len(all_regs) > self.max_defects_per_roi:
            all_regs = all_regs[:self.max_defects_per_roi]

        return all_regs

    def _extract_regions(
        self, mask: np.ndarray, signed_diff: np.ndarray, pixel_size_mm: float = 0.18,
        min_contrast: float | None = None, relaxed: bool = False,
    ) -> list[LeatherDefectRegion]:
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        regions: list[LeatherDefectRegion] = []

        # In relaxed mode (PatchCore already confirmed an anomaly) drop the score gate
        # to 1/3 of the normal threshold so subtle scratches aren't silently discarded.
        score_threshold = (self.anomaly_threshold / 3.0) if relaxed else self.anomaly_threshold

        for i in range(1, num_labels):
            x, y, w, h, area_px = (
                int(stats[i, cv2.CC_STAT_LEFT]),
                int(stats[i, cv2.CC_STAT_TOP]),
                int(stats[i, cv2.CC_STAT_WIDTH]),
                int(stats[i, cv2.CC_STAT_HEIGHT]),
                int(stats[i, cv2.CC_STAT_AREA]),
            )
            area_mm2 = area_px * (pixel_size_mm ** 2)
            if area_mm2 < self.min_area_mm2 or area_px > self.max_area_px:
                continue

            mean_dev = float(signed_diff[labels == i].mean())
            contrast_threshold = min_contrast if min_contrast is not None else self.min_contrast
            if abs(mean_dev) < contrast_threshold:
                continue

            anomaly_score = min(1.0, abs(mean_dev) / 60.0)
            if anomaly_score < score_threshold:
                continue

            defect_type = self._classify(w, h, area_px, mean_dev, pixel_size_mm)

            regions.append(LeatherDefectRegion(
                defect_type=defect_type,
                bbox_px=(x, y, w, h),
                area_px=float(area_px),
                length_px=float(max(w, h)),
                aspect_ratio=float(max(w, h)) / max(float(min(w, h)), 1.0),
                anomaly_score=anomaly_score,
            ))
        return regions

    @staticmethod
    def _classify(w: int, h: int, area: float, mean_dev: float, pixel_size_mm: float = 0.18) -> LeatherDefectType:
        """Classify by sign + shape, strict priority order."""
        aspect = float(max(w, h)) / max(float(min(w, h)), 1.0)
        is_dark = mean_dev < 0   # negative signed diff → darker than background
        max_dim = max(w, h)
        area_mm2 = area * (pixel_size_mm ** 2)

        # 1. Pinhole: tiny dark spot (area_mm2 <= 1.5 mm², aspect < 2.5)
        if is_dark and area_mm2 <= 1.5 and aspect < 2.5:
            return LeatherDefectType.PINHOLE

        # 2. Large area (shade band - wide region from step-edge or material variation)
        if area > 15_000 or (max_dim > 250 and area > 5_000):
            return LeatherDefectType.SHADE_BAND

        # 3. Cut: dark + elongated (aspect ≥ 2.0, not too long)
        # Lowered from 2.5 to 2.0 to catch subtle cuts
        if is_dark and aspect >= 2.0 and max_dim <= 300:
            return LeatherDefectType.CUT

        # 4. Coating streak: bright + very long
        if not is_dark and max_dim > 150 and aspect >= 4.0:
            return LeatherDefectType.COATING_STREAK

        # 5. Scratch: BRIGHT + elongated (aspect ≥ 2.0, shorter than streak)
        # Lowered from 3.0 to 2.0 to catch subtle scratches
        # Scratches are BRIGHT (surface drag/fingernail marks)
        # Cuts are DARK (material broken/scored)
        if not is_dark and aspect >= 2.0 and max_dim <= 150:
            return LeatherDefectType.SCRATCH

        # 6. Stain: dark blob (non-pinhole, non-elongated)
        if is_dark and area_mm2 > 0.3:
            return LeatherDefectType.STAIN

        return LeatherDefectType.UNKNOWN
