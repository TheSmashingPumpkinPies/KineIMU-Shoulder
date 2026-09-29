from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import cast

import pytest

from experiments import m1_ble_link_matrix as matrix_runner
from experiments import m1_ble_link_precheck as precheck
from experiments.m1_ble_connparam_independent_analysis import verify_manifest
from kineimu_shoulder.io.m1_ble import NodeTarget
from kineimu_shoulder.io.m1_capture import encode_capture_record
from kineimu_shoulder.io.m1_packet import (
    NodeId,
    Sample,
    SampleFlags,
    SamplePacket,
    encode_sample_packet,
)


def test_precheck_schedule_is_fixed_off_and_covers_both_links_and_orders() -> None:
    assert precheck.PRECHECK_SCHEDULE == (
        ("OFF", ("a_only", "dual_a_to_b", "b_only", "dual_b_to_a")),
    )
    conditions = precheck.precheck_order()
    assert conditions == ("a_only", "dual_a_to_b", "b_only", "dual_b_to_a")
    assert precheck.active_nodes_for_condition("a_only") == ("A",)
    assert precheck.active_nodes_for_condition("b_only") == ("B",)
    assert precheck.active_nodes_for_condition("dual_a_to_b") == ("A", "B")
    assert precheck.active_nodes_for_condition("dual_b_to_a") == ("B", "A")
    assert precheck.active_nodes_for_condition("dual_a_to_b") != precheck.active_nodes_for_condition(
        "dual_b_to_a"
    )
    policy = matrix_runner._change_policy(
        True,
        connection_parameter_request=False,
    )
    assert policy == {
        "connection_parameter_request": False,
        "completion_driven_tx": True,
        "host_disk_write_decoupling": False,
        "tx_queue_capacity_change": False,
    }


def _assert_dual_link_state_is_realized(
    condition: str,
    connect_order: tuple[str, str],
) -> None:
    capture_start = 1_000_000_000
    capture_deadline = capture_start + 15_000_000_000
    events = [
        {
            "event": "peripheral_connected_event",
            "node": node,
            "host_monotonic_ns": capture_start - (200_000_000 - index * 100_000_000),
        }
        for index, node in enumerate(connect_order)
    ]
    for offset, node in enumerate(connect_order):
        start = capture_start + offset * 10_000
        events.append(
            {
                "event": "matrix_capture_window",
                "node": node,
                "capture_start_host_monotonic_ns": start,
                "capture_deadline_host_monotonic_ns": start + 15_000_000_000,
                "capture_start_perf_counter_ns": start,
                "capture_deadline_perf_counter_ns": start + 15_000_000_000,
            }
        )
    events.extend(
        {
            "event": "peripheral_disconnected_event",
            "node": node,
            "host_monotonic_ns": capture_deadline + 10_000_000,
        }
        for node in connect_order
    )

    result = precheck.audit_active_link_state(condition, events)
    assert result["realized"] is True
    assert result["expected_active_links"] == 2
    assert result["observed_connection_order"] == list(connect_order)
    assert result["concurrent_capture_overlap_ns"] >= 14_999_000_000


def test_dual_link_state_is_realized_for_a_then_b_over_shared_capture() -> None:
    _assert_dual_link_state_is_realized("dual_a_to_b", ("A", "B"))


def test_dual_link_state_is_realized_for_b_then_a_over_shared_capture() -> None:
    _assert_dual_link_state_is_realized("dual_b_to_a", ("B", "A"))


