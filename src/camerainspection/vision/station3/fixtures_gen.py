"""Deterministic generator for synthetic golden templates and test fixture images."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def generate_station3_golden_assets(variants_root: Path) -> None:
    """Generate LH and RH golden component templates."""
    lh_dir = variants_root / "FRONT_LH_BLACK" / "golden_images"
    rh_dir = variants_root / "FRONT_RH_BLACK" / "golden_images"
    lh_dir.mkdir(parents=True, exist_ok=True)
    rh_dir.mkdir(parents=True, exist_ok=True)

    # 1. LH Side Shield template (200x150, distinctive LH geometry)
    lh_shield = np.full((150, 200, 3), 40, dtype=np.uint8)  # Black plastic body
    # Draw LH-specific ribbing and bevel on left side
    cv2.rectangle(lh_shield, (20, 20), (80, 130), (90, 90, 90), -1)
    cv2.circle(lh_shield, (50, 75), 18, (140, 140, 140), -1)
    cv2.putText(lh_shield, "LH", (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(str(lh_dir / "side_shield.png"), lh_shield)

    # 2. RH Side Shield template (mirror feature on right side)
    rh_shield = np.full((150, 200, 3), 40, dtype=np.uint8)
    cv2.rectangle(rh_shield, (120, 20), (180, 130), (90, 90, 90), -1)
    cv2.circle(rh_shield, (150, 75), 18, (140, 140, 140), -1)
    cv2.putText(rh_shield, "RH", (125, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(str(rh_dir / "side_shield.png"), rh_shield)

    # 3. LH Lever Handle (100x120)
    lh_handle = np.full((120, 100, 3), 45, dtype=np.uint8)
    cv2.ellipse(lh_handle, (35, 60), (25, 40), 0, 0, 360, (110, 110, 110), -1)
    cv2.imwrite(str(lh_dir / "lever_handle.png"), lh_handle)

    # 4. RH Lever Handle (100x120)
    rh_handle = np.full((120, 100, 3), 45, dtype=np.uint8)
    cv2.ellipse(rh_handle, (65, 60), (25, 40), 0, 0, 360, (110, 110, 110), -1)
    cv2.imwrite(str(rh_dir / "lever_handle.png"), rh_handle)


def generate_station3_test_scene(
    variants_root: Path,
    width: int = 2592,
    height: int = 1944,
    variant_id: str = "FRONT_LH_BLACK",
    missing_shield: bool = False,
    wrong_hand_shield: bool = False,
    discolored_shield: bool = False,
    shield_gap_offset_px: int = 25,  # 25px * 0.1mm = 2.5mm (nominal)
    add_flash_px: int = 0,
) -> np.ndarray:
    """Generate a realistic synthetic station 3 scene with configurable defects."""
    canvas = np.full((height, width, 3), 25, dtype=np.uint8)  # Seat background dark

    lh_dir = variants_root / "FRONT_LH_BLACK" / "golden_images"
    rh_dir = variants_root / "FRONT_RH_BLACK" / "golden_images"

    # Positions matching station_3_plastic.yaml ROIs:
    # side_shield: x: 200, y: 400
    # lever_handle: x: 1500, y: 500

    # 1. Place side shield
    if not missing_shield:
        if wrong_hand_shield:
            template = cv2.imread(str(rh_dir / "side_shield.png"))
        else:
            template = cv2.imread(str(lh_dir / "side_shield.png"))

        if discolored_shield and template is not None:
            # Shift color significantly: add red tint
            template = template.copy()
            template[:, :, 2] = np.clip(template[:, :, 2] + 80, 0, 255)

        if template is not None:
            th, tw = template.shape[:2]
            # Ensure the template has a solid edge at its boundary so transition is sharp
            template_placed = template.copy()
            template_placed[:, tw - 10 : tw] = 80
            canvas[450 : 450 + th, 250 : 250 + tw] = template_placed

            # Draw mating panel body after the gap channel
            edge_x = 250 + tw + shield_gap_offset_px
            canvas[450 : 450 + th, edge_x : edge_x + 100] = 80

    # 2. Place lever handle
    handle_tmpl = cv2.imread(str(lh_dir / "lever_handle.png"))
    if handle_tmpl is not None:
        hh, hw = handle_tmpl.shape[:2]
        canvas[520 : 520 + hh, 1520 : 1520 + hw] = handle_tmpl

        if add_flash_px > 0:
            # Add protrusion along bottom edge
            cv2.rectangle(
                canvas,
                (1530, 520 + hh),
                (1560, 520 + hh + add_flash_px),
                (110, 110, 110),
                -1,
            )

    return canvas
