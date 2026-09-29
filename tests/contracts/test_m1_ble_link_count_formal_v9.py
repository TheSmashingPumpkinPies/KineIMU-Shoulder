from __future__ import annotations

import asyncio
from importlib import import_module
from pathlib import Path

import pytest


class _FakeCapture:
    def __init__(self, node_name: str, order: list[str], *, ready: bool = True) -> None:
        self.node_name = node_name
        self.order = order
        self.ready = ready

    def begin_control_session(self, timeout_s: float) -> dict[str, object]:
        self.order.append(f"HELLO_READY_{self.node_name}")
        return {
            "node_id": 1 if self.node_name == "A" else 2,
            "session": f"session-{self.node_name}",
            "ready": self.ready,
            "error": None if self.ready else "READY timeout",
        }


def test_fixed_off_run_waits_for_both_cdc_control_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        formal = import_module("experiments.m1_ble_link_count_formal_v9")
        helper = getattr(formal, "_run_after_control_ready", None)
        assert callable(helper), "formal acquisition needs an explicit CDC HELLO/READY gate"

        order: list[str] = []
        captures = {
            formal.NodeId.A: _FakeCapture("A", order),
            formal.NodeId.B: _FakeCapture("B", order),
        }

        async def direct_worker(function: object, *args: object, **kwargs: object) -> object:
            return function(*args, **kwargs)  # type: ignore[operator]

        monkeypatch.setattr(formal.matrix_runner, "_run_control_worker", direct_worker)

        async def run_fixed_off() -> dict[str, object]:
            order.append("FIXED_OFF")
            return {"started": True}

        control_events: list[tuple[str, dict[str, object]]] = []

        def event_writer(event: str, **details: object) -> None:
            control_events.append((event, details))

        result = await helper(
            cdc_captures=captures,
            run_index=1,
            events=event_writer,
            run_condition=run_fixed_off,
            timeout_s=5.0,
        )

        assert order == ["HELLO_READY_A", "HELLO_READY_B", "FIXED_OFF"]
        assert result["cdc_control_sessions"]["A"]["ready"] is True
        assert result["cdc_control_sessions"]["B"]["ready"] is True
        assert [event for event, _ in control_events] == [
            "formal_run_cdc_control_session_ready",
            "formal_run_cdc_control_session_ready",
        ]

    asyncio.run(scenario())


def test_failed_ready_gate_never_starts_fixed_off(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        formal = import_module("experiments.m1_ble_link_count_formal_v9")
        helper = getattr(formal, "_run_after_control_ready", None)
        assert callable(helper), "formal acquisition needs an explicit CDC HELLO/READY gate"

        order: list[str] = []
        captures = {
            formal.NodeId.A: _FakeCapture("A", order),
            formal.NodeId.B: _FakeCapture("B", order, ready=False),
        }

        async def direct_worker(function: object, *args: object, **kwargs: object) -> object:
            return function(*args, **kwargs)  # type: ignore[operator]

        monkeypatch.setattr(formal.matrix_runner, "_run_control_worker", direct_worker)

        async def run_fixed_off() -> dict[str, object]:
            order.append("FIXED_OFF")
            return {"started": True}

        with pytest.raises(formal.matrix_runner.CdcControlGateError, match="Node B.*READY"):
            await helper(
                cdc_captures=captures,
                run_index=1,
                events=lambda *_args, **_kwargs: None,
                run_condition=run_fixed_off,
                timeout_s=5.0,
            )

        assert order == ["HELLO_READY_A", "HELLO_READY_B"]

    asyncio.run(scenario())


def test_independent_audit_requires_both_run_local_cdc_ready_events() -> None:
    auditor = import_module("experiments.m1_ble_link_count_formal_audit_v9")
    audit_gate = getattr(auditor, "_audit_control_readiness", None)
    assert callable(audit_gate), "independent audit must verify the CDC READY gate"

    events = [
        {
            "event": "formal_run_cdc_control_session_ready",
            "run_index": 3,
            "node": "A",
            "ready": True,
            "session": "session-A",
        },
        {
            "event": "formal_run_cdc_control_session_ready",
            "run_index": 3,
            "node": "B",
            "ready": True,
            "session": "session-B",
        },
    ]
    sessions = {
        "A": {"ready": True, "session": "session-A"},
        "B": {"ready": True, "session": "session-B"},
    }

    assert audit_gate(3, events, sessions) == []
    assert audit_gate(3, events[:1], sessions)
    events[1]["ready"] = False
    assert audit_gate(3, events, sessions)


def test_independent_audit_requires_ready_then_boundaries_then_fixed_off() -> None:
    auditor = import_module("experiments.m1_ble_link_count_formal_audit_v9")
    audit_order = getattr(auditor, "_audit_control_boundary_order", None)
    assert callable(audit_order), "independent audit must enforce CDC/OFF event order"

    events = [
        {"event": "formal_run_cdc_control_session_ready", "run_index": 4, "node": "A", "host_monotonic_ns": 10},
        {"event": "formal_run_cdc_control_session_ready", "run_index": 4, "node": "B", "host_monotonic_ns": 11},
        {"event": "formal_run_cdc_boundary", "run_index": 4, "node": "A", "offset": 100, "host_monotonic_ns": 12},
        {"event": "formal_run_cdc_boundary", "run_index": 4, "node": "B", "offset": 200, "host_monotonic_ns": 13},
        {
            "event": "block_request_mode_acknowledgment",
            "run_index": 4,
            "node": "A",
            "request_mode": "OFF",
            "host_monotonic_ns": 14,
        },
        {
            "event": "block_request_mode_acknowledgment",
            "run_index": 4,
            "node": "B",
            "request_mode": "OFF",
            "host_monotonic_ns": 15,
        },
    ]
    assert audit_order(4, events) == []

    events[2]["host_monotonic_ns"] = 9
    assert any("boundary was recorded before both READY" in error for error in audit_order(4, events))


def test_locked_config_serializes_pristine_start_as_boolean(monkeypatch: pytest.MonkeyPatch) -> None:
    formal = import_module("experiments.m1_ble_link_count_formal_v9")
    monkeypatch.setattr(formal.precheck, "_live_input_config", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(formal.matrix_runner, "_git_head", lambda _root: "a" * 40)
    monkeypatch.setattr(
        formal.precheck,
        "validate_committed_precheck_inputs",
        lambda *_args, **_kwargs: None,
    )
    same_file = Path(__file__)
    config = formal._locked_input_config(
        Path("<external-data>/v9-config-test-root"),
        preflash={},
        images={formal.NodeId.A: same_file, formal.NodeId.B: same_file},
        configurations={formal.NodeId.A: same_file, formal.NodeId.B: same_file},
        port_info={formal.NodeId.A: {}, formal.NodeId.B: {}},
        adapter_identity={},
    )

    assert config["require_pristine_start"] is True
    assert config["plan_version"] == "v9"
    assert config["precheck_plan_version"] == "v6"


def test_shared_matrix_runner_uses_v9_run_schemas() -> None:
    matrix_runner = import_module("experiments.m1_ble_link_matrix")

    assert matrix_runner._run_config_schema("link_count_formal_v9") == (
        "kineimu.m1.ble-link-count-formal-v9-run/1.0",
        "kineimu.m1.ble-link-count-formal-v9-run-result/1.0",
        "m1-link-count-formal-v9",
    )
