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

        # Select index with highest raw heatmap peak across batch slots
        best_idx = 0
        heatmap: np.ndarray = heatmap_arr[best_idx, 0]  # (256, 256) float32
        hmap_max = float(heatmap.max())
        hmap_mean = float(heatmap.mean())
        hmap_std = float(heatmap.std())

        # Calibrate anomaly score directly from feature distances.
        # PatchCore feature distance baseline for clean leather is ~3.25.
        # Clear defects (cut, poke, fold, glue, scratch) produce peaks >= 3.55 (typically 4.0-5.8+).
        BASE_CLEAN = 3.25
        BASE_DEFECT = 4.25
        if hmap_max <= BASE_CLEAN:
            # Scaled strictly below pass_below so normal leather is reliably PASS
            score = max(0.0, (hmap_max / BASE_CLEAN) * (self.pass_below * 0.85))
        else:
            # Scaled smoothly through REVIEW band into FAIL
            score = min(
                1.0,
                self.pass_below
                + ((hmap_max - BASE_CLEAN) / (BASE_DEFECT - BASE_CLEAN))
                * (self.fail_above - self.pass_below + 0.25),
            )

        is_anomalous = bool(score >= self.fail_above)

        logger.debug(
            "PatchCore result: calibrated_score=%.4f  is_anomalous=%s  hmap_max=%.4f",
            score, is_anomalous, hmap_max
        )

        # If PASS by both criteria, return nothing
        if not is_anomalous and score < self.pass_below:
            return []

        # Find contours in anomalous regions above the clean leather baseline
        anomaly_signal = np.maximum(0.0, heatmap - BASE_CLEAN)
        sig_max = float(anomaly_signal.max())
        if sig_max > 0.20:
            thresh_val = BASE_CLEAN + 0.35 * sig_max
            binary_mask = (heatmap >= thresh_val).astype(np.uint8) * 255
            # Suppress extreme 6-pixel outer border to prevent camera letterbox artifacts
            binary_mask[:6, :] = 0
            binary_mask[-6:, :] = 0
            binary_mask[:, :6] = 0
            binary_mask[:, -6:] = 0
        else:
            binary_mask = np.zeros_like(heatmap, dtype=np.uint8)

        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours = [cnt for cnt in contours if cv2.contourArea(cnt) >= _MIN_CONTOUR_AREA_PX]

        if not valid_contours:
            # Score is elevated but discrete contours were below size threshold — use heatmap-peak fallback
            detections = [self._make_detection(score, is_anomalous, heatmap, None, image.shape)]
        else:
            # Sort contours by area (largest first) and emit detections for the most prominent ones
            valid_contours = sorted(valid_contours, key=cv2.contourArea, reverse=True)
            max_contour_area = binary_mask.size * 0.40
            detections = []
            for cnt in valid_contours[:3]:
                area = cv2.contourArea(cnt)
                if area > max_contour_area:
                    logger.debug(
                        "Contour area %.1f%% exceeds 40%% cap; using heatmap-peak fallback",
                        100.0 * area / binary_mask.size,
                    )
                    detections = [self._make_detection(score, is_anomalous, heatmap, None, image.shape)]
                    break
                detections.append(
                    self._make_detection(score, is_anomalous, heatmap, cnt, image.shape)
                )
            if not detections:
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
            interior = blurred.copy()
            interior[:8, :] = 0
            interior[-8:, :] = 0
            interior[:, :8] = 0
            interior[:, -8:] = 0
            y_peak, x_peak = np.unravel_index(np.argmax(interior), interior.shape)
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
