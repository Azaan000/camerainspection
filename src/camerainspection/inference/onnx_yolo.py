"""ONNX inference engine for YOLOv8 object detection models.

Model I/O contract (YOLOv8 ONNX export, opset 17, dynamic batch):
  Input  : "images"   float32  [N, 3, 640, 640]  NCHW, RGB 0-1
  Output : "output0"  float32  [N, num_classes+4, 8400]
           Each of the 8400 columns is a candidate box:
             [cx, cy, w, h, cls0_score, cls1_score, ...]  (centre-format, pixel coords)

Preprocessing:
  BGR → RGB, letterbox-resize to 640×640 (preserving aspect ratio),
  divide by 255.0.

Postprocessing:
  argmax over class scores → class_id + confidence.
  NMS (IoU 0.45) to suppress duplicate boxes.
  Coordinates are scaled back to original image size.

Class names must be provided at construction time and must match the
order the model was trained with:
  Station 2: ["broken_thread", "skip_stitch"]
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from camerainspection.core.models import BoundingBox
from camerainspection.inference.base import BaseInferenceEngine, ModelDetection

logger = logging.getLogger("inference.onnx_yolo")

# YOLOv8 standard input geometry
_INPUT_SIZE = 640
_IOU_THRESHOLD = 0.45


class OnnxYoloEngine(BaseInferenceEngine):
    """ONNX-runtime inference engine wrapping a YOLOv8 detection export.

    Parameters
    ----------
    class_names : list[str]
        Ordered class labels matching the training data.yaml names list.
    confidence_threshold : float
        Minimum score to keep a detection (default 0.50).
    iou_threshold : float
        NMS IoU threshold (default 0.45).
    providers : list[str] | None
        ONNX Runtime execution providers.  None → auto (CUDA → CPU).
    """

    def __init__(
        self,
        class_names: list[str],
        confidence_threshold: float = 0.50,
        iou_threshold: float = _IOU_THRESHOLD,
        providers: list[str] | None = None,
    ) -> None:
        if not class_names:
            raise ValueError("class_names must not be empty.")
        self.class_names = class_names
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self._providers = providers
        self._session: Any = None
        self._input_name: str = "images"
        self._weights_path: Path | None = None
        self._version: str = "onnx-yolo-unknown"

    # ------------------------------------------------------------------
    # BaseInferenceEngine interface
    # ------------------------------------------------------------------

    def load(self, weights_path: str | Path) -> None:
        """Load the ONNX model from disk."""
        try:
            import onnxruntime as ort  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "onnxruntime is not installed. "
                "Install it with: pip install onnxruntime"
            ) from exc

        path = Path(weights_path)
        if not path.exists():
            raise FileNotFoundError(f"ONNX model not found: {path}")

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
        self._version = f"onnx-yolo-{path.stem}"
        self._input_name = self._session.get_inputs()[0].name

        logger.info(
            "YOLOv8 ONNX model loaded from %s (input='%s', providers=%s, classes=%s)",
            path,
            self._input_name,
            self._session.get_providers(),
            self.class_names,
        )

    def predict(self, image: np.ndarray) -> list[ModelDetection]:
        """Run YOLOv8 detection on a single BGR image.

        Returns a list of ModelDetection instances above confidence_threshold.
        An empty list means no defects detected (PASS).
        """
        if self._session is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        orig_h, orig_w = image.shape[:2]

        # Preprocess: letterbox + normalise
        resized, scale, pad_x, pad_y = self._letterbox(image, _INPUT_SIZE)
        tensor = self._to_tensor(resized)  # [1, 3, 640, 640]

        # Inference
        raw = self._session.run(None, {self._input_name: tensor})
        output = raw[0]  # [1, num_classes+4, 8400]

        # Postprocess
        detections = self._postprocess(
            output[0],           # [num_classes+4, 8400]
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
            orig_w=orig_w,
            orig_h=orig_h,
        )

        logger.debug(
            "YOLOv8 predict: %d detection(s) above threshold %.2f",
            len(detections),
            self.confidence_threshold,
        )
        return detections

    def get_version(self) -> str:
        return self._version

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _letterbox(
        self,
        image: np.ndarray,
        target: int,
    ) -> tuple[np.ndarray, float, int, int]:
        """Resize image with letterboxing to preserve aspect ratio.

        Returns (resized_image, scale, pad_left, pad_top).
        scale is the ratio applied to both dimensions.
        """
        h, w = image.shape[:2]
        scale = min(target / w, target / h)
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))

        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Pad to target × target with grey (114)
        canvas = np.full((target, target, 3), 114, dtype=np.uint8)
        pad_x = (target - new_w) // 2
        pad_y = (target - new_h) // 2
        canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

        return canvas, scale, pad_x, pad_y

    def _to_tensor(self, bgr_image: np.ndarray) -> np.ndarray:
        """BGR uint8 HWC → float32 NCHW RGB [0, 1] with batch dim."""
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        chw = rgb.astype(np.float32) / 255.0
        chw = np.transpose(chw, (2, 0, 1))   # HWC → CHW
        return np.expand_dims(chw, axis=0)    # CHW → NCHW

    def _postprocess(
        self,
        output: np.ndarray,
        scale: float,
        pad_x: int,
        pad_y: int,
        orig_w: int,
        orig_h: int,
    ) -> list[ModelDetection]:
        """Decode YOLOv8 output tensor into ModelDetection list.

        output shape: [4 + num_classes, 8400]  (transposed from model output)
        """
        # YOLOv8 output is [4+nc, 8400] — transpose to [8400, 4+nc]
        preds = output.T   # [8400, 4+nc]

        boxes_cx = preds[:, 0]
        boxes_cy = preds[:, 1]
        boxes_w  = preds[:, 2]
        boxes_h  = preds[:, 3]
        class_scores = preds[:, 4:]   # [8400, nc]

        # Best class per box
        class_ids = np.argmax(class_scores, axis=1)          # [8400]
        confidences = class_scores[np.arange(len(class_ids)), class_ids]  # [8400]

        # Filter by confidence
        mask = confidences >= self.confidence_threshold
        if not mask.any():
            return []

        boxes_cx   = boxes_cx[mask]
        boxes_cy   = boxes_cy[mask]
        boxes_w    = boxes_w[mask]
        boxes_h    = boxes_h[mask]
        class_ids  = class_ids[mask]
        confidences = confidences[mask]

        # Convert cx,cy,w,h (letterboxed coords) → x1,y1,x2,y2 in original image space
        x1 = ((boxes_cx - boxes_w / 2) - pad_x) / scale
        y1 = ((boxes_cy - boxes_h / 2) - pad_y) / scale
        x2 = ((boxes_cx + boxes_w / 2) - pad_x) / scale
        y2 = ((boxes_cy + boxes_h / 2) - pad_y) / scale

        # Clamp to image bounds
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        # NMS per class
        detections: list[ModelDetection] = []
        for cls_id in np.unique(class_ids):
            cls_mask = class_ids == cls_id
            cls_boxes = np.stack([x1[cls_mask], y1[cls_mask],
                                  x2[cls_mask], y2[cls_mask]], axis=1).astype(np.float32)
            cls_scores_nms = confidences[cls_mask].astype(np.float32)

            indices = cv2.dnn.NMSBoxes(
                cls_boxes.tolist(),
                cls_scores_nms.tolist(),
                self.confidence_threshold,
                self.iou_threshold,
            )

            if indices is None or len(indices) == 0:
                continue

            # cv2.dnn.NMSBoxes returns shape (N,) or (N,1) depending on version
            indices = np.array(indices).flatten()

            cls_name = (
                self.class_names[int(cls_id)]
                if int(cls_id) < len(self.class_names)
                else f"class_{cls_id}"
            )

            for idx in indices:
                bx1, by1, bx2, by2 = cls_boxes[idx]
                bw = max(1, int(bx2 - bx1))
                bh = max(1, int(by2 - by1))
                conf = float(cls_scores_nms[idx])

                detections.append(
                    ModelDetection(
                        class_name=cls_name,
                        confidence=conf,
                        bounding_box=BoundingBox(
                            x=int(bx1),
                            y=int(by1),
                            w=bw,
                            h=bh,
                        ),
                        metadata={"class_id": int(cls_id)},
                    )
                )

        return detections
