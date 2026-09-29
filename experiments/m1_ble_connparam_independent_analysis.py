"""Independently recompute the locked connection-parameter matrix from raw files.

This reader does not use ``matrix_audit.json`` or modify capture files. It reads
the matrix index, raw per-run CDC bytes, append-only KIMU records, and event
sidecars, then writes one derived JSON report when ``--output-json`` is given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import struct
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kineimu_shoulder.io.m1_packet import NodeId, ProtocolError, decode_sample_packet

JSON = dict[str, Any]
TARGET = (15_000, 0, 420_000)
ACTIVE_SECONDS = 15.0
BUCKETS_US = (
    (0, 1_000, "<1 ms"),
    (1_000, 2_500, "1–<2.5 ms"),
    (2_500, 5_000, "2.5–<5 ms"),
    (5_000, 10_000, "5–<10 ms"),
    (10_000, 25_000, "10–<25 ms"),
    (25_000, 50_000, "25–<50 ms"),
    (50_000, 100_000, "50–<100 ms"),
    (100_000, None, "≥100 ms"),
)
EXPECTED_BLOCKS = (
    ("OFF", ("a_only", "b_only", "dual_b_to_a", "dual_a_to_b")),
    ("ON", ("b_only", "dual_a_to_b", "a_only", "dual_b_to_a")),
    ("ON", ("dual_b_to_a", "a_only", "dual_a_to_b", "b_only")),
    ("OFF", ("dual_a_to_b", "dual_b_to_a", "b_only", "a_only")),
)
EXPECTED_ORDER = tuple(condition for _, block in EXPECTED_BLOCKS for condition in block)
NODE_ID = {"A": NodeId.A, "B": NodeId.B}
FIRST_NODE = {"dual_a_to_b": "A", "dual_b_to_a": "B"}
M1_SERVICE_UUID = "f7d20001-4b49-4e45-494d-552d53484c44"
EXPECTED_HARDWARE_ID = {"A": 1, "B": 2}
TX_PREFIX = re.compile(r"Node (?P<node>[AB]): tx_diag (?P<body>.*)$")
LINK_PREFIX = re.compile(r"Node (?P<node>[AB]): BLE link event=(?P<event>[a-z_]+) (?P<body>.*)$")
REQUEST_PREFIX = re.compile(r"Node (?P<node>[AB]): conn_param_request (?P<body>.*)$")
TOKEN = re.compile(r"(?P<name>[a-z_]+)=(?P<value>[^\s]+)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> JSON:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def verify_manifest(root: Path) -> JSON:
    path = root / "SHA256SUMS.txt"
    entries: list[tuple[str, str]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            expected, relative = line.split("  ", 1)
        except ValueError as error:
            raise ValueError(f"invalid SHA256SUMS.txt line {line_number}") from error
        entries.append((expected.lower(), relative))
    missing: list[str] = []
    mismatched: list[str] = []
    listed = {relative for _, relative in entries}
    for expected, relative in entries:
        file_path = root / Path(relative)
        if not file_path.is_file():
            missing.append(relative)
        elif sha256(file_path) != expected:
            mismatched.append(relative)
    actual = {
        file_path.relative_to(root).as_posix()
        for file_path in root.rglob("*")
        if file_path.is_file() and file_path != path
    }
    return {
        "path": str(path),
        "sha256": sha256(path),
        "entries": len(entries),
        "missing": missing,
        "mismatched": mismatched,
        "unlisted": sorted(actual - listed),
        "listed_files_missing_from_disk": sorted(listed - actual),
        "valid": not (missing or mismatched or actual - listed or listed - actual),
    }


def raw_input_hashes(root: Path) -> dict[str, str]:
    extensions = {".kimu", ".ndjson", ".bin"}
    selected = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix == ".kimu" or path.name.endswith(".events.ndjson") or path.name.endswith(".cdc.bin"):
            selected.append(path)
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(selected)
        if path.suffix in extensions or path.name.endswith(".events.ndjson") or path.name.endswith(".cdc.bin")
    }


def sequence_delta(previous: int | None, current: int) -> tuple[int, int, int, int]:
    """Return updated previous, missing, duplicate and reordered counts."""

    if previous is None:
        return current, 0, 0, 0
    distance = (current - previous) & 0xFFFF_FFFF
    if distance == 0:
        return previous, 0, 1, 0
    if distance >= 0x8000_0000:
        return previous, 0, 0, 1
    return current, distance - 1, 0, 0


def decode_raw_capture(path: Path, node: str) -> JSON:
    data = path.read_bytes()
    offset = 0
    records_seen = 0
    valid_packets = 0
    samples_decoded = 0
    decode_errors = 0
    crc_errors = 0
    framing_errors = 0
    wrong_node = 0
    packet_missing = packet_duplicates = packet_reordered = 0
    sample_missing = sample_duplicates = sample_reordered = 0
    epoch_changes = 0
    previous_packet: int | None = None
    previous_sample: int | None = None
    previous_epoch: int | None = None
    payload_lengths: Counter[int] = Counter()
    record_lengths: Counter[int] = Counter()
    expected_node = NODE_ID[node]

    while offset < len(data):
        if len(data) - offset < 12:
            framing_errors += 1
            break
        payload_length = struct.unpack_from("<I", data, offset)[0]
        if payload_length > 512:
            framing_errors += 1
            break
        record_length = 12 + payload_length
        if len(data) - offset < record_length:
            framing_errors += 1
            break
        payload = data[offset + 12 : offset + record_length]
        records_seen += 1
        payload_lengths[payload_length] += 1
        record_lengths[record_length] += 1
        offset += record_length
        try:
            packet = decode_sample_packet(payload)
        except ProtocolError as error:
            decode_errors += 1
            crc_errors += int("CRC-32C" in str(error))
            continue
        if packet.node_id is not expected_node:
            wrong_node += 1
            continue
        valid_packets += 1
        if previous_epoch is None:
            previous_epoch = packet.clock_epoch
        elif packet.clock_epoch != previous_epoch:
            epoch_changes += 1
            previous_epoch = packet.clock_epoch
            previous_packet = None
            previous_sample = None
        previous_packet, missing, duplicates, reordered = sequence_delta(
            previous_packet, packet.packet_sequence
        )
        packet_missing += missing
        packet_duplicates += duplicates
        packet_reordered += reordered
        for sample in packet.samples:
            samples_decoded += 1
            previous_sample, missing, duplicates, reordered = sequence_delta(
                previous_sample, sample.sequence
            )
            sample_missing += missing
            sample_duplicates += duplicates
            sample_reordered += reordered

    return {
        "path": str(path),
        "sha256": sha256(path),
        "bytes": len(data),
        "records_seen": records_seen,
        "valid_packets": valid_packets,
        "samples_decoded": samples_decoded,
        "decode_errors": decode_errors,
        "crc_errors": crc_errors,
        "framing_errors": framing_errors,
        "wrong_node_packets": wrong_node,
        "packet_sequence_gaps": packet_missing,
        "packet_duplicates": packet_duplicates,
        "packet_reordered": packet_reordered,
        "sample_sequence_gaps": sample_missing,
        "sample_duplicates": sample_duplicates,
        "sample_reordered": sample_reordered,
        "clock_epoch_changes": epoch_changes,
        "payload_length_counts": dict(sorted(payload_lengths.items())),
        "outer_record_length_counts": dict(sorted(record_lengths.items())),
        "parsed_bytes": offset,
        "trailing_bytes": len(data) - offset,
    }


def parse_tx_snapshot(body: str, line_number: int) -> JSON:
    raw = {match.group("name"): match.group("value") for match in TOKEN.finditer(body)}
    errors: list[str] = []
    fields: JSON = {"line": line_number, "raw": raw}
    scalar_keys = (
        "boot", "generation", "calls", "accepted", "final_fail", "packet_drops",
        "return_last", "enomem", "eagain", "retries", "window_owned", "window_full",
        "wait_us", "completed", "cancelled", "callbacks_stale", "callbacks_cancelled",
        "callbacks_unexpected", "age_count", "saturated",
    )
    for key in scalar_keys:
        value = raw.get(key)
        try:
            fields[key] = int(value) if value is not None else None
        except ValueError:
            fields[key] = None
            errors.append(f"invalid {key}={value}")
        if value is None:
            errors.append(f"missing {key}")

    for key in ("schedule_fail", "schedule_last", "inflight"):
        pieces = raw.get(key, "").split("/")
        if len(pieces) != 2:
            fields[key] = None
            errors.append(f"invalid {key}")
        else:
            try:
                fields[key] = [int(piece) for piece in pieces]
            except ValueError:
                fields[key] = None
                errors.append(f"invalid {key}")

    age = raw.get("age_us", "").split("/")
    if len(age) == 4:
        try:
            fields["age_us"] = [int(piece) for piece in age]
        except ValueError:
            fields["age_us"] = None
            errors.append("invalid age_us")
    else:
        fields["age_us"] = None
        errors.append("invalid age_us")

    bins = raw.get("age_bins", "").split(",")
    try:
        parsed_bins = [int(piece) for piece in bins]
        if len(parsed_bins) != 8:
            raise ValueError
        fields["age_bins"] = parsed_bins
    except ValueError:
        fields["age_bins"] = None
        errors.append("invalid age_bins")

    return_counts: dict[str, int] = {}
    for item in raw.get("return_counts", "").split(","):
        if not item or item == "none":
            continue
        try:
            code, count = item.split(":", 1)
            return_counts[str(int(code))] = int(count)
        except ValueError:
            errors.append(f"invalid return_counts item {item}")
    fields["return_counts"] = return_counts
    fields["parse_errors"] = errors
    return fields


def parse_cdc(path: Path, node: str) -> JSON:
    data = path.read_bytes() if path.is_file() else b""
    lines = data.decode("utf-8", errors="replace").splitlines()
    tx: list[JSON] = []
    links: list[JSON] = []
    requests: list[JSON] = []
    for line_number, line in enumerate(lines, start=1):
        match = TX_PREFIX.search(line)
        if match is not None and match.group("node") == node:
            tx.append(parse_tx_snapshot(match.group("body"), line_number))
            continue
        match = LINK_PREFIX.search(line)
        if match is not None and match.group("node") == node:
            fields = {item.group("name"): item.group("value") for item in TOKEN.finditer(match.group("body"))}
            try:
                tuple_value = (
                    int(fields["interval_us"]),
                    int(fields["latency"]),
                    int(fields["supervision_timeout_us"]),
                )
            except (KeyError, ValueError):
                tuple_value = None
            links.append({"line": line_number, "event": match.group("event"), "fields": fields, "tuple": tuple_value})
            continue
        match = REQUEST_PREFIX.search(line)
        if match is not None and match.group("node") == node:
            fields = {item.group("name"): item.group("value") for item in TOKEN.finditer(match.group("body"))}
            requests.append({"line": line_number, "fields": fields})
    return {
        "path": str(path),
        "sha256": sha256(path) if path.is_file() else None,
        "bytes": len(data),
        "line_count": len(lines),
        "tx_snapshot_count": len(tx),
        "tx_snapshots": tx,
        "link_events": links,
        "parameter_request_logs": requests,
        "last_valid_link_tuple": next((item["tuple"] for item in reversed(links) if item["tuple"] is not None), None),
    }


def delta(before: Any, after: Any) -> int | None:
    if not isinstance(before, int) or not isinstance(after, int) or after < before:
        return None
    return after - before


def percentile_bucket(bins: list[int] | None, quantile: float) -> JSON | None:
    if bins is None:
        return None
    total = sum(bins)
    if total <= 0:
        return None
    rank = math.ceil(total * quantile)
    cumulative = 0
    for index, count in enumerate(bins):
        cumulative += count
        if cumulative >= rank:
            low, high, label = BUCKETS_US[index]
            return {
                "rank": rank,
                "sample_count": total,
                "bucket_index": index,
                "lower_inclusive_us": low,
                "upper_exclusive_us": high,
                "bucket": label,
            }
    return None


def diagnostic_summary(cdc: JSON, active_seconds: float) -> JSON:
    snapshots = cdc["tx_snapshots"]
    grouped: list[list[JSON]] = []
    group_key: tuple[Any, Any] | None = None
    for snapshot in snapshots:
        key = (snapshot.get("boot"), snapshot.get("generation"))
        if not grouped or key != group_key:
            grouped.append([])
            group_key = key
        grouped[-1].append(snapshot)

    counter_names = (
        "calls", "accepted", "final_fail", "packet_drops", "enomem", "eagain", "retries",
        "window_full", "wait_us", "completed", "cancelled", "callbacks_stale",
        "callbacks_cancelled", "callbacks_unexpected", "age_count",
    )
    segments: list[JSON] = []
    for index, group in enumerate(grouped, start=1):
        first, last = group[0], group[-1]
        counters = {name: delta(first.get(name), last.get(name)) for name in counter_names}
        schedule_first = first.get("schedule_fail")
        schedule_last = last.get("schedule_fail")
        counters["schedule_fail_initial"] = (
            delta(schedule_first[0], schedule_last[0])
            if isinstance(schedule_first, list) and isinstance(schedule_last, list)
            else None
        )
        counters["schedule_fail_retry"] = (
            delta(schedule_first[1], schedule_last[1])
            if isinstance(schedule_first, list) and isinstance(schedule_last, list)
            else None
        )
        initial_returns = first.get("return_counts", {})
        final_returns = last.get("return_counts", {})
        return_deltas = {
            code: delta(initial_returns.get(code, 0), final_returns.get(code, 0))
            for code in sorted(set(initial_returns) | set(final_returns))
        }
        first_bins, last_bins = first.get("age_bins"), last.get("age_bins")
        bins_delta = None
        if isinstance(first_bins, list) and isinstance(last_bins, list) and len(first_bins) == len(last_bins) == 8:
            values = [delta(a, b) for a, b in zip(first_bins, last_bins, strict=True)]
            if all(value is not None for value in values):
                bins_delta = [int(value) for value in values if value is not None]
        age_first, age_last = first.get("age_us"), last.get("age_us")
        age_total_delta = (
            delta(age_first[3], age_last[3])
            if isinstance(age_first, list) and isinstance(age_last, list)
            else None
        )
        enough = len(group) >= 2
        saturated = any(snapshot.get("saturated") == 1 for snapshot in group)
        parse_errors = [error for snapshot in group for error in snapshot.get("parse_errors", [])]
        exact = (
            enough
            and not saturated
            and not parse_errors
            and all(value is not None for value in counters.values())
        )
        segments.append({
            "segment_index": index,
            "boot_id": first.get("boot"),
            "connection_generation": first.get("generation"),
            "snapshot_count": len(group),
            "first_line": first.get("line"),
            "last_line": last.get("line"),
            "parse_errors": parse_errors,
            "saturated": saturated,
            "delta_quality": "exact" if exact else "incomplete_or_lower_bound",
            "counter_deltas": counters,
            "return_code_deltas": return_deltas,
            "completion_age_total_us_delta": age_total_delta,
            "completion_age_bucket_deltas": bins_delta,
        })

    def total_counter(name: str) -> int | None:
        values = [segment["counter_deltas"].get(name) for segment in segments]
        if not values or any(value is None for value in values):
            return None
        return sum(values)

    total_bins: list[int] | None = None
    if segments and all(segment["completion_age_bucket_deltas"] is not None for segment in segments):
        total_bins = [
            sum(segment["completion_age_bucket_deltas"][index] for segment in segments)
            for index in range(8)
        ]
    age_total = sum(
        segment["completion_age_total_us_delta"] for segment in segments
        if isinstance(segment["completion_age_total_us_delta"], int)
    ) if segments and all(isinstance(segment["completion_age_total_us_delta"], int) for segment in segments) else None
    accepted = total_counter("accepted")
    age_count = total_counter("age_count")
    retries = total_counter("retries")
    enomem = total_counter("enomem")
    eagain = total_counter("eagain")
    full = total_counter("window_full")
    wait_us = total_counter("wait_us")
    rates = {
        "retry_calls_per_active_second": retries / active_seconds if retries is not None and active_seconds else None,
        "enomem_per_active_second": enomem / active_seconds if enomem is not None and active_seconds else None,
        "eagain_per_active_second": eagain / active_seconds if eagain is not None and active_seconds else None,
        "full_window_events_per_active_second": full / active_seconds if full is not None and active_seconds else None,
        "full_window_wait_us_per_active_second": (
            wait_us / active_seconds if wait_us is not None and active_seconds else None
        ),
        "retry_calls_per_notification_submission": (
            retries / accepted if retries is not None and accepted else None
        ),
        "enomem_per_notification_submission": (
            enomem / accepted if enomem is not None and accepted else None
        ),
        "eagain_per_notification_submission": (
            eagain / accepted if eagain is not None and accepted else None
        ),
        "full_window_events_per_notification_submission": (
            full / accepted if full is not None and accepted else None
        ),
        "full_window_wait_us_per_notification_submission": (
            wait_us / accepted if wait_us is not None and accepted else None
        ),
    }
    return_codes: dict[str, int | None] = {}
    codes = sorted({code for segment in segments for code in segment["return_code_deltas"]})
    for code in codes:
        values = [segment["return_code_deltas"].get(code) for segment in segments]
        return_codes[code] = sum(values) if values and all(value is not None for value in values) else None
    all_segments_exact = bool(segments) and all(
        segment["delta_quality"] == "exact" for segment in segments
    )
    return {
        "snapshot_count": len(snapshots),
        "segment_count": len(segments),
        "delta_quality": "exact" if all_segments_exact else "incomplete_or_lower_bound",
        "segments": segments,
        "total_counter_deltas": {name: total_counter(name) for name in counter_names},
        "total_return_code_deltas": return_codes,
        "completion_age_total_us_delta": age_total,
        "completion_age_mean_us": age_total / age_count if age_total is not None and age_count else None,
        "completion_age_p50_bucket": percentile_bucket(total_bins, 0.50),
        "completion_age_p95_bucket": percentile_bucket(total_bins, 0.95),
        "completion_age_histogram_count": sum(total_bins) if total_bins is not None else None,
        "rates": rates,
    }


def read_events(path: Path) -> list[JSON]:
    events: list[JSON] = []
    if not path.is_file():
        return events
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def count_invalid_event_lines(path: Path) -> int:
    if not path.is_file():
        return 1
    invalid = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if not isinstance(item, dict):
            invalid += 1
    return invalid


def capture_quality(events: list[JSON], raw: JSON) -> JSON:
    callback_times = [
        int(event["callback_duration_ns"])
        for event in events
        if event.get("event") == "notify_callback_timing"
        and isinstance(event.get("callback_duration_ns"), int)
    ]
    notify_events = [event for event in events if event.get("event") == "notify"]
    crc_false = sum(event.get("crc_ok") is False for event in events)
    decode_false = sum(event.get("decode_ok") is False or event.get("event") == "decode_error" for event in events)
    sorted_callbacks = sorted(callback_times)
    callback_p95 = (
        sorted_callbacks[math.ceil(len(sorted_callbacks) * 0.95) - 1]
        if sorted_callbacks
        else None
    )
    return {
        "event_count": len(events),
        "notify_events": len(notify_events),
        "event_crc_false": crc_false,
        "event_decode_failures": decode_false,
        "callback_duration_count": len(callback_times),
        "callback_duration_min_ns": min(callback_times) if callback_times else None,
        "callback_duration_p50_ns": statistics.median(callback_times) if callback_times else None,
        "callback_duration_p95_ns": callback_p95,
        "callback_duration_max_ns": max(callback_times) if callback_times else None,
        "raw_decode_errors": raw["decode_errors"],
        "raw_crc_errors": raw["crc_errors"],
        "raw_framing_errors": raw["framing_errors"],
        "wrong_node_packets": raw["wrong_node_packets"],
        "raw_packet_sequence_gaps": raw["packet_sequence_gaps"],
        "raw_sample_sequence_gaps": raw["sample_sequence_gaps"],
    }


def safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator > 0 else None


def has_parameter_request(entry: JSON, *, mode: str, call: str, api_rc: str) -> bool:
    return any(
        log.get("fields", {}).get("mode") == mode
        and log.get("fields", {}).get("call") == call
        and log.get("fields", {}).get("api_rc") == api_rc
        for log in entry["request_logs"]
    )


def audit_run_timing_events(
    control_events: list[JSON],
    capture_events_by_node: dict[str, list[JSON]],
    *,
    active_nodes: list[str],
    settle_seconds: float,
    capture_seconds: float,
    connect_gatt_timeout_seconds: float,
    require_full_callback_span: bool = True,
) -> JSON:
    """Reconcile scan/connect/GATT/window/capture times from append-only events."""

    errors: list[str] = []
    nodes: JSON = {}

    def matching(event_name: str, node: str | None = None) -> list[JSON]:
        return [
            event
            for event in control_events
            if event.get("event") == event_name
            and (node is None or event.get("node") == node)
        ]

    settle_events = matching("connection_parameter_settle_complete")
    settle_ns_values = [
        event.get("host_monotonic_ns")
        for event in settle_events
        if isinstance(event.get("host_monotonic_ns"), int)
    ]
    settle_complete_ns = min(settle_ns_values) if settle_ns_values else None

    for node in active_nodes:
        node_errors: list[str] = []
        capture_errors: list[str] = []

        def add_capture_error(
            message: str,
            *,
            errors_for_node: list[str] = node_errors,
            capture_errors_for_node: list[str] = capture_errors,
        ) -> None:
            errors_for_node.append(message)
            capture_errors_for_node.append(message)

        def one(
            event_name: str,
            *,
            node_name: str = node,
            errors_for_node: list[str] = node_errors,
        ) -> JSON | None:
            records = matching(event_name, node_name)
            if len(records) != 1:
                errors_for_node.append(
                    f"Node {node_name} expected one {event_name} event, found {len(records)}"
                )
                return None
            return records[0]

        scan_start = one("ble_scan_start")
        scan_complete = one("ble_scan_complete")
        connect_start = one("ble_os_connect_start")
        connect_return = one("ble_os_connect_return")
        connect_total = one("ble_connect_total")
        gatt_discovery = one("ble_gatt_service_discovery")
        connected = one("peripheral_connected_event")
        telemetry_enabled = one("telemetry_notify_enabled")
        capture_window_records = matching("matrix_capture_window", node)
        capture_window_event = capture_window_records[0] if len(capture_window_records) == 1 else None
        mtu_event = one("ble_mtu_observed")
        gatt_reads = matching("ble_gatt_read_complete", node)
        gatt_notify_setup = matching("ble_gatt_notify_setup_complete", node)
        capture_events = capture_events_by_node.get(node, [])

        scan: JSON = {}
        if scan_start is not None and scan_complete is not None:
            address = scan_start.get("address")
            scan_duration_ns = scan_complete.get("duration_ns")
            timeout_s = scan_start.get("timeout_s")
            cleanup_grace_s = scan_start.get("cleanup_grace_s")
            service_uuid = str(scan_start.get("service_uuid", "")).lower()
            if service_uuid != M1_SERVICE_UUID:
                node_errors.append(f"Node {node} scan did not use the locked M1 service filter")
            if scan_complete.get("observed_address") != address:
                node_errors.append(f"Node {node} scan result address did not match the requested address")
            if str(scan_complete.get("address", "")).upper() != str(address).upper():
                node_errors.append(f"Node {node} scan completion did not retain the requested address")
            if not isinstance(scan_duration_ns, int):
                node_errors.append(f"Node {node} scan duration is missing")
                scan_duration_ns = 0
            if isinstance(timeout_s, (int, float)) and isinstance(cleanup_grace_s, (int, float)):
                if scan_duration_ns / 1_000_000_000 > timeout_s + cleanup_grace_s + 0.1:
                    node_errors.append(f"Node {node} filtered scan exceeded its timeout and cleanup grace")
            scan = {
                "address": address,
                "service_uuid": service_uuid,
                "timeout_s": timeout_s,
                "cleanup_grace_s": cleanup_grace_s,
                "duration_s": scan_duration_ns / 1_000_000_000,
                "started_host_monotonic_ns": scan_start.get("host_monotonic_ns"),
                "completed_host_monotonic_ns": scan_complete.get("host_monotonic_ns"),
            }

        connect_gatt: JSON = {}
        if connect_start is not None and connect_return is not None and connect_total is not None:
            start_ns = connect_start.get("host_monotonic_ns")
            return_ns = connect_return.get("host_monotonic_ns")
            scan_complete_ns = scan_complete.get("host_monotonic_ns") if scan_complete else None
            duration_ns = connect_total.get("duration_ns")
            if not isinstance(duration_ns, int):
                node_errors.append(f"Node {node} Windows connect/GATT duration is missing")
                duration_ns = 0
            duration_s = duration_ns / 1_000_000_000
            if connect_total.get("succeeded") is not True:
                node_errors.append(f"Node {node} Windows connect/GATT setup did not succeed")
            if str(connect_start.get("address", "")).upper() != str(scan_start.get("address", "")).upper():
                node_errors.append(f"Node {node} OS connect did not use the freshly scanned device address")
            if duration_s > connect_gatt_timeout_seconds:
                node_errors.append(f"Node {node} Windows connect/GATT setup exceeded its independent limit")
            if isinstance(start_ns, int) and isinstance(scan_complete_ns, int) and start_ns < scan_complete_ns:
                node_errors.append(f"Node {node} connect/GATT timer began before its filtered scan completed")
            connect_gatt = {
                "duration_s": duration_s,
                "start_host_monotonic_ns": start_ns,
                "return_host_monotonic_ns": return_ns,
                "os_connect_setup_s_before_gatt": (
                    connect_total.get("os_connect_setup_ns", 0) / 1_000_000_000
                ),
                "gatt_service_discovery_s": (
                    gatt_discovery.get("duration_ns", 0) / 1_000_000_000
                    if gatt_discovery is not None
                    else None
                ),
                "post_gatt_setup_s": connect_total.get("post_gatt_setup_ns", 0) / 1_000_000_000,
                "scan_charged_to_connect_limit": False,
            }
        if gatt_discovery is not None:
            if gatt_discovery.get("call_index") != 1:
                node_errors.append(f"Node {node} GATT service discovery was not the first recorded call")
            if not isinstance(gatt_discovery.get("duration_ns"), int):
                node_errors.append(f"Node {node} GATT service discovery duration is missing")

        parameter_window: JSON = {}
        if connected is not None:
            connected_ns = connected.get(
                "peripheral_event_host_monotonic_ns", connected.get("host_monotonic_ns")
            )
            complete_records = [
                event
                for event in settle_events
                if node in event.get("observed_duration_s_by_node", {})
            ]
            if not complete_records:
                node_errors.append(f"Node {node} is missing connection-event-relative settle completion")
            else:
                complete = min(
                    complete_records,
                    key=lambda event: event.get("host_monotonic_ns", 0),
                )
                observed_s = complete.get("observed_duration_s_by_node", {}).get(node)
                complete_ns = complete.get("host_monotonic_ns")
                if not isinstance(observed_s, (int, float)) or observed_s + 1e-9 < settle_seconds:
                    node_errors.append(
                        f"Node {node} parameter observation was shorter than {settle_seconds:.3f} s"
                    )
                if isinstance(connected_ns, int) and isinstance(complete_ns, int):
                    measured_s = (complete_ns - connected_ns) / 1_000_000_000
                    if measured_s + 1e-9 < settle_seconds:
                        node_errors.append(
                            f"Node {node} settle deadline did not span {settle_seconds:.3f} s from peripheral connect"
                        )
                else:
                    measured_s = None
                    node_errors.append(f"Node {node} connected-event timing is incomplete")
                window_end_ns = (
                    connected_ns + int(settle_seconds * 1_000_000_000)
                    if isinstance(connected_ns, int)
                    else None
                )
                raw_parameter_events = [
                    event for event in matching("peripheral_param_updated", node)
                    if isinstance(event.get("host_monotonic_ns"), int)
                    and isinstance(connected_ns, int)
                    and isinstance(window_end_ns, int)
                    and connected_ns <= event["host_monotonic_ns"] <= window_end_ns
                ]
                raw_callback_rows = [
                    {
                        "firmware_event": "param_updated",
                        "firmware_uptime_ms": event.get("firmware_uptime_ms"),
                        "host_monotonic_ns": event.get("host_monotonic_ns"),
                        "tuple": [event.get("interval_us"), event.get("latency"), event.get("supervision_timeout_us")],
                    }
                    for event in raw_parameter_events
                ]
                recorded_updates = complete.get("parameter_updates_by_node", {}).get(node, [])
                in_window_updates = [
                    item for item in recorded_updates
                    if isinstance(item.get("host_monotonic_ns"), int)
                    and isinstance(connected_ns, int)
                    and isinstance(window_end_ns, int)
                    and connected_ns <= item["host_monotonic_ns"] <= window_end_ns
                ]
                raw_parameter_projection = [
                    (item["firmware_uptime_ms"], tuple(item["tuple"])) for item in raw_callback_rows
                ]
                recorded_parameter_projection = [
                    (item.get("firmware_uptime_ms"), tuple(item.get(key) for key in (
                        "interval_us", "latency", "supervision_timeout_us"
                    )))
                    for item in in_window_updates
                    if item.get("firmware_event") == "param_updated"
                ]
                if raw_parameter_projection != recorded_parameter_projection:
                    node_errors.append(
                        f"Node {node} parameter-update callbacks do not reconcile with the complete-window snapshot"
                    )
                connected_tuple = connected.get("firmware_event_line", "")
                connected_match = LINK_PREFIX.search(str(connected_tuple))
                connected_fields = (
                    {item.group("name"): item.group("value") for item in TOKEN.finditer(connected_match.group("body"))}
                    if connected_match is not None
                    else {}
                )
                actual_window_rows = [
                    {
                        "event": "connected",
                        "firmware_uptime_ms": connected.get("peripheral_event_firmware_uptime_ms"),
                        "host_monotonic_ns": connected_ns,
                        "tuple": [
                            int(connected_fields[name]) if name in connected_fields else None
                            for name in ("interval_us", "latency", "supervision_timeout_us")
                        ],
                    }
                ] + [
                    {
                        "event": "param_updated",
                        "firmware_uptime_ms": event.get("firmware_uptime_ms"),
                        "host_monotonic_ns": event.get("host_monotonic_ns"),
                        "tuple": [event.get("interval_us"), event.get("latency"), event.get("supervision_timeout_us")],
                    }
                    for event in raw_parameter_events
                ]
                target_observed = any(
                    tuple(item["tuple"]) == TARGET
                    for item in actual_window_rows
                    if all(value is not None for value in item["tuple"])
                )
                if complete.get("target_observed_by_node", {}).get(node) is not target_observed:
                    node_errors.append(f"Node {node} target-tuple gate disagrees with the complete-window callbacks")
                parameter_window = {
                    "anchor": "firmware_cdc_peripheral_connected_event",
                    "connected_host_monotonic_ns": connected_ns,
                    "settle_complete_host_monotonic_ns": complete_ns,
                    "observed_duration_s": observed_s,
                    "measured_host_duration_s": measured_s,
                    "window_end_host_monotonic_ns": window_end_ns,
                    "target_observed": target_observed,
                    "callback_count": len(actual_window_rows),
                    "param_updated_callback_count": len(raw_parameter_events),
                    "callbacks": actual_window_rows,
                }

        capture: JSON = {}
        if telemetry_enabled is not None:
            telemetry_ns = telemetry_enabled.get("host_monotonic_ns")
            window_start_perf_ns = (
                capture_window_event.get("capture_start_perf_counter_ns")
                if capture_window_event is not None
                else None
            )
            window_end_perf_ns = (
                capture_window_event.get("capture_deadline_perf_counter_ns")
                if capture_window_event is not None
                else None
            )
            window_start_host_ns = (
                capture_window_event.get("capture_start_host_monotonic_ns")
                if capture_window_event is not None
                else None
            )
            window_end_host_ns = (
                capture_window_event.get("capture_deadline_host_monotonic_ns")
                if capture_window_event is not None
                else None
            )
            if capture_window_event is None:
                add_capture_error(
                    f"Node {node} expected one shared capture-window marker, "
                    f"found {len(capture_window_records)}; capture boundary is unauditable"
                )
            if capture_window_event is not None:
                if capture_window_event.get("anchor") != "shared_recorder_ready_barrier":
                    add_capture_error(f"Node {node} capture-window marker has an unexpected anchor")
                if capture_window_event.get("capture_clock_domain") != "perf_counter_ns":
                    add_capture_error(f"Node {node} capture-window marker has an unexpected callback clock domain")
                boundaries = (
                    window_start_perf_ns,
                    window_end_perf_ns,
                    window_start_host_ns,
                    window_end_host_ns,
                )
                if not all(isinstance(value, int) for value in boundaries):
                    add_capture_error(
                        f"Node {node} capture-window marker has incomplete clock-domain boundaries"
                    )
                else:
                    duration_ns = window_end_perf_ns - window_start_perf_ns
                    host_duration_ns = window_end_host_ns - window_start_host_ns
                    expected_duration_ns = round(capture_seconds * 1_000_000_000)
                    if (
                        capture_window_event.get("duration_ns") != duration_ns
                        or duration_ns != expected_duration_ns
                        or host_duration_ns != expected_duration_ns
                    ):
                        add_capture_error(
                            f"Node {node} recorded capture window does not equal the planned {capture_seconds:.3f} s"
                        )
                    if isinstance(settle_complete_ns, int) and window_start_host_ns < settle_complete_ns:
                        add_capture_error(
                            f"Node {node} capture window began before parameter settling completed"
                        )
                    if isinstance(telemetry_ns, int) and telemetry_ns > window_start_host_ns:
                        add_capture_error(
                            f"Node {node} telemetry notifications were enabled after the capture window began"
                        )
                    uncertainty_ns = capture_window_event.get("capture_clock_pair_uncertainty_ns")
                    if not isinstance(uncertainty_ns, int) or uncertainty_ns < 0:
                        add_capture_error(f"Node {node} capture-window marker has invalid clock-pair uncertainty")
                    elif uncertainty_ns > 10_000_000:
                        add_capture_error(
                            f"Node {node} capture-window clock-pair uncertainty exceeds 10 ms"
                        )
            callback_events = [
                event
                for event in capture_events
                if event.get("event") == "notify_callback_timing"
            ]
            accepted_callback_times: list[int] = []
            callbacks_outside_window = 0
            callbacks_missing_boundary_evidence = 0
            callback_admission_mismatches = 0
            for event in callback_events:
                callback_ns = event.get("capture_window_check_perf_counter_ns")
                claimed_accepted = event.get("capture_window_accepted")
                if not isinstance(callback_ns, int) or not isinstance(claimed_accepted, bool):
                    callbacks_missing_boundary_evidence += 1
                    continue
                if isinstance(window_start_perf_ns, int) and isinstance(window_end_perf_ns, int):
                    if event.get("capture_clock_domain") != "perf_counter_ns":
                        callback_admission_mismatches += 1
                    expected_accepted = window_start_perf_ns <= callback_ns < window_end_perf_ns
                    if claimed_accepted is not expected_accepted:
                        callback_admission_mismatches += 1
                    if expected_accepted:
                        accepted_callback_times.append(callback_ns)
                    else:
                        callbacks_outside_window += 1
                elif claimed_accepted:
                    callback_admission_mismatches += 1
                else:
                    callbacks_outside_window += 1

            if callbacks_missing_boundary_evidence:
                add_capture_error(
                    f"Node {node} has {callbacks_missing_boundary_evidence} notification callbacks without "
                    "capture-boundary timestamp/admission evidence"
                )
            if callback_admission_mismatches:
                add_capture_error(
                    f"Node {node} has {callback_admission_mismatches} callback admission flags that disagree "
                    "with the recorded capture window"
                )

            first_callback_ns = min(accepted_callback_times) if accepted_callback_times else None
            last_callback_ns = max(accepted_callback_times) if accepted_callback_times else None
            callback_span_s = (
                (last_callback_ns - first_callback_ns) / 1_000_000_000
                if isinstance(last_callback_ns, int) and isinstance(first_callback_ns, int)
                else None
            )
            if callback_span_s is None:
                add_capture_error(f"Node {node} has no accepted notification callbacks in the capture window")
            elif require_full_callback_span and callback_span_s + 0.1 < capture_seconds:
                add_capture_error(
                    f"Node {node} accepted notification callbacks do not span the {capture_seconds:.3f} s capture"
                )

            # Older runner output did not persist its shared deadline. This
            # lower-bound estimate is diagnostic only; it cannot establish
            # which callbacks were inside the actual window.
            earliest_possible_deadline_host_ns = None
            callbacks_after_earliest_deadline = 0
            if capture_window_event is None:
                telemetry_start_values = [
                    event.get("host_monotonic_ns")
                    for event in matching("telemetry_notify_enabled")
                    if isinstance(event.get("host_monotonic_ns"), int)
                ]
                if telemetry_start_values:
                    earliest_possible_deadline_host_ns = max(telemetry_start_values) + round(
                        capture_seconds * 1_000_000_000
                    )
                    callbacks_after_earliest_deadline = sum(
                        isinstance(event.get("callback_start_host_monotonic_ns"), int)
                        and event["callback_start_host_monotonic_ns"]
                        >= earliest_possible_deadline_host_ns
                        for event in callback_events
                    )
            capture = {
                "telemetry_enabled_host_monotonic_ns": telemetry_ns,
                "window_anchor": (
                    capture_window_event.get("anchor") if capture_window_event is not None else None
                ),
                "window_clock_domain": (
                    capture_window_event.get("capture_clock_domain")
                    if capture_window_event is not None
                    else None
                ),
                "window_start_perf_counter_ns": window_start_perf_ns,
                "window_deadline_perf_counter_ns": window_end_perf_ns,
                "window_start_host_monotonic_ns": window_start_host_ns,
                "window_deadline_host_monotonic_ns": window_end_host_ns,
                "clock_pair_uncertainty_ns": (
                    capture_window_event.get("capture_clock_pair_uncertainty_ns")
                    if capture_window_event is not None
                    else None
                ),
                "window_duration_ns": (
                    window_end_perf_ns - window_start_perf_ns
                    if isinstance(window_start_perf_ns, int) and isinstance(window_end_perf_ns, int)
                    else None
                ),
                "explicit_boundary_recorded": capture_window_event is not None,
                "callback_count": len(callback_events),
                "accepted_callback_count": len(accepted_callback_times),
                "callbacks_missing_boundary_evidence": callbacks_missing_boundary_evidence,
                "callback_admission_mismatches": callback_admission_mismatches,
                "callbacks_outside_recorded_window": callbacks_outside_window,
                "first_accepted_callback_perf_counter_ns": first_callback_ns,
                "last_accepted_callback_perf_counter_ns": last_callback_ns,
                "callback_span_s": callback_span_s,
                "callback_span_gate_required": require_full_callback_span,
                "planned_capture_seconds": capture_seconds,
                "earliest_possible_deadline_host_monotonic_ns_without_marker": (
                    earliest_possible_deadline_host_ns
                ),
                "callbacks_at_or_after_earliest_possible_deadline": callbacks_after_earliest_deadline,
            }

        config_reads = [
            event for event in capture_events
            if event.get("event") == "config" and event.get("source") == "read"
        ]
        if len(config_reads) != 1:
            node_errors.append(f"Node {node} expected one GATT-read identity/config event, found {len(config_reads)}")
        config_identity = config_reads[0] if len(config_reads) == 1 else {}
        expected_node_id = 1 if node == "A" else 2
        expected_hardware_id = EXPECTED_HARDWARE_ID[node]
        if config_identity.get("node_id") != expected_node_id:
            node_errors.append(f"Node {node} GATT identity read has the wrong node_id")
        if config_identity.get("hardware_device_id") != expected_hardware_id:
            node_errors.append(f"Node {node} GATT identity read does not match the locked hardware device ID")
        if config_identity.get("firmware_git_commit") != "270911756c227a20feb18df71edad7ad4544aedb":
            node_errors.append(f"Node {node} GATT identity read does not match the matched firmware source commit")
        mtu_records = [event for event in capture_events if event.get("event") == "mtu"]
        if len(mtu_records) != 1 or mtu_records[0].get("accepted") is not True or mtu_records[0].get("mtu", 0) < 127:
            node_errors.append(f"Node {node} capture-side MTU validation did not meet the required 127 bytes")
        phase_reads = {
            phase: [event for event in gatt_reads if event.get("phase") == phase]
            for phase in ("identity", "status")
        }
        if not phase_reads["identity"] or not phase_reads["status"]:
            node_errors.append(f"Node {node} is missing timed identity or status GATT reads")
        phase_setup = {
            event.get("phase"): {
                "duration_ns": event.get("duration_ns"),
                "host_monotonic_ns": event.get("host_monotonic_ns"),
                "char_uuid": event.get("char_uuid"),
            }
            for event in gatt_notify_setup
        }

        if not gatt_reads:
            node_errors.append(f"Node {node} has no timed GATT identity/status reads")
        setup_errors = [error for error in node_errors if error not in capture_errors]
        nodes[node] = {
            "scan": scan,
            "connect_gatt": connect_gatt,
            "firmware_connected_event": (
                {
                    "host_monotonic_ns": connected.get(
                        "peripheral_event_host_monotonic_ns", connected.get("host_monotonic_ns")
                    ),
                    "firmware_uptime_ms": connected.get("peripheral_event_firmware_uptime_ms"),
                }
                if connected is not None
                else None
            ),
            "identity_gatt_reads": {
                "count": len(gatt_reads),
                "durations_ns": [event.get("duration_ns") for event in gatt_reads],
                "host_monotonic_ns": [event.get("host_monotonic_ns") for event in gatt_reads],
                "by_phase": {
                    phase: [
                        {"duration_ns": event.get("duration_ns"), "host_monotonic_ns": event.get("host_monotonic_ns")}
                        for event in phase_events
                    ]
                    for phase, phase_events in phase_reads.items()
                },
            },
            "gatt_notify_setup_by_phase": phase_setup,
            "mtu": {"control_event": mtu_event, "capture_event": mtu_records[0] if mtu_records else None},
            "identity_config_read": config_identity,
            "parameter_window": parameter_window,
            "capture": capture,
            "setup_valid": not setup_errors,
            "capture_boundary_valid": not capture_errors,
            "capture_errors": capture_errors,
            "errors": node_errors,
        }
        errors.extend(node_errors)

    capture_markers = [
        matching("matrix_capture_window", node)[0]
        for node in active_nodes
        if len(matching("matrix_capture_window", node)) == 1
    ]
    if len(capture_markers) == len(active_nodes) and active_nodes:
        boundaries = {
            (
                event.get("capture_start_perf_counter_ns"),
                event.get("capture_deadline_perf_counter_ns"),
                event.get("capture_start_host_monotonic_ns"),
                event.get("capture_deadline_host_monotonic_ns"),
            )
            for event in capture_markers
        }
        if len(boundaries) != 1:
            errors.append("Active nodes did not share the same recorder capture window")

    return {
        "valid": not errors,
        "expected_m1_service_uuid": M1_SERVICE_UUID,
        "settle_seconds": settle_seconds,
        "capture_seconds": capture_seconds,
        "connect_gatt_limit_seconds": connect_gatt_timeout_seconds,
        "errors": errors,
        "nodes": nodes,
    }


def _row_metric(row: JSON, metric: str) -> float | None:
    if metric == "completion_age_p95_bucket_index":
        value = row.get("tx_diagnostics", {}).get("completion_age_p95_bucket")
        raw = value.get("bucket_index") if isinstance(value, dict) else None
    elif metric == "retry_calls_per_notification_submission":
        raw = row.get("tx_diagnostics", {}).get("rates", {}).get(metric)
    elif metric == "full_window_wait_us_per_notification_submission":
        raw = row.get("tx_diagnostics", {}).get("rates", {}).get(metric)
    else:
        raise ValueError(f"unknown mechanism metric {metric}")
    return float(raw) if isinstance(raw, (int, float)) and math.isfinite(raw) else None


def classify_predeclared_outcome(
    runs: list[JSON], *, manipulation_realized: bool, data_complete: bool
) -> JSON:
    """Apply the locked v2 transport and mechanism thresholds to raw-derived runs."""

    transport_threshold = 0.90
    mechanism_metrics = (
        "completion_age_p95_bucket_index",
        "retry_calls_per_notification_submission",
        "full_window_wait_us_per_notification_submission",
    )
    order_comparisons: JSON = {}
    comparison_data_complete = True

    def median_ratio(selected: list[JSON], node: str) -> float | None:
        values = [run.get("nodes", {}).get(node, {}).get("dual_to_single_ratio") for run in selected]
        if len(values) != 2 or any(not isinstance(value, (int, float)) for value in values):
            return None
        return float(statistics.median([float(value) for value in values]))

    for order in FIRST_NODE:
        order_rows: JSON = {"nodes": {}}
        on_order = [run for run in runs if run["condition"] == order and run["mode"] == "ON"]
        off_order = [run for run in runs if run["condition"] == order and run["mode"] == "OFF"]
        if len(on_order) != 2 or len(off_order) != 2:
            comparison_data_complete = False
        for node in ("A", "B"):
            on_ratio = median_ratio(on_order, node)
            off_ratio = median_ratio(off_order, node)
            metric_comparisons: JSON = {}
            for metric in mechanism_metrics:
                on_values = [
                    _row_metric(run.get("nodes", {}).get(node, {}), metric)
                    for run in on_order
                ]
                off_values = [
                    _row_metric(run.get("nodes", {}).get(node, {}), metric)
                    for run in off_order
                ]
                if (
                    len(on_values) != 2
                    or len(off_values) != 2
                    or any(value is None for value in (*on_values, *off_values))
                ):
                    comparison_data_complete = False
                    on_median = off_median = None
                else:
                    on_median = float(statistics.median([value for value in on_values if value is not None]))
                    off_median = float(statistics.median([value for value in off_values if value is not None]))
                metric_comparisons[metric] = {
                    "on_values": on_values,
                    "off_values": off_values,
                    "on_median": on_median,
                    "off_median": off_median,
                    "improved": on_median < off_median if on_median is not None and off_median is not None else None,
                    "not_worsened": (
                        on_median <= off_median
                        if on_median is not None and off_median is not None
                        else None
                    ),
                    "not_improved": (
                        on_median >= off_median
                        if on_median is not None and off_median is not None
                        else None
                    ),
                }
            order_rows["nodes"][node] = {
                "on_dual_single_median": on_ratio,
                "off_dual_single_median": off_ratio,
                "on_ratio_does_not_exceed_off": (
                    on_ratio <= off_ratio if on_ratio is not None and off_ratio is not None else None
                ),
                "mechanism_metrics": metric_comparisons,
            }
        order_comparisons[order] = order_rows

    on_dual_runs = [
        run for run in runs if run["mode"] == "ON" and run["condition"] in FIRST_NODE
    ]
    all_on_dual_transport_met = len(on_dual_runs) == 4 and all(
        run.get("first_to_second_throughput_ratio") is not None
        and run["first_to_second_throughput_ratio"] >= transport_threshold
        and all(
            run.get("nodes", {}).get(node, {}).get("dual_to_single_ratio") is not None
            and run["nodes"][node]["dual_to_single_ratio"] >= transport_threshold
            for node in ("A", "B")
        )
        for run in on_dual_runs
    )
    all_on_dual_transport_below = len(on_dual_runs) == 4 and all(
        run.get("first_to_second_throughput_ratio") is not None
        and run["first_to_second_throughput_ratio"] < transport_threshold
        and all(
            run.get("nodes", {}).get(node, {}).get("dual_to_single_ratio") is not None
            and run["nodes"][node]["dual_to_single_ratio"] < transport_threshold
            for node in ("A", "B")
        )
        for run in on_dual_runs
    )
    on_dual_quality_clean = len(on_dual_runs) == 4 and all(
        row.get("tx_diagnostics", {}).get("delta_quality") == "exact"
        and
        isinstance(row.get("tx_diagnostics", {}).get("total_counter_deltas", {}).get("packet_drops"), int)
        and row["tx_diagnostics"]["total_counter_deltas"]["packet_drops"] == 0
        and all(
            row.get("capture_quality", {}).get(name) == 0
            for name in (
                "event_crc_false",
                "event_decode_failures",
                "raw_crc_errors",
                "raw_decode_errors",
                "raw_framing_errors",
            )
        )
        for run in on_dual_runs
        for row in run.get("nodes", {}).values()
    )

    pair_results = [
        node_result
        for order_result in order_comparisons.values()
        for node_result in order_result["nodes"].values()
    ]
    support_mechanism_gate = comparison_data_complete and all(
        all(metric["not_worsened"] is True for metric in node_result["mechanism_metrics"].values())
        and sum(metric["improved"] is True for metric in node_result["mechanism_metrics"].values()) >= 2
        for node_result in pair_results
    )
    not_supported_median_gate = comparison_data_complete and all(
        node_result["on_ratio_does_not_exceed_off"] is True
        and sum(metric["not_improved"] is True for metric in node_result["mechanism_metrics"].values()) >= 2
        for node_result in pair_results
    )
    support_gate = all_on_dual_transport_met and on_dual_quality_clean and support_mechanism_gate
    not_supported_gate = all_on_dual_transport_below and not_supported_median_gate

    reasons: list[str] = []
    if not manipulation_realized:
        reasons.append("The locked ON/OFF tuple contrast was not realized.")
    if not data_complete:
        reasons.append("Required scheduled run, capture, timing, control, or TX diagnostic data are incomplete.")
    if data_complete and manipulation_realized and not support_gate and not not_supported_gate:
        reasons.append(
            "The complete realized result does not meet either locked supported or not-supported threshold set."
        )
    if not manipulation_realized or not data_complete:
        label = "inconclusive"
    elif support_gate:
        label = "supported"
    elif not_supported_gate:
        label = "not supported"
    else:
        label = "inconclusive"

    return {
        "label": label,
        "classification_reasons": reasons,
        "transport_threshold": transport_threshold,
        "comparison_data_complete": comparison_data_complete,
        "gates": {
            "manipulation_realized": manipulation_realized,
            "data_complete": data_complete,
            "all_on_dual_transport_thresholds_met": all_on_dual_transport_met,
            "all_on_dual_transport_thresholds_below": all_on_dual_transport_below,
            "on_dual_tx_drops_and_capture_errors_zero": on_dual_quality_clean,
            "support_mechanism_gate_met": support_mechanism_gate,
            "not_supported_median_gate_met": not_supported_median_gate,
            "support_gate_met": support_gate,
            "not_supported_gate_met": not_supported_gate,
        },
        "comparisons_by_dual_order": order_comparisons,
    }


def audit_cdc_control_events(control_events: list[JSON], result: JSON) -> JSON:
    """Independently reconcile nonce-bound READY/ACK traffic and result summaries."""

    errors: list[str] = []
    ready_events = [event for event in control_events if event.get("event") == "conn_param_control_ready"]
    hello_events = [event for event in control_events if event.get("event") == "conn_param_control_hello_write"]
    writes = [event for event in control_events if event.get("event") == "conn_param_request_write"]
    acknowledgements = [event for event in control_events if event.get("event") == "conn_param_request_ack"]

    def transaction_key(event: JSON) -> tuple[Any, Any, Any]:
        return event.get("node"), event.get("session"), event.get("tx")

    writes_by_key: dict[tuple[Any, Any, Any], list[JSON]] = {}
    acks_by_key: dict[tuple[Any, Any, Any], list[JSON]] = {}
    for event in writes:
        writes_by_key.setdefault(transaction_key(event), []).append(event)
    for event in acknowledgements:
        acks_by_key.setdefault(transaction_key(event), []).append(event)

    transactions: list[JSON] = []
    for key, write_records in writes_by_key.items():
        ack_records = acks_by_key.get(key, [])
        node, session, tx = key
        if len(write_records) != 1 or len(ack_records) != 1:
            errors.append(
                f"CDC node={node} session={session} tx={tx} has {len(write_records)} writes and {len(ack_records)} ACKs"
            )
            continue
        write = write_records[0]
        ack = ack_records[0]
        command = str(write.get("command", ""))
        byte_count = write.get("byte_count")
        expected_byte_count = write.get("expected_byte_count")
        expected_command_bytes = len(command.encode("ascii")) + 1
        if (
            not isinstance(byte_count, int)
            or byte_count != expected_byte_count
            or byte_count != expected_command_bytes
        ):
            errors.append(f"CDC node={node} session={session} tx={tx} write was not complete")
        write_ns = write.get("host_monotonic_ns")
        ack_ns = ack.get("host_monotonic_ns")
        latency_ms = (
            (ack_ns - write_ns) / 1_000_000
            if isinstance(write_ns, int) and isinstance(ack_ns, int)
            else None
        )
        if latency_ms is None or latency_ms < 0 or latency_ms > 500:
            errors.append(f"CDC node={node} session={session} tx={tx} ACK missed the 500 ms transaction limit")
        if (
            ack.get("node_id") != write.get("node_id")
            or ack.get("session") != session
            or ack.get("tx") != tx
            or ack.get("requested") != write.get("requested")
            or ack.get("selected") != write.get("requested")
            or ack.get("rc") != 0
        ):
            errors.append(f"CDC node={node} session={session} tx={tx} ACK did not match the request exactly")
        transactions.append({
            "node": node,
            "node_id": write.get("node_id"),
            "session": session,
            "tx": tx,
            "requested": write.get("requested"),
            "selected": ack.get("selected"),
            "rc": ack.get("rc"),
            "byte_count": byte_count,
            "expected_byte_count": expected_byte_count,
            "write_host_monotonic_ns": write_ns,
            "ack_host_monotonic_ns": ack_ns,
            "ack_latency_ms": latency_ms,
        })
    for key in acks_by_key.keys() - writes_by_key.keys():
        errors.append(f"CDC ACK has no matching write for node/session/tx={key}")

    ready_by_session = {(event.get("node"), event.get("session")): event for event in ready_events}
    for hello in hello_events:
        ready = ready_by_session.get((hello.get("node"), hello.get("session")))
        if ready is None or ready.get("observed_node_id") != hello.get("node_id"):
            errors.append(f"CDC HELLO for node={hello.get('node')} lacks matching nonce/node READY")
    if len(ready_events) != len(hello_events) or len(hello_events) != 4:
        errors.append("CDC initial/final handshake READY/HELLO event counts are incomplete")

    initial = result.get("initial_control_handshake", {})
    final = result.get("final_control_cleanup", {})

    def event_transaction(node: str, details: JSON) -> JSON | None:
        return next((
            transaction for transaction in transactions
            if transaction.get("node") == node
            and transaction.get("session") == details.get("session")
            and transaction.get("tx") == details.get("tx")
        ), None)

    for node, expected_node_id in (("A", 1), ("B", 2)):
        hello = initial.get(node, {})
        if (
            hello.get("control_ready") is not True
            or hello.get("node_id") != expected_node_id
            or hello.get("ready_result", {}).get("session") != hello.get("session")
        ):
            errors.append(f"Node {node} initial session handshake did not validate identity and nonce")
        requests = hello.get("requests", [])
        expected_modes = ["OFF", "ON", "OFF"]
        if len(requests) != 3 or [request.get("requested") for request in requests] != expected_modes:
            errors.append(f"Node {node} initial OFF/ON/OFF control sequence is incomplete")
        if any(
            request.get("acknowledged") is not True
            or request.get("applied") is not True
            or request.get("rc") != 0
            or request.get("session") != hello.get("session")
            or request.get("node_id") != expected_node_id
            for request in requests
        ):
            errors.append(f"Node {node} initial control request ACK/session validation failed")
        if any(
            (transaction := event_transaction(node, request)) is None
            or transaction.get("requested") != request.get("requested")
            or transaction.get("rc") != 0
            for request in requests
        ):
            errors.append(f"Node {node} initial-control summary differs from its raw nonce/tx transactions")
        cleanup = final.get(node, {})
        if (
            cleanup.get("ready") is not True
            or cleanup.get("node_id") != expected_node_id
            or cleanup.get("requested") != "OFF"
            or cleanup.get("selected") != "OFF"
            or cleanup.get("acknowledged") is not True
            or cleanup.get("applied") is not True
            or cleanup.get("rc") != 0
            or cleanup.get("ready_result", {}).get("session") != cleanup.get("session")
        ):
            errors.append(f"Node {node} final OFF session cleanup did not validate")
        cleanup_transaction = event_transaction(node, cleanup)
        if (
            cleanup_transaction is None
            or cleanup_transaction.get("requested") != "OFF"
            or cleanup_transaction.get("rc") != 0
        ):
            errors.append(f"Node {node} final OFF summary differs from its raw nonce/tx transaction")

    block_controls = result.get("block_mode_control", [])
    block_attempts = [
        (block.get("block"), block.get("request_mode"), node, details)
        for block in block_controls
        for node, details in block.get("nodes", {}).items()
    ]
    if len(block_controls) != 4 or len(block_attempts) != 8:
        errors.append("CDC four-block mode-control attempts are incomplete")
    for block, mode, node, details in block_attempts:
        expected_node_id = 1 if node == "A" else 2
        if (
            details.get("acknowledged") is not True
            or details.get("applied") is not True
            or details.get("requested") != mode
            or details.get("selected") != mode
            or details.get("rc") != 0
            or details.get("node_id") != expected_node_id
            or not details.get("session")
            or not isinstance(details.get("tx"), int)
        ):
            errors.append(f"Block {block} node {node} mode-control acknowledgement failed")
        transaction = event_transaction(node, details)
        if transaction is None or transaction.get("requested") != mode or transaction.get("rc") != 0:
            errors.append(f"Block {block} node {node} result does not match its raw nonce/tx transaction")

    latencies = [
        item["ack_latency_ms"]
        for item in transactions
        if isinstance(item.get("ack_latency_ms"), (int, float))
    ]
    return {
        "valid": not errors,
        "hello_count": len(hello_events),
        "ready_count": len(ready_events),
        "request_write_count": len(writes),
        "ack_count": len(acknowledgements),
        "matched_transaction_count": len(transactions),
        "ack_latency_ms": {
            "min": min(latencies) if latencies else None,
            "median": statistics.median(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "within_500ms_count": sum(isinstance(value, (int, float)) and 0 <= value <= 500 for value in latencies),
        },
        "initial_handshake_and_off_on_off": initial,
        "four_block_mode_controls": block_controls,
        "final_off_cleanup": final,
        "transactions": transactions,
        "errors": errors,
    }


def analyze(root: Path) -> JSON:
    config_path = root / "matrix_config.json"
    result_path = root / "matrix_result.json"
    config = read_json(config_path)
    result = read_json(result_path)
    manifest = verify_manifest(root)
    raw_before = raw_input_hashes(root)
    plan_copy = root / str(config.get("predeclared_plan_copy", "PREDECLARED_PLAN.md"))
    plan_hash = sha256(plan_copy)
    runs: list[JSON] = []

    for run_result in result.get("run_results", []):
        active_nodes = list(run_result.get("nodes", []))
        run_index = int(run_result["run_index"])
        block = int(run_result["block_index"])
        mode = str(run_result["request_mode"])
        condition = str(run_result["condition"])
        recorder_nodes = run_result.get("recorder_result", {}).get("nodes", {})
        cdc_nodes = run_result.get("cdc", {})
        node_rows: JSON = {}
        run_capture_dir = root / f"run-{run_index:02d}-{condition}"
        for node in active_nodes:
            recorder_node = recorder_nodes.get(node, {})
            raw_path = Path(str(recorder_node.get("raw_path", "")))
            events_path = Path(str(recorder_node.get("events_path", "")))
            cdc_meta = cdc_nodes.get(node, {})
            cdc_path_value = Path(str(cdc_meta.get("raw_path", "")))
            cdc_path = (
                cdc_path_value
                if cdc_path_value.is_absolute()
                else run_capture_dir / cdc_path_value
            )
            if not cdc_path.is_file():
                raise FileNotFoundError(
                    f"missing raw CDC capture for run {run_index} node {node}: {cdc_path}"
                )
            raw = decode_raw_capture(raw_path, node) if raw_path.is_file() else {
                "path": str(raw_path), "sha256": None, "bytes": 0, "records_seen": 0,
                "valid_packets": 0, "samples_decoded": 0, "decode_errors": 0,
                "crc_errors": 0, "framing_errors": 0, "wrong_node_packets": 0,
                "packet_sequence_gaps": 0, "packet_duplicates": 0, "packet_reordered": 0,
                "sample_sequence_gaps": 0, "sample_duplicates": 0, "sample_reordered": 0,
                "clock_epoch_changes": 0, "payload_length_counts": {},
                "outer_record_length_counts": {}, "parsed_bytes": 0, "trailing_bytes": 0,
            }
            events = read_events(events_path)
            cdc = parse_cdc(cdc_path, node)
            diag = diagnostic_summary(cdc, ACTIVE_SECONDS)
            result_packets = recorder_node.get("packets")
            event_packets = sum(event.get("event") == "notify" for event in events)
            link_events = cdc["link_events"]
            last_tuple = cdc["last_valid_link_tuple"]
            target_tuple_count = sum(
                tuple(event["tuple"]) == TARGET
                for event in link_events
                if event["tuple"] is not None
            )
            node_rows[node] = {
                "raw_capture": raw,
                "runner_packet_count": result_packets,
                "event_packet_count": event_packets,
                "raw_vs_runner_packet_count_match": raw["valid_packets"] == result_packets,
                "raw_vs_event_packet_count_match": raw["valid_packets"] == event_packets,
                "throughput_packets_per_15s": raw["valid_packets"],
                "throughput_packets_per_second": raw["valid_packets"] / ACTIVE_SECONDS,
                "capture_quality": capture_quality(events, raw),
                "local_parameter_request_logs": cdc["parameter_request_logs"],
                "link_parameter_events": link_events,
                "last_observed_link_tuple": last_tuple,
                "target_tuple_event_count": target_tuple_count,
                "target_tuple_observed": target_tuple_count > 0,
                "tx_diagnostics": diag,
                "cdc_raw_path": cdc["path"],
                "cdc_raw_sha256": cdc["sha256"],
                "cdc_bytes": cdc["bytes"],
            }
        runs.append({
            "run_index": run_index,
            "block": block,
            "mode": mode,
            "condition": condition,
            "active_nodes": active_nodes,
            "run_error": run_result.get("error"),
            "block_mode_control": run_result.get("block_mode_control", {}),
            "nodes": node_rows,
        })

    root_control_events = read_events(root / "matrix_control.ndjson")
    root_control_audit = audit_cdc_control_events(root_control_events, result)
    expected_schedule = [
        {"block": block_index, "mode": mode, "condition": condition}
        for block_index, (mode, conditions) in enumerate(EXPECTED_BLOCKS, start=1)
        for condition in conditions
    ]
    observed_schedule = [
        {"block": run["block"], "mode": run["mode"], "condition": run["condition"]}
        for run in runs
    ]
    for run, run_result in zip(runs, result.get("run_results", []), strict=True):
        active_nodes = run["active_nodes"]
        run_capture_dir = root / f"run-{run['run_index']:02d}-{run['condition']}"
        run_control_events = read_events(run_capture_dir / "experiment_control.ndjson")
        events_by_node: dict[str, list[JSON]] = {
            node: read_events(
                Path(
                    str(
                        run_result.get("recorder_result", {})
                        .get("nodes", {})
                        .get(node, {})
                        .get("events_path", "")
                    )
                )
            )
            for node in active_nodes
        }
        timing_audit = audit_run_timing_events(
            run_control_events,
            events_by_node,
            active_nodes=active_nodes,
            settle_seconds=float(config.get("connection_settle_seconds", 10.0)),
            capture_seconds=ACTIVE_SECONDS,
            connect_gatt_timeout_seconds=15.0,
        )
        run["phase_timing"] = timing_audit
        disconnect_events = [
            event for event in run_control_events
            if event.get("event") == "matrix_run_disconnect_complete"
        ]
        host_disconnects = run_result.get("host_disconnects", [])
        peripheral_disconnects = run_result.get("peripheral_disconnects", {})
        cleanup_errors = run_result.get("disconnect_cleanup_errors", [])
        cleanup_valid = (
            len(disconnect_events) == 1
            and disconnect_events[0].get("errors") == []
            and not cleanup_errors
            and all(
                any(
                    host.get("node") == node
                    and host.get("completed") is True
                    and host.get("is_connected") is False
                    for host in host_disconnects
                )
                for node in active_nodes
            )
            and all(
                peripheral_disconnects.get(node, {}).get("required") is True
                and peripheral_disconnects.get(node, {}).get("observed") is True
                and peripheral_disconnects.get(node, {}).get("completed") is True
                for node in active_nodes
            )
        )
        run["cleanup_audit"] = {
            "valid": cleanup_valid,
            "disconnect_cleanup_errors": cleanup_errors,
            "host_disconnects": host_disconnects,
            "peripheral_disconnects": peripheral_disconnects,
            "matrix_disconnect_completion_events": disconnect_events,
        }
        for node in active_nodes:
            node_row = run["nodes"][node]
            phase_node = timing_audit.get("nodes", {}).get(node, {})
            window = phase_node.get("parameter_window", {})
            callbacks = window.get("callbacks", [])
            target_in_window = sum(
                tuple(callback.get("tuple", [])) == TARGET
                for callback in callbacks
                if isinstance(callback.get("tuple"), list) and len(callback["tuple"]) == 3
            )
            node_row["parameter_window_audit"] = phase_node
            node_row["target_tuple_event_count_in_complete_window"] = target_in_window
            node_row["target_tuple_observed"] = target_in_window > 0
            recorder_info = run_result.get("recorder_result", {}).get("nodes", {}).get(node, {})
            events_path = Path(str(recorder_info.get("events_path", "")))
            node_row["event_sidecar_parse_errors"] = count_invalid_event_lines(events_path)
            node_row["event_sidecar_bytes"] = events_path.stat().st_size if events_path.is_file() else 0
            raw_capture = node_row["raw_capture"]
            diag = node_row["tx_diagnostics"]
            node_row["data_integrity"] = {
                "raw_file_nonempty": raw_capture.get("bytes", 0) > 0,
                "raw_bytes_fully_parsed": (
                    raw_capture.get("parsed_bytes") == raw_capture.get("bytes")
                    and raw_capture.get("trailing_bytes") == 0
                ),
                "event_sidecar_nonempty": node_row["event_sidecar_bytes"] > 0,
                "event_sidecar_json_valid": node_row["event_sidecar_parse_errors"] == 0,
                "valid_packet_count_positive": raw_capture.get("valid_packets", 0) > 0,
                "packet_counts_match": (
                    node_row["raw_vs_runner_packet_count_match"]
                    and node_row["raw_vs_event_packet_count_match"]
                ),
                "raw_and_event_errors_zero": all(
                    node_row["capture_quality"].get(name) == 0
                    for name in (
                        "event_crc_false",
                        "event_decode_failures",
                        "raw_crc_errors",
                        "raw_decode_errors",
                        "raw_framing_errors",
                        "wrong_node_packets",
                    )
                ),
                "tx_diagnostics_exact": diag.get("delta_quality") == "exact",
                "required_tx_metrics_present": (
                    diag.get("completion_age_p95_bucket") is not None
                    and diag.get("rates", {}).get("retry_calls_per_notification_submission") is not None
                    and diag.get("rates", {}).get("full_window_wait_us_per_notification_submission") is not None
                ),
                "setup_timing_and_parameter_window_valid": phase_node.get("setup_valid") is True,
                "capture_boundary_valid": phase_node.get("capture_boundary_valid") is True,
            }

    # Add within-block dual/single and first/second ratios from direct raw parsing.
    singles: dict[tuple[int, str], int] = {}
    for run in runs:
        if run["condition"] == "a_only" and "A" in run["nodes"]:
            singles[(run["block"], "A")] = run["nodes"]["A"]["raw_capture"]["valid_packets"]
        elif run["condition"] == "b_only" and "B" in run["nodes"]:
            singles[(run["block"], "B")] = run["nodes"]["B"]["raw_capture"]["valid_packets"]
    for run in runs:
        if run["condition"] not in FIRST_NODE:
            continue
        for node, row in run["nodes"].items():
            single = singles.get((run["block"], node), 0)
            row["same_block_single_control_packets"] = single
            row["dual_to_single_ratio"] = safe_ratio(row["raw_capture"]["valid_packets"], single)
            row["dual_to_single_threshold_0_90_met"] = (
                row["dual_to_single_ratio"] is not None and row["dual_to_single_ratio"] >= 0.90
            )
        first_node = FIRST_NODE[run["condition"]]
        second_node = "B" if first_node == "A" else "A"
        first_packets = run["nodes"].get(first_node, {}).get("raw_capture", {}).get("valid_packets", 0)
        second_packets = run["nodes"].get(second_node, {}).get("raw_capture", {}).get("valid_packets", 0)
        run["first_connected_node"] = first_node
        run["second_connected_node"] = second_node
        run["first_to_second_throughput_ratio"] = safe_ratio(first_packets, second_packets)
        run["first_to_second_threshold_0_90_met"] = (
            run["first_to_second_throughput_ratio"] is not None
            and run["first_to_second_throughput_ratio"] >= 0.90
        )

    expected_order = list(EXPECTED_ORDER)
    observed_order = list(result.get("run_order", []))
    schedule_matches = (
        observed_order == expected_order
        and len(runs) == 16
        and observed_schedule == expected_schedule
        and result.get("scheduled_count") == 16
        and result.get("schedule_attempted_count") == 16
        and result.get("all_scheduled_runs_attempted") is True
    )
    on_links: list[JSON] = []
    off_links: list[JSON] = []
    for run in runs:
        target = on_links if run["mode"] == "ON" else off_links
        for node, row in run["nodes"].items():
            target.append({
                "run_index": run["run_index"],
                "block": run["block"],
                "condition": run["condition"],
                "node": node,
                "request_mode": run["mode"],
                "request_logs": row["local_parameter_request_logs"],
                "last_observed_link_tuple": row["last_observed_link_tuple"],
                "target_tuple_observed": row["target_tuple_observed"],
            })

    controls = result.get("block_mode_control", [])
    control_attempts = [
        node_info
        for block_control in controls
        for node_info in block_control.get("nodes", {}).values()
    ]
    all_block_controls_acknowledged_applied = bool(control_attempts) and all(
        entry.get("acknowledged") is True and entry.get("applied") is True
        for entry in control_attempts
    )
    all_on_links_target = bool(on_links) and all(entry["target_tuple_observed"] for entry in on_links)
    all_on_links_requested = bool(on_links) and all(
        has_parameter_request(entry, mode="ON", call="1", api_rc="0")
        for entry in on_links
    )
    all_off_links_no_local_request = bool(off_links) and all(
        has_parameter_request(entry, mode="OFF", call="0", api_rc="NA")
        for entry in off_links
    )
    all_off_tuples_differ = bool(off_links) and all(
        entry["last_observed_link_tuple"] is not None
        and tuple(entry["last_observed_link_tuple"]) != TARGET
        for entry in off_links
    )
    manipulation_realized = all((
        all_block_controls_acknowledged_applied,
        all_on_links_target,
        all_on_links_requested,
        all_off_links_no_local_request,
        all_off_tuples_differ,
    ))
    run_errors = [run["run_index"] for run in runs if run.get("run_error") is not None]
    active_capture_packet_counts = [
        row["raw_capture"]["valid_packets"]
        for run in runs for row in run["nodes"].values()
    ]
    all_active_captures_have_packets = bool(active_capture_packet_counts) and all(
        count > 0 for count in active_capture_packet_counts
    )
    completeness_issues: list[str] = []
    if not schedule_matches:
        completeness_issues.append(
            "The recorded schedule, attempted count or four locked Williams blocks do not match."
        )
    if run_errors:
        completeness_issues.append(f"Run-level errors were recorded for runs {run_errors}.")
    if result.get("control_gate_error") is not None or result.get("stop_reason") is not None:
        completeness_issues.append(
            f"Matrix control/stop state was not clean: control_gate_error={result.get('control_gate_error')!r}, "
            f"stop_reason={result.get('stop_reason')!r}."
        )
    if not root_control_audit["valid"]:
        completeness_issues.extend(root_control_audit["errors"])
    if not all_active_captures_have_packets:
        completeness_issues.append("At least one scheduled active-node capture contains zero valid KIMU packets.")

    cleanup_failures = [run["run_index"] for run in runs if not run.get("cleanup_audit", {}).get("valid")]
    if cleanup_failures:
        completeness_issues.append(f"Confirmed host/peripheral cleanup is incomplete for runs {cleanup_failures}.")
    node_data_failures = [
        {
            "run": run["run_index"],
            "node": node,
            "failed_checks": [name for name, okay in row.get("data_integrity", {}).items() if not okay],
        }
        for run in runs
        for node, row in run["nodes"].items()
        if not all(row.get("data_integrity", {}).values())
    ]
    for failure in node_data_failures:
        completeness_issues.append(
            f"Run {failure['run']} node {failure['node']} has incomplete required data: {failure['failed_checks']}."
        )

    tx_incomplete_segments = [
        {
            "run": run["run_index"],
            "node": node,
            "segments": [
                {
                    "segment_index": segment.get("segment_index"),
                    "boot_id": segment.get("boot_id"),
                    "connection_generation": segment.get("connection_generation"),
                    "snapshot_count": segment.get("snapshot_count"),
                    "delta_quality": segment.get("delta_quality"),
                    "parse_errors": segment.get("parse_errors"),
                    "saturated": segment.get("saturated"),
                }
                for segment in row.get("tx_diagnostics", {}).get("segments", [])
                if segment.get("delta_quality") != "exact"
            ],
        }
        for run in runs
        for node, row in run["nodes"].items()
        if row.get("tx_diagnostics", {}).get("delta_quality") != "exact"
    ]
    timing_failures = [
        {"run": run["run_index"], "errors": run.get("phase_timing", {}).get("errors", [])}
        for run in runs
        if not run.get("phase_timing", {}).get("valid")
    ]
    if timing_failures:
        completeness_issues.extend(
            f"Run {failure['run']} timing/setup audit failed: {failure['errors']}"
            for failure in timing_failures
        )
    if tx_incomplete_segments:
        completeness_issues.extend(
            f"Run {failure['run']} node {failure['node']} has incomplete or lower-bound TX diagnostic segments."
            for failure in tx_incomplete_segments
        )

    data_complete = not completeness_issues
    classification = classify_predeclared_outcome(
        runs,
        manipulation_realized=manipulation_realized,
        data_complete=data_complete,
    )
    reasons = list(classification["classification_reasons"])
    if not all_off_tuples_differ:
        for entry in off_links:
            if entry["last_observed_link_tuple"] is None or tuple(entry["last_observed_link_tuple"]) == TARGET:
                reasons.append(
                    "OFF target contrast failed at "
                    f"run {entry['run_index']} node {entry['node']}: last observed tuple="
                    f"{entry['last_observed_link_tuple']}."
                )
    reasons.extend(completeness_issues)
    classification["classification_reasons"] = reasons

    raw_after = raw_input_hashes(root)
    raw_unchanged = raw_before == raw_after
    artifact_names = (
        "PREDECLARED_PLAN.md",
        "matrix_config.json",
        "matrix_result.json",
        "preflash_firmware_and_hardware_check.json",
        "matrix_control.ndjson",
    )
    artifact_hashes = {
        name: sha256(root / name)
        for name in artifact_names
        if (root / name).is_file()
    }
    all_node_rows = [row for run in runs for row in run["nodes"].values()]
    scan_durations = [
        node["scan"]["duration_s"]
        for run in runs
        for node in run["phase_timing"].get("nodes", {}).values()
        if isinstance(node.get("scan", {}).get("duration_s"), (int, float))
    ]
    connect_gatt_durations = [
        node["connect_gatt"]["duration_s"]
        for run in runs
        for node in run["phase_timing"].get("nodes", {}).values()
        if isinstance(node.get("connect_gatt", {}).get("duration_s"), (int, float))
    ]
    settle_durations = [
        node["parameter_window"]["measured_host_duration_s"]
        for run in runs
        for node in run["phase_timing"].get("nodes", {}).values()
        if isinstance(node.get("parameter_window", {}).get("measured_host_duration_s"), (int, float))
    ]
    capture_spans = [
        node["capture"]["callback_span_s"]
        for run in runs
        for node in run["phase_timing"].get("nodes", {}).values()
        if isinstance(node.get("capture", {}).get("callback_span_s"), (int, float))
    ]
    phase_node_audits = [
        node
        for run in runs
        for node in run.get("phase_timing", {}).get("nodes", {}).values()
    ]
    capture_audits = [node.get("capture", {}) for node in phase_node_audits]
    return {
        "schema": "kineimu.m1.ble-connparam-independent-recalculation/1.0",
        "computed_at_utc": datetime.now(UTC).isoformat(),
        "root_dir": str(root),
        "analysis_source": (
            "matrix_result.json + raw per-run .cdc.bin + raw .kimu + .events.ndjson; "
            "matrix_audit.json was not used as an input"
        ),
        "analysis_script_path": str(Path(__file__).resolve()),
        "analysis_script_sha256": sha256(Path(__file__).resolve()),
        "plan_sha256": plan_hash,
        "matrix_config_sha256": artifact_hashes.get("matrix_config.json"),
        "matrix_result_sha256": artifact_hashes.get("matrix_result.json"),
        "preflash_record_sha256": artifact_hashes.get("preflash_firmware_and_hardware_check.json"),
        "initial_manifest_verification": manifest,
        "raw_inputs_unchanged_during_recalculation": raw_unchanged,
        "raw_input_hashes_before": raw_before,
        "raw_input_hashes_after": raw_after,
        "fixed_parameters": {
            "planned_active_seconds": ACTIVE_SECONDS,
            "connection_settle_seconds": config.get("connection_settle_seconds"),
            "inter_run_rest_seconds": config.get("inter_run_rest_seconds"),
            "target_interval_us": TARGET[0],
            "target_latency": TARGET[1],
            "target_supervision_timeout_us": TARGET[2],
        },
        "schedule_check": {
            "expected_order": expected_order,
            "observed_order": observed_order,
            "expected_block_mode_condition_schedule": expected_schedule,
            "observed_block_mode_condition_schedule": observed_schedule,
            "scheduled_count": result.get("scheduled_count"),
            "attempted_count": result.get("schedule_attempted_count"),
            "all_scheduled_runs_attempted": result.get("all_scheduled_runs_attempted"),
            "matches_locked_schedule": schedule_matches,
        },
        "cdc_control_plane": root_control_audit,
        "phase_timing_summary": {
            "valid_run_count": sum(run.get("phase_timing", {}).get("valid") is True for run in runs),
            "total_active_node_windows": len(settle_durations),
            "scan_connect_parameter_setup_valid_node_windows": sum(
                node.get("setup_valid") is True for node in phase_node_audits
            ),
            "capture_boundary_valid_node_windows": sum(
                node.get("capture_boundary_valid") is True for node in phase_node_audits
            ),
            "filtered_scan_s": {
                "count": len(scan_durations),
                "min": min(scan_durations) if scan_durations else None,
                "max": max(scan_durations) if scan_durations else None,
            },
            "windows_connect_and_gatt_s_excluding_scan": {
                "count": len(connect_gatt_durations),
                "min": min(connect_gatt_durations) if connect_gatt_durations else None,
                "max": max(connect_gatt_durations) if connect_gatt_durations else None,
                "limit_s": 15.0,
            },
            "peripheral_event_relative_parameter_window_s": {
                "count": len(settle_durations),
                "min": min(settle_durations) if settle_durations else None,
                "max": max(settle_durations) if settle_durations else None,
                "planned_s": config.get("connection_settle_seconds"),
            },
            "notification_callback_capture_span_s": {
                "count": len(capture_spans),
                "min": min(capture_spans) if capture_spans else None,
                "max": max(capture_spans) if capture_spans else None,
                "planned_s": ACTIVE_SECONDS,
            },
        },
        "capture_boundary_summary": {
            "active_node_streams": len(capture_audits),
            "explicit_boundaries_recorded": sum(
                audit.get("explicit_boundary_recorded") is True for audit in capture_audits
            ),
            "streams_missing_explicit_boundary": sum(
                audit.get("explicit_boundary_recorded") is not True for audit in capture_audits
            ),
            "callbacks_outside_recorded_window": sum(
                audit.get("callbacks_outside_recorded_window", 0) for audit in capture_audits
            ),
            "callbacks_at_or_after_earliest_possible_deadline_without_marker": sum(
                audit.get("callbacks_at_or_after_earliest_possible_deadline", 0)
                for audit in capture_audits
            ),
            "interpretation": (
                "Without explicit per-run capture markers, callbacks at or after the earliest possible deadline "
                "are diagnostic evidence only; exact inclusion in the planned capture cannot be determined."
            ),
        },
        "mode_control_check": {
            "block_count": len(controls),
            "node_mode_control_attempt_count": len(control_attempts),
            "acknowledged_and_applied_count": sum(
                entry.get("acknowledged") is True and entry.get("applied") is True
                for entry in control_attempts
            ),
            "errors": [
                {
                    "block": block.get("block"),
                    "mode": block.get("request_mode"),
                    "node": node,
                    "error": info.get("error"),
                }
                for block in controls
                for node, info in block.get("nodes", {}).items()
                if info.get("error")
            ],
            "all_block_controls_acknowledged_and_applied": all_block_controls_acknowledged_applied,
        },
        "manipulation_validity": {
            "on_link_count": len(on_links),
            "on_links_with_target_tuple": sum(entry["target_tuple_observed"] for entry in on_links),
            "on_links_with_local_on_api_call_rc0": sum(
                has_parameter_request(entry, mode="ON", call="1", api_rc="0")
                for entry in on_links
            ),
            "off_link_count": len(off_links),
            "off_links_with_no_local_request": sum(
                has_parameter_request(entry, mode="OFF", call="0", api_rc="NA")
                for entry in off_links
            ),
            "off_links_with_different_last_tuple": sum(
                entry["last_observed_link_tuple"] is not None and tuple(entry["last_observed_link_tuple"]) != TARGET
                for entry in off_links
            ),
            "checks": {
                "all_block_controls_acknowledged_and_applied": all_block_controls_acknowledged_applied,
                "every_on_link_reports_15ms_0_420ms": all_on_links_target,
                "every_on_link_records_successful_local_request": all_on_links_requested,
                "every_off_link_records_no_local_request": all_off_links_no_local_request,
                "every_off_link_last_tuple_differs_from_target": all_off_tuples_differ,
            },
            "realized": manipulation_realized,
            "on_links": on_links,
            "off_links": off_links,
        },
        "capture_summary": {
            "active_node_capture_count": len(all_node_rows),
            "valid_packet_total": sum(row["raw_capture"]["valid_packets"] for row in all_node_rows),
            "valid_packet_count_min": (
                min(row["raw_capture"]["valid_packets"] for row in all_node_rows)
                if all_node_rows
                else None
            ),
            "valid_packet_count_max": (
                max(row["raw_capture"]["valid_packets"] for row in all_node_rows)
                if all_node_rows
                else None
            ),
            "nonzero_valid_packet_captures": sum(row["raw_capture"]["valid_packets"] > 0 for row in all_node_rows),
            "tx_diagnostic_exact_captures": sum(
                row["tx_diagnostics"]["delta_quality"] == "exact" for row in all_node_rows
            ),
            "clean_capture_count": sum(
                all(row["data_integrity"].get(name) is True for name in (
                    "raw_file_nonempty", "raw_bytes_fully_parsed", "event_sidecar_nonempty",
                    "event_sidecar_json_valid", "valid_packet_count_positive", "packet_counts_match",
                    "raw_and_event_errors_zero", "setup_timing_and_parameter_window_valid",
                    "capture_boundary_valid",
                ))
                for row in all_node_rows
            ),
        },
        "data_completeness": {
            "run_level_errors": run_errors,
            "all_active_node_captures_contain_packets": all_active_captures_have_packets,
            "zero_packet_active_node_captures": [
                {"run": run["run_index"], "node": node, "mode": run["mode"], "condition": run["condition"]}
                for run in runs for node, row in run["nodes"].items()
                if row["raw_capture"]["valid_packets"] == 0
            ],
            "cleanup_failure_runs": cleanup_failures,
            "node_data_failures": node_data_failures,
            "incomplete_tx_diagnostic_segments": tx_incomplete_segments,
            "timing_audit_failures": timing_failures,
            "completeness_issues": completeness_issues,
            "complete": data_complete,
        },
        "classification": classification,
        "classification_reasons": reasons,
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    root = args.root_dir.resolve()
    report = analyze(root)
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output_json is None:
        print(serialized, end="")
    else:
        output_path = args.output_json.resolve()
        if "raw" in output_path.parts:
            raise ValueError("refusing to write analysis output inside a raw directory")
        if output_path.exists():
            raise FileExistsError(f"refusing to overwrite derived output: {output_path}")
        output_path.write_text(serialized, encoding="utf-8")
        print(json.dumps({
            "output_json": str(output_path),
            "output_sha256": sha256(output_path),
            "classification": report["classification"],
            "schedule_matches_locked": report["schedule_check"]["matches_locked_schedule"],
            "manipulation_realized": report["manipulation_validity"]["realized"],
            "raw_inputs_unchanged": report["raw_inputs_unchanged_during_recalculation"],
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
