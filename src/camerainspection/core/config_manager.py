"""Configuration Manager service for reading, writing, and validating station and limits YAML configs with audit logging."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml

from camerainspection.core.config import (
    StationConfig,
    load_station_config,
    load_yaml,
    ConfigurationError,
)
from camerainspection.storage.db import DatabaseManager


STATION_FILE_MAP = {
    "STATION_1": "configs/stations/station_1_leather.yaml",
    "STATION_2": "configs/stations/station_2_stitch.yaml",
    "STATION_3": "configs/stations/station_3_plastic.yaml",
    "STATION_4": "configs/stations/station_4_complete.yaml",
}


class ConfigurationManager:
    """Manages runtime reading, validation, persistence, and audit logging of configs."""

    def __init__(self, root_dir: Path | str = ".", db_manager: DatabaseManager | None = None):
        self.root_dir = Path(root_dir)
        self.db_manager = db_manager

    def get_station_file_path(self, station_id: str) -> Path:
        rel = STATION_FILE_MAP.get(station_id.upper())
        if not rel:
            raise ConfigurationError(f"Unknown station ID: {station_id}")
        return self.root_dir / rel

    def load_station_config(self, station_id: str) -> dict[str, Any]:
        path = self.get_station_file_path(station_id)
        raw = load_yaml(path)
        return raw

    def save_station_config(
        self, station_id: str, new_data: dict[str, Any], author: str = "system"
    ) -> StationConfig:
        path = self.get_station_file_path(station_id)

        # Validate against StationConfig Pydantic model before saving (fail-closed)
        try:
            validated = StationConfig.model_validate(new_data)
        except Exception as e:
            raise ConfigurationError(f"Invalid station configuration payload: {e}") from e

        # Load old config for audit diff if possible
        old_data = {}
        if path.exists():
            old_data = load_yaml(path)

        # Save to YAML
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(new_data, f, sort_keys=False, default_flow_style=False)

        # Log audit event
        if self.db_manager:
            try:
                self.db_manager.log_audit(
                    seat_id=None,
                    station_id=station_id.upper(),
                    event_type="CONFIG_UPDATED",
                    details=f"Configuration updated by {author}. Station: {station_id}",
                )
            except Exception:
                pass  # Non-blocking audit logging

        return validated

    def load_limits_config(self) -> dict[str, Any]:
        limits_path = self.root_dir / "configs/variants/default_limits.yaml"
        return load_yaml(limits_path)

    def save_limits_config(
        self, new_data: dict[str, Any], author: str = "system"
    ) -> dict[str, Any]:
        limits_path = self.root_dir / "configs/variants/default_limits.yaml"

        with open(limits_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(new_data, f, sort_keys=False, default_flow_style=False)

        if self.db_manager:
            try:
                self.db_manager.log_audit(
                    seat_id=None,
                    station_id=None,
                    event_type="LIMITS_CONFIG_UPDATED",
                    details=f"Global limits configuration updated by {author}.",
                )
            except Exception:
                pass

        return new_data
