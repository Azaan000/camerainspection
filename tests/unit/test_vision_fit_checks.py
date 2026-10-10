"""Unit tests for Phase 7 rule-based fit checks (shield gap, wrinkles, foam show-through)."""

import pytest

from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.models import Outcome
from camerainspection.vision.fit.fixtures_gen import (
    make_foam_showthrough_fixture,
    make_shield_gap_fixture,
    make_wrinkle_fixture,
)
from camerainspection.vision.fit.foam_showthrough import FoamShowthroughEngine
from camerainspection.vision.fit.shield_gap import ShieldGapEngine
from camerainspection.vision.fit.wrinkles import WrinkleDetectionEngine


@pytest.fixture
def fit_evaluator() -> LimitsEvaluator:
    # Based on default_limits.yaml
    limits = {
        "plastic": {
            "shield_gap_mm": {"nominal": 2.5, "pass_tol": 0.5, "fail_tol": 1.0},
        },
        "fit": {
            "wrinkle_puckering": {"review_on_any": True},
            "short_cover_foam_showthrough": {"fail_on_any": True},
        },
    }
    return LimitsEvaluator(limits)


def test_shield_gap_nominal_pass(fit_evaluator: LimitsEvaluator) -> None:
    # 17px at 0.15 mm/px ≈ 2.55mm (nominal 2.5mm ± 0.5)
    img = make_shield_gap_fixture(gap_width_px=17)
    meas = ShieldGapEngine.measure_gap(img, pixel_size_mm=0.15, axis="horizontal")

    assert abs(meas.mean_gap_mm - 2.5) < 0.3
    defect = fit_evaluator.evaluate_check(
        "plastic", "shield_gap_mm", meas.mean_gap_mm, nominal=2.5
    )
    assert defect.outcome == Outcome.PASS


def test_shield_gap_excessive_fail(fit_evaluator: LimitsEvaluator) -> None:
    # 35px at 0.15 mm/px = 5.25mm (dev 2.75mm > fail_tol=1.0)
    img = make_shield_gap_fixture(gap_width_px=35)
    meas = ShieldGapEngine.measure_gap(img, pixel_size_mm=0.15, axis="horizontal")

    assert meas.mean_gap_mm > 4.5
    defect = fit_evaluator.evaluate_check(
        "plastic", "shield_gap_mm", meas.mean_gap_mm, nominal=2.5
    )
    assert defect.outcome == Outcome.FAIL


def test_wrinkle_clean_surface_pass(fit_evaluator: LimitsEvaluator) -> None:
    img = make_wrinkle_fixture(has_wrinkle=False)
    detections = WrinkleDetectionEngine.detect_wrinkles(img, pixel_size_mm=0.15)
    assert len(detections) == 0

    defect = fit_evaluator.evaluate_check("fit", "wrinkle_puckering", False)
    assert defect.outcome == Outcome.PASS


def test_wrinkle_detected_review(fit_evaluator: LimitsEvaluator) -> None:
    # 60px crease = 9.0mm
    img = make_wrinkle_fixture(has_wrinkle=True, crease_length_px=60)
    detections = WrinkleDetectionEngine.detect_wrinkles(img, pixel_size_mm=0.15)

    assert len(detections) >= 1
    assert detections[0].length_mm >= 5.0

    defect = fit_evaluator.evaluate_check("fit", "wrinkle_puckering", True)
    assert defect.outcome == Outcome.REVIEW


def test_foam_showthrough_clean_pass(fit_evaluator: LimitsEvaluator) -> None:
    img = make_foam_showthrough_fixture(has_foam=False)
    defects = FoamShowthroughEngine.detect_foam(img, pixel_size_mm=0.15)
    assert len(defects) == 0

    res = fit_evaluator.evaluate_check("fit", "short_cover_foam_showthrough", False)
    assert res.outcome == Outcome.PASS


def test_foam_showthrough_detected_fail(fit_evaluator: LimitsEvaluator) -> None:
    # 40x25 px = 1000 px² ≈ 22.5 mm²
    img = make_foam_showthrough_fixture(has_foam=True, foam_width_px=40, foam_height_px=25)
    defects = FoamShowthroughEngine.detect_foam(img, pixel_size_mm=0.15)

    assert len(defects) >= 1
    assert defects[0].exposed_area_mm2 > 5.0

    res = fit_evaluator.evaluate_check("fit", "short_cover_foam_showthrough", True)
    assert res.outcome == Outcome.FAIL
