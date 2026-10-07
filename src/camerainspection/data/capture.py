"""Image capture tool saving frames with production metadata."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import cv2
import numpy as np
from pydantic import BaseModel, Field

from camerainspection.core.logging import get_logger
from camerainspection.hardware.camera.base import BaseCamera

logger = get_logger("data.capture")


class CaptureMetadata(BaseModel):
    """Metadata recorded with every captured image."""

    seat_id: str
    station_id: str
    camera_id: str
    variant_id: str
    lot_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    light_settings: dict[str, Any] = Field(default_factory=dict)
    exposure_us: int | None = None
    gain_db: float | None = None
    pixel_size_mm: float | None = None
    notes: str = ""


class ImageCaptureTool:
    """Acquires and writes images with sidecar JSON metadata."""

    def __init__(self, base_output_dir: str | Path = "data/captures") -> None:
        self.base_output_dir = Path(base_output_dir)

    def capture_and_save(
        self,
        camera: BaseCamera,
        metadata: CaptureMetadata,
        filename_prefix: str | None = None,
    ) -> tuple[Path, Path]:
        """Capture frame from camera and persist image + JSON metadata.

        Returns:
            tuple[image_path, metadata_path]
        """
        frame = camera.capture()

        # Consistent structured directory: base / station_id / variant_id / lot_id /
        target_dir = (
            self.base_output_dir
            / metadata.station_id
            / metadata.variant_id
            / metadata.lot_id
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        prefix = filename_prefix or f"{metadata.seat_id}_{int(datetime.now().timestamp() * 1000)}"
        image_path = target_dir / f"{prefix}.png"
        meta_path = target_dir / f"{prefix}.json"

        # Write image
        success = cv2.imwrite(str(image_path), frame)
        if not success:
            raise IOError(f"Failed to write captured image to {image_path}")

        # Write metadata
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(metadata.model_dump_json(indent=2))

        logger.info(f"Captured and saved frame: {image_path} with metadata: {meta_path}")
        return image_path, meta_path
