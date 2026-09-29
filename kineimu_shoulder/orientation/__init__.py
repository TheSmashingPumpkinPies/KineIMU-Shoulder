"""Per-epoch six-axis node orientation and fixed segment alignment.

The pinned imufusion backend receives g and deg/s. Project arrays remain SI;
all returned quaternions are active scalar-first q_WN. Each call creates a new
AHRS, so callers must split device-clock epochs and cannot carry state across
resets. Six-axis heading has no absolute reference.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import imufusion
import numpy as np
from numpy.typing import NDArray

from kineimu_shoulder.frames import compose_quaternions, inverse_quaternion

FloatArray = NDArray[np.float64]

STANDARD_GRAVITY_MPS2 = 9.80665


@dataclass(frozen=True)
class OrientationResult:
    """One epoch's q_WN samples, with an explicit unobservable heading flag."""

    timestamp_us: NDArray[np.int64]
    quaternion_wn: FloatArray
    heading_observable: bool = False


def estimate_orientation(
    timestamp_us: NDArray[np.int64],
    acceleration_mps2: FloatArray,
    angular_rate_rads: FloatArray,
    *,
    max_gap_s: float,
    initial_quaternion_wn: Sequence[float] = (1.0, 0.0, 0.0, 0.0),
) -> OrientationResult:
    """Estimate q_WN for one strictly increasing node-clock epoch.

    The first sample uses the declared initial orientation without an invented
    sample period. For each later sample, observed device time supplies dt.
    A gap above max_gap_s is rejected; callers may start a new epoch instead.
    Startup gain is skipped to avoid silently suppressing initial gyro motion.
    Absolute yaw remains arbitrary and can drift without a heading reference.
    """
    times = np.asarray(timestamp_us)
    acceleration = np.asarray(acceleration_mps2, dtype=np.float64)
    angular_rate = np.asarray(angular_rate_rads, dtype=np.float64)
    if times.ndim != 1 or len(times) == 0 or times.dtype != np.int64:
        raise ValueError("timestamp_us must be a nonempty int64 vector")
    if acceleration.shape != (len(times), 3) or angular_rate.shape != (len(times), 3):
        raise ValueError("acceleration and angular rate must have shape (N, 3)")
    if not bool(np.isfinite(acceleration).all() and np.isfinite(angular_rate).all()):
        raise ValueError("acceleration and angular rate must be finite")
    if bool((np.linalg.norm(acceleration, axis=1) == 0).any()):
        raise ValueError("acceleration magnitude must be nonzero for six-axis orientation")
    if not np.isfinite(max_gap_s) or max_gap_s <= 0:
        raise ValueError("max_gap_s must be finite and positive")
    if bool((times[1:] <= times[:-1]).any()):
        raise ValueError("timestamp_us must increase strictly within an epoch")
    delta_us = np.diff(times)
    if bool((delta_us <= 0).any()):
        raise ValueError("timestamp_us interval exceeds supported int64 range")
    if bool((delta_us.astype(np.float64) / 1e6 > max_gap_s).any()):
        raise ValueError("observed timestamp gap exceeds max_gap_s")

    initial = np.asarray(initial_quaternion_wn, dtype=np.float64)
    if initial.shape != (4,) or not bool(np.isfinite(initial).all()):
        raise ValueError("initial quaternion must have four finite components")
    if not bool(np.isclose(np.linalg.norm(initial), 1.0, atol=1e-12, rtol=0)):
        raise ValueError("initial quaternion must have unit norm")

    output = np.empty((len(times), 4), dtype=np.float64)
    output[0] = initial
    ahrs = imufusion.Ahrs()
    ahrs.set_quaternion(initial)
    ahrs.skip_startup()
    for index, interval_us in enumerate(delta_us, start=1):
        ahrs.set_sample_period(float(interval_us) / 1e6)
        gyro_dps = np.rad2deg(angular_rate[index])
        accel_g = acceleration[index] / STANDARD_GRAVITY_MPS2
        ahrs.update_no_magnetometer(gyro_dps, accel_g)
        quaternion = np.asarray(ahrs.get_quaternion(), dtype=np.float64)
        norm = float(np.linalg.norm(quaternion))
        if quaternion.shape != (4,) or not np.isfinite(norm) or abs(norm - 1.0) > 1e-5:
            raise ValueError(f"imufusion returned invalid orientation at sample {index}")
        output[index] = quaternion / norm
    return OrientationResult(times.copy(), output)


def align_segment(q_wn: Sequence[float], q_nsegment: Sequence[float]) -> FloatArray:
    """Return q_WSegment = q_WN ⊗ q_NSegment, once after node-frame AHRS.

    q_NSegment maps segment coordinates to node coordinates. A separately
    measured sensor-to-segment rotation must be inverted and composed with
    the declared q_NS before it can be supplied here.
    """
    return compose_quaternions(q_wn, q_nsegment)


def segment_to_node_alignment(
    q_ns: Sequence[float], q_segment_sensor: Sequence[float]
) -> FloatArray:
    """Convert an observed sensor-to-segment map to q_NSegment.

    q_NS is the declared sensor-to-node proper rotation. q_SegmentSensor
    maps sensor vectors into anatomical segment coordinates. Therefore
    q_NSegment = q_NS ⊗ inverse(q_SegmentSensor). This fixed alignment is
    applied after AHRS; calibrated node-frame samples are not rotated again.
    """
    return compose_quaternions(q_ns, inverse_quaternion(q_segment_sensor).tolist())
