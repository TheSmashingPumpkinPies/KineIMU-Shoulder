"""M2.2 known-input calibration and applicability gates."""

import json

import numpy as np
import pytest

from kineimu_shoulder.calibration import (
    CalibrationArtifact,
    StationarityCriteria,
    apply_calibration,
    estimate_accelerometer_affine,
    estimate_gyro_bias,
)
from kineimu_shoulder.io.m1_packet import NodeId, SampleFlags
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorToNodeTransform


def _config() -> M1RawCountAdapterConfig:
    return M1RawCountAdapterConfig(
        accel_range_g=4.0,
        gyro_range_dps=500.0,
        accel_sensitivity_mg_per_lsb=0.122,
        gyro_sensitivity_mdps_per_lsb=17.5,
        axis_transform=SensorToNodeTransform(
            sensor_axes=("sx", "sy", "sz"),
            node_axes=("nx", "ny", "nz"),
            sensor_to_node=((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
            description="known quarter turn",
        ),
    )


def _artifact() -> CalibrationArtifact:
    return CalibrationArtifact(
        calibration_id="synthetic-a-01",
        node_id=NodeId.A,
        sensor_id="sensor-a",
        config=_config(),
        accel_matrix=((2.0, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, 1.0)),
        accel_bias_mps2=(0.5, -0.25, 0.0),
        gyro_bias_rads=(0.1, -0.2, 0.0),
        fit_method="injected_synthetic_truth",
        fit_window_us=(100, 200),
        source_sha256=("a" * 64,),
        validity="synthetic known-parameter fixture; matching sensor and configuration only",
    )


def test_apply_calibration_before_sensor_to_node_rotation_and_round_trip() -> None:
    artifact = CalibrationArtifact.from_json(_artifact().to_json())
    accel, gyro = apply_calibration(
        np.array([[1.0, 1.75, 0.0]]),
        np.array([[0.1, 0.8, 0.0]]),
        artifact=artifact,
        node_id=NodeId.A,
        sensor_id="sensor-a",
        config=_config(),
        sample_flags=(SampleFlags.NONE,),
    )
    # Injected bias/scale gives sensor-frame [1, 1, 0] m/s², then +90° R_NS gives [-1, 1, 0].
    np.testing.assert_allclose(accel, [[-1.0, 1.0, 0.0]], rtol=0, atol=1e-12)
    # Injected gyro bias gives sensor-frame [0, 1, 0] rad/s, then R_NS gives [-1, 0, 0].
    np.testing.assert_allclose(gyro, [[-1.0, 0.0, 0.0]], rtol=0, atol=1e-12)
    assert artifact.to_json() == _artifact().to_json()


@pytest.mark.parametrize("change,match", [("node", "node"), ("sensor", "sensor"), ("range", "configuration")])
def test_apply_rejects_mismatched_applicability(change: str, match: str) -> None:
    kwargs = dict(node_id=NodeId.A, sensor_id="sensor-a", config=_config())
    if change == "node":
        kwargs["node_id"] = NodeId.B
    elif change == "sensor":
        kwargs["sensor_id"] = "sensor-b"
    else:
        kwargs["config"] = M1RawCountAdapterConfig(
            accel_range_g=8.0,
            gyro_range_dps=500.0,
            accel_sensitivity_mg_per_lsb=0.122,
            gyro_sensitivity_mdps_per_lsb=17.5,
            axis_transform=_config().axis_transform,
        )
    with pytest.raises(ValueError, match=match):
        apply_calibration(
            np.zeros((1, 3)), np.zeros((1, 3)), artifact=_artifact(), sample_flags=(SampleFlags.NONE,), **kwargs
        )


def test_apply_rejects_clipping_nonfinite_and_out_of_range() -> None:
    common = dict(artifact=_artifact(), node_id=NodeId.A, sensor_id="sensor-a", config=_config())
    with pytest.raises(ValueError, match="clipped"):
        apply_calibration(np.zeros((1, 3)), np.zeros((1, 3)), sample_flags=(SampleFlags.ACCEL_CLIPPED,), **common)
    with pytest.raises(ValueError, match="finite"):
        apply_calibration(np.array([[np.nan, 0, 0]]), np.zeros((1, 3)), sample_flags=(SampleFlags.NONE,), **common)
    with pytest.raises(ValueError, match="range"):
        apply_calibration(np.array([[50.0, 0, 0]]), np.zeros((1, 3)), sample_flags=(SampleFlags.NONE,), **common)


def test_known_pose_affine_fit_recovers_injected_bias_scale_and_axis_coupling() -> None:
    g = 9.80665
    reference = np.array([[g, 0, 0], [-g, 0, 0], [0, g, 0], [0, -g, 0], [0, 0, g], [0, 0, -g]])
    injected_matrix = np.array([[1.1, 0.02, 0], [0, 0.9, 0.03], [0, 0, 1.05]])
    injected_bias = np.array([0.2, -0.3, 0.1])
    measured = reference @ np.linalg.inv(injected_matrix).T + injected_bias
    matrix, bias = estimate_accelerometer_affine(measured, reference)
    # Analytical injection uses the inverse affine map; fitting must recover its known coefficients.
    np.testing.assert_allclose(matrix, injected_matrix, rtol=0, atol=1e-12)
    np.testing.assert_allclose(bias, injected_bias, rtol=0, atol=1e-12)


def test_known_pose_fit_rejects_insufficient_or_unidentifiable_poses() -> None:
    repeated = np.tile([0.0, 0.0, 9.80665], (6, 1))
    with pytest.raises(ValueError, match="rank|pose"):
        estimate_accelerometer_affine(repeated, repeated)
    with pytest.raises(ValueError, match="six"):
        estimate_accelerometer_affine(repeated[:5], repeated[:5])
    four_directions = np.array([[9.80665, 0, 0], [-9.80665, 0, 0], [0, 9.80665, 0],
                                [0, -9.80665, 0], [9.80665, 0, 0], [0, 9.80665, 0]])
    with pytest.raises(ValueError, match="distinct|pose"):
        estimate_accelerometer_affine(four_directions, four_directions)


def test_fit_rejects_inconsistent_known_pose_data_and_clipping() -> None:
    g = 9.80665
    reference = np.array([[g, 0, 0], [-g, 0, 0], [0, g, 0], [0, -g, 0], [0, 0, g], [0, 0, -g],
                          [g / np.sqrt(2), g / np.sqrt(2), 0]])
    measured = reference.copy()
    measured[-1] += [1.0, 0, 0]
    with pytest.raises(ValueError, match="residual"):
        estimate_accelerometer_affine(measured, reference)
    with pytest.raises(ValueError, match="clipped"):
        estimate_accelerometer_affine(reference[:6], reference[:6], sample_flags=(SampleFlags.ACCEL_CLIPPED,) +
                                      (SampleFlags.NONE,) * 5)


def test_json_rejects_changed_units() -> None:
    payload = json.loads(_artifact().to_json())
    payload["units"]["angular_velocity"] = "deg/s"
    with pytest.raises(ValueError, match="SI units"):
        CalibrationArtifact.from_json(json.dumps(payload))


def test_gyro_bias_requires_stationary_window() -> None:
    criteria = StationarityCriteria(min_samples=4, min_duration_s=0.03, accel_norm_tolerance_mps2=0.2,
                                    accel_axis_std_max_mps2=0.1, gyro_norm_max_rads=0.2)
    times = np.array([0, 10_000, 20_000, 30_000], dtype=np.int64)
    accel = np.tile([0.0, 0.0, 9.80665], (4, 1))
    gyro = np.tile([0.01, -0.02, 0.03], (4, 1))
    # Constant injected zero-rate offset is identifiable only under the declared stationary assumption.
    np.testing.assert_allclose(estimate_gyro_bias(accel, gyro, times, criteria=criteria), [0.01, -0.02, 0.03])
    with pytest.raises(ValueError, match="stationary"):
        estimate_gyro_bias(accel, gyro + [0.3, 0, 0], times, criteria=criteria)
    with pytest.raises(ValueError, match="stationary"):
        estimate_gyro_bias(accel + [[0, 0, 0], [1, 0, 0], [0, 0, 0], [0, 0, 0]], gyro, times, criteria=criteria)
    with pytest.raises(ValueError, match="duration"):
        estimate_gyro_bias(accel, gyro, times // 10, criteria=criteria)
