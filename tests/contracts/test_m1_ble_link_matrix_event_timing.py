"""Contracts for firmware-connected-event parameter observation windows."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

import experiments.m1_ble_link_matrix as matrix_runner
from experiments.m1_transport_experiment import EventLog
from kineimu_shoulder.io.m1_ble import NodeId
from kineimu_shoulder.io.m1_control import (
    AcquisitionState,
    Status,
    StatusFlags,
    encode_status,
)


class _Events:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []

    def write(self, event: str, **details: object) -> None:
        self.rows.append({"event": event, **details})


def _connected_line(
    node: str, interval_us: int | None = None, firmware_uptime_ms: int = 0
) -> str:
    line = (
        f"Node {node}: BLE link event=connected "
        f"firmware_uptime_ms={firmware_uptime_ms}"
    )
    if interval_us is not None:
        line += (
            f" info_rc=0 interval_us={interval_us} latency=0 "
            "supervision_timeout_us=420000"
        )
    return line


def _updated_line(node: str, interval_us: int, firmware_uptime_ms: int = 0) -> str:
    return (
        f"Node {node}: BLE link event=param_updated interval_us={interval_us} "
        f"latency=0 supervision_timeout_us=420000 firmware_uptime_ms={firmware_uptime_ms}"
    )


def test_settle_window_uses_cdc_connected_time_and_keeps_all_updates() -> None:
    async def scenario() -> tuple[matrix_runner._MatrixConnectionGate, int, int]:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A, NodeId.B), first_node=None, events=events
        )
        node_a_attempt = gate.note_connect_attempt(NodeId.A)
        node_b_attempt = gate.note_connect_attempt(NodeId.B)
        connected_ns = time.monotonic_ns()
        gate.note_firmware_event(
            NodeId.A, "connected", connected_ns, _connected_line("A", firmware_uptime_ms=1_000)
        )
        gate.note_connected(NodeId.A, node_a_attempt)
        await asyncio.sleep(0.025)
        node_b_connected_ns = time.monotonic_ns()
        gate.note_firmware_event(
            NodeId.B,
            "connected",
            node_b_connected_ns,
            _connected_line("B", firmware_uptime_ms=1_025),
        )
        gate.note_connected(NodeId.B, node_b_attempt)
        await asyncio.sleep(0.055)
        gate.note_firmware_event(
            NodeId.A,
            "param_updated",
            time.monotonic_ns(),
            _updated_line("A", 30_000, firmware_uptime_ms=1_080),
        )
        gate.note_firmware_event(
            NodeId.A,
            "param_updated",
            time.monotonic_ns(),
            _updated_line("A", 15_000, firmware_uptime_ms=1_081),
        )
        wait_started_ns = time.monotonic_ns()
        await gate.wait_for_settle(0.12)
        finished_ns = time.monotonic_ns()
        return gate, wait_started_ns, finished_ns

    gate, wait_started_ns, finished_ns = asyncio.run(scenario())

    assert finished_ns - gate.peripheral_connected_at[NodeId.B] >= 120_000_000
    assert wait_started_ns - gate.peripheral_connected_at[NodeId.B] < 120_000_000
    assert [
        update["interval_us"] for update in gate.parameter_updates[NodeId.A]
    ] == [30_000, 15_000]
    node_a_window = gate.parameter_window_result(NodeId.A, 0.12)
    assert node_a_window["target_observed"] is True
    window_updates = node_a_window["updates"]
    assert isinstance(window_updates, list)
    assert [
        update["interval_us"] for update in window_updates
    ] == [30_000, 15_000]


def test_settle_window_rechecks_deadline_after_an_early_timer_wakeup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> list[dict[str, object]]:
        now_ns = 1_000_000_000
        first_wakeup = True

        async def early_sleep(delay_s: float) -> None:
            nonlocal now_ns, first_wakeup
            advance_ns = round(delay_s * 1_000_000_000)
            if first_wakeup:
                advance_ns -= 10_000_000
                first_wakeup = False
            now_ns += advance_ns

        monkeypatch.setattr(matrix_runner.time, "monotonic_ns", lambda: now_ns)
        monkeypatch.setattr(matrix_runner.asyncio, "sleep", early_sleep)
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_firmware_event(
            NodeId.A, "connected", now_ns, _connected_line("A", firmware_uptime_ms=1_000)
        )
        gate.note_connected(NodeId.A, attempt)
        await gate.wait_for_settle(0.12)
        return events.rows

    rows = asyncio.run(scenario())
    complete = next(row for row in rows if row["event"] == "connection_parameter_settle_complete")
    # Literal deadline: 120 ms after the 1 s CDC anchor, despite a 110 ms wakeup.
    assert complete["monotonic_ns"] == 1_120_000_000
    assert complete["observed_duration_s_by_node"] == {"A": 0.12}


def test_reconnect_uses_new_connected_event_anchor_for_parameter_window() -> None:
    async def scenario() -> tuple[matrix_runner._MatrixConnectionGate, int]:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        initial_ns = time.monotonic_ns()
        reconnect_ns = initial_ns + 1_000_000
        first_attempt = gate.note_connect_attempt(NodeId.A)

        gate.note_firmware_event(
            NodeId.A, "connected", initial_ns, _connected_line("A", firmware_uptime_ms=1_000)
        )
        gate.note_connected(NodeId.A, first_attempt)
        gate.note_firmware_event(
            NodeId.A,
            "param_updated",
            initial_ns + 500_000,
            _updated_line("A", 30_000, firmware_uptime_ms=1_500),
        )
        reconnect_attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_firmware_event(
            NodeId.A, "connected", reconnect_ns, _connected_line("A", firmware_uptime_ms=2_000)
        )
        gate.note_connected(NodeId.A, reconnect_attempt)
        gate.note_firmware_event(
            NodeId.A,
            "param_updated",
            reconnect_ns + 500_000,
            _updated_line("A", 15_000, firmware_uptime_ms=2_005),
        )
        return gate, initial_ns

    gate, initial_ns = asyncio.run(scenario())
    assert gate.peripheral_connected_at[NodeId.A] == initial_ns + 1_000_000
    result = gate.parameter_window_result(NodeId.A, 0.01)
    assert result["target_observed"] is True
    updates = result["updates"]
    assert isinstance(updates, list)
    assert [update["interval_us"] for update in updates] == [15_000]


def test_connected_event_tuple_counts_as_target_observed() -> None:
    async def scenario() -> dict[str, object]:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        connected_ns = time.monotonic_ns()
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            connected_ns,
            _connected_line("A", interval_us=15_000, firmware_uptime_ms=1_000),
        )
        gate.note_connected(NodeId.A, attempt)
        return gate.parameter_window_result(NodeId.A, 10.0)

    result = asyncio.run(scenario())
    assert result["target_observed"] is True
    updates = result["updates"]
    assert isinstance(updates, list)
    assert len(updates) == 1
    assert updates[0]["interval_us"] == 15_000


def test_parameter_window_uses_firmware_event_time_not_cdc_delivery_time() -> None:
    async def scenario() -> dict[str, object]:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            1_000_000_000,
            _connected_line("A", firmware_uptime_ms=1_000),
        )
        gate.note_firmware_event(
            NodeId.A,
            "param_updated",
            2_000_000_000,
            _updated_line("A", 15_000, firmware_uptime_ms=11_001),
        )
        return gate.parameter_window_result(NodeId.A, 10.0)

    result = asyncio.run(scenario())
    assert result["target_observed"] is False
    assert result["connected_firmware_uptime_ms"] == 1_000
    updates = result["updates"]
    assert isinstance(updates, list)
    assert updates == []


def test_parameter_window_uses_modular_firmware_uptime_at_inclusive_deadline() -> None:
    async def scenario() -> dict[str, object]:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            1_000_000_000,
            _connected_line("A", firmware_uptime_ms=0xFFFFFFF0),
        )
        gate.note_firmware_event(
            NodeId.A,
            "param_updated",
            1_001_000_000,
            _updated_line("A", 15_000, firmware_uptime_ms=0x00000004),
        )
        gate.note_firmware_event(
            NodeId.A,
            "param_updated",
            1_002_000_000,
            _updated_line("A", 30_000, firmware_uptime_ms=0x00000005),
        )
        return gate.parameter_window_result(NodeId.A, 0.02)

    result = asyncio.run(scenario())
    assert result["target_observed"] is True
    assert result["deadline_firmware_uptime_ms"] == 0x00000004
    updates = result["updates"]
    assert isinstance(updates, list)
    assert len(updates) == 1
    assert updates[0]["firmware_uptime_ms"] == 0x00000004


def test_disconnect_before_settle_deadline_cannot_complete_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> dict[str, object]:
        monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_CONNECTION_TIMEOUT_S", 0.02)
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        connected_ns = time.monotonic_ns()
        gate.note_connected(NodeId.A, attempt)
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            connected_ns,
            _connected_line("A", 15_000, firmware_uptime_ms=1_000),
        )
        settle = asyncio.create_task(gate.wait_for_settle(0.06))
        await asyncio.sleep(0.01)
        gate.note_firmware_event(
            NodeId.A,
            "disconnected",
            connected_ns + 10_000_000,
            "Node A: BLE link event=disconnected firmware_uptime_ms=1010 reason=0x13",
        )
        try:
            await settle
        except RuntimeError:
            return gate.parameter_window_result(NodeId.A, 0.06)
        raise AssertionError("settle passed after the peripheral link disconnected")

    result = asyncio.run(scenario())
    assert result["peripheral_connected_for_full_window"] is False
    assert result["peripheral_disconnected_host_monotonic_ns"] is not None


def test_wait_for_peripheral_disconnect_uses_current_firmware_link_event() -> None:
    async def scenario() -> tuple[dict[str, object], matrix_runner._MatrixConnectionGate]:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        connected_ns = time.monotonic_ns()
        gate.note_connected(NodeId.A, attempt)
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            connected_ns,
            _connected_line("A", firmware_uptime_ms=1_000),
        )
        wait_task = asyncio.create_task(
            gate.wait_for_peripheral_disconnect(NodeId.A, timeout_s=0.2)
        )
        await asyncio.sleep(0.01)
        assert not wait_task.done()
        disconnected_ns = time.monotonic_ns()
        gate.note_firmware_event(
            NodeId.A,
            "disconnected",
            disconnected_ns,
            "Node A: BLE link event=disconnected firmware_uptime_ms=1100 reason=0x13",
        )
        return await wait_task, gate

    result, gate = asyncio.run(scenario())

    assert result["observed"] is True
    assert result["connect_attempt"] == 1
    assert result["firmware_uptime_ms"] == 1100
    assert any(row["event"] == "peripheral_disconnect_wait_complete" for row in gate.events.rows)


def test_wait_for_peripheral_disconnect_times_out_without_firmware_confirmation() -> None:
    async def scenario() -> matrix_runner._MatrixConnectionGate:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_connected(NodeId.A, attempt)
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            time.monotonic_ns(),
            _connected_line("A", firmware_uptime_ms=1_000),
        )
        with pytest.raises(TimeoutError, match="did not confirm"):
            await gate.wait_for_peripheral_disconnect(NodeId.A, timeout_s=0.01)
        return gate

    gate = asyncio.run(scenario())

    assert any(row["event"] == "peripheral_disconnect_wait_timeout" for row in gate.events.rows)


def test_wait_for_peripheral_disconnect_is_not_required_without_connected_event() -> None:
    async def scenario() -> dict[str, object]:
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=_Events()
        )
        return await gate.wait_for_peripheral_disconnect(NodeId.A, timeout_s=0.01)

    result = asyncio.run(scenario())

    assert result["required"] is False
    assert result["observed"] is False
    assert result["completed"] is True


def test_matrix_run_cleanup_waits_for_firmware_disconnect_before_rest_anchor() -> None:
    async def scenario() -> tuple[dict[str, object], _Events]:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_connected(NodeId.A, attempt)
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            time.monotonic_ns(),
            _connected_line("A", firmware_uptime_ms=1_000),
        )

        class UnderlyingClient:
            is_connected = True

            async def disconnect(self) -> None:
                await asyncio.sleep(0.02)
                self.is_connected = False
                gate.note_firmware_event(
                    NodeId.A,
                    "disconnected",
                    time.monotonic_ns(),
                    "Node A: BLE link event=disconnected firmware_uptime_ms=1100 reason=0x13",
                )

        client = matrix_runner.MatrixBleClient(
            node=NodeId.A,
            address="A-address",
            disconnected_callback=lambda _client: None,
            events=events,
            connection_gate=gate,
        )
        client._client = UnderlyingClient()  # type: ignore[assignment]
        cleanup = await matrix_runner._disconnect_matrix_clients([client], gate)
        return cleanup, events

    cleanup, events = asyncio.run(scenario())

    event_names = [row["event"] for row in events.rows]
    assert event_names.index("peripheral_disconnected_event") < event_names.index(
        "matrix_run_disconnect_complete"
    )
    assert cleanup["disconnect_completed_monotonic_ns"] >= max(
        item["host_monotonic_ns"]
        for item in cleanup["peripheral_disconnects"].values()
        if item["observed"]
    )
    assert cleanup["errors"] == []


def test_matrix_run_cleanup_waits_for_delayed_firmware_connected_and_disconnected_events() -> None:
    async def scenario() -> tuple[dict[str, object], _Events]:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_connected(NodeId.A, attempt)

        class UnderlyingClient:
            is_connected = True

            async def disconnect(self) -> None:
                await asyncio.sleep(0.01)
                gate.note_firmware_event(
                    NodeId.A,
                    "connected",
                    time.monotonic_ns(),
                    _connected_line("A", firmware_uptime_ms=1_000),
                )
                await asyncio.sleep(0.01)
                self.is_connected = False
                gate.note_firmware_event(
                    NodeId.A,
                    "disconnected",
                    time.monotonic_ns(),
                    "Node A: BLE link event=disconnected firmware_uptime_ms=1100 reason=0x13",
                )

        client = matrix_runner.MatrixBleClient(
            node=NodeId.A,
            address="A-address",
            disconnected_callback=lambda _client: None,
            events=events,
            connection_gate=gate,
        )
        client._client = UnderlyingClient()  # type: ignore[assignment]
        cleanup = await matrix_runner._disconnect_matrix_clients([client], gate)
        return cleanup, events

    cleanup, events = asyncio.run(scenario())

    event_names = [row["event"] for row in events.rows]
    assert "peripheral_connected_event" in event_names
    assert "peripheral_disconnected_event" in event_names
    assert event_names.index("peripheral_disconnected_event") < event_names.index(
        "matrix_run_disconnect_complete"
    )
    assert cleanup["peripheral_disconnects"]["A"]["observed"] is True  # type: ignore[index]


def test_matrix_run_cleanup_calls_disconnect_for_client_not_marked_connected() -> None:
    async def scenario() -> tuple[dict[str, object], int]:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )

        class UnderlyingClient:
            is_connected = False

            def __init__(self) -> None:
                self.disconnect_calls = 0

            async def disconnect(self) -> None:
                self.disconnect_calls += 1

        underlying = UnderlyingClient()
        client = matrix_runner.MatrixBleClient(
            node=NodeId.A,
            address="A-address",
            disconnected_callback=lambda _client: None,
            events=events,
            connection_gate=gate,
        )
        client._client = underlying  # type: ignore[assignment]
        cleanup = await matrix_runner._disconnect_matrix_clients([client], gate)
        return cleanup, underlying.disconnect_calls

    cleanup, disconnect_calls = asyncio.run(scenario())

    assert disconnect_calls == 1
    host_disconnects = cleanup["host_disconnects"]
    assert isinstance(host_disconnects, list)
    assert host_disconnects[0]["disconnect_called"] is True
    assert host_disconnects[0]["was_connected"] is False
    assert cleanup["errors"] == []


def test_reconnect_settle_waits_for_connected_event_from_new_attempt() -> None:
    async def scenario() -> tuple[int, int]:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        first_attempt = gate.note_connect_attempt(NodeId.A)
        first_connected_ns = time.monotonic_ns()
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            first_connected_ns,
            _connected_line("A", firmware_uptime_ms=1_000),
        )
        gate.note_connected(NodeId.A, first_attempt)
        await gate.wait_for_settle(0.05)

        second_attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_connected(NodeId.A, second_attempt)
        wait_task = asyncio.create_task(gate.wait_for_settle(0.05))
        await asyncio.sleep(0.01)
        assert not wait_task.done()
        second_connected_ns = time.monotonic_ns()
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            second_connected_ns,
            _connected_line("A", firmware_uptime_ms=2_000),
        )
        await wait_task
        return second_connected_ns, time.monotonic_ns()

    connected_ns, finished_ns = asyncio.run(scenario())
    assert finished_ns - connected_ns >= 20_000_000


def test_firmware_event_with_wrong_cdc_node_label_fails_closed() -> None:
    async def scenario() -> matrix_runner._MatrixConnectionGate:
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        gate.note_firmware_event(
            NodeId.A, "connected", time.monotonic_ns(), _connected_line("B")
        )
        return gate

    gate = asyncio.run(scenario())

    assert gate.failed_event.is_set()
    assert "node" in str(gate.failure).lower()


def test_disconnect_timeout_is_retried_and_both_phases_are_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> tuple[int, list[dict[str, object]]]:
        monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_DISCONNECT_TIMEOUT_S", 0.01)
        events = EventLog(tmp_path / "disconnect-events.ndjson")
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )

        class UnderlyingClient:
            is_connected = True

            def __init__(self) -> None:
                self.disconnect_attempts = 0

            async def disconnect(self) -> None:
                self.disconnect_attempts += 1
                if self.disconnect_attempts == 1:
                    await asyncio.Event().wait()
                self.is_connected = False

        underlying = UnderlyingClient()
        client = matrix_runner.MatrixBleClient(
            node=NodeId.A,
            address="A-address",
            disconnected_callback=lambda _client: None,
            events=events,
            connection_gate=gate,
        )
        client._client = underlying  # type: ignore[assignment]
        try:
            await client.disconnect()
        finally:
            events.close()
        event_path = tmp_path / "disconnect-events.ndjson"
        rows = [
            json.loads(line)
            for line in event_path.read_text(encoding="utf-8").splitlines()
        ]
        return underlying.disconnect_attempts, rows

    attempts, rows = asyncio.run(scenario())

    assert attempts == 2
    assert [row["event"] for row in rows] == [
        "ble_disconnect_call",
        "ble_disconnect_timeout",
        "ble_disconnect_call",
        "ble_disconnect_complete",
    ]


def _status_bytes(*, streaming: bool = False) -> bytes:
    return encode_status(
        Status(
            node_id=NodeId.A,
            acquisition_state=(
                AcquisitionState.STREAMING if streaming else AcquisitionState.ARMED
            ),
            flags=StatusFlags.SENSOR_READY,
            boot_id=123,
            clock_epoch=0,
            status_sequence=0,
            last_sample_sequence=0xFFFFFFFF if not streaming else 10,
            last_packet_sequence=0xFFFFFFFF if not streaming else 2,
            samples_acquired=0 if not streaming else 11,
            packets_generated=0 if not streaming else 3,
            sensor_fifo_overruns=0,
            firmware_queue_overruns=0,
            transport_backpressure_events=0,
            samples_dropped_before_packetization=0,
            acquisition_buffer_high_water_samples=0,
            transport_queue_high_water_packets=0,
            last_error_code=0,
        )
    )


def test_pre_notify_freshness_gate_blocks_stale_status_before_telemetry_ccc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> tuple[int, list[dict[str, object]]]:
        monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_SETUP_SETTLE_S", 0.0)
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_connected(NodeId.A, attempt)
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            time.monotonic_ns(),
            _connected_line("A", firmware_uptime_ms=1_000),
        )

        class UnderlyingClient:
            is_connected = True

            def __init__(self) -> None:
                self.notify_calls = 0

            async def read_gatt_char(self, _char: str) -> bytes:
                return _status_bytes(streaming=True)

            async def start_notify(self, _char: str, _callback: object) -> None:
                self.notify_calls += 1

        underlying = UnderlyingClient()
        client = matrix_runner.MatrixBleClient(
            node=NodeId.A,
            address="A-address",
            disconnected_callback=lambda _client: None,
            events=events,
            connection_gate=gate,
            require_pristine_start=True,
        )
        client._client = underlying  # type: ignore[assignment]
        await client.read_gatt_char(matrix_runner.STATUS_UUID)
        with pytest.raises(matrix_runner.CdcControlGateError, match="pristine armed"):
            await client.start_notify(matrix_runner.TELEMETRY_UUID, lambda *_args: None)
        return underlying.notify_calls, events.rows

    notify_calls, rows = asyncio.run(scenario())

    assert notify_calls == 0
    failed_gate = next(row for row in rows if row["event"] == "pre_notify_status_gate")
    assert failed_gate["passed"] is False
    assert any("acquisition_state" in error for error in failed_gate["errors"])


def test_pre_notify_freshness_gate_allows_pristine_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> int:
        monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_SETUP_SETTLE_S", 0.0)
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_connected(NodeId.A, attempt)
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            time.monotonic_ns(),
            _connected_line("A", firmware_uptime_ms=1_000),
        )

        class UnderlyingClient:
            is_connected = True

            def __init__(self) -> None:
                self.notify_calls = 0

            async def read_gatt_char(self, _char: str) -> bytes:
                return _status_bytes()

            async def start_notify(self, _char: str, _callback: object) -> None:
                self.notify_calls += 1

        underlying = UnderlyingClient()
        client = matrix_runner.MatrixBleClient(
            node=NodeId.A,
            address="A-address",
            disconnected_callback=lambda _client: None,
            events=events,
            connection_gate=gate,
            require_pristine_start=True,
        )
        client._client = underlying  # type: ignore[assignment]
        await client.read_gatt_char(matrix_runner.STATUS_UUID)
        await client.start_notify(matrix_runner.TELEMETRY_UUID, lambda *_args: None)
        return underlying.notify_calls

    assert asyncio.run(scenario()) == 1


def test_pre_notify_freshness_gate_rejects_a_previously_observed_boot_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> tuple[int, list[dict[str, object]]]:
        monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_SETUP_SETTLE_S", 0.0)
        events = _Events()
        gate = matrix_runner._MatrixConnectionGate(
            required_nodes=(NodeId.A,), first_node=None, events=events
        )
        attempt = gate.note_connect_attempt(NodeId.A)
        gate.note_connected(NodeId.A, attempt)
        gate.note_firmware_event(
            NodeId.A,
            "connected",
            time.monotonic_ns(),
            _connected_line("A", firmware_uptime_ms=1_000),
        )

        class UnderlyingClient:
            is_connected = True

            def __init__(self) -> None:
                self.notify_calls = 0

            async def read_gatt_char(self, _char: str) -> bytes:
                return _status_bytes()

            async def start_notify(self, _char: str, _callback: object) -> None:
                self.notify_calls += 1

        underlying = UnderlyingClient()
        client = matrix_runner.MatrixBleClient(
            node=NodeId.A,
            address="A-address",
            disconnected_callback=lambda _client: None,
            events=events,
            connection_gate=gate,
            require_pristine_start=True,
            forbidden_boot_ids=frozenset({123}),
        )
        client._client = underlying  # type: ignore[assignment]
        await client.read_gatt_char(matrix_runner.STATUS_UUID)
        with pytest.raises(matrix_runner.CdcControlGateError, match="boot ID was already used"):
            await client.start_notify(matrix_runner.TELEMETRY_UUID, lambda *_args: None)
        return underlying.notify_calls, events.rows

    notify_calls, rows = asyncio.run(scenario())

    assert notify_calls == 0
    failed_gate = next(row for row in rows if row["event"] == "pre_notify_status_gate")
    assert failed_gate["passed"] is False
    assert any("boot ID was already used" in error for error in failed_gate["errors"])
