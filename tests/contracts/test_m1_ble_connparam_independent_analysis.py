"""Predeclared v2 disposition rules for independent matrix recalculation."""

from __future__ import annotations

import pytest

from experiments.m1_ble_connparam_independent_analysis import (
    audit_cdc_control_events,
    audit_run_timing_events,
    classify_predeclared_outcome,
)


def _dual_runs(
    *,
    on_ratio: float,
    off_ratio: float,
    on_first_second: float,
    off_first_second: float,
    on_age_bucket: int,
    off_age_bucket: int,
    on_retry_rate: float,
    off_retry_rate: float,
    on_wait_rate: float,
    off_wait_rate: float,
) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    for block, mode in ((1, "OFF"), (2, "ON"), (3, "ON"), (4, "OFF")):
        ratio = on_ratio if mode == "ON" else off_ratio
        first_second = on_first_second if mode == "ON" else off_first_second
        age = on_age_bucket if mode == "ON" else off_age_bucket
        retries = on_retry_rate if mode == "ON" else off_retry_rate
        wait = on_wait_rate if mode == "ON" else off_wait_rate
        for condition in ("dual_b_to_a", "dual_a_to_b"):
            runs.append(
                {
                    "block": block,
                    "mode": mode,
                    "condition": condition,
                    "first_to_second_throughput_ratio": first_second,
                    "nodes": {
                        node: {
                            "dual_to_single_ratio": ratio,
                            "raw_capture": {"valid_packets": 95},
                            "capture_quality": {
                                "event_crc_false": 0,
                                "event_decode_failures": 0,
                                "raw_crc_errors": 0,
                                "raw_decode_errors": 0,
                                "raw_framing_errors": 0,
                            },
                            "tx_diagnostics": {
                                "delta_quality": "exact",
                                "total_counter_deltas": {"packet_drops": 0},
                                "completion_age_p95_bucket": {"bucket_index": age},
                                "rates": {
                                    "retry_calls_per_notification_submission": retries,
                                    "full_window_wait_us_per_notification_submission": wait,
                                },
                            },
                        }
                        for node in ("A", "B")
                    },
                }
            )
    return runs


def test_off_tuple_contrast_failure_forces_inconclusive_even_if_transport_gates_pass() -> None:
    runs = _dual_runs(
        on_ratio=0.95,
        off_ratio=0.40,
        on_first_second=0.95,
        off_first_second=0.40,
        on_age_bucket=1,
        off_age_bucket=3,
        on_retry_rate=0.5,
        off_retry_rate=2.0,
        on_wait_rate=10.0,
        off_wait_rate=100.0,
    )

    result = classify_predeclared_outcome(
        runs, manipulation_realized=False, data_complete=True
    )

    assert result["label"] == "inconclusive"
    assert result["gates"]["all_on_dual_transport_thresholds_met"] is True
    assert result["classification_reasons"]


def test_supported_requires_realized_contrast_complete_data_and_all_support_gates() -> None:
    runs = _dual_runs(
        on_ratio=0.95,
        off_ratio=0.40,
        on_first_second=0.95,
        off_first_second=0.40,
        on_age_bucket=1,
        off_age_bucket=3,
        on_retry_rate=0.5,
        off_retry_rate=2.0,
        on_wait_rate=10.0,
        off_wait_rate=100.0,
    )

    result = classify_predeclared_outcome(
        runs, manipulation_realized=True, data_complete=True
    )

    assert result["label"] == "supported"
    assert result["gates"]["all_on_dual_transport_thresholds_met"] is True
    assert result["gates"]["support_mechanism_gate_met"] is True


def test_not_supported_requires_below_threshold_results_and_no_mechanism_improvement() -> None:
    runs = _dual_runs(
        on_ratio=0.20,
        off_ratio=0.30,
        on_first_second=0.20,
        off_first_second=0.30,
        on_age_bucket=4,
        off_age_bucket=2,
        on_retry_rate=3.0,
        off_retry_rate=1.0,
        on_wait_rate=150.0,
        off_wait_rate=80.0,
    )

    result = classify_predeclared_outcome(
        runs, manipulation_realized=True, data_complete=True
    )

    assert result["label"] == "not supported"
    assert result["gates"]["all_on_dual_transport_thresholds_below"] is True
    assert result["gates"]["not_supported_median_gate_met"] is True


