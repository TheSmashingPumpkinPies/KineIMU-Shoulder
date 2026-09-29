"""Explicit processed reconstruction of an observable rate transition in a short gap.

This offline stage uses adjacent calibrated observations, never motion labels or
truth. It assumes one collinear, piecewise-constant body-rate transition, and
gravity-dominated acceleration. Unobservable or incompatible gaps stay unchanged.
The AHRS adapter itself does not resample or change its pinned configuration.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation  # type: ignore[import-untyped]

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class ReconstructedSamples:
    timestamp_us: NDArray[np.int64]
    acceleration_mps2: FloatArray
    angular_rate_rads: FloatArray
    observed_indices: NDArray[np.int64]
    knots: tuple[tuple[int, int, int, float], ...]
    method: str = "gravity-supported single collinear rate transition/1.0"
    assumptions: tuple[str, ...] = (
        "gravity-dominated specific force; no independently measured linear acceleration",
        "one collinear piecewise-constant rate transition inside a short missing-sample bracket",
        "inferred time is a processed estimate, not a recovered raw timestamp",
    )


def reconstruct_short_gaps(
    timestamp_us: NDArray[np.int64], acceleration_mps2: FloatArray, angular_rate_rads: FloatArray,
    *, max_gap_s: float,
) -> ReconstructedSamples:
    """Insert supported transition samples while retaining every original row.

    A gap is >1.5 times the median observed interval and <= the declared limit.
    Both neighboring rates must confirm their respective constant branches.
    Gravity supplies the observable angular displacement, not absolute heading.
    Only a physically interior transition with consistent endpoint force is used.
    Invalid input/long gaps are returned untouched for the AHRS rejection gate.
    """
    times = np.asarray(timestamp_us)
    acceleration = np.asarray(acceleration_mps2, dtype=np.float64)
    rate = np.asarray(angular_rate_rads, dtype=np.float64)
    original = ReconstructedSamples(times.copy(), acceleration.copy(), rate.copy(),
                                    np.arange(len(times), dtype=np.int64), ())
    if (times.ndim != 1 or times.dtype != np.int64 or len(times) < 4
            or acceleration.shape != (len(times), 3) or rate.shape != (len(times), 3)
            or not np.isfinite(acceleration).all() or not np.isfinite(rate).all()):
        return original
    intervals = np.diff(times)
    if (not np.isfinite(max_gap_s) or max_gap_s <= 0 or (intervals <= 0).any()
            or (intervals / 1e6 > max_gap_s).any()):
        return original
    nominal = float(np.median(intervals))
    candidates = np.flatnonzero(intervals > 1.5 * nominal) + 1
    knots: dict[int, tuple[int, FloatArray, FloatArray, float]] = {}
    for candidate in candidates:
        i = int(candidate)
        if i < 2 or i + 1 >= len(times):
            continue
        before, after = rate[i - 1], rate[i]
        change = before - after
        change_norm = float(np.linalg.norm(change))
        if change_norm < 0.1:
            continue
        axis = change / change_norm
        if (np.linalg.norm(np.cross(before, after)) > 1e-4
                or np.linalg.norm(before - rate[i - 2]) > 0.001
                or np.linalg.norm(after - rate[i + 1]) > 0.001):
            continue
        norms = np.linalg.norm(acceleration[[i - 1, i]], axis=1)
        if (np.abs(norms - 9.80665) > 0.05).any():
            continue
        g0, g1 = acceleration[[i - 1, i]] / norms[:, None]
        p0, p1 = g0 - axis * np.dot(axis, g0), g1 - axis * np.dot(axis, g1)
        if min(np.linalg.norm(p0), np.linalg.norm(p1)) < 0.1:
            continue  # rotation about gravity cannot locate a yaw transition
        displacement = float(np.arctan2(np.dot(axis, np.cross(p1, p0)), np.dot(p1, p0)))
        dt = float(intervals[i - 1]) / 1e6
        if max(np.linalg.norm(before), np.linalg.norm(after)) * dt >= np.pi:
            continue
        early = (displacement - float(np.dot(axis, after)) * dt) / change_norm
        knot_time = int(np.rint(int(times[i - 1]) + early * 1e6))
        if not int(times[i - 1]) < knot_time < int(times[i]):
            continue
        early = (knot_time - int(times[i - 1])) / 1e6
        at_knot = Rotation.from_rotvec(-before * early).apply(g0)
        predicted = Rotation.from_rotvec(-after * (dt - early)).apply(at_knot)
        residual = float(np.linalg.norm(predicted - g1))
        if residual > 0.001:
            continue
        knots[int(i)] = (knot_time, at_knot * norms[0], before.copy(), residual)
    if not knots:
        return original
    output_times, output_acc, output_rate, indices, records = [], [], [], [], []
    for i, t in enumerate(times):
        if i in knots:
            kt, ka, kr, residual = knots[i]
            output_times.append(kt)
            output_acc.append(ka)
            output_rate.append(kr)
            records.append((i - 1, i, kt, residual))
        indices.append(len(output_times))
        output_times.append(int(t))
        output_acc.append(acceleration[i])
        output_rate.append(rate[i])
    return ReconstructedSamples(np.asarray(output_times, dtype=np.int64), np.asarray(output_acc),
                                np.asarray(output_rate), np.asarray(indices, dtype=np.int64), tuple(records))
