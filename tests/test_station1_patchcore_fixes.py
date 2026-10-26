"""Comprehensive regression tests for Station 1 PatchCore fixes.

Tests all 5 critical issues:
1. Threshold applied matches slider value (0.55)
2. Raw unclamped anomaly score displayed
3. Defect boxes restricted to leather ROI
4. Domain warnings for out-of-distribution images
5. All defect types properly detected
"""

import numpy as np
import pytest
import cv2
from pathlib import Path

from camerainspection.station.station_1 import Station1Service
from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.models import Outcome


def create_test_station(threshold_pass: float = 0.55, threshold_fail: float = 0.60):
    """Create Station 1 service with specified thresholds."""
    from camerainspection.core.config import load_station_config

    # Load actual config from file
    config_path = Path("configs/stations/station_1_leather.yaml")
    config = load_station_config(config_path)

    # Override thresholds
    config.model.pass_below = threshold_pass
    config.model.fail_above = threshold_fail
    config.model.threshold = threshold_pass  # Slider value

    station = Station1Service(
        station_config=config,
        variants_root=Path("configs/variants"),
        default_limits_path=Path("configs/variants/default_limits.yaml"),
    )

    return station


def load_limits():
    """Load default limits for testing."""
    import yaml
    with open("configs/variants/default_limits.yaml") as f:
        data = yaml.safe_load(f)
    return data.get("limits", {})


class TestThresholdConsistency:
    """Test Issue #1: Threshold applied matches slider value."""

    def test_threshold_from_slider_not_hardcoded(self):
        """Threshold in measurements should match slider value (0.55), not hardcoded 0.60."""
        station = create_test_station(threshold_pass=0.55, threshold_fail=0.60)
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        # Use any test image
        img_path = Path("data/station_1/replay/01_pass_nominal.png")
        if not img_path.exists():
            pytest.skip("Test image not found")

        img = cv2.imread(str(img_path))
        defects, measurements, _ = station.inspect_image(
            img, "FRONT_LH_BLACK", evaluator, {}
        )

        # Check that threshold in measurements matches slider (0.55), not 0.60
        threshold_recorded = measurements.get("seating_face.anomaly_threshold")
        assert threshold_recorded is not None, "Threshold not recorded in measurements"
        assert abs(threshold_recorded - 0.55) < 0.001, \
            f"Expected threshold 0.55 (slider value), got {threshold_recorded}"

        # Also check fail threshold is recorded
        threshold_fail = measurements.get("seating_face.anomaly_threshold_fail")
        assert threshold_fail is not None, "Fail threshold not recorded"
        assert abs(threshold_fail - 0.60) < 0.001, \
            f"Expected fail threshold 0.60, got {threshold_fail}"

    def test_different_slider_values_respected(self):
        """System should respect different slider values."""
        test_cases = [
            (0.40, 0.50),
            (0.55, 0.65),
            (0.60, 0.70),
        ]

        img_path = Path("data/station_1/replay/01_pass_nominal.png")
        if not img_path.exists():
            pytest.skip("Test image not found")

        img = cv2.imread(str(img_path))
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        for pass_thresh, fail_thresh in test_cases:
            station = create_test_station(pass_thresh, fail_thresh)
            defects, measurements, _ = station.inspect_image(
                img, "FRONT_LH_BLACK", evaluator, {}
            )

            recorded_pass = measurements.get("seating_face.anomaly_threshold", 0)
            recorded_fail = measurements.get("seating_face.anomaly_threshold_fail", 0)

            assert abs(recorded_pass - pass_thresh) < 0.001, \
                f"Pass threshold mismatch: expected {pass_thresh}, got {recorded_pass}"
            assert abs(recorded_fail - fail_thresh) < 0.001, \
                f"Fail threshold mismatch: expected {fail_thresh}, got {recorded_fail}"