def test_incomplete_required_data_forces_inconclusive() -> None:
    runs = _dual_runs(
        on_ratio=0.95,
        off_ratio=0.40,
        on_first_second=0.95,
        off_first_second=0.40,
        on_age_bucket=1,
        off_age_bucket=3,
        on_retry_rate=0.5,
        off_retry_rate=2.0,
        on_wait_rate=10.0,
        off_wait_rate=100.0,
    )

    result = classify_predeclared_outcome(
        runs, manipulation_realized=True, data_complete=False
    )

    assert result["label"] == "inconclusive"
    assert result["gates"]["data_complete"] is False


def _control_fixture() -> tuple[list[dict[str, object]], dict[str, object]]:
    events: list[dict[str, object]] = []
    initial: dict[str, object] = {}
    final: dict[str, object] = {}
    transaction_ns = 1_000_000_000
    next_tx = {"A": 1, "B": 1}

    def request(node: str, session: str, node_id: int, tx: int, mode: str) -> dict[str, object]:
        nonlocal transaction_ns
        command = f"SET session={session} tx={tx} mode={mode}"
        byte_count = len(command.encode("ascii")) + 1
        events.append({
            "event": "conn_param_request_write",
            "node": node,
            "node_id": node_id,
            "session": session,
            "tx": tx,
            "requested": mode,
            "command": command,
            "byte_count": byte_count,
            "expected_byte_count": byte_count,
            "host_monotonic_ns": transaction_ns,
        })
        events.append({
            "event": "conn_param_request_ack",
            "node": node,
            "node_id": node_id,
            "session": session,
            "tx": tx,
            "requested": mode,
            "selected": mode,
            "rc": 0,
            "host_monotonic_ns": transaction_ns + 10_000_000,
        })
        transaction_ns += 20_000_000
        return {
            "acknowledged": True,
            "applied": True,
            "error": None,
            "node_id": node_id,
            "rc": 0,
            "requested": mode,
            "selected": mode,
            "session": session,
            "tx": tx,
        }

    for node, node_id in (("A", 1), ("B", 2)):
        initial_session = f"initial-{node}"
        events.extend([
            {"event": "conn_param_control_hello_write", "node": node, "node_id": node_id, "session": initial_session},
            {
                "event": "conn_param_control_ready",
                "node": node,
                "node_id": node_id,
                "observed_node_id": node_id,
                "session": initial_session,
            },
        ])
        requests = [
            request(node, initial_session, node_id, tx, mode)
            for tx, mode in enumerate(("OFF", "ON", "OFF"), 1)
        ]
        initial[node] = {
            "control_ready": True,
            "node_id": node_id,
            "ready_result": {"session": initial_session},
            "session": initial_session,
            "requests": requests,
        }
        next_tx[node] = 4

    blocks: list[dict[str, object]] = []
    for block, mode in enumerate(("OFF", "ON", "ON", "OFF"), 1):
        details: dict[str, object] = {}
        for node, node_id in (("A", 1), ("B", 2)):
            tx = next_tx[node]
            next_tx[node] += 1
            details[node] = request(node, f"initial-{node}", node_id, tx, mode)
        blocks.append({"block": block, "request_mode": mode, "nodes": details})

    for node, node_id in (("A", 1), ("B", 2)):
        final_session = f"final-{node}"
        events.extend([
            {"event": "conn_param_control_hello_write", "node": node, "node_id": node_id, "session": final_session},
            {
                "event": "conn_param_control_ready",
                "node": node,
                "node_id": node_id,
                "observed_node_id": node_id,
                "session": final_session,
            },
        ])
        details = request(node, final_session, node_id, 1, "OFF")
        final[node] = {
            **details,
            "ready": True,
            "ready_result": {"session": final_session},
        }
    return events, {
        "initial_control_handshake": initial,
        "block_mode_control": blocks,
        "final_control_cleanup": final,
    }


