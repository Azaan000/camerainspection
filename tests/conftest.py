"""Pytest fixtures for unit and integration testing."""

import os
from pathlib import Path
import pytest

from camerainspection.core.config import load_station_config, load_variant_config
from camerainspection.hardware.camera.synthetic import SyntheticCamera
from camerainspection.hardware.plc.simulator import PLCSimulator
from camerainspection.storage.db import DatabaseManager

# Strong 32+ char test key for test suite
TEST_API_KEY = "test_secret_inspection_key_32_characters_long_min!"
os.environ["INSPECTION_API_KEY"] = TEST_API_KEY

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True, scope="session")
def setup_test_api_key() -> None:
    """Ensure strong API key is set for test session."""
    os.environ["INSPECTION_API_KEY"] = TEST_API_KEY


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def configs_dir(project_root: Path) -> Path:
    return project_root / "configs"


@pytest.fixture
def variants_dir(configs_dir: Path) -> Path:
    return configs_dir / "variants"


@pytest.fixture
def default_limits_path(variants_dir: Path) -> Path:
    return variants_dir / "default_limits.yaml"


@pytest.fixture
def in_memory_db() -> DatabaseManager:
    """In-memory SQLite database instance with initialized schema."""
    db = DatabaseManager("sqlite:///:memory:")
    db.init_tables()
    return db


@pytest.fixture
def plc_sim() -> PLCSimulator:
    """Connected PLC simulator instance."""
    sim = PLCSimulator()
    sim.connect()
    return sim


@pytest.fixture
def synthetic_camera() -> SyntheticCamera:
    """Connected synthetic camera instance."""
    cam = SyntheticCamera(width=640, height=480, pattern="stitch_line")
    cam.connect()
    return cam
