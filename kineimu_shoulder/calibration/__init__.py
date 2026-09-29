"""Versioned sensor-frame calibration with explicit applicability checks.

Known-pose affine estimation uses NumPy least squares. Application delegates
the pinned imucal affine implementation; axis rotation remains project-owned.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite

import numpy as np
from numpy.typing import NDArray

from kineimu_shoulder.io.m1_packet import NodeId, SampleFlags
from kineimu_shoulder.io.m1_raw import STANDARD_GRAVITY_MPS2, M1RawCountAdapterConfig, SensorToNodeTransform

FloatArray = NDArray[np.float64]


def _vectors(values: FloatArray, name: str) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3 or not len(array):
        raise ValueError(f"{name} must have shape (N,3) with N>0, got {array.shape}")
    if not bool(np.isfinite(array).all()):
        raise ValueError(f"{name} must be finite")
    return array


def _reject_clipping(flags: tuple[SampleFlags, ...] | None, count: int) -> None:
    if flags is None:
        return
    if len(flags) != count:
        raise ValueError("sample_flags length must match sample count")
    if any(flag & (SampleFlags.ACCEL_CLIPPED | SampleFlags.GYRO_CLIPPED) for flag in flags):
        raise ValueError("clipped samples cannot be used for calibration")


@dataclass(frozen=True, slots=True)
class CalibrationArtifact:
    """One node's sensor-coordinate SI calibration and its validity identity."""

    calibration_id: str
    node_id: NodeId
    sensor_id: str
    config: M1RawCountAdapterConfig
    accel_matrix: tuple[tuple[float, float, float], ...]
    accel_bias_mps2: tuple[float, float, float]
    gyro_bias_rads: tuple[float, float, float]
    fit_method: str
    fit_window_us: tuple[int, int]
    source_sha256: tuple[str, ...]
    validity: str
    schema_version: str = "m2-calibration/1.0"

    def __post_init__(self) -> None:
        if self.schema_version != "m2-calibration/1.0":
            raise ValueError("unsupported calibration schema version")
        if not self.calibration_id or not self.sensor_id or not self.fit_method or not self.validity:
            raise ValueError("calibration identity, method and validity must be nonempty")
        if self.fit_window_us[0] >= self.fit_window_us[1] or self.fit_window_us[0] < 0:
            raise ValueError("fit_window_us must be a positive ordered interval")
        if not self.source_sha256 or any(
            len(h) != 64 or any(c not in "0123456789abcdef" for c in h) for h in self.source_sha256
        ):
            raise ValueError("source_sha256 must contain lowercase SHA-256 digests")
        matrix = np.asarray(self.accel_matrix, dtype=np.float64)
        if matrix.shape != (3, 3) or not bool(np.isfinite(matrix).all()) or abs(float(np.linalg.det(matrix))) < 1e-12:
            raise ValueError("accel_matrix must be a finite nonsingular 3x3 matrix")
        if not all(isfinite(x) for x in (*self.accel_bias_mps2, *self.gyro_bias_rads)):
            raise ValueError("calibration biases must be finite")
        if len(self.accel_bias_mps2) != 3 or len(self.gyro_bias_rads) != 3:
            raise ValueError("calibration biases must have three components")
        if not np.isclose(np.linalg.det(self.config.axis_transform.matrix()), 1.0, rtol=0, atol=1e-12):
            raise ValueError("sensor-to-node transform must be a proper rotation")

    def to_json(self) -> str:
        """Serialize all parameters, SI units, sensor configuration and provenance."""

        transform = self.config.axis_transform
        payload = {
            "schema_version": self.schema_version,
            "calibration_id": self.calibration_id,
            "node_id": int(self.node_id),
            "sensor_id": self.sensor_id,
            "units": {"acceleration": "m/s^2", "angular_velocity": "rad/s"},
            "config": {
                "accel_range_g": self.config.accel_range_g,
                "gyro_range_dps": self.config.gyro_range_dps,
                "accel_sensitivity_mg_per_lsb": self.config.accel_sensitivity_mg_per_lsb,
                "gyro_sensitivity_mdps_per_lsb": self.config.gyro_sensitivity_mdps_per_lsb,
                "sensor_axes": transform.sensor_axes,
                "node_axes": transform.node_axes,
                "sensor_to_node": transform.sensor_to_node,
                "description": transform.description,
            },
            "accel_matrix": self.accel_matrix,
            "accel_bias_mps2": self.accel_bias_mps2,
            "gyro_bias_rads": self.gyro_bias_rads,
            "fit_method": self.fit_method,
            "fit_window_us": self.fit_window_us,
            "source_sha256": self.source_sha256,
            "validity": self.validity,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @classmethod
    def from_json(cls, encoded: str) -> CalibrationArtifact:
        """Load a versioned artifact; reject incompatible units and fields."""

        data = json.loads(encoded)
        if data["units"] != {"acceleration": "m/s^2", "angular_velocity": "rad/s"}:
            raise ValueError("calibration artifact requires SI units")
        conf = data["config"]
        transform = SensorToNodeTransform(
            sensor_axes=tuple(conf["sensor_axes"]),
            node_axes=tuple(conf["node_axes"]),
            sensor_to_node=tuple(tuple(row) for row in conf["sensor_to_node"]),
            description=conf["description"],
        )
        config = M1RawCountAdapterConfig(
            accel_range_g=conf["accel_range_g"],
            gyro_range_dps=conf["gyro_range_dps"],
            accel_sensitivity_mg_per_lsb=conf["accel_sensitivity_mg_per_lsb"],
            gyro_sensitivity_mdps_per_lsb=conf["gyro_sensitivity_mdps_per_lsb"],
            axis_transform=transform,
        )
        return cls(
            schema_version=data["schema_version"],
            calibration_id=data["calibration_id"],
            node_id=NodeId(data["node_id"]),
            sensor_id=data["sensor_id"],
            config=config,
            accel_matrix=tuple(tuple(row) for row in data["accel_matrix"]),
            accel_bias_mps2=tuple(data["accel_bias_mps2"]),
            gyro_bias_rads=tuple(data["gyro_bias_rads"]),
            fit_method=data["fit_method"],
            fit_window_us=tuple(data["fit_window_us"]),
            source_sha256=tuple(data["source_sha256"]),
            validity=data["validity"],
        )


def apply_calibration(
    accel_mps2: FloatArray,
    gyro_rads: FloatArray,
    *,
    artifact: CalibrationArtifact,
    node_id: NodeId,
    sensor_id: str,
    config: M1RawCountAdapterConfig,
    sample_flags: tuple[SampleFlags, ...],
) -> tuple[FloatArray, FloatArray]:
    """Apply imucal in sensor axes, then declared proper ``R_NS`` once."""

    if artifact.node_id != node_id:
        raise ValueError("calibration node identity mismatch")
    if artifact.sensor_id != sensor_id:
        raise ValueError("calibration sensor identity mismatch")
    if artifact.config != config:
        raise ValueError("calibration configuration mismatch")
    accel = _vectors(accel_mps2, "acceleration")
    gyro = _vectors(gyro_rads, "gyroscope")
    if accel.shape != gyro.shape:
        raise ValueError("acceleration and gyroscope shapes must match")
    _reject_clipping(sample_flags, len(accel))
    if bool((np.abs(accel) > config.accel_range_g * STANDARD_GRAVITY_MPS2 * 1.001).any()) or bool(
        (np.abs(gyro) > np.deg2rad(config.gyro_range_dps) * 1.001).any()
    ):
        raise ValueError("sensor values exceed configured range")

    from imucal import FerrarisCalibrationInfo  # type: ignore[import-untyped]  # optional pinned extra

    matrix = np.asarray(artifact.accel_matrix, dtype=np.float64)
    identity = np.eye(3)
    calibration = FerrarisCalibrationInfo(
        acc_unit="m/s^2", gyr_unit="rad/s", from_acc_unit="m/s^2", from_gyr_unit="rad/s",
        K_a=np.linalg.inv(matrix), R_a=identity, b_a=np.asarray(artifact.accel_bias_mps2),
        K_g=identity, R_g=identity, K_ga=np.zeros((3, 3)), b_g=np.asarray(artifact.gyro_bias_rads),
    )
    calibrated_acc, calibrated_gyro = calibration.calibrate(accel, gyro, "m/s^2", "rad/s")
    rotation = config.axis_transform.matrix()
    node_acc: FloatArray = np.asarray(calibrated_acc @ rotation.T, dtype=np.float64)
    node_gyro: FloatArray = np.asarray(calibrated_gyro @ rotation.T, dtype=np.float64)
    node_acc.setflags(write=False)
    node_gyro.setflags(write=False)
    return node_acc, node_gyro


def estimate_accelerometer_affine(
    measured_mps2: FloatArray,
    reference_mps2: FloatArray,
    *,
    sample_flags: tuple[SampleFlags, ...] | None = None,
) -> tuple[FloatArray, FloatArray]:
    """Fit ``reference = M @ (measured - bias)`` from labelled known poses.

    The reference vectors must be independently known in sensor axes; six
    gravity-magnitude poses with full affine design rank are the minimum.
    """

    measured = _vectors(measured_mps2, "measured acceleration")
    reference = _vectors(reference_mps2, "reference acceleration")
    if measured.shape != reference.shape:
        raise ValueError("measured and reference pose shapes must match")
    if len(measured) < 6:
        raise ValueError("at least six labelled known poses are required")
    _reject_clipping(sample_flags, len(measured))
    if not bool(np.allclose(np.linalg.norm(reference, axis=1), STANDARD_GRAVITY_MPS2, rtol=0, atol=0.05)):
        raise ValueError("reference poses must have known gravity magnitude in sensor axes")
    if len(np.unique(np.round(reference, decimals=6), axis=0)) < 6:
        raise ValueError("at least six distinct known pose directions are required")
    design = np.column_stack((measured, np.ones(len(measured))))
    if np.linalg.matrix_rank(design) != 4:
        raise ValueError("known poses lack affine rank; pose directions are not identifiable")
    coefficients, _, _, _ = np.linalg.lstsq(design, reference, rcond=None)
    if float(np.max(np.linalg.norm(design @ coefficients - reference, axis=1))) > 0.05:
        raise ValueError("known-pose affine fit residual exceeds 0.05 m/s^2")
    matrix: FloatArray = np.asarray(coefficients[:3, :].T, dtype=np.float64)
    if abs(float(np.linalg.det(matrix))) < 1e-12 or np.linalg.cond(matrix) > 1e6:
        raise ValueError("estimated accelerometer matrix is singular or ill-conditioned")
    bias: FloatArray = np.asarray(-np.linalg.solve(matrix, coefficients[3, :]), dtype=np.float64)
    return matrix, bias


@dataclass(frozen=True, slots=True)
class StationarityCriteria:
    min_samples: int
    min_duration_s: float
    accel_norm_tolerance_mps2: float
    accel_axis_std_max_mps2: float
    gyro_norm_max_rads: float

    def __post_init__(self) -> None:
        if self.min_samples < 2 or any(
            not isfinite(value) or value <= 0
            for value in (self.min_duration_s, self.accel_norm_tolerance_mps2,
                          self.accel_axis_std_max_mps2, self.gyro_norm_max_rads)
        ):
            raise ValueError("stationarity criteria must contain positive thresholds and at least two samples")


def estimate_gyro_bias(
    accel_mps2: FloatArray,
    gyro_rads: FloatArray,
    device_time_us: NDArray[np.int64],
    *,
    criteria: StationarityCriteria,
    sample_flags: tuple[SampleFlags, ...] | None = None,
) -> FloatArray:
    """Return mean gyro only when observed acceleration and rate pass a stationary gate."""

    accel = _vectors(accel_mps2, "acceleration")
    gyro = _vectors(gyro_rads, "gyroscope")
    times = np.asarray(device_time_us, dtype=np.int64)
    if accel.shape != gyro.shape or times.shape != (len(accel),):
        raise ValueError("stationarity window arrays must have matching sample counts")
    _reject_clipping(sample_flags, len(accel))
    if len(accel) < criteria.min_samples or not bool((np.diff(times) > 0).all()):
        raise ValueError("stationary window requires enough strictly increasing samples")
    if (int(times[-1]) - int(times[0])) / 1e6 < criteria.min_duration_s - 1e-12:
        raise ValueError("stationary window duration is too short")
    if (
        bool((np.abs(np.linalg.norm(accel, axis=1) - STANDARD_GRAVITY_MPS2) > criteria.accel_norm_tolerance_mps2).any())
        or bool((np.std(accel, axis=0) > criteria.accel_axis_std_max_mps2).any())
        or bool((np.linalg.norm(gyro, axis=1) > criteria.gyro_norm_max_rads).any())
    ):
        raise ValueError("stationary window failed acceleration or angular-rate gate")
    bias: FloatArray = np.asarray(np.mean(gyro, axis=0), dtype=np.float64)
    return bias
