"""M2 right-handed active frame rotations in scalar-first Hamilton order.

Numerical rotation operations delegate to SciPy Rotation. The wrappers keep
KineIMU's [w, x, y, z] order explicit and reject invalid inputs before SciPy
can silently normalize them.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation  # type: ignore[import-untyped]

FloatArray = NDArray[np.float64]


def _rotation(quaternion_wxyz: Sequence[float]) -> Rotation:
    values = np.asarray(quaternion_wxyz, dtype=np.float64)
    if values.shape != (4,) or not bool(np.isfinite(values).all()):
        raise ValueError("quaternion must have four finite [w, x, y, z] components")
    if not bool(np.isclose(np.linalg.norm(values), 1.0, rtol=0.0, atol=1e-12)):
        raise ValueError("quaternion must have unit norm")
    return Rotation.from_quat(values, scalar_first=True)


def compose_quaternions(q_ab: Sequence[float], q_bc: Sequence[float]) -> FloatArray:
    """Return q_AC = q_AB ⊗ q_BC; the rightmost active rotation acts first."""
    result: FloatArray = (_rotation(q_ab) * _rotation(q_bc)).as_quat(scalar_first=True)
    return result


def inverse_quaternion(q_ab: Sequence[float]) -> FloatArray:
    """Return q_BA, the inverse of q_AB."""
    result: FloatArray = _rotation(q_ab).inv().as_quat(scalar_first=True)
    return result


def rotate_vector(q_ab: Sequence[float], vector_b: Sequence[float]) -> FloatArray:
    """Express a vector from frame B in frame A using active q_AB."""
    vector = np.asarray(vector_b, dtype=np.float64)
    if vector.shape != (3,) or not bool(np.isfinite(vector).all()):
        raise ValueError("vector must have three finite components")
    result: FloatArray = _rotation(q_ab).apply(vector)
    return result
