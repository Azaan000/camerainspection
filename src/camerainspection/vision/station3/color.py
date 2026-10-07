"""Color matching in CIE L*a*b* color space for automotive plastics."""

from __future__ import annotations

import cv2
import numpy as np


class ColorMatchEngine:
    """Computes perceptual color difference Delta E between sample and golden reference."""

    @classmethod
    def compute_delta_e(cls, sample_bgr: np.ndarray, golden_bgr: np.ndarray) -> float:
        """Calculate CIE Delta E 76 between mean color of sample and golden reference."""
        if sample_bgr.size == 0 or golden_bgr.size == 0:
            return 999.0  # Safe extreme difference on invalid inputs

        sample_lab = cv2.cvtColor(sample_bgr, cv2.COLOR_BGR2Lab).astype(np.float32)
        golden_lab = cv2.cvtColor(golden_bgr, cv2.COLOR_BGR2Lab).astype(np.float32)

        # Average Lab coordinates across the ROIs
        sample_mean = np.mean(sample_lab, axis=(0, 1))
        golden_mean = np.mean(golden_lab, axis=(0, 1))

        # CIE Delta E 76 euclidean distance
        delta_e = float(np.linalg.norm(sample_mean - golden_mean))
        return delta_e