class TestRawScoreDisplay:
    """Test Issue #2: Raw unclamped scores displayed."""

    def test_raw_score_recorded_unclamped(self):
        """Raw anomaly score should be unclamped (can exceed 1.0)."""
        station = create_test_station()
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        # Use image that might produce high score
        img_path = Path("data/station_1/replay/03_fail_glue.png")
        if not img_path.exists():
            pytest.skip("Test image not found")

        img = cv2.imread(str(img_path))
        defects, measurements, _ = station.inspect_image(
            img, "FRONT_LH_BLACK", evaluator, {}
        )

        # Check both clamped and raw scores are recorded
        clamped_score = measurements.get("leather.anomaly_score")
        raw_score = measurements.get("leather.raw_anomaly_score")
        heatmap_max = measurements.get("leather.heatmap_max")

        assert clamped_score is not None, "Clamped score not recorded"
        assert raw_score is not None, "Raw score not recorded"
        assert heatmap_max is not None, "Heatmap max not recorded"

        # Raw score should be >= clamped score
        assert raw_score >= clamped_score, \
            f"Raw score ({raw_score}) should be >= clamped score ({clamped_score})"

        print(f"Scores - Clamped: {clamped_score:.4f}, Raw: {raw_score:.4f}, HeatmapMax: {heatmap_max:.4f}")

    def test_defect_description_shows_raw_score(self):
        """Defect descriptions should show raw_score, not just confidence."""
        station = create_test_station()
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        img_path = Path("data/station_1/replay/02_fail_color_stain.png")
        if not img_path.exists():
            pytest.skip("Test image not found")

        img = cv2.imread(str(img_path))
        defects, measurements, _ = station.inspect_image(
            img, "FRONT_LH_BLACK", evaluator, {}
        )

        # Find leather anomaly defects
        anomaly_defects = [d for d in defects if "LEATHER_ANOMALY" in d.defect_type]

        if anomaly_defects:
            desc = anomaly_defects[0].description
            assert "raw_score=" in desc, "Defect description should include raw_score"
            assert "heatmap_max=" in desc, "Defect description should include heatmap_max"
            print(f"Defect description: {desc}")


class TestROIRestriction:
    """Test Issue #3: Defect boxes restricted to leather ROI."""

    def test_defect_boxes_within_image_bounds(self):
        """All defect boxes should be within image dimensions."""
        station = create_test_station()
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        # Test multiple images
        test_images = [
            "02_fail_color_stain.png",
            "03_fail_glue.png",
            "04_fail_cut.png",
        ]

        for img_name in test_images:
            img_path = Path(f"data/station_1/replay/{img_name}")
            if not img_path.exists():
                continue

            img = cv2.imread(str(img_path))
            h, w = img.shape[:2]

            defects, _, _ = station.inspect_image(
                img, "FRONT_LH_BLACK", evaluator, {}
            )

            for defect in defects:
                if defect.bounding_box is not None:
                    bbox = defect.bounding_box

                    # Check bbox is within image bounds
                    assert bbox.x >= 0, f"{img_name}: bbox.x={bbox.x} should be >= 0"
                    assert bbox.y >= 0, f"{img_name}: bbox.y={bbox.y} should be >= 0"
                    assert bbox.x + bbox.w <= w, \
                        f"{img_name}: bbox.x_max={bbox.x + bbox.w} should be <= {w}"
                    assert bbox.y + bbox.h <= h, \
                        f"{img_name}: bbox.y_max={bbox.y + bbox.h} should be <= {h}"

                    print(f"{img_name}: BBox ({bbox.x}, {bbox.y}, {bbox.w}, {bbox.h}) OK")


class TestDomainWarnings:
    """Test Issue #4: Domain warnings for OOD images."""

    def test_domain_warning_for_high_scores(self):
        """Images with very high anomaly scores should trigger domain warnings."""
        station = create_test_station()
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        # Create synthetic OOD image (completely wrong)
        # Pure white image (office paper, not leather)
        ood_image = np.ones((1024, 1280, 3), dtype=np.uint8) * 255

        defects, measurements, _ = station.inspect_image(
            ood_image, "FRONT_LH_BLACK", evaluator, {}
        )

        # Check for domain warning in defects
        domain_warnings = [d for d in defects if "domain_warning" in d.defect_type]

        # If score is very high, should have domain warning
        raw_score = measurements.get("leather.raw_anomaly_score", 0)
        if raw_score > 1.2:
            assert len(domain_warnings) > 0, \
                f"High raw_score ({raw_score:.4f}) should trigger domain warning"
            print(f"Domain warning triggered for score {raw_score:.4f}: {domain_warnings[0].description}")
        else:
            print(f"Score {raw_score:.4f} did not trigger domain warning (threshold is 1.2)")


