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
    """Check if image color matches expected variant color family.

    This is a GROSS mismatch detector for catching process errors (wrong barcode
    scanned, wrong variant selected in system). It uses coarse color categories
    and will NOT catch subtle color variations within the same category.

    Example: Brown seat tested as FRONT_LH_BLACK → mismatch detected
             Dark grey vs black → no mismatch (both in BLACK_DARK category)

    Supports multiple acceptable colors per variant (e.g., BLACK can accept
    BLACK_DARK and GREY_MEDIUM for charcoal/dark grey variants).

    Parameters
    ----------
    image : np.ndarray
        BGR image of leather surface
    variant_id : str
        Seat variant ID (e.g., "FRONT_LH_BLACK", "FRONT_RH_BROWN")
    roi_mask : np.ndarray | None
        Optional binary mask of valid leather ROI

    Returns
    -------
    tuple[bool, str]
        (matches, reason) - True if color matches variant expectation,
        otherwise False with reason string. False indicates probable wrong variant.
    """
    observed_color = classify_leather_color(image, roi_mask)

    # Extract expected color from variant ID
    variant_upper = variant_id.upper()

    expected_colors = []
    # BLACK variants accept BLACK_DARK and GREY_MEDIUM (for charcoal/dark grey)
    if "BLACK" in variant_upper or "DARK" in variant_upper:
        expected_colors = [LeatherColorClass.BLACK_DARK, LeatherColorClass.GREY_MEDIUM]
    # BROWN variants accept BROWN_TAN and sometimes GREY_MEDIUM (for taupe/greige)
    elif "BROWN" in variant_upper or "TAN" in variant_upper:
        expected_colors = [LeatherColorClass.BROWN_TAN, LeatherColorClass.GREY_MEDIUM]
    # CREAM/LIGHT variants
    elif "CREAM" in variant_upper or "LIGHT" in variant_upper or "BEIGE" in variant_upper:
        expected_colors = [LeatherColorClass.CREAM_LIGHT]
    # GREY variants accept GREY_MEDIUM and BLACK_DARK (for dark grey)
    elif "GREY" in variant_upper or "GRAY" in variant_upper:
        expected_colors = [LeatherColorClass.GREY_MEDIUM, LeatherColorClass.BLACK_DARK]
    else:
        # Unknown variant color - cannot validate, pass through
        return (True, f"Variant {variant_id} has no color keyword - skipping validation")

    if observed_color == LeatherColorClass.UNKNOWN:
        # Could not classify - do not block (avoid false rejects on edge lighting)
        return (True, f"Observed color could not be classified - skipping validation")

    if observed_color in expected_colors:
        return (True, f"Color match: observed {observed_color.value} matches expected {[c.value for c in expected_colors]}")

    # Mismatch detected - this is likely a wrong barcode or variant selection
    reason = (
        f"Color mismatch: variant '{variant_id}' expects {[c.value for c in expected_colors]}, "
        f"but observed {observed_color.value}. Possible wrong barcode or variant selection."
    )
    return (False, reason)
