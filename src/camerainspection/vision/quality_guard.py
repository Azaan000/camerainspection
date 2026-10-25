"""Image quality and domain contrast guards for station inspection inputs."""

from __future__ import annotations

import numpy as np
import cv2

from camerainspection.core.models import DefectDetail, Outcome


class ImageQualityGuard:
    """Validates input image domains, contrast, and lighting exposure before inspection."""

    @staticmethod
    def evaluate_image(
        image: np.ndarray,
        min_std: float = -1.0,
        min_mean: float = -1.0,
        max_mean: float = 999.0,
        min_edge_density: float = 0.0,
    ) -> DefectDetail | None:
        """Check if image is flat/blank, pitch black, overexposed, or lacks expected domain edge features."""
        if image is None or image.size == 0:
            return DefectDetail(
                defect_type="station.empty_image",
                outcome=Outcome.FAIL,
                description="Input image is empty or null.",
            )

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        mean_val = float(np.mean(gray))
        std_val = float(np.std(gray))

        if std_val < min_std:
            return DefectDetail(
                defect_type="station.flat_image_domain",
                outcome=Outcome.FAIL,
                measured_value=std_val,
                nominal_value=min_std,
                unit="std_dev",
                description=f"Image has insufficient contrast/texture (std={std_val:.1f} < {min_std}). Check lighting, lens cover, or part presence.",
            )

        if mean_val < min_mean:
            return DefectDetail(
                defect_type="station.underexposed_image",
                outcome=Outcome.FAIL,
                measured_value=mean_val,
                nominal_value=min_mean,
                unit="brightness",
                description=f"Image is severely underexposed (mean={mean_val:.1f} < {min_mean}). Check camera exposure and illumination.",
            )

        if mean_val > max_mean:
            return DefectDetail(
                defect_type="station.overexposed_image",
                outcome=Outcome.FAIL,
                measured_value=mean_val,
                nominal_value=max_mean,
                unit="brightness",
                description=f"Image is severely overexposed (mean={mean_val:.1f} > {max_mean}). Check lighting intensity and aperture.",
            )

        # Feature density / Canny edge check for domain/wrong part validation
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.count_nonzero(edges)) / float(edges.size)
        if edge_density < min_edge_density:
            return DefectDetail(
                defect_type="station.invalid_image_domain",
                outcome=Outcome.FAIL,
                measured_value=edge_density,
                nominal_value=min_edge_density,
                unit="edge_density",
                description=f"Image lacks sufficient structural edge features (edge density={edge_density:.4f} < {min_edge_density}). Image may belong to the wrong station or part type.",
            )

        return None
