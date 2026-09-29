"""Integration smoke for the retained physical Node B stationary record."""

from pathlib import Path
from typing import Any, cast

import pytest

from validation.m1_single_node_smoke import load_smoke_config, run_smoke

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "tests/fixtures/acquisition/node-config.json"


def test_retained_node_b_record_reaches_calibration_and_ahrs_interfaces() -> None:
    config = load_smoke_config(CONFIG_PATH)

    result = cast(dict[str, Any], run_smoke(config))

    assert result["result"] == "pass"
    assert result["input"]["sha256"] == config.expected_input_sha256
    assert result["input"]["sample_count"] == 832
    assert result["input"]["packet_count"] == 208
    assert result["raw_counts"]["signed_int16_status"] == "pass"
    assert result["qc"]["all_zero_issue_counts"] is True
    assert result["timestamps"]["monotonic"] is True
    assert result["timestamps"]["resampling"] == "none"
    assert result["interfaces"]["calibration"]["status"] == "pass"
    assert result["interfaces"]["calibration"]["samples"] == 832
    assert result["interfaces"]["ahrs"]["status"] == "pass"
    assert result["interfaces"]["ahrs"]["updated_samples"] == 832
    assert result["sensor"]["accel_odr_hz"] == 104.0
    assert result["sensor"]["gyro_odr_hz"] == 104.0
    assert result["clipping"]["accel_clipped_samples"] == 0
    assert result["clipping"]["gyro_clipped_samples"] == 0

    # Source: node_b_20260913_compatibility.md records this stationary capture's
    # raw-count norm range; after the documented SI adapter, a stationary record
    # must remain in the broad 0.5 g--1.5 g engineering plausibility band.
    assert 0.5 * 9.80665 <= result["units"]["accel_norm_mps2"]["median"] <= 1.5 * 9.80665
    assert result["units"]["gyro_norm_rads"]["max"] <= 0.5


def test_smoke_report_retains_non_m2_scope_and_explicit_frame_contract() -> None:
    config = load_smoke_config(CONFIG_PATH)

    result = cast(dict[str, Any], run_smoke(config))

    assert result["scope"]["m2_claims"] is False
    assert result["frames"]["sensor_axes"] == ["sensor_x", "sensor_y", "sensor_z"]
    assert result["frames"]["node_axes"] == ["node_x", "node_y", "node_z"]
    assert result["frames"]["sensor_to_node_matrix"] == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    assert result["frames"]["anatomical_alignment"] is False
