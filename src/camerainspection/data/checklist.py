"""Automated audit tool validating that data collection meets OEM statistical thresholds."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from camerainspection.core.logging import get_logger

logger = get_logger("data.checklist")


class VariantCollectionAudit(BaseModel):
    variant_id: str
    good_seats_count: int
    defective_seats_count: int
    golden_image_present: bool
    meets_target: bool
    missing_requirements: list[str] = Field(default_factory=list)


class DataCollectionAuditor:
    """Verifies that an image collection satisfies OEM statistical sample size requirements."""

    MIN_GOOD_SAMPLES = 200  # 200-300 good seats requirement
    MIN_DEFECT_SAMPLES = 10

    @classmethod
    def audit_variant_collection(
        cls,
        variant_dir: Path,
        variant_id: str,
        captures_dir: Path,
    ) -> VariantCollectionAudit:
        """Inspect golden images and collected dataset counts."""
        missing = []

        # Check golden images
        golden_dir = variant_dir / "golden_images"
        golden_present = golden_dir.exists() and any(golden_dir.iterdir())
        if not golden_present:
            missing.append(f"Golden image directory missing or empty at {golden_dir}")

        # Scan captures for this variant
        var_captures = captures_dir / variant_id
        good_count = 0
        defect_count = 0

        if var_captures.exists():
            for p in var_captures.glob("**/*.json"):
                # Sidecar metadata contains seat info
                try:
                    import json
                    with open(p, encoding="utf-8") as f:
                        meta = json.load(f)
                    if "defect" in meta.get("notes", "").lower():
                        defect_count += 1
                    else:
                        good_count += 1
                except Exception:
                    pass

        if good_count < cls.MIN_GOOD_SAMPLES:
            missing.append(
                f"Insufficient good seats: {good_count} collected, minimum required is {cls.MIN_GOOD_SAMPLES}"
            )

        meets_target = len(missing) == 0

        return VariantCollectionAudit(
            variant_id=variant_id,
            good_seats_count=good_count,
            defective_seats_count=defect_count,
            golden_image_present=golden_present,
            meets_target=meets_target,
            missing_requirements=missing,
        )
