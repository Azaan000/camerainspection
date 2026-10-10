"""Unit tests for Station 4 mechanism vision algorithms with known-answer synthetic images."""

from __future__ import annotations

from camerainspection.vision.station4.fixtures_gen import generate_station4_test_scene
from camerainspection.vision.station4.mechanism import MechanismVisionEngine


def test_recliner_angle_nominal_90_deg() -> None:
    """Lever drawn at 90.0 deg upright must measure 90.0 deg ± 0.5 deg."""
    scene = generate_station4_test_scene(recliner_angle_deg=90.0, track_end_pos_mm=240.0)
    recliner_crop = scene[800:1300, 400:900]
    angle = MechanismVisionEngine.measure_recliner_angle(recliner_crop)
    assert abs(angle - 90.0) < 0.5, f"Expected 90.0 deg, got {angle}"


def test_recliner_angle_tilted_93_deg() -> None:
    """Lever drawn at 93.0 deg must measure 93.0 deg ± 0.6 deg."""
    scene = generate_station4_test_scene(recliner_angle_deg=93.0, track_end_pos_mm=240.0)
    recliner_crop = scene[800:1300, 400:900]
    angle = MechanismVisionEngine.measure_recliner_angle(recliner_crop)
    assert abs(angle - 93.0) < 0.6, f"Expected ~93.0 deg, got {angle}"


def test_recliner_angle_tilted_87_deg() -> None:
    """Lever drawn at 87.0 deg must measure 87.0 deg ± 0.6 deg."""
    scene = generate_station4_test_scene(recliner_angle_deg=87.0, track_end_pos_mm=240.0)
    recliner_crop = scene[800:1300, 400:900]
    angle = MechanismVisionEngine.measure_recliner_angle(recliner_crop)
    assert abs(angle - 87.0) < 0.6, f"Expected ~87.0 deg, got {angle}"


def test_track_position_nominal_240mm() -> None:
    """Track marker placed at 240.0 mm (1600 px at 0.15 mm/px) must measure 240.0 mm ± 0.2 mm."""
    scene = generate_station4_test_scene(recliner_angle_deg=90.0, track_end_pos_mm=240.0, pixel_size_mm=0.15)
    track_crop = scene[1400:1800, 200:2200]
    pos = MechanismVisionEngine.measure_track_position_mm(track_crop, pixel_size_mm=0.15, reference_datum_x=0.0)
    assert abs(pos - 240.0) < 0.2, f"Expected 240.0 mm, got {pos}"


def test_track_position_short_236mm() -> None:
    """Track marker placed at 236.0 mm must measure 236.0 mm ± 0.2 mm."""
    scene = generate_station4_test_scene(recliner_angle_deg=90.0, track_end_pos_mm=236.0, pixel_size_mm=0.15)
    track_crop = scene[1400:1800, 200:2200]
    pos = MechanismVisionEngine.measure_track_position_mm(track_crop, pixel_size_mm=0.15, reference_datum_x=0.0)
    assert abs(pos - 236.0) < 0.2, f"Expected 236.0 mm, got {pos}"


def test_repeatability_10_runs() -> None:
    """Repeated measurement on the same scene must produce identical results."""
    scene = generate_station4_test_scene(recliner_angle_deg=90.0, track_end_pos_mm=240.0)
    recliner_crop = scene[800:1300, 400:900]
    track_crop = scene[1400:1800, 200:2200]

    angles = [MechanismVisionEngine.measure_recliner_angle(recliner_crop.copy()) for _ in range(10)]
    positions = [
        MechanismVisionEngine.measure_track_position_mm(track_crop.copy(), pixel_size_mm=0.15, reference_datum_x=0.0)
        for _ in range(10)
    ]

    assert len(set(angles)) == 1, f"Angles varied: {set(angles)}"
    assert len(set(positions)) == 1, f"Positions varied: {set(positions)}"
