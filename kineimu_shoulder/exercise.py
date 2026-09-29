"""M4.1 plane verification and deterministic observed repetition envelopes.

Implements CP1 of protocols/M4_EXERCISE_CONTRACT.md. No smoothing or input
repair. The project-specific confirmation/QC rules justify this small state
machine; rotations and closed-interval amplitude use the existing M3 path.
Per-repetition metrics, thorax proxy and session summaries belong to CP2–CP4.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, is_dataclass
from math import atan2, hypot, isfinite, isnan, pi
from typing import Literal

import numpy as np

from kineimu_shoulder.frames import rotate_vector
from kineimu_shoulder.relative_orientation import _round_clock_times
from kineimu_shoulder.shoulder import (
    AngularSpeedResult,
    ElevationResult,
    Side,
    interval_rom_duration,
    long_axis_elevation,
    relative_angular_speed,
)

Exercise = Literal["flexion", "abduction"]


@dataclass(frozen=True)
class ExerciseConfig:
    """Complete SI m4-thresholds/1.0 profile; gap is always caller supplied."""

    max_sample_gap_us: int
    rest_level_rad: float = pi / 18
    start_level_rad: float = pi / 9
    rest_confirm_us: int = 200000
    start_confirm_us: int = 200000
    min_peak_rad: float = pi / 3
    min_rom_rad: float = 2 * pi / 9
    min_phase_us: int = 200000
    min_rep_us: int = 800000
    plane_min_elevation_rad: float = pi / 6
    plane_tolerance_rad: float = pi / 9
    plane_min_fraction: float = .90
    hold_band_rad: float = pi / 36
    hold_speed_limit_rads: float = pi / 36
    min_hold_us: int = 500000
    cv_mean_floor_rad: float = pi / 180
    decomposition_cos_floor: float = 1e-8
    max_thorax_drift_rad: float | None = None
    version: str = "m4-thresholds/1.0"

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if name == "version":
                continue
            if name == "max_thorax_drift_rad" and value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"configuration {name} must be finite numeric SI")
            if name.endswith("_us") and (not isinstance(value, int) or value <= 0):
                raise ValueError(f"configuration {name} must be a positive integer")
        if not (
            self.version == "m4-thresholds/1.0"
            and 0 <= self.rest_level_rad < self.start_level_rad < self.plane_min_elevation_rad
            <= self.min_peak_rad < pi
            and 0 < self.min_rom_rad <= pi and 0 < self.plane_tolerance_rad < pi / 2
            and 0 < self.plane_min_fraction <= 1 and 0 <= self.hold_band_rad < self.min_peak_rad
            and self.hold_speed_limit_rads >= 0 and self.cv_mean_floor_rad > 0
            and 0 < self.decomposition_cos_floor < 1
            and (self.max_thorax_drift_rad is None or self.max_thorax_drift_rad > 0)
        ):
            raise ValueError("configuration violates m4-thresholds/1.0 bounds")

    @property
    def sha256(self) -> str:
        self.validate()
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                                        allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class SegmentationDiagnostic:
    reason: str
    bounds_us: tuple[int, int]
    offending_rows: tuple[tuple[int, str], ...] = ()
    offending_intervals: tuple[tuple[int, str], ...] = ()


@dataclass(frozen=True)
class RepetitionCandidate:
    id: int
    start_us: int
    end_us: int
    start_confirmation_us: tuple[int, int] | None
    end_confirmation_us: tuple[int, int] | None
    peak_us: int
    partial_start: bool
    partial_end: bool
    interrupted: bool
    valid: bool
    reasons: tuple[str, ...]
    offending_rows: tuple[tuple[int, str], ...]
    offending_intervals: tuple[tuple[int, str], ...]
    plane_eligible_duration_s: float
    plane_passing_duration_s: float
    plane_fraction: float | None
    plane_failing_intervals: tuple[int, ...]
    plane_nonidentifiable_intervals: tuple[int, ...]
    rise_support_us: tuple[int, int]
    return_support_us: tuple[int, int]
    observed_duration_s: float
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class SegmentationResult:
    definition_version: str
    session_id: str
    protocol_id: str
    protocol_version: str
    exercise: Exercise
    side: Side
    analysis_window_us: tuple[int, int]
    configuration: ExerciseConfig
    configuration_sha256: str
    calibration_sha256: tuple[str, str]
    processing_sha256: str
    elevation_result: ElevationResult
    angular_speed_result: AngularSpeedResult
    analysis_valid: bool
    reasons: tuple[str, ...]
    evidence_label: str
    anatomical_eligible: bool
    detected_count: int | None
    valid_count: int | None
    excluded_count: int | None
    candidates: tuple[RepetitionCandidate, ...]
    segmentation_diagnostics: tuple[SegmentationDiagnostic, ...]
    observed_valid_duration_s: float
    observed_invalid_duration_s: float


def _same(left: object, right: object) -> bool:
    """Exact nested association, including NaNs and original evidence records."""
    if type(left) is not type(right):
        return False
    if isinstance(left, float) and isinstance(right, float) and isnan(left) and isnan(right):
        return True
    if isinstance(left, np.ndarray):
        assert isinstance(right, np.ndarray)
        return bool(left.dtype == right.dtype and np.array_equal(left, right, equal_nan=True))
    if is_dataclass(left) and not isinstance(left, type):
        return all(_same(getattr(left, f.name), getattr(right, f.name)) for f in fields(left))
    if isinstance(left, tuple):
        assert isinstance(right, tuple)
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right, strict=True))
    return bool(left == right)


def _hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _validate_inputs(e: ElevationResult, s: AngularSpeedResult, config: ExerciseConfig,
                     side: Side) -> tuple[ElevationResult, AngularSpeedResult]:
    if not isinstance(e, ElevationResult) or not isinstance(s, AngularSpeedResult):
        raise ValueError("M4 requires explicit M3 elevation and speed records; no missing-speed fallback")
    grid = e.common_time_us
    if grid.ndim != 1 or grid.dtype != np.int64 or len(grid) < 2:
        raise ValueError("M4 requires at least two int64 common-time rows")
    if any(int(b) <= int(a) for a, b in zip(grid[:-1], grid[1:], strict=True)):
        raise ValueError("M4 common-time rows must be strictly ordered")
    n = len(grid)
    for values, count, dtype in [(e.elevation_rad, n, np.float64), (e.valid, n, np.bool_),
                                 (s.relative_angular_speed_rads, n-1, np.float64), (s.valid, n-1, np.bool_)]:
        if values.shape != (count,) or values.dtype != dtype:
            raise ValueError("M4 M3 array shape/dtype mismatch")
    if len(e.reason) != n or len(s.reason) != n - 1:
        raise ValueError("M4 M3 reason count mismatch")
    for mask, reasons in ((e.valid, e.reason), (s.valid, s.reason)):
        if any(not isinstance(r, str) or not r or (bool(v) != (r == "valid"))
               for v, r in zip(mask, reasons, strict=True)):
            raise ValueError("M4 M3 validity and reason disagree")
    if not _same(grid, e.relative_orientation.common_time_us) or not _same(e, s.elevation_result):
        raise ValueError("M4 elevation/speed/M2 association mismatch")
    if not _same(s.start_time_us, grid[:-1]) or not _same(s.end_time_us, grid[1:]):
        raise ValueError("M4 speed intervals must be exact adjacent grid pairs")
    for name in ("side", "source_type", "thorax_source_sha256", "humerus_source_sha256", "max_sample_gap_us"):
        if getattr(e, name) != getattr(s, name):
            raise ValueError(f"M4 M3 binding mismatch: {name}")
    if e.side != side or e.max_sample_gap_us != config.max_sample_gap_us:
        raise ValueError("M4 side/gap must match M3")
    if e.definition_version != "m3-long-axis-elevation/1.0" or s.definition_version != "m3-relative-angular-speed/1.0":
        raise ValueError("M4 requires supported M3 definitions")
    relative = e.relative_orientation
    if not all(_hash(v) for v in (e.thorax_source_sha256, e.humerus_source_sha256)) or (
        e.thorax_source_sha256 != relative.thorax_source_sha256
        or e.humerus_source_sha256 != relative.humerus_source_sha256
    ):
        raise ValueError("M4 original source SHA-256 binding mismatch")
    if (relative.interpolation != "slerp" or isinstance(relative.max_interpolation_gap_us, bool)
        or not isinstance(relative.max_interpolation_gap_us, int) or relative.max_interpolation_gap_us <= 0
        or not isfinite(relative.max_timing_uncertainty_us) or relative.max_timing_uncertainty_us < 0):
        raise ValueError("M4 malformed M2 interpolation/timing policy")
    for clock in (relative.thorax_clock_map, relative.humerus_clock_map):
        if clock is None:
            continue  # Missing global evidence is an invalid analysis, not malformed geometry.
        if (not clock.node_id or not clock.clock_id or not _hash(clock.source_sha256)
            or not isfinite(clock.slope) or clock.slope <= 0 or not isfinite(clock.intercept_us)
            or not isfinite(clock.uncertainty_us) or clock.uncertainty_us < 0
            or clock.fit_device_start_us > clock.fit_device_end_us
            or clock.valid_device_start_us > clock.valid_device_end_us
            or clock.heldout_residual_us is not None and (
                not isfinite(clock.heldout_residual_us) or clock.heldout_residual_us < 0)):
            raise ValueError("M4 malformed M2 clock map")
        device_times = _round_clock_times(
            (grid.astype(np.float64) - clock.intercept_us) / clock.slope, clock
        )
        if bool((relative.valid & ((device_times < clock.valid_device_start_us)
                                   | (device_times > clock.valid_device_end_us))).any()):
            raise ValueError("M4 claimed valid M2 rows outside clock validity")
    expected_e = long_axis_elevation(
        relative, thorax_alignment=e.thorax_alignment, humerus_alignment=e.humerus_alignment,
        side=e.side, source_type=e.source_type, max_sample_gap_us=e.max_sample_gap_us,
    )
    expected_s = relative_angular_speed(
        relative, thorax_alignment=e.thorax_alignment, humerus_alignment=e.humerus_alignment,
        side=e.side, source_type=e.source_type, max_sample_gap_us=e.max_sample_gap_us,
    )
    return expected_e, expected_s


def segment_shoulder_repetitions(
    elevation: ElevationResult, speed: AngularSpeedResult, *, exercise: Exercise, side: Side,
    configuration: ExerciseConfig, analysis_window_us: tuple[int, int],
    session_id: str, protocol_id: str, protocol_version: str,
    calibration_sha256: tuple[str, str], processing_sha256: str,
) -> SegmentationResult:
    """Retain all observed envelopes, including censored/QC-excluded candidates.

    CP1 result is an in-memory stage record, not the complete CP5 JSON export.
    Nested M2/M3 records retain all clock, alignment, source and QC evidence.
    No per-repetition metric or numerical session summary is emitted here.
    """
    configuration.validate()
    c = configuration
    if exercise not in ("flexion", "abduction") or side not in ("left", "right"):
        raise ValueError("M4 requires declared flexion/abduction and left/right side")
    if not all(isinstance(v, str) and v for v in (session_id, protocol_id, protocol_version)):
        raise ValueError("M4 requires session and protocol identity/version")
    if len(calibration_sha256) != 2 or not all(_hash(v) for v in (*calibration_sha256, processing_sha256)):
        raise ValueError("M4 requires A/B calibration and processing SHA-256")
    expected_e, expected_s = _validate_inputs(elevation, speed, c, side)
    grid, angles = elevation.common_time_us, elevation.elevation_rad
    if len(analysis_window_us) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, np.integer))
                                         for v in analysis_window_us):
        raise ValueError("M4 analysis window requires integer microseconds")
    first, last = (int(v) for v in analysis_window_us)
    if first >= last or first not in grid or last not in grid:
        raise ValueError("M4 analysis window requires exact ordered grid endpoints")
    lo, hi = int(np.searchsorted(grid, first)), int(np.searchsorted(grid, last))
    global_reasons = {"alignment_missing", "alignment_expired", "alignment_incompatible", "clock_or_heading_missing"}
    failures = tuple(dict.fromkeys(r for r in expected_e.reason if r in global_reasons))
    candidates: list[RepetitionCandidate] = []
    diagnostics: list[SegmentationDiagnostic] = []
    valid_duration_us = 0

    def result(reasons: tuple[str, ...]) -> SegmentationResult:
        valid = not reasons
        count = len(candidates) if valid else None
        eligible = sum(candidate.valid for candidate in candidates) if valid else None
        return SegmentationResult(
            "m4-exercise/1.0", session_id, protocol_id, protocol_version, exercise, side, (first, last),
            c, c.sha256, calibration_sha256, processing_sha256, elevation, speed, valid,
            reasons or ("ok",), expected_e.evidence_label if valid else "Invalid",
            valid and expected_e.anatomical_eligible, count, eligible,
            count - eligible if count is not None and eligible is not None else None,
            tuple(candidates), tuple(diagnostics), valid_duration_us / 1e6,
            (last - first - valid_duration_us) / 1e6,
        )

    if failures:
        return result(failures)
    for supplied, expected, values, expected_values, tolerance in (
        (elevation.valid, expected_e.valid, angles, expected_e.elevation_rad, 1e-10),
        (speed.valid, expected_s.valid, speed.relative_angular_speed_rads,
         expected_s.relative_angular_speed_rads, 1e-10),
    ):
        if bool((supplied & ~expected).any()) or not bool(np.isfinite(values[supplied]).all()) or not bool(
            np.allclose(values[supplied], expected_values[supplied], rtol=0, atol=tolerance)
        ):
            raise ValueError("M4 claimed valid M3 values violate quaternion/elevation/speed contract")
    if (elevation.evidence_label != expected_e.evidence_label
        or elevation.anatomical_eligible != expected_e.anatomical_eligible
        or speed.evidence_label != (expected_s.evidence_label if bool(speed.valid.any()) else "Invalid")
        or speed.anatomical_eligible and not expected_s.anatomical_eligible):
        raise ValueError("M4 input evidence must not be strengthened or mismatched")

    row_valid = elevation.valid & expected_e.valid
    connected = np.zeros(len(grid) - 1, dtype=np.bool_)
    for i in range(lo, hi):
        delta = int(grid[i+1]) - int(grid[i])
        connected[i] = bool(row_valid[i] and row_valid[i+1] and speed.valid[i] and delta <= c.max_sample_gap_us)
        if connected[i]:
            valid_duration_us += delta
        else:
            rows = tuple((j, elevation.reason[j]) for j in (i, i+1) if not row_valid[j])
            intervals: tuple[tuple[int, str], ...] = ((i, speed.reason[i]),) if not speed.valid[i] else ()
            if delta > c.max_sample_gap_us and (i, "sample_gap") not in intervals:
                intervals += ((i, "sample_gap"),)
            diagnostics.append(SegmentationDiagnostic("continuity_break", (int(grid[i]), int(grid[i+1])),
                                                       rows, intervals))
    if not bool(connected[lo:hi].any()):
        return result(("no_usable_continuity",))

    def emit(start: int, end: int, start_confirmation: tuple[int, int] | None,
             end_confirmation: tuple[int, int] | None, partial_start: bool, partial_end: bool,
             break_diagnostic: SegmentationDiagnostic | None) -> None:
        peak = start + int(np.argmax(angles[start:end+1]))
        rows = break_diagnostic.offending_rows if break_diagnostic else ()
        intervals = break_diagnostic.offending_intervals if break_diagnostic else ()
        reasons = [f"upstream_invalid:{r}" for _, r in rows]
        reasons.extend("sample_gap" if r == "sample_gap" else f"upstream_invalid:{r}" for _, r in intervals)
        if break_diagnostic:
            reasons.append("interrupted")
        if partial_start:
            reasons.append("partial_start")
        if partial_end:
            reasons.append("partial_end")
        if min(int(grid[peak]) - int(grid[start]), int(grid[end]) - int(grid[peak])) < c.min_phase_us:
            reasons.append("phase_too_short")
        if int(grid[end]) - int(grid[start]) < c.min_rep_us:
            reasons.append("rep_too_short")
        if angles[peak] < c.min_peak_rad:
            reasons.append("peak_below_minimum")
        amplitude = interval_rom_duration(
            elevation.relative_orientation, thorax_alignment=elevation.thorax_alignment,
            humerus_alignment=elevation.humerus_alignment, side=side, source_type=elevation.source_type,
            max_sample_gap_us=c.max_sample_gap_us, start_time_us=int(grid[start]), end_time_us=int(grid[end]),
        )
        # Singleton interrupted envelopes still retain bounds; their observed range is zero.
        if (amplitude.rom_rad if amplitude.valid else 0.0) < c.min_rom_rad:
            reasons.append("rom_below_minimum")
        deviations: dict[int, float] = {}
        for j in range(start, end+1):
            u = rotate_vector(elevation.relative_orientation.quaternion_th[j], (0., 0., 1.))
            if angles[j] >= c.plane_min_elevation_rad and hypot(float(u[0]), float(u[1])) > 1e-12:
                anterior, lateral = -float(u[0]), -(1 if side == "left" else -1) * float(u[1])
                deviations[j] = (atan2(abs(lateral), anterior) if exercise == "flexion"
                                 else atan2(abs(anterior), lateral))
        eligible_us = passing_us = 0
        failing: list[int] = []
        nonidentifiable: list[int] = []
        for j in range(start, end):
            if j not in deviations or j+1 not in deviations:
                nonidentifiable.append(j)
                continue
            delta = int(grid[j+1]) - int(grid[j])
            eligible_us += delta
            if max(deviations[j], deviations[j+1]) <= c.plane_tolerance_rad:
                passing_us += delta
            else:
                failing.append(j)
        fraction = passing_us / eligible_us if eligible_us else None
        if fraction is None:
            reasons.append("plane_unobservable")
        elif fraction < c.plane_min_fraction:
            reasons.append("plane_mismatch")
        candidates.append(RepetitionCandidate(
            len(candidates)+1, int(grid[start]), int(grid[end]), start_confirmation, end_confirmation,
            int(grid[peak]), partial_start, partial_end, break_diagnostic is not None, not reasons,
            tuple(dict.fromkeys(reasons)) if reasons else ("ok",), rows, intervals,
            eligible_us / 1e6, passing_us / 1e6, fraction, tuple(failing), tuple(nonidentifiable),
            (int(grid[start]), int(grid[peak])), (int(grid[peak]), int(grid[end])),
            (int(grid[end]) - int(grid[start])) / 1e6,
            ("plane_deviation_present",) if failing else (),
        ))

    # Every continuity block begins UNARMED. Confirmation state never crosses QC.
    i = lo
    while i <= hi:
        if not row_valid[i]:
            i += 1
            continue
        block_start = i
        while i < hi and connected[i]:
            i += 1
        block_end = i
        break_diagnostic = next((d for d in diagnostics if d.bounds_us[0] == int(grid[block_end])), None)
        armed = False
        low_start: int | None = None
        high_start: int | None = None
        active_start: int | None = None
        start_confirmation: tuple[int, int] | None = None
        partial_start = False
        for j in range(block_start, block_end+1):
            low = angles[j] <= c.rest_level_rad
            if low:
                if low_start is None:
                    low_start = j
            else:
                low_start = None
            if active_start is not None:
                if low_start is not None and int(grid[j]) - int(grid[low_start]) >= c.rest_confirm_us:
                    emit(active_start, low_start, start_confirmation, (int(grid[low_start]), int(grid[j])),
                         partial_start, False, None)
                    active_start, start_confirmation, partial_start = None, None, False
                    armed = True
                continue
            if low_start is not None and int(grid[j]) - int(grid[low_start]) >= c.rest_confirm_us:
                armed = True
            if not armed and not low:
                active_start, partial_start = j, True
                continue
            high = angles[j] >= c.start_level_rad
            if armed and high:
                if high_start is None:
                    high_start = j
                if int(grid[j]) - int(grid[high_start]) >= c.start_confirm_us:
                    active_start = high_start
                    start_confirmation = (int(grid[high_start]), int(grid[j]))
                    high_start = None
            elif high_start is not None:
                diagnostics.append(SegmentationDiagnostic("start_debounce_failed",
                                                          (int(grid[high_start]), int(grid[j-1]))))
                high_start = None
        if active_start is not None:
            emit(active_start, block_end, start_confirmation, None, partial_start,
                 break_diagnostic is None, break_diagnostic)
        if high_start is not None:
            diagnostics.append(SegmentationDiagnostic("start_debounce_failed",
                                                      (int(grid[high_start]), int(grid[block_end]))))
        i += 1
    return result(())


@dataclass(frozen=True)
class ExerciseMetric:
    """SI scalar; unavailable in-memory values are NaN, never zero."""

    value: float
    valid: bool
    reason: str
    unit: str
    evidence_label: str
    anatomical_eligible: bool


@dataclass(frozen=True)
class RepetitionMetrics:
    rom_rad: ExerciseMetric
    peak_elevation_rad: ExerciseMetric
    rep_duration_s: ExerciseMetric
    elevation_duration_s: ExerciseMetric
    return_duration_s: ExerciseMetric
    hold_duration_s: ExerciseMetric
    rep_speed_mean_rads: ExerciseMetric
    rep_speed_max_rads: ExerciseMetric
    elevation_speed_mean_rads: ExerciseMetric
    elevation_speed_max_rads: ExerciseMetric
    return_speed_mean_rads: ExerciseMetric
    return_speed_max_rads: ExerciseMetric
    hold_speed_mean_rads: ExerciseMetric
    hold_speed_max_rads: ExerciseMetric
    preceding_rest_duration_s: ExerciseMetric


@dataclass(frozen=True)
class RepetitionMetricResult:
    candidate: RepetitionCandidate
    hold_runs_us: tuple[tuple[int, int], ...]
    elevation_intervals: tuple[int, ...]
    return_intervals: tuple[int, ...]
    hold_intervals: tuple[int, ...]
    metrics: RepetitionMetrics


@dataclass(frozen=True)
class ExerciseMetricsResult:
    """CP2 stage with CP1 evidence/provenance; CP3–CP5 remain separate."""

    segmentation: SegmentationResult
    repetitions: tuple[RepetitionMetricResult, ...]


def compute_repetition_metrics(segmentation: SegmentationResult) -> ExerciseMetricsResult:
    """Compute frozen M4 closed-rep metrics and observed interval ownership.

    Hold removes qualifying maximal runs from chronological rise/return
    supports. Speed is the M3 principal 3-D interval magnitude, not a signed
    elevation derivative. No interpolation, smoothing or missing-speed repair.
    Revalidate the full CP1 record so forged bounds/eligibility or mutated
    nested arrays cannot bypass the QC/evidence gates.
    """
    if not isinstance(segmentation, SegmentationResult):
        raise ValueError("M4 metrics require an explicit segmentation result")
    s = segmentation
    expected = segment_shoulder_repetitions(
        s.elevation_result, s.angular_speed_result, exercise=s.exercise, side=s.side,
        configuration=s.configuration, analysis_window_us=s.analysis_window_us,
        session_id=s.session_id, protocol_id=s.protocol_id, protocol_version=s.protocol_version,
        calibration_sha256=s.calibration_sha256, processing_sha256=s.processing_sha256,
    )
    if not _same(s, expected):
        raise ValueError("M4 segmentation result does not match its inputs/configuration")
    e, speed, c = s.elevation_result, s.angular_speed_result, s.configuration
    grid, angles = e.common_time_us, e.elevation_rad
    values = speed.relative_angular_speed_rads
    reps: list[RepetitionMetricResult] = []

    def metric(value: float, unit: str, reason: str = "ok") -> ExerciseMetric:
        valid = reason == "ok"
        return ExerciseMetric(value if valid else float("nan"), valid, reason, unit,
                              s.evidence_label, valid and s.anatomical_eligible)

    def elapsed(intervals: tuple[int, ...]) -> int:
        # Python integer subtraction avoids overflowing signed int64 timestamps.
        return sum(int(grid[i+1]) - int(grid[i]) for i in intervals)

    def statistics(intervals: tuple[int, ...]) -> tuple[ExerciseMetric, ExerciseMetric]:
        duration = elapsed(intervals)
        if not duration:
            return metric(0., "rad/s", "empty_phase"), metric(0., "rad/s", "empty_phase")
        weighted = sum(float(values[i]) * (int(grid[i+1]) - int(grid[i])) for i in intervals)
        return metric(weighted / duration, "rad/s"), metric(max(float(values[i]) for i in intervals), "rad/s")

    for ordinal, candidate in enumerate(s.candidates):
        if not candidate.valid:
            reason = candidate.reasons[0]
            unavailable = RepetitionMetrics(
                *(metric(0., unit, reason) for unit in
                  ("rad", "rad", "s", "s", "s", "s", "rad/s", "rad/s", "rad/s", "rad/s",
                   "rad/s", "rad/s", "rad/s", "rad/s", "s")),
            )
            reps.append(RepetitionMetricResult(candidate, (), (), (), (), unavailable))
            continue
        start, end, peak = (int(np.searchsorted(grid, time)) for time in
                            (candidate.start_us, candidate.end_us, candidate.peak_us))
        amplitude = interval_rom_duration(
            e.relative_orientation, thorax_alignment=e.thorax_alignment, humerus_alignment=e.humerus_alignment,
            side=e.side, source_type=e.source_type, max_sample_gap_us=c.max_sample_gap_us,
            start_time_us=candidate.start_us, end_time_us=candidate.end_us,
        )
        if not amplitude.valid:
            raise ValueError("M4 eligible segmentation contradicts the M3 closed interval")
        hold_runs: list[tuple[int, int]] = []
        hold_indices: list[int] = []
        run_start: int | None = None
        lower = float(angles[peak]) - c.hold_band_rad
        for i in range(start, end+1):
            qualified = i < end and lower <= angles[i] <= angles[peak] and (
                lower <= angles[i+1] <= angles[peak] and speed.valid[i]
                and values[i] <= c.hold_speed_limit_rads
                and int(grid[i+1]) - int(grid[i]) <= c.max_sample_gap_us
            )
            if qualified:
                if run_start is None:
                    run_start = i
            elif run_start is not None:
                if int(grid[i]) - int(grid[run_start]) >= c.min_hold_us:
                    hold_runs.append((int(grid[run_start]), int(grid[i])))
                    hold_indices.extend(range(run_start, i))
                run_start = None
        hold = tuple(hold_indices)
        hold_set = set(hold)
        rise = tuple(i for i in range(start, peak) if i not in hold_set)
        returned = tuple(i for i in range(peak, end) if i not in hold_set)
        all_intervals = tuple(range(start, end))
        rest = metric(0., "s", "rest_interrupted")
        if ordinal and s.candidates[ordinal-1].valid:
            previous = s.candidates[ordinal-1]
            rest_start = int(np.searchsorted(grid, previous.end_us))
            rest_rows = e.valid[rest_start:start+1]
            continuous = bool(rest_rows.all() and speed.valid[rest_start:start].all()) and all(
                int(grid[i+1]) - int(grid[i]) <= c.max_sample_gap_us for i in range(rest_start, start)
            )
            if continuous:
                rest = metric((candidate.start_us - previous.end_us) / 1e6, "s")
        rep_metrics = RepetitionMetrics(
            metric(amplitude.rom_rad, "rad"), metric(float(angles[peak]), "rad"),
            metric(amplitude.elapsed_duration_s, "s"), metric(elapsed(rise) / 1e6, "s"),
            metric(elapsed(returned) / 1e6, "s"), metric(elapsed(hold) / 1e6, "s"),
            *statistics(all_intervals), *statistics(rise), *statistics(returned), *statistics(hold), rest,
        )
        reps.append(RepetitionMetricResult(candidate, tuple(hold_runs), rise, returned, hold, rep_metrics))
    return ExerciseMetricsResult(s, tuple(reps))
