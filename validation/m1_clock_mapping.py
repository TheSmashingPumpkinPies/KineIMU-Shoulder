"""Independent M1 clock mapping and held-out synchronization validation.

This module is validation-only.  It consumes an immutable event annotation
plan and raw-stream hashes; it does not capture BLE data, modify raw streams,
or resample samples.  The fitted model is, for every node and uninterrupted
clock epoch,

``t_common_us = a_i * t_device_us + b_i``.

The common event reference clock must be independent of BLE host arrival time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import cast

import numpy as np
from numpy.typing import NDArray

EVENT_PLAN_SCHEMA_VERSION = "kineimu.m1.sync-event-plan/0.1"
CLOCK_MAPPING_REPORT_SCHEMA_VERSION = "kineimu.m1.clock-mapping-validation/0.1"
CLOCK_MAPPING_METHOD_VERSION = "kineimu.m1.clock-mapping.ols-wls/0.1"

DEFAULT_P95_LIMIT_US = 1_000.0
DEFAULT_MAX_LIMIT_US = 1_500.0
THRESHOLD_SEPARATION_US = DEFAULT_MAX_LIMIT_US - DEFAULT_P95_LIMIT_US
DEFAULT_COVERAGE_FACTOR = 2.0
REQUIRED_NODES = ("A", "B")

FloatArray = NDArray[np.float64]


class EventPhase(StrEnum):
    """Required temporal placement of a fixture event."""

    BEGINNING = "beginning"
    MIDDLE = "middle"
    END = "end"


class EventRole(StrEnum):
    """Disjoint use of an event in fitting or held-out validation."""

    FIT = "fit"
    HELD_OUT = "held_out"


class ClockMappingValidationError(ValueError):
    """Raised when an event plan cannot support an auditable M1 result."""


@dataclass(frozen=True, slots=True)
class RawStreamInput:
    """Immutable raw-stream identity used by an event annotation plan."""

    node_id: str
    path: str
    sha256: str

    def __post_init__(self) -> None:
        _validate_node_id(self.node_id)
        if not self.path.strip():
            raise ClockMappingValidationError("raw stream path must not be empty")
        _validate_sha256(self.sha256, field="raw stream SHA-256")


@dataclass(frozen=True, slots=True)
class EventObservation:
    """One node-local localization of a repeated common fixture event."""

    node_id: str
    clock_epoch: int
    device_time_us: int
    localization_method: str
    localization_resolution_us: float
    localization_uncertainty_us: float
    raw_sha256: str
    sample_sequence: int | None = None

    def __post_init__(self) -> None:
        _validate_node_id(self.node_id)
        if isinstance(self.clock_epoch, bool) or not isinstance(self.clock_epoch, int) or self.clock_epoch < 0:
            raise ClockMappingValidationError("clock_epoch must be a non-negative integer")
        if isinstance(self.device_time_us, bool) or not isinstance(self.device_time_us, int) or self.device_time_us < 0:
            raise ClockMappingValidationError("device_time_us must be a non-negative integer")
        if not self.localization_method.strip():
            raise ClockMappingValidationError("localization_method must not be empty")
        _validate_nonnegative_finite(self.localization_resolution_us, "localization_resolution_us")
        _validate_nonnegative_finite(self.localization_uncertainty_us, "localization_uncertainty_us")
        _validate_sha256(self.raw_sha256, field="event observation raw SHA-256")
        if self.sample_sequence is not None and (
            isinstance(self.sample_sequence, bool)
            or not isinstance(self.sample_sequence, int)
            or self.sample_sequence < 0
        ):
            raise ClockMappingValidationError("sample_sequence must be a non-negative integer when present")


@dataclass(frozen=True, slots=True)
class CommonEvent:
    """A common event with one independent reference time and A/B observations."""

    event_id: str
    phase: EventPhase
    role: EventRole
    common_time_us: float
    reference_method: str
    reference_resolution_us: float
    reference_uncertainty_us: float
    observations: tuple[EventObservation, ...]

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ClockMappingValidationError("event_id must not be empty")
        try:
            object.__setattr__(self, "phase", EventPhase(self.phase))
            object.__setattr__(self, "role", EventRole(self.role))
        except ValueError as error:
            raise ClockMappingValidationError(f"unsupported event phase/role for {self.event_id}") from error
        _validate_nonnegative_finite(self.common_time_us, "common_time_us")
        if not self.reference_method.strip():
            raise ClockMappingValidationError(f"reference_method must not be empty for {self.event_id}")
        _validate_nonnegative_finite(self.reference_resolution_us, "reference_resolution_us")
        _validate_nonnegative_finite(self.reference_uncertainty_us, "reference_uncertainty_us")
        object.__setattr__(self, "observations", tuple(self.observations))


@dataclass(frozen=True, slots=True)
class EventPlan:
    """Versioned event annotations and raw-stream provenance for one session."""

    schema_version: str
    session_id: str
    method_version: str
    raw_streams: tuple[RawStreamInput, ...]
    events: tuple[CommonEvent, ...]
    fixture_id: str
    fixture_description: str

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ClockMappingValidationError("session_id must not be empty")
        if not self.method_version.strip():
            raise ClockMappingValidationError("method_version must not be empty")
        if not self.fixture_id.strip():
            raise ClockMappingValidationError("fixture_id must not be empty")
        if not self.fixture_description.strip():
            raise ClockMappingValidationError("fixture_description must not be empty")
        object.__setattr__(self, "raw_streams", tuple(self.raw_streams))
        object.__setattr__(self, "events", tuple(self.events))


@dataclass(frozen=True, slots=True)
class MappingEstimate:
    """One fitted mapping for exactly one node and one uninterrupted epoch."""

    node_id: str
    clock_epoch: int
    coefficient_a: float
    coefficient_b_us: float
    relative_drift_ppm: float
    fit_event_ids: tuple[str, ...]
    fit_window_device_us: tuple[int, int]
    fit_window_common_us: tuple[float, float]
    common_reference_us: float
    offset_us_at_common_reference: float
    coefficient_covariance: tuple[tuple[float, float], tuple[float, float]]
    fit_residuals_us: tuple[float, ...]
    fit_residual_rms_us: float


@dataclass(frozen=True, slots=True)
class ResidualStatistics:
    """Absolute residual distribution and its decision-relevant uncertainty."""

    event_ids: tuple[str, ...]
    residuals_us: tuple[float, ...]
    standard_uncertainties_us: tuple[float, ...]
    expanded_uncertainties_us: tuple[float, ...]
    event_resolution_us: tuple[float, ...]
    p50_us: float
    p95_us: float
    p99_us: float
    max_us: float
    coverage_factor: float
    max_standard_uncertainty_us: float
    max_expanded_uncertainty_us: float
    max_event_resolution_us: float
    decision_resolution_us: float
    threshold_separation_us: float
    resolution_sufficient: bool


@dataclass(frozen=True, slots=True)
class NodeHeldOutMetrics:
    """Held-out residuals for one node/epoch mapping."""

    node_id: str
    clock_epoch: int
    held_out: ResidualStatistics


@dataclass(frozen=True, slots=True)
class MappingPairSummary:
    """Relative A/B clock relation for one pair of node epochs."""

    node_a_epoch: int
    node_b_epoch: int
    common_event_ids: tuple[str, ...]
    relative_drift_ppm: float
    device_offset_b_minus_a_us_at_common_reference: float


@dataclass(frozen=True, slots=True)
class PairHeldOutMetrics:
    """Held-out pairwise timing residuals and relative clock summary."""

    held_out: ResidualStatistics
    relative_drift_ppm: float | None
    device_offset_b_minus_a_us_at_common_reference: float | None
    mapping_pairs: tuple[MappingPairSummary, ...]


@dataclass(frozen=True, slots=True)
class DecisionSummary:
    """Engineering decision against the predeclared M1 timing budget."""

    status: str
    reason: str
    p95_limit_us: float
    max_limit_us: float
    threshold_separation_us: float
    pair_p95_within_limit: bool
    pair_max_within_limit: bool
    resolution_sufficient: bool


@dataclass(frozen=True, slots=True)
class ClockMappingReport:
    """Complete serializable result of one independent held-out validation."""

    schema_version: str
    method_version: str
    session_id: str
    event_plan_schema_version: str
    fixture_id: str
    fixture_description: str
    raw_streams: tuple[RawStreamInput, ...]
    events: tuple[CommonEvent, ...]
    mappings: tuple[MappingEstimate, ...]
    node_results: tuple[NodeHeldOutMetrics, ...]
    pair: PairHeldOutMetrics
    decision: DecisionSummary
    fit_time_source: str = "device_time_us"
    host_arrival_used_for_fit: bool = False
    raw_hashes_verified: bool = False
    raw_data_modified: bool = False
    resampling: str = "none"

    @property
    def decision_status(self) -> str:
        """Return ``pass``, ``fail`` or ``inconclusive``."""

        return self.decision.status

    @property
    def fit_event_ids(self) -> tuple[str, ...]:
        """Return all unique event IDs used for fitting."""

        return tuple(event.event_id for event in self.events if event.role is EventRole.FIT)

    @property
    def held_out_event_ids(self) -> tuple[str, ...]:
        """Return all unique event IDs reserved for held-out validation."""

        return tuple(event.event_id for event in self.events if event.role is EventRole.HELD_OUT)

    def as_dict(self) -> dict[str, object]:
        """Serialize the result with all event and provenance fields retained."""

        return {
            "schema_version": self.schema_version,
            "method": {
                "version": self.method_version,
                "model": "t_common_us = a_i * t_device_us + b_i",
                "fit": "weighted least squares using declared event standard uncertainties",
                "quantile_method": "numpy.quantile(method='linear')",
                "coverage_factor": self.pair.held_out.coverage_factor,
            },
            "input": {
                "session_id": self.session_id,
                "event_plan_schema_version": self.event_plan_schema_version,
                "fixture_id": self.fixture_id,
                "fixture_description": self.fixture_description,
                "raw_streams": [_raw_stream_to_dict(stream) for stream in self.raw_streams],
                "raw_hashes_verified": self.raw_hashes_verified,
                "raw_data_modified": self.raw_data_modified,
                "fit_time_source": self.fit_time_source,
                "host_arrival_used_for_fit": self.host_arrival_used_for_fit,
            },
            "event_split": {
                "fit_event_ids": list(self.fit_event_ids),
                "held_out_event_ids": list(self.held_out_event_ids),
                "disjoint": not bool(set(self.fit_event_ids) & set(self.held_out_event_ids)),
            },
            "events": [_event_to_dict(event) for event in self.events],
            "mappings": [_mapping_to_dict(mapping) for mapping in self.mappings],
            "held_out": {
                "nodes": [_node_result_to_dict(result) for result in self.node_results],
                "pair": _pair_result_to_dict(self.pair),
            },
            "decision": _decision_to_dict(self.decision),
            "processing": {
                "resampling": self.resampling,
                "raw_streams_unchanged": not self.raw_data_modified,
            },
        }


def validate_event_plan(plan: EventPlan) -> None:
    """Validate event placement, provenance, and strict fit/held-out separation."""

    if plan.schema_version != EVENT_PLAN_SCHEMA_VERSION:
        raise ClockMappingValidationError(
            f"unsupported event-plan schema {plan.schema_version!r}; expected {EVENT_PLAN_SCHEMA_VERSION!r}"
        )
    if plan.method_version != CLOCK_MAPPING_METHOD_VERSION:
        raise ClockMappingValidationError(
            f"unsupported clock-mapping method version {plan.method_version!r}; "
            f"expected {CLOCK_MAPPING_METHOD_VERSION!r}"
        )
    raw_by_node: dict[str, RawStreamInput] = {}
    for stream in plan.raw_streams:
        if stream.node_id in raw_by_node:
            raise ClockMappingValidationError(f"duplicate raw stream for node {stream.node_id}")
        raw_by_node[stream.node_id] = stream
    if tuple(sorted(raw_by_node)) != REQUIRED_NODES:
        raise ClockMappingValidationError("event plan must contain exactly raw streams for nodes A and B")

    events_by_id: dict[str, CommonEvent] = {}
    fit_ids: set[str] = set()
    held_out_ids: set[str] = set()
    for event in plan.events:
        if event.event_id in events_by_id:
            raise ClockMappingValidationError(
                "fit and held-out event IDs must be disjoint; duplicate event ID "
                f"{event.event_id!r} was supplied"
            )
        events_by_id[event.event_id] = event
        (fit_ids if event.role is EventRole.FIT else held_out_ids).add(event.event_id)
        if len(event.observations) != len(REQUIRED_NODES):
            raise ClockMappingValidationError(
                f"event {event.event_id} must have exactly one observation for each of nodes A and B"
            )
        observations_by_node: dict[str, EventObservation] = {}
        for observation in event.observations:
            if observation.node_id in observations_by_node:
                raise ClockMappingValidationError(
                    f"event {event.event_id} has duplicate observation for node {observation.node_id}"
                )
            observations_by_node[observation.node_id] = observation
            if observation.raw_sha256 != raw_by_node[observation.node_id].sha256:
                raise ClockMappingValidationError(
                    f"event {event.event_id} node {observation.node_id} raw SHA-256 does not match its raw stream"
                )
        if tuple(sorted(observations_by_node)) != REQUIRED_NODES:
            raise ClockMappingValidationError(f"event {event.event_id} must contain observations for nodes A and B")

    if fit_ids & held_out_ids:
        raise ClockMappingValidationError("fit and held-out event IDs must be disjoint")
    if len(fit_ids) < 3:
        raise ClockMappingValidationError("at least three fit events are required")
    if len(held_out_ids) < 3:
        raise ClockMappingValidationError("at least three held-out events are required")
    for role, ids in ((EventRole.FIT, fit_ids), (EventRole.HELD_OUT, held_out_ids)):
        phases = {events_by_id[event_id].phase for event_id in ids}
        missing = [phase.value for phase in EventPhase if phase not in phases]
        if missing:
            raise ClockMappingValidationError(
                f"{role.value} events must cover beginning, middle and end; missing {missing}"
            )

    fit_by_node_epoch: dict[tuple[str, int], int] = defaultdict(int)
    held_out_by_node_epoch: dict[tuple[str, int], int] = defaultdict(int)
    for event in plan.events:
        counter = fit_by_node_epoch if event.role is EventRole.FIT else held_out_by_node_epoch
        for observation in event.observations:
            counter[(observation.node_id, observation.clock_epoch)] += 1
    for key, count in fit_by_node_epoch.items():
        if count < 2:
            raise ClockMappingValidationError(
                f"node {key[0]} clock_epoch {key[1]} has {count} fit events; at least two are required"
            )
        if held_out_by_node_epoch.get(key, 0) < 1:
            raise ClockMappingValidationError(
                f"node {key[0]} clock_epoch {key[1]} has no held-out event"
            )
    missing_fit = sorted(set(held_out_by_node_epoch) - set(fit_by_node_epoch))
    if missing_fit:
        raise ClockMappingValidationError(
            "held-out observations cannot be evaluated without fit events for node/clock_epoch "
            f"{missing_fit}"
        )


def analyze_clock_mapping(
    plan: EventPlan,
    *,
    p95_limit_us: float = DEFAULT_P95_LIMIT_US,
    max_limit_us: float = DEFAULT_MAX_LIMIT_US,
    threshold_separation_us: float = THRESHOLD_SEPARATION_US,
    coverage_factor: float = DEFAULT_COVERAGE_FACTOR,
) -> ClockMappingReport:
    """Fit independent node/epoch mappings and score only held-out events."""

    validate_event_plan(plan)
    for name, value in (
        ("p95_limit_us", p95_limit_us),
        ("max_limit_us", max_limit_us),
        ("threshold_separation_us", threshold_separation_us),
        ("coverage_factor", coverage_factor),
    ):
        if not math.isfinite(value) or value <= 0.0:
            raise ClockMappingValidationError(f"{name} must be finite and positive")
    if max_limit_us < p95_limit_us:
        raise ClockMappingValidationError("max_limit_us must be at least p95_limit_us")

    events_by_node_epoch: dict[tuple[str, int], list[tuple[CommonEvent, EventObservation]]] = defaultdict(list)
    for event in plan.events:
        for observation in event.observations:
            events_by_node_epoch[(observation.node_id, observation.clock_epoch)].append((event, observation))

    mappings: list[MappingEstimate] = []
    mapping_by_key: dict[tuple[str, int], MappingEstimate] = {}
    node_results: list[NodeHeldOutMetrics] = []
    for key in sorted(events_by_node_epoch):
        node_id, clock_epoch = key
        pairs = events_by_node_epoch[key]
        fit_pairs = [(event, observation) for event, observation in pairs if event.role is EventRole.FIT]
        held_out_pairs = [(event, observation) for event, observation in pairs if event.role is EventRole.HELD_OUT]
        mapping = _fit_mapping(node_id, clock_epoch, fit_pairs)
        mappings.append(mapping)
        mapping_by_key[key] = mapping
        stats = _score_node_held_out(mapping, held_out_pairs, coverage_factor, threshold_separation_us)
        node_results.append(NodeHeldOutMetrics(node_id=node_id, clock_epoch=clock_epoch, held_out=stats))

    pair = _score_pair_held_out(plan.events, mapping_by_key, coverage_factor, threshold_separation_us)
    resolution_sufficient = pair.held_out.resolution_sufficient
    p95_within = pair.held_out.p95_us <= p95_limit_us
    max_within = pair.held_out.max_us <= max_limit_us
    if not resolution_sufficient:
        decision = DecisionSummary(
            status="inconclusive",
            reason="event resolution/uncertainty cannot separate 1.0 ms and 1.5 ms limits",
            p95_limit_us=p95_limit_us,
            max_limit_us=max_limit_us,
            threshold_separation_us=threshold_separation_us,
            pair_p95_within_limit=p95_within,
            pair_max_within_limit=max_within,
            resolution_sufficient=False,
        )
    elif p95_within and max_within:
        decision = DecisionSummary(
            status="pass",
            reason="held-out pairwise residuals meet the predeclared M1 timing limits",
            p95_limit_us=p95_limit_us,
            max_limit_us=max_limit_us,
            threshold_separation_us=threshold_separation_us,
            pair_p95_within_limit=True,
            pair_max_within_limit=True,
            resolution_sufficient=True,
        )
    else:
        decision = DecisionSummary(
            status="fail",
            reason="held-out pairwise residuals exceed a predeclared M1 timing limit",
            p95_limit_us=p95_limit_us,
            max_limit_us=max_limit_us,
            threshold_separation_us=threshold_separation_us,
            pair_p95_within_limit=p95_within,
            pair_max_within_limit=max_within,
            resolution_sufficient=True,
        )

    return ClockMappingReport(
        schema_version=CLOCK_MAPPING_REPORT_SCHEMA_VERSION,
        method_version=plan.method_version,
        session_id=plan.session_id,
        event_plan_schema_version=plan.schema_version,
        fixture_id=plan.fixture_id,
        fixture_description=plan.fixture_description,
        raw_streams=plan.raw_streams,
        events=plan.events,
        mappings=tuple(mappings),
        node_results=tuple(node_results),
        pair=pair,
        decision=decision,
    )


def load_event_plan(path: Path, *, verify_raw_hashes: bool = False) -> EventPlan:
    """Load and validate a JSON event plan without modifying any input file."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ClockMappingValidationError(f"cannot read event plan {path}: {error}") from error
    plan = event_plan_from_dict(payload)
    validate_event_plan(plan)
    if verify_raw_hashes:
        for stream in plan.raw_streams:
            stream_path = Path(stream.path)
            if not stream_path.is_absolute():
                stream_path = path.parent / stream_path
            if not stream_path.is_file():
                raise ClockMappingValidationError(f"raw stream for node {stream.node_id} is missing: {stream_path}")
            actual = _sha256_file(stream_path)
            if actual != stream.sha256:
                raise ClockMappingValidationError(
                    f"raw SHA-256 mismatch for node {stream.node_id}: expected {stream.sha256}, got {actual}"
                )
    return plan


