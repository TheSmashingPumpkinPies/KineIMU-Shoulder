"""Behavioral checks for session-bound CDC control transactions."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import experiments.m1_ble_link_matrix as matrix_runner


class _Events:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []

    def __call__(self, event: str, **details: object) -> None:
        self.rows.append({"event": event, **details})


def _client(
    nonce: str,
    writer: Callable[..., int],
) -> tuple[Any, _Events]:
    events = _Events()
    client = matrix_runner.ConnParamControlClient(
        node_id=1,
        write=writer,
        event_sink=events,
        session_nonce=nonce,
    )
    return client, events


def test_hello_requires_exact_node_and_session_before_controls_are_enabled() -> None:
    nonce = "0123456789abcdef"
    writes: list[bytes] = []
    hello_written = threading.Event()

    def writer(data: bytes, *, timeout_s: float) -> int:
        writes.append(data)
        hello_written.set()
        return len(data)

    client, _events = _client(nonce, writer)
    results: list[dict[str, object]] = []
    thread = threading.Thread(
        target=lambda: results.append(client.begin_session(timeout_s=0.5))
    )
    thread.start()
    assert hello_written.wait(timeout=0.5)
    assert writes == [b"HELLO session=0123456789abcdef\n"]

    # The session must fail closed on the wrong node; a later matching line
    # cannot turn the failed handshake into a successful one.
    client.handle_line("READY node_id=2 session=0123456789abcdef")
    thread.join(timeout=0.5)
    assert not thread.is_alive()
    assert results[0]["ready"] is False
    assert "node" in str(results[0]["error"]).lower()

    client.handle_line("READY node_id=1 session=0123456789abcdef")
    assert client.request("OFF", timeout_s=0.0)["applied"] is False
    assert len(writes) == 1


def test_wrong_session_ack_fails_the_pending_request_even_when_tx_matches() -> None:
    nonce = "0123456789abcdef"
    writes: list[bytes] = []
    hello_written = threading.Event()
    command_written = threading.Event()

    def writer(data: bytes, *, timeout_s: float) -> int:
        writes.append(data)
        if data.startswith(b"HELLO "):
            hello_written.set()
        else:
            command_written.set()
        return len(data)

    client, _events = _client(nonce, writer)
    ready_results: list[dict[str, object]] = []
    ready_thread = threading.Thread(
        target=lambda: ready_results.append(client.begin_session(timeout_s=0.5))
    )
    ready_thread.start()
    assert hello_written.wait(timeout=0.5)
    client.handle_line("READY node_id=1 session=0123456789abcdef")
    ready_thread.join(timeout=0.5)
    assert ready_results[0]["ready"] is True

    request_results: list[dict[str, object]] = []
    request_thread = threading.Thread(
        target=lambda: request_results.append(client.request("ON", timeout_s=0.5))
    )
    request_thread.start()
    assert command_written.wait(timeout=0.5)
    assert writes[-1] == (
        b"SET session=0123456789abcdef tx=1 mode=ON\n"
    )
    client.handle_line(
        "ACK node_id=1 session=fedcba9876543210 tx=1 "
        "requested=ON selected=ON rc=0"
    )
    request_thread.join(timeout=0.5)

    assert not request_thread.is_alive()
    assert request_results[0]["applied"] is False
    assert "session" in str(request_results[0]["error"]).lower()


def test_late_ack_after_timeout_poison_session_instead_of_matching_reused_tx() -> None:
    nonce = "0123456789abcdef"
    writes: list[bytes] = []
    hello_written = threading.Event()

    def writer(data: bytes, *, timeout_s: float) -> int:
        writes.append(data)
        if data.startswith(b"HELLO "):
            hello_written.set()
        return len(data)

    client, events = _client(nonce, writer)
    ready_results: list[dict[str, object]] = []
    ready_thread = threading.Thread(
        target=lambda: ready_results.append(client.begin_session(timeout_s=0.5))
    )
    ready_thread.start()
    assert hello_written.wait(timeout=0.5)
    client.handle_line("READY node_id=1 session=0123456789abcdef")
    ready_thread.join(timeout=0.5)

    first = client.request("OFF", timeout_s=0.0)
    assert first["applied"] is False
    client.handle_line(
        "ACK node_id=1 session=0123456789abcdef tx=1 "
        "requested=OFF selected=OFF rc=0"
    )
    second = client.request("ON", timeout_s=0.0)

    assert second["applied"] is False
    assert len(writes) == 2  # HELLO and the first SET only.
    assert any(row["event"] == "conn_param_request_late_ack" for row in events.rows)


def test_ack_delivered_after_transaction_deadline_is_rejected_during_write() -> None:
    nonce = "0123456789abcdef"
    holder: dict[str, Any] = {}

    def writer(data: bytes, *, timeout_s: float) -> int:
        if data.startswith(b"HELLO "):
            holder["client"].handle_line(
                "READY node_id=1 session=0123456789abcdef"
            )
        else:
            time.sleep(0.02)
            holder["client"].handle_line(
                "ACK node_id=1 session=0123456789abcdef tx=1 "
                "requested=ON selected=ON rc=0"
            )
        return len(data)

    client, events = _client(nonce, writer)
    holder["client"] = client
    assert client.begin_session(timeout_s=0.5)["ready"] is True

    result = client.request("ON", timeout_s=0.005)

    assert result["applied"] is False
    assert "deadline" in str(result["error"]).lower()
    assert client.poisoned is True
    assert any(row["event"] == "conn_param_request_late_ack" for row in events.rows)


def test_ready_delivered_after_handshake_deadline_is_rejected_during_write() -> None:
    nonce = "0123456789abcdef"
    holder: dict[str, Any] = {}

    def writer(data: bytes, *, timeout_s: float) -> int:
        assert data == b"HELLO session=0123456789abcdef\n"
        time.sleep(0.02)
        holder["client"].handle_line("READY node_id=1 session=0123456789abcdef")
        return len(data)

    client, events = _client(nonce, writer)
    holder["client"] = client

    result = client.begin_session(timeout_s=0.005)

    assert result["ready"] is False
    assert client.poisoned is True
    assert any(row["event"] == "conn_param_control_late_ready" for row in events.rows)
