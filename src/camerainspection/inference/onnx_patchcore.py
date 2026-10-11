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

        # Use batch index 0
        score: float = float(score_arr[0])
        is_anomalous: bool = bool(label_arr[0])
        heatmap: np.ndarray = heatmap_arr[0, 0]  # (256, 256) float32
        mask: np.ndarray = mask_arr[0, 0].astype(np.uint8) * 255  # (256, 256) uint8

        logger.debug(
            "PatchCore result: score=%.4f  pred_label=%s", score, is_anomalous
        )

        # If PASS by both criteria, return nothing
        if not is_anomalous and score < self.pass_below:
            return []

        # Find contours in the thresholded mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            # Score is elevated but mask is empty — create a full-image detection
            detections = [self._make_detection(score, is_anomalous, heatmap, None)]
        else:
            detections = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < _MIN_CONTOUR_AREA_PX:
                    continue
                detections.append(
                    self._make_detection(score, is_anomalous, heatmap, cnt)
                )
            if not detections:
                # All contours were below noise threshold — still flag if score says so
                detections = [self._make_detection(score, is_anomalous, heatmap, None)]

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
    ) -> ModelDetection:
        """Build a ModelDetection from one contour (or full-image if contour is None)."""
        bbox: BoundingBox | None = None
        if contour is not None:
            x, y, w, h = cv2.boundingRect(contour)
            bbox = BoundingBox(x=x, y=y, w=w, h=h)

        # Determine outcome hint once, so callers don't need to re-implement the rules.
        # FAIL: pred_label True OR score >= fail_above
        # REVIEW: pass_below <= score < fail_above and pred_label False
        # PASS: score < pass_below and pred_label False  (not reached here — predict() returns [])
        outcome_hint = "FAIL" if is_anomalous or score >= self.fail_above else "REVIEW"

        return ModelDetection(
            class_name="LEATHER_ANOMALY",
            confidence=score,
            bounding_box=bbox,
            anomaly_score=score,
            metadata={
                "pred_label": is_anomalous,
                "outcome_hint": outcome_hint,
                "heatmap_max": float(heatmap.max()),
                "heatmap_mean": float(heatmap.mean()),
            },
        )
