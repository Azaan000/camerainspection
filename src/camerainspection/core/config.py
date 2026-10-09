"""Configuration loader and Pydantic schemas for stations, variants, and OEM limits."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from camerainspection.core.exceptions import ConfigurationError, UnknownVariantError


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override dictionary into base dictionary."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class RangeLimit(BaseModel):
    """Range limit where value <= pass_max is PASS, pass_max < value < fail_at is REVIEW, >= fail_at is FAIL."""

    pass_max: float
    fail_at: float


class ToleranceLimit(BaseModel):
    """Tolerance limit where |value - nominal| <= pass_tol is PASS, <= fail_tol is REVIEW, > fail_tol is FAIL."""

    pass_tol: float
    fail_tol: float


class BooleanRule(BaseModel):
    """Rule triggering immediate FAIL or REVIEW on detection."""

    fail_on_any: bool = False
    review_on_any: bool = False
    fail_on_any_missing_or_wrong: bool = False
    required: bool = False


class ROIConfig(BaseModel):
    x: int
    y: int
    w: int
    h: int


class CameraConfig(BaseModel):
    name: str = "main"
    view: str = "main"
    enabled: bool = True
    adapter: str = "replay"
    replay_dir: str = ""
    resolution: list[int] = Field(default_factory=lambda: [2592, 1944])
    exposure_us: int = 15000
    gain_db: float = 0.0
    pixel_size_mm: float = 0.08
    timeout_ms: int = 3000
    camera_id: int | str = 0
    serial_number: str | None = None
    loop: bool = True
    pattern: str = "solid_black"
    regions_of_interest: dict[str, ROIConfig] = Field(default_factory=dict)
    lighting: dict[str, Any] = Field(default_factory=dict)
    poses: list[dict[str, Any]] = Field(default_factory=list)


class StationModelConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    backend: str = "mock"
    model_type: str = "generic"
    weights_path: str = ""
    version: str = "v0.1.0"
    threshold: float = 0.5


class TriggerConfig(BaseModel):
    timeout_s: float = 5.0


class StationConfig(BaseModel):
    station_id: str
    name: str
    description: str = ""
    enabled: bool = True
    camera: CameraConfig
    cameras: list[CameraConfig] = Field(default_factory=list)
    lighting: dict[str, Any] = Field(default_factory=dict)
    regions_of_interest: dict[str, ROIConfig] = Field(default_factory=dict)
    matching: dict[str, Any] = Field(default_factory=dict)
    mechanism: dict[str, Any] = Field(default_factory=dict)
    model: StationModelConfig = Field(default_factory=StationModelConfig)
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    capture_sequence: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def harmonize_cameras(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw_camera = data.get("camera")
            raw_cameras = data.get("cameras")
            if raw_cameras and isinstance(raw_cameras, list):
                if not raw_camera and len(raw_cameras) > 0:
                    data["camera"] = raw_cameras[0]
            elif raw_camera:
                cam_dict = dict(raw_camera) if isinstance(raw_camera, dict) else raw_camera.model_dump()
                cam_dict.setdefault("name", "main")
                cam_dict.setdefault("view", "main")
                data["cameras"] = [cam_dict]
            elif not raw_cameras and not raw_camera:
                default_cam = {"name": "main", "view": "main", "adapter": "replay"}
                data["camera"] = default_cam
                data["cameras"] = [default_cam]
        return data


class ComponentSpec(BaseModel):
    expected_hand: str | None = None
    count: int = 1
    required: bool = True


class VariantConfig(BaseModel):
    variant_id: str
    description: str = ""
    hand: str = "LH"
    position: str = "FRONT"
    color: str = "BLACK"
    nominals: dict[str, dict[str, Any]] = Field(default_factory=dict)
    components: dict[str, ComponentSpec] = Field(default_factory=dict)
    golden_images_dir: str = "golden_images"
    limit_overrides: dict[str, Any] = Field(default_factory=dict)


class SystemDatabaseConfig(BaseModel):
    url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/inspection.db")
    )
    echo_sql: bool = False


class SystemPLCConfig(BaseModel):
    adapter: str = "simulator"
    host: str = "127.0.0.1"
    port: int = 502
    rack: int = 0
    slot: int = 1
    poll_interval_ms: int = 100


class SystemStorageConfig(BaseModel):
    image_dir: str = "storage/images"
    raw_image_dir: str = "storage/images/raw"
    annotated_image_dir: str = "storage/images/annotated"
    defect_crops_dir: str = "storage/images/defects"


class SystemCoordinatorConfig(BaseModel):
    expected_stations: list[str] = Field(
        default_factory=lambda: ["STATION_1", "STATION_2", "STATION_3", "STATION_4"]
    )
    cycle_timeout_s: float = 60.0


class SystemConfig(BaseModel):
    system: dict[str, Any] = Field(
        default_factory=lambda: {
            "environment": "development",
            "shadow_mode": False,
            "config_version": "v0.1.0",
        }
    )
    database: SystemDatabaseConfig = Field(default_factory=SystemDatabaseConfig)
    plc: SystemPLCConfig = Field(default_factory=SystemPLCConfig)
    storage: SystemStorageConfig = Field(default_factory=SystemStorageConfig)
    coordinator: SystemCoordinatorConfig = Field(default_factory=SystemCoordinatorConfig)

    @property
    def environment(self) -> str:
        return str(self.system.get("environment", "development"))

    @property
    def shadow_mode(self) -> bool:
        return bool(self.system.get("shadow_mode", False))

    @property
    def config_version(self) -> str:
        return str(self.system.get("config_version", "v0.1.0"))


def load_yaml(file_path: Path) -> dict[str, Any]:
    """Safely load a YAML file and return a dictionary."""
    if not file_path.exists():
        raise ConfigurationError(f"Configuration file not found: {file_path}")
    try:
        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        raise ConfigurationError(f"Failed to parse YAML file {file_path}: {e}") from e


def load_station_config(file_path: Path) -> StationConfig:
    """Load and validate a Station configuration from a YAML file."""
    raw = load_yaml(file_path)
    try:
        return StationConfig.model_validate(raw)
    except Exception as e:
        raise ConfigurationError(f"Invalid station config at {file_path}: {e}") from e


def load_system_config(file_path: Path) -> SystemConfig:
    """Load and validate system configuration."""
    raw = load_yaml(file_path)
    try:
        return SystemConfig.model_validate(raw)
    except Exception as e:
        raise ConfigurationError(f"Invalid system config at {file_path}: {e}") from e


def load_variant_config(
    variant_id: str,
    variants_root: Path,
    default_limits_path: Path | None = None,
) -> tuple[VariantConfig, dict[str, Any]]:
    """Load variant configuration and merge limit overrides with default OEM limits.

    Returns:
        tuple[VariantConfig, merged_limits_dict]
    """
    variant_dir = variants_root / variant_id
    config_file = variant_dir / "config.yaml"
    if not config_file.exists():
        raise UnknownVariantError(
            f"Variant '{variant_id}' not found at {variant_dir}. "
            f"Adding a variant requires a new config folder at configs/variants/{variant_id}/config.yaml"
        )

    variant_raw = load_yaml(config_file)
    variant_config = VariantConfig.model_validate(variant_raw)

    # Base limits
    base_limits_path = default_limits_path or (variants_root / "default_limits.yaml")
    base_limits_raw = load_yaml(base_limits_path) if base_limits_path.exists() else {}
    base_limits = base_limits_raw.get("limits", {})

    # Merge overrides
    overrides = variant_config.limit_overrides
    merged_limits = _deep_merge(base_limits, overrides)

    return variant_config, merged_limits
