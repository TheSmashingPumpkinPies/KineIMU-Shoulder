"""Analytical convention fixtures for the M2 active rotation contract."""

from math import sqrt

import numpy as np
import pytest

from kineimu_shoulder.frames import compose_quaternions, inverse_quaternion, rotate_vector

ROOT_HALF = sqrt(0.5)
Q_X90 = (ROOT_HALF, ROOT_HALF, 0.0, 0.0)
Q_Y90 = (ROOT_HALF, 0.0, ROOT_HALF, 0.0)
Q_Z90 = (ROOT_HALF, 0.0, 0.0, ROOT_HALF)


@pytest.mark.parametrize(
    ("quaternion", "source", "expected"),
    [
        (Q_X90, (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        (Q_Y90, (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
        (Q_Z90, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    ],
)
def test_positive_quarter_turn_follows_right_hand_rule(
    quaternion: tuple[float, ...], source: tuple[float, ...], expected: tuple[float, ...]
) -> None:
    # Analytical source: Rodrigues' right-hand rule on Cartesian unit axes.
    np.testing.assert_allclose(rotate_vector(quaternion, source), expected, rtol=0.0, atol=1e-12)


def test_composition_is_ordered_and_noncommutative() -> None:
    # Hamilton products derived directly: qx⊗qy=(1,1,1,1)/2,
    # qy⊗qx=(1,1,1,-1)/2. A rightmost active rotation acts first.
    xy = compose_quaternions(Q_X90, Q_Y90)
    yx = compose_quaternions(Q_Y90, Q_X90)
    np.testing.assert_allclose(xy, (0.5, 0.5, 0.5, 0.5), rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(yx, (0.5, 0.5, 0.5, -0.5), rtol=0.0, atol=1e-12)
    # Independent axis tracing: Ry maps +Z to +X; Rx leaves +X fixed.
    np.testing.assert_allclose(rotate_vector(xy, (0.0, 0.0, 1.0)), (1.0, 0.0, 0.0), rtol=0.0, atol=1e-12)
    # Rx maps +Z to -Y; Ry leaves -Y fixed.
    np.testing.assert_allclose(rotate_vector(yx, (0.0, 0.0, 1.0)), (0.0, -1.0, 0.0), rtol=0.0, atol=1e-12)


def test_inverse_maps_rotated_axis_back_to_source() -> None:
    # Analytical source: Rz(+90°) sends +X to +Y; its inverse sends +Y to +X.
    np.testing.assert_allclose(
        rotate_vector(inverse_quaternion(Q_Z90), (0.0, 1.0, 0.0)), (1.0, 0.0, 0.0), rtol=0.0, atol=1e-12
    )


@pytest.mark.parametrize(
    "quaternion",
    [(0.0, 0.0, 0.0, 0.0), (2.0, 0.0, 0.0, 0.0), (1.0, 0.0, float("nan"), 0.0)],
)
def test_invalid_quaternion_is_rejected(quaternion: tuple[float, ...]) -> None:
    with pytest.raises(ValueError, match="quaternion"):
        rotate_vector(quaternion, (1.0, 0.0, 0.0))