def test_physical_connection_tx_summary_keeps_queue_transition_totals() -> None:
    """A queue epoch label change must not discard cumulative connection totals."""
    counter_names = (
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

    def snapshot(
        line: int,
        generation: int,
        *,
        calls: int,
        accepted: int,
        completed: int,
    ) -> dict[str, object]:
        values = {name: 0 for name in counter_names}
        values.update(calls=calls, accepted=accepted, completed=completed)
        return {
            **values,
            "line": line,
            "boot": 9353023436044725051,
            "generation": generation,
            "schedule_fail": [0, 0],
            "return_counts": {"0": accepted, "-12": calls - accepted},
            "saturated": 0,
            "parse_errors": [],
            "age_bins": [0] * 8,
            "age_us": [0, 0, 0, completed],
            "window_owned": 0,
            "inflight": [0, 8],
        }

    snapshots = [
        snapshot(1, 2, calls=10, accepted=8, completed=5),
        snapshot(2, 2, calls=20, accepted=13, completed=12),
        snapshot(3, 3, calls=25, accepted=15, completed=20),
        snapshot(4, 3, calls=25, accepted=15, completed=27),
        snapshot(5, 4, calls=25, accepted=15, completed=27),
    ]
    tx_summary = {
        "snapshot_count": 5,
        "delta_quality": "incomplete_or_lower_bound",
        "segments": [
            {
                "connection_generation": 2,
                "first_line": 1,
                "last_line": 2,
                "delta_quality": "exact",
                "counter_deltas": {
                    **{name: 0 for name in counter_names},
                    "calls": 10,
                    "accepted": 5,
                    "completed": 7,
                },
            },
            {
                "connection_generation": 3,
                "first_line": 3,
                "last_line": 4,
                "delta_quality": "exact",
                "counter_deltas": {
                    **{name: 0 for name in counter_names},
                    "completed": 7,
                },
            },
            {
                "connection_generation": 4,
                "first_line": 5,
                "last_line": 5,
                "delta_quality": "incomplete_or_lower_bound",
                "counter_deltas": {
                    **{name: 0 for name in counter_names},
                },
            },
        ],
    }

    result = precheck.summarize_physical_connection_tx(
        tx_summary,
        snapshots,
        expected_boot_id=9353023436044725051,
    )

    assert result["active_queue_generations"] == [2]
    assert result["physical_connection_totals"]["calls"] == 25
    assert result["physical_connection_totals"]["accepted"] == 15
    assert result["physical_connection_totals"]["completed"] == 27
    assert result["transition_deltas"][0]["from_generation"] == 2
    assert result["transition_deltas"][0]["to_generation"] == 3
    assert result["transition_deltas"][0]["counter_deltas"]["calls"] == 5
    assert result["transition_deltas"][0]["counter_deltas"]["accepted"] == 2
    assert result["transition_deltas"][1]["from_generation"] == 3
    assert result["transition_deltas"][1]["to_generation"] == 4
    assert result["transition_deltas"][1]["counter_deltas"]["calls"] == 0
    assert result["transition_deltas"][1]["counter_deltas"]["accepted"] == 0
    assert result["errors"] == []

    nonmonotonic = [dict(item) for item in snapshots]
    nonmonotonic[-1]["calls"] = 24
    rejected = precheck.summarize_physical_connection_tx(
        tx_summary,
        nonmonotonic,
        expected_boot_id=9353023436044725051,
    )
    assert any("counter calls is not monotonic" in error for error in rejected["errors"])


def test_v6_records_sequence_gaps_as_outcomes_but_older_plans_reject_them() -> None:
    raw = {"packet_sequence_gaps": 7, "sample_sequence_gaps": 19}

    assert precheck.sample_sequence_gap_errors(
        raw,
        expected_plan_sha256=precheck.PRECHECK_PLAN_V6_SHA256,
        node="A",
    ) == []
    assert precheck.sample_sequence_gap_errors(
        raw,
        expected_plan_sha256=precheck.PRECHECK_PLAN_V5_SHA256,
        node="A",
    ) == ["Node A raw sample sequence has 19 gaps"]
    assert len(
        precheck.sample_sequence_gap_errors(
            {"sample_sequence_gaps": 19},
            expected_plan_sha256=precheck.PRECHECK_PLAN_V6_SHA256,
            node="A",
        )
    ) == 1


def test_link_count_precheck_rejects_disconnect_inside_capture_window() -> None:
    capture_start = 1_000_000_000
    events = [
        {"event": "peripheral_connected_event", "node": "A", "host_monotonic_ns": 10},
        {"event": "peripheral_connected_event", "node": "B", "host_monotonic_ns": 20},
    ]
    for node in ("A", "B"):
        events.append(
            {
                "event": "matrix_capture_window",
                "node": node,
                "capture_start_host_monotonic_ns": capture_start,
                "capture_deadline_host_monotonic_ns": capture_start + 15_000_000_000,
                "capture_start_perf_counter_ns": capture_start,
                "capture_deadline_perf_counter_ns": capture_start + 15_000_000_000,
            }
        )
    events.append(
        {
            "event": "peripheral_disconnected_event",
            "node": "A",
            "host_monotonic_ns": capture_start + 7_000_000_000,
        }
    )

    result = precheck.audit_active_link_state("dual_a_to_b", events)
    assert result["realized"] is False
    assert any("disconnected before" in error for error in result["errors"])


def test_precheck_plan_hash_is_bound_to_one_fixed_output_root(tmp_path: Path) -> None:
    expected = precheck.PRECHECK_PLAN_SHA256
    root = precheck.PRECHECK_OUTPUT_ROOT
    assert precheck.validate_plan_output_root(expected, root) == root.resolve()

    with pytest.raises(ValueError, match="unknown precheck plan"):
        precheck.validate_plan_output_root("0" * 64, root)
    with pytest.raises(ValueError, match="requires locked output root"):
        precheck.validate_plan_output_root(expected, tmp_path / "cross-bound")


def test_v4_cold_start_precheck_binds_one_condition_to_each_empty_root() -> None:
    assert precheck.sha256(precheck.PRECHECK_PLAN_V4_PATH).upper() == (
        precheck.PRECHECK_PLAN_V4_SHA256
    )
    assert precheck.precheck_order("v4", "a_only") == ("a_only",)
    assert precheck.precheck_order("v4", "dual_a_to_b") == ("dual_a_to_b",)
    assert precheck.validate_plan_output_root(
        precheck.PRECHECK_PLAN_V4_SHA256,
        precheck.PRECHECK_V4_OUTPUT_ROOTS["a_only"],
        condition="a_only",
    ) == precheck.PRECHECK_V4_OUTPUT_ROOTS["a_only"].resolve()
    assert precheck.validate_plan_output_root(
        precheck.PRECHECK_PLAN_V4_SHA256,
        precheck.PRECHECK_V4_OUTPUT_ROOTS["dual_a_to_b"],
        condition="dual_a_to_b",
    ) == precheck.PRECHECK_V4_OUTPUT_ROOTS["dual_a_to_b"].resolve()

    with pytest.raises(ValueError, match="requires locked output root"):
        precheck.validate_plan_output_root(
            precheck.PRECHECK_PLAN_V4_SHA256,
            precheck.PRECHECK_V4_OUTPUT_ROOTS["a_only"],
            condition="dual_a_to_b",
        )
    with pytest.raises(ValueError, match="requires one of"):
        precheck.precheck_order("v4")


def test_v5_precheck_locks_new_roots_and_common_30_second_setup_allowance() -> None:
    assert precheck.sha256(precheck.PRECHECK_PLAN_V5_PATH).upper() == (
        precheck.PRECHECK_PLAN_V5_SHA256
    )
    assert precheck.precheck_order("v5", "a_only") == ("a_only",)
    assert precheck.precheck_order("v5", "dual_a_to_b") == ("dual_a_to_b",)
    assert precheck.precheck_connect_timeout_seconds("v3") == 15.0
    assert precheck.precheck_connect_timeout_seconds("v4") == 15.0
    assert precheck.precheck_connect_timeout_seconds("v5") == 30.0
    assert precheck.validate_plan_output_root(
        precheck.PRECHECK_PLAN_V5_SHA256,
        precheck.PRECHECK_V5_OUTPUT_ROOTS["a_only"],
        condition="a_only",
    ) == precheck.PRECHECK_V5_OUTPUT_ROOTS["a_only"].resolve()
    assert precheck.validate_plan_output_root(
        precheck.PRECHECK_PLAN_V5_SHA256,
        precheck.PRECHECK_V5_OUTPUT_ROOTS["dual_a_to_b"],
        condition="dual_a_to_b",
    ) == precheck.PRECHECK_V5_OUTPUT_ROOTS["dual_a_to_b"].resolve()

    with pytest.raises(ValueError, match="requires locked output root"):
        precheck.validate_plan_output_root(
            precheck.PRECHECK_PLAN_V5_SHA256,
            precheck.PRECHECK_V5_OUTPUT_ROOTS["a_only"],
            condition="dual_a_to_b",
        )


def test_v6_precheck_locks_physical_connection_tx_audit_and_fresh_roots() -> None:
    assert precheck.sha256(precheck.PRECHECK_PLAN_V6_PATH).upper() == (
        precheck.PRECHECK_PLAN_V6_SHA256
    )
    assert precheck.precheck_order("v6", "a_only") == ("a_only",)
    assert precheck.precheck_order("v6", "dual_a_to_b") == ("dual_a_to_b",)
    assert precheck.precheck_connect_timeout_seconds("v6") == 30.0
    assert all("_v6_" in str(root) for root in precheck.PRECHECK_V6_OUTPUT_ROOTS.values())
    for condition, root in precheck.PRECHECK_V6_OUTPUT_ROOTS.items():
        assert precheck.validate_plan_output_root(
            precheck.PRECHECK_PLAN_V6_SHA256,
            root,
            condition=condition,
        ) == root.resolve()
    assert precheck.audit_connect_timeout_config(
        {"windows_connect_gatt_setup_timeout_seconds": 30.0},
        precheck.PRECHECK_PLAN_V6_SHA256,
    ) == []
    assert any(
        "V6 allowance (30.0s)" in error
        for error in precheck.audit_connect_timeout_config(
            {"windows_connect_gatt_setup_timeout_seconds": 15.0},
            precheck.PRECHECK_PLAN_V6_SHA256,
        )
    )


def test_cold_start_audit_rejects_a_timeout_that_differs_from_its_locked_plan() -> None:
    assert precheck.audit_connect_timeout_config(
        {"windows_connect_gatt_setup_timeout_seconds": 30.0},
        precheck.PRECHECK_PLAN_V5_SHA256,
    ) == []
    assert any(
        "V5 allowance (30.0s)" in error
        for error in precheck.audit_connect_timeout_config(
            {"windows_connect_gatt_setup_timeout_seconds": 15.0},
            precheck.PRECHECK_PLAN_V5_SHA256,
        )
    )
    # V4 raw run configs predate this explicit field. Keep their audit contract
    # backward-compatible while V5 locks and requires the recorded allowance.
    assert precheck.audit_connect_timeout_config(
        {}, precheck.PRECHECK_PLAN_V4_SHA256
    ) == []


@pytest.mark.parametrize(("recorded_timeout", "expected_pass"), [(30.0, True), (15.0, False)])
def test_v5_single_audit_checks_timeout_and_locked_raw_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recorded_timeout: float,
    expected_pass: bool,
) -> None:
    root = tmp_path / "v5-a-only"
    root.mkdir()
    dual_root = tmp_path / "v5-dual"
    monkeypatch.setattr(
        precheck,
        "PRECHECK_V5_OUTPUT_ROOTS",
        {"a_only": root, "dual_a_to_b": dual_root},
    )
    (root / "PREDECLARED_PRECHECK_PLAN.md").write_bytes(
        precheck.PRECHECK_PLAN_V5_PATH.read_bytes()
    )
    ports = {
        node.name: {
            "device": "COM5" if node is NodeId.A else "COM8",
            "serial_number": matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node],
            "vid": precheck.PRECHECK_RUNTIME_CDC_VID,
            "pid": precheck.PRECHECK_RUNTIME_CDC_PID,
        }
        for node in (NodeId.A, NodeId.B)
    }
    interface = {
        "vid": precheck.PRECHECK_RUNTIME_CDC_VID,
        "pid": precheck.PRECHECK_RUNTIME_CDC_PID,
        "usage": "application CDC; UF2 bootloader interface is forbidden",
    }
    config = {
        "schema": "kineimu.m1.ble-link-count-precheck/2.0",
        "precheck_plan_version": "v5",
        "predeclared_plan_sha256": precheck.PRECHECK_PLAN_V5_SHA256,
        "run_order": ["a_only"],
        "runtime_cdc_interface_expected": interface,
        "firmware_source_commit": precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT,
        "require_pristine_start": True,
        "windows_connect_gatt_setup_timeout_seconds": recorded_timeout,
        "cdc_ports_resolved_by_usb_serial": ports,
        "firmware_images": {
            node.name: {"sha256": precheck.PRECHECK_IMAGE_SHA256[node]}
            for node in (NodeId.A, NodeId.B)
        },
        "build_configs": {
            node.name: {"sha256": precheck.PRECHECK_CONFIG_SHA256}
            for node in (NodeId.A, NodeId.B)
        },
    }
    off_control = {
        node.name: {"requested": "OFF", "applied": True, "rc": 0}
        for node in (NodeId.A, NodeId.B)
    }
    result = {
        "schema": "kineimu.m1.ble-link-count-precheck-result/1.0",
        "run_order": ["a_only"],
        "schedule_attempted_count": 1,
        "scheduled_count": 1,
        "all_scheduled_runs_attempted": True,
        "stop_reason": None,
        "initial_off_control": off_control,
        "final_control_cleanup": off_control,
    }
    (root / "matrix_config.json").write_text(json.dumps(config), encoding="utf-8")
    (root / "matrix_result.json").write_text(json.dumps(result), encoding="utf-8")

    def valid_run_audit(
        _root: Path,
        _run_index: int,
        condition: str,
        *,
        expected_source_commit: str,
        expected_plan_sha256: str,
    ) -> dict[str, object]:
        assert expected_source_commit == precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT
        assert expected_plan_sha256 == precheck.PRECHECK_PLAN_V5_SHA256
        return {"valid": True, "errors": [], "condition": condition, "nodes": {}}

    monkeypatch.setattr(precheck, "_audit_run", valid_run_audit)
    precheck.write_sha256_manifest(root)

    report = precheck.audit_precheck_v5_single(root)

    assert report["manifest_verification"]["valid"] is True
    assert report["raw_inputs_unchanged"] is True
    assert report["precheck_passed"] is expected_pass
    assert (
        any("V5 allowance (30.0s)" in error for error in report["errors"])
        is not expected_pass
    )


