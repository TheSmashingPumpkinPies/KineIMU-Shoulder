"""Contracts for the closed-loop dual-link throughput matrix."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import experiments.m1_ble_link_matrix as matrix_runner
from experiments.m1_ble_link_matrix import (
    ROOT_CAUSE_BLOCK_SCHEDULE,
    _change_policy,
    _validate_firmware_source_commit,
    matrix_order,
    resolve_cdc_port_by_serial,
)
from experiments.m1_ble_link_matrix_audit import summarize_callback_durations


def test_root_cause_matrix_order_matches_locked_four_block_williams_schedule() -> None:
    expected_blocks = (
        ("a_only", "b_only", "dual_b_to_a", "dual_a_to_b"),
        ("b_only", "dual_a_to_b", "a_only", "dual_b_to_a"),
        ("dual_b_to_a", "a_only", "dual_a_to_b", "b_only"),
        ("dual_a_to_b", "dual_b_to_a", "b_only", "a_only"),
    )

    assert matrix_order(4) == tuple(condition for block in expected_blocks for condition in block)


def test_root_cause_schedule_encodes_fixed_off_on_on_off_blocks() -> None:
    expected_blocks = (
        ("OFF", ("a_only", "b_only", "dual_b_to_a", "dual_a_to_b")),
        ("ON", ("b_only", "dual_a_to_b", "a_only", "dual_b_to_a")),
        ("ON", ("dual_b_to_a", "a_only", "dual_a_to_b", "b_only")),
        ("OFF", ("dual_a_to_b", "dual_b_to_a", "b_only", "a_only")),
    )

    assert ROOT_CAUSE_BLOCK_SCHEDULE == expected_blocks
    assert matrix_order(4) == tuple(
        condition for _request_mode, block in expected_blocks for condition in block
    )


def test_root_cause_matrix_rejects_incomplete_block_counts() -> None:
    with pytest.raises(ValueError, match="exactly four blocks"):
        matrix_order(3)


def test_cdc_port_resolution_uses_the_requested_usb_serial() -> None:
    port = SimpleNamespace(
        device="COM7",
        serial_number="NODE-B-SERIAL",
        vid=0x2886,
        pid=0x8045,
        hwid="USB VID:PID=2886:8045 SER=NODE-B-SERIAL",
    )

    assert resolve_cdc_port_by_serial("NODE-B-SERIAL", ports=[port]) == {
        "device": "COM7",
        "serial_number": "NODE-B-SERIAL",
        "vid": 0x2886,
        "pid": 0x8045,
        "hwid": "USB VID:PID=2886:8045 SER=NODE-B-SERIAL",
    }


def test_cdc_port_resolution_rejects_missing_or_ambiguous_serials() -> None:
    port = SimpleNamespace(device="COM7", serial_number="NODE-B-SERIAL")

    with pytest.raises(RuntimeError, match="found 0"):
        resolve_cdc_port_by_serial("UNKNOWN", ports=[port])
    with pytest.raises(RuntimeError, match="found 2"):
        resolve_cdc_port_by_serial("NODE-B-SERIAL", ports=[port, port])


def _mock_firmware_source_validation(
    monkeypatch: pytest.MonkeyPatch,
    *,
    firmware_diff_returncode: int = 0,
    status_output: str = "",
    ancestor_returncode: int = 0,
) -> tuple[str, str]:
    source_commit = "a" * 40
    host_head = "b" * 40

    def fake_run(args: list[str], **_kwargs: object) -> SimpleNamespace:
        if "rev-parse" in args:
            return SimpleNamespace(returncode=0, stdout=f"{source_commit}\n")
        if "merge-base" in args:
            return SimpleNamespace(returncode=ancestor_returncode, stdout="")
        if "diff" in args:
            return SimpleNamespace(returncode=firmware_diff_returncode, stdout="")
        if "status" in args:
            return SimpleNamespace(returncode=0, stdout=status_output)
        raise AssertionError(f"unexpected Git command: {args}")

    monkeypatch.setattr(matrix_runner, "_git_head", lambda _repo_root: host_head)
    monkeypatch.setattr(matrix_runner.subprocess, "run", fake_run)
    return source_commit, host_head


def test_firmware_source_validation_allows_a_clean_docs_only_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_commit, host_head = _mock_firmware_source_validation(monkeypatch)

    assert (
        _validate_firmware_source_commit(
            Path("."), source_commit
        )
        == host_head
    )


def test_firmware_source_validation_rejects_firmware_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    source_commit, _ = _mock_firmware_source_validation(
        monkeypatch, firmware_diff_returncode=1
    )

    with pytest.raises(ValueError, match="firmware build inputs changed"):
        _validate_firmware_source_commit(Path("."), source_commit)


def test_firmware_source_validation_rejects_a_dirty_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_commit, _ = _mock_firmware_source_validation(
        monkeypatch, status_output=" M NOTES.md\n"
    )

    with pytest.raises(ValueError, match="clean working tree"):
        _validate_firmware_source_commit(Path("."), source_commit)


def test_matrix_change_policy_records_completion_profile_explicitly() -> None:
    assert _change_policy(False) == {
        "connection_parameter_request": True,
        "completion_driven_tx": False,
        "host_disk_write_decoupling": False,
        "tx_queue_capacity_change": False,
    }
    assert _change_policy(True) == {
        "connection_parameter_request": True,
        "completion_driven_tx": True,
        "host_disk_write_decoupling": False,
        "tx_queue_capacity_change": False,
    }


def test_formal_link_count_run_profile_has_its_own_schema() -> None:
    assert matrix_runner._run_config_schema("link_count_formal_v7") == (
        "kineimu.m1.ble-link-count-formal-run/1.0",
        "kineimu.m1.ble-link-count-formal-run-result/1.0",
        "m1-link-count-formal-v7",
    )


def test_callback_duration_summary_reports_count_and_tail_quantiles() -> None:
    summary = summarize_callback_durations([100, 20, 300, 40])

    assert summary == {
        "count": 4,
        "min_ns": 20,
        "max_ns": 300,
        "mean_ns": 115,
        "p50_ns": 40,
        "p95_ns": 300,
    }


def test_callback_duration_summary_handles_no_notifications() -> None:
    assert summarize_callback_durations([]) == {
        "count": 0,
        "min_ns": None,
        "max_ns": None,
        "mean_ns": None,
        "p50_ns": None,
        "p95_ns": None,
    }
