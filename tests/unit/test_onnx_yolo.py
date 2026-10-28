"""Regression tests for OnnxYoloEngine NMS box format fix (T3).

The fix changed NMSBoxes input from [x1,y1,x2,y2] to [x,y,w,h].
"""
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock

from camerainspection.inference.onnx_yolo import OnnxYoloEngine


def _make_engine_with_fake_output(raw_output: np.ndarray) -> OnnxYoloEngine:
    """Build an OnnxYoloEngine with a mocked session returning raw_output."""
    engine = OnnxYoloEngine(
        class_names=["broken_thread"],
        confidence_threshold=0.5,
        iou_threshold=0.35,
    )
    session_mock = MagicMock()
    # _session.run(None, {...}) returns [raw_output]
    session_mock.run.return_value = [raw_output]
    session_mock.get_inputs.return_value = [MagicMock(name="images")]
    engine._session = session_mock
    engine._input_name = "images"
    return engine


def _build_output_tensor(boxes_xyxy_640: list[tuple[float, float, float, float]],
                          scores: list[float]) -> np.ndarray:
    """Build a fake YOLOv8 output tensor [1, 5, 8400] with given boxes.

    Boxes are in 640-space xyxy; converted to cxcywh for the tensor.
    Class 0 score = score; rest 0.
    """
    n_classes = 1
    output = np.zeros((1, 4 + n_classes, 8400), dtype=np.float32)
    for i, ((x1, y1, x2, y2), score) in enumerate(zip(boxes_xyxy_640, scores)):
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        w = x2 - x1
        h = y2 - y1
        output[0, 0, i] = cx
        output[0, 1, i] = cy
        output[0, 2, i] = w
        output[0, 3, i] = h
        output[0, 4, i] = score  # class 0 score
    return output


class TestNmsBoxFormat:
    """Tests that verify NMS correctly uses xywh format (T3 fix)."""

    def test_two_non_overlapping_boxes_both_survive(self):
        """Two boxes far apart (IoU ≈ 0) must both survive NMS."""
        # Box 1 at x=0..40, y=0..40 (in 640 space)
        # Box 2 at x=600..640, y=0..40 (in 640 space) — no overlap
        output = _build_output_tensor(
            boxes_xyxy_640=[(20, 20, 60, 60), (600, 20, 640, 60)],
            scores=[0.9, 0.85],
        )
        engine = _make_engine_with_fake_output(output)
        # 640x640 image — scale=1.0, no padding
        image = np.zeros((640, 640, 3), dtype=np.uint8)
        detections = engine.predict(image)
        assert len(detections) == 2, (
            f"Expected both non-overlapping boxes to survive NMS, got {len(detections)}"
        )

    def test_two_identical_overlapping_boxes_one_survives(self):
        """Two boxes at the same location (IoU=1.0) — only 1 should survive NMS."""
        output = _build_output_tensor(
            boxes_xyxy_640=[(100, 100, 200, 200), (100, 100, 200, 200)],
            scores=[0.9, 0.85],
        )
        engine = _make_engine_with_fake_output(output)
        image = np.zeros((640, 640, 3), dtype=np.uint8)
        detections = engine.predict(image)
        assert len(detections) == 1, (
            f"Expected overlapping boxes to be merged to 1 by NMS, got {len(detections)}"
        )

    def test_output_bbox_coordinates_are_correct(self):
        """Ensure the surviving detection has correct xyxy→xywh BoundingBox (not corrupted by NMS fix)."""
        # Single box at (50,60,150,160) in 640 space
        output = _build_output_tensor(
            boxes_xyxy_640=[(50, 60, 150, 160)],
            scores=[0.9],
        )
        engine = _make_engine_with_fake_output(output)
        image = np.zeros((640, 640, 3), dtype=np.uint8)
        detections = engine.predict(image)
        assert len(detections) == 1
        bb = detections[0].bounding_box
        assert bb is not None
        # x,y should be near 50,60; w,h near 100,100
        assert abs(bb.x - 50) <= 2, f"Expected x≈50, got {bb.x}"
        assert abs(bb.y - 60) <= 2, f"Expected y≈60, got {bb.y}"
        assert abs(bb.w - 100) <= 2, f"Expected w≈100, got {bb.w}"
        assert abs(bb.h - 100) <= 2, f"Expected h≈100, got {bb.h}"

    def test_partially_overlapping_boxes_above_iou_threshold_merged(self):
        """Two boxes with IoU well above threshold (0.35) → 1 survives."""
        # Box1: (100,100,200,200), Box2: (105,105,205,205) — heavily overlapping
        output = _build_output_tensor(
            boxes_xyxy_640=[(100, 100, 200, 200), (105, 105, 205, 205)],
            scores=[0.9, 0.85],
        )
        engine = _make_engine_with_fake_output(output)
        image = np.zeros((640, 640, 3), dtype=np.uint8)
        detections = engine.predict(image)
        assert len(detections) == 1, (
            f"Heavily overlapping boxes should merge to 1, got {len(detections)}"
        )
