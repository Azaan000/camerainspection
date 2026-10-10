"""Unit tests for Station 3 OpenCV vision measurement algorithms."""

from pathlib import Path

import cv2
import numpy as np

from camerainspection.vision.station3.color import ColorMatchEngine
from camerainspection.vision.station3.dimensions import PlasticDimensionEngine
from camerainspection.vision.station3.presence import GoldenTemplateMatcher


def test_color_delta_e_accuracy() -> None:
    # Identical images must produce 0.0 Delta E
    img1 = np.full((50, 50, 3), (40, 40, 40), dtype=np.uint8)
    img2 = np.full((50, 50, 3), (40, 40, 40), dtype=np.uint8)
    assert ColorMatchEngine.compute_delta_e(img1, img2) == 0.0

    # Large color shift: Black plastic vs Red/Brownish shifted
    img_shifted = np.full((50, 50, 3), (40, 40, 150), dtype=np.uint8)
    de = ColorMatchEngine.compute_delta_e(img1, img_shifted)
    assert de > 20.0  # Significant Delta E detected


def test_golden_template_matching(variants_dir: Path) -> None:
    lh_tmpl_path = variants_dir / "FRONT_LH_BLACK" / "golden_images" / "side_shield.png"
    rh_tmpl_path = variants_dir / "FRONT_RH_BLACK" / "golden_images" / "side_shield.png"

    lh_tmpl = cv2.imread(str(lh_tmpl_path))
    rh_tmpl = cv2.imread(str(rh_tmpl_path))
    assert lh_tmpl is not None and rh_tmpl is not None

    # Search ROI with LH part centered
    search_roi = np.full((300, 350, 3), 20, dtype=np.uint8)
    search_roi[50 : 50 + lh_tmpl.shape[0], 50 : 50 + lh_tmpl.shape[1]] = lh_tmpl

    # 1. Match LH seat against LH part -> PASS
    res_lh = GoldenTemplateMatcher.match_component(
        search_roi=search_roi,
        component_name="side_shield",
        golden_template=lh_tmpl,
        expected_hand="LH",
        opposite_hand_template=rh_tmpl,
    )
    assert res_lh.detected is True
    assert res_lh.is_correct_hand is True
    assert res_lh.match_score > 0.95

    # 2. Match when RH part is mounted instead of LH -> WRONG HAND DETECTED!
    search_roi_rh = np.full((300, 350, 3), 20, dtype=np.uint8)
    search_roi_rh[50 : 50 + rh_tmpl.shape[0], 50 : 50 + rh_tmpl.shape[1]] = rh_tmpl

    res_wrong_hand = GoldenTemplateMatcher.match_component(
        search_roi=search_roi_rh,
        component_name="side_shield",
        golden_template=lh_tmpl,  # Expecting LH
        expected_hand="LH",
        opposite_hand_template=rh_tmpl,  # Passing RH template
    )
    assert res_wrong_hand.is_correct_hand is False
    assert "WRONG HAND" in res_wrong_hand.message

    # 3. Missing part
    empty_roi = np.full((300, 350, 3), 20, dtype=np.uint8)
    res_missing = GoldenTemplateMatcher.match_component(
        search_roi=empty_roi,
        component_name="side_shield",
        golden_template=lh_tmpl,
        expected_hand="LH",
    )
    assert res_missing.detected is False
    assert res_missing.is_correct_hand is False


def test_shield_gap_measurement() -> None:
    # Synthetic gap image: 200px wide, 50px high
    # Left edge at x=40, right edge at x=65 -> 25 pixels gap
    # pixel_size_mm = 0.10 mm/pixel -> 25 * 0.1 = 2.5 mm
    gap_roi = np.full((50, 200, 3), 20, dtype=np.uint8)
    # Part 1 ending at x=40
    gap_roi[:, :40] = 80
    # Part 2 starting at x=65
    gap_roi[:, 65:] = 80

    measured_mm = PlasticDimensionEngine.measure_gap_mm(
        gap_roi=gap_roi,
        pixel_size_mm=0.10,
        axis="horizontal",
    )
    # Expected: 2.5 mm; gradient extremum after Gaussian blur may shift by ≤ 3 px (0.3 mm)
    assert abs(measured_mm - 2.5) <= 0.30, (
        f"Measured gap {measured_mm:.2f}mm outside ±0.30mm of expected 2.50mm"
    )


def test_flash_protrusion_measurement() -> None:
    # Part with bottom edge nominally at y=60
    # Add a burr flash extending to y=65 (5 pixels = 0.5 mm at 0.1mm/px)
    part_roi = np.zeros((100, 100, 3), dtype=np.uint8)
    # Body
    part_roi[10:60, 20:80] = 100
    # Flash protrusion down to y=66 (6 pixels: 60..66 inclusive -> slice 60:67 * 0.1 = 0.6 mm)
    part_roi[60:67, 45:55] = 100

    flash_mm = PlasticDimensionEngine.measure_flash_mm(
        part_roi=part_roi,
        expected_edge_coord=60,
        pixel_size_mm=0.10,
        direction="bottom",
    )
    assert abs(flash_mm - 0.6) < 0.05
