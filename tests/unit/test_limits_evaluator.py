"""Unit tests for OEM LimitsEvaluator."""

from pathlib import Path

from camerainspection.core.config import load_yaml
from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.models import Outcome


def test_range_check_evaluation() -> None:
    evaluator = LimitsEvaluator({})

    # pass_max = 3.0, fail_at = 5.0 (e.g., loose end mm)
    res_pass = evaluator.evaluate_range(2.5, pass_max=3.0, fail_at=5.0, defect_type="loose_end")
    assert res_pass.outcome == Outcome.PASS

    res_review = evaluator.evaluate_range(4.0, pass_max=3.0, fail_at=5.0, defect_type="loose_end")
    assert res_review.outcome == Outcome.REVIEW

    res_fail = evaluator.evaluate_range(5.2, pass_max=3.0, fail_at=5.0, defect_type="loose_end")
    assert res_fail.outcome == Outcome.FAIL

    # Boundary conditions
    assert evaluator.evaluate_range(3.0, 3.0, 5.0, "t").outcome == Outcome.PASS
    assert evaluator.evaluate_range(5.0, 3.0, 5.0, "t").outcome == Outcome.FAIL


def test_tolerance_check_evaluation() -> None:
    evaluator = LimitsEvaluator({})

    # nominal = 6.0, pass_tol = 0.5, fail_tol = 1.0 (stitches per inch)
    # PASS: [5.5, 6.5]
    # REVIEW: (5.0, 5.5) or (6.5, 7.0]
    # FAIL: < 5.0 or > 7.0

    assert (
        evaluator.evaluate_tolerance(
            6.2, nominal=6.0, pass_tol=0.5, fail_tol=1.0, defect_type="spi"
        ).outcome
        == Outcome.PASS
    )
    assert (
        evaluator.evaluate_tolerance(
            5.5, nominal=6.0, pass_tol=0.5, fail_tol=1.0, defect_type="spi"
        ).outcome
        == Outcome.PASS
    )
    assert (
        evaluator.evaluate_tolerance(
            6.8, nominal=6.0, pass_tol=0.5, fail_tol=1.0, defect_type="spi"
        ).outcome
        == Outcome.REVIEW
    )
    assert (
        evaluator.evaluate_tolerance(
            7.5, nominal=6.0, pass_tol=0.5, fail_tol=1.0, defect_type="spi"
        ).outcome
        == Outcome.FAIL
    )


def test_oem_default_limits_dispatch(default_limits_path: Path) -> None:
    limits_data = load_yaml(default_limits_path)["limits"]
    evaluator = LimitsEvaluator(limits_data)

    # Stitch skip length: pass_max=0, fail_at=5
    # Value 0.0 -> PASS
    assert evaluator.evaluate_check("stitch", "skip_length_mm", 0.0).outcome == Outcome.PASS
    # Value 2.0 -> REVIEW (in 0 < v < 5 band)
    assert evaluator.evaluate_check("stitch", "skip_length_mm", 2.0).outcome == Outcome.REVIEW
    # Value 6.0 -> FAIL
    assert evaluator.evaluate_check("stitch", "skip_length_mm", 6.0).outcome == Outcome.FAIL

    # Broken thread: fail_on_any: true
    assert evaluator.evaluate_check("stitch", "broken_thread", False).outcome == Outcome.PASS
    assert evaluator.evaluate_check("stitch", "broken_thread", True).outcome == Outcome.FAIL

    # Wrinkle / puckering: review_on_any: true
    assert evaluator.evaluate_check("fit", "wrinkle_puckering", False).outcome == Outcome.PASS
    assert evaluator.evaluate_check("fit", "wrinkle_puckering", True).outcome == Outcome.REVIEW

    # Mechanism lock sensor: required: true
    assert (
        evaluator.evaluate_check("mechanism", "lock_sensor_confirmed", True).outcome == Outcome.PASS
    )
    assert (
        evaluator.evaluate_check("mechanism", "lock_sensor_confirmed", False).outcome
        == Outcome.FAIL
    )


def test_fail_safe_on_missing_or_corrupt_rule() -> None:
    evaluator = LimitsEvaluator({})

    # Completely missing rule -> FAIL
    res_missing = evaluator.evaluate_check("non_existent_cat", "unknown_defect", 12.0)
    assert res_missing.outcome == Outcome.FAIL

    # Invalid non-numeric value for numeric rule -> FAIL
    limits = {"stitch": {"skip_length_mm": {"pass_max": 0, "fail_at": 5}}}
    evaluator2 = LimitsEvaluator(limits)
    res_corrupt = evaluator2.evaluate_check("stitch", "skip_length_mm", "corrupt_data")
    assert res_corrupt.outcome == Outcome.FAIL
