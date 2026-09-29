"""API-level compatibility checks for pinned third-party dependencies.

These tests verify callable contracts only. They do not validate algorithmic or
biomechanical performance.
"""

import imufusion
import numpy as np
import pandas as pd
from imucal import FerrarisCalibrationInfo
from scipy.spatial.transform import Rotation


def test_scientific_stack_preserves_shapes_and_quaternion_convention() -> None:
    frame = pd.DataFrame({"x": [1.0, 0.0], "y": [0.0, 1.0], "z": [0.0, 0.0]})
    rotation = Rotation.from_quat([0.0, 0.0, 0.0, 1.0])

    rotated = rotation.apply(frame[["x", "y", "z"]].to_numpy())

    np.testing.assert_allclose(rotated, frame.to_numpy())
    assert rotated.shape == (2, 3)


def test_imufusion_stationary_update_returns_normalized_wxyz_quaternion() -> None:
    ahrs = imufusion.Ahrs()
    ahrs.set_sample_period(0.01)

    # imufusion's public API consumes gyroscope deg/s and acceleration g.
    ahrs.update_no_magnetometer(np.zeros(3), np.array([0.0, 0.0, 1.0]))
    quaternion_wxyz = np.asarray(ahrs.get_quaternion())

    assert quaternion_wxyz.shape == (4,)
    np.testing.assert_allclose(np.linalg.norm(quaternion_wxyz), 1.0)
    np.testing.assert_allclose(quaternion_wxyz, [1.0, 0.0, 0.0, 0.0])


def test_imucal_identity_calibration_accepts_core_si_units() -> None:
    identity = np.eye(3)
    zeros = np.zeros((2, 3))
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

    calibrated_acc, calibrated_gyr = calibration.calibrate(zeros, zeros, "m/s^2", "rad/s")
    restored = FerrarisCalibrationInfo.from_json(calibration.to_json())

    np.testing.assert_array_equal(calibrated_acc, zeros)
    np.testing.assert_array_equal(calibrated_gyr, zeros)
    assert restored == calibration
