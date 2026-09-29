"""M2.4 explicit clock mapping, resampling, and thorax-relative orientation.

This processed operation is outside the calibration and AHRS adapters. Inputs
are already aligned segment orientations in each node's own world frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation, Slerp  # type: ignore[import-untyped]

from kineimu_shoulder.frames import compose_quaternions, inverse_quaternion

FloatArray = NDArray[np.float64]
EvidenceStatus = Literal["supported", "assumed"]


@dataclass(frozen=True)
class SegmentOrientationStream:
    """One node-clock epoch of post-alignment q_WT or q_WH samples."""

    node_id: str
    clock_id: str
    epoch: int
    world_id: str
    source_sha256: str
    timestamp_us: NDArray[np.int64]
    quaternion_wsegment: FloatArray


@dataclass(frozen=True)
class ClockMap:
    """Evidence for t_common_us = slope * t_device_us + intercept_us."""

    node_id: str
    clock_id: str
    epoch: int
    slope: float
    intercept_us: float
    fit_device_start_us: int
    fit_device_end_us: int
    valid_device_start_us: int
    valid_device_end_us: int
    uncertainty_us: float
    heldout_residual_us: float | None
    method: str
    source_sha256: str
    status: EvidenceStatus


@dataclass(frozen=True)
class HeadingRelation:
    """Explicit q_WaWb mapping humerus world B into thorax world A."""

    thorax_world_id: str
    humerus_world_id: str
    quaternion_thorax_world_humerus_world: tuple[float, float, float, float]
    method: str
    source_sha256: str
    status: EvidenceStatus


@dataclass(frozen=True)
class RelativeOrientationResult:
    """Processed q_TH; invalid rows carry NaNs and an exact validity reason."""

    common_time_us: NDArray[np.int64]
    quaternion_th: FloatArray
    valid: NDArray[np.bool_]
    reason: tuple[str, ...]
    evidence_label: Literal["Derived", "Assumed/Experimental", "Invalid"]
    interpolation: Literal["slerp"]
    max_interpolation_gap_us: int
    max_timing_uncertainty_us: float
    thorax_source_sha256: str
    humerus_source_sha256: str
    thorax_clock_map: ClockMap | None
    humerus_clock_map: ClockMap | None
    heading_relation: HeadingRelation | None


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)


def _check_stream(stream: SegmentOrientationStream) -> None:
    times = stream.timestamp_us
    quaternions = stream.quaternion_wsegment
    if not stream.node_id or not stream.clock_id or not stream.world_id or not _valid_sha256(stream.source_sha256):
        raise ValueError("segment stream needs node, clock, world and source SHA-256 identity")
    if times.ndim != 1 or times.dtype != np.int64 or len(times) == 0:
        raise ValueError("segment timestamp_us must be a nonempty int64 vector")
    if bool((times[1:] <= times[:-1]).any()) or bool((np.diff(times) <= 0).any()):
        raise ValueError("segment timestamps must increase strictly without int64 overflow")
    if quaternions.shape != (len(times), 4) or not bool(np.isfinite(quaternions).all()):
        raise ValueError("segment quaternions must be finite (N, 4)")
    if not bool(np.allclose(np.linalg.norm(quaternions, axis=1), 1.0, rtol=0.0, atol=1e-12)):
        raise ValueError("segment quaternions must have unit norm")


def _check_map(clock_map: ClockMap, stream: SegmentOrientationStream) -> bool:
    if (clock_map.node_id, clock_map.clock_id, clock_map.epoch) != (stream.node_id, stream.clock_id, stream.epoch):
        return False
    if (
        clock_map.status not in ("supported", "assumed")
        or not clock_map.method
        or not _valid_sha256(clock_map.source_sha256)
    ):
        return False
    if not np.isfinite(clock_map.slope) or clock_map.slope <= 0 or not np.isfinite(clock_map.intercept_us):
        return False
    if (
        clock_map.fit_device_start_us > clock_map.fit_device_end_us
        or clock_map.valid_device_start_us > clock_map.valid_device_end_us
    ):
        return False
    if not np.isfinite(clock_map.uncertainty_us) or clock_map.uncertainty_us < 0:
        return False
    if clock_map.status == "supported" and clock_map.heldout_residual_us is None:
        return False
    if clock_map.heldout_residual_us is not None and (
        not np.isfinite(clock_map.heldout_residual_us) or clock_map.heldout_residual_us < 0
    ):
        return False
    return True


def _check_heading(
    relation: HeadingRelation, thorax: SegmentOrientationStream, humerus: SegmentOrientationStream
) -> bool:
    if (relation.thorax_world_id, relation.humerus_world_id) != (thorax.world_id, humerus.world_id):
        return False
    if (
        relation.status not in ("supported", "assumed")
        or not relation.method
        or not _valid_sha256(relation.source_sha256)
    ):
        return False
    quaternion = np.asarray(relation.quaternion_thorax_world_humerus_world, dtype=np.float64)
    return quaternion.shape == (4,) and bool(np.isfinite(quaternion).all()) and bool(
        np.isclose(np.linalg.norm(quaternion), 1.0, rtol=0, atol=1e-12)
    )


def _round_clock_times(mapped: FloatArray, clock_map: ClockMap) -> FloatArray:
    """Remove only floating arithmetic roundoff at integer microseconds.

    This bound is machine precision, independent of timing uncertainty. Actual
    quantization residuals remain fractional and cannot authorize extrapolation.
    """
    nearest = np.rint(mapped)
    scale = np.maximum(np.abs(mapped), max(abs(clock_map.intercept_us), 1.0))
    roundoff = 4 * np.finfo(np.float64).eps * scale
    return np.where(np.abs(mapped - nearest) <= roundoff, nearest, mapped)


def _sample_at(
    mapped: FloatArray,
    quaternions: FloatArray,
    clock_map: ClockMap,
    common_time_us: int,
    max_gap_us: int,
) -> tuple[FloatArray | None, str]:
    mapped_valid_start, mapped_valid_end = _round_clock_times(
        clock_map.slope * np.array([clock_map.valid_device_start_us, clock_map.valid_device_end_us], dtype=float)
        + clock_map.intercept_us, clock_map,
    )
    if not mapped_valid_start <= common_time_us <= mapped_valid_end:
        return None, "outside_clock_validity"
    if len(mapped) == 0:
        return None, "outside_stream"
    start, end = _round_clock_times(mapped[[0, -1]], clock_map)
    if common_time_us < start or common_time_us > end:
        return None, "outside_stream"
    if common_time_us == start:
        return quaternions[0].copy(), "valid"
    if common_time_us == end:
        return quaternions[-1].copy(), "valid"
    position = int(np.searchsorted(mapped, common_time_us, side="left"))
    if position < len(mapped) and mapped[position] == common_time_us:
        return quaternions[position].copy(), "valid"
    left, right = position - 1, position
    if mapped[right] - mapped[left] > max_gap_us:
        return None, "interpolation_gap"
    rotation = Rotation.from_quat(quaternions[[left, right]], scalar_first=True)
    interpolated: FloatArray = Slerp(mapped[[left, right]], rotation)([float(common_time_us)]).as_quat(
        scalar_first=True
    )[0]
    return interpolated, "valid"


def _mapped_samples(stream: SegmentOrientationStream, clock_map: ClockMap) -> tuple[FloatArray, FloatArray] | None:
    device_times = stream.timestamp_us
    within = (device_times >= clock_map.valid_device_start_us) & (device_times <= clock_map.valid_device_end_us)
    mapped = _round_clock_times(
        clock_map.slope * device_times[within].astype(np.float64) + clock_map.intercept_us, clock_map
    )
    if not bool(np.isfinite(mapped).all()) or bool((mapped[1:] <= mapped[:-1]).any()):
        return None
    return mapped, stream.quaternion_wsegment[within]


def relative_orientation(
    thorax: SegmentOrientationStream,
    humerus: SegmentOrientationStream,
    *,
    common_time_us: NDArray[np.int64],
    thorax_clock_map: ClockMap | None,
    humerus_clock_map: ClockMap | None,
    heading_relation: HeadingRelation | None,
    max_interpolation_gap_us: int,
    max_timing_uncertainty_us: float,
    evidence_source_sha256: tuple[str, str, str] | None = None,
) -> RelativeOrientationResult:
    """Return q_TH = inverse(q_WaT) ⊗ q_WaWb ⊗ q_WbH on a declared grid.

    No clock map is inferred. Every valid row has both orientations sampled at
    its common time with a declared slerp gap limit. Assumptions remain labeled.
    """
    if evidence_source_sha256 is not None and (
        len(evidence_source_sha256) != 3 or not all(_valid_sha256(h) for h in evidence_source_sha256)
    ):
        raise ValueError("evidence source hashes must identify A map, B map and heading reference")
    _check_stream(thorax)
    _check_stream(humerus)
    grid = np.asarray(common_time_us)
    if grid.ndim != 1 or grid.dtype != np.int64 or len(grid) == 0 or bool((grid[1:] <= grid[:-1]).any()):
        raise ValueError("common_time_us must be a nonempty strictly increasing int64 vector")
    if (
        isinstance(max_interpolation_gap_us, bool)
        or not isinstance(max_interpolation_gap_us, int)
        or max_interpolation_gap_us <= 0
    ):
        raise ValueError("max_interpolation_gap_us must be a positive integer")
    if not np.isfinite(max_timing_uncertainty_us) or max_timing_uncertainty_us < 0:
        raise ValueError("max_timing_uncertainty_us must be finite and nonnegative")
    output = np.full((len(grid), 4), np.nan, dtype=np.float64)
    valid = np.zeros(len(grid), dtype=np.bool_)
    reasons: list[str] = []
    global_reason: str | None = None
    if thorax_clock_map is None or humerus_clock_map is None:
        global_reason = "clock_map_missing"
    elif not _check_map(thorax_clock_map, thorax) or not _check_map(humerus_clock_map, humerus):
        global_reason = "clock_map_incompatible"
    elif evidence_source_sha256 is not None and (
        thorax_clock_map.source_sha256 != evidence_source_sha256[0]
        or humerus_clock_map.source_sha256 != evidence_source_sha256[1]
    ):
        global_reason = "clock_map_incompatible"
    elif heading_relation is None:
        global_reason = "heading_missing"
    elif not _check_heading(heading_relation, thorax, humerus):
        global_reason = "heading_incompatible"
    elif evidence_source_sha256 is not None and heading_relation.source_sha256 != evidence_source_sha256[2]:
        global_reason = "heading_incompatible"
    elif thorax_clock_map.uncertainty_us + humerus_clock_map.uncertainty_us > max_timing_uncertainty_us:
        global_reason = "clock_uncertainty"
    if global_reason is None:
        assert thorax_clock_map is not None and humerus_clock_map is not None
        thorax_samples = _mapped_samples(thorax, thorax_clock_map)
        humerus_samples = _mapped_samples(humerus, humerus_clock_map)
        if thorax_samples is None or humerus_samples is None:
            global_reason = "clock_map_incompatible"
    if global_reason is not None:
        reasons = [global_reason] * len(grid)
    else:
        assert thorax_clock_map is not None and humerus_clock_map is not None and heading_relation is not None
        assert thorax_samples is not None and humerus_samples is not None
        for index, common_time in enumerate(grid):
            q_wat, thorax_reason = _sample_at(
                *thorax_samples, thorax_clock_map, int(common_time), max_interpolation_gap_us
            )
            q_wbh, humerus_reason = _sample_at(
                *humerus_samples, humerus_clock_map, int(common_time), max_interpolation_gap_us
            )
            if q_wat is None or q_wbh is None:
                reasons.append(thorax_reason if q_wat is None else humerus_reason)
                continue
            q_wah = compose_quaternions(heading_relation.quaternion_thorax_world_humerus_world, q_wbh.tolist())
            output[index] = compose_quaternions(inverse_quaternion(q_wat.tolist()).tolist(), q_wah.tolist())
            valid[index] = True
            reasons.append("valid")
    label: Literal["Derived", "Assumed/Experimental", "Invalid"] = "Invalid"
    if bool(valid.any()):
        if (thorax_clock_map is not None and humerus_clock_map is not None and heading_relation is not None
                and "assumed" in (thorax_clock_map.status, humerus_clock_map.status, heading_relation.status)):
            label = "Assumed/Experimental"
        else:
            label = "Derived"
    return RelativeOrientationResult(
        common_time_us=grid.copy(), quaternion_th=output, valid=valid, reason=tuple(reasons),
        evidence_label=label, interpolation="slerp", max_interpolation_gap_us=max_interpolation_gap_us,
        max_timing_uncertainty_us=max_timing_uncertainty_us,
        thorax_source_sha256=thorax.source_sha256, humerus_source_sha256=humerus.source_sha256,
        thorax_clock_map=thorax_clock_map, humerus_clock_map=humerus_clock_map, heading_relation=heading_relation,
    )
