"""Abstract model inference interface supporting ONNX, TensorRT, and Mock engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import numpy as np
from pydantic import BaseModel, Field

from camerainspection.core.models import BoundingBox


class ModelDetection(BaseModel):
    """Detection output from an AI model (defect detection, segmentation, or anomaly)."""

    class_name: str
    confidence: float
    bounding_box: BoundingBox | None = None
    mask: list[list[int]] | None = None  # Optional polygon points or binary mask summary
    anomaly_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseInferenceEngine(ABC):
    """Abstract interface for AI model execution backends."""

    @abstractmethod
    def load(self, weights_path: str | Path) -> None:
        """Load model weights or compile graph."""

    @abstractmethod
    def predict(self, image: np.ndarray) -> list[ModelDetection]:
        """Perform forward inference on a BGR image array.

        Returns:
            List of detected anomalies or defects with calibrated confidence scores.
        """

    @abstractmethod
    def get_version(self) -> str:
        """Return model/weights version string."""
