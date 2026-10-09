"""Unit tests for Station 2 stitch measurement algorithms with known-answer synthetic images."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from camerainspection.vision.station2.fixtures_gen import make_stitch_seam
from camerainspection.vision.station2.stitch_geometry import StitchGeometryEngine
from camerainspection.vision.station2.thread_color import ThreadColorEngine


# ------ StitchGeometryEngine -----------------------------------------------

def test_spi_known_answer() -> None:
    """Synthetic seam: 30 stitches, 18px pitch, 0.05mm/px -> pitch=0.9mm -> SPI=25.4/0.9≈28.2."""
    seam = make_stitch_seam(n_stitches=30, pitch_px=18)
    meas = StitchGeometryEngine.analyze_seam(seam, pixel_size_mm=0.05)
    expected_spi = 25.4 / (18 * 0.05)  # ≈ 28.22
    assert meas.stitch_count >= 25, f"Too few stitches detected: {meas.stitch_count}"
    assert abs(meas.stitches_per_inch - expected_spi) < 2.0, (
        f"SPI {meas.stitches_per_inch:.2f} too far from expected {expected_spi:.2f}"
    )


def test_skip_detection_known_answer() -> None:
    """Skip at index 10: gap = 2 pitches = 2*18px*0.05mm/px = 1.8mm, skip = gap - pitch = 0.9mm."""
    seam = make_stitch_seam(n_stitches=30, pitch_px=18, skip_index=10)
    meas = StitchGeometryEngine.analyze_seam(seam, pixel_size_mm=0.05)
    expected_skip = 18 * 0.05  # = 0.90mm (one missing pitch)
    assert meas.max_skip_length_mm > 0, "Skip not detected"
    assert abs(meas.max_skip_length_mm - expected_skip) < 0.20, (
        f"Skip {meas.max_skip_length_mm:.2f}mm, expected ~{expected_skip:.2f}mm"
    )


def test_no_skip_on_clean_seam() -> None:
    """A perfect seam with no defects must report max_skip_length_mm == 0."""
    seam = make_stitch_seam(n_stitches=30, pitch_px=18)
    meas = StitchGeometryEngine.analyze_seam(seam, pixel_size_mm=0.05)
    assert meas.max_skip_length_mm == 0.0, (
        f"False skip detected on clean seam: {meas.max_skip_length_mm}"
    )


def test_seam_position_at_centre() -> None:
    """A centred seam should measure ~0mm deviation from style line at ROI midpoint."""
    seam = make_stitch_seam(height=200, seam_y=100)
    meas = StitchGeometryEngine.analyze_seam(seam, pixel_size_mm=0.05, reference_style_line_y=100.0)
    assert meas.seam_position_mm < 0.5, (
        f"Seam position {meas.seam_position_mm:.2f}mm should be near 0"
    )


def test_seam_position_offset() -> None:
    """Seam shifted 20px from style line = 20 * 0.05mm = 1.0mm."""
    seam = make_stitch_seam(height=200, seam_y=80)
    meas = StitchGeometryEngine.analyze_seam(seam, pixel_size_mm=0.05, reference_style_line_y=100.0)
    expected_mm = 20 * 0.05  # 1.0mm
    assert abs(meas.seam_position_mm - expected_mm) < 0.2, (
        f"Seam position {meas.seam_position_mm:.2f}mm, expected ~{expected_mm:.2f}mm"
    )


def test_double_seam_detection() -> None:
    """Seam shifted in second half = double seam flag raised."""
    seam = make_stitch_seam(n_stitches=30, pitch_px=18, shift_y_at_half=20)
    meas = StitchGeometryEngine.analyze_seam(seam, pixel_size_mm=0.05)
    assert meas.has_double_seam is True, "Double seam not flagged"


def test_insufficient_stitches_returns_zero() -> None:
    """Empty / blank image must return zeros without crashing."""
    blank = np.zeros((100, 200, 3), dtype=np.uint8)
    meas = StitchGeometryEngine.analyze_seam(blank, pixel_size_mm=0.05)
    assert meas.stitch_count <= 1
    assert meas.stitches_per_inch == 0.0


# ------ ThreadColorEngine ---------------------------------------------------

def test_thread_color_zero_delta_e() -> None:
    """When the reference patch matches the extracted thread sample, ΔE is exactly 0.0."""
    good_seam = make_stitch_seam(thread_color_bgr=(210, 210, 210))
    good_meas = StitchGeometryEngine.analyze_seam(good_seam, pixel_size_mm=0.05)
    ref_sample = ThreadColorEngine.extract_thread_sample(good_seam, good_meas.stitch_centers)
    assert ref_sample is not None, "Could not extract reference from good seam"
    de = ThreadColorEngine.compute_thread_delta_e(good_seam, good_meas.stitch_centers, ref_sample)
    assert de == 0.0 or de < 1e-4, f"Self-reference ΔE should be zero, got {de}"


def test_thread_color_matching_lower_than_wrong_color() -> None:
    """Matching thread color must give much lower ΔE than wrong (red) thread."""
    # Build a per-scene reference from a good frame sample so both share the
    # same illumination model — this mirrors production where the reference chip
    # is photographed under station lighting, not hand-specified as (210,210,210).
    good_seam = make_stitch_seam(thread_color_bgr=(210, 210, 210))
    good_meas = StitchGeometryEngine.analyze_seam(good_seam, pixel_size_mm=0.05)

    # Extract a reference patch from the good seam itself
    ref_sample = ThreadColorEngine.extract_thread_sample(good_seam, good_meas.stitch_centers)
    assert ref_sample is not None, "Could not extract reference from good seam"

    # ΔE of good seam against its own reference must be near 0
    de_good = ThreadColorEngine.compute_thread_delta_e(good_seam, good_meas.stitch_centers, ref_sample)
    assert de_good < 3.0, f"Self-reference ΔE {de_good:.1f} should be near 0"

    # Wrong-color seam (red thread) against grey reference must give large ΔE
    wrong_seam = make_stitch_seam(thread_color_bgr=(30, 30, 200))
    wrong_meas = StitchGeometryEngine.analyze_seam(wrong_seam, pixel_size_mm=0.05)
    de_wrong = ThreadColorEngine.compute_thread_delta_e(wrong_seam, wrong_meas.stitch_centers, ref_sample)
    assert de_wrong > 5.0, f"Wrong-color ΔE {de_wrong:.1f} should exceed fail threshold"


def test_thread_color_none_reference_returns_sentinel() -> None:
    """When no variant reference is configured, engine must return the skip sentinel."""
    good_seam = make_stitch_seam(thread_color_bgr=(210, 210, 210))
    good_meas = StitchGeometryEngine.analyze_seam(good_seam, pixel_size_mm=0.05)
    de = ThreadColorEngine.compute_thread_delta_e(good_seam, good_meas.stitch_centers, None)
    from camerainspection.vision.station2.thread_color import _NO_REFERENCE_SENTINEL
    assert de == _NO_REFERENCE_SENTINEL, f"Expected sentinel, got {de}"
