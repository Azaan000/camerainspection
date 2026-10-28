"""ONNX inference engine for Anomalib PatchCore anomaly detection.

Model I/O contract (confirmed on exported model):
  Input  : "input"     float32  [2, 3, 256, 256]  NCHW, RGB 0-1
           Batch is FIXED at 2 — duplicate the single frame into both slots
           and use only index 0 of every output.
  Outputs:
    pred_score   [2]            float32  per-image anomaly score (0–1)
    pred_label   [2]            bool     True = anomalous
    anomaly_map  [2, 1, 256, 256] float32 per-pixel heatmap
    pred_mask    [2, 1, 256, 256] bool   thresholded defect mask

Preprocessing (MUST NOT use ImageNet mean/std — confirmed broken):
  BGR→RGB, resize to 256×256, divide by 255.0  (no further normalisation).

Thresholding:
  pred_label True              → FAIL
  pass_below ≤ score < fail_above → REVIEW   (configurable, default 0.40/0.60)
  score < pass_below           → PASS

The engine maps pred_mask contours to ModelDetection / DefectDetail instances
with defect_type "LEATHER_ANOMALY", a BoundingBox from the contour, and
confidence from pred_score[0].
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from camerainspection.core.models import BoundingBox
from camerainspection.inference.base import BaseInferenceEngine, ModelDetection

logger = logging.getLogger("inference.onnx_patchcore")

# Model geometry — fixed by export
_INPUT_SIZE = 256
_BATCH_SIZE = 2
_INPUT_NAME = "input"

# Output names (exact names from onnxruntime session output metadata)
_OUT_SCORE = "pred_score"
_OUT_LABEL = "pred_label"
_OUT_HEATMAP = "anomaly_map"
_OUT_MASK = "pred_mask"

# Minimum contour area in pixels to report as a detection (avoids noise specks)
_MIN_CONTOUR_AREA_PX = 16


class OnnxPatchCoreEngine(BaseInferenceEngine):
    """ONNX-runtime inference engine wrapping an Anomalib PatchCore export.

    Parameters
    ----------
    pass_below : float
        Scores strictly below this value are PASS (default 0.40).
    fail_above : float
        Scores at or above this value are FAIL (default 0.60).
        Scores in [pass_below, fail_above) become REVIEW detections.
    providers : list[str] | None
        ONNX Runtime execution providers.  None → auto (CUDA → CPU).
    """

    def __init__(
        self,
        pass_below: float = 0.40,
        fail_above: float = 0.60,
        providers: list[str] | None = None,
    ) -> None:
        if pass_below >= fail_above:
            raise ValueError(
                f"pass_below ({pass_below}) must be strictly less than fail_above ({fail_above})."
            )
        self.pass_below = pass_below
        self.fail_above = fail_above
        self._providers = providers  # resolved at load() time
        self._session: Any = None  # onnxruntime.InferenceSession
        self._weights_path: Path | None = None
        self._version: str = "onnx-patchcore-unknown"

    # ------------------------------------------------------------------
    # BaseInferenceEngine interface
    # ------------------------------------------------------------------

    def load(self, weights_path: str | Path) -> None:
        """Load the ONNX model.  Both model.onnx and model.onnx.data must sit
        in the same directory — onnxruntime resolves the data file automatically.
        """
        try:
            import onnxruntime as ort  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "onnxruntime is not installed.  "
                "Install it with: pip install onnxruntime  (or onnxruntime-gpu)"
            ) from exc

        path = Path(weights_path)
        if not path.exists():
            raise FileNotFoundError(f"ONNX model not found: {path}")

        # Resolve providers: prefer GPU when available
        available = ort.get_available_providers()
        if self._providers is None:
            self._providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if "CUDAExecutionProvider" in available
                else ["CPUExecutionProvider"]
            )

        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self._session = ort.InferenceSession(
            str(path), sess_options=sess_opts, providers=self._providers
        )
        self._weights_path = path
        self._version = f"onnx-patchcore-{path.parent.name}"
        logger.info(
            "PatchCore ONNX model loaded from %s using providers %s",
            path,
            self._session.get_providers(),
        )

        # Sanity-check I/O names
        input_names = [i.name for i in self._session.get_inputs()]
        output_names = [o.name for o in self._session.get_outputs()]
        if _INPUT_NAME not in input_names:
            raise RuntimeError(
                f"Expected ONNX input named '{_INPUT_NAME}', got: {input_names}"
            )
        for expected in (_OUT_SCORE, _OUT_LABEL, _OUT_HEATMAP, _OUT_MASK):
            if expected not in output_names:
                raise RuntimeError(
                    f"Expected ONNX output named '{expected}', got: {output_names}"
                )

    def predict(self, image: np.ndarray) -> list[ModelDetection]:
        """Run PatchCore inference on a single BGR image array.

        Returns a list of ModelDetection instances.  An empty list means PASS.
        """
        if self._session is None:
            raise RuntimeError("Model is not loaded.  Call load() first.")

        tensor = self._preprocess(image)
        outputs = self._session.run(
            [_OUT_SCORE, _OUT_LABEL, _OUT_HEATMAP, _OUT_MASK],
            {_INPUT_NAME: tensor},
        )

        score_arr, label_arr, heatmap_arr, mask_arr = outputs

        # Select index with highest score across the duplicated batch slots
        # to avoid non-deterministic 0/0 normalizer tie-breaks
        best_idx = int(np.argmax(score_arr))
        raw_score_unclamped: float = float(score_arr[best_idx])

        # Guard against NaN/Inf from the ONNX model's internal normalisation
        # (happens when both batch slots produce identical scores → division by zero)
        import math
        if math.isnan(raw_score_unclamped) or math.isinf(raw_score_unclamped):
            # Fall back to heatmap-derived score: normalised max of anomaly map
            heatmap_raw = heatmap_arr[best_idx, 0]
            hmap_max = float(heatmap_raw.max())
            hmap_min = float(heatmap_raw.min())
            denom = hmap_max - hmap_min
            raw_score_unclamped = (hmap_max - hmap_min) / (denom + 1e-8) if denom > 0 else 0.0
            # Scale to [0,1] using a fixed reference max (empirically ~10-20 for WideResNet features)
            raw_score_unclamped = min(1.0, hmap_max / 20.0)
            logger.debug("NaN score corrected via heatmap fallback: %.4f", raw_score_unclamped)

        # CRITICAL: Store UNCLAMPED raw score for diagnostics
        # Clamping at 1.0 loses information about how out-of-distribution the image is
        score: float = raw_score_unclamped  # Keep raw value, don't clamp

        is_anomalous: bool = bool(label_arr[best_idx])
        heatmap: np.ndarray = heatmap_arr[best_idx, 0]  # (256, 256) float32
        mask: np.ndarray = mask_arr[best_idx, 0].astype(np.uint8) * 255  # (256, 256) uint8

        # Compute heatmap statistics for domain warning detection
        hmap_max = float(heatmap.max())
        hmap_mean = float(heatmap.mean())
        hmap_std = float(heatmap.std())

        logger.debug(
            "PatchCore result: raw_score=%.4f  pred_label=%s  hmap_max=%.4f",
            score, is_anomalous, hmap_max
        )

        # If PASS by both criteria, return nothing
        if not is_anomalous and score < self.pass_below:
            return []

        # Find contours in the thresholded mask combined with thresholded heatmap
        hmap_min, hmap_max_val = float(heatmap.min()), float(heatmap.max())
        if hmap_max_val > hmap_min:
            hmap_norm = ((heatmap - hmap_min) / (hmap_max_val - hmap_min) * 255).astype(np.uint8)
        else:
            hmap_norm = np.zeros_like(heatmap, dtype=np.uint8)
        _, hmap_thresh = cv2.threshold(hmap_norm, int(255 * 0.35), 255, cv2.THRESH_BINARY)
        combined_mask = cv2.bitwise_or(mask, hmap_thresh)

        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            # Score is elevated but mask is empty — use heatmap-peak fallback
            detections = [self._make_detection(score, is_anomalous, heatmap, None, image.shape)]
        else:
            # Filter and sort contours by area (largest first).
            # When the mask is nearly fully saturated (>80% of pixels set, i.e. OOD image),
            # skip individual contours and fall back to the heatmap-peak strategy so we pin
            # the box on the hottest region rather than returning a full-image bbox.
            mask_coverage = float(np.count_nonzero(combined_mask)) / combined_mask.size
            if mask_coverage > 0.80:
                # OOD / fully-saturated: use the densest heatmap region instead
                detections = [self._make_detection(score, is_anomalous, heatmap, None, image.shape)]
            else:
                # Cap any single contour at 25% of the image area. A contour that large
                # is a saturation artefact (heatmap blooms across most of the surface) rather
                # than a real defect boundary, so fall back to the heatmap-peak strategy,
                # which pins a box on the hottest region instead.
                max_contour_area = combined_mask.size * 0.25
                detections = []
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area < _MIN_CONTOUR_AREA_PX:
                        continue
                    if area > max_contour_area:
                        logger.debug(
                            "Contour area %.1f%% exceeds 25%% cap; using heatmap-peak fallback",
                            100.0 * area / combined_mask.size,
                        )
                        detections = [self._make_detection(score, is_anomalous, heatmap, None, image.shape)]
                        break
                    detections.append(
                        self._make_detection(score, is_anomalous, heatmap, cnt, image.shape)
                    )
                if not detections:
                    # All contours were below noise threshold — still flag if score says so
                    detections = [self._make_detection(score, is_anomalous, heatmap, None, image.shape)]

        return detections

    def get_version(self) -> str:
        return self._version

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _preprocess(self, bgr_image: np.ndarray) -> np.ndarray:
        """BGR uint8 → NCHW float32 batch of 2 (both slots identical), RGB, 0–1."""
        # BGR → RGB
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        # Resize to model input size
        resized = cv2.resize(rgb, (_INPUT_SIZE, _INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
        # HWC → CHW, float32, 0–1
        chw = resized.astype(np.float32) / 255.0
        chw = np.transpose(chw, (2, 0, 1))  # (3, 256, 256)
        # Duplicate into fixed batch of 2
        batch = np.stack([chw, chw], axis=0)  # (2, 3, 256, 256)
        return batch

    def _make_detection(
        self,
        score: float,
        is_anomalous: bool,
        heatmap: np.ndarray,
        contour: np.ndarray | None,
        original_shape: tuple[int, int, int] = (1024, 1024, 3),
    ) -> ModelDetection:
        """Build a ModelDetection from one contour (or full-image if contour is None).

        Args:
            score: Raw unclamped anomaly score
            is_anomalous: pred_label from model
            heatmap: Anomaly heatmap (256x256)
            contour: Detected contour in 256x256 space (or None)
            original_shape: Original image shape (H, W, C) for bbox scaling
        """
        bbox: BoundingBox | None = None
        if contour is not None:
            x, y, w, h = cv2.boundingRect(contour)

            # Scale bbox from 256x256 back to original image dimensions
            h_orig, w_orig = original_shape[:2]
            scale_x = w_orig / _INPUT_SIZE
            scale_y = h_orig / _INPUT_SIZE

            bbox = BoundingBox(
                x=int(x * scale_x),
                y=int(y * scale_y),
                w=int(w * scale_x),
                h=int(h * scale_y),
            )
        else:
            # Fallback: find the hottest contiguous region in the heatmap.
            # Blur the heatmap first so the peak lands on the centre of a dense
            # anomalous region rather than on a single high-value pixel at the edge.
            blurred = cv2.GaussianBlur(heatmap, (31, 31), 0)
            y_peak, x_peak = np.unravel_index(np.argmax(blurred), blurred.shape)
            box_size = 96
            x1 = max(0, x_peak - box_size // 2)
            y1 = max(0, y_peak - box_size // 2)
            x2 = min(_INPUT_SIZE, x_peak + box_size // 2)
            y2 = min(_INPUT_SIZE, y_peak + box_size // 2)

            h_orig, w_orig = original_shape[:2]
            scale_x = w_orig / _INPUT_SIZE
            scale_y = h_orig / _INPUT_SIZE

            bbox = BoundingBox(
                x=int(x1 * scale_x),
                y=int(y1 * scale_y),
                w=int((x2 - x1) * scale_x),
                h=int((y2 - y1) * scale_y),
            )

        # Determine outcome hint once, so callers don't need to re-implement the rules.
        # FAIL: pred_label True OR score >= fail_above
        # REVIEW: pass_below <= score < fail_above and pred_label False
        # PASS: score < pass_below and pred_label False  (not reached here — predict() returns [])
        outcome_hint = "FAIL" if is_anomalous or score >= self.fail_above else "REVIEW"

        # Compute heatmap statistics for domain warning
        hmap_max = float(heatmap.max())
        hmap_mean = float(heatmap.mean())
        hmap_std = float(heatmap.std())

        # Domain warning: detect out-of-distribution images
        # High score (>1.5) or very high heatmap max (>20) indicates OOD
        domain_warning = None
        if score > 1.5 or hmap_max > 20.0:
            domain_warning = "Result unreliable: image differs from trained leather"
        elif score > 1.2:
            domain_warning = "Result uncertain: score saturated above normal range"

        return ModelDetection(
            class_name="LEATHER_ANOMALY",
            confidence=min(score, 1.0),  # Clamp confidence display to [0,1]
            bounding_box=bbox,
            anomaly_score=score,  # Keep unclamped for analysis
            metadata={
                "pred_label": is_anomalous,
                "outcome_hint": outcome_hint,
                "heatmap_max": hmap_max,
                "heatmap_mean": hmap_mean,
                "heatmap_std": hmap_std,
                "raw_score": score,  # Store unclamped raw score
                "threshold_pass_below": self.pass_below,
                "threshold_fail_above": self.fail_above,
                "domain_warning": domain_warning,
            },
        )
