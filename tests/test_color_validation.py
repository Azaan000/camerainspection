"""Tests for Station 1 material handling — any leather color is accepted.

The old variant color-restriction logic has been removed. PatchCore itself is
color-agnostic (it learns leather texture, not specific colors), so new leather
colors require zero reconfiguration. These tests verify that:

  1. Any valid leather color (black, brown, grey, cream) is accepted — no
     false `station.variant_color_mismatch` defect is raised.
  2. A non-leather / blank / solid-color frame still fails (caught by
     ImageQualityGuard + PatchCore's domain warning), not by a color check.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from camerainspection.core.config import load_station_config
from camerainspection.core.limits import LimitsEvaluator
from camerainspection.core.models import Outcome
from camerainspection.station.station_1 import Station1Service


def _make_station(threshold: float = 0.45) -> Station1Service:
    repo_root = Path(__file__).resolve().parents[1]
    station_cfg = load_station_config(repo_root / "configs" / "stations" / "station_1_leather.yaml")
    station_cfg.model.threshold = threshold
    return Station1Service(
        station_config=station_cfg,
        variants_root=repo_root / "configs" / "variants",
        default_limits_path=repo_root / "configs" / "variants" / "default_limits.yaml",
    )


def _load_limits() -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    import yaml
    with open(repo_root / "configs" / "variants" / "default_limits.yaml") as f:
        data = yaml.safe_load(f)
    return data.get("limits", {})


def _lab_to_bgr(lab: tuple[int, int, int], size=(200, 200)) -> np.ndarray:
    """Create a uniform-color BGR image from LAB values (with light grain so PatchCore sees texture)."""
    lab_img = np.zeros((*size, 3), dtype=np.uint8)
    lab_img[:, :] = lab
    bgr = cv2.cvtColor(lab_img, cv2.COLOR_LAB2BGR)
    # Add subtle grain so the image isn't a perfectly flat frame (std_dev > 0)
    rng = np.random.default_rng(42)
    noise = rng.integers(-3, 4, size + (3,), dtype=np.int16)
    return np.clip(bgr.astype(np.int16) + noise, 0, 255).astype(np.uint8)


class TestAnyColorAccepted:
    """Any valid leather color must pass through without a color-mismatch defect."""

    @pytest.mark.parametrize("variant_id", ["FRONT_LH_BLACK", "FRONT_RH_BROWN", "FRONT_LH_GREY"])
    def test_no_color_mismatch_defect(self, variant_id: str) -> None:
        """A black leather image inspected under any variant ID must NOT raise a color mismatch defect."""
        station = _make_station()
        evaluator = LimitsEvaluator(_load_limits())

        # Black leather (low L, neutral chroma) with grain
        img = _lab_to_bgr((30, 128, 128))

        defects, measurements, _ = station.inspect_image(
            image=img,
            variant_id=variant_id,
            evaluator=evaluator,
            variant_nominals={},
        )

        # No defect should mention color mismatch — color restriction is gone
        color_defects = [d for d in defects if "color_mismatch" in d.defect_type.lower()]
        assert not color_defects, (
            f"Color mismatch defect raised for {variant_id} on black leather: "
            f"{[d.defect_type for d in color_defects]}"
        )

    def test_brown_leather_not_rejected_as_color_mismatch(self) -> None:
        """Brown leather under a BLACK variant must not get a variant_color_mismatch defect."""
        station = _make_station()
        evaluator = LimitsEvaluator(_load_limits())

        # Brown leather (medium L, red + yellow chroma) with grain
        img = _lab_to_bgr((120, 145, 150))

        defects, measurements, _ = station.inspect_image(
            image=img,
            variant_id="FRONT_LH_BLACK",
            evaluator=evaluator,
            variant_nominals={},
        )

        color_defects = [d for d in defects if "color_mismatch" in d.defect_type.lower()]
        assert not color_defects, (
            f"Brown-as-BLOCK raised a color mismatch defect: {[d.defect_type for d in color_defects]}"
        )


class TestBlankFrameStillFails:
    """A completely blank / solid-color frame must still fail (via ImageQualityGuard or PatchCore)."""

    def test_solid_black_frame_fails(self) -> None:
        """A perfectly uniform black frame (no texture) must not PASS."""
        station = _make_station()
        evaluator = LimitsEvaluator(_load_limits())

        # Perfectly uniform black — zero texture
        img = np.zeros((512, 512, 3), dtype=np.uint8)

        defects, measurements, _ = station.inspect_image(
            image=img,
            variant_id="FRONT_LH_BLACK",
            evaluator=evaluator,
            variant_nominals={},
        )

        # Must produce at least one defect (quality guard, engine unavailable, or anomaly)
        assert len(defects) > 0, "Blank black frame must not PASS silently"
        outcomes = [d.outcome for d in defects]
        assert Outcome.FAIL in outcomes, f"Blank frame should FAIL, got {outcomes}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