def event_plan_from_dict(payload: object) -> EventPlan:
    """Decode the versioned JSON event-plan representation."""

    root = _mapping(payload, "event plan")
    raw_streams = tuple(
        RawStreamInput(
            node_id=_required_string(item, "node_id"),
            path=_required_string(item, "path"),
            sha256=_required_string(item, "sha256"),
        )
        for item in _required_list(root, "raw_streams")
    )
    events: list[CommonEvent] = []
    for raw_event in _required_list(root, "events"):
        event = _mapping(raw_event, "event")
        observations = tuple(
            EventObservation(
                node_id=_required_string(item, "node_id"),
                clock_epoch=_required_int(item, "clock_epoch"),
                device_time_us=_required_int(item, "device_time_us"),
                localization_method=_required_string(item, "localization_method"),
                localization_resolution_us=_required_float(item, "localization_resolution_us"),
                localization_uncertainty_us=_required_float(item, "localization_uncertainty_us"),
                raw_sha256=_required_string(item, "raw_sha256"),
                sample_sequence=_optional_int(item, "sample_sequence"),
            )
            for item in _required_list(event, "observations")
        )
        events.append(
            CommonEvent(
                event_id=_required_string(event, "event_id"),
                phase=EventPhase(_required_string(event, "phase")),
                role=EventRole(_required_string(event, "role")),
                common_time_us=_required_float(event, "common_time_us"),
                reference_method=_required_string(event, "reference_method"),
                reference_resolution_us=_required_float(event, "reference_resolution_us"),
                reference_uncertainty_us=_required_float(event, "reference_uncertainty_us"),
                observations=observations,
            )
        )
    fixture = _mapping(root.get("fixture"), "fixture")
    return EventPlan(
        schema_version=_required_string(root, "schema_version"),
        session_id=_required_string(root, "session_id"),
        method_version=_required_string(root, "method_version"),
        raw_streams=raw_streams,
        events=tuple(events),
        fixture_id=_required_string(fixture, "id"),
        fixture_description=_required_string(fixture, "description"),
    )


