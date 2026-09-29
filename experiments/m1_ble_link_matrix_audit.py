"""Audit the closed-loop M1 BLE link matrix without changing raw captures."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from experiments.m1_transport_audit import _parse_cdc
from kineimu_shoulder.io.m1_packet import NodeId
from kineimu_shoulder.io.m1_qc import audit_capture_stream

JSON = dict[str, Any]
AGE_BUCKETS_US = (
    (0, 1_000),
    (1_000, 2_500),
    (2_500, 5_000),
    (5_000, 10_000),
    (10_000, 25_000),
    (25_000, 50_000),
    (50_000, 100_000),
    (100_000, None),
)
AGE_BUCKET_LABELS = (
    "<1 ms",
    "1–<2.5 ms",
    "2.5–<5 ms",
    "5–<10 ms",
    "10–<25 ms",
    "25–<50 ms",
    "50–<100 ms",
    "≥100 ms",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> JSON:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return cast(JSON, value)


def _read_ndjson(path: Path) -> list[JSON]:
    if not path.is_file():
        return []
    records: list[JSON] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        records.append(cast(JSON, value))
    return records


def summarize_callback_durations(durations_ns: Sequence[int]) -> dict[str, int | None]:
    """Summarize callback wall time with deterministic nearest-rank quantiles."""

    values = sorted(int(value) for value in durations_ns)
    if not values:
        return {
            "count": 0,
            "min_ns": None,
            "max_ns": None,
            "mean_ns": None,
            "p50_ns": None,
            "p95_ns": None,
        }

    def nearest_rank(probability: float) -> int:
        return values[max(0, math.ceil(probability * len(values)) - 1)]

    return {
        "count": len(values),
        "min_ns": values[0],
        "max_ns": values[-1],
        "mean_ns": sum(values) // len(values),
        "p50_ns": nearest_rank(0.50),
        "p95_ns": nearest_rank(0.95),
    }


def _int_field(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _latest_link_snapshot(cdc: JSON) -> JSON | None:
    snapshots = cdc.get("link_snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        return None
    latest = snapshots[-1]
    return cast(JSON, latest) if isinstance(latest, dict) else None


def _latest_trace_snapshot(cdc: JSON) -> JSON | None:
    snapshots = cdc.get("trace_snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        return None
    latest = snapshots[-1]
    return cast(JSON, latest) if isinstance(latest, dict) else None


def _snapshot_fields(snapshot: JSON) -> JSON:
    fields = snapshot.get("fields")
    return cast(JSON, fields) if isinstance(fields, dict) else {}


def _counter_delta(initial: JSON, final: JSON, name: str, *, enough_snapshots: bool) -> int | None:
    if not enough_snapshots:
        return None
    initial_value = _int_field(initial.get(name))
    final_value = _int_field(final.get(name))
    if (
        initial_value is None
        or final_value is None
        or initial_value < 0
        or final_value < initial_value
    ):
        return None
    return final_value - initial_value


def _nested_counter_delta(
    initial: JSON,
    final: JSON,
    name: str,
    component: str,
    *,
    enough_snapshots: bool,
) -> int | None:
    initial_group = initial.get(name)
    final_group = final.get(name)
    if not isinstance(initial_group, dict) or not isinstance(final_group, dict):
        return None
    return _counter_delta(
        cast(JSON, initial_group),
        cast(JSON, final_group),
        component,
        enough_snapshots=enough_snapshots,
    )


def _age_bucket(bins: object, count: int | None, probability: float) -> JSON | None:
    if not isinstance(bins, list) or count is None or count <= 0:
        return None
    values = [_int_field(value) for value in bins]
    if len(values) != len(AGE_BUCKETS_US) or any(value is None or value < 0 for value in values):
        return None
    rank = math.ceil(probability * count)
    cumulative = 0
    for index, value in enumerate(values):
        cumulative += cast(int, value)
        if cumulative >= rank:
            lower, upper = AGE_BUCKETS_US[index]
            return {
                "index": index,
                "label": AGE_BUCKET_LABELS[index],
                "lower_us": lower,
                "upper_us": upper,
            }
    return None


def _return_code_deltas(
    initial: JSON,
    final: JSON,
    *,
    enough_snapshots: bool,
    submit_attempts: int | None,
) -> JSON:
    initial_counts = initial.get("return_counts")
    final_counts = final.get("return_counts")
    initial_errors = initial.get("parse_errors", [])
    final_errors = final.get("parse_errors", [])
    count_parse_ok = (
        isinstance(initial_counts, dict)
        and isinstance(final_counts, dict)
        and not any("return_counts" in str(error) or "return code count" in str(error)
                    for error in (*initial_errors, *final_errors)
        )
    )
    if not enough_snapshots or not count_parse_ok:
        return {
            "exact_delta_by_code": None,
            "categories": None,
            "count_reconciles_with_submit_attempts": None,
        }

    first = cast(JSON, initial_counts)
    last = cast(JSON, final_counts)
    deltas: dict[str, int] = {}
    for code in sorted(set(first) | set(last), key=lambda value: int(str(value))):
        first_value = _int_field(first.get(code))
        last_value = _int_field(last.get(code))
        if first_value is None:
            first_value = 0
        if last_value is None:
            if code in first:
                return {
                    "exact_delta_by_code": None,
                    "categories": None,
                    "count_reconciles_with_submit_attempts": None,
                }
            last_value = 0
        if last_value < first_value:
            return {
                "exact_delta_by_code": None,
                "categories": None,
                "count_reconciles_with_submit_attempts": None,
            }
        deltas[str(code)] = last_value - first_value

    categories = {
        "accepted": 0,
        "enomem": 0,
        "eagain": 0,
        "other_negative": 0,
        "unexpected_positive": 0,
    }
    for raw_code, count in deltas.items():
        code = int(raw_code)
        if code == 0:
            category = "accepted"
        elif code == -errno.ENOMEM:
            category = "enomem"
        elif code == -errno.EAGAIN:
            category = "eagain"
        elif code < 0:
            category = "other_negative"
        else:
            category = "unexpected_positive"
        categories[category] += count

    return {
        "exact_delta_by_code": deltas,
        "categories": categories,
        "count_reconciles_with_submit_attempts": (
            sum(deltas.values()) == submit_attempts if submit_attempts is not None else None
        ),
    }


def _completion_age_summary(
    initial: JSON,
    final: JSON,
    *,
    enough_snapshots: bool,
) -> JSON:
    count = _counter_delta(initial, final, "age_count", enough_snapshots=enough_snapshots)
    initial_age = initial.get("age_us")
    final_age = final.get("age_us")
    if isinstance(initial_age, dict) and isinstance(final_age, dict):
        total_us = _counter_delta(
            cast(JSON, initial_age), cast(JSON, final_age), "total", enough_snapshots=enough_snapshots
        )
        last_us = _int_field(final_age.get("last")) if count is not None and count > 0 else None
    else:
        total_us = None
        last_us = None

    initial_bins = initial.get("age_bins")
    final_bins = final.get("age_bins")
    bins: list[int] | None = None
    if (
        enough_snapshots
        and isinstance(initial_bins, list)
        and isinstance(final_bins, list)
        and len(initial_bins) == len(AGE_BUCKETS_US)
        and len(final_bins) == len(AGE_BUCKETS_US)
    ):
        initial_values = [_int_field(value) for value in initial_bins]
        final_values = [_int_field(value) for value in final_bins]
        if all(value is not None for value in (*initial_values, *final_values)):
            differences = [
                cast(int, last) - cast(int, first)
                for first, last in zip(initial_values, final_values, strict=True)
            ]
            if all(value >= 0 for value in differences):
                bins = differences

    mean_us = total_us / count if total_us is not None and count is not None and count > 0 else None
    occupied_bins = [index for index, value in enumerate(bins or []) if value > 0]
    return {
        "count": count,
        "last_us": last_us,
        "total_us": total_us,
        "mean_us": mean_us,
        "bins": bins,
        "histogram_count_matches": (
            sum(bins) == count if bins is not None and count is not None else None
        ),
        "minimum_occupied_bucket": (
            _age_bucket([1 if index == occupied_bins[0] else 0 for index in range(8)], 1, 1.0)
            if occupied_bins
            else None
        ),
        "maximum_occupied_bucket": (
            _age_bucket([1 if index == occupied_bins[-1] else 0 for index in range(8)], 1, 1.0)
            if occupied_bins
            else None
        ),
        "p50_bucket": _age_bucket(bins, count, 0.50),
        "p95_bucket": _age_bucket(bins, count, 0.95),
    }


def _tx_diag_segment(snapshots: list[JSON], segment_index: int) -> JSON:
    first_snapshot = snapshots[0]
    final_snapshot = snapshots[-1]
    initial = _snapshot_fields(first_snapshot)
    final = _snapshot_fields(final_snapshot)
    enough_snapshots = len(snapshots) >= 2
    saturated = any(_int_field(_snapshot_fields(snapshot).get("saturated")) == 1 for snapshot in snapshots)
    parse_errors = [
        error
        for snapshot in snapshots
        for error in cast(list[str], snapshot.get("parse_errors", []))
    ]
    delta_quality = (
        "insufficient_snapshots"
        if not enough_snapshots
        else "lower_bound"
        if saturated
        else "incomplete_snapshot"
        if parse_errors
        else "exact"
    )
    counters = {
        name: _counter_delta(initial, final, name, enough_snapshots=enough_snapshots)
        for name in (
            "calls",
            "accepted",
            "final_fail",
            "packet_drops",
            "enomem",
            "eagain",
            "retries",
            "window_full",
            "wait_us",
            "completed",
            "cancelled",
            "callbacks_stale",
            "callbacks_cancelled",
            "callbacks_unexpected",
            "age_count",
        )
    }
    schedule_failures = {
        kind: _nested_counter_delta(
            initial,
            final,
            "schedule_fail",
            kind,
            enough_snapshots=enough_snapshots,
        )
        for kind in ("initial", "retry")
    }
    code_deltas = _return_code_deltas(
        {**initial, "parse_errors": first_snapshot.get("parse_errors", [])},
        {**final, "parse_errors": final_snapshot.get("parse_errors", [])},
        enough_snapshots=enough_snapshots,
        submit_attempts=counters["calls"],
    )
    current_values = []
    for snapshot in snapshots:
        inflight = _snapshot_fields(snapshot).get("inflight")
        current_values.append(
            _int_field(inflight.get("current")) if isinstance(inflight, dict) else None
        )
    observed_current = [value for value in current_values if value is not None]
    first_inflight = initial.get("inflight")
    final_inflight = final.get("inflight")
    boot_peak_start = (
        _int_field(first_inflight.get("boot_peak")) if isinstance(first_inflight, dict) else None
    )
    boot_peak_end = (
        _int_field(final_inflight.get("boot_peak")) if isinstance(final_inflight, dict) else None
    )
    run_peak_value = (
        boot_peak_end
        if enough_snapshots
        and not saturated
        and boot_peak_start is not None
        and boot_peak_end is not None
        and boot_peak_end > boot_peak_start
        else None
    )
    return {
        "segment_index": segment_index,
        "boot_id": initial.get("boot_id"),
        "generation": initial.get("generation"),
        "first_line": first_snapshot.get("line"),
        "last_line": final_snapshot.get("line"),
        "snapshot_count": len(snapshots),
        "parse_errors": parse_errors,
        "delta_quality": delta_quality,
        "submit_attempts": counters["calls"],
        "accepted": counters["accepted"],
        "final_failures": counters["final_fail"],
        "packet_drops": counters["packet_drops"],
        "return_codes": code_deltas,
        "retries": {
            "actual_attempts": counters["retries"],
            "transient_returns": {
                "enomem": counters["enomem"],
                "eagain": counters["eagain"],
            },
            "schedule_failures": schedule_failures,
            "last_schedule_return_codes": final.get("schedule_last"),
        },
        "lifecycle": {
            "completed": counters["completed"],
            "cancelled": counters["cancelled"],
            "stale_callbacks": counters["callbacks_stale"],
            "callbacks_after_cancel": counters["callbacks_cancelled"],
            "unexpected_callbacks": counters["callbacks_unexpected"],
        },
        "in_flight": {
            "initial_current": (
                _int_field(first_inflight.get("current"))
                if isinstance(first_inflight, dict)
                else None
            ),
            "final_current": (
                _int_field(final_inflight.get("current"))
                if isinstance(final_inflight, dict)
                else None
            ),
            "observed_peak_current": max(observed_current) if observed_current else None,
            "boot_peak_start": boot_peak_start,
            "boot_peak_end": boot_peak_end,
            "run_peak_value": run_peak_value,
            "run_peak_basis": (
                "boot_peak_advanced_during_segment" if run_peak_value is not None else "not_exactly_observable"
            ),
        },
        "completion_window": {
            "full_count": counters["window_full"],
            "wait_total_us": counters["wait_us"],
        },
        "completion_age": _completion_age_summary(
            initial,
            final,
            enough_snapshots=enough_snapshots,
        ),
        "saturated": saturated,
    }


def _tx_diagnostics_summary(cdc: JSON) -> JSON:
    raw_snapshots = cdc.get("tx_diag_snapshots")
    snapshots = (
        [cast(JSON, snapshot) for snapshot in raw_snapshots if isinstance(snapshot, dict)]
        if isinstance(raw_snapshots, list)
        else []
    )
    groups: list[list[JSON]] = []
    current_key: tuple[object, object] | None = None
    for snapshot in snapshots:
        fields = _snapshot_fields(snapshot)
        boot_id = _int_field(fields.get("boot_id"))
        generation = _int_field(fields.get("generation"))
        key = (boot_id, generation)
        if boot_id is None or generation is None:
            key = (boot_id, (generation, snapshot.get("line")))
        if not groups or key != current_key:
            groups.append([])
            current_key = key
        groups[-1].append(snapshot)
    segments = [_tx_diag_segment(group, index) for index, group in enumerate(groups, start=1)]
    return {
        "available": bool(snapshots),
        "status": "available" if snapshots else "not_recorded_legacy_cdc",
        "snapshot_count": len(snapshots),
        "segment_count": len(segments),
        "split_on": ["boot_id", "generation"],
        "segments": segments,
    }


def _queue_drop_summary(cdc: JSON) -> JSON:
    raw_deltas = cdc.get("trace_deltas_first_to_last")
    deltas = cast(JSON, raw_deltas) if isinstance(raw_deltas, dict) else {}
    return {
        "snapshot_count": cdc.get("trace_snapshot_count", 0),
        "quality": cdc.get("trace_delta_quality", "unavailable"),
        "deltas": {
            "enqueue": deltas.get("tx_enqueue_drops"),
            "disconnect": deltas.get("tx_disconnect_drops"),
            "stop": deltas.get("tx_stop_drops"),
        },
    }


def _actual_connection_parameters(cdc: JSON) -> JSON:
    snapshots = cdc.get("link_snapshots")
    valid_snapshots = (
        [cast(JSON, snapshot) for snapshot in snapshots if isinstance(snapshot, dict)]
        if isinstance(snapshots, list)
        else []
    )
    selected: JSON | None = None
    for snapshot in reversed(valid_snapshots):
        fields = _snapshot_fields(snapshot)
        if _int_field(fields.get("info_rc")) == 0 and (_int_field(fields.get("interval_us")) or 0) > 0:
            selected = snapshot
            break
    if selected is None and valid_snapshots:
        selected = valid_snapshots[-1]
    fields = _snapshot_fields(selected) if selected is not None else {}
    parameter_names = (
        "interval_us",
        "latency",
        "supervision_timeout_us",
        "phy_valid",
        "phy_tx",
        "phy_rx",
        "dle_valid",
        "dle_tx_max_len",
        "dle_tx_max_time_us",
        "dle_rx_max_len",
        "dle_rx_max_time_us",
    )
    return {
        "event": selected.get("event") if selected is not None else None,
        "info_rc": fields.get("info_rc"),
        **{name: fields.get(name) for name in parameter_names},
    }


def _capture_quality_summary(run_dir: Path, node_name: str, events: list[JSON]) -> JSON:
    node_key = node_name.lower()
    events_path = run_dir / "raw" / f"node-{node_key}.events.ndjson"
    raw_path = run_dir / "raw" / f"node-{node_key}.kimu"
    decode_events = [
        event
        for event in events
        if event.get("event") == "decode_error" or event.get("decode_ok") is False
    ]
    crc_events = [event for event in events if event.get("crc_ok") is False]
    raw_qc: JSON | None = None
    raw_unchanged: bool | None = None
    raw_hash: str | None = None
    raw_crc_errors: int | None = None
    if raw_path.is_file():
        raw_hash_before = _sha256(raw_path)
        with raw_path.open("rb") as stream:
            report = audit_capture_stream(stream, expected_node_id=NodeId[node_name])
        raw_hash_after = _sha256(raw_path)
        raw_hash = raw_hash_after
        raw_unchanged = raw_hash_before == raw_hash_after
        raw_crc_errors = sum("CRC-32C mismatch" in issue.detail for issue in report.issues)
        raw_qc = {
            "records_seen": report.records_seen,
            "packets_decoded": report.packets_decoded,
            "decode_errors": report.decode_errors,
            "framing_errors": report.framing_errors,
            "node_mismatches": report.node_mismatches,
        }

    event_sidecar_available = events_path.is_file()
    event_decode_errors = len(decode_events) if event_sidecar_available else None
    event_crc_errors = len(crc_events) if event_sidecar_available else None
    if event_decode_errors is None:
        decode_errors = raw_qc.get("decode_errors") if raw_qc is not None else None
    else:
        decode_errors = event_decode_errors
    if event_crc_errors is None:
        crc_errors = raw_crc_errors
    else:
        crc_errors = event_crc_errors
    return {
        "available": event_sidecar_available or raw_qc is not None,
        "event_sidecar_available": event_sidecar_available,
        "raw_qc_available": raw_qc is not None,
        "crc_errors": crc_errors,
        "event_crc_errors": event_crc_errors,
        "raw_crc_errors": raw_crc_errors,
        "decode_errors": decode_errors,
        "event_decode_errors": event_decode_errors,
        "raw_decode_errors": raw_qc.get("decode_errors") if raw_qc is not None else None,
        "framing_errors": raw_qc.get("framing_errors") if raw_qc is not None else None,
        "raw_qc": raw_qc,
        "raw_sha256": raw_hash,
        "raw_unchanged_during_audit": raw_unchanged,
    }


def _setup_error_summary(run_result: JSON, control_events: list[JSON]) -> JSON:
    attempts: dict[str, int] = {}
    returns: dict[str, int] = {}
    cdc_errors: list[JSON] = []
    for event in control_events:
        event_type = event.get("event")
        node_name = event.get("node")
        if event_type in {"ble_connect_call", "ble_connect_return"} and node_name in {"A", "B"}:
            destination = attempts if event_type == "ble_connect_call" else returns
            destination[str(node_name)] = destination.get(str(node_name), 0) + 1
        if event_type == "cdc_error":
            cdc_errors.append({"label": event.get("label"), "detail": event.get("detail")})

    cdc_metadata = run_result.get("cdc")
    if isinstance(cdc_metadata, dict):
        for label, metadata in cdc_metadata.items():
            if isinstance(metadata, dict) and metadata.get("error"):
                entry = {"label": label, "detail": metadata.get("error")}
                if entry not in cdc_errors:
                    cdc_errors.append(entry)
    connect_failures = {
        node_name: attempts.get(node_name, 0) - returns.get(node_name, 0)
        for node_name in ("A", "B")
        if attempts.get(node_name, 0) > returns.get(node_name, 0)
    }
    run_error = run_result.get("error")
    error_observations = sum(connect_failures.values()) + len(cdc_errors) + int(bool(run_error))
    return {
        "run_error": run_error,
        "ble_connect_attempts_by_node": attempts,
        "ble_connect_returns_by_node": returns,
        "ble_connect_failures_by_node": connect_failures,
        "cdc_capture_errors": cdc_errors,
        "error_observation_count": error_observations,
        "has_errors": error_observations > 0,
    }


def _node_audit(run_dir: Path, node_name: str, run_config: JSON, run_result: JSON) -> JSON:
    node_key = node_name.lower()
    cdc_meta_value = run_result.get("cdc", {})
    cdc_meta: JSON = {}
    if isinstance(cdc_meta_value, dict):
        for candidate_key in (node_name, f"node-{node_key}"):
            candidate = cdc_meta_value.get(candidate_key)
            if isinstance(candidate, dict):
                cdc_meta = cast(JSON, candidate)
                break
    decoded_log = cdc_meta.get("decoded_log_path")
    cdc = _parse_cdc(run_dir / str(decoded_log), node_name) if decoded_log else {
        "available": False,
        "trace_snapshots": [],
        "trace_snapshot_count": 0,
        "trace_deltas_first_to_last": {},
        "link_snapshots": [],
        "tx_diag_snapshots": [],
        "maxima": {},
    }
    events_path = run_dir / "raw" / f"node-{node_key}.events.ndjson"
    raw_path = run_dir / "raw" / f"node-{node_key}.kimu"
    events = _read_ndjson(events_path)
    timing_values = [
        duration
        for event in events
        if event.get("event") == "notify_callback_timing"
        and (duration := _int_field(event.get("callback_duration_ns"))) is not None
    ]
    notify_events = [event for event in events if event.get("event") == "notify"]
    latest_link = _latest_link_snapshot(cdc)
    latest_trace = _latest_trace_snapshot(cdc)
    actual_parameters = _actual_connection_parameters(cdc)
    return {
        "node": node_name,
        "events_path": str(events_path),
        "events_sha256": _sha256(events_path) if events_path.is_file() else None,
        "raw_path": str(raw_path),
        "cdc": cdc,
        "notify_event_count": len(notify_events),
        "callback_durations": summarize_callback_durations(timing_values),
        "tx_diagnostics": _tx_diagnostics_summary(cdc),
        "queue_drops": _queue_drop_summary(cdc),
        "capture_quality": _capture_quality_summary(run_dir, node_name, events),
        "latest_link": latest_link,
        "latest_trace": latest_trace,
        "actual_connection_parameters": actual_parameters,
        "actual": actual_parameters,
        "run_error": run_result.get("error"),
        "configured_nodes": run_config.get("nodes"),
    }


def audit_matrix(root_dir: Path) -> JSON:
    config = _read_json(root_dir / "matrix_config.json")
    result = _read_json(root_dir / "matrix_result.json")
    order = config.get("run_order")
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise ValueError("matrix_config.json has no valid run_order")
    runs: list[JSON] = []
    for run_index, condition in enumerate(order, start=1):
        run_dir = root_dir / f"run-{run_index:02d}-{condition}"
        run_config = _read_json(run_dir / "run_config.json")
        run_result = _read_json(run_dir / "run_result.json")
        control_events = _read_ndjson(run_dir / "experiment_control.ndjson")
        node_names = run_config.get("nodes")
        if not isinstance(node_names, list) or not all(isinstance(item, str) for item in node_names):
            raise ValueError(f"invalid node list in {run_dir / 'run_config.json'}")
        runs.append(
            {
                "run_index": run_index,
                "condition": condition,
                "run_dir": str(run_dir),
                "run_error": run_result.get("error"),
                "setup_errors": _setup_error_summary(run_result, control_events),
                "nodes": {
                    node_name: _node_audit(run_dir, node_name, run_config, run_result)
                    for node_name in node_names
                },
            }
        )
    return {
        "schema": "kineimu.m1.ble-link-matrix-audit/0.2",
        "root_dir": str(root_dir),
        "matrix_config": config,
        "matrix_result": result,
        "runs": runs,
        "decision_policy": {
            "connection_parameter_request": (
                "Only if actual interval/latency/timeout differs materially by condition "
                "and throughput follows it."
            ),
            "completion_driven_tx": (
                "Only if device notify call duration is the limiting boundary while host "
                "callback time is small."
            ),
            "host_disk_write_decoupling": (
                "Only if host callback p95/max is material while device notify call "
                "duration is ordinary."
            ),
            "queue_capacity": (
                "No queue-capacity conclusion is drawn from queue high-water alone; "
                "capacity is unchanged."
            ),
        },
    }


def _write_json(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _display(value: object) -> str:
    return "n/a" if value is None else str(value)


def _markdown_cell(value: object) -> str:
    return _display(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _format_return_categories(return_codes: JSON) -> str:
    categories = return_codes.get("categories")
    if not isinstance(categories, dict):
        return "n/a"
    reconciles = return_codes.get("count_reconciles_with_submit_attempts")
    reconciliation_text = (
        "reconciled"
        if reconciles is True
        else "unreconciled"
        if reconciles is False
        else "n/a"
    )
    return (
        f"0:{_display(categories.get('accepted'))}, "
        f"ENOMEM:{_display(categories.get('enomem'))}, "
        f"EAGAIN:{_display(categories.get('eagain'))}, "
        f"other:{_display(categories.get('other_negative'))}, "
        f"positive:{_display(categories.get('unexpected_positive'))}; "
        f"attempt count reconciliation: {reconciliation_text}"
    )


def _format_bucket(value: object) -> str:
    if not isinstance(value, dict):
        return "n/a"
    return str(value.get("label", "n/a"))


def _format_age_distribution(summary: JSON) -> str:
    bins = summary.get("bins")
    formatted_bins = "/".join(str(value) for value in bins) if isinstance(bins, list) else "n/a"
    mean = summary.get("mean_us")
    mean_text = f"{mean:g}" if isinstance(mean, (int, float)) else "n/a"
    return (
        f"n={_display(summary.get('count'))}; mean={mean_text} us; bins={formatted_bins}; "
        f"p50={_format_bucket(summary.get('p50_bucket'))}; "
        f"p95={_format_bucket(summary.get('p95_bucket'))}"
    )


def _format_connection_parameters(parameters: JSON) -> str:
    interval = parameters.get("interval_us")
    latency = parameters.get("latency")
    timeout = parameters.get("supervision_timeout_us")
    phy = (
        f"{parameters.get('phy_tx')}/{parameters.get('phy_rx')}"
        if parameters.get("phy_valid") == 1
        else "n/a"
    )
    dle = (
        f"{parameters.get('dle_tx_max_len')}/{parameters.get('dle_rx_max_len')} B"
        if parameters.get("dle_valid") == 1
        else "n/a"
    )
    return (
        f"interval={_display(interval)} us; latency={_display(latency)}; "
        f"timeout={_display(timeout)} us; PHY tx/rx={phy}; DLE tx/rx={dle}"
    )


def _format_callback_durations(summary: JSON) -> str:
    return (
        f"n={_display(summary.get('count'))}; min/p50/p95/max="
        f"{_display(summary.get('min_ns'))}/{_display(summary.get('p50_ns'))}/"
        f"{_display(summary.get('p95_ns'))}/{_display(summary.get('max_ns'))} ns"
    )


def _write_report(path: Path, audit: JSON) -> None:
    matrix_config = cast(JSON, audit["matrix_config"])
    change_policy = cast(JSON, matrix_config.get("change_policy", {}))
    if bool(change_policy.get("completion_driven_tx", False)):
        transport_description = (
            "The selected completion-driven TX implementation was enabled; connection-parameter "
            "requests, host disk-write decoupling and queue capacity were unchanged."
        )
    else:
        transport_description = (
            "The baseline matrix leaves connection-parameter requests, completion-driven TX, host "
            "disk-write decoupling and queue capacity unchanged."
        )
    lines = [
        "# Closed-loop M1 BLE link throughput matrix",
        "",
        "Raw `.kimu` streams are read-only inputs. The offline audit does not repair, filter, "
        "interpolate, or resample them.",
        transport_description,
        "",
        "The CDC counters are boot-cumulative. Additive values below use the first and last "
        "snapshot in each same-boot, same-generation segment. In-flight peak is calculated from "
        "the current values observed in that segment; a retained boot maximum is shown only as "
        "start/end evidence when the run-local peak cannot be recovered exactly.",
        "",
        "## Per-run TX diagnostics",
        "",
        "| Run | Condition | Node | CDC segment | submit attempts / accepted | return-code categories | "
        "retry calls / ENOMEM-EAGAIN / schedule failures | completed / cancelled / stale / "
        "post-cancel / unexpected callbacks | in-flight start→end / observed peak / exact run peak | "
        "full-window count / wait us | completion-age distribution | enqueue / disconnect / stop drops |",
        "|---:|---|---|---|---:|---|---|---|---|---|---|---|",
    ]
    for run in cast(list[JSON], audit["runs"]):
        nodes = cast(dict[str, JSON], run["nodes"])
        for node_name, node in nodes.items():
            diagnostics = cast(JSON, node["tx_diagnostics"])
            segments = cast(list[JSON], diagnostics["segments"])
            queue_drops = cast(JSON, node["queue_drops"]["deltas"])
            rows = segments or [None]
            for segment_value in rows:
                segment = cast(JSON, segment_value) if segment_value is not None else {}
                return_codes = cast(JSON, segment.get("return_codes", {}))
                retries = cast(JSON, segment.get("retries", {}))
                lifecycle = cast(JSON, segment.get("lifecycle", {}))
                in_flight = cast(JSON, segment.get("in_flight", {}))
                window = cast(JSON, segment.get("completion_window", {}))
                age = cast(JSON, segment.get("completion_age", {}))
                if segment:
                    in_flight_text = (
                        f"{_display(in_flight.get('initial_current'))}→"
                        f"{_display(in_flight.get('final_current'))}; observed peak="
                        f"{_display(in_flight.get('observed_peak_current'))}; exact run peak="
                        f"{_display(in_flight.get('run_peak_value'))}"
                    )
                    segment_label = (
                        f"{segment.get('segment_index')} "
                        f"(boot {segment.get('boot_id')}, gen {segment.get('generation')}, "
                        f"{segment.get('delta_quality')})"
                    )
                    calls_text = (
                        f"{_display(segment.get('submit_attempts'))} / "
                        f"{_display(segment.get('accepted'))}"
                    )
                    retry_text = (
                        f"calls={_display(retries.get('actual_attempts'))}; ENOMEM/EAGAIN="
                        f"{_display(cast(JSON, retries.get('transient_returns', {})).get('enomem'))}/"
                        f"{_display(cast(JSON, retries.get('transient_returns', {})).get('eagain'))}; "
                        f"schedule initial/retry="
                        f"{_display(cast(JSON, retries.get('schedule_failures', {})).get('initial'))}/"
                        f"{_display(cast(JSON, retries.get('schedule_failures', {})).get('retry'))}"
                    )
                    lifecycle_text = (
                        f"{_display(lifecycle.get('completed'))} / "
                        f"{_display(lifecycle.get('cancelled'))} / "
                        f"{_display(lifecycle.get('stale_callbacks'))} / "
                        f"{_display(lifecycle.get('callbacks_after_cancel'))} / "
                        f"{_display(lifecycle.get('unexpected_callbacks'))}"
                    )
                    window_text = (
                        f"{_display(window.get('full_count'))} / "
                        f"{_display(window.get('wait_total_us'))}"
                    )
                    age_text = _format_age_distribution(age)
                else:
                    segment_label = "no tx_diag snapshots"
                    calls_text = "n/a"
                    retry_text = "n/a"
                    lifecycle_text = "n/a"
                    in_flight_text = "n/a"
                    window_text = "n/a"
                    age_text = "n/a"
                queue_text = (
                    f"{_display(queue_drops.get('enqueue'))} / "
                    f"{_display(queue_drops.get('disconnect'))} / "
                    f"{_display(queue_drops.get('stop'))}"
                )
                lines.append(
                    "| {run} | {condition} | {node} | {segment} | {calls} | {returns} | "
                    "{retries} | {lifecycle} | {in_flight} | {window} | {age} | {queue} |".format(
                        run=run["run_index"],
                        condition=run["condition"],
                        node=node_name,
                        segment=_markdown_cell(segment_label),
                        calls=_markdown_cell(calls_text),
                        returns=_markdown_cell(_format_return_categories(return_codes)),
                        retries=_markdown_cell(retry_text),
                        lifecycle=_markdown_cell(lifecycle_text),
                        in_flight=_markdown_cell(in_flight_text),
                        window=_markdown_cell(window_text),
                        age=_markdown_cell(age_text),
                        queue=_markdown_cell(queue_text),
                    )
                )

    lines.extend(
        [
            "",
            "## Connection and host callback observations",
            "",
            "| Run | Condition | Node | actual connection parameters | "
            "host callback time (count / min / p50 / p95 / max ns) | decoded notifications |",
            "|---:|---|---|---|---|---:|",
        ]
    )
    for run in cast(list[JSON], audit["runs"]):
        nodes = cast(dict[str, JSON], run["nodes"])
        for node_name, node in nodes.items():
            lines.append(
                "| {run} | {condition} | {node} | {parameters} | {callbacks} | {notifies} |".format(
                    run=run["run_index"],
                    condition=run["condition"],
                    node=node_name,
                    parameters=_markdown_cell(
                        _format_connection_parameters(cast(JSON, node["actual_connection_parameters"]))
                    ),
                    callbacks=_markdown_cell(
                        _format_callback_durations(cast(JSON, node["callback_durations"]))
                    ),
                    notifies=node["notify_event_count"],
                )
            )

    lines.extend(
        [
            "",
            "## CRC / decode / framing",
            "",
            "| Run | Condition | Node | CRC errors (events / raw QC) | "
            "decode errors (events / raw QC) | framing errors | raw SHA-256 unchanged during audit |",
            "|---:|---|---|---:|---|---:|---|",
        ]
    )
    for run in cast(list[JSON], audit["runs"]):
        nodes = cast(dict[str, JSON], run["nodes"])
        for node_name, node in nodes.items():
            quality = cast(JSON, node["capture_quality"])
            crc_text = (
                f"{_display(quality.get('event_crc_errors'))} / "
                f"{_display(quality.get('raw_crc_errors'))}"
            )
            decode_text = (
                f"{_display(quality.get('event_decode_errors'))} / "
                f"{_display(quality.get('raw_decode_errors'))}"
            )
            unchanged = quality.get("raw_unchanged_during_audit")
            unchanged_text = "n/a" if unchanged is None else str(unchanged)
            lines.append(
                "| {run} | {condition} | {node} | {crc} | {decode} | {framing} | {unchanged} |".format(
                    run=run["run_index"],
                    condition=run["condition"],
                    node=node_name,
                    crc=_markdown_cell(crc_text),
                    decode=_markdown_cell(decode_text),
                    framing=_display(quality.get("framing_errors")),
                    unchanged=unchanged_text,
                )
            )

    lines.extend(
        [
            "",
            "## Setup errors",
            "",
            "| Run | Condition | BLE connect attempts / returns / failures by node | CDC capture errors | run error |",
            "|---:|---|---|---|---|",
        ]
    )
    for run in cast(list[JSON], audit["runs"]):
        setup = cast(JSON, run["setup_errors"])
        attempts = cast(JSON, setup.get("ble_connect_attempts_by_node", {}))
        returns = cast(JSON, setup.get("ble_connect_returns_by_node", {}))
        failures = cast(JSON, setup.get("ble_connect_failures_by_node", {}))
        connect_text = (
            f"attempts={_markdown_cell(attempts)}; returns={_markdown_cell(returns)}; "
            f"failures={_markdown_cell(failures)}"
        )
        cdc_errors = cast(list[JSON], setup.get("cdc_capture_errors", []))
        cdc_error_text = "; ".join(
            f"{entry.get('label')}: {entry.get('detail')}" for entry in cdc_errors
        ) or "none"
        lines.append(
            "| {run} | {condition} | {connect} | {cdc} | {error} |".format(
                run=run["run_index"],
                condition=run["condition"],
                connect=_markdown_cell(connect_text),
                cdc=_markdown_cell(cdc_error_text),
                error=_markdown_cell(setup.get("run_error") or "none"),
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Compare each node across the single-node and dual-node conditions. Use the per-run "
            "return-code, retry, completion-age, full-window, enqueue-drop, actual-link, and host "
            "callback fields as observations for follow-up analysis. The matrix does not change "
            "queue capacity or public acquisition schemas.",
            "",
            "The JSON audit retains every parsed CDC snapshot and the per-run snapshot boundaries. "
            "Legacy logs without `tx_diag` remain represented with unavailable diagnostic deltas.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_hash_manifest(root_dir: Path) -> None:
    path = root_dir / "SHA256SUMS.txt"
    with path.open("w", encoding="utf-8") as stream:
        for file in sorted(root_dir.rglob("*")):
            if file.is_file() and file != path:
                stream.write(f"{_sha256(file)}  {file.relative_to(root_dir).as_posix()}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-dir", type=Path, required=True)
    parser.add_argument("--overwrite-derived", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    root_dir: Path = args.root_dir
    if args.overwrite_derived:
        for name in ("matrix_audit.json", "MATRIX_REPORT.md", "SHA256SUMS.txt"):
            path = root_dir / name
            if path.exists():
                path.unlink()
    audit = audit_matrix(root_dir)
    _write_json(root_dir / "matrix_audit.json", audit)
    _write_report(root_dir / "MATRIX_REPORT.md", audit)
    _write_hash_manifest(root_dir)
    print(json.dumps({"root_dir": str(root_dir), "runs": len(audit["runs"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
