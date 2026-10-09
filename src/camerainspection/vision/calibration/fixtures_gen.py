"""Synthetic calibration image generator for checkerboard and fiducial targets."""

from __future__ import annotations

import cv2
import numpy as np


def generate_checkerboard_image(
    rows: int = 6,
    cols: int = 8,
    square_size_px: int = 40,
    margin_px: int = 50,
) -> np.ndarray:
    """Generate synthetic black-and-white checkerboard calibration image."""
    img_h = rows * square_size_px + 2 * margin_px
    img_w = cols * square_size_px + 2 * margin_px
    image = np.full((img_h, img_w), 255, dtype=np.uint8)

    for r in range(rows):
        for c in range(cols):
            if (r + c) % 2 == 1:
                y1 = margin_px + r * square_size_px
                y2 = y1 + square_size_px
                x1 = margin_px + c * square_size_px
                x2 = x1 + square_size_px
                image[y1:y2, x1:x2] = 0

    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)


def generate_two_dot_target_image(
    distance_px: int = 200,
    radius_px: int = 15,
    width: int = 640,
    height: int = 480,
) -> np.ndarray:
    """Generate white background with two distinct circular black targets at known distance."""
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    cx = width // 2
    cy = height // 2
    c1 = (cx - distance_px // 2, cy)
    c2 = (cx + distance_px // 2, cy)

    cv2.circle(image, c1, radius_px, (0, 0, 0), -1)
    cv2.circle(image, c2, radius_px, (0, 0, 0), -1)
    return image
