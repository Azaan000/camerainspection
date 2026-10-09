"""Synthetic image fixtures for rule-based fit checks."""

from __future__ import annotations

import cv2
import numpy as np


def make_shield_gap_fixture(
    gap_width_px: int = 16,
    width: int = 400,
    height: int = 200,
) -> np.ndarray:
    """Generate image of rigid plastic shield separated from leather cover by dark gap."""
    image = np.full((height, width, 3), 30, dtype=np.uint8)  # Dark shadow gap base

    # Left: Plastic shield (smooth medium grey)
    shield_w = (width - gap_width_px) // 2
    image[:, :shield_w] = (80, 80, 80)

    # Right: Leather cover (slightly textured dark grey)
    cover_start = shield_w + gap_width_px
    image[:, cover_start:] = (110, 105, 100)

    # Add edge highlights
    cv2.line(image, (shield_w - 1, 0), (shield_w - 1, height), (130, 130, 130), 1)
    cv2.line(image, (cover_start, 0), (cover_start, height), (150, 140, 130), 1)

    return image


def make_wrinkle_fixture(
    has_wrinkle: bool = True,
    crease_length_px: int = 60,
    width: int = 300,
    height: int = 300,
) -> np.ndarray:
    """Generate smooth leather surface with optional prominent dark crease line."""
    # Smooth dark leather background
    image = np.full((height, width, 3), 90, dtype=np.uint8)
    # Slight gradient to simulate bolster curve
    for y in range(height):
        image[y, :] = int(70 + 40 * (y / height))

    if has_wrinkle:
        cx, cy = width // 2, height // 2
        p1 = (cx - crease_length_px // 2, cy - 10)
        p2 = (cx + crease_length_px // 2, cy + 10)
        # Deep shadow line
        cv2.line(image, p1, p2, (20, 20, 20), 4)
        # Highlight alongside the shadow (fold reflection)
        cv2.line(image, (p1[0], p1[1] + 3), (p2[0], p2[1] + 3), (160, 160, 160), 2)

    return image


def make_foam_showthrough_fixture(
    has_foam: bool = True,
    foam_width_px: int = 40,
    foam_height_px: int = 25,
    width: int = 300,
    height: int = 200,
) -> np.ndarray:
    """Generate dark seat skirt with exposed polyurethane yellow/cream foam patch."""
    # Dark upholstery fabric (near black)
    image = np.full((height, width, 3), 35, dtype=np.uint8)

    if has_foam:
        fx = (width - foam_width_px) // 2
        fy = (height - foam_height_px) // 2
        # Polyurethane foam color in BGR: light yellow / cream (B=100, G=210, R=240)
        cv2.rectangle(
            image,
            (fx, fy),
            (fx + foam_width_px, fy + foam_height_px),
            (100, 210, 240),
            -1,
        )

    return image
