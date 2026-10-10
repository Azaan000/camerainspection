"""Unit tests for configuration loaders and validation."""

from pathlib import Path

import pytest

from camerainspection.core.config import (
    load_station_config,
    load_system_config,
    load_variant_config,
    load_yaml,
)
from camerainspection.core.exceptions import UnknownVariantError


def test_load_default_oem_limits(default_limits_path: Path) -> None:
    data = load_yaml(default_limits_path)
    assert "limits" in data
    limits = data["limits"]
    assert "stitch" in limits
    assert "leather" in limits
    assert "plastic" in limits
    assert "mechanism" in limits

    # Verify key starting values
    assert limits["stitch"]["skip_length_mm"]["fail_at"] == 5.0
    assert limits["stitch"]["broken_thread"]["fail_on_any"] is True
    assert limits["plastic"]["flash_mm"]["pass_max"] == 0.3


def test_load_all_standard_variants(variants_dir: Path, default_limits_path: Path) -> None:
    expected_variants = [
        "FRONT_LH_BLACK",
        "FRONT_RH_BLACK",
        "REAR_BENCH_BLACK",
        "FRONT_LH_GREY",
    ]
    for vid in expected_variants:
        cfg, merged_limits = load_variant_config(
            variant_id=vid,
            variants_root=variants_dir,
            default_limits_path=default_limits_path,
        )
        assert cfg.variant_id == vid
        assert "stitch" in merged_limits
        assert "plastic" in merged_limits


def test_variant_limit_override(variants_dir: Path, default_limits_path: Path) -> None:
    # FRONT_LH_BLACK has no overrides -> base thread_color pass_max = 3.0
    cfg_black, limits_black = load_variant_config("FRONT_LH_BLACK", variants_dir, default_limits_path)
    assert limits_black["stitch"]["thread_color_delta_e"]["pass_max"] == 3.0

    # FRONT_LH_GREY has override -> pass_max = 2.5, fail_at = 4.0
    cfg_grey, limits_grey = load_variant_config("FRONT_LH_GREY", variants_dir, default_limits_path)
    assert limits_grey["stitch"]["thread_color_delta_e"]["pass_max"] == 2.5
    assert limits_grey["stitch"]["thread_color_delta_e"]["fail_at"] == 4.0


def test_unknown_variant_raises_error(variants_dir: Path) -> None:
    with pytest.raises(UnknownVariantError):
        load_variant_config("NON_EXISTENT_SEAT", variants_dir)


def test_load_station_configs(configs_dir: Path) -> None:
    stations = [
        "station_1_leather.yaml",
        "station_2_stitch.yaml",
        "station_3_plastic.yaml",
        "station_4_complete.yaml",
    ]
    for st_file in stations:
        st_path = configs_dir / "stations" / st_file
        cfg = load_station_config(st_path)
        assert cfg.enabled is True
        assert cfg.camera.adapter in ["replay", "webcam", "basler", "hikrobot"]
        assert cfg.trigger.timeout_s > 0


def test_load_system_config(configs_dir: Path) -> None:
    sys_path = configs_dir / "system.yaml"
    cfg = load_system_config(sys_path)
    assert cfg.system["config_version"] == "v0.1.0"
    assert "STATION_1" in cfg.coordinator.expected_stations
