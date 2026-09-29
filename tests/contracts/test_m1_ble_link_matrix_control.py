"""Contracts for the experiment-only USB CDC connection-parameter control path."""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from typing import Any

import pytest

import experiments.m1_ble_link_matrix as matrix_runner
from kineimu_shoulder.io.m1_packet import NodeId

_SESSION_NONCE = "0123456789abcdef"


def _control_client_type() -> type[Any]:
    client_type = getattr(matrix_runner, "ConnParamControlClient", None)
    assert client_type is not None, "matrix runner lacks transaction-aware CDC control"
    return client_type


class _EventSink:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []

    def __call__(self, event: str, **details: object) -> None:
        self.rows.append({"event": event, **details})

    def select(self, event: str) -> list[dict[str, object]]:
        return [row for row in self.rows if row["event"] == event]


def _new_client(
    node_id: int,
    writer: Callable[[bytes], int],
    events: _EventSink | None = None,
    *,
    slow_write_threshold_s: float = 0.02,
) -> tuple[Any, _EventSink]:
    event_sink = events or _EventSink()

    client_ref: dict[str, Any] = {}

    def session_writer(data: bytes, *, timeout_s: float) -> int:
        if data.startswith(b"HELLO "):
            client_ref["client"].handle_line(
                f"READY node_id={client_ref['node_id']} session={_SESSION_NONCE}"
            )
            return len(data)
        return writer(data)

    client = _control_client_type()(
        node_id=node_id,
        write=session_writer,
        event_sink=event_sink,
        session_nonce=_SESSION_NONCE,
        slow_write_threshold_s=slow_write_threshold_s,
    )
    client_ref["client"] = client
    client_ref["node_id"] = node_id
    assert client.begin_session(timeout_s=0.1)["ready"] is True
    return client, event_sink


def _transaction_from(command: bytes) -> tuple[int, str]:
    match = re.fullmatch(
        rb"SET session=[0-9a-f]{16} tx=(\d+) mode=(OFF|ON)\n", command
    )
    assert match is not None, f"unexpected CDC control command: {command!r}"
    return int(match.group(1)), match.group(2).decode("ascii")


def _ack(node_id: int, tx: int, requested: str, selected: str, rc: int) -> str:
    return (
        f"ACK node_id={node_id} session={_SESSION_NONCE} tx={tx} "
        f"requested={requested} selected={selected} rc={rc}"
    )


def test_control_ready_requires_the_expected_node_id() -> None:
    commands: list[bytes] = []

    def writer(data: bytes, *, timeout_s: float) -> int:
        commands.append(data)
        return len(data)

    client = _control_client_type()(
        node_id=1,
        write=writer,
        event_sink=_EventSink(),
        session_nonce=_SESSION_NONCE,
    )
    result: list[dict[str, object]] = []
    thread = threading.Thread(
        target=lambda: result.append(client.begin_session(timeout_s=0.5))
    )
    thread.start()
    deadline = time.monotonic() + 0.5
    while not commands and time.monotonic() < deadline:
        time.sleep(0.001)
    assert commands == [b"HELLO session=0123456789abcdef\n"]

    client.handle_line("READY node_id=2 session=0123456789abcdef")
    thread.join(timeout=0.5)
    assert result[0]["ready"] is False

    client.handle_line("READY node_id=1 session=0123456789abcdef")
    assert client.wait_ready(timeout_s=0.0) is False
    assert client.request("OFF", timeout_s=0.0)["applied"] is False
    assert len(commands) == 1


