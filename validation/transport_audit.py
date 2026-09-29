"""Audit one independent M1 transport experiment without changing its raw data.

The auditor is deliberately offline.  It reads the recorder's immutable BLE
streams, transport sidecars, experiment-control sidecar, and CDC captures, then
writes derived audit/report artifacts beside them.  It never opens a raw file
for writing and never filters, repairs, interpolates, or resamples a packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any, cast

from kineimu_shoulder.io.m1_capture import CaptureFormatError, CaptureRecord, iter_capture_records
from kineimu_shoulder.io.m1_packet import NodeId, PacketFlags, ProtocolError, decode_sample_packet
from kineimu_shoulder.io.m1_qc import QcIssue, audit_capture_stream

JSON = dict[str, Any]

LOSS_COUNTERS = (
    "sensor_fifo_overruns",
    "firmware_queue_overruns",
    "transport_backpressure_events",
    "samples_dropped_before_packetization",
)
STATUS_TRACE_FIELDS = (
    "samples_acquired",
    "packets_generated",
    "sensor_fifo_overruns",
    "firmware_queue_overruns",
    "transport_backpressure_events",
    "samples_dropped_before_packetization",
    "acquisition_buffer_high_water_samples",
    "transport_queue_high_water_packets",
    "last_error_code",
)
PACKET_FLAG_FIELDS = {
    "sensor_fifo_overrun": PacketFlags.SENSOR_FIFO_OVERRUN,
    "firmware_queue_overrun": PacketFlags.FIRMWARE_QUEUE_OVERRUN,
    "transport_backpressure": PacketFlags.TRANSPORT_BACKPRESSURE,
    "discontinuity_before_first_sample": PacketFlags.DISCONTINUITY_BEFORE_FIRST_SAMPLE,
}
TRACE_LINE = re.compile(r"Node (?P<node>[AB]): acquisition trace (?P<body>.*)$")
TRACE_FIELD = re.compile(r"(?P<name>[a-z_]+)=(?P<value>-?\d+)")
LINK_LINE = re.compile(
    r"Node (?P<node>[AB]): BLE link event=(?P<event>[a-z_]+) (?P<body>.*)$"
)
TX_DIAG_LINE = re.compile(r"Node (?P<node>[AB]): tx_diag (?P<body>.*)$")
TX_DIAG_TOKEN = re.compile(r"(?P<name>[a-z_]+)=(?P<value>[^\s]+)")


def _parse_tx_diag_fields(body: str) -> tuple[JSON, list[str]]:
    """Parse one boot-cumulative Zephyr TX diagnostic snapshot."""

    raw_fields = {
        match.group("name"): match.group("value") for match in TX_DIAG_TOKEN.finditer(body)
    }
    fields: JSON = {}
    errors: list[str] = []
    scalar_names = {
        "boot": "boot_id",
        "generation": "generation",
        "calls": "calls",
        "accepted": "accepted",
        "final_fail": "final_fail",
        "packet_drops": "packet_drops",
        "return_last": "return_last",
        "enomem": "enomem",
        "eagain": "eagain",
        "retries": "retries",
        "window_owned": "window_owned",
        "window_full": "window_full",
        "wait_us": "wait_us",
        "completed": "completed",
        "cancelled": "cancelled",
        "callbacks_stale": "callbacks_stale",
        "callbacks_cancelled": "callbacks_cancelled",
        "callbacks_unexpected": "callbacks_unexpected",
        "age_count": "age_count",
        "saturated": "saturated",
    }
    for source_name, output_name in scalar_names.items():
        raw_value = raw_fields.get(source_name)
        if raw_value is None:
            errors.append(f"missing {source_name}")
            continue
        try:
            fields[output_name] = int(raw_value)
        except ValueError:
            errors.append(f"invalid integer for {source_name}: {raw_value}")

    paired_fields = {
        "schedule_fail": ("initial", "retry"),
        "schedule_last": ("initial", "retry"),
        "inflight": ("current", "boot_peak"),
    }
    for source_name, component_names in paired_fields.items():
        raw_value = raw_fields.get(source_name)
        if raw_value is None:
            errors.append(f"missing {source_name}")
            continue
        parts = raw_value.split("/")
        if len(parts) != len(component_names):
            errors.append(f"invalid {source_name} pair: {raw_value}")
            continue
        try:
            fields[source_name] = {
                component: int(value)
                for component, value in zip(component_names, parts, strict=True)
            }
        except ValueError:
            errors.append(f"invalid integer in {source_name}: {raw_value}")

    raw_age = raw_fields.get("age_us")
    if raw_age is None:
        errors.append("missing age_us")
    else:
        age_parts = raw_age.split("/")
        if len(age_parts) != 4:
            errors.append(f"invalid age_us tuple: {raw_age}")
        else:
            try:
                last_us, min_us, max_us, total_us = (int(value) for value in age_parts)
                fields["age_us"] = {
                    "last": last_us,
                    "min": min_us,
                    "max": max_us,
                    "total": total_us,
                }
            except ValueError:
                errors.append(f"invalid integer in age_us: {raw_age}")

    raw_bins = raw_fields.get("age_bins")
    if raw_bins is None:
        errors.append("missing age_bins")
    else:
        try:
            bins = [int(value) for value in raw_bins.split(",")]
        except ValueError:
            bins = []
            errors.append(f"invalid integer in age_bins: {raw_bins}")
        if len(bins) != 8:
            errors.append(f"age_bins must contain 8 values: {raw_bins}")
        else:
            fields["age_bins"] = bins

    raw_return_counts = raw_fields.get("return_counts")
    return_counts: JSON = {}
    if raw_return_counts is None:
        errors.append("missing return_counts")
    elif raw_return_counts != "none":
        for entry in raw_return_counts.split(","):
            match = re.fullmatch(r"(?P<code>-?\d+):(?P<count>\d+)", entry)
            if match is None:
                errors.append(f"invalid return code count: {entry}")
                continue
            return_counts[str(int(match.group("code")))] = int(match.group("count"))
    fields["return_counts"] = return_counts
    fields["raw_fields"] = raw_fields
    return fields, errors


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
    records: list[JSON] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        records.append(cast(JSON, value))
    return records


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _int_field(event: JSON, name: str) -> int | None:
    value = event.get(name)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _event_time(event: JSON) -> int | None:
    return _int_field(event, "host_monotonic_ns")


def _sorted_events(events: list[JSON], event_type: str) -> list[JSON]:
    return sorted(
        [event for event in events if event.get("event") == event_type],
        key=lambda event: _event_time(event) or 0,
    )


def _complete_capture_records(raw_bytes: bytes) -> tuple[list[CaptureRecord], str | None]:
    stream = BytesIO(raw_bytes)
    records: list[CaptureRecord] = []
    iterator = iter_capture_records(stream)
    while True:
        try:
            records.append(next(iterator))
        except StopIteration:
            return records, None
        except CaptureFormatError as error:
            return records, str(error)


def _issue_dict(issue: QcIssue) -> JSON:
    return {
        "code": issue.code.value,
        "stream_offset": issue.stream_offset,
        "detail": issue.detail,
        "previous": issue.previous,
        "current": issue.current,
        "missing_count": issue.missing_count,
    }


def _parse_cdc(path: Path, node_name: str) -> JSON:
    if not path.is_file():
        return {
            "path": path.name,
            "available": False,
            "error": "CDC decoded log is missing",
            "trace_snapshots": [],
            "trace_snapshot_count": 0,
            "trace_deltas_first_to_last": {},
            "link_snapshots": [],
            "link_snapshot_count": 0,
            "tx_diag_snapshots": [],
            "tx_diag_snapshot_count": 0,
            "maxima": {},
            "maxima_scope": "boot_cumulative",
        }
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    snapshots: list[JSON] = []
    link_snapshots: list[JSON] = []
    tx_diag_snapshots: list[JSON] = []
    for line_number, line in enumerate(lines, start=1):
        tx_match = TX_DIAG_LINE.search(line)
        if tx_match is not None and tx_match.group("node") == node_name:
            fields, parse_errors = _parse_tx_diag_fields(tx_match.group("body"))
            tx_diag_snapshots.append(
                {
                    "line": line_number,
                    "text": line,
                    "fields": fields,
                    "parse_errors": parse_errors,
                }
            )
            continue
        match = TRACE_LINE.search(line)
        if match is not None and match.group("node") == node_name:
            fields = {
                field.group("name"): int(field.group("value"))
                for field in TRACE_FIELD.finditer(match.group("body"))
            }
            snapshots.append({"line": line_number, "text": line, "fields": fields})
            continue
        link_match = LINK_LINE.search(line)
        if link_match is None or link_match.group("node") != node_name:
            continue
        link_fields = {
            field.group("name"): int(field.group("value"))
            for field in TRACE_FIELD.finditer(link_match.group("body"))
        }
        link_snapshots.append(
            {
                "line": line_number,
                "text": line,
                "event": link_match.group("event"),
                "fields": link_fields,
            }
        )
    maxima: dict[str, int] = {}
    for snapshot in snapshots:
        fields = cast(JSON, snapshot["fields"])
        for name, value in fields.items():
            if isinstance(value, int):
                maxima[name] = max(maxima.get(name, value), value)
    trace_deltas: dict[str, int | None] = {}
    trace_delta_fields = (
        "tx_enqueue_drops",
        "tx_disconnect_drops",
        "tx_stop_drops",
        "notify_calls",
        "notify_failures",
        "notify_total_duration",
    )
    if len(snapshots) >= 2:
        initial_fields = cast(JSON, snapshots[0]["fields"])
        final_fields = cast(JSON, snapshots[-1]["fields"])
        for name in trace_delta_fields:
            initial_value = initial_fields.get(name)
            final_value = final_fields.get(name)
            if (
                isinstance(initial_value, int)
                and not isinstance(initial_value, bool)
                and isinstance(final_value, int)
                and not isinstance(final_value, bool)
                and final_value >= initial_value
            ):
                trace_deltas[name] = final_value - initial_value
            else:
                trace_deltas[name] = None
    else:
        trace_deltas = {name: None for name in trace_delta_fields}
    trace_saturated = any(
        cast(JSON, snapshot["fields"]).get("saturated") == 1 for snapshot in snapshots
    )
    trace_delta_quality = (
        "insufficient_snapshots"
        if len(snapshots) < 2
        else "lower_bound" if trace_saturated else "exact"
    )
    return {
        "path": path.name,
        "available": True,
        "byte_length": path.stat().st_size,
        "trace_snapshot_count": len(snapshots),
        "trace_snapshots": snapshots,
        "trace_deltas_first_to_last": trace_deltas,
        "trace_delta_quality": trace_delta_quality,
        "link_snapshot_count": len(link_snapshots),
        "link_snapshots": link_snapshots,
        "tx_diag_snapshot_count": len(tx_diag_snapshots),
        "tx_diag_snapshots": tx_diag_snapshots,
        "maxima": maxima,
        "maxima_scope": "boot_cumulative",
    }


def _status_snapshot(event: JSON) -> JSON:
    return {
        "host_monotonic_ns": _event_time(event),
        "source": event.get("source"),
        "connection_id": event.get("connection_id"),
        **{
            name: event.get(name)
            for name in (
                "node_id",
                "acquisition_state",
                "status_flags",
                "boot_id",
                "clock_epoch",
                "status_sequence",
                "last_sample_sequence",
                "last_packet_sequence",
                *STATUS_TRACE_FIELDS,
            )
            if name in event
        },
    }


def _status_summary(status_events: list[JSON]) -> JSON:
    decoded = [event for event in status_events if event.get("decode_ok") is True]
    reads = [event for event in decoded if event.get("source") == "read"]
    finals = [event for event in decoded if event.get("source") == "final"]
    initial = reads[0] if reads else None
    final = finals[-1] if finals else None
    deltas: dict[str, int] = {}
    if initial is not None and final is not None:
        for name in LOSS_COUNTERS:
            initial_value = _int_field(initial, name)
            final_value = _int_field(final, name)
            if initial_value is not None and final_value is not None:
                deltas[name] = final_value - initial_value
        for name in ("samples_acquired", "packets_generated"):
            initial_value = _int_field(initial, name)
            final_value = _int_field(final, name)
            if initial_value is not None and final_value is not None:
                deltas[name] = final_value - initial_value

    values: dict[str, list[int]] = {}
    for name in STATUS_TRACE_FIELDS:
        values[name] = [
            value
            for event in decoded
            if (value := _int_field(event, name)) is not None
        ]
    return {
        "event_count": len(status_events),
        "decoded_event_count": len(decoded),
        "snapshots": [_status_snapshot(event) for event in decoded],
        "initial_read": _status_snapshot(initial) if initial is not None else None,
        "final_read": _status_snapshot(final) if final is not None else None,
        "cumulative_deltas_initial_to_final": deltas,
        "field_values": values,
        "status_reconciliation": {
            name: {
                "initial": _int_field(initial, name) if initial is not None else None,
                "final": _int_field(final, name) if final is not None else None,
                "delta": deltas.get(name),
            }
            for name in LOSS_COUNTERS
        },
    }


def _config_snapshot(event: JSON) -> JSON:
    stable_fields = (
        "node_id",
        "timestamp_source",
        "firmware_version",
        "batch_size",
        "config_generation",
        "hardware_device_id",
        "firmware_git_commit",
        "timer_frequency_hz",
        "accel_odr_millihz",
        "gyro_odr_millihz",
        "accel_range_mg",
        "gyro_range_mdps",
        "sensor_registers_hex",
    )
    return {
        "host_monotonic_ns": _event_time(event),
        "source": event.get("source"),
        "connection_id": event.get("connection_id"),
        **{
            name: event.get(name)
            for name in (*stable_fields, "clock_epoch", "boot_id")
            if name in event
        },
    }


def _config_signature(snapshot: JSON) -> tuple[object, ...]:
    return tuple(
        json.dumps(snapshot.get(name), ensure_ascii=False, sort_keys=True)
        for name in (
            "node_id",
            "timestamp_source",
            "firmware_version",
            "batch_size",
            "config_generation",
            "hardware_device_id",
            "firmware_git_commit",
            "timer_frequency_hz",
            "accel_odr_millihz",
            "gyro_odr_millihz",
            "accel_range_mg",
            "gyro_range_mdps",
            "sensor_registers_hex",
        )
    )


def _planned_disconnect_times(control_events: list[JSON], node_name: str) -> list[int]:
    return [
        time_ns
        for event in control_events
        if event.get("event") == "stimulus_disconnect_request"
        and event.get("node") == node_name
        if (time_ns := _event_time(event)) is not None
    ]


def _outage_intervals(
    events: list[JSON],
    control_events: list[JSON],
    node_name: str,
    run_end_ns: int,
) -> list[JSON]:
    disconnects = _sorted_events(events, "disconnect")
    reconnects = _sorted_events(events, "reconnect")
    planned_times = _planned_disconnect_times(control_events, node_name)
    intervals: list[JSON] = []
    used_reconnect_ids: set[str] = set()
    for disconnect in disconnects:
        disconnect_ns = _event_time(disconnect)
        if disconnect_ns is None:
            continue
        reconnect = next(
            (
                candidate
                for candidate in reconnects
                if (_event_time(candidate) or 0) > disconnect_ns
                and str(candidate.get("connection_id")) not in used_reconnect_ids
            ),
            None,
        )
        reconnect_ns = _event_time(reconnect) if reconnect is not None else None
        if reconnect is not None:
            used_reconnect_ids.add(str(reconnect.get("connection_id")))
        is_planned = any(abs(planned - disconnect_ns) <= 2_000_000_000 for planned in planned_times)
        kind = "planned_recovery" if is_planned else "unplanned_or_teardown"
        end_ns = reconnect_ns if reconnect_ns is not None else run_end_ns
        intervals.append(
            {
                "node": node_name,
                "kind": kind,
                "disconnect_host_monotonic_ns": disconnect_ns,
                "reconnect_host_monotonic_ns": reconnect_ns,
                "interval_end_host_monotonic_ns": end_ns,
                "link_unavailable_ns": max(0, end_ns - disconnect_ns),
                "disconnect_connection_id": disconnect.get("connection_id"),
                "reconnect_connection_id": reconnect.get("connection_id") if reconnect else None,
                "reconnect_found": reconnect is not None,
            }
        )
    return intervals


def _first_event_after(events: list[JSON], time_ns: int, *, connection_id: str | None = None) -> JSON | None:
    for event in sorted(events, key=lambda item: _event_time(item) or 0):
        event_time = _event_time(event)
        if event_time is None or event_time < time_ns:
            continue
        if connection_id is not None and event.get("connection_id") != connection_id:
            continue
        return event
    return None


def _recovery_records(
    events: list[JSON],
    control_events: list[JSON],
    intervals: list[JSON],
    run_end_ns: int,
) -> list[JSON]:
    configs = _sorted_events(events, "config")
    notifies = _sorted_events(events, "notify")
    telemetry_enabled = [
        event for event in control_events if event.get("event") == "telemetry_notify_enabled"
    ]
    reconnect_calls = [
        event for event in control_events if event.get("event") == "ble_connect_call"
    ]
    records: list[JSON] = []
    for interval in intervals:
        if interval["kind"] != "planned_recovery":
            continue
        disconnect_ns = cast(int, interval["disconnect_host_monotonic_ns"])
        reconnect_ns = interval["reconnect_host_monotonic_ns"]
        reconnect_id = interval["reconnect_connection_id"]
        if reconnect_ns is not None:
            config = _first_event_after(
                configs,
                cast(int, reconnect_ns),
                connection_id=cast(str, reconnect_id),
            )
            notify = _first_event_after(
                notifies,
                cast(int, reconnect_ns),
                connection_id=cast(str, reconnect_id),
            )
            enabled = next(
                (
                    event
                    for event in sorted(telemetry_enabled, key=lambda item: _event_time(item) or 0)
                    if event.get("node") == interval.get("node")
                    and (_event_time(event) or 0) >= reconnect_ns
                ),
                None,
            )
        else:
            config = None
            notify = None
            enabled = None
        config_ns = _event_time(config) if config is not None else None
        notify_ns = _event_time(notify) if notify is not None else None
        telemetry_ns = _event_time(enabled) if enabled is not None else notify_ns
        node_name = interval.get("node")
        attempts = [
            _event_time(event)
            for event in sorted(reconnect_calls, key=lambda item: _event_time(item) or 0)
            if event.get("node") == node_name
            and (_event_time(event) or 0) > disconnect_ns
            and (_event_time(event) or 0) <= run_end_ns
            if _event_time(event) is not None
        ]
        records.append(
            {
                **interval,
                "disconnect_host_monotonic_ns": disconnect_ns,
                "reconnect_latency_ns": reconnect_ns - disconnect_ns if reconnect_ns is not None else None,
                "identity_config_revalidation_host_monotonic_ns": config_ns,
                "identity_config_revalidation_latency_ns": config_ns - disconnect_ns
                if config_ns is not None
                else None,
                "telemetry_resume_host_monotonic_ns": telemetry_ns,
                "telemetry_unavailable_ns": telemetry_ns - disconnect_ns
                if telemetry_ns is not None
                else None,
                "reconnect_attempt_host_monotonic_ns": attempts,
                "recovery_target_10s": config_ns is not None and config_ns - disconnect_ns <= 10_000_000_000,
            }
        )
    return records


def _event_has_sequence(event: JSON, sequence: int, *, sample: bool) -> bool:
    field = "sample_sequences" if sample else "packet_sequence"
    value = event.get(field)
    if sample:
        return isinstance(value, list) and sequence in value
    return isinstance(value, int) and value == sequence


def _gap_attribution(
    issue: QcIssue,
    *,
    event: JSON | None,
    notify_events: list[JSON],
    recovery_records: list[JSON],
) -> tuple[list[str], JSON]:
    if issue.code.value not in {"missing_packets", "missing_samples"}:
        return [], {"status": "not_a_loss_gap"}
    attributions: list[str] = []
    packet_flags = _int_field(event, "packet_flags") if event is not None else None
    if packet_flags is not None:
        if packet_flags & int(PacketFlags.SENSOR_FIFO_OVERRUN):
            attributions.append("sensor_fifo_overrun_packet_flag")
        if packet_flags & int(PacketFlags.FIRMWARE_QUEUE_OVERRUN):
            attributions.append("acquisition_queue_overrun_packet_flag")
        if packet_flags & int(PacketFlags.TRANSPORT_BACKPRESSURE):
            attributions.append("transport_backpressure_packet_flag")

    current_ns = _event_time(event) if event is not None else None
    boundary_evidence: JSON | None = None
    if current_ns is not None:
        for recovery in recovery_records:
            disconnect_ns = cast(int, recovery["disconnect_host_monotonic_ns"])
            reconnect_ns = recovery.get("reconnect_host_monotonic_ns")
            if reconnect_ns is None or current_ns < cast(int, reconnect_ns):
                continue
            previous = issue.previous
            previous_event = None
            if previous is not None:
                previous_event = next(
                    (
                        candidate
                        for candidate in reversed(notify_events)
                        if (_event_time(candidate) or 0) < disconnect_ns
                        and _event_has_sequence(
                            candidate,
                            previous,
                            sample=issue.code.value == "missing_samples",
                        )
                    ),
                    None,
                )
            if previous_event is not None:
                attributions.append("ble_link_unavailable_interval")
                boundary_evidence = {
                    "disconnect_host_monotonic_ns": disconnect_ns,
                    "reconnect_host_monotonic_ns": reconnect_ns,
                    "previous_sequence_event_host_monotonic_ns": _event_time(previous_event),
                    "current_sequence_event_host_monotonic_ns": current_ns,
                }
                break
    if not attributions:
        return ["unattributed"], {"status": "no_packet_flag_or_link-boundary_evidence"}
    return attributions, {
        "status": "attributed",
        "packet_flags": packet_flags,
        "link_boundary": boundary_evidence,
    }


def _sequence_audit(
    raw_path: Path,
    events: list[JSON],
    node_id: NodeId,
    recovery_records: list[JSON],
) -> JSON:
    raw_bytes = raw_path.read_bytes()
    raw_hash_before = hashlib.sha256(raw_bytes).hexdigest()
    report = audit_capture_stream(BytesIO(raw_bytes), expected_node_id=node_id)
    records, framing_error = _complete_capture_records(raw_bytes)
    notify_events = [
        event
        for event in events
        if event.get("event") == "notify" and event.get("decode_ok") is True
    ]
    event_by_offset = {
        offset: event
        for event in notify_events
        if (offset := _int_field(event, "raw_stream_offset")) is not None
    }
    decoded_records: list[JSON] = []
    for record in records:
        try:
            packet = decode_sample_packet(record.payload)
        except ProtocolError:
            continue
        decoded_records.append(
            {
                "stream_offset": record.stream_offset,
                "host_monotonic_ns": record.host_monotonic_ns,
                "node_id": int(packet.node_id),
                "packet_sequence": packet.packet_sequence,
                "clock_epoch": packet.clock_epoch,
                "packet_flags": int(packet.flags),
                "sample_sequences": [sample.sequence for sample in packet.samples],
            }
        )
    issues: list[JSON] = []
    missing_gaps: list[JSON] = []
    for issue in report.issues:
        event = event_by_offset.get(issue.stream_offset)
        attribution, attribution_evidence = _gap_attribution(
            issue,
            event=event,
            notify_events=notify_events,
            recovery_records=recovery_records,
        )
        entry: JSON = {
            **_issue_dict(issue),
            "is_sequence_gap": issue.code.value in {"missing_packets", "missing_samples"},
            "connection_id": event.get("connection_id") if event is not None else None,
            "event_host_monotonic_ns": _event_time(event) if event is not None else None,
            "packet_flags": _int_field(event, "packet_flags") if event is not None else None,
            "attribution": attribution,
            "attribution_evidence": attribution_evidence,
        }
        issues.append(entry)
        if entry["is_sequence_gap"]:
            missing_gaps.append(entry)
    raw_hash_after = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    return {
        "raw_path": raw_path.name,
        "raw_sha256_before_audit": raw_hash_before,
        "raw_sha256_after_audit": raw_hash_after,
        "raw_unchanged_during_audit": raw_hash_before == raw_hash_after,
        "complete_outer_records_seen": len(records),
        "complete_record_parse_error": framing_error,
        "decoded_record_metadata": decoded_records,
        "qc": {
            "records_seen": report.records_seen,
            "packets_decoded": report.packets_decoded,
            "samples_decoded": report.samples_decoded,
            "decode_errors": report.decode_errors,
            "framing_errors": report.framing_errors,
            "packet_duplicates": report.packet_duplicates,
            "packet_reordered": report.packet_reordered,
            "packets_missing": report.packets_missing,
            "sample_duplicates": report.sample_duplicates,
            "sample_reordered": report.sample_reordered,
            "samples_missing": report.samples_missing,
            "timestamp_duplicates": report.timestamp_duplicates,
            "timestamp_reordered": report.timestamp_reordered,
            "epoch_changes": report.epoch_changes,
            "node_mismatches": report.node_mismatches,
        },
        "all_sequence_issues": issues,
        "missing_sequence_gaps": missing_gaps,
        "unattributed_gap_count": sum("unattributed" in gap["attribution"] for gap in missing_gaps),
    }


def _packet_flag_summary(events: list[JSON]) -> JSON:
    notify_events = [
        event
        for event in events
        if event.get("event") == "notify" and event.get("decode_ok") is True
    ]
    connection_ids = sorted(
        {
            connection_id
            for event in notify_events
            if isinstance(connection_id := event.get("connection_id"), str)
        }
    )
    return {
        "decoded_notify_count": len(notify_events),
        "flagged_notify_counts": {
            name: sum(
                bool((_int_field(event, "packet_flags") or 0) & int(flag))
                for event in notify_events
            )
            for name, flag in PACKET_FLAG_FIELDS.items()
        },
        "packet_flags_by_connection": {
            str(connection_id): {
                name: sum(
                    bool((_int_field(event, "packet_flags") or 0) & int(flag))
                    for event in notify_events
                    if event.get("connection_id") == connection_id
                )
                for name, flag in PACKET_FLAG_FIELDS.items()
            }
            for connection_id in connection_ids
        },
    }


def _loss_attribution(
    *,
    status: JSON,
    packet_flags: JSON,
    cdc: JSON,
    sequence: JSON,
    mode: str,
) -> JSON:
    status_deltas = cast(JSON, status.get("cumulative_deltas_initial_to_final", {}))
    flagged = cast(JSON, packet_flags.get("flagged_notify_counts", {}))
    cdc_trace_deltas = cast(JSON, cdc.get("trace_deltas_first_to_last", {}))
    sources = {
        "sensor_fifo": {
            "status_counter_delta": status_deltas.get("sensor_fifo_overruns", 0),
            "packet_flag_count": flagged.get("sensor_fifo_overrun", 0),
            "evidence_sources": ["status sidecar", "packet event sidecar"],
        },
        "acquisition_queue": {
            "status_firmware_queue_delta": status_deltas.get("firmware_queue_overruns", 0),
            "status_pre_packetization_delta": status_deltas.get(
                "samples_dropped_before_packetization", 0
            ),
            "packet_flag_count": flagged.get("firmware_queue_overrun", 0),
            "evidence_sources": ["status sidecar", "packet event sidecar"],
        },
        "transport_backpressure": {
            "status_counter_delta": status_deltas.get("transport_backpressure_events", 0),
            "packet_flag_count": flagged.get("transport_backpressure", 0),
            "cdc_tx_enqueue_drops_delta": cdc_trace_deltas.get("tx_enqueue_drops"),
            "cdc_tx_disconnect_drops_delta": cdc_trace_deltas.get("tx_disconnect_drops"),
            "cdc_tx_stop_drops_delta": cdc_trace_deltas.get("tx_stop_drops"),
            "cdc_notify_failures_delta": cdc_trace_deltas.get("notify_failures"),
            "cdc_delta_quality": cdc.get("trace_delta_quality", "unavailable"),
            "evidence_sources": ["status sidecar", "packet event sidecar", "CDC trace"],
        },
        "host_capture_or_protocol": {
            "decode_errors": sequence["qc"]["decode_errors"],
            "framing_errors": sequence["qc"]["framing_errors"],
            "evidence_sources": ["raw QC", "transport event sidecar"],
        },
    }
    for category, evidence in sources.items():
        observed = any(
            isinstance(value, int) and value > 0
            for key, value in evidence.items()
            if key not in {"evidence_sources"}
        )
        if category == "host_capture_or_protocol":
            closed = True
        elif category == "sensor_fifo":
            closed = not observed or evidence["packet_flag_count"] > 0
        elif category == "acquisition_queue":
            closed = not observed or evidence["packet_flag_count"] > 0
        else:
            closed = not observed or any(
                evidence.get(name, 0) > 0
                for name in (
                    "packet_flag_count",
                    "cdc_tx_enqueue_drops",
                    "cdc_tx_disconnect_drops",
                    "cdc_tx_stop_drops",
                    "cdc_notify_failures",
                )
            )
        evidence["observed"] = observed
        evidence["closure"] = "closed" if closed else "partial_or_unclosed"
    sources["sequence_gaps"] = {
        "missing_packet_count": sequence["qc"]["packets_missing"],
        "missing_sample_count": sequence["qc"]["samples_missing"],
        "unattributed_gap_count": sequence["unattributed_gap_count"],
        "closure": "closed" if sequence["unattributed_gap_count"] == 0 else "unattributed_gap_present",
        "mode_context": mode,
    }
    return sources


def _node_analysis(
    run_dir: Path,
    node_name: str,
    control_events: list[JSON],
    mode: str,
    run_end_ns: int,
) -> JSON:
    node_id = NodeId.A if node_name == "A" else NodeId.B
    raw_path = run_dir / "raw" / f"node-{node_name.lower()}.kimu"
    events_path = run_dir / "raw" / f"node-{node_name.lower()}.events.ndjson"
    cdc_path = run_dir / f"node-{node_name.lower()}.cdc.log"
    raw_hash = _sha256(raw_path)
    events = _read_ndjson(events_path)
    intervals = _outage_intervals(events, control_events, node_name, run_end_ns)
    recovery_records = _recovery_records(events, control_events, intervals, run_end_ns)
    status_events = _sorted_events(events, "status")
    config_events = _sorted_events(events, "config")
    status = _status_summary(status_events)
    packet_flags = _packet_flag_summary(events)
    cdc = _parse_cdc(cdc_path, node_name)
    sequence = _sequence_audit(raw_path, events, node_id, recovery_records)
    configs = [_config_snapshot(event) for event in config_events if event.get("decode_ok") is True]
    initial_config = configs[0] if configs else None
    reconnect_configs = [config for config in configs if config.get("source") == "read"][1:]
    continuity_reasons: list[str] = []
    stable_identity = bool(initial_config is not None)
    if initial_config is None:
        continuity_reasons.append("missing_initial_identity_config")
    initial_signature = _config_signature(initial_config) if initial_config is not None else None
    config_consistent = True
    boot_epoch_consistent = True
    for config in reconnect_configs:
        if initial_signature is not None and _config_signature(config) != initial_signature:
            config_consistent = False
        if initial_config is not None and (
            config.get("boot_id") != initial_config.get("boot_id")
            or config.get("clock_epoch") != initial_config.get("clock_epoch")
        ):
            boot_epoch_consistent = False
    if not config_consistent:
        continuity_reasons.append("reconnected_identity_or_configuration_changed")
    if not boot_epoch_consistent:
        continuity_reasons.append("reconnected_boot_or_clock_epoch_changed")
    if sequence["qc"]["packet_reordered"] or sequence["qc"]["sample_reordered"]:
        continuity_reasons.append("raw_sequence_reordered")
    if sequence["qc"]["timestamp_reordered"]:
        continuity_reasons.append("raw_device_timestamp_reordered")
    if sequence["qc"]["epoch_changes"]:
        continuity_reasons.append("raw_clock_epoch_changed")
    if any(
        snapshot.get("last_error_code", 0) not in (0, None)
        or snapshot.get("acquisition_state") == "error"
        or bool((_int_field(snapshot, "status_flags") or 0) & 4)
        for snapshot in cast(list[JSON], status["snapshots"])
    ):
        continuity_reasons.append("fatal_or_error_status_observed")
    recovery_target_ok = all(record["recovery_target_10s"] for record in recovery_records)
    if mode == "recovery" and not recovery_target_ok:
        continuity_reasons.append("identity_config_revalidation_missing_or_over_10s")
    if sequence["unattributed_gap_count"]:
        continuity_reasons.append("unattributed_sequence_gap")
    continuity_proven = stable_identity and config_consistent and boot_epoch_consistent and not continuity_reasons
    epoch_decision = "retain_existing_epoch" if continuity_proven else "start_new_processed_epoch_and_clock_map"
    loss_attribution = _loss_attribution(
        status=status,
        packet_flags=packet_flags,
        cdc=cdc,
        sequence=sequence,
        mode=mode,
    )
    return {
        "node": node_name,
        "raw_sha256": raw_hash,
        "events_sha256": _sha256(events_path),
        "event_type_counts": dict(Counter(str(event.get("event")) for event in events)),
        "connect_events": _sorted_events(events, "connect"),
        "reconnect_events": _sorted_events(events, "reconnect"),
        "disconnect_events": _sorted_events(events, "disconnect"),
        "identity_config_snapshots": configs,
        "status": status,
        "packet_flags": packet_flags,
        "cdc": cdc,
        "outage_intervals": intervals,
        "recovery_records": recovery_records,
        "sequence": sequence,
        "high_water": {
            "sensor_fifo_high_water": {
                "value": None,
                "observable": False,
                "reason": "No sensor FIFO occupancy high-water field exists in the frozen M1 status contract.",
            },
            "acquisition_buffer_high_water_samples": {
                "reported_values": status["field_values"].get(
                    "acquisition_buffer_high_water_samples", []
                ),
                "max_reported": max(
                    status["field_values"].get("acquisition_buffer_high_water_samples", [0]),
                    default=0,
                ),
                "observable": False,
                "reason": (
                    "Current firmware publishes a hardcoded 0U; sample_queue.c maintains "
                    "but does not export the actual high-water value."
                ),
            },
            "tx_queue_high_water_packets": {
                "status_values": status["field_values"].get("transport_queue_high_water_packets", []),
                "status_boot_cumulative_max": max(
                    status["field_values"].get("transport_queue_high_water_packets", [0]),
                    default=0,
                ),
                "cdc_boot_cumulative_max": cdc.get("maxima", {}).get("tx_queue_high_water", 0),
                "run_peak_exact": None,
                "observable": True,
            },
        },
        "loss_attribution": loss_attribution,
        "continuity": {
            "identity_stable": stable_identity and config_consistent,
            "boot_and_clock_epoch_stable": boot_epoch_consistent,
            "fatal_or_reset_evidence_absent": "fatal_or_error_status_observed" not in continuity_reasons,
            "raw_order_clean": not bool(
                sequence["qc"]["packet_reordered"]
                or sequence["qc"]["sample_reordered"]
                or sequence["qc"]["timestamp_reordered"]
            ),
            "continuity_proven": continuity_proven,
            "epoch_decision": epoch_decision,
            "reasons": continuity_reasons,
        },
    }


def check_plan_parameters(config: JSON) -> JSON:
    mode = config.get("mode")
    expected_by_mode: dict[object, JSON] = {
        "pressure": {
            "seconds": 90.0,
            "callback_delay_ms": 8.0,
            "disconnect_a_after_s": None,
            "disconnect_b_after_s": None,
            "disconnect_hold_s": 3.0,
        },
        "recovery": {
            "seconds": 55.0,
            "callback_delay_ms": 0.0,
            "disconnect_a_after_s": 35.0,
            "disconnect_b_after_s": 15.0,
            "disconnect_hold_s": 3.0,
        },
        "bench": {
            "seconds": 1800.0,
            "callback_delay_ms": 0.0,
            "disconnect_a_after_s": None,
            "disconnect_b_after_s": None,
            "disconnect_hold_s": 3.0,
        },
    }
    if mode not in expected_by_mode:
        raise ValueError(f"unsupported M1 transport experiment mode: {mode!r}")
    expected = expected_by_mode[mode]
    actual = {name: config.get(name) for name in expected}
    mismatches = [name for name in expected if actual[name] != expected[name]]
    return {"expected": expected, "actual": actual, "pass": not mismatches, "mismatches": mismatches}


def _manifest_check(run_dir: Path, session: JSON, node_names: tuple[str, ...]) -> JSON:
    if not session:
        return {
            "pass": False,
            "reason": "session.json is absent because the recorder did not complete the capture",
        }
    streams = session.get("streams")
    if not isinstance(streams, list):
        return {"pass": False, "reason": "session.json has no streams list"}
    results: dict[str, JSON] = {}
    for node_name in node_names:
        stream = next(
            (cast(JSON, value) for value in streams if isinstance(value, dict) and value.get("node_id") == node_name),
            None,
        )
        if stream is None:
            results[node_name] = {"pass": False, "reason": "manifest stream missing"}
            continue
        raw_rel = stream.get("raw_path")
        events_rel = stream.get("transport_events_path")
        raw_path = run_dir / str(raw_rel)
        events_path = run_dir / str(events_rel)
        raw_hash = _sha256(raw_path)
        events_hash = _sha256(events_path)
        results[node_name] = {
            "pass": raw_hash == stream.get("raw_sha256") and events_hash == stream.get("transport_events_sha256"),
            "raw_manifest_sha256": stream.get("raw_sha256"),
            "raw_actual_sha256": raw_hash,
            "events_manifest_sha256": stream.get("transport_events_sha256"),
            "events_actual_sha256": events_hash,
        }
    return {"pass": all(value.get("pass") is True for value in results.values()), "nodes": results}


def _write_hash_manifest(run_dir: Path) -> Path:
    path = run_dir / "SHA256SUMS.txt"
    files = sorted(
        file
        for file in run_dir.rglob("*")
        if file.is_file() and file.name != path.name
    )
    with path.open("x", encoding="utf-8") as stream:
        for file in files:
            stream.write(f"{_sha256(file)}  {file.relative_to(run_dir).as_posix()}\n")
    return path


def _write_report(run_dir: Path, audit: JSON) -> None:
    lines = [
        "# Independent M1 Transport Experiment Report",
        "",
        f"- Mode: `{audit['run_config'].get('mode')}`",
        f"- Session: `{audit['run_config'].get('session_id')}`",
        f"- Predeclared plan SHA-256: `{audit['predeclared_plan_sha256']}`",
        f"- Plan parameters unchanged: **{audit['plan_parameter_check']['pass']}**",
        f"- Recorder produced a completed session: **{audit['session_present']}**",
        f"- Recorder error: `{audit['run_result'].get('error')}`",
        f"- Raw unchanged during offline audit: **{audit['raw_unchanged_during_audit']}**",
        f"- Manifest hashes verify: **{audit['manifest_check']['pass']}**",
        "",
        "Raw BLE streams are immutable inputs. No result below changes a packet, "
        "inserts a sample, resamples, interpolates, or changes the frozen acceptance thresholds.",
        "",
        "## Node results",
        "",
        "| Node | packets | samples | missing packets | missing samples | FIFO overrun | "
        "acquisition queue overrun | transport backpressure | unattributed gaps | epoch decision |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for node_name in ("A", "B"):
        node = audit["nodes"][node_name]
        qc = node["sequence"]["qc"]
        status_deltas = node["status"]["cumulative_deltas_initial_to_final"]
        lines.append(
            (
                "| {node} | {packets} | {samples} | {missing_packets} | {missing_samples} | "
                "{fifo} | {queue} | {transport} | {unattributed} | `{epoch}` |"
            ).format(
                node=node_name,
                packets=qc["packets_decoded"],
                samples=qc["samples_decoded"],
                missing_packets=qc["packets_missing"],
                missing_samples=qc["samples_missing"],
                fifo=status_deltas.get("sensor_fifo_overruns", 0),
                queue=status_deltas.get("firmware_queue_overruns", 0),
                transport=status_deltas.get("transport_backpressure_events", 0),
                unattributed=node["sequence"]["unattributed_gap_count"],
                epoch=node["continuity"]["epoch_decision"],
            )
        )
    lines.extend(["", "## High-water observability", ""])
    for node_name in ("A", "B"):
        high_water = audit["nodes"][node_name]["high_water"]
        lines.extend(
            [
                f"- Node {node_name}: boot-cumulative TX queue high-water is "
                f"`{high_water['tx_queue_high_water_packets']['status_boot_cumulative_max']}` "
                "packets from status and "
                f"`{high_water['tx_queue_high_water_packets']['cdc_boot_cumulative_max']}` "
                "from CDC. This is not a peak attributable to this host run.",
                f"  Acquisition queue high-water field reports "
                f"`{high_water['acquisition_buffer_high_water_samples']['max_reported']}` but is "
                "**not observable** in this firmware image because it is hardcoded `0U`; "
                "the actual `sample_queue.c` high-water is not exported.",
                "  Sensor FIFO occupancy high-water is not part of the frozen status contract.",
            ]
        )
    lines.extend(["", "## BLE recovery timing", ""])
    for node_name in ("A", "B"):
        records = audit["nodes"][node_name]["recovery_records"]
        if not records:
            lines.append(f"- Node {node_name}: no planned recovery interval recorded.")
            continue
        for index, record in enumerate(records, start=1):
            lines.append(
                f"- Node {node_name}, recovery {index}: link unavailable "
                f"`{record['link_unavailable_ns'] / 1e9:.6f}` s; telemetry unavailable "
                f"`{(record['telemetry_unavailable_ns'] or 0) / 1e9:.6f}` s; "
                f"identity/config revalidation within 10 s: **{record['recovery_target_10s']}**."
            )
    lines.extend(
        [
            "",
            "## Attribution and continuity rules",
            "",
            "Every missing packet/sample is listed in `sequence_gaps.json` with stream offset, "
            "previous/current sequence, packet flags, connection, and attribution evidence. "
            "A gap without packet-flag or planned link-boundary evidence is marked "
            "`unattributed`; it is not silently assigned to BLE.",
            "",
            "The complete per-node event/QC/status/CDC evidence is in `offline_audit.json`. "
            "`SHA256SUMS.txt` covers every artifact in this run directory except itself.",
        ]
    )
    (run_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--overwrite-derived", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    run_dir: Path = args.run_dir
    config = _read_json(run_dir / "run_config.json")
    session_path = run_dir / "session.json"
    session = _read_json(session_path) if session_path.is_file() else {}
    control_events = _read_ndjson(run_dir / "experiment_control.ndjson")
    run_result = _read_json(run_dir / "run_result.json")
    run_end_ns = _int_field(run_result, "ended_monotonic_ns") or max(
        (_event_time(event) or 0 for event in control_events),
        default=0,
    )
    plan_copy = run_dir / str(config.get("predeclared_plan_copy", "PREDECLARED_PLAN.md"))
    plan_hash = _sha256(plan_copy)
    node_names = ("A", "B")
    nodes = {
        node_name: _node_analysis(
            run_dir,
            node_name,
            control_events,
            str(config.get("mode")),
            run_end_ns,
        )
        for node_name in node_names
    }
    audit: JSON = {
        "schema": "kineimu.m1.transport-experiment-audit/0.1",
        "run_directory": str(run_dir),
        "run_config": config,
        "run_result": run_result,
        "session_present": session_path.is_file(),
        "predeclared_plan_sha256": plan_hash,
        "predeclared_plan_hash_matches_run_config": plan_hash == config.get("predeclared_plan_sha256"),
        "plan_parameter_check": check_plan_parameters(config),
        "control_event_count": len(control_events),
        "control_event_type_counts": dict(Counter(str(event.get("event")) for event in control_events)),
        "manifest_check": _manifest_check(run_dir, session, node_names),
        "raw_unchanged_during_audit": all(
            node["sequence"]["raw_unchanged_during_audit"] for node in nodes.values()
        ),
        "nodes": nodes,
        "audit_notes": [
            "Raw BLE files were opened read-only during this audit.",
            "Acquisition queue high-water is reported as non-observable because current firmware "
            "publishes hardcoded 0U while sample_queue.c maintains an unexported value.",
            "Formal 30-minute acceptance thresholds were not changed by this audit.",
        ],
    }
    if not audit["predeclared_plan_hash_matches_run_config"]:
        raise ValueError("predeclared plan copy hash does not match run_config.json")
    if args.overwrite_derived:
        for derived_path in (
            run_dir / "sequence_gaps.json",
            run_dir / "offline_audit.json",
            run_dir / "REPORT.md",
            run_dir / "SHA256SUMS.txt",
        ):
            if derived_path.exists():
                derived_path.unlink()
    _write_json(
        run_dir / "sequence_gaps.json",
        {
            "schema": "kineimu.m1.transport-sequence-gaps/0.1",
            "raw_unchanged_during_audit": audit["raw_unchanged_during_audit"],
            "nodes": {
                node_name: {
                    "all_sequence_issues": node["sequence"]["all_sequence_issues"],
                    "missing_sequence_gaps": node["sequence"]["missing_sequence_gaps"],
                }
                for node_name, node in nodes.items()
            },
        },
    )
    _write_json(run_dir / "offline_audit.json", audit)
    _write_report(run_dir, audit)
    _write_hash_manifest(run_dir)
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
