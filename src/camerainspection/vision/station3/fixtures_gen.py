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
    shield_gap_offset_px: int = 14,  # 14px * 0.10mm = 1.4mm (within pass_tol=2.0mm)
    add_flash_px: int = 0,
) -> np.ndarray:
    """Generate a synthetic station 3 scene that passes image sanity checks.

    Components are placed at 1:1 scale matching the golden templates so
    cv2.matchTemplate (TM_CCOEFF_NORMED) returns a near-perfect score (≥0.95)
    for present+correct components.

    Sanity check requirements (check_image_sanity):
      mean_val > 20, edge_density > 0.01, variance > 100

    Strategy: mid-grey background with dense horizontal+vertical rib grid to
    achieve edge_density ~0.03 across the full 2592×1944 canvas.
    """
    rng = np.random.default_rng(42)
    base = np.full((height, width, 3), 75, dtype=np.int16)
    noise = rng.integers(-12, 13, (height, width, 3), dtype=np.int16)
    canvas = np.clip(base + noise, 0, 255).astype(np.uint8)

    # Dense plastic panel rib grid — gives edge_density ≥ 0.01
    for y in range(80, height, 80):
        cv2.line(canvas, (0, y), (width, y), (45, 45, 45), 2)
    for x in range(120, width, 120):
        cv2.line(canvas, (x, 0), (x, height), (45, 45, 45), 2)

    # Major structural features — large contrast blocks raise blurred variance above 100
    cv2.line(canvas, (0, height // 3), (width, height // 3), (35, 35, 35), 8)
    cv2.line(canvas, (width // 4, 0), (width // 4, height), (35, 35, 35), 6)
    cv2.rectangle(canvas, (150, 150), (width - 150, height - 150), (40, 40, 40), 8)
    # Two large dark bolster blocks (high contrast → blurred variance >> 100)
    cv2.rectangle(canvas, (0, 0), (500, height), (30, 30, 30), -1)
    cv2.rectangle(canvas, (width - 500, 0), (width, height), (30, 30, 30), -1)
    # Two bright highlight strips
    cv2.rectangle(canvas, (500, 0), (700, height), (130, 130, 130), -1)
    cv2.rectangle(canvas, (width - 700, 0), (width - 500, height), (130, 130, 130), -1)

    # Clear component ROIs to black (value < 40) so the flash/gap detectors
    # (which threshold at gray > 40) only see intentional component pixels, not
    # background rib lines.
    # side_shield ROI: x=200, y=400, w=1200, h=800
    canvas[400:1200, 200:1400] = 20
    # lever_handle ROI: x=1500, y=500, w=600, h=500
    canvas[500:1000, 1500:2100] = 20

    # Paint a synthetic gap in the gap measurement crop region so the measured
    # gap ≈ nominal (2.5 mm @ 0.18 mm/px → ~14 px).
    # Gap crop: image[cy-50:cy+50, cx-45:cx+45] where cx=450, cy=525
    #   → image[475:575, 405:495]
    # Strategy: left edge at x=405..418 (14px bright strip), then black gap
    # (14px → ~2.52 mm), then right edge at x=433..495 bright.
    # This gives drop_idx ≈ 14 (left edge falls off), rise_idx ≈ 28 (gap reopens),
    # gap_pixels ≈ 14, gap_mm ≈ 14 * 0.18 = 2.52 mm (within pass_tol=2.0mm of 2.5mm nominal).
    gap_left_x, gap_right_x = 405, 419   # 14px bright left panel edge
    canvas[475:575, gap_left_x:gap_right_x] = 110   # bright left panel face
    # 14px dark gap between panels (stays at 20 from the ROI clear above)
    gap_fill_x = 433
    canvas[475:575, gap_fill_x:495] = 110           # bright right panel face

    lh_dir = variants_root / "FRONT_LH_BLACK" / "golden_images"
    rh_dir = variants_root / "FRONT_RH_BLACK" / "golden_images"

    # ── Side shield (ROI: x=200, y=400, w=1200, h=800) ───────────────────────
    # Place template at 1:1 scale inside the ROI so NCC returns ≥ 0.95
    if not missing_shield:
        if wrong_hand_shield:
            tmpl_path = rh_dir / "side_shield.png"
        else:
            tmpl_path = lh_dir / "side_shield.png"
        template = cv2.imread(str(tmpl_path))

        if discolored_shield and template is not None:
            template = template.copy()
            template[:, :, 2] = np.clip(
                template[:, :, 2].astype(np.int16) + 80, 0, 255
            ).astype(np.uint8)

        if template is not None:
            th, tw = template.shape[:2]
            # Place at 1:1 scale inside ROI origin (x=200, y=400).
            # Keep the template's right edge (200+tw) below x=400 so the gap
            # measurement crop (cx=450±45 → x=405..495) sits fully in the black
            # background, returning gap=0.0 mm on a clean scene.
            px, py = 200, 400
            canvas[py: py + th, px: px + tw] = template

    # ── Lever handle (ROI: x=1500, y=500, w=600, h=500) ─────────────────────
    handle_tmpl = cv2.imread(str(lh_dir / "lever_handle.png"))
    if handle_tmpl is not None:
        hh, hw = handle_tmpl.shape[:2]
        px, py = 1510, 510
        canvas[py: py + hh, px: px + hw] = handle_tmpl

        if add_flash_px > 0:
            cv2.rectangle(
                canvas,
                (px + 10, py + hh),
                (px + 50, py + hh + add_flash_px),
                (110, 110, 110),
                -1,
            )

    return canvas
