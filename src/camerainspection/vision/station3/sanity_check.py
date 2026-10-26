"""Sanity check to detect unrelated images (wrong part, wrong station)."""

import cv2
import numpy as np


def check_image_sanity(
    image: np.ndarray,
    expected_component_count: int,
    expected_color_family: str,
) -> tuple[bool, str]:
    """Quick sanity check that image matches expected part type.

    Args:
        image: Input image (BGR format)
        expected_component_count: Number of components expected in view
        expected_color_family: Expected color (e.g., "black", "grey", "white")

    Returns:
        (is_sane, reason): True if image passes basic sanity checks
    """
    h, w = image.shape[:2]

    # 1. Check image is not mostly background (empty fixture)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean_val = gray.mean()
    if mean_val < 20 or mean_val > 240:
        return False, f"Image is mostly {'black' if mean_val < 20 else 'white'} (background only?)"

    # 2. Check edge density (plastic parts have distinct edges)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = edges.sum() / (h * w * 255.0)

    if edge_density < 0.01:
        return False, "No distinct edges detected (wrong part or blurred image?)"

    if edge_density > 0.5:
        return False, "Too many edges (textured surface, not plastic?)"

    # 3. Basic color family check
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    s_channel = hsv[:, :, 1]
    v_channel = hsv[:, :, 2]

    mean_saturation = s_channel.mean()
    mean_value = v_channel.mean()

    # Color-specific checks
    if expected_color_family.lower() in ("black", "grey", "gray"):
        # Low saturation, low-to-medium value
        if mean_saturation > 100:
            return False, f"Expected {expected_color_family} but image is highly saturated (wrong color?)"
        if mean_value > 180:
            return False, f"Expected {expected_color_family} but image is too bright (wrong part?)"
    elif expected_color_family.lower() == "white":
        # Low saturation, high value
        if mean_value < 150:
            return False, "Expected white but image is too dark (wrong part?)"
    else:
        # Colored parts should have some saturation
        if mean_saturation < 20:
            return False, f"Expected {expected_color_family} but image has no color saturation (wrong part?)"

    # 4. Check for obvious fixture markers or unexpected patterns
    # Detect large uniform regions (empty fixture)
    blurred = cv2.GaussianBlur(gray, (21, 21), 0)
    variance = np.var(blurred)
    if variance < 100:
        return False, "Image too uniform (empty fixture or solid background?)"

    return True, "Sanity check passed"