def test_v4_pair_audit_rejects_condition_labels_swapped_between_locked_roots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = {
        "a_only": Path("<external-root>/synthetic-v4/a_only"),
        "dual_a_to_b": Path("<external-root>/synthetic-v4/dual_a_to_b"),
    }
    monkeypatch.setattr(precheck, "PRECHECK_V4_OUTPUT_ROOTS", roots)
    shared = {
        "git_head": "abc123",
        "firmware_source_commit": precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT,
        "firmware_images": {"A": "a", "B": "b"},
        "build_configs": {"A": "cfg", "B": "cfg"},
        "build_configurations_identical": True,
        "host": {"controller": "fixed"},
        "ble_addresses": {"A": "A", "B": "B"},
        "expected_hardware_device_ids": {"A": 1, "B": 2},
        "usb_serials": {"A": "SA", "B": "SB"},
    }

    def swapped_audit(condition_root: Path) -> dict[str, object]:
        root_name = next(
            name for name, path in roots.items() if path.resolve() == condition_root
        )
        node_a_boot = 100 if root_name == "a_only" else 200
        node_rows: dict[str, object] = {
            "A": {
                "hardware_device_id": 1,
                "node_id": 1,
                "firmware_git_commit": precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT,
                "mtu": 127,
                "acquisition_start": {"boot_id": node_a_boot},
            }
        }
        active_links = 1 if root_name == "a_only" else 2
        if root_name == "dual_a_to_b":
            node_rows["B"] = {"acquisition_start": {"boot_id": 300}}
        return {
            "precheck_passed": True,
            "condition": "dual_a_to_b" if root_name == "a_only" else "a_only",
            "matrix_config": shared,
            "run": {
                "valid": True,
                "nodes": node_rows,
                "expected_active_links": active_links,
            },
        }

    monkeypatch.setattr(precheck, "audit_precheck_v4_single", swapped_audit)

    report = precheck.audit_precheck_v4_pair()

    assert report["precheck_passed"] is False
    assert any("condition label" in error for error in report["errors"])


