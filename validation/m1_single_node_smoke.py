"""Run the M1 single-node numerical integration smoke on an immutable record.

This module is validation/report code.  The production raw-count conversion
boundary lives in ``kineimu_shoulder.io.m1_raw``; this runner only selects a
record, audits it, invokes the pinned calibration/AHRS APIs, and writes
machine-readable evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import math
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import imufusion
import numpy as np
from numpy.typing import NDArray

from kineimu_shoulder.io.m1_capture import iter_capture_records
from kineimu_shoulder.io.m1_packet import NodeId, SampleFlags, decode_sample_packet
from kineimu_shoulder.io.m1_qc import SequenceQcReport, audit_capture_stream
from kineimu_shoulder.io.m1_raw import (
    STANDARD_GRAVITY_MPS2,
    ConvertedImuData,
    M1RawCountAdapterConfig,
    SensorToNodeTransform,
    convert_raw_samples,
)

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class SmokeConfig:
    """Resolved configuration for one reproducible validation run."""

    config_path: Path
    repository_root: Path
    input_path: Path
    expected_input_sha256: str
    expected_node_id: NodeId
    expected_packet_count: int
    expected_sample_count: int
    firmware: dict[str, str]
    sensor_model: str
    sensor_driver: str
    timestamp_source: str
    accel_odr_hz: float
    gyro_odr_hz: float
    raw_register_order: tuple[str, str, str]
    sensor: M1RawCountAdapterConfig
    timestamp_dt_us_bounds: tuple[float, float]
    stationary_accel_norm_g_bounds: tuple[float, float]
    stationary_gyro_norm_max_rads: float


def load_smoke_config(path: Path) -> SmokeConfig:
    """Load and resolve the committed JSON experiment configuration."""

    config_path = path.resolve()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("smoke config root must be a JSON object")

    repository_root = (config_path.parent / _required_string(raw, "repository_root")).resolve()
    input_path = Path(_required_string(raw, "input_path"))
    if not input_path.is_absolute():
        input_path = repository_root / input_path

    sensor_raw = _required_object(raw, "sensor")
    transform_raw = _required_object(sensor_raw, "sensor_to_node")
    transform = SensorToNodeTransform(
        sensor_axes=_required_string_tuple(transform_raw, "sensor_axes"),
        node_axes=_required_string_tuple(transform_raw, "node_axes"),
        sensor_to_node=_matrix3(transform_raw, "matrix"),
        description=_required_string(transform_raw, "description"),
    )
    sensor_config = M1RawCountAdapterConfig(
        accel_range_g=_required_float(sensor_raw, "accel_range_g"),
        gyro_range_dps=_required_float(sensor_raw, "gyro_range_dps"),
        accel_sensitivity_mg_per_lsb=_required_float(sensor_raw, "accel_sensitivity_mg_per_lsb"),
        gyro_sensitivity_mdps_per_lsb=_required_float(sensor_raw, "gyro_sensitivity_mdps_per_lsb"),
        axis_transform=transform,
    )
    raw_register_order = _required_string_tuple(sensor_raw, "raw_register_order")

    checks_raw = _required_object(raw, "checks")
    dt_bounds = _float_pair(checks_raw, "timestamp_dt_us_bounds")
    accel_bounds = _float_pair(checks_raw, "stationary_accel_norm_g_bounds")
    gyro_max = _required_float(checks_raw, "stationary_gyro_norm_max_rads")
    expected_hash = _required_string(raw, "expected_input_sha256").lower()
    if len(expected_hash) != 64 or any(character not in "0123456789abcdef" for character in expected_hash):
        raise ValueError("expected_input_sha256 must be a 64-character hexadecimal SHA-256")

    firmware_raw = _required_object(raw, "firmware")
    firmware = {str(key): str(value) for key, value in firmware_raw.items()}
    return SmokeConfig(
        config_path=config_path,
        repository_root=repository_root,
        input_path=input_path.resolve(),
        expected_input_sha256=expected_hash,
        expected_node_id=NodeId[_required_string(raw, "node_id")],
        expected_packet_count=_required_int(raw, "expected_packet_count"),
        expected_sample_count=_required_int(raw, "expected_sample_count"),
        firmware=firmware,
        sensor_model=_required_string(sensor_raw, "model"),
        sensor_driver=_required_string(sensor_raw, "driver"),
        timestamp_source=_required_string(sensor_raw, "timestamp_source"),
        accel_odr_hz=_required_float(sensor_raw, "accel_odr_hz"),
        gyro_odr_hz=_required_float(sensor_raw, "gyro_odr_hz"),
        raw_register_order=raw_register_order,
        sensor=sensor_config,
        timestamp_dt_us_bounds=dt_bounds,
        stationary_accel_norm_g_bounds=accel_bounds,
        stationary_gyro_norm_max_rads=gyro_max,
    )


def run_smoke(config: SmokeConfig, *, command: str | None = None) -> dict[str, object]:
    """Run the immutable-record audit and backend interface smoke."""

    input_bytes = config.input_path.read_bytes()
    input_sha256 = hashlib.sha256(input_bytes).hexdigest()
    if input_sha256 != config.expected_input_sha256:
        raise ValueError(
            f"input SHA-256 mismatch for {config.input_path}: "
            f"expected {config.expected_input_sha256}, got {input_sha256}"
        )

    qc = audit_capture_stream(io.BytesIO(input_bytes), expected_node_id=config.expected_node_id)
    records = tuple(iter_capture_records(io.BytesIO(input_bytes)))
    packets = tuple(decode_sample_packet(record.payload) for record in records)
    samples = tuple(sample for packet in packets for sample in packet.samples)
    if not samples:
        raise ValueError("selected M1 record contains no decodable samples")

    converted = convert_raw_samples(samples, config=config.sensor)
    timestamps = np.asarray(converted.device_time_us, dtype=np.float64)
    dt_us = np.diff(timestamps)
    timestamp_monotonic = bool(np.all(dt_us > 0.0))
    if not timestamp_monotonic:
        raise ValueError("device timestamps are not strictly increasing; refusing AHRS integration")

    calibrated_accel, calibrated_gyro, calibration_metadata = _run_identity_calibration(
        converted.accel_mps2,
        converted.gyro_rads,
    )
    quaternions, ahrs_metadata = _run_ahrs(
        calibrated_accel,
        calibrated_gyro,
        timestamps,
    )

    clipping = _clipping_report(converted, config.sensor)
    accel_norm = np.linalg.norm(converted.accel_mps2, axis=1)
    gyro_norm = np.linalg.norm(converted.gyro_rads, axis=1)
    raw_domain_clear = bool(
        np.all(converted.accel_raw_counts >= -32_768)
        and np.all(converted.accel_raw_counts <= 32_767)
        and np.all(converted.gyro_raw_counts >= -32_768)
        and np.all(converted.gyro_raw_counts <= 32_767)
    )
    accel_abs_max = np.max(np.abs(converted.accel_mps2), axis=0)
    gyro_abs_max = np.max(np.abs(converted.gyro_rads), axis=0)
    accel_full_scale = config.sensor.accel_range_g * float(STANDARD_GRAVITY_MPS2)
    gyro_full_scale = config.sensor.gyro_range_dps * math.pi / 180.0

    qc_counts = _qc_counts(qc)
    qc_clear = all(count == 0 for count in qc_counts.values())
    epoch_values = sorted({packet.clock_epoch for packet in packets})
    range_clear = bool(np.max(accel_abs_max) <= accel_full_scale + config.sensor.accel_lsb_to_mps2)
    range_clear = range_clear and bool(np.max(gyro_abs_max) <= gyro_full_scale + config.sensor.gyro_lsb_to_rads)
    units_clear = (
        config.stationary_accel_norm_g_bounds[0] * float(STANDARD_GRAVITY_MPS2)
        <= float(np.median(accel_norm))
        <= config.stationary_accel_norm_g_bounds[1] * float(STANDARD_GRAVITY_MPS2)
        and float(np.max(gyro_norm)) <= config.stationary_gyro_norm_max_rads
    )
    timestamp_clear = (
        timestamp_monotonic
        and config.timestamp_dt_us_bounds[0] <= float(np.min(dt_us))
        and float(np.max(dt_us)) <= config.timestamp_dt_us_bounds[1]
    )
    interface_clear = (
        calibration_metadata["status"] == "pass"
        and ahrs_metadata["status"] == "pass"
        and len(samples) == int(cast(int, calibration_metadata["samples"]))
        and len(samples) == int(cast(int, ahrs_metadata["updated_samples"]))
    )
    checks = {
        "input_hash": True,
        "record_counts": len(records) == config.expected_packet_count and len(samples) == config.expected_sample_count,
        "raw_counts": raw_domain_clear,
        "qc": qc_clear and len(epoch_values) == 1,
        "timestamps": timestamp_clear,
        "units": units_clear,
        "configured_ranges": range_clear,
        "clipping": clipping["flag_consistency"] is True
        and clipping["accel_clipped_samples"] == 0
        and clipping["gyro_clipped_samples"] == 0,
        "interfaces": interface_clear,
        "no_resampling": len(converted.device_time_us) == len(samples),
    }

    report: dict[str, object] = {
        "schema_version": "kineimu.m1.single_node_smoke/0.1",
        "result": "pass" if all(checks.values()) else "fail",
        "input": {
            "path": _relative_path(config.input_path, config.repository_root),
            "sha256": input_sha256,
            "expected_sha256": config.expected_input_sha256,
            "byte_length": len(input_bytes),
            "packet_count": len(records),
            "sample_count": len(samples),
            "node_id": config.expected_node_id.name,
            "clock_epochs": epoch_values,
            "host_arrival_monotonic_ns": {
                "first": records[0].host_monotonic_ns,
                "last": records[-1].host_monotonic_ns,
                "used_for_sample_period": False,
            },
        },
        "firmware": config.firmware,
        "sensor": {
            "model": config.sensor_model,
            "driver": config.sensor_driver,
            "timestamp_source": config.timestamp_source,
            "accel_odr_hz": config.accel_odr_hz,
            "gyro_odr_hz": config.gyro_odr_hz,
            "accel_range_g": config.sensor.accel_range_g,
            "gyro_range_dps": config.sensor.gyro_range_dps,
            "accel_sensitivity_mg_per_lsb": config.sensor.accel_sensitivity_mg_per_lsb,
            "gyro_sensitivity_mdps_per_lsb": config.sensor.gyro_sensitivity_mdps_per_lsb,
            "raw_register_order": list(config.raw_register_order),
        },
        "raw_counts": {
            "axis_order": list(config.raw_register_order),
            "accel_min": converted.accel_raw_counts.min(axis=0).tolist(),
            "accel_max": converted.accel_raw_counts.max(axis=0).tolist(),
            "gyro_min": converted.gyro_raw_counts.min(axis=0).tolist(),
            "gyro_max": converted.gyro_raw_counts.max(axis=0).tolist(),
            "signed_int16_min": -32_768,
            "signed_int16_max": 32_767,
            "signed_int16_status": "pass" if raw_domain_clear else "fail",
        },
        "frames": {
            "sensor_axes": list(converted.axis_transform.sensor_axes),
            "node_axes": list(converted.axis_transform.node_axes),
            "sensor_to_node_matrix": [list(row) for row in converted.axis_transform.sensor_to_node],
            "matrix_semantics": "node column vector = sensor_to_node_matrix * sensor column vector",
            "description": converted.axis_transform.description,
            "raw_axis_order": list(config.raw_register_order),
            "anatomical_alignment": False,
        },
        "qc": {
            "issue_counts": qc_counts,
            "all_zero_issue_counts": qc_clear,
            "epoch_count": len(epoch_values),
        },
        "timestamps": {
            "source": "device_time_us",
            "monotonic": timestamp_monotonic,
            "resampling": "none",
            "sample_interval_us": {
                "min": float(np.min(dt_us)),
                "median": float(np.median(dt_us)),
                "max": float(np.max(dt_us)),
            },
            "actual_rate_hz_from_device_span": float((len(timestamps) - 1) * 1e6 / (timestamps[-1] - timestamps[0])),
            "used_for_ahrs_period": "each observed device-time delta; first sample reuses first observed delta",
        },
        "units": {
            "acceleration": "m/s^2",
            "angular_velocity": "rad/s",
            "accel_lsb_to_mps2": config.sensor.accel_lsb_to_mps2,
            "gyro_lsb_to_rads": config.sensor.gyro_lsb_to_rads,
            "accel_abs_max_mps2": accel_abs_max.tolist(),
            "gyro_abs_max_rads": gyro_abs_max.tolist(),
            "accel_norm_mps2": _summary(accel_norm),
            "gyro_norm_rads": _summary(gyro_norm),
            "range_check": {
                "accel_full_scale_mps2": accel_full_scale,
                "gyro_full_scale_rads": gyro_full_scale,
                "status": "pass" if range_clear else "fail",
            },
            "stationary_magnitude_check": {
                "accel_norm_g_bounds": list(config.stationary_accel_norm_g_bounds),
                "gyro_norm_max_rads": config.stationary_gyro_norm_max_rads,
                "status": "pass" if units_clear else "fail",
            },
        },
        "clipping": clipping,
        "interfaces": {
            "calibration": calibration_metadata,
            "ahrs": ahrs_metadata,
        },
        "checks": checks,
        "scope": {
            "m2_claims": False,
            "anatomical_claims": False,
            "claims": [
                "M1 numerical input and third-party API integration compatibility only",
                "identity calibration call and AHRS call completed on the selected record",
            ],
            "not_claimed": [
                "M2 calibration quality or estimated calibration parameters",
                "heading or yaw validity",
                "sensor-to-segment/anatomical alignment",
                "glenohumeral, scapular, or shoulder-joint angle validation",
            ],
        },
        "reproducibility": {
            "config_path": _relative_path(config.config_path, config.repository_root),
            "config_sha256": _sha256_file(config.config_path),
            "software_commit": _git_head(config.repository_root),
            "python": sys.version,
            "imufusion_version": _distribution_version("imufusion"),
            "imucal_version": _distribution_version("imucal"),
            "command": command,
            "raw_data_modified": False,
        },
    }
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    args = build_argument_parser().parse_args()
    config = load_smoke_config(args.config)
    command = "python -m validation.m1_single_node_smoke " + shlex.join(sys.argv[1:])
    report = run_smoke(config, command=command)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["result"] == "pass" else 1


def _run_identity_calibration(
    accel_mps2: FloatArray,
    gyro_rads: FloatArray,
) -> tuple[FloatArray, FloatArray, dict[str, object]]:
    from imucal import FerrarisCalibrationInfo  # type: ignore[import-untyped]

    identity = np.eye(3)
    calibration = FerrarisCalibrationInfo(
        acc_unit="m/s^2",
        gyr_unit="rad/s",
        from_acc_unit="m/s^2",
        from_gyr_unit="rad/s",
        K_a=identity,
        R_a=identity,
        b_a=np.zeros(3),
        K_g=identity,
        R_g=identity,
        K_ga=np.zeros((3, 3)),
        b_g=np.zeros(3),
    )
    calibrated_accel, calibrated_gyro = calibration.calibrate(accel_mps2, gyro_rads, "m/s^2", "rad/s")
    calibration_json = calibration.to_json().encode("utf-8")
    status = (
        calibrated_accel.shape == accel_mps2.shape
        and calibrated_gyro.shape == gyro_rads.shape
        and bool(np.isfinite(calibrated_accel).all())
        and bool(np.isfinite(calibrated_gyro).all())
    )
    return (
        calibrated_accel,
        calibrated_gyro,
        {
            "backend": "imucal",
            "version": _distribution_version("imucal"),
            "status": "pass" if status else "fail",
            "mode": "identity_only_interface_smoke",
            "input_units": {"acceleration": "m/s^2", "angular_velocity": "rad/s"},
            "output_units": {"acceleration": "m/s^2", "angular_velocity": "rad/s"},
            "samples": int(accel_mps2.shape[0]),
            "calibration_artifact_sha256": hashlib.sha256(calibration_json).hexdigest(),
            "estimated_parameters": False,
        },
    )


def _run_ahrs(
    accel_mps2: FloatArray,
    gyro_rads: FloatArray,
    timestamps_us: FloatArray,
) -> tuple[FloatArray, dict[str, object]]:
    periods_s = np.diff(timestamps_us) / 1e6
    periods_for_updates = np.concatenate((periods_s[:1], periods_s))
    quaternions = np.empty((accel_mps2.shape[0], 4), dtype=np.float64)
    ahrs = imufusion.Ahrs()
    for index, period_s in enumerate(periods_for_updates):
        ahrs.set_sample_period(float(period_s))
        ahrs.update_no_magnetometer(
            gyro_rads[index] * 180.0 / math.pi,
            accel_mps2[index] / float(STANDARD_GRAVITY_MPS2),
        )
        quaternion = np.asarray(ahrs.get_quaternion(), dtype=np.float64)
        if quaternion.shape != (4,):
            raise ValueError(f"imufusion returned quaternion shape {quaternion.shape}, expected (4,)")
        quaternions[index] = quaternion

    norms = np.linalg.norm(quaternions, axis=1)
    status = bool(np.isfinite(quaternions).all()) and bool(np.allclose(norms, 1.0, rtol=0.0, atol=1e-5))
    return (
        quaternions,
        {
            "backend": "imufusion",
            "version": _distribution_version("imufusion"),
            "status": "pass" if status else "fail",
            "algorithm_call": "Ahrs.set_sample_period + update_no_magnetometer",
            "input_units": {"acceleration": "g", "angular_velocity": "deg/s"},
            "input_conversion_from_si": "m/s^2 -> g and rad/s -> deg/s",
            "updated_samples": int(quaternions.shape[0]),
            "quaternion_order": ["w", "x", "y", "z"],
            "quaternion_shape": list(quaternions.shape),
            "quaternion_norm": _summary(norms),
            "magnetometer": False,
            "anatomical_alignment": False,
        },
    )


def _clipping_report(converted: ConvertedImuData, config: M1RawCountAdapterConfig) -> dict[str, object]:
    accel_code = math.ceil(config.accel_range_g * 1000.0 / config.accel_sensitivity_mg_per_lsb)
    accel_positive_limit = min(32_767, accel_code)
    accel_negative_magnitude = min(32_768, accel_code)
    gyro_limit = math.ceil(config.gyro_range_dps * 1000.0 / config.gyro_sensitivity_mdps_per_lsb)
    accel_clipped = np.any(
        (converted.accel_raw_counts >= accel_positive_limit)
        | (converted.accel_raw_counts <= -accel_negative_magnitude),
        axis=1,
    )
    gyro_clipped = np.any(
        (converted.gyro_raw_counts >= gyro_limit) | (converted.gyro_raw_counts <= -gyro_limit),
        axis=1,
    )
    sample_flags = np.asarray([int(flag) for flag in converted.sample_flags], dtype=np.uint16)
    flagged_accel = (sample_flags & int(SampleFlags.ACCEL_CLIPPED)) != 0
    flagged_gyro = (sample_flags & int(SampleFlags.GYRO_CLIPPED)) != 0
    return {
        "criterion": "configured code-domain full-scale equivalence; not analog saturation",
        "accel_positive_code": accel_positive_limit,
        "accel_negative_magnitude": accel_negative_magnitude,
        "gyro_code_magnitude": gyro_limit,
        "accel_clipped_samples": int(np.count_nonzero(accel_clipped)),
        "gyro_clipped_samples": int(np.count_nonzero(gyro_clipped)),
        "packet_flagged_accel_samples": int(np.count_nonzero(flagged_accel)),
        "packet_flagged_gyro_samples": int(np.count_nonzero(flagged_gyro)),
        "flag_consistency": bool(
            np.array_equal(accel_clipped, flagged_accel)
            and np.array_equal(gyro_clipped, flagged_gyro)
        ),
    }


def _qc_counts(report: SequenceQcReport) -> dict[str, int]:
    names = (
        "decode_errors",
        "framing_errors",
        "packet_duplicates",
        "packet_reordered",
        "packets_missing",
        "sample_duplicates",
        "sample_reordered",
        "samples_missing",
        "timestamp_duplicates",
        "timestamp_reordered",
        "epoch_changes",
        "node_mismatches",
    )
    return {name: int(getattr(report, name)) for name in names}


def _summary(values: FloatArray) -> dict[str, float]:
    return {
        "min": float(np.min(values)),
        "median": float(np.median(values)),
        "max": float(np.max(values)),
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"
    return completed.stdout.strip()


def _distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _required_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_object(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return value


def _required_float(mapping: dict[str, Any], key: str) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    return float(value)


def _required_int(mapping: dict[str, Any], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _required_string_tuple(mapping: dict[str, Any], key: str) -> tuple[str, str, str]:
    value = mapping.get(key)
    if not isinstance(value, list) or len(value) != 3 or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must contain exactly three strings")
    return (value[0], value[1], value[2])


def _matrix3(mapping: dict[str, Any], key: str) -> tuple[tuple[float, float, float], ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{key} must be a 3x3 matrix")
    rows: list[tuple[float, float, float]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != 3 or any(
            isinstance(item, bool) or not isinstance(item, (int, float)) for item in row
        ):
            raise ValueError(f"{key} must be a 3x3 numeric matrix")
        rows.append((float(row[0]), float(row[1]), float(row[2])))
    return tuple(rows)


def _float_pair(mapping: dict[str, Any], key: str) -> tuple[float, float]:
    value = mapping.get(key)
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{key} must contain two numeric bounds")
    result = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in result) or result[0] > result[1]:
        raise ValueError(f"{key} must be finite and ordered")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
