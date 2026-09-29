"""M4 CP4 descriptive set/session summaries and evidence-aware comparisons.

Arithmetic summaries use NumPy; sample SD uses ddof=1. Input stages remain
linked intact. This in-memory stage does not define the CP5 export schema.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timedelta

import numpy as np

from kineimu_shoulder.exercise import (
    ExerciseMetric,
    ExerciseMetricsResult,
    RepetitionMetrics,
    _hash,
    _same,
    compute_repetition_metrics,
)
from kineimu_shoulder.shoulder import AlignmentRecord
from kineimu_shoulder.thorax import ExerciseThoraxResult, compute_thorax_excursion


@dataclass(frozen=True)
class SummaryContext:
    """Explicit processing provenance absent from the M3/CP2 stage records.

    backend=(name, version, configuration SHA256); grid_policy=(method,
    version/configuration identity); generator=(name, version), required for
    synthetic input. Alignment hashes identify artifacts, not raw recordings.
    Start may be absent for a standalone set; comparison requires UTC.
    """

    session_start_utc: str | None
    calibration_ids: tuple[str, str]
    alignment_sha256: tuple[str, str]
    backend: tuple[str, str, str]
    grid_policy: tuple[str, str]
    source_generator: tuple[str, str] | None


@dataclass(frozen=True)
class MetricSummary:
    n: int
    mean: ExerciseMetric
    maximum: ExerciseMetric


@dataclass(frozen=True)
class ExerciseSummary:
    input_result: ExerciseMetricsResult | ExerciseThoraxResult
    context: SummaryContext
    analysis_valid: bool
    reasons: tuple[str, ...]
    detected_count: int | None
    valid_count: int | None
    excluded_count: int | None
    partial_start_count: int | None
    partial_end_count: int | None
    interrupted_count: int | None
    exclusion_reasons: dict[str, tuple[int, ...]]
    exclusion_reason_counts: dict[str, int]
    proxy_valid_count: int | None
    proxy_unavailable_count: int | None
    statistics: dict[str, tuple[MetricSummary, ...]]
    rom_range: ExerciseMetric
    rom_sd: ExerciseMetric
    rom_cv: ExerciseMetric
    active_time_s: ExerciseMetric
    active_cadence: ExerciseMetric
    analysis_window_duration_s: ExerciseMetric
    comparability_keys: dict[str, object]
    definition_version: str = "m4-exercise-summary/1.0"


@dataclass(frozen=True)
class MetricDifference:
    earlier_n: int
    later_n: int
    difference: ExerciseMetric


@dataclass(frozen=True)
class SummaryComparison:
    earlier_id: str
    later_id: str
    earlier: ExerciseSummary
    later: ExerciseSummary
    comparable: bool
    differing_keys: tuple[str, ...]
    differences: dict[str, tuple[MetricDifference, ...]] | None


def _utc(value: str | None) -> datetime:
    if not isinstance(value, str):
        raise ValueError("comparison requires explicit UTC session start")
    try:
        time = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("session start must be ISO UTC") from error
    if time.tzinfo is None or time.utcoffset() != timedelta(0):
        raise ValueError("session start must be explicit UTC")
    return time


def _same_summary(left: object, right: object) -> bool:
    """Extend stage association to CP4 dictionaries containing unavailable NaNs."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        assert isinstance(right, dict)
        return left.keys() == right.keys() and all(_same_summary(v, right[k]) for k, v in left.items())
    if isinstance(left, tuple):
        assert isinstance(right, tuple)
        return len(left) == len(right) and all(_same_summary(a, b) for a, b in zip(left, right, strict=True))
    if is_dataclass(left) and not isinstance(left, type):
        return all(_same_summary(getattr(left, f.name), getattr(right, f.name)) for f in fields(left))
    return _same(left, right)


def _validate_context(context: SummaryContext, source_type: str) -> None:
    if not isinstance(context, SummaryContext):
        raise ValueError("summary requires explicit processing context")
    for values, count in ((context.calibration_ids, 2), (context.alignment_sha256, 2),
                          (context.backend, 3), (context.grid_policy, 2)):
        if not isinstance(values, tuple) or len(values) != count or not all(
            isinstance(v, str) and v.strip() for v in values
        ):
            raise ValueError("summary context requires complete identities/versions")
    if not all(_hash(v) for v in (*context.alignment_sha256, context.backend[2])):
        raise ValueError("summary context requires alignment/backend SHA256")
    generator = context.source_generator
    if generator is not None and (not isinstance(generator, tuple) or len(generator) != 2
                                 or not all(isinstance(v, str) and v.strip() for v in generator)):
        raise ValueError("source generator requires identity/version")
    if source_type == "synthetic" and generator is None:
        raise ValueError("synthetic summaries require source generator/version")
    if context.session_start_utc is not None:
        _utc(context.session_start_utc)


