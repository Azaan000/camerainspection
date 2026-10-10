"""Limits evaluation engine implementing OEM Range, Tolerance, and Fail-Safe rules."""

from __future__ import annotations

from typing import Any

from camerainspection.core.logging import get_logger
from camerainspection.core.models import DefectDetail, Outcome

logger = get_logger("limits")


class LimitsEvaluator:
    """Evaluates measurements against active variant limits.

    Safety Rule: When uncertain or encountering an unhandled check,
    the system MUST fail safe (return FAIL or REVIEW, never PASS).
    """

    def __init__(self, limits: dict[str, Any]) -> None:
        self.limits = limits

    def evaluate_range(
        self,
        value: float,
        pass_max: float,
        fail_at: float,
        defect_type: str,
        unit: str = "mm",
    ) -> DefectDetail:
        """Evaluate a scalar value against a range rule.

        - value <= pass_max -> PASS
        - pass_max < value < fail_at -> REVIEW
        - value >= fail_at -> FAIL
        """
        if value <= pass_max:
            outcome = Outcome.PASS
            desc = f"{defect_type} ({value:.2f} {unit}) within pass limit (<= {pass_max:.2f})"
        elif value < fail_at:
            outcome = Outcome.REVIEW
            desc = (
                f"{defect_type} ({value:.2f} {unit}) in review band "
                f"({pass_max:.2f} < value < {fail_at:.2f})"
            )
        else:
            outcome = Outcome.FAIL
            desc = f"{defect_type} ({value:.2f} {unit}) exceeds fail limit (>= {fail_at:.2f})"

        return DefectDetail(
            defect_type=defect_type,
            outcome=outcome,
            measured_value=value,
            unit=unit,
            description=desc,
        )

    def evaluate_tolerance(
        self,
        value: float,
        nominal: float,
        pass_tol: float,
        fail_tol: float,
        defect_type: str,
        unit: str = "mm",
    ) -> DefectDetail:
        """Evaluate deviation from nominal against tolerance bands.

        - deviation <= pass_tol -> PASS
        - pass_tol < deviation <= fail_tol -> REVIEW
        - deviation > fail_tol -> FAIL
        """
        deviation = abs(value - nominal)
        if deviation <= pass_tol:
            outcome = Outcome.PASS
            desc = (
                f"{defect_type} deviation {deviation:.2f} {unit} "
                f"(val={value:.2f}, nom={nominal:.2f}) within pass tolerance (<= {pass_tol:.2f})"
            )
        elif deviation <= fail_tol:
            outcome = Outcome.REVIEW
            desc = (
                f"{defect_type} deviation {deviation:.2f} {unit} "
                f"in review tolerance band ({pass_tol:.2f} < dev <= {fail_tol:.2f})"
            )
        else:
            outcome = Outcome.FAIL
            desc = (
                f"{defect_type} deviation {deviation:.2f} {unit} "
                f"exceeds fail tolerance (> {fail_tol:.2f})"
            )

        return DefectDetail(
            defect_type=defect_type,
            outcome=outcome,
            measured_value=value,
            nominal_value=nominal,
            unit=unit,
            description=desc,
        )

    def evaluate_boolean(
        self,
        detected: bool,
        rule: dict[str, Any],
        defect_type: str,
        description: str = "",
    ) -> DefectDetail:
        """Evaluate presence or binary defect condition."""
        if not detected:
            return DefectDetail(
                defect_type=defect_type,
                outcome=Outcome.PASS,
                description=f"{defect_type}: None detected (PASS)",
            )

        if rule.get("fail_on_any", False) or rule.get("fail_on_any_missing_or_wrong", False):
            outcome = Outcome.FAIL
            desc = description or f"Critical defect detected: {defect_type} (FAIL)"
        elif rule.get("review_on_any", False):
            outcome = Outcome.REVIEW
            desc = description or f"Uncertain defect detected: {defect_type} (REVIEW)"
        else:
            # Unhandled rule fails safe
            outcome = Outcome.FAIL
            desc = f"{defect_type}: Unhandled boolean rule flagged for safety (FAIL)"

        return DefectDetail(
            defect_type=defect_type,
            outcome=outcome,
            description=desc,
        )

    def evaluate_check(
        self,
        category: str,
        check_name: str,
        value: Any,
        nominal: float | None = None,
        sub_category: str | None = None,
    ) -> DefectDetail:
        """High-level generic evaluation dispatcher for category and check_name.

        Falls back safely to FAIL if check rule is missing or malformed.
        """
        cat_limits = self.limits.get(category, {})
        rule = cat_limits.get(check_name)

        if sub_category and isinstance(rule, dict) and sub_category in rule:
            rule = rule[sub_category]

        if not rule:
            logger.warning(
                f"No rule found for {category}.{check_name} (sub={sub_category}). Failing safe."
            )
            return DefectDetail(
                defect_type=f"{category}.{check_name}",
                outcome=Outcome.FAIL,
                description="Missing limit configuration; failed safe to FAIL.",
            )

        # Range rule: pass_max, fail_at
        if isinstance(rule, dict) and "pass_max" in rule and "fail_at" in rule:
            try:
                num_val = float(value)
                return self.evaluate_range(
                    value=num_val,
                    pass_max=float(rule["pass_max"]),
                    fail_at=float(rule["fail_at"]),
                    defect_type=f"{category}.{check_name}",
                )
            except (ValueError, TypeError):
                return DefectDetail(
                    defect_type=f"{category}.{check_name}",
                    outcome=Outcome.FAIL,
                    description=f"Invalid numeric value '{value}'; failed safe to FAIL.",
                )

        # Tolerance rule: pass_tol, fail_tol
        if isinstance(rule, dict) and "pass_tol" in rule and "fail_tol" in rule:
            if nominal is None:
                return DefectDetail(
                    defect_type=f"{category}.{check_name}",
                    outcome=Outcome.FAIL,
                    description="Nominal value missing for tolerance check; failed safe to FAIL.",
                )
            try:
                num_val = float(value)
                return self.evaluate_tolerance(
                    value=num_val,
                    nominal=nominal,
                    pass_tol=float(rule["pass_tol"]),
                    fail_tol=float(rule["fail_tol"]),
                    defect_type=f"{category}.{check_name}",
                )
            except (ValueError, TypeError):
                return DefectDetail(
                    defect_type=f"{category}.{check_name}",
                    outcome=Outcome.FAIL,
                    description=f"Invalid numeric value '{value}'; failed safe to FAIL.",
                )

        # Boolean rules
        if isinstance(rule, dict) and (
            "fail_on_any" in rule
            or "review_on_any" in rule
            or "fail_on_any_missing_or_wrong" in rule
            or "required" in rule
        ):
            if "required" in rule:
                is_ok = bool(value)
                outcome = Outcome.PASS if is_ok else Outcome.FAIL
                return DefectDetail(
                    defect_type=f"{category}.{check_name}",
                    outcome=outcome,
                    description=(
                        f"Required check passed: {check_name}"
                        if is_ok
                        else f"Required check missing/failed: {check_name}"
                    ),
                )
            is_detected = bool(value)
            return self.evaluate_boolean(
                detected=is_detected,
                rule=rule,
                defect_type=f"{category}.{check_name}",
            )

        # Fallback
        return DefectDetail(
            defect_type=f"{category}.{check_name}",
            outcome=Outcome.FAIL,
            description=f"Unhandled rule structure {rule}; failed safe to FAIL.",
        )