def test_v5_pair_audit_requires_matching_timeout_and_distinct_cold_boots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = {
        "a_only": Path("<external-root>/synthetic-v5/a_only"),
        "dual_a_to_b": Path("<external-root>/synthetic-v5/dual_a_to_b"),
    }
    monkeypatch.setattr(precheck, "PRECHECK_V5_OUTPUT_ROOTS", roots)
    shared = {
        "git_head": "abc123",
        "firmware_source_commit": precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT,
        "firmware_images": {"A": "a", "B": "b"},
        "build_configs": {"A": "cfg", "B": "cfg"},
        "build_configurations_identical": True,
        "host": {"controller": "fixed"},
        "windows_connect_gatt_setup_timeout_seconds": 30.0,
        "ble_addresses": {"A": "A", "B": "B"},
        "expected_hardware_device_ids": {"A": 1, "B": 2},
        "usb_serials": {"A": "SA", "B": "SB"},
    }

    def valid_audit(root: Path) -> dict[str, object]:
        root_name = next(name for name, path in roots.items() if path.resolve() == root)
        node_rows: dict[str, object] = {
            "A": {
                "hardware_device_id": 1,
                "node_id": 1,
                "firmware_git_commit": precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT,
                "mtu": 127,
                "acquisition_start": {
                    "boot_id": 100 if root_name == "a_only" else 200
                },
            }
        }
        active_links = 1 if root_name == "a_only" else 2
        if root_name == "dual_a_to_b":
            node_rows["B"] = {"acquisition_start": {"boot_id": 300}}
        return {
            "precheck_passed": True,
            "condition": root_name,
            "matrix_config": shared,
            "run": {
                "valid": True,
                "nodes": node_rows,
                "expected_active_links": active_links,
            },
        }

    monkeypatch.setattr(precheck, "audit_precheck_v5_single", valid_audit)

    report = precheck.audit_precheck_v5_pair()

    assert report["precheck_passed"] is True
    assert report["schema"].endswith("/5.0")
    assert report["node_a_boot_ids"] == {"a_only": 100, "dual_a_to_b": 200}


