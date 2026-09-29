"""Explicit host conversion from M1 raw sensor counts to SI vectors.

The firmware packet stores LSM6DS3TR-C register-order signed counts.  This
adapter performs only the declared scale conversion and the supplied
sensor-to-node axis transform.  It does not infer axes, timestamps, sampling
grids, anatomical alignment, or calibration parameters.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite, pi

import numpy as np
from numpy.typing import NDArray
from scipy.constants import g as _STANDARD_GRAVITY_MPS2  # type: ignore[import-untyped]

from kineimu_shoulder.io.m1_packet import Sample, SampleFlags

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
STANDARD_GRAVITY_MPS2: float = float(_STANDARD_GRAVITY_MPS2)


@dataclass(frozen=True, slots=True)
class SensorToNodeTransform:
    """Declared 3-D transform with column-vector semantics ``node = M * sensor``."""

    sensor_axes: tuple[str, str, str]
    node_axes: tuple[str, str, str]
    sensor_to_node: tuple[tuple[float, float, float], ...]
    description: str

    def __post_init__(self) -> None:
        if len(set(self.sensor_axes)) != 3 or len(set(self.node_axes)) != 3:
            raise ValueError("sensor and node axis labels must each contain three unique labels")
        matrix = np.asarray(self.sensor_to_node, dtype=np.float64)
        if matrix.shape != (3, 3):
            raise ValueError(f"sensor_to_node must be a 3x3 matrix, got shape {matrix.shape}")
        if not bool(np.isfinite(matrix).all()):
            raise ValueError("sensor_to_node must contain only finite values")
        if not bool(np.allclose(matrix @ matrix.T, np.eye(3), rtol=0.0, atol=1e-12)):
            raise ValueError("sensor_to_node must be an orthonormal axis transform")

    def matrix(self) -> FloatArray:
        """Return a defensive floating-point copy of the declared matrix."""

        return np.array(self.sensor_to_node, dtype=np.float64, copy=True)


@dataclass(frozen=True, slots=True)
class M1RawCountAdapterConfig:
    """Sensor configuration required to convert one M1 raw stream."""

    accel_range_g: float
    gyro_range_dps: float
    accel_sensitivity_mg_per_lsb: float
    gyro_sensitivity_mdps_per_lsb: float
    axis_transform: SensorToNodeTransform

    def __post_init__(self) -> None:
        for name, value in (
            ("accel_range_g", self.accel_range_g),
            ("gyro_range_dps", self.gyro_range_dps),
            ("accel_sensitivity_mg_per_lsb", self.accel_sensitivity_mg_per_lsb),
            ("gyro_sensitivity_mdps_per_lsb", self.gyro_sensitivity_mdps_per_lsb),
        ):
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be a finite positive number, got {value!r}")

    @property
    def accel_lsb_to_mps2(self) -> float:
        """Return the acceleration scale in m/s² per signed count."""

        return self.accel_sensitivity_mg_per_lsb * 1e-3 * float(STANDARD_GRAVITY_MPS2)

    @property
    def gyro_lsb_to_rads(self) -> float:
        """Return the angular-rate scale in rad/s per signed count."""

        return self.gyro_sensitivity_mdps_per_lsb * 1e-3 * pi / 180.0


@dataclass(frozen=True, slots=True)
class ConvertedImuData:
    """One-to-one converted samples with raw values and device times retained."""

    sample_sequences: tuple[int, ...]
    device_time_us: tuple[int, ...]
    sample_flags: tuple[SampleFlags, ...]
    accel_raw_counts: IntArray
    gyro_raw_counts: IntArray
    accel_mps2: FloatArray
    gyro_rads: FloatArray
    axis_transform: SensorToNodeTransform


@dataclass(frozen=True, slots=True)
class SensorImuData:
    """Uncalibrated SI values in sensor register axes, before ``R_NS``."""

    sample_sequences: tuple[int, ...]
    device_time_us: tuple[int, ...]
    sample_flags: tuple[SampleFlags, ...]
    accel_raw_counts: IntArray
    gyro_raw_counts: IntArray
    accel_mps2: FloatArray
    gyro_rads: FloatArray


def convert_sensor_samples(
    samples: Sequence[Sample],
    *,
    config: M1RawCountAdapterConfig,
) -> SensorImuData:
    """Scale M1 signed counts to sensor-frame SI without axis conversion."""

    sample_tuple = tuple(samples)
    if not sample_tuple:
        raise ValueError("at least one M1 sample is required")

    for sample in sample_tuple:
        raw_values = (*sample.accel_raw, *sample.gyro_raw)
        if any(not -32_768 <= value <= 32_767 for value in raw_values):
            raise ValueError("M1 raw sensor counts must fit signed int16")

    raw_accel: IntArray = np.asarray([sample.accel_raw for sample in sample_tuple], dtype=np.int64)
    raw_gyro: IntArray = np.asarray([sample.gyro_raw for sample in sample_tuple], dtype=np.int64)
    accel_mps2: FloatArray = raw_accel.astype(np.float64) * config.accel_lsb_to_mps2
    gyro_rads: FloatArray = raw_gyro.astype(np.float64) * config.gyro_lsb_to_rads
    for array in (raw_accel, raw_gyro, accel_mps2, gyro_rads):
        array.setflags(write=False)

    return SensorImuData(
        sample_sequences=tuple(sample.sequence for sample in sample_tuple),
        device_time_us=tuple(sample.device_time_us for sample in sample_tuple),
        sample_flags=tuple(sample.flags for sample in sample_tuple),
        accel_raw_counts=raw_accel,
        gyro_raw_counts=raw_gyro,
        accel_mps2=accel_mps2,
        gyro_rads=gyro_rads,
    )


def convert_raw_samples(
    samples: Sequence[Sample],
    *,
    config: M1RawCountAdapterConfig,
) -> ConvertedImuData:
    """Convert decoded M1 samples without resampling or changing their order."""

    sensor = convert_sensor_samples(samples, config=config)
    matrix = config.axis_transform.matrix()
    accel_mps2: FloatArray = sensor.accel_mps2 @ matrix.T
    gyro_rads: FloatArray = sensor.gyro_rads @ matrix.T
    for array in (accel_mps2, gyro_rads):
        array.setflags(write=False)

    return ConvertedImuData(
        sample_sequences=sensor.sample_sequences,
        device_time_us=sensor.device_time_us,
        sample_flags=sensor.sample_flags,
        accel_raw_counts=sensor.accel_raw_counts,
        gyro_raw_counts=sensor.gyro_raw_counts,
        accel_mps2=accel_mps2,
        gyro_rads=gyro_rads,
        axis_transform=config.axis_transform,
    )
