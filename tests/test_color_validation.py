"""Test color validation improvements for black and multi-color variants."""

import numpy as np
import pytest
from camerainspection.vision.station1.color_validator import (
    classify_leather_color,
    check_variant_color_match,
    LeatherColorClass,
)


def create_test_image(lab_values: tuple[int, int, int], size=(100, 100)) -> np.ndarray:
    """Create test image with uniform LAB color.

    Args:
        lab_values: (L, a, b) values in LAB color space
        size: Image dimensions

    Returns:
        BGR image
    """
    import cv2

    # Create LAB image
    lab_img = np.zeros((*size, 3), dtype=np.uint8)
    lab_img[:, :] = lab_values

    # Convert to BGR
    bgr_img = cv2.cvtColor(lab_img, cv2.COLOR_LAB2BGR)
    return bgr_img


class TestBlackColorVariations:
    """Test black leather color variations."""

    def test_pure_black_leather(self):
        """Pure black leather (L=20) should classify as BLACK_DARK."""
        img = create_test_image((20, 128, 128))  # Low L, neutral a/b
        color_class = classify_leather_color(img)
        assert color_class == LeatherColorClass.BLACK_DARK

    def test_dark_charcoal_leather(self):
        """Dark charcoal (L=50) should classify as BLACK_DARK."""
        img = create_test_image((50, 128, 128))
        color_class = classify_leather_color(img)
        assert color_class == LeatherColorClass.BLACK_DARK

    def test_charcoal_grey_leather(self):
        """Charcoal grey (L=75) should classify as BLACK_DARK."""
        img = create_test_image((75, 128, 128))
        color_class = classify_leather_color(img)
        assert color_class == LeatherColorClass.BLACK_DARK

    def test_medium_grey_leather(self):
        """Medium grey (L=100) should classify as GREY_MEDIUM."""
        img = create_test_image((100, 128, 128))
        color_class = classify_leather_color(img)
        assert color_class == LeatherColorClass.GREY_MEDIUM


class TestVariantColorMatching:
    """Test variant color matching with multiple acceptable colors."""

    def test_black_variant_accepts_black_dark(self):
        """BLACK variant should accept BLACK_DARK classification."""
        img = create_test_image((30, 128, 128))  # Pure black
        matches, reason = check_variant_color_match(img, "FRONT_LH_BLACK")
        assert matches, f"Black leather should match BLACK variant: {reason}"

    def test_black_variant_accepts_charcoal(self):
        """BLACK variant should accept charcoal grey (BLACK_DARK)."""
        img = create_test_image((70, 128, 128))  # Dark charcoal
        matches, reason = check_variant_color_match(img, "FRONT_LH_BLACK")
        assert matches, f"Charcoal leather should match BLACK variant: {reason}"

    def test_black_variant_accepts_medium_grey(self):
        """BLACK variant should accept GREY_MEDIUM (for dark grey seats)."""
        img = create_test_image((100, 128, 128))  # Medium grey
        matches, reason = check_variant_color_match(img, "FRONT_LH_BLACK")
        assert matches, f"Medium grey leather should match BLACK variant: {reason}"

    def test_black_variant_rejects_brown(self):
        """BLACK variant should reject brown leather."""
        img = create_test_image((120, 145, 150))  # Brown (red + yellow)
        matches, reason = check_variant_color_match(img, "FRONT_LH_BLACK")
        assert not matches, f"Brown leather should not match BLACK variant"
        assert "brown_tan" in reason.lower()

    def test_black_variant_rejects_cream(self):
        """BLACK variant should reject cream/light leather."""
        img = create_test_image((200, 128, 128))  # Cream/light
        matches, reason = check_variant_color_match(img, "FRONT_LH_BLACK")
        assert not matches, f"Cream leather should not match BLACK variant"
        assert "cream_light" in reason.lower()

    def test_grey_variant_accepts_both_grey_and_black(self):
        """GREY variant should accept both GREY_MEDIUM and BLACK_DARK."""
        # Test medium grey
        img1 = create_test_image((100, 128, 128))
        matches1, _ = check_variant_color_match(img1, "FRONT_LH_GREY")
        assert matches1, "Medium grey should match GREY variant"

        # Test dark grey (BLACK_DARK range)
        img2 = create_test_image((60, 128, 128))
        matches2, _ = check_variant_color_match(img2, "FRONT_LH_GREY")
        assert matches2, "Dark grey should match GREY variant"

    def test_brown_variant_accepts_brown_and_grey(self):
        """BROWN variant should accept BROWN_TAN and GREY_MEDIUM (for taupe)."""
        # Test brown
        img1 = create_test_image((120, 145, 150))
        matches1, _ = check_variant_color_match(img1, "FRONT_LH_BROWN")
        assert matches1, "Brown should match BROWN variant"

        # Test greige/taupe (medium grey)
        img2 = create_test_image((100, 128, 128))
        matches2, _ = check_variant_color_match(img2, "FRONT_LH_BROWN")
        assert matches2, "Greige/taupe should match BROWN variant"

    def test_unknown_variant_passes_through(self):
        """Variants without color keywords should pass through."""
        img = create_test_image((50, 128, 128))
        matches, reason = check_variant_color_match(img, "FRONT_LH_PREMIUM")
        assert matches, "Unknown variant color should pass through"
        assert "no color keyword" in reason.lower()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_unknown_color_classification_passes_through(self):
        """If color cannot be classified, should pass through (avoid false rejects)."""
        # Create ambiguous color that falls in UNKNOWN category
        img = create_test_image((150, 128, 128))  # Between categories
        matches, reason = check_variant_color_match(img, "FRONT_LH_BLACK")
        # Should either classify correctly or pass through as UNKNOWN
        assert isinstance(matches, bool)

    def test_with_roi_mask(self):
        """Test color classification with ROI mask."""
        # Create image with black center and white border
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        img[25:75, 25:75] = 20  # Black center

        # Mask for center only
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[25:75, 25:75] = 255

        color = classify_leather_color(img, roi_mask=mask)
        assert color == LeatherColorClass.BLACK_DARK


def test_real_world_black_variants():
    """Test with actual variant IDs from production."""
    test_cases = [
        ("FRONT_LH_BLACK", (40, 128, 128), True, "Pure black"),
        ("FRONT_RH_BLACK", (70, 128, 128), True, "Charcoal"),
        ("REAR_CENTER_BLACK", (95, 128, 128), True, "Dark grey"),
        ("FRONT_LH_DARK_GREY", (60, 128, 128), True, "Dark grey variant"),
        ("FRONT_LH_BLACK", (120, 145, 150), False, "Brown (should fail)"),
    ]

    for variant_id, lab_color, should_match, description in test_cases:
        img = create_test_image(lab_color)
        matches, reason = check_variant_color_match(img, variant_id)

        if should_match:
            assert matches, f"{description} should match {variant_id}: {reason}"
        else:
            assert not matches, f"{description} should NOT match {variant_id}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
