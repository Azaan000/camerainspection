"""Thread color measurement using CIE Delta E in L*a*b* color space."""

from __future__ import annotations

import cv2
import numpy as np

from camerainspection.vision.station3.color import ColorMatchEngine

# Sentinel value: no reference configured — thread color check is skipped
_NO_REFERENCE_SENTINEL = -1.0


class ThreadColorEngine:
    """Measures thread color deviation from variant reference using CIE Delta E.

    Design notes:
    - The reference_bgr image should be the variant-specific golden thread color
      chip, photographed under the same lighting as the seam station.
    - If reference_bgr is None (no variant reference configured), the method
      returns _NO_REFERENCE_SENTINEL so the caller can skip the limit check
      rather than producing a spurious failure.
    - Sampling uses a ±sample_radius crop around each stitch centroid then
      computes the global mean across all patches before the CIE ΔE conversion.
    """

    @classmethod
    def extract_thread_sample(
        cls,
        seam_roi: np.ndarray,
        stitch_centers: list[list[float]],
        sample_radius: int = 4,
        max_samples: int = 20,
    ) -> np.ndarray | None:
        """Collect BGR patches centred on detected stitch centroids."""
        if not stitch_centers or seam_roi.size == 0:
            return None

        h, w = seam_roi.shape[:2]
        patches: list[np.ndarray] = []
        for cx, cy in stitch_centers[:max_samples]:
            x1 = max(0, int(cx) - sample_radius)
            x2 = min(w, int(cx) + sample_radius)
            y1 = max(0, int(cy) - sample_radius)
            y2 = min(h, int(cy) + sample_radius)
            patch = seam_roi[y1:y2, x1:x2]
            if patch.size > 0:
                patches.append(patch)

        if not patches:
            return None

        return np.concatenate(patches, axis=1)

    @classmethod
    def compute_thread_delta_e(
        cls,
        seam_roi: np.ndarray,
        stitch_centers: list[list[float]],
        reference_bgr: np.ndarray | None,
    ) -> float:
        """Compute mean ΔE between measured thread color and variant reference.

        Returns:
            ΔE float, or _NO_REFERENCE_SENTINEL (-1.0) when no reference is
            provided so the caller can skip the limit check.
        """
        if reference_bgr is None:
            return _NO_REFERENCE_SENTINEL

        thread_sample = cls.extract_thread_sample(seam_roi, stitch_centers)
        if thread_sample is None:
            return _NO_REFERENCE_SENTINEL

        return ColorMatchEngine.compute_delta_e(thread_sample, reference_bgr)
