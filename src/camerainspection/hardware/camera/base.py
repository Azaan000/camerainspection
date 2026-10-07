"""Abstract camera interface for industrial inspection."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import numpy as np


class BaseCamera(ABC):
    """Abstract interface defining required camera operations."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to camera hardware or initialize stream."""

    @abstractmethod
    def disconnect(self) -> None:
        """Release camera resource and cleanup driver connection."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if camera is online and ready for acquisition."""

    @abstractmethod
    def capture(self) -> np.ndarray:
        """Trigger and acquire a single frame as a BGR numpy array.

        Raises:
            CameraOfflineError: If camera is disconnected.
            CameraTimeoutError: If acquisition exceeds configured timeout.
            CorruptImageError: If returned image is empty or invalid.
        """

    @abstractmethod
    def get_metadata(self) -> dict[str, Any]:
        """Return camera diagnostic metadata (exposure, serial, resolution, source)."""