def test_mode_request_requires_full_write_and_matching_ack() -> None:
    commands: list[bytes] = []
    command_written = threading.Event()

    def writer(data: bytes) -> int:
        commands.append(data)
        command_written.set()
        return len(data)

    client, events = _new_client(1, writer)
    results: list[dict[str, object]] = []
    request_thread = threading.Thread(
        target=lambda: results.append(client.request("ON", timeout_s=0.5))
    )
    request_thread.start()
    assert command_written.wait(timeout=0.5)
    tx, mode = _transaction_from(commands[0])
    assert mode == "ON"

    client.handle_line(_ack(1, tx, "ON", "ON", 0))
    request_thread.join(timeout=0.5)

    assert not request_thread.is_alive()
    assert results[0] == {
        "node_id": 1,
        "session": _SESSION_NONCE,
        "tx": tx,
        "requested": "ON",
        "selected": "ON",
        "rc": 0,
        "acknowledged": True,
        "applied": True,
        "error": None,
    }
    assert events.select("conn_param_request_write")[0]["byte_count"] == len(commands[0])
    assert client.pending_count == 0


@pytest.mark.parametrize(
    ("writer", "error_text"),
    [
        (lambda data: len(data) - 1, "partial"),
        (lambda _data: (_ for _ in ()).throw(OSError("disconnected")), "disconnected"),
    ],
)
def test_write_failure_fails_immediately_and_clears_pending(
    writer: Callable[[bytes], int], error_text: str
) -> None:
    client, events = _new_client(2, writer)

    result = client.request("OFF", timeout_s=0.5)

    assert result["acknowledged"] is False
    assert result["applied"] is False
    assert error_text in str(result["error"])
    assert client.pending_count == 0
    assert events.select("conn_param_request_write_failure")


def test_ack_timeout_poisons_session_and_late_ack_cannot_match_future_tx() -> None:
    commands: list[bytes] = []
    command_written = threading.Event()

    def writer(data: bytes) -> int:
        commands.append(data)
        command_written.set()
        return len(data)

    client, events = _new_client(1, writer)
    timed_out = client.request("ON", timeout_s=0.01)
    old_tx, _ = _transaction_from(commands[0])

    assert timed_out["acknowledged"] is False
    assert "timeout" in str(timed_out["error"])
    assert client.pending_count == 0

    client.handle_line(_ack(1, old_tx, "ON", "ON", 0))
    assert events.select("conn_param_request_late_ack")
    blocked = client.request("ON", timeout_s=0.5)
    assert blocked["applied"] is False
    assert len(commands) == 1


def test_duplicate_on_off_requests_use_distinct_transactions() -> None:
    commands: list[bytes] = []
    client: Any

    def writer(data: bytes) -> int:
        commands.append(data)
        tx, mode = _transaction_from(data)
        client.handle_line(_ack(2, tx, mode, mode, 0))
        return len(data)

    client, _events = _new_client(2, writer)
    results = [
        client.request(mode, timeout_s=0.1) for mode in ("OFF", "ON", "ON", "OFF")
    ]

    tx_ids = [_transaction_from(command)[0] for command in commands]
    assert len(set(tx_ids)) == len(tx_ids)
    assert [result["requested"] for result in results] == ["OFF", "ON", "ON", "OFF"]
    assert all(result["applied"] is True for result in results)


def test_wrong_node_ack_fails_pending_request_and_poisons_session() -> None:
    commands: list[bytes] = []
    command_written = threading.Event()

    def writer(data: bytes) -> int:
        commands.append(data)
        command_written.set()
        return len(data)

    client, events = _new_client(1, writer)
    results: list[dict[str, object]] = []
    request_thread = threading.Thread(
        target=lambda: results.append(client.request("OFF", timeout_s=0.5))
    )
    request_thread.start()
    assert command_written.wait(timeout=0.5)
    tx, _ = _transaction_from(commands[0])

    client.handle_line(f"prefix {_ack(1, tx, 'OFF', 'OFF', 0)}")
    assert request_thread.is_alive()
    client.handle_line(_ack(2, tx, "OFF", "OFF", 0))
    request_thread.join(timeout=0.5)

    assert not request_thread.is_alive()
    assert results[0]["applied"] is False
    assert "node" in str(results[0]["error"]).lower()
    assert events.select("conn_param_request_wrong_node_ack")
    assert client.request("ON", timeout_s=0.0)["applied"] is False
    assert len(commands) == 1