def summarize_exercise(
    result: ExerciseMetricsResult | ExerciseThoraxResult, *, context: SummaryContext,
) -> ExerciseSummary:
    """Summarize eligible whole repetitions; never pool proxy evidence strata.

    One call describes a caller-declared set or session analysis window.
    Reconstruct CP2/CP3 to reject forged metrics, provenance or QC masks.
    Rest/empty phases and optional proxies retain their own denominators.
    """
    if isinstance(result, ExerciseThoraxResult):
        expected_proxy = compute_thorax_excursion(result.metrics, trace=result.trace)
        if not _same(result, expected_proxy):
            raise ValueError("summary proxy does not match its inputs")
        metrics = result.metrics
        proxy = result
    elif isinstance(result, ExerciseMetricsResult):
        metrics = result
        proxy = compute_thorax_excursion(metrics, trace=None)
    else:
        raise ValueError("summary requires explicit M4 metrics or proxy result")
    if not _same(metrics, compute_repetition_metrics(metrics.segmentation)):
        raise ValueError("summary metrics do not match their inputs")
    s = metrics.segmentation
    e = s.elevation_result
    relative = e.relative_orientation
    _validate_context(context, e.source_type)

    def scalar(value: float, unit: str, reason: str = "ok", *, label: str = s.evidence_label,
               anatomical: bool = s.anatomical_eligible) -> ExerciseMetric:
        valid = reason == "ok"
        return ExerciseMetric(value if valid else float("nan"), valid, reason, unit, label, valid and anatomical)

    eligible = tuple(rep for rep in metrics.repetitions if s.analysis_valid and rep.candidate.valid)
    statistics: dict[str, tuple[MetricSummary, ...]] = {}

    def aggregate(name: str, values: Sequence[ExerciseMetric], unit: str, missing: str) -> None:
        strata: dict[tuple[str, bool], list[float]] = {}
        for metric in values:
            if metric.valid:
                strata.setdefault((metric.evidence_label, metric.anatomical_eligible), []).append(metric.value)
        if not strata:
            statistics[name] = (MetricSummary(0, scalar(0, unit, missing), scalar(0, unit, missing)),)
            return
        summaries = []
        for (label, anatomical), samples in sorted(strata.items()):
            summaries.append(MetricSummary(len(samples),
                scalar(float(np.mean(samples)), unit, label=label, anatomical=anatomical),
                scalar(float(np.max(samples)), unit, label=label, anatomical=anatomical)))
        statistics[name] = tuple(summaries)

    for field in fields(RepetitionMetrics):
        values = [getattr(rep.metrics, field.name) for rep in eligible]
        # Units are determined by the metric contract even for a quiet window.
        unit = "rad/s" if "speed" in field.name else "rad" if field.name.endswith("_rad") else "s"
        aggregate(field.name, values, unit, "no_valid_repetitions")
    proxy_eligible = [rep for rep in proxy.repetitions if s.analysis_valid and rep.repetition.candidate.valid]
    proxy_count = sum(rep.extension.valid and rep.lateral_flexion.valid and rep.axial_rotation.valid
                      for rep in proxy_eligible)
    for component in ("extension", "lateral_flexion", "axial_rotation"):
        for quantity in ("min_rad", "max_rad", "magnitude_rad"):
            values = []
            for rep in proxy_eligible:
                item = getattr(rep, component)
                values.append(ExerciseMetric(getattr(item, quantity), item.valid, item.reason, item.unit,
                                             item.evidence_label, item.anatomical_eligible))
            aggregate(f"thorax_{component}_{quantity}", values, "rad", "no_valid_proxy")

    rom = [rep.metrics.rom_rad.value for rep in eligible]
    n = len(rom)
    rom_range = scalar(float(np.ptp(rom)) if n else 0, "rad", "ok" if n else "no_valid_repetitions")
    sd = float(np.std(rom, ddof=1)) if n >= 2 else 0
    rom_sd = scalar(sd, "rad", "ok" if n >= 2 else "insufficient_repetitions")
    mean = float(np.mean(rom)) if n else 0
    cv_reason = "insufficient_repetitions" if n < 2 else (
        "ok" if mean > s.configuration.cv_mean_floor_rad else "cv_mean_near_zero")
    rom_cv = scalar(sd / abs(mean) if cv_reason == "ok" else 0, "dimensionless", cv_reason)
    active_time = sum(rep.metrics.rep_duration_s.value for rep in eligible)
    active = scalar(active_time, "s", "ok" if s.analysis_valid else s.reasons[0])
    cadence = scalar(n / active_time if active_time > 0 else 0, "s^-1",
                     "ok" if active_time > 0 else "empty_active_time")
    exclusion: dict[str, list[int]] = {}
    for candidate in s.candidates:
        if not candidate.valid:
            for reason in candidate.reasons:
                exclusion.setdefault(reason, []).append(candidate.id)

    # Compare processing decisions and artifact identities, not recording hashes,
    # fitted offsets, per-session coverage windows or observed QC/drift values.
    def alignment_keys(alignment: AlignmentRecord | None) -> object:
        if alignment is None:
            return None
        return tuple((field.name, getattr(alignment, field.name)) for field in fields(alignment)
                     if field.name not in ("source_sha256", "epoch"))

    clocks = (relative.thorax_clock_map, relative.humerus_clock_map)
    heading = relative.heading_relation
    trace = proxy.trace
    keys: dict[str, object] = {
        "definition_version": (s.definition_version, e.definition_version, s.angular_speed_result.definition_version),
        "configuration": s.configuration,
        "side": s.side, "exercise": s.exercise,
        "protocol": (s.protocol_id, s.protocol_version),
        "frame_conventions": "active scalar-first Hamilton; thorax X anterior Y left Z superior; H +Z proximal",
        "calibration_ids": context.calibration_ids, "calibration_sha256": s.calibration_sha256,
        "alignment_sha256": context.alignment_sha256,
        "alignment": (alignment_keys(e.thorax_alignment), alignment_keys(e.humerus_alignment)),
        "clock_methods": tuple(None if clock is None else (clock.method, clock.status) for clock in clocks),
        "heading_method": None if heading is None else (heading.method, heading.status,
            heading.thorax_world_id, heading.humerus_world_id, heading.quaternion_thorax_world_humerus_world),
        "evidence_stratum": (s.evidence_label, s.anatomical_eligible),
        "timing_policy": (relative.interpolation, relative.max_interpolation_gap_us,
                          relative.max_timing_uncertainty_us),
        "proxy_policy": None if trace is None else (proxy.definition_version, trace.definition_version,
            trace.method_version, trace.interpolation,
            None if trace.heading_evidence is None else (trace.heading_evidence.method, trace.heading_evidence.status),
            None if trace.drift_evidence is None else (trace.drift_evidence.method, trace.drift_evidence.status)),
        "backend": context.backend, "grid_policy": context.grid_policy,
        "source_type": e.source_type, "source_generator": context.source_generator,
    }
    valid = s.analysis_valid
    return ExerciseSummary(
        result, context, valid, s.reasons, s.detected_count, s.valid_count, s.excluded_count,
        sum(c.partial_start for c in s.candidates) if valid else None,
        sum(c.partial_end for c in s.candidates) if valid else None,
        sum(c.interrupted for c in s.candidates) if valid else None,
        {reason: tuple(ids) for reason, ids in sorted(exclusion.items())},
        {reason: len(ids) for reason, ids in sorted(exclusion.items())},
        proxy_count if valid else None, n-proxy_count if valid else None, statistics,
        rom_range, rom_sd, rom_cv, active, cadence,
        scalar((s.analysis_window_us[1]-s.analysis_window_us[0])/1e6, "s", label="Observed", anatomical=False), keys,
    )


