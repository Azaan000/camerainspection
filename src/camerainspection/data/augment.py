"""Controlled augmentation pipeline with strict hand-safety guards."""

from __future__ import annotations

import cv2
import numpy as np

from camerainspection.core.logging import get_logger

logger = get_logger("data.augment")


class HandSafetyViolationError(ValueError):
    """Raised when an illegal flip or mirror transform is attempted on LH/RH parts."""


class SafeImageAugmentor:
    """Applies mild industrial augmentations while prohibiting hand-destroying transforms."""

    def __init__(
        self,
        max_brightness_delta: float = 0.10,  # Max +/- 10% brightness shift
        max_shift_pixels: int = 5,           # Max +/- 5 pixels translation
        is_hand_sensitive: bool = True,     # True for plastic parts, LH/RH components
    ) -> None:
        self.max_brightness_delta = max_brightness_delta
        self.max_shift_pixels = max_shift_pixels
        self.is_hand_sensitive = is_hand_sensitive

    def augment_mild(
        self,
        image: np.ndarray,
        brightness_factor: float = 1.0,
        shift_x: int = 0,
        shift_y: int = 0,
        flip_horizontal: bool = False,
    ) -> np.ndarray:
        """Apply mild brightness and shift augmentation.

        Raises HandSafetyViolationError if horizontal flip is attempted on hand-sensitive parts.
        """
        if flip_horizontal and self.is_hand_sensitive:
            raise HandSafetyViolationError(
                "CRITICAL SAFETY VIOLATION: Horizontal flip cannot be applied to LH/RH-sensitive parts. "
                "Flipping would invert part geometry and hide wrong-hand assembly escapes!"
            )

        out = image.copy()

        # Mild translation
        if shift_x != 0 or shift_y != 0:
            shift_x = int(np.clip(shift_x, -self.max_shift_pixels, self.max_shift_pixels))
            shift_y = int(np.clip(shift_y, -self.max_shift_pixels, self.max_shift_pixels))
            m = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
            out = cv2.warpAffine(out, m, (image.shape[1], image.shape[0]), borderMode=cv2.BORDER_REFLECT_101)

        # Mild brightness scaling
        if brightness_factor != 1.0:
            factor = float(
                np.clip(
                    brightness_factor,
                    1.0 - self.max_brightness_delta,
                    1.0 + self.max_brightness_delta,
                )
            )
            out = cv2.convertScaleAbs(out, alpha=factor, beta=0)

        if flip_horizontal and not self.is_hand_sensitive:
            out = cv2.flip(out, 1)

        return out

    def paste_synthetic_defect(
        self,
        base_image: np.ndarray,
        defect_patch: np.ndarray,
        mask: np.ndarray,
        target_x: int,
        target_y: int,
    ) -> np.ndarray:
        """Blend rare synthetic defect patch (e.g. crack or stain) onto base image via seamless cloning."""
        h, w = defect_patch.shape[:2]
        center = (target_x + w // 2, target_y + h // 2)
        try:
            blended = cv2.seamlessClone(defect_patch, base_image, mask, center, cv2.NORMAL_CLONE)
            return blended
        except Exception as e:
            logger.warning(f"Seamless clone failed ({e}), falling back to direct alpha blend")
            out = base_image.copy()
            norm_mask = mask.astype(float) / 255.0
            if len(norm_mask.shape) == 2:
                norm_mask = np.repeat(norm_mask[:, :, np.newaxis], 3, axis=2)
            roi = out[target_y : target_y + h, target_x : target_x + w]
            out[target_y : target_y + h, target_x : target_x + w] = (
                defect_patch * norm_mask + roi * (1.0 - norm_mask)
            ).astype(np.uint8)
            return out
