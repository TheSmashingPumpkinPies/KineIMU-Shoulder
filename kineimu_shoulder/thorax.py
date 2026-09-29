"""M4 CP3 explicit thorax resampling and movement-start excursion proxy.

Post-alignment scalar-first quaternions remain the rotation representation.
SciPy supplies SLERP, quaternion composition and rotation matrices. The
contract's explicit Z-Y-X extraction respects its configured singularity
floor; Euler components are output only. No clinical score.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation  # type: ignore[import-untyped]

from kineimu_shoulder.exercise import (
    ExerciseConfig,
    ExerciseMetricsResult,
    RepetitionMetricResult,
    _hash,
    _same,
    compute_repetition_metrics,
)
from kineimu_shoulder.relative_orientation import (
    ClockMap,
    EvidenceStatus,
    SegmentOrientationStream,
    _check_map,
    _check_stream,
    _round_clock_times,
    _sample_at,
)
from kineimu_shoulder.shoulder import AlignmentRecord, _alignment_reason


@dataclass(frozen=True)
class ThoraxHeadingEvidence:
    world_id: str
    method: str
    reference_sha256: str
    covered_window_us: tuple[int, int]
    status: EvidenceStatus


@dataclass(frozen=True)
class ThoraxDriftEvidence:
    world_id: str
    method: str
    reference_sha256: str
    covered_window_us: tuple[int, int]
    bound_rad: float
    status: EvidenceStatus


@dataclass(frozen=True)
class ThoraxCommonGrid:
    original_stream: SegmentOrientationStream
    source_valid: NDArray[np.bool_]
    source_reason: tuple[str, ...]
    mapped_time_us: NDArray[np.float64]
    clock_map: ClockMap | None
    alignment: AlignmentRecord | None
    calibration_sha256: str
    common_time_us: NDArray[np.int64]
    quaternion_wat: NDArray[np.float64]
    valid: NDArray[np.bool_]
    reason: tuple[str, ...]
    bracket_indices: tuple[tuple[int, int] | None, ...]
    interpolation_weights: tuple[float | None, ...]
    max_timing_uncertainty_us: float
    configuration: ExerciseConfig
    configuration_sha256: str
    heading_evidence: ThoraxHeadingEvidence | None
    drift_evidence: ThoraxDriftEvidence | None
    definition_version: str = "m4-thorax-common-grid/1.0"
    interpolation: Literal["slerp"] = "slerp"
    method_version: str = "m4-thorax-preparation/1.0"


@dataclass(frozen=True)
class ThoraxComponent:
    min_rad: float
    max_rad: float
    magnitude_rad: float
    valid: bool
    reason: str
    evidence_label: str
    anatomical_eligible: bool
    unit: Literal["rad"] = "rad"


@dataclass(frozen=True)
class RepetitionThoraxResult:
    repetition: RepetitionMetricResult
    extension: ThoraxComponent
    lateral_flexion: ThoraxComponent
    axial_rotation: ThoraxComponent
    reasons: tuple[str, ...]
    offending_rows: tuple[tuple[int, str], ...]
    offending_intervals: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class ExerciseThoraxResult:
    metrics: ExerciseMetricsResult
    trace: ThoraxCommonGrid | None
    repetitions: tuple[RepetitionThoraxResult, ...]
    definition_version: str = "m4-thorax-excursion/1.0"


def _check_evidence(record: ThoraxHeadingEvidence | ThoraxDriftEvidence | None) -> None:
    if record is None:
        return
    window = record.covered_window_us
    if (not record.world_id or not record.method or not _hash(record.reference_sha256)
        or record.status not in ("supported", "assumed") or len(window) != 2
        or any(isinstance(v, bool) or not isinstance(v, int) for v in window)
        or window[0] > window[1]):
        raise ValueError("thorax evidence requires method/reference/window/status")
    if isinstance(record, ThoraxDriftEvidence) and (
        isinstance(record.bound_rad, bool) or not isfinite(record.bound_rad) or record.bound_rad < 0
    ):
        raise ValueError("thorax drift bound must be finite nonnegative rad")


def prepare_thorax_common_grid(
    stream: SegmentOrientationStream, *, common_time_us: NDArray[np.int64],
    clock_map: ClockMap | None, alignment: AlignmentRecord | None, calibration_sha256: str,
    configuration: ExerciseConfig, max_timing_uncertainty_us: float,
    heading_evidence: ThoraxHeadingEvidence | None, drift_evidence: ThoraxDriftEvidence | None,
    source_valid: NDArray[np.bool_] | None = None, source_reason: tuple[str, ...] | None = None,
) -> ThoraxCommonGrid:
    """Explicit processed operation, no extrapolation or second alignment.

    Retain original indices (including filtered clock-validity rows), mapped
    times for ALL originals and endpoint QC. Brackets/weights also survive
    failed interpolation. Inputs must be finite unit segment quaternions;
    independent acquisition QC is supplied with source_valid/source_reason.
    """
    _check_stream(stream)
    configuration.validate()
    if configuration.max_thorax_drift_rad is None:
        raise ValueError("thorax trace requires a configured drift limit")
    grid = np.asarray(common_time_us)
    if (grid.ndim != 1 or grid.dtype != np.int64 or len(grid) < 2
        or any(int(b) <= int(a) for a, b in zip(grid[:-1], grid[1:], strict=True))):
        raise ValueError("thorax grid must contain ordered int64 common-time rows")
    if (isinstance(max_timing_uncertainty_us, bool) or not isfinite(max_timing_uncertainty_us)
        or max_timing_uncertainty_us < 0 or not _hash(calibration_sha256)):
        raise ValueError("thorax preparation requires calibration hash and timing uncertainty limit")
    _check_evidence(heading_evidence)
    _check_evidence(drift_evidence)
    n = len(stream.timestamp_us)
    if (source_valid is None) != (source_reason is None):
        raise ValueError("thorax source QC requires both validity and reasons")
    qc = np.ones(n, dtype=np.bool_) if source_valid is None else np.asarray(source_valid)
    qc_reasons = ("valid",)*n if source_reason is None else source_reason
    if (qc.shape != (n,) or qc.dtype != np.bool_ or len(qc_reasons) != n
        or any(not isinstance(r, str) or not r or bool(v) != (r == "valid")
               for v, r in zip(qc, qc_reasons, strict=True))):
        raise ValueError("thorax source QC shape/reason mismatch")
    output = np.full((len(grid), 4), np.nan, dtype=np.float64)
    valid = np.zeros(len(grid), dtype=np.bool_)
    mapped = np.full(n, np.nan, dtype=np.float64)
    reasons: list[str] = []
    brackets: list[tuple[int, int] | None] = []
    weights: list[float | None] = []
    failure: str | None = None
    if clock_map is None:
        failure = "clock_map_missing"
    elif not _check_map(clock_map, stream):
        failure = "clock_map_incompatible"
    else:
        mapped = _round_clock_times(
            clock_map.slope*stream.timestamp_us.astype(np.float64)+clock_map.intercept_us, clock_map
        )
        if not bool(np.isfinite(mapped).all()) or bool((mapped[1:] <= mapped[:-1]).any()):
            failure = "clock_map_incompatible"
        elif clock_map.uncertainty_us > max_timing_uncertainty_us:
            failure = "clock_uncertainty"
    alignment_failure = _alignment_reason(
        alignment, segment="T", source_sha256=stream.source_sha256,
        side=alignment.side if alignment else "left", node_id=stream.node_id, epoch=stream.epoch,
    )
    failure = failure or alignment_failure
    indices = np.array([], dtype=np.int64)
    if clock_map is not None:
        indices = np.flatnonzero((stream.timestamp_us >= clock_map.valid_device_start_us)
                                 & (stream.timestamp_us <= clock_map.valid_device_end_us))
    for time in grid:
        bracket = None
        weight = None
        q = None
        reason = failure or "valid"
        if failure is None:
            assert clock_map is not None
            filtered = mapped[indices]
            q, reason = _sample_at(filtered, stream.quaternion_wsegment[indices], clock_map,
                                   int(time), configuration.max_sample_gap_us)
            if len(filtered) and filtered[0] <= time <= filtered[-1]:
                position = int(np.searchsorted(filtered, time))
                if filtered[position] == time:
                    left = right = int(indices[position])
                    weight = 0.
                else:
                    left, right = int(indices[position-1]), int(indices[position])
                    weight = float((int(time)-mapped[left])/(mapped[right]-mapped[left]))
                bracket = (left, right)
                # Preserve all source causes in the original record; row reason
                # selects the first failing endpoint in temporal order.
                for source_index in dict.fromkeys((left, right)):
                    if not qc[source_index] and reason == "valid":
                        reason = f"source_qc:{qc_reasons[source_index]}"
                        q = None
        if q is not None:
            output[len(reasons)] = q
            valid[len(reasons)] = True
        reasons.append(reason)
        brackets.append(bracket)
        weights.append(weight)
    original = SegmentOrientationStream(stream.node_id, stream.clock_id, stream.epoch, stream.world_id,
                                        stream.source_sha256, stream.timestamp_us.copy(),
                                        stream.quaternion_wsegment.copy())
    return ThoraxCommonGrid(original, qc.copy(), tuple(qc_reasons), mapped, clock_map, alignment,
                           calibration_sha256, grid.copy(), output, valid, tuple(reasons),
                           tuple(brackets), tuple(weights), max_timing_uncertainty_us, configuration,
                           configuration.sha256, heading_evidence, drift_evidence)


def _validate_trace(trace: ThoraxCommonGrid) -> None:
    expected = prepare_thorax_common_grid(
        trace.original_stream, common_time_us=trace.common_time_us, clock_map=trace.clock_map,
        alignment=trace.alignment, calibration_sha256=trace.calibration_sha256,
        configuration=trace.configuration, max_timing_uncertainty_us=trace.max_timing_uncertainty_us,
        heading_evidence=trace.heading_evidence, drift_evidence=trace.drift_evidence,
        source_valid=trace.source_valid, source_reason=trace.source_reason,
    )
    if not _same(trace, expected):
        raise ValueError("thorax trace does not match original samples/preparation/provenance")


def compute_thorax_excursion(
    metrics: ExerciseMetricsResult, *, trace: ThoraxCommonGrid | None,
) -> ExerciseThoraxResult:
    """All-or-nothing closed-rep excursion with independent proxy validity."""
    if not isinstance(metrics, ExerciseMetricsResult) or not _same(
        metrics, compute_repetition_metrics(metrics.segmentation)
    ):
        raise ValueError("thorax proxy requires authentic M4 repetition metrics")
    if trace is not None:
        if not isinstance(trace, ThoraxCommonGrid):
            raise ValueError("thorax trace must be an explicit common-grid record")
        _validate_trace(trace)
    s = metrics.segmentation
    e = s.elevation_result
    relative = e.relative_orientation
    binding_ok = trace is not None and (
        _same(trace.common_time_us, e.common_time_us)
        and trace.original_stream.source_sha256 == e.thorax_source_sha256
        and _same(trace.clock_map, relative.thorax_clock_map)
        and trace.clock_map is not None
        and (trace.original_stream.node_id, trace.original_stream.clock_id, trace.original_stream.epoch)
        == (trace.clock_map.node_id, trace.clock_map.clock_id, trace.clock_map.epoch)
        and _same(trace.alignment, e.thorax_alignment)
        and trace.calibration_sha256 == s.calibration_sha256[0]
        and _same(trace.configuration, s.configuration)
        and trace.max_timing_uncertainty_us == relative.max_timing_uncertainty_us
        and relative.heading_relation is not None
        and trace.original_stream.world_id == relative.heading_relation.thorax_world_id
        and trace.alignment is not None and trace.alignment.validity == "current"
        and not trace.alignment.remounted
    )
    reps: list[RepetitionThoraxResult] = []
    for rep in metrics.repetitions:
        c = rep.candidate
        reasons: list[str] = []
        bad_rows: list[tuple[int, str]] = []
        bad_intervals: list[tuple[int, str]] = []
        label = s.evidence_label
        eligible = False
        components = np.empty((0, 3))
        if not c.valid:
            reasons.extend(c.reasons)
        elif trace is None:
            reasons.append("thorax_trace_missing")
        elif not binding_ok:
            reasons.append("thorax_trace_incompatible")
        else:
            start, end = (int(np.searchsorted(trace.common_time_us, v)) for v in (c.start_us, c.end_us))
            for i in range(start, end+1):
                if not trace.valid[i]:
                    bad_rows.append((i, trace.reason[i]))
                    reasons.append("thorax_sample_gap" if trace.reason[i] == "interpolation_gap"
                                   else "thorax_invalid_row")
            for i in range(start, end):
                if int(trace.common_time_us[i+1])-int(trace.common_time_us[i]) > s.configuration.max_sample_gap_us:
                    bad_intervals.append((i, "sample_gap"))
                    reasons.append("thorax_sample_gap")
            for record, missing in ((trace.heading_evidence, "thorax_heading_missing"),
                                    (trace.drift_evidence, "thorax_drift_unbounded")):
                if (record is None or record.world_id != trace.original_stream.world_id
                    or record.covered_window_us[0] > c.start_us or record.covered_window_us[1] < c.end_us):
                    reasons.append(missing)
            if trace.drift_evidence is not None:
                assert s.configuration.max_thorax_drift_rad is not None
                if trace.drift_evidence.bound_rad > s.configuration.max_thorax_drift_rad:
                    reasons.append("thorax_drift_exceeded")
            if not reasons:
                assert trace.heading_evidence is not None and trace.drift_evidence is not None
                assert trace.clock_map is not None and trace.alignment is not None
                if "assumed" in (trace.heading_evidence.status, trace.drift_evidence.status,
                                 trace.clock_map.status, trace.alignment.status):
                    label = "Assumed/Experimental"
                # Compute q0^-1 * qt using SciPy. The contract's explicit
                # matrix extraction avoids as_euler's fixed gimbal-lock
                # tolerance overriding the caller's decomposition_cos_floor.
                rotations = Rotation.from_quat(trace.quaternion_wat[start:end+1], scalar_first=True)
                delta = rotations[0].inv()*rotations
                matrices = delta.as_matrix()
                cos_beta = np.hypot(matrices[:, 0, 0], matrices[:, 1, 0])
                singular = np.flatnonzero(cos_beta <= s.configuration.decomposition_cos_floor)
                if len(singular):
                    reasons.append("thorax_decomposition_singular")
                    bad_rows.extend((start+int(i), "thorax_decomposition_singular") for i in singular)
                else:
                    beta = np.arctan2(-matrices[:, 2, 0], cos_beta)
                    alpha = np.arctan2(matrices[:, 2, 1], matrices[:, 2, 2])
                    gamma = np.arctan2(matrices[:, 1, 0], matrices[:, 0, 0])
                    alpha = (alpha+pi) % (2*pi)-pi
                    gamma = (gamma+pi) % (2*pi)-pi
                    components = np.column_stack((-beta, -alpha, gamma))
                    components[0] = 0.  # exact baseline is part of the definition
                    crossings = np.flatnonzero((np.abs(np.diff(components, axis=0)) > pi).any(axis=1))
                    if len(crossings):
                        reasons.append("thorax_branch_crossing")
                        bad_intervals.extend((start+int(i), "thorax_branch_crossing") for i in crossings)
                    eligible = (s.anatomical_eligible and label != "Assumed/Experimental"
                                and trace.alignment.axes_basis == "measured")
        reasons = list(dict.fromkeys(reasons))
        values: list[ThoraxComponent] = []
        for axis in range(3):
            if reasons:
                values.append(ThoraxComponent(float("nan"), float("nan"), float("nan"), False,
                                              reasons[0], label, False))
            else:
                minimum, maximum = float(components[:, axis].min()), float(components[:, axis].max())
                values.append(ThoraxComponent(minimum, maximum, max(abs(minimum), abs(maximum)), True,
                                              "ok", label, eligible))
        reps.append(RepetitionThoraxResult(rep, values[0], values[1], values[2],
                                          tuple(reasons), tuple(bad_rows), tuple(bad_intervals)))
    return ExerciseThoraxResult(metrics, trace, tuple(reps))
