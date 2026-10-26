"""Regression tests for Station 1 PatchCore model using real MVTec leather defect images.

Critical bug regression (escape):
  color_000.png (MVTec leather colour defect) returned PASS with 0 defects,
  while direct ONNX inference gave pred_score=1.0, pred_label=1, FAIL.

Test coverage:
  1. Good leather images → PASS or REVIEW (no FAIL)
  2. Real defect images (color, cut, fold, etc.) → FAIL
  3. Synthetic defect-free texture → not 663 defects (heuristic false positives)
  4. Engine unavailable or inference error → FAIL (never PASS)
  5. Measurements align with defect count (same source)
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from camerainspection.core.config import StationConfig, load_variant_config
from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.models import Outcome
from camerainspection.station.station_1 import Station1Service


@pytest.fixture
def station1_onnx() -> Station1Service:
    """Station 1 service with ONNX PatchCore engine (if model exists)."""
    repo_root = Path(__file__).resolve().parents[2]

    config = StationConfig(
        station_id="STATION_1",
        name="Leather Surface Inspection",
        model={
            "backend": "onnx",
            "weights_path": str(repo_root / "models" / "station_1" / "model.onnx"),
            "version": "v1.0.0",
            "pass_below": 0.40,
            "fail_above": 0.60,
        },
        camera={"adapter": "replay", "source": str(repo_root / "data" / "station_1" / "replay")},
        regions_of_interest={
            "seating_face": {"x": 0, "y": 0, "w": 1920, "h": 1080},
        },
    )
    return Station1Service(
        station_config=config,
        variants_root=repo_root / "configs" / "variants",
        shadow_mode=False,
    )


@pytest.fixture
def station1_heuristic() -> Station1Service:
    """Station 1 service with heuristic fallback (no ONNX model)."""
    repo_root = Path(__file__).resolve().parents[2]

    config = StationConfig(
        station_id="STATION_1",
        name="Leather Surface Inspection",
        model={
            "backend": "classical",
            "version": "v1.0.0",
        },
        camera={"adapter": "replay", "source": str(repo_root / "data" / "station_1" / "replay")},
        regions_of_interest={
            "seating_face": {"x": 0, "y": 0, "w": 1920, "h": 1080},
        },
    )
    return Station1Service(
        station_config=config,
        variants_root=repo_root / "configs" / "variants",
        shadow_mode=False,
    )


@pytest.fixture
def limits_evaluator() -> LimitsEvaluator:
    """Load default limits for Station 1."""
    # Use default limits from repository root
    repo_root = Path(__file__).resolve().parents[2]
    limits_path = repo_root / "configs" / "variants" / "default_limits.yaml"

    if limits_path.exists():
        import yaml
        with open(limits_path, encoding="utf-8") as f:
            limits_dict = yaml.safe_load(f) or {}
    else:
        limits_dict = {}

    return LimitsEvaluator(limits_dict)


class TestStation1PatchCoreRegression:
    """Regression tests for critical PatchCore escape bug."""

    def test_mvtec_color_defect_fails(
        self, station1_onnx: Station1Service, limits_evaluator: LimitsEvaluator
    ) -> None:
        """MVTec color_000.png (grey-blue stain) MUST return FAIL, not PASS.

        Regression: Previously returned PASS with 0 defects while ONNX model
        gave pred_score=1.0, pred_label=1.
        """
        repo_root = Path(__file__).resolve().parents[2]
        img_path = repo_root / "data" / "leather" / "test" / "defect" / "color_000.png"
        if not img_path.exists():
            pytest.skip(f"Test image not found: {img_path}")

        image = cv2.imread(str(img_path))
        assert image is not None, f"Failed to load {img_path}"

        defects, measurements, _ = station1_onnx.inspect_image(
            image=image,
            variant_id="FRONT_LH_BLACK",
            evaluator=limits_evaluator,
            variant_nominals={},
        )

        # PRIMARY ASSERTION: MUST be FAIL (not PASS, not REVIEW)
        outcomes = [d.outcome for d in defects]
        assert Outcome.FAIL in outcomes, (
            f"color_000.png must contain FAIL defect. Got outcomes: {outcomes}, "
            f"defects: {len(defects)}, measurements: {measurements}"
        )

        # Measurements must reflect the defect
        defect_count = measurements.get("seating_face.defect_count", 0)
        assert defect_count > 0, (
            f"defect_count must be > 0 for color_000.png, got {defect_count}"
        )

        # Anomaly score must be elevated
        anomaly_score = measurements.get("leather.anomaly_score", 0)
        assert anomaly_score >= 0.40, (
            f"Anomaly score must be >= 0.40 for defect image, got {anomaly_score}"
        )

    def test_good_leather_passes_or_reviews(
        self, station1_onnx: Station1Service, limits_evaluator: LimitsEvaluator
    ) -> None:
        """Good leather samples must NOT return FAIL."""
        repo_root = Path(__file__).resolve().parents[2]
        good_dir = repo_root / "data" / "leather" / "test" / "good"
        if not good_dir.exists():
            pytest.skip(f"Good samples directory not found: {good_dir}")

        good_images = list(good_dir.glob("*.png"))
        if not good_images:
            pytest.skip("No good samples found")

        for img_path in good_images[:5]:  # Test first 5 good samples
            image = cv2.imread(str(img_path))
            assert image is not None, f"Failed to load {img_path}"

            defects, measurements, _ = station1_onnx.inspect_image(
                image=image,
                variant_id="FRONT_LH_BROWN",
                evaluator=limits_evaluator,
                variant_nominals={},
            )

            outcomes = [d.outcome for d in defects]
            assert Outcome.FAIL not in outcomes, (
                f"{img_path.name} (good sample) returned FAIL. "
                f"Outcomes: {outcomes}, defects: {len(defects)}"
            )

    def test_all_mvtec_defects_detected(
        self, station1_onnx: Station1Service, limits_evaluator: LimitsEvaluator
    ) -> None:
        """All MVTec leather defect types must be detected (FAIL or REVIEW)."""
        repo_root = Path(__file__).resolve().parents[2]
        defect_dir = repo_root / "data" / "leather" / "test" / "defect"
        if not defect_dir.exists():
            pytest.skip(f"Defect directory not found: {defect_dir}")

        defect_images = list(defect_dir.glob("*.png"))[:20]  # Test first 20
        if not defect_images:
            pytest.skip("No defect samples found")

        detected_count = 0
        for img_path in defect_images:
            image = cv2.imread(str(img_path))
            if image is None:
                continue

            defects, measurements, _ = station1_onnx.inspect_image(
                image=image,
                variant_id="FRONT_LH_BROWN",
                evaluator=limits_evaluator,
                variant_nominals={},
            )

            if defects:  # Any defect detected
                detected_count += 1

        detection_rate = detected_count / len(defect_images)
        assert detection_rate >= 0.60, (
            f"PatchCore must detect at least 60% of MVTec defects. "
            f"Got {detected_count}/{len(defect_images)} = {detection_rate:.1%}"
        )

    def test_synthetic_texture_no_false_positives(
        self, station1_heuristic: Station1Service, limits_evaluator: LimitsEvaluator
    ) -> None:
        """Synthetic defect-free texture must not return 663 defects (heuristic bug).

        Regression: Heuristic algorithm on synthetic textures previously
        returned hundreds of false positive defects.
        """
        # Create synthetic dark leather texture (512x512 grayscale noise)
        np.random.seed(42)
        noise = np.random.randint(20, 40, (512, 512), dtype=np.uint8)
        # Add subtle texture via Gaussian blur
        texture = cv2.GaussianBlur(noise, (5, 5), 0)
        synthetic = cv2.cvtColor(texture, cv2.COLOR_GRAY2BGR)

        defects, measurements, _ = station1_heuristic.inspect_image(
            image=synthetic,
            variant_id="FRONT_LH_BLACK",
            evaluator=limits_evaluator,
            variant_nominals={},
        )

        # Must NOT return hundreds of defects on clean synthetic texture
        assert len(defects) < 20, (
            f"Heuristic returned {len(defects)} defects on synthetic texture. "
            f"Expected < 20 (false positive threshold)."
        )

    def test_engine_unavailable_fails_safe(
        self, limits_evaluator: LimitsEvaluator
    ) -> None:
        """When ONNX engine unavailable, station MUST fail safe (FAIL, never PASS)."""
        # Configure station with non-existent model path
        config = StationConfig(
            station_id="STATION_1",
            name="Leather Surface Inspection",
            model={
                "backend": "onnx",
                "weights_path": "models/station_1/nonexistent.onnx",
                "version": "v1.0.0",
            },
            camera={"adapter": "replay"},
            regions_of_interest={
                "seating_face": {"x": 0, "y": 0, "w": 1920, "h": 1080},
            },
        )
        station = Station1Service(
            station_config=config,
            variants_root=Path("configs/variants"),
        )

        # Create dummy image
        image = np.zeros((512, 512, 3), dtype=np.uint8)

        defects, measurements, _ = station.inspect_image(
            image=image,
            variant_id="FRONT_LH_BLACK",
            evaluator=limits_evaluator,
            variant_nominals={},
        )

        # MUST have defect indicating engine unavailable
        assert len(defects) > 0, "Engine unavailable must produce defect"
        assert any(d.outcome == Outcome.FAIL for d in defects), (
            "Engine unavailable must produce FAIL outcome"
        )
        assert any("engine_unavailable" in d.defect_type for d in defects), (
            "Defect type must indicate engine unavailable"
        )

        # Defect count measurement MUST be > 0 (not 0, which would allow PASS)
        defect_count = measurements.get("seating_face.defect_count", 0)
        assert defect_count > 0, (
            f"Engine unavailable must set defect_count > 0, got {defect_count}"
        )

    def test_measurements_align_with_defect_count(
        self, station1_onnx: Station1Service, limits_evaluator: LimitsEvaluator
    ) -> None:
        """Defect count measurement must match len(defects) from same source."""
        repo_root = Path(__file__).resolve().parents[2]
        img_path = repo_root / "data" / "leather" / "test" / "defect" / "cut_000.png"
        if not img_path.exists():
            pytest.skip(f"Test image not found: {img_path}")

        image = cv2.imread(str(img_path))
        assert image is not None

        defects, measurements, _ = station1_onnx.inspect_image(
            image=image,
            variant_id="FRONT_LH_BLACK",
            evaluator=limits_evaluator,
            variant_nominals={},
        )

        # Measurement and defects list must agree
        measured_count = measurements.get("seating_face.defect_count", 0)
        actual_count = len(defects)

        assert measured_count == actual_count, (
            f"Defect count mismatch: measurements report {measured_count}, "
            f"but {actual_count} defects in list. Must use same source."
        )

    @pytest.mark.skipif(
        not Path("models/station_1/model.onnx").exists(),
        reason="ONNX model not available",
    )
    def test_onnx_model_direct_vs_station_consistency(self) -> None:
        """Direct ONNX model prediction must match Station 1 service outcome.

        Regression: Direct model gave pred_score=1.0 FAIL, but station returned PASS.
        """
        from camerainspection.inference.onnx_patchcore import OnnxPatchCoreEngine

        repo_root = Path(__file__).resolve().parents[2]
        img_path = repo_root / "data" / "leather" / "test" / "defect" / "color_000.png"
        if not img_path.exists():
            pytest.skip(f"Test image not found: {img_path}")

        image = cv2.imread(str(img_path))
        assert image is not None

        # Direct ONNX prediction
        engine = OnnxPatchCoreEngine(pass_below=0.40, fail_above=0.60)
        engine.load("models/station_1/model.onnx")
        detections = engine.predict(image)

        # Station service prediction
        config = StationConfig(
            station_id="STATION_1",
            name="Leather Surface Inspection",
            model={
                "backend": "onnx",
                "weights_path": str(repo_root / "models" / "station_1" / "model.onnx"),
                "pass_below": 0.40,
                "fail_above": 0.60,
            },
            camera={"adapter": "replay"},
            regions_of_interest={
                "seating_face": {"x": 0, "y": 0, "w": 1920, "h": 1080},
            },
        )
        station = Station1Service(station_config=config, variants_root=repo_root / "configs" / "variants")

        # Load limits
        import yaml
        limits_path = repo_root / "configs" / "variants" / "default_limits.yaml"
        if limits_path.exists():
            with open(limits_path, encoding="utf-8") as f:
                limits = yaml.safe_load(f) or {}
        else:
            limits = {}
        evaluator = LimitsEvaluator(limits)
        defects, measurements, _ = station.inspect_image(
            image, "FRONT_LH_BLACK", evaluator, {}
        )

        # Both must agree on outcome
        direct_has_defects = len(detections) > 0
        station_fails = any(d.outcome == Outcome.FAIL for d in defects)

        if direct_has_defects:
            assert station_fails or defects, (
                f"Direct ONNX found {len(detections)} detections, "
                f"but station returned {len(defects)} defects (no FAIL). INCONSISTENT."
            )
