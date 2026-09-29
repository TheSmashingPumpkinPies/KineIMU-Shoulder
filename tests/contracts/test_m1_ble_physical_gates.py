from __future__ import annotations

import asyncio
import json
import threading
import time
from types import SimpleNamespace

import pytest

import experiments.m1_ble_physical_gates as physical_gates
from experiments.m1_ble_link_matrix import _MatrixConnectionGate
from experiments.m1_ble_physical_gates import (
    await_cleanup_to_completion,
    await_thread_to_completion,
    evaluate_acquisition_artifacts,
    evaluate_parameter_window,
    parse_acquisition_trace,
    run_gates,
)
from experiments.m1_transport_experiment import EventLog
from kineimu_shoulder.io.m1_packet import NodeId


def test_cancel_waits_for_cdc_worker_before_reporting_cancelled() -> None:
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def worker() -> None:
        started.set()
        release.wait()
        finished.set()

    async def exercise() -> None:
        task = asyncio.create_task(await_thread_to_completion(worker))
        assert await asyncio.to_thread(started.wait, 1.0)
        task.cancel()
        await asyncio.sleep(0)
        assert task.done() is False
        release.set()

        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert finished.is_set()


def test_cleanup_await_finishes_and_reports_cancellation() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()

    async def cleanup() -> None:
        started.set()
        await release.wait()
        finished.set()

    async def exercise() -> tuple[None, bool]:
        task = asyncio.create_task(await_cleanup_to_completion(cleanup()))
        await started.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert task.done() is False
        release.set()
        return await task

    result, cancellation_seen = asyncio.run(exercise())
    assert result is None
    assert cancellation_seen is True
    assert finished.is_set()


def test_disconnect_inside_parameter_window_invalidates_full_window_gate(tmp_path) -> None:
    async def exercise() -> dict[str, object]:
        events = EventLog(tmp_path / "events.ndjson")
        gate = _MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_connected(NodeId.A, attempt)
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            1_000_000_000,
            "Node A: BLE link event=connected firmware_uptime_ms=1000 interval_us=15000 "
            "latency=0 supervision_timeout_us=420000",
        )
        gate.note_firmware_event(
            NodeId.A,
            "disconnected",
            6_000_000_000,
            "Node A: BLE link event=disconnected firmware_uptime_ms=6000 reason=0x13",
        )
        result = gate.parameter_window_result(NodeId.A, 10.0)
        events.close()
        return result

    result = asyncio.run(exercise())

    assert result["peripheral_connected_for_full_window"] is False
    assert result["peripheral_disconnected_host_monotonic_ns"] == 6_000_000_000


def test_capture_window_event_uses_node_enum_for_event_log(tmp_path) -> None:
    event_path = tmp_path / "capture-window.ndjson"
    events = EventLog(event_path)
    try:
        physical_gates._record_capture_window(
            events,
            NodeId.B,
            10_000,
            25_000_000_000,
            20_000,
            25_000_010_000,
            750,
        )
    finally:
        events.close()

    row = json.loads(event_path.read_text(encoding="utf-8"))
    assert row["node"] == "B"
    assert row["duration_ns"] == 24_999_990_000
    assert row["capture_clock_domain"] == "perf_counter_ns"
    assert row["capture_start_perf_counter_ns"] == 10_000
    assert row["capture_deadline_perf_counter_ns"] == 25_000_000_000
    assert row["capture_start_host_monotonic_ns"] == row["host_monotonic_ns"] == 20_000
    assert row["capture_deadline_host_monotonic_ns"] == 25_000_010_000
    assert row["capture_clock_pair_uncertainty_ns"] == 750


