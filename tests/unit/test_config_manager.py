"""Unit tests for ConfigurationManager service."""

from __future__ import annotations

from pathlib import Path
import pytest

from camerainspection.core.config_manager import ConfigurationManager
from camerainspection.core.exceptions import ConfigurationError
from camerainspection.storage.db import DatabaseManager


def test_config_manager_load_and_save_station(tmp_path: Path, in_memory_db: DatabaseManager) -> None:
    # Copy configs structure or use root_dir pointing to project root
    root = Path(__file__).resolve().parents[2]
    mgr = ConfigurationManager(root_dir=root, db_manager=in_memory_db)

    # Load station 2 config
    st2_cfg = mgr.load_station_config("STATION_2")
    assert st2_cfg["station_id"] == "STATION_2"
    assert "cameras" in st2_cfg

    # Save valid update
    st2_cfg["description"] = "Updated description for test"
    validated = mgr.save_station_config("STATION_2", st2_cfg, author="test_engineer")
    assert validated.description == "Updated description for test"


def test_config_manager_invalid_station_raises(in_memory_db: DatabaseManager) -> None:
    root = Path(__file__).resolve().parents[2]
    mgr = ConfigurationManager(root_dir=root, db_manager=in_memory_db)
    with pytest.raises(ConfigurationError):
        mgr.load_station_config("INVALID_STATION")


def test_config_manager_invalid_pydantic_payload_rejects(in_memory_db: DatabaseManager) -> None:
    root = Path(__file__).resolve().parents[2]
    mgr = ConfigurationManager(root_dir=root, db_manager=in_memory_db)
    invalid_data = {
        "station_id": "STATION_2",
        "name": 12345,  # should be string
        "camera": {"adapter": "invalid_adapter_name"},
    }
    with pytest.raises(ConfigurationError):
        mgr.save_station_config("STATION_2", invalid_data, author="test_engineer")


def test_config_manager_limits(in_memory_db: DatabaseManager) -> None:
    root = Path(__file__).resolve().parents[2]
    mgr = ConfigurationManager(root_dir=root, db_manager=in_memory_db)
    limits = mgr.load_limits_config()
    assert "limits" in limits

    limits["limits"]["stitch"]["skip_length_mm"]["fail_at"] = 6.0
    saved = mgr.save_limits_config(limits, author="test_operator")
    assert saved["limits"]["stitch"]["skip_length_mm"]["fail_at"] == 6.0
