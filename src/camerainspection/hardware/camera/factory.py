"""Camera adapter factory selecting appropriate hardware or simulation driver."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from camerainspection.core.config import CameraConfig
from camerainspection.core.exceptions import ConfigurationError
from camerainspection.core.logging import get_logger
from camerainspection.hardware.camera.base import BaseCamera
from camerainspection.hardware.camera.replay import FolderReplayCamera
from camerainspection.hardware.camera.synthetic import SyntheticCamera
from camerainspection.hardware.camera.webcam import WebcamCamera

logger = get_logger("hardware.camera.factory")

VALID_CAMERA_ADAPTERS = {"replay", "synthetic", "webcam", "phone", "rtsp", "ip", "basler", "hikrobot"}


def build_camera(
    camera_config: CameraConfig | dict[str, Any],
    adapter_override: str | None = None,
) -> BaseCamera:
    """Build and return configured BaseCamera adapter instance.

    Supported adapters:
        - "replay": Replays frames from a folder
        - "synthetic": Generates synthetic pattern frames in-memory
        - "webcam": USB / IP camera / RTSP stream via OpenCV
        - "basler": Basler GigE / USB3 Vision camera (pypylon SDK, lazy import)
        - "hikrobot": Hikrobot GigE / USB3 Vision camera (MVS SDK, lazy import)

    Raises:
        ConfigurationError: If adapter is unrecognized.
    """
    if isinstance(camera_config, dict):
        cfg = CameraConfig.model_validate(camera_config)
    else:
        cfg = camera_config

    adapter = (adapter_override or cfg.adapter).lower().strip()

    if adapter == "replay":
        replay_path = Path(cfg.replay_dir) if cfg.replay_dir else Path("data/replay")
        loop = getattr(cfg, "loop", True)
        return FolderReplayCamera(folder_path=replay_path, loop=loop)

    elif adapter == "synthetic":
        width = cfg.resolution[0] if len(cfg.resolution) > 0 else 640
        height = cfg.resolution[1] if len(cfg.resolution) > 1 else 480
        pattern = getattr(cfg, "pattern", "solid_black")
        return SyntheticCamera(width=width, height=height, pattern=pattern)

    elif adapter in ("webcam", "phone", "rtsp", "ip"):
        logger.warning(
            "Non-industrial camera (webcam/phone) in use: exposure_us and gain_db are ignored "
            "by hardware, and millimetre measurements are uncalibrated."
        )
        width = cfg.resolution[0] if len(cfg.resolution) > 0 else 1920
        height = cfg.resolution[1] if len(cfg.resolution) > 1 else 1080
        return WebcamCamera(camera_id=cfg.camera_id, width=width, height=height)

    elif adapter == "basler":
        from camerainspection.hardware.camera.basler import BaslerCamera

        serial_number = getattr(cfg, "serial_number", None)
        return BaslerCamera(
            serial_number=serial_number,
            exposure_us=cfg.exposure_us,
            gain_db=cfg.gain_db,
            timeout_ms=cfg.timeout_ms,
        )

    elif adapter == "hikrobot":
        from camerainspection.hardware.camera.hikrobot import HikrobotCamera

        serial_number = getattr(cfg, "serial_number", None)
        return HikrobotCamera(
            serial_number=serial_number,
            exposure_us=cfg.exposure_us,
            gain_db=cfg.gain_db,
            timeout_ms=cfg.timeout_ms,
        )

    else:
        raise ConfigurationError(
            f"Unknown camera adapter '{adapter}'. "
            f"Valid adapters are: {sorted(VALID_CAMERA_ADAPTERS)}."
        )
