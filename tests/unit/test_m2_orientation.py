"""Analytical M2.3 orientation and alignment fixtures."""

from math import cos, pi, sin, sqrt

import numpy as np
import pytest

from kineimu_shoulder.frames import rotate_vector
from kineimu_shoulder.orientation import align_segment, estimate_orientation, segment_to_node_alignment

GRAVITY = 9.80665


def test_observed_variable_intervals_integrate_positive_yaw_in_sensor_to_world_direction() -> None:
    timestamps = np.array([0, 5_000, 20_000, 40_000, 60_000], dtype=np.int64)
    acceleration = np.tile([0.0, 0.0, GRAVITY], (5, 1))
    angular_rate = np.tile([0.0, 0.0, pi / 2], (5, 1))

    result = estimate_orientation(timestamps, acceleration, angular_rate, max_gap_s=0.03)

    # Analytical source: constant +Z angular velocity integrates to +90 deg/s * 0.06 s.
    expected_angle = pi / 2 * 0.06
    expected_q = (cos(expected_angle / 2), 0.0, 0.0, sin(expected_angle / 2))
    np.testing.assert_allclose(result.quaternion_wn[0], (1.0, 0.0, 0.0, 0.0), rtol=0, atol=0)
    np.testing.assert_allclose(result.quaternion_wn[-1], expected_q, rtol=0, atol=2e-5)
    np.testing.assert_allclose(
        rotate_vector(result.quaternion_wn[-1], (1.0, 0.0, 0.0)),
        (cos(expected_angle), sin(expected_angle), 0.0),
        rtol=0,
        atol=4e-5,
    )
    assert result.heading_observable is False


def test_stationary_tilt_maps_sensor_up_into_world_up() -> None:
    timestamps = np.arange(5001, dtype=np.int64) * 10_000
    acceleration = np.tile([0.0, GRAVITY, 0.0], (len(timestamps), 1))
    angular_rate = np.zeros_like(acceleration)

    result = estimate_orientation(timestamps, acceleration, angular_rate, max_gap_s=0.02)

    # Analytical source: a +90 deg active X rotation maps sensor +Y to world +Z.
    np.testing.assert_allclose(
        rotate_vector(result.quaternion_wn[-1], (0.0, 1.0, 0.0)),
        (0.0, 0.0, 1.0),
        rtol=0,
        atol=3e-5,
    )


@pytest.mark.parametrize("direction", [-1.0, 1.0])
def test_signed_quarter_turn_from_gyro(direction: float) -> None:
    times = np.arange(1001, dtype=np.int64) * 1_000
    acceleration = np.tile([0.0, 0.0, GRAVITY], (len(times), 1))
    angular_rate = np.tile([0.0, 0.0, direction * pi / 2], (len(times), 1))

    result = estimate_orientation(times, acceleration, angular_rate, max_gap_s=0.002)

    # Analytical source: integral of constant signed pi/2 rad/s over 1 s is signed pi/2.
    np.testing.assert_allclose(
        rotate_vector(result.quaternion_wn[-1], (1.0, 0.0, 0.0)),
        (0.0, direction, 0.0),
        rtol=0,
        atol=3e-5,
    )


def test_alignment_is_composed_once_after_orientation() -> None:
    root_half = sqrt(0.5)
    q_wn = (root_half, root_half, 0.0, 0.0)
    q_ns = (root_half, 0.0, root_half, 0.0)

    aligned = align_segment(q_wn, q_ns)

    # Analytical source: Ry(+90) maps +Z to +X, then Rx(+90) leaves +X fixed.
    np.testing.assert_allclose(rotate_vector(aligned, (0.0, 0.0, 1.0)), (1.0, 0.0, 0.0), rtol=0, atol=1e-12)


def test_sensor_to_segment_rotation_converts_to_segment_to_node_then_aligns_once() -> None:
    root_half = sqrt(0.5)
    q_ns = (root_half, root_half, 0.0, 0.0)
    q_segment_sensor = (root_half, 0.0, root_half, 0.0)
    q_wn = (root_half, 0.0, 0.0, root_half)

    q_nsegment = segment_to_node_alignment(q_ns, q_segment_sensor)
    aligned = align_segment(q_wn, q_nsegment)

    # Analytical axis trace: segment +Z -> sensor -X by inverse Ry(+90),
    # node -X by Rx(+90), then world -Y by Rz(+90).
    np.testing.assert_allclose(rotate_vector(aligned, (0.0, 0.0, 1.0)), (0.0, -1.0, 0.0), rtol=0, atol=1e-12)


@pytest.mark.parametrize("timestamps", [[0, 0], [10, 0], [0, 30_001]])
def test_duplicate_reordered_or_long_gap_is_rejected(timestamps: list[int]) -> None:
    with pytest.raises(ValueError, match="timestamp|gap"):
        estimate_orientation(
            np.array(timestamps, dtype=np.int64),
            np.tile([0.0, 0.0, GRAVITY], (2, 1)),
            np.zeros((2, 3)),
            max_gap_s=0.03,
        )


def test_each_epoch_starts_with_fresh_initial_orientation() -> None:
    times = np.array([0, 10_000], dtype=np.int64)
    acceleration = np.tile([0.0, 0.0, GRAVITY], (2, 1))
    angular_rate = np.tile([0.0, 0.0, pi / 2], (2, 1))

    first = estimate_orientation(times, acceleration, angular_rate, max_gap_s=0.02)
    second = estimate_orientation(times, acceleration, angular_rate, max_gap_s=0.02)

    np.testing.assert_array_equal(first.quaternion_wn, second.quaternion_wn)
    np.testing.assert_array_equal(second.quaternion_wn[0], (1.0, 0.0, 0.0, 0.0))


def test_declared_initial_orientation_is_preserved_and_applied() -> None:
    root_half = sqrt(0.5)
    q_initial = (root_half, 0.0, 0.0, root_half)
    result = estimate_orientation(
        np.array([0, 10_000], dtype=np.int64),
        np.tile([0.0, 0.0, GRAVITY], (2, 1)),
        np.zeros((2, 3)),
        max_gap_s=0.02,
        initial_quaternion_wn=q_initial,
    )

    # Analytical source: zero angular rate and gravity parallel to +Z preserve a +Z quarter-turn.
    np.testing.assert_allclose(result.quaternion_wn, np.tile(q_initial, (2, 1)), rtol=0, atol=2e-7)


def test_unobserved_yaw_bias_accumulates_on_stationary_synthetic_case() -> None:
    times = np.arange(1001, dtype=np.int64) * 10_000
    acceleration = np.tile([0.0, 0.0, GRAVITY], (len(times), 1))
    angular_rate = np.tile([0.0, 0.0, pi / 180], (len(times), 1))

    result = estimate_orientation(times, acceleration, angular_rate, max_gap_s=0.02)

    # Analytical source: a constant +1 deg/s gyro bias integrates to +10 deg
    # over 10 s; vertical gravity cannot observe or correct yaw.
    expected = (cos(pi / 18), sin(pi / 18), 0.0)
    np.testing.assert_allclose(
        rotate_vector(result.quaternion_wn[-1], (1.0, 0.0, 0.0)), expected, rtol=0, atol=3e-5
    )
    assert result.heading_observable is False


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf")])
def test_nonfinite_samples_are_rejected(bad_value: float) -> None:
    acceleration = np.array([[0.0, 0.0, GRAVITY], [bad_value, 0.0, GRAVITY]])
    with pytest.raises(ValueError, match="finite"):
        estimate_orientation(np.array([0, 10_000]), acceleration, np.zeros((2, 3)), max_gap_s=0.02)