def compare_summaries(summaries: Sequence[ExerciseSummary]) -> tuple[SummaryComparison, ...]:
    """All chronological pairs of declared sets/sessions; incomparable pairs keep exact keys.

    No pooling or inferred time. UTC ties use session ID. Each difference is
    later arithmetic mean minus earlier arithmetic mean in SI, within stratum.
    """
    ordered: list[tuple[datetime, str, ExerciseSummary]] = []
    seen: set[str] = set()
    for summary in summaries:
        if not isinstance(summary, ExerciseSummary) or not _same_summary(
            summary, summarize_exercise(summary.input_result, context=summary.context)
        ):
            raise ValueError("comparison summary does not match its inputs")
        metrics = summary.input_result.metrics if isinstance(summary.input_result, ExerciseThoraxResult) \
            else summary.input_result
        identity = metrics.segmentation.session_id
        if identity in seen:
            raise ValueError("duplicate session ID in comparison")
        seen.add(identity)
        ordered.append((_utc(summary.context.session_start_utc), identity, summary))
    ordered.sort(key=lambda item: (item[0], item[1]))
    comparisons = []
    for index, (_, earlier_id, earlier) in enumerate(ordered):
        for _, later_id, later in ordered[index+1:]:
            differing = tuple(sorted(key for key in earlier.comparability_keys
                if not _same(earlier.comparability_keys[key], later.comparability_keys[key])))
            differences: dict[str, tuple[MetricDifference, ...]] | None = None
            if not differing:
                differences = {}
                for name, earlier_stats in earlier.statistics.items():
                    later_stats = later.statistics[name]
                    strata = sorted({(v.mean.evidence_label, v.mean.anatomical_eligible)
                                     for v in (*earlier_stats, *later_stats)})
                    items = []
                    for label, anatomical in strata:
                        a = next((v for v in earlier_stats if (v.mean.evidence_label, v.mean.anatomical_eligible)
                                  == (label, anatomical)), None)
                        b = next((v for v in later_stats if (v.mean.evidence_label, v.mean.anatomical_eligible)
                                  == (label, anatomical)), None)
                        valid = a is not None and b is not None and a.mean.valid and b.mean.valid
                        value = b.mean.value-a.mean.value if valid and a is not None and b is not None else float("nan")
                        items.append(MetricDifference(a.n if a else 0, b.n if b else 0,
                            ExerciseMetric(value, valid, "ok" if valid else "comparison_metric_unavailable",
                                           earlier_stats[0].mean.unit, label, valid and anatomical)))
                    differences[name] = tuple(items)
            comparisons.append(SummaryComparison(earlier_id, later_id, earlier, later,
                                                 not differing, differing, differences))
    return tuple(comparisons)