def test_v4_raw_audit_requires_one_passed_pre_notify_gate_per_active_node() -> None:
    events = [
        {"event": "pre_notify_status_gate", "node": "A", "passed": True},
        {"event": "pre_notify_status_gate", "node": "B", "passed": True},
    ]

    assert precheck.audit_pre_notify_status_gates(events, ("A", "B")) == []
    missing = precheck.audit_pre_notify_status_gates(events[:1], ("A", "B"))
    assert any("Node B" in error and "exactly once" in error for error in missing)
    rejected = precheck.audit_pre_notify_status_gates(
        [events[0], {**events[1], "passed": False}], ("A", "B")
    )
    assert any("Node B" in error and "exactly once" in error for error in rejected)


def test_precheck_source_lock_ignores_untracked_scratch_but_requires_tracked_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = tmp_path / "plan.md"
    runner = tmp_path / "runner.py"
    plan.write_text("locked plan\n", encoding="utf-8")
    runner.write_text("locked runner\n", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def clean_git(_repo: Path, *arguments: str) -> str:
        commands.append(arguments)
        if arguments[:2] == ("status", "--porcelain"):
            assert "--untracked-files=no" in arguments
            return ""
        if arguments[0] == "ls-files":
            return arguments[-1]
        raise AssertionError(f"unexpected git query: {arguments}")

    monkeypatch.setattr(precheck, "_run_git", clean_git)
    precheck.validate_committed_precheck_inputs(tmp_path, (plan, runner))

    assert sum(command[0] == "ls-files" for command in commands) == 2


def test_precheck_source_lock_rejects_tracked_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = tmp_path / "plan.md"
    runner = tmp_path / "runner.py"
    plan.write_text("locked plan\n", encoding="utf-8")
    runner.write_text("locked runner\n", encoding="utf-8")

    def dirty_git(_repo: Path, *arguments: str) -> str:
        if arguments[:2] == ("status", "--porcelain"):
            return " M experiments/m1_ble_link_precheck.py"
        if arguments[0] == "ls-files":
            return arguments[-1]
        raise AssertionError(f"unexpected git query: {arguments}")

    monkeypatch.setattr(precheck, "_run_git", dirty_git)
    with pytest.raises(RuntimeError, match="clean tracked code tree"):
        precheck.validate_committed_precheck_inputs(tmp_path, (plan, runner))


def test_precheck_runtime_cdc_accepts_locked_application_interface() -> None:
    precheck.validate_runtime_cdc_port(
        precheck.NodeId.A,
        {
            "serial_number": matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[
                precheck.NodeId.A
            ],
            "vid": 0x2FE3,
            "pid": 0x0004,
        },
    )


def test_precheck_runtime_cdc_rejects_matching_uf2_bootloader_interface() -> None:
    with pytest.raises(RuntimeError, match="expected application CDC 2FE3:0004"):
        precheck.validate_runtime_cdc_port(
            precheck.NodeId.A,
            {
                "serial_number": matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[
                    precheck.NodeId.A
                ],
                "vid": 0x2886,
                "pid": 0x0045,
            },
        )


def test_precheck_runtime_cdc_rejects_wrong_serial_even_when_interface_matches() -> None:
    with pytest.raises(RuntimeError, match="USB serial differs"):
        precheck.validate_runtime_cdc_port(
            precheck.NodeId.A,
            {"serial_number": "NOT-NODE-A", "vid": 0x2FE3, "pid": 0x0004},
        )


def test_single_node_precheck_records_capture_window_and_connect_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory(
        prefix="m1-precheck-single-",
        dir=Path(__file__).resolve().parents[2],
    ) as temp_dir:
        temp_path = Path(temp_dir)

        class FakeCdcCapture:
            def __init__(self) -> None:
                self.port_info: dict[str, object] = {"device": "COM5", "serial_number": "A"}
                self.error: str | None = None
                self.done = threading.Event()
                self.listeners: set[Callable[..., object]] = set()

            def add_event_listener(self, listener: Callable[..., object]) -> None:
                self.listeners.add(listener)

            def remove_event_listener(self, listener: Callable[..., object]) -> None:
                self.listeners.discard(listener)

            def cut(self) -> int:
                return 100

            def copy_segment(
                self, start: int, end: int, output_dir: Path
            ) -> dict[str, object]:
                return {"start": start, "end": end, "output_dir": str(output_dir)}

        captures = {
            matrix_runner.NodeId.A: FakeCdcCapture(),
            matrix_runner.NodeId.B: FakeCdcCapture(),
        }
        observed_capture_timeouts: list[object] = []
        observed_connection_gates: list[object] = []

        async def fake_capture_single_node(**kwargs: object) -> object:
            observed_capture_timeouts.append(kwargs["connection_timeout_s"])
            target = cast(NodeTarget, kwargs["target"])
            callback = cast(
                Callable[[matrix_runner.NodeId, int, int, int, int, int], None],
                kwargs["capture_window_callback"],
            )
            callback(target.node_id, 10, 15, 20, 25, 1)
            return SimpleNamespace(
                raw_path=temp_path / "node-a.kimu",
                events_path=temp_path / "node-a.events.ndjson",
                packet_count=0,
                sample_count=0,
                qc_pass=False,
            )

        async def no_physical_disconnect(
            _clients: list[object], connection_gate: object
        ) -> dict[str, object]:
            observed_connection_gates.append(connection_gate)
            return {
                "host_disconnects": [],
                "peripheral_disconnects": {},
                "disconnect_completed_monotonic_ns": 1,
                "errors": [],
                "cancelled": False,
            }

        monkeypatch.setattr(
            matrix_runner, "_capture_single_node", fake_capture_single_node
        )
        monkeypatch.setattr(
            matrix_runner, "_disconnect_matrix_clients", no_physical_disconnect
        )
        plan_path = temp_path / "plan.md"
        plan_path.write_text("locked test plan\n", encoding="utf-8")

        result = asyncio.run(
            matrix_runner._run_condition(
                run_dir=temp_path / "run",
                condition="a_only",
                run_index=1,
                seconds=15.0,
                node_a_address="A-address",
                node_b_address="B-address",
                expected_node_a_device_id=1,
                expected_node_b_device_id=2,
                request_mode="OFF",
                set_request_mode_before_run=False,
                cdc_captures=cast(
                    dict[matrix_runner.NodeId, matrix_runner._MatrixCdcCapture],
                    captures,
                ),
                plan_path=plan_path,
                plan_sha256="0" * 64,
                completion_driven_tx=True,
                experiment_profile="link_count_precheck",
                connection_parameter_request=False,
                connection_timeout_s=30.0,
                cdc_start_offsets={
                    matrix_runner.NodeId.A: 0,
                    matrix_runner.NodeId.B: 0,
                },
            )
        )

        events = [
            json.loads(line)
            for line in (temp_path / "run" / "experiment_control.ndjson")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        capture_windows = [
            event for event in events if event.get("event") == "matrix_capture_window"
        ]
        assert result["error"] is None
        assert len(capture_windows) == 1
        assert capture_windows[0]["node"] == "A"
        run_config = json.loads(
            (temp_path / "run" / "run_config.json").read_text(encoding="utf-8")
        )
        assert run_config["windows_connect_gatt_setup_timeout_seconds"] == 30.0
        assert observed_capture_timeouts == [30.0]
        assert (
            cast(matrix_runner._MatrixConnectionGate, observed_connection_gates[0])
            .connection_timeout_s
            == 30.0
        )


def test_precheck_live_config_records_expected_application_cdc_interface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("locked test plan\n", encoding="utf-8")
    preflash_path = tmp_path / "preflash.json"
    preflash_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(precheck, "PRECHECK_SOURCE_PREFLASH", preflash_path)
    monkeypatch.setattr(matrix_runner, "_git_head", lambda _repo: "abc123")
    monkeypatch.setattr(precheck, "validate_committed_precheck_inputs", lambda *_args: None)

    images: dict[NodeId, Path] = {}
    configurations: dict[NodeId, Path] = {}
    port_info: dict[NodeId, dict[str, object]] = {}
    for node, name in ((NodeId.A, "a"), (NodeId.B, "b")):
        image = tmp_path / f"node-{name}.uf2"
        image.write_bytes(f"image-{name}".encode("ascii"))
        config = tmp_path / f"node-{name}.config"
        config.write_bytes(b"matched config")
        images[node] = image
        configurations[node] = config
        port_info[node] = {
            "device": "COM5" if node is NodeId.A else "COM8",
            "serial_number": matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node],
            "vid": 0x2FE3,
            "pid": 0x0004,
        }

    config = precheck._live_input_config(
        tmp_path / "output",
        plan_path=plan_path,
        plan_sha256="A" * 64,
        preflash={"plan_sha256": "B" * 64},
        images=images,
        configurations=configurations,
        port_info=port_info,
        adapter_identity={"instance_id": "test"},
    )

    assert config["runtime_cdc_interface_expected"] == {
        "vid": 0x2FE3,
        "pid": 0x0004,
        "usage": "application CDC; UF2 bootloader interface is forbidden",
    }


def test_precheck_independent_audit_accepts_runner_result_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "precheck"
    root.mkdir()
    (root / "PREDECLARED_PRECHECK_PLAN.md").write_bytes(
        precheck.PRECHECK_PLAN_PATH.read_bytes()
    )
    ports = {
        node.name: {
            "device": "COM5" if node is NodeId.A else "COM8",
            "serial_number": matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node],
            "vid": 0x2FE3,
            "pid": 0x0004,
        }
        for node in (NodeId.A, NodeId.B)
    }
    config = {
        "schema": "kineimu.m1.ble-link-count-precheck/2.0",
        "predeclared_plan_sha256": precheck.PRECHECK_PLAN_SHA256,
        "runtime_cdc_interface_expected": {
            "vid": 0x2FE3,
            "pid": 0x0004,
            "usage": "application CDC; UF2 bootloader interface is forbidden",
        },
        "firmware_source_commit": precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT,
        "cdc_ports_resolved_by_usb_serial": ports,
        "firmware_images": {
            node.name: {"sha256": precheck.PRECHECK_IMAGE_SHA256[node]}
            for node in (NodeId.A, NodeId.B)
        },
        "build_configs": {
            node.name: {"sha256": precheck.PRECHECK_CONFIG_SHA256}
            for node in (NodeId.A, NodeId.B)
        },
    }
    off_control = {
        node.name: {"requested": "OFF", "applied": True, "rc": 0}
        for node in (NodeId.A, NodeId.B)
    }
    result = {
        "schema": "kineimu.m1.ble-link-count-precheck-result/1.0",
        "run_order": list(precheck.precheck_order()),
        "schedule_attempted_count": 4,
        "all_scheduled_runs_attempted": True,
        "initial_off_control": off_control,
        "final_control_cleanup": off_control,
    }
    (root / "matrix_config.json").write_text(json.dumps(config), encoding="utf-8")
    (root / "matrix_result.json").write_text(json.dumps(result), encoding="utf-8")

    def valid_run_audit(
        _root: Path,
        _run_index: int,
        condition: str,
        *,
        expected_source_commit: str,
    ) -> dict[str, object]:
        del expected_source_commit
        return {
            "valid": True,
            "errors": [],
            "condition": condition,
            "expected_active_links": len(precheck.active_nodes_for_condition(condition)),
            "observed_connection_order": list(precheck.active_nodes_for_condition(condition)),
        }

    monkeypatch.setattr(precheck, "_audit_run", valid_run_audit)
    precheck.write_sha256_manifest(root)

    report = precheck.audit_precheck(root)

    assert report["precheck_passed"] is True


