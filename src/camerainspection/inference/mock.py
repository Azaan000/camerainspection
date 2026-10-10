"""Deterministic mock inference engine for development and testing."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from camerainspection.inference.base import BaseInferenceEngine, ModelDetection


class MockInferenceEngine(BaseInferenceEngine):
    """Configurable mock engine that can return preset detections or clean passes."""

    def __init__(
        self,
        preset_detections: list[ModelDetection] | None = None,
        version: str = "mock-v0.1.0",
    ) -> None:
        self.preset_detections = preset_detections or []
        self.version = version
        self.loaded_path: Path | None = None

    def load(self, weights_path: str | Path) -> None:
        self.loaded_path = Path(weights_path)

    def predict(self, image: np.ndarray) -> list[ModelDetection]:
        # Return configured detections
        return list(self.preset_detections)

    def set_detections(self, detections: list[ModelDetection]) -> None:
        self.preset_detections = list(detections)

    def clear_detections(self) -> None:
        self.preset_detections.clear()

    def get_version(self) -> str:
        return self.version
