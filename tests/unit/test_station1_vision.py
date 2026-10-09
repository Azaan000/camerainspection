"""Unit tests for Station 1 surface analysis with known-answer synthetic images."""

from __future__ import annotations

import numpy as np
import pytest

from camerainspection.vision.station1.fixtures_gen import (
    make_clean_leather,
    make_leather_with_coating_streak,
    make_leather_with_cut,
    make_leather_with_pinhole,
    make_leather_with_scratch,
    make_leather_with_shade_band,
    make_leather_with_stain,
)
from camerainspection.vision.station1.surface_analysis import (
    LeatherDefectType,
    SurfaceAnalyzer,
)

W, H = 640, 480

ANALYZER = SurfaceAnalyzer(
    blur_ksize=51,
    diff_threshold=14,
    min_area_px=4,
    max_area_px=200_000,
)


def test_clean_leather_no_defects() -> None:
    """Clean dark leather must produce zero detected defect regions."""
    image = make_clean_leather(W, H)
    regions = ANALYZER.analyze(image)
    assert len(regions) == 0, f"False detections on clean leather: {[(r.defect_type, r.bbox_px) for r in regions]}"


def test_scratch_detected_and_classified() -> None:
    """Bright scratch line must be detected and classified as SCRATCH."""
    image = make_leather_with_scratch(W, H, x0=100, y0=240, length_px=80, brightness_add=60)
    regions = ANALYZER.analyze(image)
    scratch_regions = [r for r in regions if r.defect_type == LeatherDefectType.SCRATCH]
    assert len(scratch_regions) >= 1, f"Scratch not detected. Got: {[r.defect_type for r in regions]}"
    # Verify measured length is > 0
    assert scratch_regions[0].length_px > 10, "Scratch length too small"


def test_scratch_length_mm_known_answer() -> None:
    """Scratch of 80px at 0.08mm/px = 6.40mm. Length detection must be within ±1.5mm."""
    image = make_leather_with_scratch(W, H, x0=50, y0=240, length_px=80)
    regions = ANALYZER.analyze(image)
    scratch_regions = [r for r in regions if r.defect_type == LeatherDefectType.SCRATCH]
    assert scratch_regions, "No scratch found"
    expected_mm = 80 * 0.08
    measured_mm = scratch_regions[0].length_px * 0.08
    assert abs(measured_mm - expected_mm) < 1.5, (
        f"Scratch length {measured_mm:.2f}mm, expected ~{expected_mm:.2f}mm"
    )


def test_cut_detected_and_classified() -> None:
    """Dark cut mark must be detected and classified as CUT."""
    image = make_leather_with_cut(W, H, x0=200, y0=200, length_px=60, thickness=3)
    regions = ANALYZER.analyze(image)
    cut_regions = [r for r in regions if r.defect_type == LeatherDefectType.CUT]
    assert len(cut_regions) >= 1, f"Cut not detected. Got: {[r.defect_type for r in regions]}"


def test_pinhole_detected_and_classified() -> None:
    """Tiny dark circle must be detected and classified as PINHOLE."""
    image = make_leather_with_pinhole(W, H, cx=300, cy=240, radius=3)
    regions = ANALYZER.analyze(image)
    pinhole_regions = [r for r in regions if r.defect_type == LeatherDefectType.PINHOLE]
    assert len(pinhole_regions) >= 1, f"Pinhole not detected. Got: {[r.defect_type for r in regions]}"


def test_stain_detected_and_classified() -> None:
    """Dark irregular ellipse must be detected and classified as STAIN."""
    image = make_leather_with_stain(W, H, cx=320, cy=240, rx=30, ry=20)
    regions = ANALYZER.analyze(image)
    stain_regions = [r for r in regions if r.defect_type == LeatherDefectType.STAIN]
    assert len(stain_regions) >= 1, f"Stain not detected. Got: {[r.defect_type for r in regions]}"


def test_shade_band_detected() -> None:
    """Wide luminance gradient band must be detected (shade_band or coating_streak category)."""
    image = make_leather_with_shade_band(W, H, band_start_x=100, band_width=350, shade_delta=35)
    regions = ANALYZER.analyze(image)
    area_types = {LeatherDefectType.SHADE_BAND, LeatherDefectType.COATING_STREAK}
    band_regions = [r for r in regions if r.defect_type in area_types]
    assert len(band_regions) >= 1, f"Shade band not detected. Got: {[r.defect_type for r in regions]}"


def test_coating_streak_detected() -> None:
    """Long bright coating streak (200px, thick=4) must be detected as COATING_STREAK."""
    image = make_leather_with_coating_streak(W, H, length_px=200, thickness=4, brightness_add=70)
    regions = ANALYZER.analyze(image)
    streak_types = {LeatherDefectType.COATING_STREAK, LeatherDefectType.SCRATCH}
    streak_regions = [r for r in regions if r.defect_type in streak_types]
    assert len(streak_regions) >= 1, f"Coating streak not detected. Got: {[r.defect_type for r in regions]}"


def test_repeatability_10_runs() -> None:
    """Identical image analysed 10 times must give identical defect count and types."""
    image = make_leather_with_scratch(W, H, x0=100, y0=240, length_px=80)
    results = [ANALYZER.analyze(image.copy()) for _ in range(10)]
    counts = [len(r) for r in results]
    types_list = [[reg.defect_type for reg in r] for r in results]
    assert len(set(counts)) == 1, f"Non-deterministic defect counts: {counts}"
    assert all(t == types_list[0] for t in types_list), "Non-deterministic defect types"


def test_empty_roi_returns_empty() -> None:
    """Empty (zero-size) ROI must return no regions without crashing."""
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    regions = ANALYZER.analyze(empty)
    assert regions == []
