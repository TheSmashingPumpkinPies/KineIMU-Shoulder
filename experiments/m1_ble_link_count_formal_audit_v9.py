"""Independently audit V9 from immutable raw streams and event sidecars."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from experiments import m1_ble_link_count_formal_v9 as formal
from experiments import m1_ble_link_matrix as matrix_runner
from experiments import m1_ble_link_precheck as precheck
from experiments.m1_ble_connparam_independent_analysis import (
    audit_run_timing_events,
    capture_quality,
    count_invalid_event_lines,
    decode_raw_capture,
    diagnostic_summary,
    parse_cdc,
    raw_input_hashes,
    read_events,
    sha256,
    verify_manifest,
)
from kineimu_shoulder.io.m1_packet import NodeId

JSON = dict[str, Any]
FORMAL_PLAN_PATH = formal.FORMAL_PLAN_PATH
FORMAL_PLAN_SHA256 = formal.FORMAL_PLAN_SHA256
FORMAL_OUTPUT_ROOT = formal.FORMAL_OUTPUT_ROOT
_REQUIRED_TX_FIELDS = {
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
    "schedule_fail_initial",
    "schedule_fail_retry",
}


def _read_json(path: Path) -> JSON:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object at {path}")
    return cast(JSON, value)


def _active_tx_segment(summary: JSON) -> tuple[JSON | None, list[str]]:
    errors: list[str] = []
    segments = summary.get("segments", [])
    active = [
        cast(JSON, segment)
        for segment in segments
        if isinstance(segment, dict)
        and isinstance(segment.get("counter_deltas"), dict)
        and any(
            isinstance(segment["counter_deltas"].get(name), int)
            and segment["counter_deltas"][name] > 0
            for name in ("calls", "accepted", "retries", "enomem", "eagain")
        )
    ] if isinstance(segments, list) else []
    if not isinstance(summary.get("snapshot_count"), int) or summary["snapshot_count"] < 2:
        errors.append("TX diagnostics contain fewer than two snapshots")
    if len(active) != 1:
        errors.append(f"expected one active connection-generation TX segment, found {len(active)}")
        return None, errors
    segment = active[0]
    if segment.get("delta_quality") != "exact":
        errors.append("active connection-generation TX counters are not exact")
    if segment.get("saturated") is not False:
        errors.append("active connection-generation TX counters are saturated or unknown")
    deltas = segment.get("counter_deltas")
    if not isinstance(deltas, dict):
        errors.append("active TX segment has no counter deltas")
    else:
        missing = sorted(_REQUIRED_TX_FIELDS - set(deltas))
        if missing:
            errors.append(f"active TX segment omits counters: {missing}")
        if any(not isinstance(deltas.get(name), int) for name in _REQUIRED_TX_FIELDS):
            errors.append("active TX segment contains unavailable or non-integer counters")
    return segment, errors


def _unique_boot_id_errors(run_audits: list[JSON]) -> tuple[list[str], set[int]]:
    """Reject reuse of a board boot ID across any attempted V9 conditions."""

    seen_by_node: dict[str, dict[int, int]] = {"A": {}, "B": {}}
    errors: list[str] = []
    repeated_runs: set[int] = set()
    for audit in run_audits:
        run_index = audit.get("run_index")
        nodes = audit.get("nodes", {})
        if not isinstance(run_index, int) or not isinstance(nodes, dict):
            continue
        for node in ("A", "B"):
            row = nodes.get(node)
            start = row.get("acquisition_start", {}) if isinstance(row, dict) else {}
            boot_id = start.get("boot_id") if isinstance(start, dict) else None
            if not isinstance(boot_id, int) or isinstance(boot_id, bool):
                continue
            previous_run = seen_by_node[node].get(boot_id)
            if previous_run is not None:
                errors.append(
                    f"Node {node} reused boot ID {boot_id} in runs {previous_run} and {run_index}"
                )
                repeated_runs.update((previous_run, run_index))
            else:
                seen_by_node[node][boot_id] = run_index
    return errors, repeated_runs


def forbidden_boot_id_errors(recorded: object) -> list[str]:
    """Require every acquisition lock to exclude all retained precheck boots."""

    if not isinstance(recorded, dict):
        return ["forbidden boot-ID lock is missing or malformed"]
    errors: list[str] = []
    for node in ("A", "B"):
        values = recorded.get(node)
        observed = (
            {value for value in values if isinstance(value, int) and not isinstance(value, bool)}
            if isinstance(values, list)
            else set()
        )
        expected = formal.FORMAL_FORBIDDEN_BOOT_IDS[NodeId[node]]
        missing = sorted(expected - observed)
        if missing:
            errors.append(f"Node {node} forbidden-boot lock omits prior IDs: {missing}")
    return errors


def _audit_control_readiness(
    run_index: int,
    events: list[JSON],
    recorded_sessions: object,
) -> list[str]:
    """Require raw orchestration evidence that both CDC sessions reached READY."""

    rows = [
        event
        for event in events
        if event.get("event") == "formal_run_cdc_control_session_ready"
        and event.get("run_index") == run_index
    ]
    errors: list[str] = []
    if len(rows) != 2:
        errors.append(
            f"run {run_index} requires exactly two CDC HELLO/READY events; found {len(rows)}"
        )
    by_node: dict[str, JSON] = {}
    for event in rows:
        node = event.get("node")
        if node not in {"A", "B"} or node in by_node:
            errors.append(f"run {run_index} has an invalid or duplicate CDC READY node {node!r}")
            continue
        by_node[str(node)] = event
        if event.get("ready") is not True:
            errors.append(f"run {run_index} Node {node} CDC HELLO/READY did not pass")
        if not isinstance(event.get("session"), str) or not event.get("session"):
            errors.append(f"run {run_index} Node {node} CDC READY event has no session nonce")

    if set(by_node) != {"A", "B"}:
        errors.append(f"run {run_index} CDC READY events do not cover both Node A and Node B")
    if not isinstance(recorded_sessions, dict) or set(recorded_sessions) != {"A", "B"}:
        errors.append(f"run {run_index} result omits the two-node CDC READY session record")
    else:
        for node in ("A", "B"):
            session = recorded_sessions.get(node)
            event = by_node.get(node, {})
            if not isinstance(session, dict) or session.get("ready") is not True:
                errors.append(f"run {run_index} recorded Node {node} CDC session is not READY")
            elif session.get("session") != event.get("session"):
                errors.append(f"run {run_index} Node {node} CDC session differs from the event log")
    return errors


def _audit_control_boundary_order(run_index: int, events: list[JSON]) -> list[str]:
    """Prove READY precedes each CDC boundary and both boundaries precede fixed OFF."""

    run_events = [event for event in events if event.get("run_index") == run_index]
    ready = [
        event for event in run_events
        if event.get("event") == "formal_run_cdc_control_session_ready"
    ]
    boundaries = [
        event for event in run_events if event.get("event") == "formal_run_cdc_boundary"
    ]
    off_acks = [
        event for event in run_events
        if event.get("event") == "block_request_mode_acknowledgment"
        and event.get("request_mode") == "OFF"
    ]
    errors: list[str] = []
    if len(boundaries) != 2 or {event.get("node") for event in boundaries} != {"A", "B"}:
        errors.append(f"run {run_index} must record one CDC boundary for each node")
    elif any(
        not isinstance(event.get("offset"), int) or event.get("offset", -1) < 0
        for event in boundaries
    ):
        errors.append(f"run {run_index} has a missing or invalid CDC boundary offset")
    if len(off_acks) != 2 or {event.get("node") for event in off_acks} != {"A", "B"}:
        errors.append(f"run {run_index} must record fixed-OFF acknowledgments for both nodes")

    ready_times = [event.get("host_monotonic_ns") for event in ready]
    boundary_times = [event.get("host_monotonic_ns") for event in boundaries]
    off_times = [event.get("host_monotonic_ns") for event in off_acks]
    if not all(isinstance(value, int) for value in ready_times):
        errors.append(f"run {run_index} CDC READY events lack monotonic timestamps")
    if not all(isinstance(value, int) for value in boundary_times):
        errors.append(f"run {run_index} CDC boundaries lack monotonic timestamps")
    if not all(isinstance(value, int) for value in off_times):
        errors.append(f"run {run_index} fixed-OFF acknowledgments lack monotonic timestamps")
    if all(isinstance(value, int) for value in ready_times + boundary_times):
        if max(cast(list[int], ready_times)) > min(cast(list[int], boundary_times)):
            errors.append(f"run {run_index} CDC boundary was recorded before both READY handshakes")
    if all(isinstance(value, int) for value in boundary_times + off_times):
        if max(cast(list[int], boundary_times)) > min(cast(list[int], off_times)):
            errors.append(f"run {run_index} fixed OFF began before both CDC boundaries")
    return errors


def _audit_run(
    root: Path,
    run_index: int,
    condition: str,
    expected_head: str,
    root_control_events: list[JSON],
) -> JSON:
    run_dir = root / f"run-{run_index:02d}-{condition}"
    errors: list[str] = []
    if not run_dir.is_dir():
        return {
            "run_index": run_index,
            "condition": condition,
            "valid": False,
            "errors": [f"scheduled run directory is missing: {run_dir.name}"],
        }
    try:
        run_config = _read_json(run_dir / "run_config.json")
        run_result = _read_json(run_dir / "run_result.json")
        attempt = _read_json(run_dir / "scheduled_attempt.json")
        serial_summary = _read_json(run_dir / "serial_capture_summary.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {
            "run_index": run_index,
            "condition": condition,
            "valid": False,
            "errors": [f"run config/result cannot be read: {type(error).__name__}: {error}"],
        }

    expected_nodes = precheck.active_nodes_for_condition(condition)
    if run_config.get("schema") != "kineimu.m1.ble-link-count-formal-v9-run/1.0":
        errors.append("run config has the wrong V9 schema")
    if run_config.get("experiment_profile") != "link_count_formal_v9":
        errors.append("run config does not identify the V9 formal profile")
    if run_result.get("schema") != "kineimu.m1.ble-link-count-formal-v9-run-result/1.0":
        errors.append("run result has the wrong V9 schema")
    if run_config.get("predeclared_plan_sha256", "").upper() != FORMAL_PLAN_SHA256:
        errors.append("run config plan hash differs from locked V9 plan")
    if run_config.get("git_head") != expected_head:
        errors.append("run config HEAD differs from the predeclared lock HEAD")
    if run_config.get("condition") != condition:
        errors.append("run config condition differs from schedule")
    if run_config.get("request_mode") != "OFF" or run_config.get("set_request_mode_before_run") is not True:
        errors.append("run did not explicitly set the fixed local parameter mode OFF")
    if run_config.get("connection_order") != list(expected_nodes):
        errors.append("run config connection order differs from the locked condition")
    if run_config.get("nodes") != sorted(expected_nodes):
        errors.append("run config active node list differs from the locked condition")
    if run_config.get("capture_seconds") != formal.FORMAL_CAPTURE_SECONDS:
        errors.append("run config capture duration differs from 15.0 seconds")
    if run_config.get("connection_settle_seconds") != formal.FORMAL_SETTLE_SECONDS:
        errors.append("run config connection settling interval differs from 10.0 seconds")
    if run_config.get("windows_connect_gatt_setup_timeout_seconds") != formal.FORMAL_CONNECT_TIMEOUT_SECONDS:
        errors.append("run config Windows connect/GATT timeout differs from the locked 30.0 seconds")
    if run_config.get("require_pristine_start") is not True:
        errors.append("this condition did not require a fresh pristine boot before notify")
    errors.extend(forbidden_boot_id_errors(run_config.get("forbidden_boot_ids_by_node")))
    policy = run_config.get("change_policy", {})
    if (
        policy.get("connection_parameter_request") is not False
        or policy.get("completion_driven_tx") is not True
        or policy.get("host_disk_write_decoupling") is not False
        or policy.get("tx_queue_capacity_change") is not False
    ):
        errors.append("run change policy differs from the one-factor V9 plan")
    expected_serials = run_config.get("cdc_usb_serials", {})
    for node in expected_nodes:
        if expected_serials.get(node) != matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[NodeId[node]]:
            errors.append(f"Node {node} CDC source is not bound to the locked USB serial")

    try:
        control_events = precheck._read_ndjson(run_dir / "experiment_control.ndjson")
        events_by_node = {
            node: read_events(run_dir / "raw" / f"node-{node.lower()}.events.ndjson")
            for node in expected_nodes
        }
    except (OSError, ValueError) as error:
        return {
            "run_index": run_index,
            "condition": condition,
            "valid": False,
            "errors": errors + [f"control/sidecar stream cannot be read: {type(error).__name__}: {error}"],
        }

    errors.extend(
        _audit_control_readiness(
            run_index,
            root_control_events,
            attempt.get("cdc_control_sessions"),
        )
    )
    errors.extend(_audit_control_boundary_order(run_index, root_control_events))

    reset_path = (
        root
        / "operator_reset_confirmations"
        / f"run-{run_index:02d}-{condition}.json"
    )
    try:
        reset_confirmation = _read_json(reset_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        reset_confirmation = {}
        errors.append(f"operator cold-reset confirmation is missing/unreadable: {error}")
    if (
        reset_confirmation.get("run_index") != run_index
        or reset_confirmation.get("condition") != condition
        or reset_confirmation.get("token_expected") != formal.reset_confirmation_token(run_index)
        or reset_confirmation.get("operator_asserted_both_boards_power_cycled") is not True
        or attempt.get("operator_reset_confirmation") != reset_confirmation
    ):
        errors.append("run does not have a matching run-specific operator cold-reset confirmation")

    if set(serial_summary) != {"A", "B"}:
        errors.append("run does not preserve a complete two-node CDC capture summary")
    for node in ("A", "B"):
        metadata = serial_summary.get(node, {})
        relative_path = metadata.get("raw_relative_path") if isinstance(metadata, dict) else None
        full_cdc_path = (root / relative_path).resolve() if isinstance(relative_path, str) else None
        if (
            full_cdc_path is None
            or not full_cdc_path.is_relative_to(root.resolve())
            or not full_cdc_path.is_file()
            or full_cdc_path.stat().st_size <= 0
        ):
            errors.append(f"Node {node} complete run-local CDC byte capture is missing/empty/outside root")
        elif sha256(full_cdc_path).upper() != str(metadata.get("raw_sha256", "")).upper():
            errors.append(f"Node {node} complete run-local CDC byte capture hash differs from its summary")
        if (
            not isinstance(metadata, dict)
            or metadata.get("usb_serial")
            != matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[NodeId[node]]
        ):
            errors.append(f"Node {node} complete CDC capture is not tied to its locked USB serial")

    link_state = precheck.audit_active_link_state(condition, control_events)
    errors.extend(link_state.get("errors", []))
    timing = audit_run_timing_events(
        control_events,
        events_by_node,
        active_nodes=list(expected_nodes),
        settle_seconds=formal.FORMAL_SETTLE_SECONDS,
        capture_seconds=formal.FORMAL_CAPTURE_SECONDS,
        connect_gatt_timeout_seconds=formal.FORMAL_CONNECT_TIMEOUT_SECONDS,
        require_full_callback_span=False,
    )
    if timing.get("valid") is not True:
        errors.extend(f"capture/setup timing: {detail}" for detail in timing.get("errors", []))

    node_rows: JSON = {}
    run_transport_clean = True
    for node in expected_nodes:
        raw_path = run_dir / "raw" / f"node-{node.lower()}.kimu"
        sidecar_path = run_dir / "raw" / f"node-{node.lower()}.events.ndjson"
        cdc_path = run_dir / f"node-{node.lower()}.cdc.bin"
        if any(not path.is_file() or path.stat().st_size == 0 for path in (raw_path, sidecar_path, cdc_path)):
            errors.append(f"Node {node} raw KIMU, event sidecar, or CDC segment is missing/empty")
            continue

        raw = decode_raw_capture(raw_path, node)
        capture_events = events_by_node[node]
        quality = capture_quality(capture_events, raw)
        invalid_lines = count_invalid_event_lines(sidecar_path)
        if invalid_lines:
            errors.append(f"Node {node} sidecar contains {invalid_lines} invalid JSON lines")
        if raw.get("wrong_node_packets") != 0:
            errors.append(f"Node {node} stream contains wrong-node packets")
        if raw.get("valid_packets") != quality.get("notify_events"):
            errors.append(f"Node {node} decoded raw packet count does not reconcile with notify events")
        acquisition_start = precheck.audit_fresh_acquisition_start(
            capture_events,
            control_events,
            node,
        )
        if acquisition_start.get("valid") is not True:
            errors.extend(
                f"Node {node} pre-notify start: {detail}"
                for detail in acquisition_start.get("errors", [])
            )
        if acquisition_start.get("boot_id") in run_config.get(
            "forbidden_boot_ids_by_node", {}
        ).get(node, []):
            errors.append(f"Node {node} reused a boot ID from a prior precheck/formal run")

        node_timing = timing.get("nodes", {}).get(node, {})
        identity = node_timing.get("identity_config_read", {})
        if identity.get("hardware_device_id") != precheck.PRECHECK_HARDWARE_DEVICE_IDS[NodeId[node]]:
            errors.append(f"Node {node} identity hardware device ID differs")
        if identity.get("node_id") != int(NodeId[node]):
            errors.append(f"Node {node} identity node ID differs")
        if identity.get("firmware_git_commit") != precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT:
            errors.append(f"Node {node} BLE identity firmware commit differs")
        mtu_observation = node_timing.get("mtu", {})
        mtu = mtu_observation.get("capture_event", {}) if isinstance(mtu_observation, dict) else {}
        if mtu.get("mtu") != precheck.PRECHECK_MTU or mtu.get("accepted") is not True:
            errors.append(f"Node {node} link did not prove MTU {precheck.PRECHECK_MTU}")

        cdc = parse_cdc(cdc_path, node)
        off_records = [
            record
            for record in cdc.get("parameter_request_logs", [])
            if record.get("fields", {}).get("mode") == "OFF"
            and record.get("fields", {}).get("call") == "0"
            and record.get("fields", {}).get("api_rc") == "NA"
        ]
        if len(off_records) != 1:
            errors.append(f"Node {node} expected one OFF/no-local-request record; found {len(off_records)}")
        tx = diagnostic_summary(cdc, formal.FORMAL_CAPTURE_SECONDS)
        active_tx, tx_errors = _active_tx_segment(tx)
        errors.extend(f"Node {node} TX diagnostics: {detail}" for detail in tx_errors)
        if tx.get("snapshot_count") != len(cdc.get("tx_snapshots", [])):
            errors.append(f"Node {node} TX snapshot count does not reconcile with raw CDC")
        tx_deltas = active_tx.get("counter_deltas", {}) if active_tx is not None else {}
        boot_id = acquisition_start.get("boot_id")
        physical_tx = precheck.summarize_physical_connection_tx(
            tx,
            cdc.get("tx_snapshots", []),
            expected_boot_id=boot_id if isinstance(boot_id, int) else None,
        )
        errors.extend(
            f"Node {node} physical-connection TX history: {detail}"
            for detail in physical_tx.get("errors", [])
        )

        recorder_result = run_result.get("recorder_result")
        recorder_nodes = recorder_result.get("nodes", {}) if isinstance(recorder_result, dict) else {}
        recorder_node = recorder_nodes.get(node, {}) if isinstance(recorder_nodes, dict) else {}
        if recorder_node.get("packets") != raw.get("valid_packets"):
            errors.append(f"Node {node} recorder packet count differs from independent raw decode")
        if not all(
            isinstance(tx_deltas.get(field), int)
            for field in ("packet_drops", "enomem", "eagain", "retries", "wait_us", "window_full")
        ):
            run_transport_clean = False
        elif tx_deltas.get("packet_drops") != 0:
            run_transport_clean = False
        if any(
            quality.get(field) != 0
            for field in (
                "event_crc_false",
                "event_decode_failures",
                "raw_crc_errors",
                "raw_decode_errors",
                "raw_framing_errors",
            )
        ):
            run_transport_clean = False

        node_rows[node] = {
            "hardware_device_id": identity.get("hardware_device_id"),
            "node_id": identity.get("node_id"),
            "firmware_git_commit": identity.get("firmware_git_commit"),
            "mtu": mtu.get("mtu"),
            "capture_boundary_valid": node_timing.get("capture_boundary_valid"),
            "parameter_window": node_timing.get("parameter_window"),
            "raw_capture": raw,
            "capture_quality": quality,
            "acquisition_start": acquisition_start,
            "event_sidecar_sha256": sha256(sidecar_path),
            "cdc_segment_sha256": sha256(cdc_path),
            "tx_diagnostics": tx,
            "active_tx_segment": active_tx,
            "physical_connection_tx": physical_tx,
            "off_no_local_request_records": len(off_records),
        }

    cleanup_valid, cleanup_errors = precheck._audit_cleanup(run_result, control_events, expected_nodes)
    if not cleanup_valid:
        errors.extend(cleanup_errors)
    if run_result.get("error") is not None:
        errors.append(f"run result contains error: {run_result.get('error')}")
    return {
        "run_index": run_index,
        "block_index": (run_index - 1) // 4 + 1,
        "condition": condition,
        "expected_active_links": len(expected_nodes),
        "observed_connection_order": link_state.get("observed_connection_order"),
        "link_state_realized": link_state.get("realized"),
        "concurrent_capture_overlap_ns": link_state.get("concurrent_capture_overlap_ns"),
        "timing_audit": timing,
        "cleanup_valid": cleanup_valid,
        "nodes": node_rows,
        "transport_clean": run_transport_clean,
        "run_error": run_result.get("error"),
        "errors": errors,
        "valid": not errors,
    }


def _comparison_rows(audits: list[JSON]) -> tuple[list[JSON], JSON, JSON]:
    by_block: dict[int, dict[str, JSON]] = {}
    for audit in audits:
        if audit.get("valid") is not True:
            continue
        block = audit.get("block_index")
        condition = audit.get("condition")
        if isinstance(block, int) and isinstance(condition, str):
            by_block.setdefault(block, {})[condition] = audit
    packet_blocks: list[dict[str, dict[str, int]]] = []
    tx_blocks: list[dict[str, dict[str, JSON]]] = []
    for block_index in range(1, 5):
        conditions = by_block.get(block_index, {})
        packet_conditions: dict[str, dict[str, int]] = {}
        tx_conditions: dict[str, dict[str, JSON]] = {}
        for condition, audit in conditions.items():
            packet_conditions[condition] = {}
            tx_conditions[condition] = {}
            for node, row in audit.get("nodes", {}).items():
                count = row.get("raw_capture", {}).get("valid_packets")
                if isinstance(count, int):
                    packet_conditions[condition][node] = count
                segment = row.get("active_tx_segment")
                if isinstance(segment, dict):
                    tx_conditions[condition][node] = segment
        packet_blocks.append(packet_conditions)
        tx_blocks.append(tx_conditions)
    if len(by_block) != 4 or any(
        set(by_block[index]) != set(formal.FORMAL_CONDITIONS) for index in range(1, 5)
    ):
        return packet_blocks, {}, {}
    try:
        ratios = formal.derive_matched_ratios(packet_blocks)
    except ValueError:
        return packet_blocks, {}, {}
    return packet_blocks, ratios["per_node_dual_to_single"], {
        "first_to_second": ratios["first_to_second"],
        "tx_by_block": tx_blocks,
    }


def _mechanism_assessment(per_node_ratios: JSON, tx_by_block: list[JSON]) -> JSON:
    fields = ("enomem", "eagain", "wait_us", "window_full")
    paired_pressure: dict[str, dict[str, list[JSON]]] = {
        node: {condition: [] for condition in formal.FORMAL_ORDER_NODES}
        for node in ("A", "B")
    }
    complete_pair_count = 0
    for block_index, block in enumerate(tx_by_block):
        for condition in formal.FORMAL_ORDER_NODES:
            dual = block.get(condition, {})
            for node, single_condition in (("A", "a_only"), ("B", "b_only")):
                dual_segment = dual.get(node, {})
                single_segment = block.get(single_condition, {}).get(node, {})
                dual_deltas = dual_segment.get("counter_deltas", {})
                single_deltas = single_segment.get("counter_deltas", {})
                valid_pair = all(
                    isinstance(deltas.get(field), int)
                    for deltas in (dual_deltas, single_deltas)
                    for field in fields
                ) and (
                    dual_segment.get("delta_quality") == "exact"
                    and single_segment.get("delta_quality") == "exact"
                )
                if valid_pair:
                    complete_pair_count += 1
                pressure_increased = bool(
                    valid_pair
                    and (
                        dual_deltas["enomem"] + dual_deltas["eagain"]
                        > single_deltas["enomem"] + single_deltas["eagain"]
                        or dual_deltas["wait_us"] > single_deltas["wait_us"]
                        or dual_deltas["window_full"] > single_deltas["window_full"]
                    )
                )
                ratio_list = per_node_ratios.get(node, {}).get(condition, [])
                ratio = ratio_list[block_index] if len(ratio_list) == 4 else None
                paired_pressure[node][condition].append(
                    {
                        "block": block_index + 1,
                        "throughput_ratio": ratio,
                        "dual_tx_segment": dual_segment,
                        "single_tx_segment": single_segment,
                        "backpressure_increased": pressure_increased,
                    }
                )
    supported_nodes: dict[str, dict[str, int]] = {}
    for node, orders in paired_pressure.items():
        counts = {
            condition: sum(
                item["backpressure_increased"] is True
                and isinstance(item["throughput_ratio"], (int, float))
                and item["throughput_ratio"] < 0.90
                for item in rows
            )
            for condition, rows in orders.items()
        }
        if all(count >= 3 for count in counts.values()):
            supported_nodes[node] = counts
    if supported_nodes:
        status = "Supported at peripheral notify submit/retry boundary"
        reason = (
            "exact active-generation TX counters show increased ENOMEM/EAGAIN, wait, or window-full "
            "events in at least three impaired blocks for the same node under each dual order"
        )
    elif complete_pair_count == 16:
        status = "Not localized beyond active-link-count effect"
        reason = (
            "the formal matrix can identify the assigned link-count effect, but the exact TX "
            "backpressure co-occurrence threshold was not met"
        )
    else:
        status = "Inconclusive"
        reason = f"only {complete_pair_count}/16 matched node/order/block TX pairs are exact"
    return {
        "assessment": status,
        "reason": reason,
        "supported_node_counts": supported_nodes,
        "paired_block_details": paired_pressure,
        "not_identifiable_with_this_factor": (
            "the one-factor active-link-count design cannot separate Windows central/controller "
            "scheduling from peripheral/Zephyr BLE resource behavior"
        ),
    }


def audit_formal_root(
    root_dir: Path = FORMAL_OUTPUT_ROOT,
    *,
    output_json: Path | None = None,
) -> JSON:
    """Recompute the complete decision from the acquisition index and raw inputs only."""

    errors: list[str] = []
    if root_dir.resolve() != FORMAL_OUTPUT_ROOT.resolve():
        errors.append(f"V9 audit is bound to the locked root {FORMAL_OUTPUT_ROOT}")
    if not FORMAL_PLAN_PATH.is_file():
        errors.append(f"locked V9 plan is missing: {FORMAL_PLAN_PATH}")
    elif sha256(FORMAL_PLAN_PATH).upper() != FORMAL_PLAN_SHA256.upper():
        errors.append("source V9 plan hash differs from the runner lock")
    manifest = verify_manifest(root_dir)
    raw_hashes_before = raw_input_hashes(root_dir)
    if manifest.get("valid") is not True:
        errors.append("manifest is missing, invalid, or does not cover every file")
    try:
        config = _read_json(root_dir / "matrix_config.json")
        result = _read_json(root_dir / "matrix_result.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        config = {}
        result = {}
        errors.append(f"acquisition index cannot be read: {type(error).__name__}: {error}")
    try:
        root_control_events = precheck._read_ndjson(root_dir / "matrix_control.ndjson")
    except (OSError, ValueError) as error:
        root_control_events = []
        errors.append(f"root control event stream cannot be read: {type(error).__name__}: {error}")
    if config.get("schema") != "kineimu.m1.ble-link-count-formal-v9/1.0":
        errors.append("root matrix config has the wrong V9 schema")
    if config.get("plan_version") != "v9" or config.get("precheck_plan_version") != "v6":
        errors.append("root matrix config does not identify V9 plus its V6 screening precheck")
    if config.get("v6_precheck_manifest_sha256") != formal.V6_PRECHECK_MANIFEST_SHA256:
        errors.append("root config V6 A-only/dual precheck manifest hashes differ from the locked evidence")
    if config.get("v6_precheck_pair_audit_sha256") != formal.V6_PRECHECK_PAIR_AUDIT_SHA256:
        errors.append("root config V6 independent precheck-pair audit hash differs from the locked evidence")
    if config.get("predeclared_plan_sha256", "").upper() != FORMAL_PLAN_SHA256.upper():
        errors.append("root matrix config does not match the locked V9 plan hash")
    if config.get("single_factor") != "active_ble_link_count":
        errors.append("root matrix config does not identify the V9 active-link-count factor")
    if config.get("require_pristine_start") is not True:
        errors.append("root matrix config does not require a fresh boot for every condition")
    errors.extend(forbidden_boot_id_errors(config.get("forbidden_boot_ids_by_node")))
    if config.get("cold_reset_policy") != (
        "operator power-cycles and USB-reenumerates both boards before every scheduled condition"
    ):
        errors.append("root matrix config cold-reset policy differs from the locked V9 plan")
    if config.get("cdc_capture_policy") != (
        "new per-run CDC capture threads and run-local complete byte streams"
    ):
        errors.append("root matrix config does not require isolated full CDC captures per run")
    if config.get("schedule_seed") != formal.FORMAL_SCHEDULE_SEED:
        errors.append("root matrix config schedule seed differs from the locked V9 seed")
    if config.get("firmware_source_commit") != precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT:
        errors.append("root config firmware source commit differs from the locked image")
    if config.get("build_configurations_identical") is not True:
        errors.append("root config does not prove byte-identical Node A/B build configurations")
    if config.get("change_policy") != {
        "connection_parameter_request": False,
        "completion_driven_tx": True,
        "host_disk_write_decoupling": False,
        "tx_queue_capacity_change": False,
    }:
        errors.append("root config change policy differs from the one-factor V9 plan")
    expected_code_hashes = {
        "formal_runner": sha256(Path(formal.__file__)).upper(),
        "independent_auditor": sha256(Path(__file__)).upper(),
        "shared_matrix_runner": sha256(Path(matrix_runner.__file__)).upper(),
        "precheck_helpers": sha256(Path(precheck.__file__)).upper(),
    }
    if config.get("acquisition_code_hashes") != expected_code_hashes:
        errors.append("root config acquisition code hashes differ from the locked source files")
    if result.get("lock_head") != config.get("git_head"):
        errors.append("root config lock HEAD is inconsistent")
    for node in (NodeId.A, NodeId.B):
        name = node.name
        image = config.get("firmware_images", {}).get(name, {})
        build = config.get("build_configs", {}).get(name, {})
        board = config.get("boards", {}).get(name, {})
        expected_usb_serial = matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node]
        if image.get("sha256", "").upper() != precheck.PRECHECK_IMAGE_SHA256[node]:
            errors.append(f"root config Node {name} UF2 hash differs from the locked image")
        if build.get("sha256", "").upper() != precheck.PRECHECK_CONFIG_SHA256:
            errors.append(f"root config Node {name} build config hash differs")
        if (
            board.get("board_id") != precheck.PRECHECK_BOARD_ID
            or board.get("node_id") != int(node)
            or board.get("expected_hardware_device_id") != precheck.PRECHECK_HARDWARE_DEVICE_IDS[node]
            or board.get("bootloader_usb_serial") != expected_usb_serial
        ):
            errors.append(f"root config Node {name} board/serial/device identity differs")
        copied_image = root_dir / "firmware" / f"node-{name.lower()}.uf2"
        copied_config = root_dir / "firmware" / f"node-{name.lower()}.config"
        if not copied_image.is_file() or sha256(copied_image).upper() != precheck.PRECHECK_IMAGE_SHA256[node]:
            errors.append(f"copied Node {name} UF2 is missing or has a different hash")
        if not copied_config.is_file() or sha256(copied_config).upper() != precheck.PRECHECK_CONFIG_SHA256:
            errors.append(f"copied Node {name} build config is missing or has a different hash")
    source_preflash = root_dir / "source_preflash_record.json"
    if (
        not source_preflash.is_file()
        or sha256(source_preflash).upper() != precheck.PRECHECK_SOURCE_PREFLASH_SHA256
    ):
        errors.append("copied source preflash identity record is missing or has a different hash")
    adapter = config.get("host", {}).get("ble_controller_live_inventory", {})
    if (
        not isinstance(adapter, dict)
        or not str(adapter.get("instance_id", "")).startswith(precheck.PRECHECK_ADAPTER_INSTANCE_PREFIX)
        or str(adapter.get("driver_inf", "")).casefold()
        != precheck.PRECHECK_ADAPTER_DRIVER_INF.casefold()
        or adapter.get("driver_version") != precheck.PRECHECK_ADAPTER_DRIVER_VERSION
        or adapter.get("status") != "OK"
    ):
        errors.append("root config live Windows adapter identity differs from the V9 lock")
    plan_copy = root_dir / "PREDECLARED_PLAN.md"
    if not plan_copy.is_file() or sha256(plan_copy).upper() != FORMAL_PLAN_SHA256.upper():
        errors.append("copied predeclared plan is missing or its hash differs")
    expected_order = formal.formal_order(4)
    if config.get("run_order") != list(expected_order):
        errors.append("root config run order differs from the predeclared V9 schedule")
    if result.get("schema") != "kineimu.m1.ble-link-count-formal-v9-result/1.0":
        errors.append("root matrix result has the wrong V9 schema")
    if result.get("run_order") != list(expected_order):
        errors.append("result run order differs from the predeclared V9 schedule")
    run_results = result.get("run_results")
    runs = run_results if isinstance(run_results, list) else []
    if result.get("scheduled_count") != len(expected_order):
        errors.append("matrix result does not record all 16 scheduled conditions")
    if result.get("schedule_attempted_count") != len(runs):
        errors.append("matrix result attempted count does not reconcile with run records")
    if result.get("all_scheduled_runs_attempted") is not (len(runs) == len(expected_order)):
        errors.append("matrix result all-scheduled-runs flag is inconsistent")
    for attempted in runs:
        run_index = attempted.get("run_index")
        confirmed_reset = attempted.get("operator_reset_confirmation", {})
        if not isinstance(confirmed_reset, dict) or confirmed_reset.get(
            "operator_asserted_both_boards_power_cycled"
        ) is not True:
            continue
        for node in ("A", "B"):
            acknowledgment = attempted.get("off_control_acknowledgments", {}).get(node, {})
            cleanup = attempted.get("final_off_cleanup", {}).get(node, {})
            if (
                acknowledgment.get("requested") != "OFF"
                or acknowledgment.get("applied") is not True
                or acknowledgment.get("rc") != 0
            ):
                errors.append(f"run {run_index} Node {node} fixed-OFF acknowledgment failed")
            if (
                cleanup.get("requested") != "OFF"
                or cleanup.get("applied") is not True
                or cleanup.get("rc") != 0
            ):
                errors.append(f"run {run_index} Node {node} final OFF cleanup failed")

    expected_head = config.get("git_head")
    if not isinstance(expected_head, str) or len(expected_head) != 40:
        errors.append("root config does not identify a full lock commit SHA")
        expected_head = ""
    run_audits: list[JSON] = []
    for run_index, condition in enumerate(expected_order, start=1):
        if run_index > len(runs):
            run_audits.append(
                {
                    "run_index": run_index,
                    "condition": condition,
                    "valid": False,
                    "errors": ["scheduled condition was not attempted before the stop condition"],
                }
            )
            continue
        attempted = runs[run_index - 1]
        if attempted.get("condition") != condition or attempted.get("run_index") != run_index:
            errors.append(f"run index {run_index} does not match the locked condition order")
            run_audits.append(
                {
                    "run_index": run_index,
                    "condition": condition,
                    "valid": False,
                    "errors": ["recorded attempt differs from the predeclared schedule"],
                }
            )
            continue
        run_audit = _audit_run(
            root_dir,
            run_index,
            condition,
            expected_head,
            root_control_events,
        )
        if attempted.get("error") is not None:
            run_audit.setdefault("errors", []).append(
                f"acquisition attempt failed: {attempted.get('error')}"
            )
            run_audit["valid"] = False
        run_audits.append(run_audit)
    boot_id_errors, repeated_boot_runs = _unique_boot_id_errors(run_audits)
    errors.extend(boot_id_errors)
    for run_audit in run_audits:
        if run_audit.get("run_index") in repeated_boot_runs:
            run_audit.setdefault("errors", []).append("boot ID was reused across scheduled conditions")
            run_audit["valid"] = False
    integrity_valid = (
        not errors
        and len(runs) == len(expected_order)
        and all(run.get("valid") is True for run in run_audits)
        and result.get("stop_reason") is None
    )

    packets_by_block, per_node_ratios, ratio_details = _comparison_rows(run_audits)
    first_second = ratio_details.get("first_to_second", {}) if ratio_details else {}
    transport_clean = integrity_valid and all(
        run.get("transport_clean") is True for run in run_audits
    )
    if per_node_ratios and first_second:
        decision = formal.classify_factor_effect(
            per_node_ratios,
            first_second,
            integrity_valid=integrity_valid,
            transport_clean=transport_clean,
        )
    else:
        decision = {
            "disposition": "Inconclusive",
            "reason": "four complete same-block control sets could not be derived from raw evidence",
        }
    tx_by_block = ratio_details.get("tx_by_block", []) if ratio_details else []
    mechanism = _mechanism_assessment(per_node_ratios, tx_by_block)

    manifest_after = verify_manifest(root_dir)
    raw_hashes_after = raw_input_hashes(root_dir)
    if manifest_after.get("sha256") != manifest.get("sha256"):
        errors.append("manifest changed during independent audit")
    if raw_hashes_after != raw_hashes_before:
        errors.append("raw CDC/KIMU/event-sidecar hashes changed during independent audit")
    integrity_valid = integrity_valid and not errors
    if not integrity_valid:
        decision = {
            "disposition": "Inconclusive",
            "reason": "; ".join(errors[:8]) or "one or more scheduled run integrity gates failed",
        }
    report: JSON = {
        "schema": "kineimu.m1.ble-link-count-formal-v9-independent-audit/1.0",
        "analysis_source": (
            "matrix config/result + root control events + reset/capture summaries + raw full/run-local CDC "
            "+ raw KIMU + event sidecars + SHA256SUMS; prior audit reports were not read"
        ),
        "matrix_audit_json_used": False,
        "root_dir": str(root_dir.resolve()),
        "lock_head": expected_head,
        "plan_sha256": FORMAL_PLAN_SHA256,
        "manifest": manifest_after,
        "raw_input_hashes_before": raw_hashes_before,
        "raw_input_hashes_after": raw_hashes_after,
        "raw_inputs_unchanged": raw_hashes_after == raw_hashes_before,
        "scheduled_count": len(expected_order),
        "attempted_count": len(runs),
        "integrity_valid": integrity_valid,
        "transport_clean": transport_clean,
        "decision": decision,
        "matched_packet_counts_by_block": packets_by_block,
        "per_node_dual_to_single_ratios": per_node_ratios,
        "first_to_second_ratios": first_second,
        "mechanism_assessment": mechanism,
        "runs": run_audits,
        "errors": errors,
    }
    report["disposition"] = decision["disposition"]
    if output_json is not None:
        if output_json.resolve().is_relative_to(root_dir.resolve()):
            raise ValueError("independent audit report must be outside the immutable raw root")
        with output_json.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        report["output_json"] = str(output_json.resolve())
        report["output_sha256"] = sha256(output_json).upper()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-dir", type=Path, default=FORMAL_OUTPUT_ROOT)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("<external-data>/kineimu_m1_root_cause_formal_v9_20260924_01_independent.json"),
    )
    args = parser.parse_args()
    try:
        report = audit_formal_root(args.root_dir, output_json=args.output_json)
    except (OSError, ValueError, RuntimeError, TypeError) as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("integrity_valid") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