def test_shared_disconnect_cleanup_waits_for_firmware_event_before_off(tmp_path) -> None:
    async def exercise() -> tuple[dict[str, object], list[dict[str, object]]]:
        event_path = tmp_path / "disconnect-off-order.ndjson"
        events = EventLog(event_path)
        gate = _MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_connected(NodeId.A, attempt)
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            time.monotonic_ns(),
            "Node A: BLE link event=connected firmware_uptime_ms=1000",
        )

        class FakeCdc:
            node = NodeId.A
            error = None

            def __init__(self) -> None:
                self.done = threading.Event()

            def set_mode(self, mode: str, *, timeout_s: float) -> dict[str, object]:
                events.write("fake_control", mode=mode, timeout_s=timeout_s)
                return {
                    "acknowledged": True,
                    "applied": True,
                    "node_id": 1,
                    "rc": 0,
                    "requested": mode,
                    "selected": mode,
                }

        class FakeClient:
            is_connected = True

            async def disconnect(self) -> None:
                gate.note_firmware_event(
                    NodeId.A,
                    "disconnected",
                    time.monotonic_ns(),
                    "Node A: BLE link event=disconnected firmware_uptime_ms=1100 reason=0x13",
                )
                self.is_connected = False

        try:
            cleanup = await physical_gates._disconnect_and_confirm_off(
                NodeId.A, [FakeClient()], FakeCdc(), gate
            )
        finally:
            events.close()
        rows = [
            json.loads(line)
            for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        return cleanup, rows

    cleanup, rows = asyncio.run(exercise())

    disconnect_index = next(
        index for index, row in enumerate(rows)
        if row["event"] == "peripheral_disconnect_wait_complete"
    )
    off_index = next(
        index for index, row in enumerate(rows)
        if row["event"] == "fake_control" and row["mode"] == "OFF"
    )
    assert disconnect_index < off_index
    assert cleanup["peripheral_disconnect"]["completed"] is True
    assert cleanup["cleanup_off"]["applied"] is True


def test_parameter_window_is_inconclusive_when_full_peripheral_window_is_missing() -> None:
    result = evaluate_parameter_window(
        {
            "anchor": "firmware_cdc_peripheral_connected_event",
            "connected_host_monotonic_ns": 100,
            "connected_firmware_uptime_ms": 1_000,
            "window_duration_s": 10.0,
            "deadline_monotonic_ns": 10_000_000_100,
            "observed_duration_s": 6.609,
            "updates": [],
            "target_tuple": {
                "interval_us": 15_000,
                "latency": 0,
                "supervision_timeout_us": 420_000,
            },
        }
    )

    assert result["disposition"] == "inconclusive"
    assert result["passed"] is False


def test_parameter_window_disconnect_before_deadline_is_inconclusive() -> None:
    result = evaluate_parameter_window(
        {
            "anchor": "firmware_cdc_peripheral_connected_event",
            "connected_host_monotonic_ns": 100,
            "connected_firmware_uptime_ms": 1_000,
            "window_duration_s": 10.0,
            "deadline_monotonic_ns": 10_000_000_100,
            "observed_duration_s": 10.2,
            "peripheral_connected_for_full_window": False,
            "updates": [],
            "target_tuple": {
                "interval_us": 15_000,
                "latency": 0,
                "supervision_timeout_us": 420_000,
            },
        }
    )

    assert result["disposition"] == "inconclusive"
    assert result["window_complete"] is False


def test_run_gates_writes_aborted_result_and_manifest_on_cancellation(
    tmp_path, monkeypatch
) -> None:
    started = threading.Event()
    release = threading.Event()
    output_root = tmp_path / "evidence"

    def fake_gate1(_node, _root, _events):
        started.set()
        release.wait()
        return {"passed": True}

    monkeypatch.setattr(physical_gates, "_gate1_node", fake_gate1)
    monkeypatch.setattr(
        physical_gates,
        "_force_off_fresh_session",
        lambda *_args: {"passed": True},
    )

    async def exercise() -> None:
        task = asyncio.create_task(run_gates(output_root, gate="1"))
        assert await asyncio.to_thread(started.wait, 1.0)
        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())

    result_path = output_root / "physical_gates_result.json"
    manifest_path = output_root / "manifest.json"
    assert result_path.is_file()
    assert manifest_path.is_file()
    report = json.loads(result_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["cancelled"] is True
    assert manifest["result_sha256"]
    assert (output_root / "manifest.sha256").is_file()


def test_parameter_window_requires_target_tuple_within_complete_window() -> None:
    result = evaluate_parameter_window(
        {
            "anchor": "firmware_cdc_peripheral_connected_event",
            "connected_host_monotonic_ns": 100,
            "connected_firmware_uptime_ms": 1_000,
            "window_duration_s": 10.0,
            "deadline_monotonic_ns": 10_000_000_100,
            "observed_duration_s": 10.001,
            "updates": [
                {
                    "host_monotonic_ns": 1_000_000_100,
                    "firmware_uptime_ms": 2_000,
                    "interval_us": 11_250,
                    "latency": 0,
                    "supervision_timeout_us": 420_000,
                },
                {
                    "host_monotonic_ns": 9_922_000_100,
                    "firmware_uptime_ms": 10_922,
                    "interval_us": 15_000,
                    "latency": 0,
                    "supervision_timeout_us": 420_000,
                },
            ],
            "target_tuple": {
                "interval_us": 15_000,
                "latency": 0,
                "supervision_timeout_us": 420_000,
            },
        }
    )

    assert result["disposition"] == "passed"
    assert result["target_observed"] is True
    assert result["updates_in_window"] == 2


def test_acquisition_trace_requires_increasing_values_for_every_counter() -> None:
    snapshots = parse_acquisition_trace(
        """
Node A: acquisition trace callback=12 raw_try=12 raw_ok=12 notify_calls=12 notify_failures=0
Node B: acquisition trace callback=99 raw_try=99 raw_ok=99 notify_calls=99 notify_failures=0
Node A: acquisition trace callback=28 raw_try=28 raw_ok=28 notify_calls=28 notify_failures=0
""",
        node_name="A",
    )

    assert snapshots == [
        {"callback": 12, "raw_try": 12, "raw_ok": 12, "notify_calls": 12},
        {"callback": 28, "raw_try": 28, "raw_ok": 28, "notify_calls": 28},
    ]


def test_acquisition_artifacts_require_packets_clean_qc_and_counter_deltas(tmp_path) -> None:
    raw_path = tmp_path / "node-a.kimu"
    events_path = tmp_path / "node-a.events.ndjson"
    raw_path.write_bytes(b"capture bytes")
    events_path.write_text(
        json.dumps({"event": "notify", "crc_ok": True, "decode_ok": True}) + "\n",
        encoding="utf-8",
    )
    capture = SimpleNamespace(
        raw_path=raw_path,
        events_path=events_path,
        packet_count=1,
        sample_count=3,
        qc=SimpleNamespace(
            decode_errors=0,
            framing_errors=0,
            node_mismatches=0,
        ),
    )

    result = evaluate_acquisition_artifacts(
        capture,
        [
            {"callback": 1, "raw_try": 1, "raw_ok": 1, "notify_calls": 1},
            {"callback": 2, "raw_try": 2, "raw_ok": 2, "notify_calls": 2},
        ],
    )

    assert result["passed"] is True
    assert result["valid_packets"] == 1
    assert result["sample_count"] == 3
    assert result["packet_rate_hz"] == pytest.approx(1 / 15)
    assert result["sample_rate_hz"] == pytest.approx(3 / 15)
    assert result["checks"]["crc_errors"] is True
    assert result["decode_errors_by_source"] == {"raw_qc": 0, "event_sidecar": 0}


def test_acquisition_error_sources_are_reported_without_double_counting(tmp_path) -> None:
    raw_path = tmp_path / "node-a.kimu"
    events_path = tmp_path / "node-a.events.ndjson"
    raw_path.write_bytes(b"capture bytes")
    events_path.write_text(
        json.dumps(
            {"event": "decode_error", "crc_ok": False, "node_mismatch": True}
        )
        + "\n",
        encoding="utf-8",
    )
    capture = SimpleNamespace(
        raw_path=raw_path,
        events_path=events_path,
        packet_count=0,
        sample_count=0,
        qc=SimpleNamespace(decode_errors=1, framing_errors=0, node_mismatches=1),
    )

    result = evaluate_acquisition_artifacts(capture, [])

    assert result["decode_errors_by_source"] == {"raw_qc": 1, "event_sidecar": 1}
    assert result["node_mismatches_by_source"] == {
        "raw_qc": 1,
        "event_sidecar": 1,
    }
    assert result["crc_error_events"] == 1
    assert result["checks"]["decode_errors"] is False
    assert result["checks"]["node_mismatches"] is False


def test_acquisition_artifacts_reject_zero_packet_stream_even_with_no_errors(tmp_path) -> None:
    raw_path = tmp_path / "node-b.kimu"
    events_path = tmp_path / "node-b.events.ndjson"
    raw_path.write_bytes(b"")
    events_path.write_text("", encoding="utf-8")
    capture = SimpleNamespace(
        raw_path=raw_path,
        events_path=events_path,
        packet_count=0,
        qc=SimpleNamespace(
            decode_errors=0,
            framing_errors=0,
            node_mismatches=0,
        ),
    )

    result = evaluate_acquisition_artifacts(capture, [])

    assert result["passed"] is False
    assert "valid_packets" in result["failed_checks"]
    assert "trace_counter_delta" in result["failed_checks"]
