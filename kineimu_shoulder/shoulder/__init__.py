"""Evidence-gated humerothoracic kinematics (M3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from kineimu_shoulder.frames import compose_quaternions, inverse_quaternion, rotate_vector
from kineimu_shoulder.relative_orientation import RelativeOrientationResult

FloatArray = NDArray[np.float64]
Side = Literal["left", "right"]
EvidenceStatus = Literal["supported", "assumed"]


@dataclass(frozen=True)
class AlignmentRecord:
    """Fixed q_NSegment and its source, mounting, and anatomical evidence."""

    node_id: str
    epoch: int
    segment: Literal["T", "H"]
    side: Side
    quaternion_nsegment: tuple[float, float, float, float]
    alignment_id: str
    method: str
    source_sha256: str
    neutral_pose: str
    validity: str
    mounting_validity_statement: str
    remounted: bool
    uncertainty: str
    status: EvidenceStatus
    axes_basis: Literal["measured", "synthetic_ground_truth", "assumed"]


@dataclass(frozen=True)
class ElevationResult:
    """CP1 row result in radians, with original M2 and alignment evidence."""

    common_time_us: NDArray[np.int64]
    elevation_rad: FloatArray
    valid: NDArray[np.bool_]
    reason: tuple[str, ...]
    evidence_label: Literal["Derived", "Assumed/Experimental", "Invalid"]
    anatomical_eligible: bool
    side: Side
    source_type: str
    max_sample_gap_us: int
    thorax_source_sha256: str
    humerus_source_sha256: str
    relative_orientation: RelativeOrientationResult
    thorax_alignment: AlignmentRecord | None
    humerus_alignment: AlignmentRecord | None
    definition_version: Literal["m3-long-axis-elevation/1.0"] = "m3-long-axis-elevation/1.0"


@dataclass(frozen=True)
class AngularSpeedResult:
    """CP2 principal relative rotation magnitude averaged over each grid interval."""

    start_time_us: NDArray[np.int64]
    end_time_us: NDArray[np.int64]
    relative_angular_speed_rads: FloatArray
    valid: NDArray[np.bool_]
    reason: tuple[str, ...]
    evidence_label: Literal["Derived", "Assumed/Experimental", "Invalid"]
    anatomical_eligible: bool
    side: Side
    source_type: str
    max_sample_gap_us: int
    thorax_source_sha256: str
    humerus_source_sha256: str
    elevation_result: ElevationResult
    quantity_description: Literal[
        "principal endpoint rotation magnitude averaged over interval"
    ] = "principal endpoint rotation magnitude averaged over interval"
    definition_version: Literal["m3-relative-angular-speed/1.0"] = "m3-relative-angular-speed/1.0"


@dataclass(frozen=True)
class IntervalRomDurationResult:
    """CP3 all-or-nothing ROM and elapsed time for exact closed grid bounds."""

    start_time_us: int
    end_time_us: int
    rom_rad: float
    elapsed_duration_s: float
    valid: bool
    reason: str
    first_invalid_row_index: int | None
    invalid_row_reasons: tuple[tuple[int, str], ...]
    evidence_label: Literal["Derived", "Assumed/Experimental", "Invalid"]
    anatomical_eligible: bool
    side: Side
    source_type: str
    max_sample_gap_us: int
    thorax_source_sha256: str
    humerus_source_sha256: str
    elevation_result: ElevationResult
    definition_version: Literal["m3-interval-rom-duration/1.0"] = "m3-interval-rom-duration/1.0"


def _alignment_reason(
    record: AlignmentRecord | None, *, segment: Literal["T", "H"],
    source_sha256: str, side: Side, node_id: str, epoch: int,
) -> str | None:
    if record is None:
        return "alignment_missing"
    if record.remounted or record.validity != "current":
        return "alignment_expired"
    quaternion = np.asarray(record.quaternion_nsegment, dtype=np.float64)
    if (
        record.node_id != node_id or record.epoch != epoch or record.segment != segment
        or record.side != side or record.source_sha256 != source_sha256
        or not record.alignment_id or not record.method or not record.neutral_pose
        or not record.mounting_validity_statement
        or not record.uncertainty or record.status not in ("supported", "assumed")
        or record.axes_basis not in ("measured", "synthetic_ground_truth", "assumed")
        or (record.axes_basis == "assumed" and record.status != "assumed")
        or quaternion.shape != (4,) or not bool(np.isfinite(quaternion).all())
        or not bool(np.isclose(np.linalg.norm(quaternion), 1.0, rtol=0, atol=1e-12))
    ):
        return "alignment_incompatible"
    return None


def long_axis_elevation(
    relative: RelativeOrientationResult, *, thorax_alignment: AlignmentRecord | None,
    humerus_alignment: AlignmentRecord | None, side: Side, source_type: str,
    max_sample_gap_us: int,
) -> ElevationResult:
    """Compute unsigned angle of H +Z to T +Z from valid q_TH only.

    The alignments document transforms already applied upstream of q_TH; this
    operation checks their evidence but never composes them a second time.
    """
    grid = np.asarray(relative.common_time_us)
    quaternions = np.asarray(relative.quaternion_th)
    m2_valid = np.asarray(relative.valid)
    if grid.ndim != 1 or grid.dtype != np.int64 or len(grid) == 0:
        raise ValueError("common_time_us must be a nonempty int64 vector")
    if bool((grid[1:] <= grid[:-1]).any()) or bool((np.diff(grid) <= 0).any()):
        raise ValueError("invalid_common_time")
    if quaternions.shape != (len(grid), 4) or m2_valid.shape != (len(grid),) or m2_valid.dtype != np.bool_:
        raise ValueError("M2 quaternion and valid arrays must match common-time rows")
    if len(relative.reason) != len(grid):
        raise ValueError("M2 reason count must match common-time rows")
    if side not in ("left", "right") or not source_type:
        raise ValueError("side and source_type must be declared")
    if isinstance(max_sample_gap_us, bool) or not isinstance(max_sample_gap_us, int) or max_sample_gap_us <= 0:
        raise ValueError("max_sample_gap_us must be a positive integer")

    angles = np.full(len(grid), np.nan, dtype=np.float64)
    valid = np.zeros(len(grid), dtype=np.bool_)
    reasons: list[str] = []
    global_reason: str | None = None
    a_map, b_map, heading = relative.thorax_clock_map, relative.humerus_clock_map, relative.heading_relation
    if a_map is None or b_map is None or heading is None:
        global_reason = "clock_or_heading_missing"
    elif (
        a_map.status not in ("supported", "assumed") or b_map.status not in ("supported", "assumed")
        or heading.status not in ("supported", "assumed")
        or (a_map.status == "supported" and a_map.heldout_residual_us is None)
        or (b_map.status == "supported" and b_map.heldout_residual_us is None)
        or not a_map.method or not b_map.method or not heading.method
        or not heading.thorax_world_id or not heading.humerus_world_id
        or not np.isfinite(a_map.uncertainty_us) or not np.isfinite(b_map.uncertainty_us)
        or a_map.uncertainty_us + b_map.uncertainty_us > relative.max_timing_uncertainty_us
        or not bool(np.isfinite(heading.quaternion_thorax_world_humerus_world).all())
        or not bool(np.isclose(np.linalg.norm(heading.quaternion_thorax_world_humerus_world),
                               1.0, rtol=0, atol=1e-12))
    ):
        global_reason = "clock_or_heading_missing"
    else:
        global_reason = _alignment_reason(
            thorax_alignment, segment="T", source_sha256=relative.thorax_source_sha256,
            side=side, node_id=a_map.node_id, epoch=a_map.epoch,
        )
        if global_reason is None:
            global_reason = _alignment_reason(
                humerus_alignment, segment="H", source_sha256=relative.humerus_source_sha256,
                side=side, node_id=b_map.node_id, epoch=b_map.epoch,
            )
    if global_reason is not None:
        reasons = [global_reason] * len(grid)
    else:
        for index, quaternion in enumerate(quaternions):
            if not m2_valid[index]:
                reasons.append(f"m2_invalid:{relative.reason[index]}")
                continue
            if not bool(np.isfinite(quaternion).all()) or not bool(
                np.isclose(np.linalg.norm(quaternion), 1.0, rtol=0, atol=1e-12)
            ):
                reasons.append("nonfinite_or_nonunit_quaternion")
                continue
            axis_t = rotate_vector(quaternion, (0.0, 0.0, 1.0))
            angles[index] = np.arctan2(np.hypot(axis_t[0], axis_t[1]), axis_t[2])
            valid[index] = True
            reasons.append("valid")

    label: Literal["Derived", "Assumed/Experimental", "Invalid"] = "Invalid"
    if bool(valid.any()):
        assert a_map is not None and b_map is not None and heading is not None
        assert thorax_alignment is not None and humerus_alignment is not None
        if (
            relative.evidence_label == "Assumed/Experimental"
            or "assumed" in (a_map.status, b_map.status, heading.status,
                             thorax_alignment.status, humerus_alignment.status)
            or "assumed" in (thorax_alignment.axes_basis, humerus_alignment.axes_basis)
        ):
            label = "Assumed/Experimental"
        else:
            label = "Derived"
    anatomical_eligible = bool(
        valid.any() and label == "Derived" and source_type == "recorded"
        and thorax_alignment is not None and humerus_alignment is not None
        and thorax_alignment.axes_basis == "measured" and humerus_alignment.axes_basis == "measured"
    )
    return ElevationResult(
        common_time_us=grid.copy(), elevation_rad=angles, valid=valid, reason=tuple(reasons),
        evidence_label=label, anatomical_eligible=anatomical_eligible, side=side,
        source_type=source_type, max_sample_gap_us=max_sample_gap_us,
        thorax_source_sha256=relative.thorax_source_sha256,
        humerus_source_sha256=relative.humerus_source_sha256, relative_orientation=relative,
        thorax_alignment=thorax_alignment, humerus_alignment=humerus_alignment,
    )


def relative_angular_speed(
    relative: RelativeOrientationResult, *, thorax_alignment: AlignmentRecord | None,
    humerus_alignment: AlignmentRecord | None, side: Side, source_type: str,
    max_sample_gap_us: int,
) -> AngularSpeedResult:
    """Compute interval-average 3-D relative speed from observed common times.

    Endpoint rotations cannot reveal motion within an interval. In particular,
    identical endpoints after a full revolution yield zero by definition, not
    evidence that the segment was stationary.
    """
    gated = long_axis_elevation(
        relative, thorax_alignment=thorax_alignment, humerus_alignment=humerus_alignment,
        side=side, source_type=source_type, max_sample_gap_us=max_sample_gap_us,
    )
    grid = gated.common_time_us
    speed = np.full(len(grid) - 1, np.nan, dtype=np.float64)
    valid = np.zeros(len(grid) - 1, dtype=np.bool_)
    reasons: list[str] = []
    for index in range(len(speed)):
        if not gated.valid[index]:
            reasons.append(gated.reason[index])
            continue
        if not gated.valid[index + 1]:
            reasons.append(gated.reason[index + 1])
            continue
        delta_us = int(grid[index + 1]) - int(grid[index])
        if delta_us <= 0:
            reasons.append("invalid_common_time")
            continue
        if delta_us > max_sample_gap_us:
            reasons.append("sample_gap")
            continue
        prior_inverse = tuple(float(value) for value in inverse_quaternion(relative.quaternion_th[index]))
        delta_q = compose_quaternions(
            prior_inverse, relative.quaternion_th[index + 1],
        )
        principal_angle_rad = 2.0 * np.arctan2(np.linalg.norm(delta_q[1:]), abs(delta_q[0]))
        speed[index] = principal_angle_rad / (delta_us / 1_000_000)
        valid[index] = True
        reasons.append("valid")

    label: Literal["Derived", "Assumed/Experimental", "Invalid"] = (
        gated.evidence_label if bool(valid.any()) else "Invalid"
    )
    return AngularSpeedResult(
        start_time_us=grid[:-1].copy(), end_time_us=grid[1:].copy(),
        relative_angular_speed_rads=speed, valid=valid, reason=tuple(reasons),
        evidence_label=label, anatomical_eligible=bool(valid.any() and gated.anatomical_eligible),
        side=side, source_type=source_type, max_sample_gap_us=max_sample_gap_us,
        thorax_source_sha256=relative.thorax_source_sha256,
        humerus_source_sha256=relative.humerus_source_sha256, elevation_result=gated,
    )


def interval_rom_duration(
    relative: RelativeOrientationResult, *, thorax_alignment: AlignmentRecord | None,
    humerus_alignment: AlignmentRecord | None, side: Side, source_type: str,
    max_sample_gap_us: int, start_time_us: int, end_time_us: int,
) -> IntervalRomDurationResult:
    """Compute long-axis elevation range and elapsed time for a declared interval.

    Both endpoints must be exact common-time samples. No missing row is bridged,
    and neither metric is returned unless the entire closed interval is eligible.
    """
    gated = long_axis_elevation(
        relative, thorax_alignment=thorax_alignment, humerus_alignment=humerus_alignment,
        side=side, source_type=source_type, max_sample_gap_us=max_sample_gap_us,
    )
    if (
        isinstance(start_time_us, bool) or not isinstance(start_time_us, (int, np.integer))
        or isinstance(end_time_us, bool) or not isinstance(end_time_us, (int, np.integer))
    ):
        raise ValueError("start_time_us and end_time_us must be integer microseconds")

    grid = gated.common_time_us
    first_invalid_row_index: int | None = None
    invalid_row_reasons: tuple[tuple[int, str], ...] = ()
    reason = "valid"
    rom_rad = float("nan")
    elapsed_duration_s = float("nan")
    if start_time_us > end_time_us:
        reason = "interval_order"
    elif start_time_us == end_time_us:
        reason = "interval_too_short"
    else:
        start_index = int(np.searchsorted(grid, start_time_us))
        end_index = int(np.searchsorted(grid, end_time_us))
        if (
            start_index == len(grid) or end_index == len(grid)
            or int(grid[start_index]) != start_time_us or int(grid[end_index]) != end_time_us
        ):
            reason = "interval_endpoint_missing"
        elif end_index - start_index < 1:
            reason = "interval_too_short"
        else:
            invalid_row_reasons = tuple(
                (index, gated.reason[index]) for index in range(start_index, end_index + 1)
                if not gated.valid[index]
            )
            if invalid_row_reasons:
                first_invalid_row_index = invalid_row_reasons[0][0]
                reason = "interval_invalid_row"
            elif any(
                int(grid[index + 1]) - int(grid[index]) > max_sample_gap_us
                for index in range(start_index, end_index)
            ):
                reason = "sample_gap"
            else:
                angles = gated.elevation_rad[start_index:end_index + 1]
                rom_rad = float(np.max(angles) - np.min(angles))
                elapsed_duration_s = (int(end_time_us) - int(start_time_us)) / 1_000_000

    valid = reason == "valid"
    return IntervalRomDurationResult(
        start_time_us=int(start_time_us), end_time_us=int(end_time_us),
        rom_rad=rom_rad, elapsed_duration_s=elapsed_duration_s, valid=valid, reason=reason,
        first_invalid_row_index=first_invalid_row_index, invalid_row_reasons=invalid_row_reasons,
        evidence_label=gated.evidence_label if valid else "Invalid",
        anatomical_eligible=bool(valid and gated.anatomical_eligible),
        side=side, source_type=source_type, max_sample_gap_us=max_sample_gap_us,
        thorax_source_sha256=relative.thorax_source_sha256,
        humerus_source_sha256=relative.humerus_source_sha256, elevation_result=gated,
    )