def write_event_plan(plan: EventPlan, path: Path) -> None:
    """Write an event plan as a new JSON annotation artifact."""

    validate_event_plan(plan)
    path.write_text(json.dumps(event_plan_to_dict(plan), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def event_plan_to_dict(plan: EventPlan) -> dict[str, object]:
    """Serialize an event plan for reproducible annotation storage."""

    validate_event_plan(plan)
    return {
        "schema_version": plan.schema_version,
        "session_id": plan.session_id,
        "method_version": plan.method_version,
        "fixture": {"id": plan.fixture_id, "description": plan.fixture_description},
        "raw_streams": [_raw_stream_to_dict(stream) for stream in plan.raw_streams],
        "events": [_event_to_dict(event) for event in plan.events],
    }


def write_clock_mapping_report(
    plan: EventPlan,
    output_path: Path,
    *,
    event_plan_path: Path | None = None,
    command: str | None = None,
    repository_root: Path | None = None,
    verify_raw_hashes: bool = False,
) -> ClockMappingReport:
    """Analyze a plan and persist a processed report artifact."""

    if verify_raw_hashes:
        if event_plan_path is None:
            raise ClockMappingValidationError("event_plan_path is required when verify_raw_hashes is enabled")
        _verify_plan_raw_hashes(plan, event_plan_path)
    report = replace(analyze_clock_mapping(plan), raw_hashes_verified=verify_raw_hashes)
    payload = report.as_dict()
    reproducibility: dict[str, object] = {
        "event_plan_path": str(event_plan_path) if event_plan_path is not None else None,
        "event_plan_sha256": _sha256_file(event_plan_path) if event_plan_path is not None else None,
        "command": command,
        "python": sys.version,
        "software_commit": _git_head(repository_root or Path.cwd()),
        "raw_data_modified": False,
    }
    payload["reproducibility"] = reproducibility
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the validation CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-raw", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the standalone validation report command."""

    args = build_argument_parser().parse_args(argv)
    try:
        plan = load_event_plan(args.event_plan, verify_raw_hashes=args.verify_raw)
        report = write_clock_mapping_report(
            plan,
            args.output,
            event_plan_path=args.event_plan,
            command=" ".join(sys.argv),
            repository_root=Path.cwd(),
        )
    except (ClockMappingValidationError, OSError) as error:
        print(json.dumps({"error": str(error)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"output": str(args.output), "result": report.decision_status}, sort_keys=True))
    return 0 if report.decision_status == "pass" else 1


def _fit_mapping(
    node_id: str,
    clock_epoch: int,
    fit_pairs: Sequence[tuple[CommonEvent, EventObservation]],
) -> MappingEstimate:
    if len(fit_pairs) < 2:
        raise ClockMappingValidationError(f"node {node_id} clock_epoch {clock_epoch} needs at least two fit events")
    ordered = sorted(fit_pairs, key=lambda pair: pair[0].common_time_us)
    x_us = np.asarray([pair[1].device_time_us for pair in ordered], dtype=np.float64)
    y_us = np.asarray([pair[0].common_time_us for pair in ordered], dtype=np.float64)
    if np.ptp(x_us) <= 0.0:
        raise ClockMappingValidationError(f"node {node_id} clock_epoch {clock_epoch} fit device times are not distinct")
    # Convert protocol microseconds to SI seconds for the numerical fit and
    # scale the centered coordinate.  The report converts b/covariance back to
    # explicit microseconds; this avoids losing precision at large timer origins.
    x = x_us * 1e-6
    y = y_us * 1e-6
    x_center = float(np.mean(x, dtype=np.float64))
    x_scale = max(float(np.max(np.abs(x - x_center))), 1e-6)
    design = np.column_stack(((x - x_center) / x_scale, np.ones_like(x)))
    beta_ols, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    if rank < 2:
        raise ClockMappingValidationError(f"node {node_id} clock_epoch {clock_epoch} fit design is rank deficient")
    initial_a = float(beta_ols[0] / x_scale)
    combined_sigma = np.sqrt(
        np.asarray(
            [
                pair[0].reference_uncertainty_us**2
                + (abs(initial_a) * pair[1].localization_uncertainty_us) ** 2
                for pair in ordered
            ],
            dtype=np.float64,
        )
    )
    if bool(np.all(combined_sigma > 0.0)):
        combined_sigma_s = combined_sigma * 1e-6
        weighted_design = design / combined_sigma_s[:, None]
        weighted_y = y / combined_sigma_s
        beta, _, weighted_rank, _ = np.linalg.lstsq(weighted_design, weighted_y, rcond=None)
        if weighted_rank < 2:
            raise ClockMappingValidationError(
                f"node {node_id} clock_epoch {clock_epoch} weighted fit is rank deficient"
            )
        normal = design.T @ (design / (combined_sigma_s[:, None] ** 2))
        covariance_local = np.linalg.pinv(normal, hermitian=True)
    else:
        beta = beta_ols
        normal = design.T @ design
        covariance_local = np.linalg.pinv(normal, hermitian=True)
        residuals = y - design @ beta
        dof = len(y) - 2
        if dof > 0:
            covariance_local = covariance_local * (float(residuals @ residuals) / dof)
    coefficient_a = float(beta[0] / x_scale)
    if not math.isfinite(coefficient_a) or coefficient_a <= 0.0:
        raise ClockMappingValidationError(
            f"node {node_id} clock_epoch {clock_epoch} fitted slope must be positive, got {coefficient_a!r}"
        )
    centered_intercept = float(beta[1])
    coefficient_b_s = centered_intercept - coefficient_a * x_center
    # beta is [slope per scaled x, centered intercept] in seconds.  Transform
    # to [a, b_seconds], then to the reported [a, b_microseconds] basis.
    transform = np.asarray([[1.0 / x_scale, 0.0], [-x_center / x_scale, 1.0]], dtype=np.float64)
    covariance_ab_s = transform @ covariance_local @ transform.T
    unit_transform = np.diag(np.asarray([1.0, 1e6], dtype=np.float64))
    covariance_ab = unit_transform @ covariance_ab_s @ unit_transform.T
    coefficient_b_us = coefficient_b_s * 1e6
    predicted_us = coefficient_a * x_us + coefficient_b_us
    residuals_us = y_us - predicted_us
    common_reference_us = float(np.median(y_us))
    device_at_reference = (common_reference_us - coefficient_b_us) / coefficient_a
    return MappingEstimate(
        node_id=node_id,
        clock_epoch=clock_epoch,
        coefficient_a=coefficient_a,
        coefficient_b_us=coefficient_b_us,
        relative_drift_ppm=(coefficient_a - 1.0) * 1e6,
        fit_event_ids=tuple(pair[0].event_id for pair in ordered),
        fit_window_device_us=(int(np.min(x_us)), int(np.max(x_us))),
        fit_window_common_us=(float(np.min(y_us)), float(np.max(y_us))),
        common_reference_us=common_reference_us,
        offset_us_at_common_reference=common_reference_us - device_at_reference,
        coefficient_covariance=(
            (float(covariance_ab[0, 0]), float(covariance_ab[0, 1])),
            (float(covariance_ab[1, 0]), float(covariance_ab[1, 1])),
        ),
        fit_residuals_us=tuple(float(value) for value in residuals_us),
        fit_residual_rms_us=float(np.sqrt(np.mean(residuals_us**2))),
    )


def _score_node_held_out(
    mapping: MappingEstimate,
    held_out_pairs: Sequence[tuple[CommonEvent, EventObservation]],
    coverage_factor: float,
    threshold_separation_us: float,
) -> ResidualStatistics:
    ordered = sorted(held_out_pairs, key=lambda pair: pair[0].common_time_us)
    residuals: list[float] = []
    standard_uncertainties: list[float] = []
    resolutions: list[float] = []
    for event, observation in ordered:
        prediction = mapping.coefficient_a * observation.device_time_us + mapping.coefficient_b_us
        residuals.append(abs(prediction - event.common_time_us))
        standard_uncertainties.append(
            _prediction_uncertainty(mapping, observation, event, include_reference=True)
        )
        resolutions.append(
            math.hypot(event.reference_resolution_us, observation.localization_resolution_us)
        )
    return _residual_statistics(
        tuple(event.event_id for event, _ in ordered),
        residuals,
        standard_uncertainties,
        resolutions,
        coverage_factor,
        threshold_separation_us,
    )


def _score_pair_held_out(
    events: Sequence[CommonEvent],
    mappings: Mapping[tuple[str, int], MappingEstimate],
    coverage_factor: float,
    threshold_separation_us: float,
) -> PairHeldOutMetrics:
    held_out_events = sorted(
        (event for event in events if event.role is EventRole.HELD_OUT),
        key=lambda event: event.common_time_us,
    )
    by_node = {
        event.event_id: {observation.node_id: observation for observation in event.observations}
        for event in held_out_events
    }
    residuals: list[float] = []
    standard_uncertainties: list[float] = []
    resolutions: list[float] = []
    events_by_mapping_pair: dict[tuple[int, int], list[str]] = defaultdict(list)
    for event in held_out_events:
        observation_a = by_node[event.event_id]["A"]
        observation_b = by_node[event.event_id]["B"]
        mapping_a = mappings[("A", observation_a.clock_epoch)]
        mapping_b = mappings[("B", observation_b.clock_epoch)]
        prediction_a = mapping_a.coefficient_a * observation_a.device_time_us + mapping_a.coefficient_b_us
        prediction_b = mapping_b.coefficient_a * observation_b.device_time_us + mapping_b.coefficient_b_us
        residuals.append(abs(prediction_a - prediction_b))
        uncertainty_a = _prediction_uncertainty(mapping_a, observation_a, event, include_reference=False)
        uncertainty_b = _prediction_uncertainty(mapping_b, observation_b, event, include_reference=False)
        standard_uncertainties.append(math.hypot(uncertainty_a, uncertainty_b))
        resolutions.append(
            math.sqrt(
                event.reference_resolution_us**2
                + observation_a.localization_resolution_us**2
                + observation_b.localization_resolution_us**2
            )
        )
        events_by_mapping_pair[(mapping_a.clock_epoch, mapping_b.clock_epoch)].append(event.event_id)

    mapping_pairs: list[MappingPairSummary] = []
    for (epoch_a, epoch_b), event_ids in sorted(events_by_mapping_pair.items()):
        mapping_a = mappings[("A", epoch_a)]
        mapping_b = mappings[("B", epoch_b)]
        reference_time = float(
            np.median([event.common_time_us for event in held_out_events if event.event_id in event_ids])
        )
        device_a = (reference_time - mapping_a.coefficient_b_us) / mapping_a.coefficient_a
        device_b = (reference_time - mapping_b.coefficient_b_us) / mapping_b.coefficient_a
        mapping_pairs.append(
            MappingPairSummary(
                node_a_epoch=epoch_a,
                node_b_epoch=epoch_b,
                common_event_ids=tuple(event_ids),
                relative_drift_ppm=(mapping_b.coefficient_a / mapping_a.coefficient_a - 1.0) * 1e6,
                device_offset_b_minus_a_us_at_common_reference=device_b - device_a,
            )
        )
    stats = _residual_statistics(
        tuple(event.event_id for event in held_out_events),
        residuals,
        standard_uncertainties,
        resolutions,
        coverage_factor,
        threshold_separation_us,
    )
    if len(mapping_pairs) == 1:
        relative_drift = mapping_pairs[0].relative_drift_ppm
        offset = mapping_pairs[0].device_offset_b_minus_a_us_at_common_reference
    else:
        relative_drift = None
        offset = None
    return PairHeldOutMetrics(
        held_out=stats,
        relative_drift_ppm=relative_drift,
        device_offset_b_minus_a_us_at_common_reference=offset,
        mapping_pairs=tuple(mapping_pairs),
    )


def _prediction_uncertainty(
    mapping: MappingEstimate,
    observation: EventObservation,
    event: CommonEvent,
    *,
    include_reference: bool,
) -> float:
    # coefficient_covariance is stored in the uncentered [a, b] basis even
    # though fitting is numerically centered, so propagate at the actual x.
    vector = np.asarray([observation.device_time_us, 1.0], dtype=np.float64)
    covariance = np.asarray(mapping.coefficient_covariance, dtype=np.float64)
    fit_variance = float(vector @ covariance @ vector)
    fit_variance = max(0.0, fit_variance)
    variance = fit_variance + (mapping.coefficient_a * observation.localization_uncertainty_us) ** 2
    if include_reference:
        variance += event.reference_uncertainty_us**2
    return math.sqrt(max(0.0, variance))


def _residual_statistics(
    event_ids: tuple[str, ...],
    residuals: Sequence[float],
    standard_uncertainties: Sequence[float],
    resolutions: Sequence[float],
    coverage_factor: float,
    threshold_separation_us: float,
) -> ResidualStatistics:
    if not residuals:
        raise ClockMappingValidationError("at least one held-out residual is required")
    values = np.asarray(residuals, dtype=np.float64)
    standard = np.asarray(standard_uncertainties, dtype=np.float64)
    resolution = np.asarray(resolutions, dtype=np.float64)
    expanded = coverage_factor * standard
    max_standard = float(np.max(standard))
    max_expanded = float(np.max(expanded))
    max_resolution = float(np.max(resolution))
    decision_resolution = max(max_expanded, max_resolution)
    return ResidualStatistics(
        event_ids=event_ids,
        residuals_us=tuple(float(value) for value in values),
        standard_uncertainties_us=tuple(float(value) for value in standard),
        expanded_uncertainties_us=tuple(float(value) for value in expanded),
        event_resolution_us=tuple(float(value) for value in resolution),
        p50_us=float(np.quantile(values, 0.50, method="linear")),
        p95_us=float(np.quantile(values, 0.95, method="linear")),
        p99_us=float(np.quantile(values, 0.99, method="linear")),
        max_us=float(np.max(values)),
        coverage_factor=coverage_factor,
        max_standard_uncertainty_us=max_standard,
        max_expanded_uncertainty_us=max_expanded,
        max_event_resolution_us=max_resolution,
        decision_resolution_us=decision_resolution,
        threshold_separation_us=threshold_separation_us,
        resolution_sufficient=decision_resolution < threshold_separation_us,
    )


def _raw_stream_to_dict(stream: RawStreamInput) -> dict[str, object]:
    return {"node_id": stream.node_id, "path": stream.path, "sha256": stream.sha256}


def _event_to_dict(event: CommonEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "phase": event.phase.value,
        "role": event.role.value,
        "common_time_us": event.common_time_us,
        "reference_method": event.reference_method,
        "reference_resolution_us": event.reference_resolution_us,
        "reference_uncertainty_us": event.reference_uncertainty_us,
        "observations": [
            {
                "node_id": observation.node_id,
                "clock_epoch": observation.clock_epoch,
                "device_time_us": observation.device_time_us,
                "localization_method": observation.localization_method,
                "localization_resolution_us": observation.localization_resolution_us,
                "localization_uncertainty_us": observation.localization_uncertainty_us,
                "raw_sha256": observation.raw_sha256,
                "sample_sequence": observation.sample_sequence,
            }
            for observation in event.observations
        ],
    }


def _mapping_to_dict(mapping: MappingEstimate) -> dict[str, object]:
    return {
        "node_id": mapping.node_id,
        "clock_epoch": mapping.clock_epoch,
        "model": "t_common_us = a_i * t_device_us + b_i",
        "coefficient_a": mapping.coefficient_a,
        "coefficient_b_us": mapping.coefficient_b_us,
        "relative_drift_ppm": mapping.relative_drift_ppm,
        "offset_us_at_common_reference": mapping.offset_us_at_common_reference,
        "common_reference_us": mapping.common_reference_us,
        "fit_event_ids": list(mapping.fit_event_ids),
        "fit_window_device_us": list(mapping.fit_window_device_us),
        "fit_window_common_us": list(mapping.fit_window_common_us),
        "coefficient_covariance": [list(row) for row in mapping.coefficient_covariance],
        "fit_residuals_us": list(mapping.fit_residuals_us),
        "fit_residual_rms_us": mapping.fit_residual_rms_us,
    }


def _residual_statistics_to_dict(stats: ResidualStatistics) -> dict[str, object]:
    return {
        "event_ids": list(stats.event_ids),
        "residuals_us": list(stats.residuals_us),
        "p50_us": stats.p50_us,
        "p95_us": stats.p95_us,
        "p99_us": stats.p99_us,
        "max_us": stats.max_us,
        "standard_uncertainties_us": list(stats.standard_uncertainties_us),
        "expanded_uncertainties_us": list(stats.expanded_uncertainties_us),
        "event_resolution_us": list(stats.event_resolution_us),
        "coverage_factor": stats.coverage_factor,
        "max_standard_uncertainty_us": stats.max_standard_uncertainty_us,
        "max_expanded_uncertainty_us": stats.max_expanded_uncertainty_us,
        "max_event_resolution_us": stats.max_event_resolution_us,
        "decision_resolution_us": stats.decision_resolution_us,
        "threshold_separation_us": stats.threshold_separation_us,
        "resolution_sufficient": stats.resolution_sufficient,
    }


def _node_result_to_dict(result: NodeHeldOutMetrics) -> dict[str, object]:
    return {
        "node_id": result.node_id,
        "clock_epoch": result.clock_epoch,
        "held_out": _residual_statistics_to_dict(result.held_out),
    }


def _pair_result_to_dict(result: PairHeldOutMetrics) -> dict[str, object]:
    return {
        "relative_drift_ppm": result.relative_drift_ppm,
        "device_offset_b_minus_a_us_at_common_reference": result.device_offset_b_minus_a_us_at_common_reference,
        "mapping_pairs": [
            {
                "node_a_epoch": pair.node_a_epoch,
                "node_b_epoch": pair.node_b_epoch,
                "common_event_ids": list(pair.common_event_ids),
                "relative_drift_ppm": pair.relative_drift_ppm,
                "device_offset_b_minus_a_us_at_common_reference": pair.device_offset_b_minus_a_us_at_common_reference,
            }
            for pair in result.mapping_pairs
        ],
        "held_out": _residual_statistics_to_dict(result.held_out),
    }


def _decision_to_dict(decision: DecisionSummary) -> dict[str, object]:
    return {
        "status": decision.status,
        "reason": decision.reason,
        "p95_limit_us": decision.p95_limit_us,
        "max_limit_us": decision.max_limit_us,
        "threshold_separation_us": decision.threshold_separation_us,
        "pair_p95_within_limit": decision.pair_p95_within_limit,
        "pair_max_within_limit": decision.pair_max_within_limit,
        "resolution_sufficient": decision.resolution_sufficient,
    }


def _verify_plan_raw_hashes(plan: EventPlan, event_plan_path: Path) -> None:
    for stream in plan.raw_streams:
        stream_path = Path(stream.path)
        if not stream_path.is_absolute():
            stream_path = event_plan_path.parent / stream_path
        if not stream_path.is_file():
            raise ClockMappingValidationError(f"raw stream for node {stream.node_id} is missing: {stream_path}")
        actual = _sha256_file(stream_path)
        if actual != stream.sha256:
            raise ClockMappingValidationError(
                f"raw SHA-256 mismatch for node {stream.node_id}: expected {stream.sha256}, got {actual}"
            )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"
    return completed.stdout.strip()


def _validate_node_id(node_id: str) -> None:
    if node_id not in REQUIRED_NODES:
        raise ClockMappingValidationError(f"unsupported node_id {node_id!r}; expected A or B")


def _validate_sha256(value: str, *, field: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ClockMappingValidationError(f"{field} must be 64 lowercase hexadecimal characters")


def _validate_nonnegative_finite(value: float, field: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or value < 0.0:
        raise ClockMappingValidationError(f"{field} must be finite and non-negative")


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ClockMappingValidationError(f"{field} must be a JSON object")
    return cast(dict[str, object], value)


def _required_list(mapping: Mapping[str, object], key: str) -> list[dict[str, object]]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise ClockMappingValidationError(f"{key} must be a JSON array")
    return [_mapping(item, key) for item in value]


def _required_string(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ClockMappingValidationError(f"{key} must be a non-empty string")
    return value


def _required_int(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ClockMappingValidationError(f"{key} must be an integer")
    return value


def _optional_int(mapping: Mapping[str, object], key: str) -> int | None:
    value = mapping.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ClockMappingValidationError(f"{key} must be an integer or null")
    return value


def _required_float(mapping: Mapping[str, object], key: str) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClockMappingValidationError(f"{key} must be numeric")
    return float(value)


if __name__ == "__main__":
    raise SystemExit(main())
