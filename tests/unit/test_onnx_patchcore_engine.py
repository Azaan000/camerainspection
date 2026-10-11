"""Unit tests for OnnxPatchCoreEngine and Station1Service ONNX path.

No real model is required — a fake engine is used for all station-level tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from camerainspection.core.config import StationModelConfig  # noqa: F401
from camerainspection.core.models import Outcome
from camerainspection.inference.base import ModelDetection

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_detection(score: float, pred_label: bool, outcome_hint: str) -> ModelDetection:
    """Build a minimal ModelDetection as the real engine would produce."""
    return ModelDetection(
        class_name="LEATHER_ANOMALY",
        confidence=score,
        bounding_box=None,
        anomaly_score=score,
        metadata={
            "pred_label": pred_label,
            "outcome_hint": outcome_hint,
            "heatmap_max": score,
            "heatmap_mean": score / 2,
        },
    )


def _make_station1(
    pass_below: float = 0.40,
    fail_above: float = 0.60,
    injected_engine: Any = None,
) -> Any:
    """Build a Station1Service with an in-memory config and optional injected engine."""
    from camerainspection.core.config import (
        CameraConfig,
        StationConfig,
        StationModelConfig,
        TriggerConfig,
    )
    from camerainspection.station.station_1 import Station1Service

    model_cfg = StationModelConfig(
        backend="onnx",
        weights_path="models/station_1/model.onnx",
        pass_below=pass_below,
        fail_above=fail_above,
    )
    cam_cfg = CameraConfig(name="main", view="main", adapter="synthetic", pixel_size_mm=0.18)
    st_cfg = StationConfig(
        station_id="STATION_1",
        name="Test Station 1",
        camera=cam_cfg,
        model=model_cfg,
        trigger=TriggerConfig(timeout_s=5.0),
    )
    return Station1Service(
        station_config=st_cfg,
        variants_root=Path("configs/variants"),
        inference_engine=injected_engine,
    )


# ---------------------------------------------------------------------------
# Fix 1 — StationModelConfig thresholds are parsed from YAML / constructor
# ---------------------------------------------------------------------------


def test_station_1_thresholds_reach_model_config() -> None:
    """pass_below and fail_above are real fields on StationModelConfig (not dropped by pydantic)."""
    cfg = StationModelConfig(backend="onnx", pass_below=0.35, fail_above=0.55)
    assert cfg.pass_below == pytest.approx(0.35)
    assert cfg.fail_above == pytest.approx(0.55)


def test_station_model_config_defaults() -> None:
    """Defaults are 0.40 / 0.60."""
    cfg = StationModelConfig()
    assert cfg.pass_below == pytest.approx(0.40)
    assert cfg.fail_above == pytest.approx(0.60)


def test_station_model_config_invalid_thresholds() -> None:
    """pass_below >= fail_above must raise ValueError."""
    with pytest.raises((ValueError, Exception)):
        StationModelConfig(pass_below=0.60, fail_above=0.40)

    with pytest.raises((ValueError, Exception)):
        StationModelConfig(pass_below=0.50, fail_above=0.50)


# ---------------------------------------------------------------------------
# Fix 2 — Three outcome rules live in the engine via outcome_hint
# ---------------------------------------------------------------------------


def test_outcome_hint_fail_when_pred_label_true() -> None:
    """Engine sets outcome_hint=FAIL when pred_label is True regardless of score."""
    from camerainspection.inference.onnx_patchcore import OnnxPatchCoreEngine

    engine = OnnxPatchCoreEngine(pass_below=0.40, fail_above=0.60)
    det = engine._make_detection(score=0.30, is_anomalous=True, heatmap=np.zeros((256, 256)), contour=None)
    assert det.metadata["outcome_hint"] == "FAIL"


def test_outcome_hint_fail_when_score_above_fail_above() -> None:
    """Engine sets outcome_hint=FAIL when score >= fail_above, even if pred_label is False."""
    from camerainspection.inference.onnx_patchcore import OnnxPatchCoreEngine

    engine = OnnxPatchCoreEngine(pass_below=0.40, fail_above=0.60)
    # score=0.65, pred_label=False -> FAIL
    det = engine._make_detection(score=0.65, is_anomalous=False, heatmap=np.zeros((256, 256)), contour=None)
    assert det.metadata["outcome_hint"] == "FAIL"
    assert det.metadata["pred_label"] is False


def test_outcome_hint_review_in_band() -> None:
    """Engine sets outcome_hint=REVIEW when pass_below <= score < fail_above and pred_label False."""
    from camerainspection.inference.onnx_patchcore import OnnxPatchCoreEngine

    engine = OnnxPatchCoreEngine(pass_below=0.40, fail_above=0.60)
    # score=0.47, pred_label=False -> REVIEW
    det = engine._make_detection(score=0.47, is_anomalous=False, heatmap=np.zeros((256, 256)), contour=None)
    assert det.metadata["outcome_hint"] == "REVIEW"
    assert det.metadata["pred_label"] is False


# ---------------------------------------------------------------------------
# Fix 2 — Station1Service maps outcome_hint to Outcome correctly
# ---------------------------------------------------------------------------


def _run_onnx_analyze(station: Any, detections: list[ModelDetection]) -> tuple:
    """Drive _analyze_surface_onnx with a fake engine returning given detections."""
    station._onnx_engine = MagicMock()
    station._onnx_engine.predict.return_value = detections
    station._onnx_loaded = True
    image = np.full((480, 640, 3), 128, dtype=np.uint8)
    return station._analyze_surface_onnx(image=image, camera_name="main", view="main", pixel_size_mm=0.18)


def test_station_outcome_fail_when_outcome_hint_fail() -> None:
    """Station produces Outcome.FAIL when detection carries outcome_hint=FAIL."""
    station = _make_station1()
    det = _make_detection(score=0.65, pred_label=False, outcome_hint="FAIL")
    defects, _, _ = _run_onnx_analyze(station, [det])
    assert len(defects) == 1
    assert defects[0].outcome == Outcome.FAIL


def test_station_outcome_review_when_outcome_hint_review() -> None:
    """Station produces Outcome.REVIEW when detection carries outcome_hint=REVIEW."""
    station = _make_station1()
    det = _make_detection(score=0.47, pred_label=False, outcome_hint="REVIEW")
    defects, _, _ = _run_onnx_analyze(station, [det])
    assert len(defects) == 1
    assert defects[0].outcome == Outcome.REVIEW


def test_station_outcome_pass_when_no_detections() -> None:
    """Station produces no defects (PASS) when engine returns empty list."""
    station = _make_station1()
    defects, _, _ = _run_onnx_analyze(station, [])
    assert defects == []


def test_station_score_065_pred_label_false_is_fail() -> None:
    """score=0.65 with pred_label=False must produce FAIL (fail_above=0.60)."""
    station = _make_station1(pass_below=0.40, fail_above=0.60)
    det = _make_detection(score=0.65, pred_label=False, outcome_hint="FAIL")
    defects, measurements, _ = _run_onnx_analyze(station, [det])
    assert defects[0].outcome == Outcome.FAIL
    assert measurements["leather.anomaly_score"] == pytest.approx(0.65)


def test_station_score_047_pred_label_false_is_review() -> None:
    """score=0.47 with pred_label=False must produce REVIEW (pass_below=0.40, fail_above=0.60)."""
    station = _make_station1(pass_below=0.40, fail_above=0.60)
    det = _make_detection(score=0.47, pred_label=False, outcome_hint="REVIEW")
    defects, measurements, _ = _run_onnx_analyze(station, [det])
    assert defects[0].outcome == Outcome.REVIEW
    assert measurements["leather.anomaly_score"] == pytest.approx(0.47)


# ---------------------------------------------------------------------------
# Fix 3 — Injected engine is used; no second load happens
# ---------------------------------------------------------------------------


def test_injected_engine_is_used_directly() -> None:
    """When inference_engine is injected, _get_onnx_engine returns it without loading."""
    fake_engine = MagicMock()
    station = _make_station1(injected_engine=fake_engine)

    # _onnx_loaded should already be True after __init__
    assert station._onnx_loaded is True
    assert station._onnx_engine is fake_engine

    result = station._get_onnx_engine()
    assert result is fake_engine
    # load() must never have been called on the fake engine
    fake_engine.load.assert_not_called()


def test_no_second_load_when_engine_injected() -> None:
    """OnnxPatchCoreEngine.load is never called when an engine is pre-injected."""
    fake_engine = MagicMock()
    station = _make_station1(injected_engine=fake_engine)

    # Call _get_onnx_engine multiple times — still no load
    for _ in range(3):
        engine = station._get_onnx_engine()
        assert engine is fake_engine

    fake_engine.load.assert_not_called()


def test_lazy_load_attempted_when_no_engine_injected() -> None:
    """When no engine is injected, _get_onnx_engine tries to load (and handles failure gracefully)."""
    station = _make_station1(injected_engine=None)
    assert station._onnx_loaded is False

    # Patch load to raise so we don't need a real model file
    _patch_target = "camerainspection.inference.onnx_patchcore.OnnxPatchCoreEngine.load"
    with patch(_patch_target, side_effect=FileNotFoundError("no model")):
        engine = station._get_onnx_engine()

    # After the attempt, _onnx_loaded is True (won't retry) and engine is None (fail safe)
    assert station._onnx_loaded is True
    assert engine is None
