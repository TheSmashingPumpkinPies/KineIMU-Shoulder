"""Validation-only recorded quality partition; ADR-011, no raw repair."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from kineimu_shoulder.calibration import CalibrationArtifact, apply_calibration
from kineimu_shoulder.io.m1_packet import SampleFlags
from kineimu_shoulder.orientation import estimate_orientation
from kineimu_shoulder.validation.baseline import plain

CONTRACT = "m5-recorded-segments/1.0"


def process_segments(
    timestamp_us: NDArray[np.int64],
    acceleration_mps2: NDArray[np.float64],
    angular_rate_rads: NDArray[np.float64],
    sample_flags: tuple[SampleFlags, ...],
    *,
    artifact: CalibrationArtifact,
) -> dict[str, Any]:
    """Partition only clipping/range failures, retaining full original support.

    Each eligible contiguous interval passes the unchanged calibration gate
    with its original flags, then a new AHRS. Output rows outside these intervals
    are unavailable. All other malformed input/backend failures propagate.
    """
    times = np.asarray(timestamp_us)
    acc = np.asarray(acceleration_mps2, dtype=np.float64)
    rate = np.asarray(angular_rate_rads, dtype=np.float64)
    n = len(times)
    if times.ndim != 1 or times.dtype != np.int64 or not n:
        raise ValueError("original timestamps must be a nonempty int64 vector")
    if acc.shape != (n, 3) or rate.shape != (n, 3) or len(sample_flags) != n:
        raise ValueError("original vectors and flags must match timestamp support")
    if not np.isfinite(acc).all() or not np.isfinite(rate).all():
        raise ValueError("original sensor vectors must be finite")
    if (np.diff(times) <= 0).any() or (times[1:] <= times[:-1]).any():
        raise ValueError("original timestamps must increase strictly")
    flags = np.asarray(sample_flags, dtype=np.int64)
    # Exact predicates from apply_calibration, including its existing 1.001 factor.
    predicates = (
        ("accel_clipped", (flags & int(SampleFlags.ACCEL_CLIPPED)) != 0),
        ("gyro_clipped", (flags & int(SampleFlags.GYRO_CLIPPED)) != 0),
        ("accel_range_exceeded", (np.abs(acc) > artifact.config.accel_range_g*9.80665*1.001).any(axis=1)),
        ("gyro_range_exceeded", (np.abs(rate) > np.deg2rad(artifact.config.gyro_range_dps)*1.001).any(axis=1)),
    )
    reasons = [[name for name, mask in predicates if mask[i]] for i in range(n)]
    valid = np.asarray([not row for row in reasons], dtype=np.bool_)
    node_acc = np.full((n, 3), np.nan)
    node_rate = np.full((n, 3), np.nan)
    quaternions = np.full((n, 4), np.nan)
    segment_index: list[int | None] = [None]*n
    segments: list[dict[str, Any]] = []
    edges = np.diff(np.r_[False, valid, False].astype(np.int8))
    for start, stop in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True):
        begin, end = int(start), int(stop)
        a, w = apply_calibration(acc[begin:end], rate[begin:end], artifact=artifact,
            node_id=artifact.node_id, sensor_id=artifact.sensor_id, config=artifact.config,
            sample_flags=sample_flags[begin:end])
        orientation = estimate_orientation(times[begin:end], a, w, max_gap_s=.05)
        q = orientation.quaternion_wn
        if (not np.array_equal(orientation.timestamp_us, times[begin:end])
            or q.shape != (end-begin, 4) or not np.isfinite(q).all()
            or not np.allclose(np.linalg.norm(q, axis=1), 1., rtol=0, atol=1e-12)
            or orientation.heading_observable):
            raise ValueError("segment orientation/support/unobserved-heading gate failed")
        index = len(segments)
        node_acc[begin:end], node_rate[begin:end], quaternions[begin:end] = a, w, q
        segment_index[begin:end] = [index]*(end-begin)
        segments.append(dict(segment_index=index, start_index=begin, stop_index=end,
            first_device_time_us=int(times[begin]), last_device_time_us=int(times[end-1]),
            world_id=f"M1-{artifact.node_id.name}-{artifact.source_sha256[0]}-processing-world-{index}",
            reset_reason="initial" if begin == 0 else "after_rejected_observation",
            initial_quaternion_wn=[1., 0., 0., 0.], initial_integration_dt_s=None))
    return cast(dict[str, Any], plain(dict(node_acceleration_mps2=node_acc, node_angular_rate_rads=node_rate,
        orientation=dict(timestamp_us=times, quaternion_wn=quaternions, heading_observable=False,
                         valid=valid),
        processing=dict(contract=CONTRACT, original_sample_count=n, eligible_sample_count=int(valid.sum()),
            rejected_sample_count=int((~valid).sum()), unavailable_reasons=reasons,
            segment_index=segment_index, segments=segments,
            interpolation="NONE", reconstruction="NONE", cross_segment_orientation_comparable=False))))