@pytest.mark.parametrize(
    ("acquisition_state", "samples_acquired", "expected_start_valid"),
    [("armed", 0, True), ("streaming", 1068, False)],
)
def test_precheck_run_audit_requires_a_fresh_armed_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    acquisition_state: str,
    samples_acquired: int,
    expected_start_valid: bool,
) -> None:
    run_dir = tmp_path / "run-01-a_only"
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    packet = encode_sample_packet(
        SamplePacket(
            node_id=NodeId.A,
            packet_sequence=1,
            clock_epoch=0,
            flags=0,
            samples=(
                Sample(
                    sequence=1,
                    device_time_us=10_000,
                    flags=SampleFlags.NONE,
                    accel_raw=(100, -200, 16_000),
                    gyro_raw=(10, -20, 30),
                ),
            ),
        )
    )
    (raw_dir / "node-a.kimu").write_bytes(
        encode_capture_record(packet, host_monotonic_ns=10_000_000)
    )
    raw_events = [
        {
            "event": "config",
            "source": "read",
            "node_id": 1,
            "hardware_device_id": precheck.PRECHECK_HARDWARE_DEVICE_IDS[NodeId.A],
            "firmware_git_commit": precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT,
        },
        {
            "event": "status",
            "source": "read",
            "connection_id": "a-1",
            "host_monotonic_ns": 10,
            "boot_id": 1234,
            "acquisition_state": acquisition_state,
            "samples_acquired": samples_acquired,
            "packets_generated": samples_acquired // 4,
            "last_sample_sequence": 0xFFFFFFFF if samples_acquired == 0 else samples_acquired - 1,
            "last_packet_sequence": (
                0xFFFFFFFF if samples_acquired == 0 else samples_acquired // 4 - 1
            ),
            "sensor_fifo_overruns": 0,
            "firmware_queue_overruns": 0,
            "samples_dropped_before_packetization": 0,
            "transport_backpressure_events": 0,
            "transport_queue_high_water_packets": 0,
            "acquisition_buffer_high_water_samples": 0,
        },
        {
            "event": "telemetry_notify_enabled",
            "connection_id": "a-1",
            "host_monotonic_ns": 20,
        },
        {"event": "mtu", "node_id": 1, "mtu": 127, "accepted": True},
        {"event": "notify", "node_id": 1, "crc_ok": True, "decode_ok": True},
    ]
    (raw_dir / "node-a.events.ndjson").write_text(
        "".join(json.dumps(event) + "\n" for event in raw_events),
        encoding="utf-8",
    )
    (run_dir / "node-a.cdc.bin").write_bytes(b"\n")
    run_config = {
        "schema": "kineimu.m1.ble-link-count-precheck-run/2.0",
        "experiment_profile": "link_count_precheck",
        "predeclared_plan_sha256": precheck.PRECHECK_PLAN_SHA256,
        "condition": "a_only",
        "request_mode": "OFF",
        "connection_order": ["A"],
        "nodes": ["A"],
        "capture_seconds": 15.0,
        "change_policy": {
            "connection_parameter_request": False,
            "tx_queue_capacity_change": False,
            "host_disk_write_decoupling": False,
            "completion_driven_tx": True,
        },
        "cdc_usb_serials": {
            "A": matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[NodeId.A]
        },
    }
    run_result = {
        "schema": "kineimu.m1.ble-link-count-precheck-run-result/2.0",
        "condition": "a_only",
        "request_mode": "OFF",
        "recorder_result": None,
    }
    (run_dir / "run_config.json").write_text(json.dumps(run_config), encoding="utf-8")
    (run_dir / "run_result.json").write_text(json.dumps(run_result), encoding="utf-8")
    (run_dir / "experiment_control.ndjson").write_text(
        json.dumps(
            {
                "event": "telemetry_notify_enabled",
                "node": "A",
                "host_monotonic_ns": 20,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    timing_arguments: dict[str, object] = {}

    def timing_audit(*_args: object, **kwargs: object) -> dict[str, object]:
        timing_arguments.update(kwargs)
        return {
            "valid": True,
            "errors": [],
            "nodes": {"A": {"mtu": None}},
        }

    monkeypatch.setattr(precheck, "audit_run_timing_events", timing_audit)

    audit = precheck._audit_run(
        tmp_path,
        1,
        "a_only",
        expected_source_commit=precheck.PRECHECK_FIRMWARE_SOURCE_COMMIT,
    )

    assert audit["nodes"]["A"]["raw_capture"]["valid_packets"] == 1
    assert audit["nodes"]["A"]["capture_quality"]["notify_events"] == 1
    assert any(
        "Node A BLE connection did not prove MTU 127" in error
        for error in audit["errors"]
    )
    assert any(
        "Node A recorder packet count differs from raw decode" in error
        for error in audit["errors"]
    )
    assert audit["nodes"]["A"]["acquisition_start"]["valid"] is expected_start_valid, audit[
        "nodes"
    ]["A"]["acquisition_start"]["errors"]
    assert timing_arguments["require_full_callback_span"] is False


def test_precheck_manifest_is_complete_and_refuses_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "precheck"
    run = root / "run-01-a_only"
    run.mkdir(parents=True)
    (root / "matrix_config.json").write_text('{"profile":"precheck"}\n', encoding="utf-8")
    (run / "node-a.kimu").write_bytes(b"immutable raw fixture")

    manifest = precheck.write_sha256_manifest(root)
    first_hash = precheck.sha256(manifest)
    report = verify_manifest(root)
    assert report["valid"] is True
    assert report["entries"] == 2
    assert report["sha256"] == first_hash

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        precheck.write_sha256_manifest(root)
    assert precheck.sha256(manifest) == first_hash


def test_manifest_verification_detects_changed_raw_bytes(tmp_path: Path) -> None:
    root = tmp_path / "precheck"
    root.mkdir()
    raw = root / "node-a.kimu"
    raw.write_bytes(b"first acquisition bytes")
    precheck.write_sha256_manifest(root)

    raw.write_bytes(b"changed bytes")
    report = verify_manifest(root)
    assert report["valid"] is False
    assert report["mismatched"] == ["node-a.kimu"]