def test_control_audit_requires_nonce_bound_exact_ready_and_ack_transactions() -> None:
    events, result = _control_fixture()

    audit = audit_cdc_control_events(events, result)

    assert audit["valid"] is True
    assert audit["hello_count"] == audit["ready_count"] == 4
    assert audit["request_write_count"] == audit["ack_count"] == 16
    assert audit["matched_transaction_count"] == 16
    assert audit["ack_latency_ms"]["max"] == 10.0


def test_control_audit_rejects_an_ack_for_a_different_transaction() -> None:
    events, result = _control_fixture()
    wrong_ack = next(event for event in events if event.get("event") == "conn_param_request_ack")
    wrong_ack["tx"] = 900

    audit = audit_cdc_control_events(events, result)

    assert audit["valid"] is False
    assert any("ACK has no matching write" in error for error in audit["errors"])


def _timing_events(
    *, observed_window_s: float = 10.0, telemetry_offset_s: float = 10.1
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    base = 1_000_000_000
    settle_complete_ns = base + 15_500_000_000
    connected_ns = base + 5_500_000_000
    update_ns = base + 8_000_000_000
    capture_start_host_ns = settle_complete_ns + 100_000_000
    # Model distinct Windows clock origins: perf_counter is ahead of the
    # GetTickCount64-backed monotonic clock by about 395 ms on this runtime.
    capture_start_perf_ns = capture_start_host_ns + 395_000_000
    connected_line = (
        "Node A: BLE link event=connected firmware_uptime_ms=1000 info_rc=0 "
        "interval_us=12500 latency=0 supervision_timeout_us=9600000"
    )
    update = {
        "firmware_event": "param_updated",
        "firmware_uptime_ms": 3500,
        "host_monotonic_ns": update_ns,
        "interval_us": 15000,
        "latency": 0,
        "supervision_timeout_us": 420000,
    }
    control = [
        {
            "event": "ble_scan_start",
            "node": "A",
            "address": "02:00:00:00:00:01",
            "service_uuid": "f7d20001-4b49-4e45-494d-552d53484c44",
            "timeout_s": 5.0,
            "cleanup_grace_s": 1.0,
            "host_monotonic_ns": base,
        },
        {
            "event": "ble_scan_complete",
            "node": "A",
            "address": "02:00:00:00:00:01",
            "observed_address": "02:00:00:00:00:01",
            "duration_ns": 5_100_000_000,
            "host_monotonic_ns": base + 5_100_000_000,
        },
        {
            "event": "ble_os_connect_start",
            "node": "A",
            "address": "02:00:00:00:00:01",
            "host_monotonic_ns": base + 5_200_000_000,
        },
        {
            "event": "peripheral_connected_event",
            "node": "A",
            "connect_attempt": 1,
            "host_monotonic_ns": connected_ns,
            "peripheral_event_host_monotonic_ns": connected_ns,
            "peripheral_event_firmware_uptime_ms": 1000,
            "firmware_event_line": connected_line,
        },
        {
            "event": "peripheral_param_updated",
            "node": "A",
            "connect_attempt": 1,
            "host_monotonic_ns": update_ns,
            **{key: value for key, value in update.items() if key != "firmware_event"},
        },
        {
            "event": "ble_gatt_service_discovery",
            "node": "A",
            "call_index": 1,
            "duration_ns": 500_000_000,
            "host_monotonic_ns": base + 6_200_000_000,
        },
        {
            "event": "ble_connect_total",
            "node": "A",
            "duration_ns": 1_000_000_000,
            "succeeded": True,
            "host_monotonic_ns": base + 6_200_000_000,
        },
        {"event": "ble_os_connect_return", "node": "A", "host_monotonic_ns": base + 6_200_000_000},
        {
            "event": "ble_mtu_observed",
            "node": "A",
            "duration_ns": 10_000_000,
            "host_monotonic_ns": base + 6_300_000_000,
        },
        {
            "event": "ble_gatt_read_complete",
            "node": "A",
            "phase": "identity",
            "duration_ns": 20_000_000,
            "host_monotonic_ns": base + 6_400_000_000,
        },
        {
            "event": "ble_gatt_read_complete",
            "node": "A",
            "phase": "status",
            "duration_ns": 20_000_000,
            "host_monotonic_ns": base + 6_500_000_000,
        },
        {
            "event": "connection_parameter_settle_complete",
            "host_monotonic_ns": settle_complete_ns,
            "planned_duration_s": 10.0,
            "observed_duration_s_by_node": {"A": observed_window_s},
            "target_observed_by_node": {"A": True},
            "parameter_updates_by_node": {
                "A": [
                    {
                        "firmware_event": "connected",
                        "firmware_uptime_ms": 1000,
                        "host_monotonic_ns": connected_ns,
                        "interval_us": 12500,
                        "latency": 0,
                        "supervision_timeout_us": 9600000,
                    },
                    update,
                ]
            },
        },
        {
            "event": "telemetry_notify_enabled",
            "node": "A",
            "host_monotonic_ns": base + int(5_500_000_000 + telemetry_offset_s * 1_000_000_000),
        },
        {
            "event": "matrix_capture_window",
            "node": "A",
            "anchor": "shared_recorder_ready_barrier",
            "host_monotonic_ns": capture_start_host_ns,
            "capture_clock_domain": "perf_counter_ns",
            "capture_start_perf_counter_ns": capture_start_perf_ns,
            "capture_deadline_perf_counter_ns": capture_start_perf_ns + 15_000_000_000,
            "capture_start_host_monotonic_ns": capture_start_host_ns,
            "capture_deadline_host_monotonic_ns": capture_start_host_ns + 15_000_000_000,
            "capture_clock_pair_uncertainty_ns": 3000,
            "duration_ns": 15_000_000_000,
        },
    ]
    capture = [
        {
            "event": "config",
            "source": "read",
            "node_id": 1,
            "hardware_device_id": 1,
            "firmware_git_commit": "270911756c227a20feb18df71edad7ad4544aedb",
        },
        {"event": "mtu", "accepted": True, "mtu": 127, "required_mtu": 127},
        {
            "event": "notify_callback_timing",
            "host_monotonic_ns": capture_start_host_ns + 50_000_000,
            "callback_start_host_monotonic_ns": capture_start_host_ns + 50_000_000,
            "callback_start_perf_counter_ns": capture_start_perf_ns + 50_000_000,
            "capture_clock_domain": "perf_counter_ns",
            "capture_window_check_perf_counter_ns": capture_start_perf_ns + 50_000_000,
            "capture_window_accepted": True,
        },
        {
            "event": "notify_callback_timing",
            "host_monotonic_ns": capture_start_host_ns + 14_950_000_000,
            "callback_start_host_monotonic_ns": capture_start_host_ns + 14_950_000_000,
            "callback_start_perf_counter_ns": capture_start_perf_ns + 14_950_000_000,
            "capture_clock_domain": "perf_counter_ns",
            "capture_window_check_perf_counter_ns": capture_start_perf_ns + 14_950_000_000,
            "capture_window_accepted": True,
        },
    ]
    return control, capture


def test_timing_audit_separates_scan_from_connect_and_anchors_full_window_to_connected() -> None:
    control, capture = _timing_events()

    result = audit_run_timing_events(
        control,
        {"A": capture},
        active_nodes=["A"],
        settle_seconds=10.0,
        capture_seconds=15.0,
        connect_gatt_timeout_seconds=15.0,
    )

    assert result["valid"] is True
    assert result["nodes"]["A"]["scan"]["duration_s"] == 5.1
    assert result["nodes"]["A"]["connect_gatt"]["duration_s"] == 1.0
    assert result["nodes"]["A"]["parameter_window"]["anchor"] == "firmware_cdc_peripheral_connected_event"
    assert result["nodes"]["A"]["parameter_window"]["observed_duration_s"] == 10.0
    assert result["nodes"]["A"]["capture"]["callback_span_s"] == 14.9


def test_timing_audit_can_use_exact_window_without_minimum_callback_span_gate() -> None:
    control, capture = _timing_events()
    marker = next(event for event in control if event.get("event") == "matrix_capture_window")
    start_perf_ns = marker["capture_start_perf_counter_ns"]
    start_host_ns = marker["capture_start_host_monotonic_ns"]
    first_offset_ns = 120_000_000
    last_offset_ns = 14_980_000_000
    for event, offset_ns in zip(capture[2:], (first_offset_ns, last_offset_ns), strict=True):
        event["host_monotonic_ns"] = start_host_ns + offset_ns
        event["callback_start_host_monotonic_ns"] = start_host_ns + offset_ns
        event["callback_start_perf_counter_ns"] = start_perf_ns + offset_ns
        event["capture_window_check_perf_counter_ns"] = start_perf_ns + offset_ns

    legacy_result = audit_run_timing_events(
        control,
        {"A": capture},
        active_nodes=["A"],
        settle_seconds=10.0,
        capture_seconds=15.0,
        connect_gatt_timeout_seconds=15.0,
    )
    precheck_result = audit_run_timing_events(
        control,
        {"A": capture},
        active_nodes=["A"],
        settle_seconds=10.0,
        capture_seconds=15.0,
        connect_gatt_timeout_seconds=15.0,
        require_full_callback_span=False,
    )

    # The expected 14.86 s span is the synthetic last offset minus first offset;
    # the locked capture marker still proves an exact 15.000 s interval.
    assert precheck_result["nodes"]["A"]["capture"]["callback_span_s"] == pytest.approx(14.86)
    assert precheck_result["nodes"]["A"]["capture"]["window_duration_ns"] == 15_000_000_000
    assert precheck_result["valid"] is True
    # The default remains the historic v2 rule so its disposition is unchanged.
    assert legacy_result["valid"] is False
    assert any("callbacks do not span" in error for error in legacy_result["errors"])


def test_timing_audit_requires_explicit_capture_boundary_and_rejects_late_raw_callback() -> None:
    control, capture = _timing_events()
    control = [event for event in control if event.get("event") != "matrix_capture_window"]

    result = audit_run_timing_events(
        control,
        {"A": capture},
        active_nodes=["A"],
        settle_seconds=10.0,
        capture_seconds=15.0,
        connect_gatt_timeout_seconds=15.0,
    )

    assert result["valid"] is False
    assert any("capture-window marker" in error for error in result["errors"])


def test_timing_audit_rejects_callback_claimed_accepted_after_deadline() -> None:
    control, capture = _timing_events()
    late = capture[-1]
    marker = next(event for event in control if event.get("event") == "matrix_capture_window")
    late["capture_window_check_perf_counter_ns"] = marker["capture_deadline_perf_counter_ns"] + 1

    result = audit_run_timing_events(
        control,
        {"A": capture},
        active_nodes=["A"],
        settle_seconds=10.0,
        capture_seconds=15.0,
        connect_gatt_timeout_seconds=15.0,
    )

    assert result["valid"] is False
    assert any("admission flags that disagree" in error for error in result["errors"])


def test_timing_audit_rejects_short_window_and_telemetry_before_settle_complete() -> None:
    control, capture = _timing_events(observed_window_s=9.999, telemetry_offset_s=9.9)

    result = audit_run_timing_events(
        control,
        {"A": capture},
        active_nodes=["A"],
        settle_seconds=10.0,
        capture_seconds=15.0,
        connect_gatt_timeout_seconds=15.0,
    )

    assert result["valid"] is False
    assert any("shorter than" in error or "before" in error for error in result["errors"])


def test_timing_audit_uses_only_parameter_callbacks_inside_the_full_window() -> None:
    control, capture = _timing_events()
    late_update = {
        "event": "peripheral_param_updated",
        "node": "A",
        "host_monotonic_ns": 17_000_000_000,
        "firmware_uptime_ms": 12000,
        "interval_us": 15000,
        "latency": 0,
        "supervision_timeout_us": 420000,
    }
    control = [event for event in control if event.get("event") != "peripheral_param_updated"]
    control.append(late_update)
    settle = next(event for event in control if event.get("event") == "connection_parameter_settle_complete")
    settle["target_observed_by_node"] = {"A": False}
    settle["parameter_updates_by_node"] = {
        "A": [settle["parameter_updates_by_node"]["A"][0]]
    }

    result = audit_run_timing_events(
        control,
        {"A": capture},
        active_nodes=["A"],
        settle_seconds=10.0,
        capture_seconds=15.0,
        connect_gatt_timeout_seconds=15.0,
    )

    window = result["nodes"]["A"]["parameter_window"]
    assert result["valid"] is True
    assert window["target_observed"] is False
    assert window["param_updated_callback_count"] == 0
    assert window["callback_count"] == 1
