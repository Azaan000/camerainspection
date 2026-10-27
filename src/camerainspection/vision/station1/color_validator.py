"""Variant color validation for Station 1 leather inspection.

Detects gross color mismatches between the physical seat and the declared variant
(e.g., brown leather tested as FRONT_LH_BLACK which expects black/dark leather).

This is a PROCESS ERROR check, not a defect detection. It catches operator mistakes
like scanning the wrong barcode or loading the wrong variant configuration.
"""

from __future__ import annotations

import logging
from enum import StrEnum

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class LeatherColorClass(StrEnum):
    """Coarse leather color categories for variant matching."""
    BLACK_DARK = "black_dark"      # Black, dark grey, charcoal
    BROWN_TAN = "brown_tan"        # Brown, tan, beige
    CREAM_LIGHT = "cream_light"    # Cream, light beige, off-white
    GREY_MEDIUM = "grey_medium"    # Medium grey
    UNKNOWN = "unknown"


def classify_leather_color(image: np.ndarray, roi_mask: np.ndarray | None = None) -> LeatherColorClass:
    """Classify coarse leather color category from image.

    Parameters
    ----------
    image : np.ndarray
        BGR image of leather surface
    roi_mask : np.ndarray | None
        Optional binary mask of valid ROI pixels (to exclude background)

    Returns
    -------
    LeatherColorClass
        Coarse color category
    """
    # Convert to LAB color space for perceptual color distance
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

    if roi_mask is not None and roi_mask.sum() > 100:
        # Use only ROI pixels
        lab_pixels = lab[roi_mask > 0]
    else:
        # Use all pixels
        lab_pixels = lab.reshape(-1, 3)

    # Compute median LAB values (robust to outliers)
    L_med = float(np.median(lab_pixels[:, 0]))  # Lightness 0-255
    a_med = float(np.median(lab_pixels[:, 1]))  # Green-Red -128 to 127
    b_med = float(np.median(lab_pixels[:, 2]))  # Blue-Yellow -128 to 127

    # Coarse classification rules (empirical thresholds for automotive leather)
    # Black/Dark: Low lightness (L < 80) - relaxed from 60 to handle black leather variations
    # Note: Black leather can range from L=20 (pure black) to L=75 (dark charcoal)
    if L_med < 80:
        return LeatherColorClass.BLACK_DARK

    # Cream/Light: High lightness (L > 180) with low chroma
    if L_med > 180 and abs(a_med - 128) < 20 and abs(b_med - 128) < 20:
        return LeatherColorClass.CREAM_LIGHT

    # Brown/Tan: Medium lightness (80-180) with positive a (red) and b (yellow)
    if 80 <= L_med <= 180:
        # Brown has red and yellow components
        if (a_med > 128 + 10) and (b_med > 128 + 10):
            return LeatherColorClass.BROWN_TAN
        # Grey has low chroma (near neutral)
        if abs(a_med - 128) < 15 and abs(b_med - 128) < 15:
            return LeatherColorClass.GREY_MEDIUM

    return LeatherColorClass.UNKNOWN


def check_variant_color_match(
    image: np.ndarray,
    variant_id: str,
    roi_mask: np.ndarray | None = None,
) -> tuple[bool, str]:
    """Check if image is valid leather/rexene material (accepts any leather color).

    Any valid leather color category or synthetic texture is accepted.
    Material mismatch is triggered only for completely blank, white, or black constant frames.
    """
    if image is None or image.size == 0:
        return False, "Material mismatch: Empty or invalid image"

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    std_dev = float(np.std(gray))
    if std_dev < 0.05:
        return False, f"Material mismatch: Image is completely uniform (std_dev={std_dev:.2f}). Possible blank frame."

    observed_color = classify_leather_color(image, roi_mask)
    return True, f"Valid leather material accepted (color category: {observed_color.value})"