def test_wrong_transaction_ack_fails_pending_request_and_poisons_session() -> None:
    commands: list[bytes] = []
    command_written = threading.Event()

    def writer(data: bytes) -> int:
        commands.append(data)
        command_written.set()
        return len(data)

    client, events = _new_client(1, writer)
    results: list[dict[str, object]] = []
    request_thread = threading.Thread(
        target=lambda: results.append(client.request("OFF", timeout_s=0.5))
    )
    request_thread.start()
    assert command_written.wait(timeout=0.5)
    tx, _ = _transaction_from(commands[0])

    client.handle_line(_ack(1, tx + 1, "OFF", "OFF", 0))
    request_thread.join(timeout=0.5)

    assert not request_thread.is_alive()
    assert results[0]["applied"] is False
    assert "tx" in str(results[0]["error"]).lower()
    assert events.select("conn_param_request_wrong_tx_ack")
    assert client.request("ON", timeout_s=0.0)["applied"] is False
    assert len(commands) == 1


def test_ack_with_nonzero_rc_or_wrong_selected_mode_is_not_applied() -> None:
    commands: list[bytes] = []
    client: Any

    def writer(data: bytes) -> int:
        commands.append(data)
        tx, _mode = _transaction_from(data)
        client.handle_line(_ack(1, tx, "ON", "OFF", -16))
        return len(data)

    client, _events = _new_client(1, writer)

    result = client.request("ON", timeout_s=0.1)

    assert result["acknowledged"] is True
    assert result["selected"] == "OFF"
    assert result["rc"] == -16
    assert result["applied"] is False
    assert client.pending_count == 0


def test_delayed_write_duration_is_recorded_in_the_event_sidecar() -> None:
    client: Any

    def writer(data: bytes) -> int:
        tx, mode = _transaction_from(data)
        time.sleep(0.03)
        client.handle_line(_ack(1, tx, mode, mode, 0))
        return len(data)

    client, events = _new_client(1, writer, slow_write_threshold_s=0.01)

    result = client.request("OFF", timeout_s=0.1)

    write_events = events.select("conn_param_request_write")
    assert result["applied"] is True
    assert write_events[0]["delayed"] is True
    assert int(write_events[0]["duration_ns"]) >= 10_000_000


class _FakeCapture:
    def __init__(
        self,
        node: NodeId,
        *,
        ready: bool = True,
        fail_mode: str | None = None,
    ) -> None:
        self.node = node
        self.ready = ready
        self.fail_mode = fail_mode
        self.ready_calls = 0
        self.modes: list[str] = []

    def wait_control_ready(self, timeout_s: float) -> bool:
        self.ready_calls += 1
        return self.ready

    def begin_control_session(self, timeout_s: float) -> dict[str, object]:
        self.ready_calls += 1
        return {
            "node_id": int(self.node),
            "session": _SESSION_NONCE,
            "ready": self.ready,
            "error": None if self.ready else "READY timeout",
        }

    def begin_fresh_control_session(self, timeout_s: float) -> dict[str, object]:
        return self.begin_control_session(timeout_s)

    def set_mode(self, mode: str, *, timeout_s: float = 0.5) -> dict[str, object]:
        self.modes.append(mode)
        applied = mode != self.fail_mode
        return {
            "node_id": int(self.node),
            "tx": len(self.modes),
            "requested": mode,
            "selected": mode if applied else "OFF",
            "rc": 0 if applied else -16,
            "acknowledged": True,
            "applied": applied,
            "error": None if applied else "mode was not applied",
        }