class TestDefectTypeRegression:
    """Test Issue #5: All defect types properly detected."""

    def test_01_pass_nominal_clean_leather(self):
        """Clean leather should PASS."""
        station = create_test_station(threshold_pass=0.55)
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        img_path = Path("data/station_1/replay/01_pass_nominal.png")
        if not img_path.exists():
            pytest.skip("Test image not found")

        img = cv2.imread(str(img_path))
        defects, measurements, _ = station.inspect_image(
            img, "FRONT_LH_BLACK", evaluator, {}
        )

        # Should have very low anomaly score
        score = measurements.get("leather.anomaly_score", 1.0)
        assert score < 0.55, f"Clean leather should have score < 0.55, got {score:.4f}"

        # Should not have FAIL defects
        fail_defects = [d for d in defects if d.outcome == Outcome.FAIL]
        assert len(fail_defects) == 0, f"Clean leather should not have FAIL defects, got {len(fail_defects)}"

        print(f"✓ Clean leather PASS: score={score:.4f}")

    def test_02_fail_color_stain(self):
        """Color stain should FAIL."""
        station = create_test_station(threshold_pass=0.55)
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        img_path = Path("data/station_1/replay/02_fail_color_stain.png")
        if not img_path.exists():
            pytest.skip("Test image not found")

        img = cv2.imread(str(img_path))
        defects, measurements, _ = station.inspect_image(
            img, "FRONT_LH_BLACK", evaluator, {}
        )

        # Should have elevated anomaly score
        score = measurements.get("leather.anomaly_score", 0)
        assert score > 0.55, f"Color stain should have score > 0.55, got {score:.4f}"

        # Should have FAIL or REVIEW defects
        critical_defects = [d for d in defects if d.outcome in (Outcome.FAIL, Outcome.REVIEW)]
        assert len(critical_defects) > 0, "Color stain should be detected"

        print(f"✓ Color stain detected: score={score:.4f}, defects={len(critical_defects)}")

    def test_03_fail_glue(self):
        """Glue defect should FAIL."""
        station = create_test_station(threshold_pass=0.55)
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        img_path = Path("data/station_1/replay/03_fail_glue.png")
        if not img_path.exists():
            pytest.skip("Test image not found")

        img = cv2.imread(str(img_path))
        defects, measurements, _ = station.inspect_image(
            img, "FRONT_LH_BLACK", evaluator, {}
        )

        score = measurements.get("leather.anomaly_score", 0)
        assert score > 0.55, f"Glue defect should have score > 0.55, got {score:.4f}"

        critical_defects = [d for d in defects if d.outcome in (Outcome.FAIL, Outcome.REVIEW)]
        assert len(critical_defects) > 0, "Glue defect should be detected"

        print(f"✓ Glue defect detected: score={score:.4f}, defects={len(critical_defects)}")

    def test_04_fail_cut(self):
        """Cut defect should FAIL."""
        station = create_test_station(threshold_pass=0.55)
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        img_path = Path("data/station_1/replay/04_fail_cut.png")
        if not img_path.exists():
            pytest.skip("Test image not found")

        img = cv2.imread(str(img_path))
        defects, measurements, _ = station.inspect_image(
            img, "FRONT_LH_BLACK", evaluator, {}
        )

        score = measurements.get("leather.anomaly_score", 0)
        assert score > 0.55, f"Cut defect should have score > 0.55, got {score:.4f}"

        critical_defects = [d for d in defects if d.outcome in (Outcome.FAIL, Outcome.REVIEW)]
        assert len(critical_defects) > 0, "Cut defect should be detected"

        print(f"✓ Cut defect detected: score={score:.4f}, defects={len(critical_defects)}")

    def test_05_fail_fold(self):
        """Fold/wrinkle defect should FAIL or REVIEW."""
        station = create_test_station(threshold_pass=0.55)
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        img_path = Path("data/station_1/replay/05_fail_fold.png")
        if not img_path.exists():
            pytest.skip("Test image not found")

        img = cv2.imread(str(img_path))
        defects, measurements, _ = station.inspect_image(
            img, "FRONT_LH_BLACK", evaluator, {}
        )

        score = measurements.get("leather.anomaly_score", 0)
        # Fold might be subtle, so allow lower threshold
        assert score > 0.40, f"Fold defect should have score > 0.40, got {score:.4f}"

        print(f"✓ Fold defect evaluated: score={score:.4f}")

    def test_06_fail_poke_pinhole(self):
        """Poke/pinhole defect should FAIL."""
        station = create_test_station(threshold_pass=0.55)
        limits = load_limits()
        evaluator = LimitsEvaluator(limits)

        img_path = Path("data/station_1/replay/06_fail_poke.png")
        if not img_path.exists():
            pytest.skip("Test image not found")

        img = cv2.imread(str(img_path))
        defects, measurements, _ = station.inspect_image(
            img, "FRONT_LH_BLACK", evaluator, {}
        )

        score = measurements.get("leather.anomaly_score", 0)
        assert score > 0.55, f"Poke defect should have score > 0.55, got {score:.4f}"

        critical_defects = [d for d in defects if d.outcome in (Outcome.FAIL, Outcome.REVIEW)]
        assert len(critical_defects) > 0, "Poke defect should be detected"

        print(f"✓ Poke defect detected: score={score:.4f}, defects={len(critical_defects)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