def test_initial_matrix_handshake_waits_for_ready_then_off_on_off_each_node() -> None:
    captures = {
        NodeId.A: _FakeCapture(NodeId.A),
        NodeId.B: _FakeCapture(NodeId.B),
    }
    events = _EventSink()

    handshake = asyncio_run(
        matrix_runner._initial_control_handshake(captures, events, timeout_s=0.1)
    )

    assert handshake["A"]["applied"] is True
    assert handshake["B"]["applied"] is True
    assert captures[NodeId.A].ready_calls == 1
    assert captures[NodeId.B].ready_calls == 1
    assert captures[NodeId.A].modes == ["OFF", "ON", "OFF"]
    assert captures[NodeId.B].modes == ["OFF", "ON", "OFF"]


def test_block_control_failure_does_not_invoke_the_ble_run() -> None:
    captures = {
        NodeId.A: _FakeCapture(NodeId.A, fail_mode="ON"),
        NodeId.B: _FakeCapture(NodeId.B),
    }
    events = _EventSink()
    ble_runs: list[str] = []

    async def run_condition(**_kwargs: object) -> dict[str, object]:
        ble_runs.append("started")
        return {"error": None}

    with pytest.raises(RuntimeError, match="Node A.*ON"):
        asyncio_run(
            matrix_runner._run_condition_with_control(
                request_mode="ON",
                cdc_captures=captures,
                events=events,
                run_condition=run_condition,
                run_kwargs={"condition": "a_only"},
                timeout_s=0.1,
            )
        )

    assert ble_runs == []
    assert captures[NodeId.A].modes == ["ON", "OFF"]
    assert captures[NodeId.B].modes == []


def test_block_control_failure_rolls_back_previously_applied_nodes() -> None:
    captures = {
        NodeId.A: _FakeCapture(NodeId.A),
        NodeId.B: _FakeCapture(NodeId.B, fail_mode="ON"),
    }
    events = _EventSink()

    async def run_condition(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("BLE must not start after a failed control gate")

    with pytest.raises(matrix_runner.CdcControlGateError) as raised:
        asyncio_run(
            matrix_runner._run_condition_with_control(
                request_mode="ON",
                cdc_captures=captures,
                events=events,
                run_condition=run_condition,
                run_kwargs={"condition": "dual_a_to_b"},
                timeout_s=0.1,
                controlled_nodes=(NodeId.A, NodeId.B),
            )
        )

    assert captures[NodeId.A].modes == ["ON", "OFF"]
    assert captures[NodeId.B].modes == ["ON", "OFF"]
    rollback = raised.value.context["rollback_results"]
    assert rollback["A"]["applied"] is True
    assert rollback["B"]["applied"] is True


def test_initial_control_failure_stops_before_any_mode_handshake() -> None:
    captures = {
        NodeId.A: _FakeCapture(NodeId.A),
        NodeId.B: _FakeCapture(NodeId.B, ready=False),
    }

    with pytest.raises(RuntimeError, match="Node B.*HELLO/READY"):
        asyncio_run(
            matrix_runner._initial_control_handshake(
                captures, _EventSink(), timeout_s=0.0
            )
        )

    assert captures[NodeId.A].modes == ["OFF"]
    assert captures[NodeId.B].modes == []


def test_initial_mode_failure_rolls_back_both_control_nodes() -> None:
    captures = {
        NodeId.A: _FakeCapture(NodeId.A, fail_mode="ON"),
        NodeId.B: _FakeCapture(NodeId.B),
    }

    with pytest.raises(matrix_runner.CdcControlGateError) as raised:
        asyncio_run(
            matrix_runner._initial_control_handshake(
                captures, _EventSink(), timeout_s=0.1
            )
        )

    assert captures[NodeId.A].modes == ["OFF", "ON", "OFF"]
    assert captures[NodeId.B].modes == ["OFF"]
    assert set(raised.value.context["rollback_results"]) == {"A", "B"}


def asyncio_run(awaitable: Any) -> Any:
    import asyncio

    return asyncio.run(awaitable)
