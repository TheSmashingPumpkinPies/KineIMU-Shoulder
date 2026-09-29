"""Run the locked M1 peripheral connection-parameter root-cause matrix.

The experiment-only driver keeps the completion-driven TX profile, M1 recorder,
and raw capture format fixed. It varies the peripheral's local connection-
parameter request mode by the predeclared OFF–ON–ON–OFF block schedule. It does
not change the public data schema, decouple host disk writes, or change the TX
queue capacity.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import queue
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kineimu_shoulder.io.m1_ble import (
    CLOCK_EXCHANGE_UUID,
    DEFAULT_RECOVERY_TIMEOUT_S,
    IDENTITY_CONFIG_UUID,
    M1_SCAN_CLEANUP_GRACE_S,
    M1_SERVICE_UUID,
    STATUS_UUID,
    TELEMETRY_UUID,
    BleClient,
    CaptureWindowCallback,
    ClientFactory,
    M1BleSessionRecorder,
    NodeTarget,
    _CaptureReadyGate,
    _CaptureSink,
    _NodeRecorder,
    create_bleak_client,
    discover_m1_ble_device,
)
from kineimu_shoulder.io.m1_control import AcquisitionState, Status, decode_status
from kineimu_shoulder.io.m1_packet import NodeId
from validation.transport_experiment import EventLog

ROOT_CAUSE_BLOCK_SCHEDULE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("OFF", ("a_only", "b_only", "dual_b_to_a", "dual_a_to_b")),
    ("ON", ("b_only", "dual_a_to_b", "a_only", "dual_b_to_a")),
    ("ON", ("dual_b_to_a", "a_only", "dual_a_to_b", "b_only")),
    ("OFF", ("dual_a_to_b", "dual_b_to_a", "b_only", "a_only")),
)
CONDITIONS = frozenset({"a_only", "b_only", "dual_a_to_b", "dual_b_to_a"})
ROOT_CAUSE_PLAN_SHA256 = "6B295C3C5CC5B2B9E06623D9E28B9A7DD70F342085DA66D29D3ABBF847B9D2D4"
ROOT_CAUSE_OUTPUT_ROOT = Path("<external-data>/kineimu_m1_ble_connparam_rootcause_20260921_01")
ROOT_CAUSE_PLAN_V2_SHA256 = "D2FA561B8E699BB61855188931C0C40812600CD7D30117A79D88CFB92D52B9FB"
ROOT_CAUSE_OUTPUT_ROOT_V2 = Path(
    "<external-data>/kineimu_m1_ble_connparam_rootcause_v2_20260923_01"
)
ROOT_CAUSE_SETUP_SETTLE_S = 10.0
ROOT_CAUSE_CAPTURE_S = 15.0
ROOT_CAUSE_INTER_RUN_REST_S = 2.0
ROOT_CAUSE_SCAN_TIMEOUT_S = 5.0
ROOT_CAUSE_CONNECTION_TIMEOUT_S = 15.0
ROOT_CAUSE_DISCONNECT_TIMEOUT_S = 5.0
ROOT_CAUSE_TARGET_PARAMETERS = (15_000, 0, 420_000)
ROOT_CAUSE_NODE_USB_SERIALS = {
    NodeId.A: "0000000000000001",
    NodeId.B: "0000000000000002",
}


def _validate_plan_output_root(plan_sha256: str, root_dir: Path) -> Path:
    """Bind each immutable plan hash to its own one-time output root."""

    normalized_sha256 = plan_sha256.upper()
    if normalized_sha256 == ROOT_CAUSE_PLAN_SHA256:
        expected_root = ROOT_CAUSE_OUTPUT_ROOT
    elif normalized_sha256 == ROOT_CAUSE_PLAN_V2_SHA256:
        expected_root = ROOT_CAUSE_OUTPUT_ROOT_V2
    else:
        raise ValueError(f"unknown locked plan SHA-256: {plan_sha256}")

    resolved_root = expected_root.resolve()
    if root_dir.resolve() != resolved_root:
        raise ValueError(
            f"plan SHA-256 {normalized_sha256} requires locked output root {resolved_root}"
        )
    return resolved_root


def _change_policy(
    completion_driven_tx: bool,
    *,
    connection_parameter_request: bool = True,
) -> dict[str, bool]:
    """Return the transport changes that are true for this matrix profile."""

    return {
        "connection_parameter_request": connection_parameter_request,
        "completion_driven_tx": completion_driven_tx,
        "host_disk_write_decoupling": False,
        "tx_queue_capacity_change": False,
    }


def _run_config_schema(experiment_profile: str) -> tuple[str, str, str]:
    """Return the versioned run/result schemas and session prefix for a profile."""

    if experiment_profile == "link_count_precheck":
        return (
            "kineimu.m1.ble-link-count-precheck-run/2.0",
            "kineimu.m1.ble-link-count-precheck-run-result/2.0",
            "m1-ble-link-count-precheck-v2",
        )
    if experiment_profile == "link_count_formal_v7":
        return (
            "kineimu.m1.ble-link-count-formal-run/1.0",
            "kineimu.m1.ble-link-count-formal-run-result/1.0",
            "m1-link-count-formal-v7",
        )
    if experiment_profile == "link_count_formal_v8":
        return (
            "kineimu.m1.ble-link-count-formal-v8-run/1.0",
            "kineimu.m1.ble-link-count-formal-v8-run-result/1.0",
            "m1-link-count-formal-v8",
        )
    if experiment_profile == "link_count_formal_v9":
        return (
            "kineimu.m1.ble-link-count-formal-v9-run/1.0",
            "kineimu.m1.ble-link-count-formal-v9-run-result/1.0",
            "m1-link-count-formal-v9",
        )
    return (
        "kineimu.m1.ble-connparam-root-cause-run/1.0",
        "kineimu.m1.ble-connparam-root-cause-run-result/1.0",
        "m1-ble-connparam-root-cause",
    )


def matrix_order(blocks: int) -> tuple[str, ...]:
    """Return the locked 16-condition connection-parameter root-cause order."""

    if blocks != len(ROOT_CAUSE_BLOCK_SCHEDULE):
        raise ValueError("the locked connection-parameter experiment requires exactly four blocks")
    return tuple(
        condition
        for _request_mode, block in ROOT_CAUSE_BLOCK_SCHEDULE
        for condition in block
    )


def resolve_cdc_port_by_serial(
    usb_serial: str, *, ports: Iterable[object] | None = None
) -> dict[str, object]:
    """Resolve one current CDC port by its USB serial number, never by COM order."""

    if ports is None:
        from serial.tools import list_ports  # type: ignore[import-untyped]

        port_inventory = list_ports.comports()
    else:
        port_inventory = ports
    matches = [
        port
        for port in port_inventory
        if getattr(port, "serial_number", None) == usb_serial
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one CDC port for USB serial {usb_serial}, found {len(matches)}"
        )
    port = matches[0]
    return {
        "device": getattr(port, "device", None),
        "serial_number": getattr(port, "serial_number", None),
        "vid": getattr(port, "vid", None),
        "pid": getattr(port, "pid", None),
        "hwid": getattr(port, "hwid", None),
    }


def _nodes_for_condition(condition: str) -> tuple[NodeId, ...]:
    if condition == "a_only":
        return (NodeId.A,)
    if condition == "b_only":
        return (NodeId.B,)
    if condition in {"dual_a_to_b", "dual_b_to_a"}:
        return (NodeId.A, NodeId.B)
    raise ValueError(f"unsupported matrix condition: {condition}")


def _capture_error(capture: object) -> str | None:
    error = getattr(capture, "error", None)
    if error is not None:
        return str(error)
    done = getattr(capture, "done", None)
    if done is not None and done.is_set():
        return "CDC capture thread is not running"
    return None


async def _await_cleanup_completion(
    awaitable: Awaitable[Any],
) -> tuple[Any, bool]:
    """Complete a cleanup task before allowing cancellation to escape."""

    cleanup = asyncio.ensure_future(awaitable)
    cancelled = False
    while True:
        try:
            return await asyncio.shield(cleanup), cancelled
        except asyncio.CancelledError:
            cancelled = True
            if cleanup.done():
                if cleanup.cancelled():
                    return None, cancelled
                return cleanup.result(), cancelled


async def _run_control_worker(
    function: Callable[..., Any], *args: Any, **kwargs: Any
) -> Any:
    """Keep serial work alive through task cancellation before propagating it."""

    worker = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
        try:
            worker.result()
        except BaseException:
            pass
        raise


async def _rollback_control_nodes(
    cdc_captures: dict[NodeId, _MatrixCdcCapture],
    nodes: tuple[NodeId, ...],
    events: Callable[..., None],
    *,
    timeout_s: float,
    event_name: str,
) -> dict[str, dict[str, object]]:
    """Start fresh nonce sessions and explicitly request OFF on each node."""

    rollback: dict[str, dict[str, object]] = {}
    for node in reversed(nodes):
        capture = cdc_captures[node]
        capture_error = _capture_error(capture)
        result: dict[str, object] = {
            "node_id": int(node),
            "requested": "OFF",
            "ready": False,
            "applied": False,
            "error": capture_error,
        }
        if capture_error is None:
            begin_fresh = getattr(
                capture, "begin_fresh_control_session", capture.begin_control_session
            )
            try:
                ready = await _run_control_worker(begin_fresh, timeout_s)
                result["ready_result"] = ready
                if not isinstance(ready, dict) or ready.get("ready") is not True:
                    result["error"] = (
                        str(ready.get("error"))
                        if isinstance(ready, dict)
                        else "fresh HELLO/READY returned no result"
                    )
                else:
                    result["ready"] = True
                    ack = await _run_control_worker(
                        capture.set_mode, "OFF", timeout_s=timeout_s
                    )
                    if isinstance(ack, dict):
                        result.update(ack)
                    else:
                        result["error"] = "OFF transaction returned no result"
            except Exception as error:
                result["error"] = f"{type(error).__name__}: {error}"
        result["applied"] = result.get("applied") is True
        rollback[node.name] = result
        events(event_name, node=node, **result)
    return rollback


async def _initial_control_handshake(
    cdc_captures: dict[NodeId, _MatrixCdcCapture],
    events: Callable[..., None],
    *,
    timeout_s: float = 5.0,
) -> dict[str, dict[str, object]]:
    """Establish nonce-bound sessions, then exercise OFF/ON/OFF."""

    session_values = await asyncio.gather(
        *(
            _run_control_worker(
                cdc_captures[node].begin_control_session, timeout_s
            )
            for node in (NodeId.A, NodeId.B)
        )
    )
    handshake: dict[str, dict[str, object]] = {}
    readiness_failures: list[str] = []
    for node, session_result in zip(
        (NodeId.A, NodeId.B), session_values, strict=True
    ):
        capture_error = _capture_error(cdc_captures[node])
        observed_ready = (
            isinstance(session_result, dict)
            and session_result.get("ready") is True
            and capture_error is None
        )
        handshake[node.name] = {
            "node_id": int(node),
            "control_ready": observed_ready,
            "session": session_result.get("session")
            if isinstance(session_result, dict)
            else None,
            "ready_result": session_result,
            "requests": [],
            "applied": False,
        }
        events(
            "initial_control_ready",
            node=node,
            control_ready=observed_ready,
            error=(
                capture_error
                or (
                    str(session_result.get("error"))
                    if isinstance(session_result, dict)
                    and session_result.get("error") is not None
                    else None
                )
            ),
            session=(
                session_result.get("session")
                if isinstance(session_result, dict)
                else None
            ),
        )
        if not observed_ready:
            detail = capture_error or (
                str(session_result.get("error"))
                if isinstance(session_result, dict)
                else "HELLO/READY returned no session result"
            )
            readiness_failures.append(
                f"Node {node.name} HELLO/READY gate failed: {detail}"
            )
    if readiness_failures:
        rollback_results = await _rollback_control_nodes(
            cdc_captures,
            (NodeId.A, NodeId.B),
            events,
            timeout_s=timeout_s,
            event_name="initial_control_readiness_rollback",
        )
        raise CdcControlGateError(
            "; ".join(readiness_failures),
            context={
                "initial_control_handshake": handshake,
                "rollback_results": rollback_results,
            },
        )

    for node in (NodeId.A, NodeId.B):
        capture = cdc_captures[node]
        node_result = handshake[node.name]
        requests = node_result["requests"]
        assert isinstance(requests, list)
        for mode in ("OFF", "ON", "OFF"):
            try:
                ack = await _run_control_worker(
                    capture.set_mode, mode, timeout_s=timeout_s
                )
            except Exception as error:
                ack = {
                    "node_id": int(node),
                    "requested": mode,
                    "acknowledged": False,
                    "applied": False,
                    "error": f"{type(error).__name__}: {error}",
                }
            requests.append(ack)
            node_result.update(ack)
            events(
                "initial_control_handshake_request",
                node=node,
                **ack,
            )
            if ack.get("applied") is not True:
                node_result["applied"] = False
                rollback_results = await _rollback_control_nodes(
                    cdc_captures,
                    (NodeId.A, NodeId.B),
                    events,
                    timeout_s=timeout_s,
                    event_name="initial_control_handshake_rollback",
                )
                node_result["rollback_results"] = rollback_results
                raise CdcControlGateError(
                    f"Node {node.name} {mode} initial control handshake failed: "
                    f"{ack.get('error') or 'mode was not applied'}",
                    control_results={node: ack},
                    context={
                        "initial_control_handshake": handshake,
                        "rollback_results": rollback_results,
                    },
                )
        node_result["applied"] = True
    return handshake


async def _run_condition_with_control(
    *,
    request_mode: str,
    cdc_captures: dict[NodeId, _MatrixCdcCapture],
    events: Callable[..., None],
    run_condition: Callable[..., Awaitable[dict[str, object]]],
    run_kwargs: dict[str, object],
    timeout_s: float = 5.0,
    controlled_nodes: tuple[NodeId, ...] | None = None,
) -> dict[str, object]:
    """Apply and verify a block mode before invoking the BLE capture runner."""

    if request_mode not in {"OFF", "ON"}:
        raise ValueError(f"unsupported connection-parameter request mode: {request_mode}")
    condition = run_kwargs.get("condition")
    if not isinstance(condition, str):
        raise ValueError("run_kwargs must contain a condition")
    nodes = controlled_nodes or _nodes_for_condition(condition)
    control_results: dict[NodeId, dict[str, object]] = {}
    for node in nodes:
        capture = cdc_captures[node]
        capture_error = _capture_error(capture)
        if capture_error is not None:
            ack: dict[str, object] = {
                "node_id": int(node),
                "requested": request_mode,
                "acknowledged": False,
                "applied": False,
                "error": capture_error,
            }
        else:
            try:
                ack = await _run_control_worker(
                    capture.set_mode, request_mode, timeout_s=timeout_s
                )
            except Exception as error:
                ack = {
                    "node_id": int(node),
                    "requested": request_mode,
                    "acknowledged": False,
                    "applied": False,
                    "error": f"{type(error).__name__}: {error}",
                }
        control_results[node] = ack
        events(
            "block_request_mode_acknowledgment",
            node=node,
            request_mode=request_mode,
            **ack,
        )
        if ack.get("applied") is not True:
            rollback_results = await _rollback_control_nodes(
                cdc_captures,
                nodes,
                events,
                timeout_s=timeout_s,
                event_name="block_mode_control_rollback",
            )
            raise CdcControlGateError(
                f"Node {node.name} {request_mode} control gate failed: "
                f"{ack.get('error') or 'mode was not applied'}",
                control_results=control_results,
                context={
                    "block_mode_control": control_results,
                    "rollback_results": rollback_results,
                },
            )

    kwargs = dict(run_kwargs)
    kwargs["pre_run_control_results"] = {
        node.name: ack for node, ack in control_results.items()
    }
    return await run_condition(**kwargs)


async def _cut_cdc_captures(
    cdc_captures: dict[NodeId, _MatrixCdcCapture],
) -> dict[NodeId, int]:
    """Take synchronized run boundaries and fail before BLE if either CDC path fails."""

    offsets: dict[NodeId, int] = {}
    for node in (NodeId.A, NodeId.B):
        capture = cdc_captures[node]
        capture_error = _capture_error(capture)
        if capture_error is not None:
            raise CdcControlGateError(
                f"Node {node.name} CDC capture gate failed before BLE: {capture_error}"
            )
        try:
            offsets[node] = await _run_control_worker(capture.cut)
        except Exception as error:
            raise CdcControlGateError(
                f"Node {node.name} CDC capture boundary failed before BLE: "
                f"{type(error).__name__}: {error}"
            ) from error
    return offsets


def _connection_order_for_condition(condition: str) -> tuple[NodeId, ...]:
    if condition == "dual_a_to_b":
        return (NodeId.A, NodeId.B)
    if condition == "dual_b_to_a":
        return (NodeId.B, NodeId.A)
    return _nodes_for_condition(condition)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _validate_firmware_source_commit(repo_root: Path, firmware_source_commit: str) -> str:
    """Require a clean host checkout with unchanged firmware inputs since image build."""

    if re.fullmatch(r"[0-9a-fA-F]{40}", firmware_source_commit) is None:
        raise ValueError("firmware source commit must be a full 40-character Git SHA")
    try:
        source_result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "rev-parse",
                "--verify",
                f"{firmware_source_commit}^{{commit}}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(
            f"firmware source commit is not available: {firmware_source_commit}"
        ) from error
    source_commit = source_result.stdout.strip()
    if source_commit.lower() != firmware_source_commit.lower():
        raise ValueError("firmware source commit must be supplied as its full canonical SHA")

    host_head = _git_head(repo_root)
    if host_head is None:
        raise RuntimeError("cannot resolve current host repository HEAD")
    ancestor = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", source_commit, host_head],
        capture_output=True,
        text=True,
    )
    if ancestor.returncode != 0:
        raise ValueError("firmware source commit must be an ancestor of the current host HEAD")

    firmware_diff = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--quiet",
            source_commit,
            host_head,
            "--",
            "firmware",
            "experiments/M1_CONN_PARAM_ROOTCAUSE.overlay.conf",
        ],
        capture_output=True,
        text=True,
    )
    if firmware_diff.returncode != 0:
        raise ValueError("firmware build inputs changed after the recorded image source commit")

    status = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=normal"],
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise ValueError("the host repository must have a clean working tree before acquisition")
    return host_head


class _MatrixConnectionGate:
    def __init__(
        self,
        *,
        required_nodes: tuple[NodeId, ...],
        first_node: NodeId | None,
        events: EventLog,
        connection_timeout_s: float = ROOT_CAUSE_CONNECTION_TIMEOUT_S,
    ) -> None:
        if connection_timeout_s <= 0.0:
            raise ValueError("connection timeout must be positive")
        self.required_nodes = frozenset(required_nodes)
        self.first_node = first_node
        self.events = events
        self.connection_timeout_s = connection_timeout_s
        self.loop = asyncio.get_running_loop()
        self.first_connected = asyncio.Event()
        self.all_connected = asyncio.Event()
        self._peripheral_state_changed = asyncio.Event()
        self.failed_event = asyncio.Event()
        self.connected_nodes: set[NodeId] = set()
        self.failure: str | None = None
        self.last_connection_completed_monotonic_ns: int | None = None
        self.peripheral_connected_at: dict[NodeId, int] = {}
        self.peripheral_connected_uptime_ms: dict[NodeId, int] = {}
        self.peripheral_disconnected_at: dict[NodeId, int] = {}
        self.peripheral_disconnected_uptime_ms: dict[NodeId, int] = {}
        self.connect_attempt_ids: dict[NodeId, int] = {
            node: 0 for node in self.required_nodes
        }
        self.successful_connect_attempt_ids: dict[NodeId, int] = {}
        self.peripheral_connected_attempt_ids: dict[NodeId, int] = {}
        self.peripheral_disconnected_attempt_ids: dict[NodeId, int] = {}
        self.parameter_updates: dict[NodeId, list[dict[str, object]]] = {
            node: [] for node in self.required_nodes
        }
        self._peripheral_lock = threading.Lock()

    def note_connect_attempt(self, node: NodeId) -> int:
        if node not in self.required_nodes:
            raise ValueError(f"Node {node.name} is not in this connection gate")
        with self._peripheral_lock:
            attempt_id = self.connect_attempt_ids[node] + 1
            self.connect_attempt_ids[node] = attempt_id
        return attempt_id

    def note_connected(self, node: NodeId, attempt_id: int) -> None:
        with self._peripheral_lock:
            current_attempt_id = self.connect_attempt_ids.get(node)
            if current_attempt_id != attempt_id:
                error = RuntimeError(
                    f"Node {node.name} completed stale connect attempt {attempt_id}; "
                    f"current attempt is {current_attempt_id}"
                )
            else:
                error = None
                self.successful_connect_attempt_ids[node] = attempt_id
        if error is not None:
            self.note_failure(node, error)
            raise error
        self.connected_nodes.add(node)
        if node is self.first_node:
            self.first_connected.set()
        if self.connected_nodes.issuperset(self.required_nodes):
            self.last_connection_completed_monotonic_ns = time.monotonic_ns()
            self.all_connected.set()
            self.events.write(
                "selected_host_connects_completed",
                nodes=[item.name for item in sorted(self.required_nodes, key=int)],
                last_node=node,
                connect_attempt=attempt_id,
                monotonic_ns=self.last_connection_completed_monotonic_ns,
            )
        self._peripheral_state_changed.set()

    def note_firmware_event(
        self, node: NodeId, event_name: str, host_monotonic_ns: int, line: str
    ) -> None:
        if node not in self.required_nodes:
            return
        observed_node_match = re.match(
            r"^Node ([AB]): BLE link event=", line
        )
        if observed_node_match is None or NodeId[observed_node_match.group(1)] is not node:
            observed = (
                observed_node_match.group(1)
                if observed_node_match is not None
                else "unparseable"
            )
            error = RuntimeError(
                f"CDC Node {node.name} received BLE event labelled Node {observed}"
            )
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            if running_loop is self.loop:
                self.note_failure(node, error)
            else:
                self.loop.call_soon_threadsafe(self.note_failure, node, error)
            return
        firmware_time_match = re.search(r"\bfirmware_uptime_ms=([0-9]+)\b", line)
        if firmware_time_match is None:
            error = RuntimeError(
                f"Node {node.name} {event_name} event is missing firmware uptime"
            )
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            if running_loop is self.loop:
                self.note_failure(node, error)
            else:
                self.loop.call_soon_threadsafe(self.note_failure, node, error)
            return
        firmware_uptime_ms = int(firmware_time_match.group(1))
        if firmware_uptime_ms > 0xFFFFFFFF:
            error = RuntimeError(
                f"Node {node.name} firmware uptime is outside the uint32 range"
            )
            self.loop.call_soon_threadsafe(self.note_failure, node, error)
            return
        if event_name == "connected":
            attempt_id: int
            with self._peripheral_lock:
                attempt_id = self.connect_attempt_ids.get(node, 0)
                self.peripheral_connected_at[node] = host_monotonic_ns
                self.peripheral_connected_uptime_ms[node] = firmware_uptime_ms
                self.peripheral_disconnected_at.pop(node, None)
                self.peripheral_disconnected_uptime_ms.pop(node, None)
                self.peripheral_disconnected_attempt_ids.pop(node, None)
                self.peripheral_connected_attempt_ids[node] = attempt_id
                tuple_match = re.search(
                    r"interval_us=(?P<interval>[0-9]+) latency=(?P<latency>[0-9]+) "
                    r"supervision_timeout_us=(?P<timeout>[0-9]+)",
                    line,
                )
                connected_update: dict[str, object] = {
                    "host_monotonic_ns": host_monotonic_ns,
                    "firmware_uptime_ms": firmware_uptime_ms,
                    "line": line,
                    "firmware_event": event_name,
                    "connect_attempt": attempt_id,
                    "tuple_parsed": tuple_match is not None,
                }
                if tuple_match is not None:
                    connected_update.update(
                        interval_us=int(tuple_match.group("interval")),
                        latency=int(tuple_match.group("latency")),
                        supervision_timeout_us=int(tuple_match.group("timeout")),
                    )
                if tuple_match is not None:
                    self.parameter_updates[node].append(connected_update)
            self.events.write(
                "peripheral_connected_event",
                node=node,
                firmware_event_line=line,
                connect_attempt=attempt_id,
                peripheral_event_host_monotonic_ns=host_monotonic_ns,
                peripheral_event_firmware_uptime_ms=firmware_uptime_ms,
            )
            if attempt_id == 0:
                error = RuntimeError(
                    f"Node {node.name} peripheral connected event has no active host attempt"
                )
                self.loop.call_soon_threadsafe(self.note_failure, node, error)
            self.loop.call_soon_threadsafe(self._peripheral_state_changed.set)
            return
        if event_name == "disconnected":
            with self._peripheral_lock:
                attempt_id = self.peripheral_connected_attempt_ids.get(node, 0)
                self.peripheral_disconnected_at[node] = host_monotonic_ns
                self.peripheral_disconnected_uptime_ms[node] = firmware_uptime_ms
                self.peripheral_disconnected_attempt_ids[node] = attempt_id
            self.events.write(
                "peripheral_disconnected_event",
                node=node,
                firmware_event_line=line,
                connect_attempt=attempt_id,
                peripheral_event_host_monotonic_ns=host_monotonic_ns,
                peripheral_event_firmware_uptime_ms=firmware_uptime_ms,
            )
            self.loop.call_soon_threadsafe(self._peripheral_state_changed.set)
            return
        if event_name != "param_updated":
            return

        tuple_match = re.search(
            r"interval_us=(?P<interval>[0-9]+) latency=(?P<latency>[0-9]+) "
            r"supervision_timeout_us=(?P<timeout>[0-9]+)",
            line,
        )
        parameter_update: dict[str, object] = {
            "host_monotonic_ns": host_monotonic_ns,
            "firmware_uptime_ms": firmware_uptime_ms,
            "line": line,
            "firmware_event": event_name,
            "tuple_parsed": tuple_match is not None,
        }
        if tuple_match is not None:
            parameter_update.update(
                interval_us=int(tuple_match.group("interval")),
                latency=int(tuple_match.group("latency")),
                supervision_timeout_us=int(tuple_match.group("timeout")),
            )
        with self._peripheral_lock:
            parameter_update["connect_attempt"] = self.connect_attempt_ids.get(node, 0)
            self.parameter_updates[node].append(parameter_update)
        self.events.write("peripheral_param_updated", node=node, **parameter_update)

    def note_failure(self, node: NodeId, error: BaseException) -> None:
        if self.failure is None:
            self.failure = f"{type(error).__name__}: {error}"
        self.failed_event.set()
        self._peripheral_state_changed.set()
        self.events.write("ble_connection_setup_failure", node=node, detail=self.failure)

    def parameter_window_result(
        self, node: NodeId, duration_s: float
    ) -> dict[str, object]:
        if node not in self.required_nodes:
            raise ValueError(f"Node {node.name} is not in this connection gate")
        with self._peripheral_lock:
            connected_ns = self.peripheral_connected_at.get(node)
            connected_uptime_ms = self.peripheral_connected_uptime_ms.get(node)
            disconnected_ns = self.peripheral_disconnected_at.get(node)
            disconnected_uptime_ms = self.peripheral_disconnected_uptime_ms.get(node)
            disconnected_attempt_id = self.peripheral_disconnected_attempt_ids.get(node)
            connected_attempt_id = self.peripheral_connected_attempt_ids.get(node)
            updates = [dict(update) for update in self.parameter_updates[node]]
        if connected_ns is None:
            raise RuntimeError(
                f"Node {node.name} has no CDC peripheral connected-event anchor"
            )
        if connected_uptime_ms is None:
            raise RuntimeError(
                f"Node {node.name} connected event has no firmware uptime anchor"
            )
        deadline_ns = connected_ns + int(duration_s * 1_000_000_000)
        duration_ms = int(round(duration_s * 1_000))
        window_updates: list[dict[str, object]] = []
        for update in updates:
            update_uptime_ms = update.get("firmware_uptime_ms")
            if not isinstance(update_uptime_ms, int):
                continue
            elapsed_ms = (update_uptime_ms - connected_uptime_ms) & 0xFFFFFFFF
            if elapsed_ms <= duration_ms:
                window_updates.append(update)
        target_interval, target_latency, target_timeout = ROOT_CAUSE_TARGET_PARAMETERS
        target_observed = any(
            update.get("interval_us") == target_interval
            and update.get("latency") == target_latency
            and update.get("supervision_timeout_us") == target_timeout
            for update in window_updates
        )
        disconnected_elapsed_ms = (
            None
            if disconnected_uptime_ms is None
            else (disconnected_uptime_ms - connected_uptime_ms) & 0xFFFFFFFF
        )
        stayed_connected = not (
            disconnected_ns is not None
            and disconnected_attempt_id == connected_attempt_id
            and disconnected_elapsed_ms is not None
            and disconnected_elapsed_ms <= duration_ms
        )
        return {
            "node": node.name,
            "anchor": "firmware_cdc_peripheral_connected_event",
            "connected_host_monotonic_ns": connected_ns,
            "connected_firmware_uptime_ms": connected_uptime_ms,
            "window_duration_s": duration_s,
            "deadline_monotonic_ns": deadline_ns,
            "deadline_firmware_uptime_ms": (connected_uptime_ms + duration_ms)
            & 0xFFFFFFFF,
            "firmware_timebase": "k_uptime_get_32 milliseconds",
            "peripheral_disconnected_host_monotonic_ns": disconnected_ns,
            "peripheral_disconnected_firmware_uptime_ms": disconnected_uptime_ms,
            "peripheral_disconnected_elapsed_ms": disconnected_elapsed_ms,
            "peripheral_connected_for_full_window": stayed_connected,
            "observed_duration_s": max(
                0.0,
                (time.monotonic_ns() - connected_ns) / 1_000_000_000,
            ),
            "updates": window_updates,
            "target_tuple": {
                "interval_us": target_interval,
                "latency": target_latency,
                "supervision_timeout_us": target_timeout,
            },
            "target_observed": target_observed,
        }

    async def _wait_for(self, event: asyncio.Event, name: str) -> None:
        if self.failed_event.is_set():
            raise RuntimeError(f"BLE setup failed before {name}: {self.failure}")
        if event.is_set():
            return
        event_task = asyncio.create_task(event.wait())
        failure_task = asyncio.create_task(self.failed_event.wait())
        done, pending = await asyncio.wait(
            (event_task, failure_task), return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        if self.failed_event.is_set():
            raise RuntimeError(f"BLE setup failed before {name}: {self.failure}")
        if event_task not in done:
            raise RuntimeError(f"BLE setup did not reach {name}")

    async def wait_for_first(self) -> None:
        await self._wait_for(self.first_connected, "first link connection")

    async def wait_for_peripheral_disconnect(
        self, node: NodeId, *, timeout_s: float
    ) -> dict[str, object]:
        if node not in self.required_nodes:
            raise ValueError(f"Node {node.name} is not in this connection gate")
        if timeout_s <= 0.0:
            raise ValueError("peripheral disconnect timeout must be positive")
        with self._peripheral_lock:
            attempts = (
                self.peripheral_connected_attempt_ids.get(node),
                self.successful_connect_attempt_ids.get(node),
            )
            attempt_id = max((item for item in attempts if item is not None), default=None)
        if attempt_id is None:
            result: dict[str, object] = {
                "required": False,
                "observed": False,
                "completed": True,
                "reason": "no successful host connect or firmware connected event was observed",
            }
            self.events.write(
                "peripheral_disconnect_wait_skipped", node=node, **result
            )
            return result

        started_ns = time.monotonic_ns()
        deadline = self.loop.time() + timeout_s
        self.events.write(
            "peripheral_disconnect_wait_start",
            node=node,
            connect_attempt=attempt_id,
            timeout_s=timeout_s,
            host_monotonic_ns=started_ns,
        )
        while True:
            self._peripheral_state_changed.clear()
            with self._peripheral_lock:
                connected_at = self.peripheral_connected_at.get(node)
                connected_attempt_id = self.peripheral_connected_attempt_ids.get(node)
                disconnected_at = self.peripheral_disconnected_at.get(node)
                disconnected_uptime_ms = self.peripheral_disconnected_uptime_ms.get(node)
                observed_attempt_id = self.peripheral_disconnected_attempt_ids.get(node)
                complete = (
                    connected_attempt_id == attempt_id
                    and connected_at is not None
                    and observed_attempt_id == attempt_id
                    and disconnected_at is not None
                    and disconnected_at >= connected_at
                )
            if complete:
                finished_ns = time.monotonic_ns()
                result = {
                    "required": True,
                    "observed": True,
                    "completed": True,
                    "connect_attempt": attempt_id,
                    "host_monotonic_ns": disconnected_at,
                    "firmware_uptime_ms": disconnected_uptime_ms,
                    "elapsed_s": (finished_ns - started_ns) / 1_000_000_000,
                }
                self.events.write(
                    "peripheral_disconnect_wait_complete", node=node, **result
                )
                return result
            remaining = deadline - self.loop.time()
            if remaining <= 0.0:
                elapsed_s = (time.monotonic_ns() - started_ns) / 1_000_000_000
                self.events.write(
                    "peripheral_disconnect_wait_timeout",
                    node=node,
                    connect_attempt=attempt_id,
                    timeout_s=timeout_s,
                    elapsed_s=elapsed_s,
                )
                raise TimeoutError(
                    f"Node {node.name} firmware did not confirm a full connected-to-disconnected "
                    f"event pair for connect attempt {attempt_id} within {timeout_s:.3f}s"
                )
            try:
                await asyncio.wait_for(
                    self._peripheral_state_changed.wait(), timeout=remaining
                )
            except TimeoutError:
                continue

    async def _wait_for_current_peripheral_events(self) -> None:
        deadline = self.loop.time() + self.connection_timeout_s
        while True:
            self._peripheral_state_changed.clear()
            with self._peripheral_lock:
                ready = all(
                    node in self.successful_connect_attempt_ids
                    and self.connect_attempt_ids[node]
                    == self.successful_connect_attempt_ids[node]
                    and self.peripheral_connected_attempt_ids.get(node)
                    == self.successful_connect_attempt_ids[node]
                    and not (
                        self.peripheral_disconnected_attempt_ids.get(node)
                        == self.successful_connect_attempt_ids[node]
                        and self.peripheral_disconnected_at.get(node, 0)
                        >= self.peripheral_connected_at.get(node, 0)
                    )
                    for node in self.required_nodes
                )
            if ready:
                return
            remaining = deadline - self.loop.time()
            if remaining <= 0:
                raise TimeoutError(
                    "firmware connected events did not match the current host connect attempts"
                )
            await asyncio.wait_for(
                self._wait_for(
                    self._peripheral_state_changed,
                    "current firmware peripheral connected events",
                ),
                timeout=remaining,
            )

    async def wait_for_settle(self, duration_s: float) -> None:
        wait_started_ns = time.monotonic_ns()
        while True:
            try:
                await self._wait_for_current_peripheral_events()
            except TimeoutError as error:
                raise RuntimeError(
                    "CDC did not report a peripheral connected event for the current host "
                    f"connect attempt within {self.connection_timeout_s:.1f} seconds"
                ) from error
            with self._peripheral_lock:
                connect_attempts = dict(self.successful_connect_attempt_ids)
                connected_at = dict(self.peripheral_connected_at)
            settle_ns = int(duration_s * 1_000_000_000)
            missing = self.required_nodes - set(connected_at)
            if missing:
                raise RuntimeError(
                    "firmware connected-event timeline missing nodes: "
                    + ", ".join(sorted(node.name for node in missing))
                )
            deadlines = {
                node: connected_at[node] + settle_ns for node in self.required_nodes
            }
            target_ns = max(deadlines.values())
            now_ns = time.monotonic_ns()
            if now_ns < target_ns:
                await asyncio.sleep((target_ns - now_ns) / 1_000_000_000)
            with self._peripheral_lock:
                attempts_settled = (
                    connect_attempts == self.successful_connect_attempt_ids
                    and all(
                        self.connect_attempt_ids.get(node) == connect_attempts.get(node)
                        and self.peripheral_connected_attempt_ids.get(node)
                        == connect_attempts.get(node)
                        and not (
                            self.peripheral_disconnected_attempt_ids.get(node)
                            == connect_attempts.get(node)
                            and self.peripheral_disconnected_at.get(node, 0)
                            >= connected_at.get(node, 0)
                        )
                        for node in self.required_nodes
                    )
                )
            # An event-loop timer may wake before the monotonic deadline.
            if attempts_settled and time.monotonic_ns() >= target_ns:
                break

        finished_ns = time.monotonic_ns()
        parameter_windows = {
            node: self.parameter_window_result(node, duration_s)
            for node in self.required_nodes
        }
        self.events.write(
            "connection_parameter_settle_wait",
            duration_s=duration_s,
            anchor="firmware_cdc_peripheral_connected_event",
            peripheral_connected_host_monotonic_ns={
                node.name: connected_at[node] for node in self.required_nodes
            },
            target_monotonic_ns=target_ns,
            wait_s=(finished_ns - wait_started_ns) / 1_000_000_000,
        )
        self.events.write(
            "connection_parameter_settle_complete",
            planned_duration_s=duration_s,
            anchor="firmware_cdc_peripheral_connected_event",
            observed_duration_s_by_node={
                node.name: (finished_ns - connected_at[node]) / 1_000_000_000
                for node in self.required_nodes
            },
            parameter_updates_by_node={
                node.name: parameter_windows[node]["updates"]
                for node in self.required_nodes
            },
            target_tuple_by_node={
                node.name: parameter_windows[node]["target_tuple"]
                for node in self.required_nodes
            },
            target_observed_by_node={
                node.name: parameter_windows[node]["target_observed"]
                for node in self.required_nodes
            },
            monotonic_ns=finished_ns,
        )


class MatrixBleClient:
    """Experiment-only fresh-device client with separate scan/connect gates."""

    def __init__(
        self,
        *,
        node: NodeId,
        address: str,
        disconnected_callback: Callable[[object], None],
        events: EventLog,
        connection_gate: _MatrixConnectionGate,
        require_pristine_start: bool = False,
        forbidden_boot_ids: frozenset[int] = frozenset(),
    ) -> None:
        self.node = node
        self.address = address
        self.events = events
        self.connection_gate = connection_gate
        self.require_pristine_start = require_pristine_start
        self.forbidden_boot_ids = forbidden_boot_ids
        self._pre_notify_status: Status | None = None
        self._pre_notify_status_error: str | None = None
        self._client: BleClient | None = None
        self._device: object | None = None
        self._connect_attempt_id: int | None = None

        def on_underlying_disconnected(_underlying_client: object) -> None:
            disconnected_callback(self)

        self._disconnected_callback = on_underlying_disconnected

    def _require_client(self) -> BleClient:
        if self._client is None:
            raise RuntimeError("BLE client has no fresh M1 BLEDevice")
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected if self._client is not None else False

    @property
    def mtu_size(self) -> int:
        started_ns = time.perf_counter_ns()
        mtu = self._require_client().mtu_size
        self.events.write(
            "ble_mtu_observed",
            node=self.node,
            address=self.address,
            mtu=mtu,
            duration_ns=time.perf_counter_ns() - started_ns,
            host_monotonic_ns=time.monotonic_ns(),
        )
        return mtu

    async def wait_for_connect_slot(self) -> None:
        if (
            self.connection_gate.first_node is not None
            and self.node is not self.connection_gate.first_node
        ):
            self.events.write(
                "ble_connect_wait",
                node=self.node,
                first_node=self.connection_gate.first_node,
            )
            await self.connection_gate.wait_for_first()

        started_ns = time.perf_counter_ns()
        self.events.write(
            "ble_scan_start",
            node=self.node,
            address=self.address,
            service_uuid=M1_SERVICE_UUID,
            timeout_s=ROOT_CAUSE_SCAN_TIMEOUT_S,
            cleanup_grace_s=M1_SCAN_CLEANUP_GRACE_S,
            watchdog_s=ROOT_CAUSE_SCAN_TIMEOUT_S + M1_SCAN_CLEANUP_GRACE_S,
            host_monotonic_ns=time.monotonic_ns(),
        )
        try:
            self._device = await discover_m1_ble_device(
                self.address, timeout_s=ROOT_CAUSE_SCAN_TIMEOUT_S
            )
        except Exception as error:
            duration_ns = time.perf_counter_ns() - started_ns
            self.events.write(
                "ble_scan_failure",
                node=self.node,
                address=self.address,
                duration_ns=duration_ns,
                scan_timeout_s=ROOT_CAUSE_SCAN_TIMEOUT_S,
                cleanup_grace_s=M1_SCAN_CLEANUP_GRACE_S,
                watchdog_s=ROOT_CAUSE_SCAN_TIMEOUT_S + M1_SCAN_CLEANUP_GRACE_S,
                error=f"{type(error).__name__}: {error}",
                host_monotonic_ns=time.monotonic_ns(),
            )
            self.connection_gate.note_failure(self.node, error)
            raise
        duration_ns = time.perf_counter_ns() - started_ns
        observed_address = str(getattr(self._device, "address", ""))
        if observed_address.casefold() != self.address.casefold():
            error = RuntimeError(
                f"fresh M1 scan returned {observed_address}, expected {self.address}"
            )
            self.events.write(
                "ble_scan_identity_failure",
                node=self.node,
                address=self.address,
                observed_address=observed_address,
                duration_ns=duration_ns,
            )
            self.connection_gate.note_failure(self.node, error)
            raise error
        self.events.write(
            "ble_scan_complete",
            node=self.node,
            address=self.address,
            observed_address=observed_address,
            name=getattr(self._device, "name", None),
            duration_ns=duration_ns,
            host_monotonic_ns=time.monotonic_ns(),
        )

        def operation_timing_sink(event: str, **details: object) -> None:
            self.events.write(
                event,
                node=self.node,
                address=self.address,
                **details,
            )

        self._client = create_bleak_client(
            self._device,
            self._disconnected_callback,
            services=[M1_SERVICE_UUID],
            operation_timing_sink=operation_timing_sink,
        )

    async def connect(self) -> None:
        client = self._require_client()
        attempt_id = self.connection_gate.note_connect_attempt(self.node)
        self._connect_attempt_id = attempt_id
        self.events.write(
            "ble_os_connect_start",
            node=self.node,
            address=self.address,
            connect_attempt=attempt_id,
            host_monotonic_ns=time.monotonic_ns(),
        )
        try:
            await client.connect()
        except asyncio.CancelledError:
            self.events.write(
                "ble_os_connect_cancelled",
                node=self.node,
                address=self.address,
                connect_attempt=attempt_id,
                host_monotonic_ns=time.monotonic_ns(),
            )
            self.connection_gate.note_failure(
                self.node, TimeoutError("BLE OS connect/GATT setup was cancelled")
            )
            raise
        except Exception as error:
            self.events.write(
                "ble_os_connect_failure",
                node=self.node,
                address=self.address,
                connect_attempt=attempt_id,
                error=f"{type(error).__name__}: {error}",
                host_monotonic_ns=time.monotonic_ns(),
            )
            self.connection_gate.note_failure(self.node, error)
            raise
        self.events.write(
            "ble_os_connect_return",
            node=self.node,
            address=self.address,
            connect_attempt=attempt_id,
            host_monotonic_ns=time.monotonic_ns(),
        )
        self.connection_gate.note_connected(self.node, attempt_id)

    async def disconnect(self) -> None:
        if self._client is None:
            return
        for attempt in (1, 2):
            started_ns = time.perf_counter_ns()
            self.events.write(
                "ble_disconnect_call",
                node=self.node,
                address=self.address,
                attempt=attempt,
                timeout_s=ROOT_CAUSE_DISCONNECT_TIMEOUT_S,
            )
            try:
                await asyncio.wait_for(
                    self._client.disconnect(),
                    timeout=ROOT_CAUSE_DISCONNECT_TIMEOUT_S,
                )
            except asyncio.CancelledError:
                self.events.write(
                    "ble_disconnect_cancelled",
                    node=self.node,
                    address=self.address,
                    attempt=attempt,
                    duration_ns=time.perf_counter_ns() - started_ns,
                )
                raise
            except Exception as error:
                event = (
                    "ble_disconnect_timeout"
                    if isinstance(error, TimeoutError)
                    else "ble_disconnect_failure"
                )
                self.events.write(
                    event,
                    node=self.node,
                    address=self.address,
                    attempt=attempt,
                    duration_ns=time.perf_counter_ns() - started_ns,
                    error=f"{type(error).__name__}: {error}",
                )
                if attempt == 2:
                    raise
            else:
                self.events.write(
                    "ble_disconnect_complete",
                    node=self.node,
                    address=self.address,
                    attempt=attempt,
                    duration_ns=time.perf_counter_ns() - started_ns,
                    host_monotonic_ns=time.monotonic_ns(),
                )
                return

    async def read_gatt_char(self, char_specifier: str) -> bytes | bytearray:
        started_ns = time.perf_counter_ns()
        try:
            value = await self._require_client().read_gatt_char(char_specifier)
        except Exception as error:
            self.events.write(
                "ble_gatt_read_failure",
                node=self.node,
                address=self.address,
                char_uuid=char_specifier,
                phase={
                    IDENTITY_CONFIG_UUID: "identity",
                    STATUS_UUID: "status",
                    CLOCK_EXCHANGE_UUID: "clock_exchange",
                }.get(char_specifier, "other"),
                duration_ns=time.perf_counter_ns() - started_ns,
                error=f"{type(error).__name__}: {error}",
            )
            raise
        self.events.write(
            "ble_gatt_read_complete",
            node=self.node,
            address=self.address,
            char_uuid=char_specifier,
            phase={
                IDENTITY_CONFIG_UUID: "identity",
                STATUS_UUID: "status",
                CLOCK_EXCHANGE_UUID: "clock_exchange",
            }.get(char_specifier, "other"),
            duration_ns=time.perf_counter_ns() - started_ns,
            host_monotonic_ns=time.monotonic_ns(),
        )
        if self.require_pristine_start and char_specifier == STATUS_UUID:
            try:
                self._pre_notify_status = decode_status(bytes(value))
                self._pre_notify_status_error = None
            except Exception as error:
                self._pre_notify_status = None
                self._pre_notify_status_error = f"{type(error).__name__}: {error}"
        return value

    async def write_gatt_char(
        self,
        char_specifier: str,
        data: bytes,
        *,
        response: bool | None = None,
    ) -> None:
        started_ns = time.perf_counter_ns()
        try:
            await self._require_client().write_gatt_char(
                char_specifier, data, response=response
            )
        except Exception as error:
            self.events.write(
                "ble_gatt_write_failure",
                node=self.node,
                address=self.address,
                char_uuid=char_specifier,
                duration_ns=time.perf_counter_ns() - started_ns,
                error=f"{type(error).__name__}: {error}",
            )
            raise
        self.events.write(
            "ble_gatt_write_complete",
            node=self.node,
            address=self.address,
            char_uuid=char_specifier,
            phase={
                IDENTITY_CONFIG_UUID: "identity",
                STATUS_UUID: "status",
                CLOCK_EXCHANGE_UUID: "clock_exchange",
            }.get(char_specifier, "other"),
            duration_ns=time.perf_counter_ns() - started_ns,
            host_monotonic_ns=time.monotonic_ns(),
        )

    async def start_notify(
        self,
        char_specifier: str,
        callback: Callable[[object, bytearray], None],
    ) -> None:
        if char_specifier == TELEMETRY_UUID:
            if self.require_pristine_start:
                status = self._pre_notify_status
                errors = _pristine_start_status_errors(
                    status,
                    self.node,
                    forbidden_boot_ids=self.forbidden_boot_ids,
                )
                if self._pre_notify_status_error is not None:
                    errors.insert(0, f"status decode failed: {self._pre_notify_status_error}")
                status_summary = None
                if status is not None:
                    status_summary = {
                        "node_id": int(status.node_id),
                        "acquisition_state": status.acquisition_state.name.lower(),
                        "boot_id": status.boot_id,
                        "last_sample_sequence": status.last_sample_sequence,
                        "last_packet_sequence": status.last_packet_sequence,
                        "samples_acquired": status.samples_acquired,
                        "packets_generated": status.packets_generated,
                        "sensor_fifo_overruns": status.sensor_fifo_overruns,
                        "firmware_queue_overruns": status.firmware_queue_overruns,
                        "transport_backpressure_events": status.transport_backpressure_events,
                        "samples_dropped_before_packetization": (
                            status.samples_dropped_before_packetization
                        ),
                        "acquisition_buffer_high_water_samples": (
                            status.acquisition_buffer_high_water_samples
                        ),
                        "transport_queue_high_water_packets": (
                            status.transport_queue_high_water_packets
                        ),
                    }
                self.events.write(
                    "pre_notify_status_gate",
                    node=self.node,
                    address=self.address,
                    passed=not errors,
                    status=status_summary,
                    errors=errors,
                    host_monotonic_ns=time.monotonic_ns(),
                )
                if errors:
                    raise CdcControlGateError(
                        "pre-notify status is not a pristine armed state: "
                        + "; ".join(errors)
                    )
            await self.connection_gate.wait_for_settle(ROOT_CAUSE_SETUP_SETTLE_S)
        started_ns = time.perf_counter_ns()
        await self._require_client().start_notify(char_specifier, callback)
        self.events.write(
            "ble_gatt_notify_setup_complete",
            node=self.node,
            address=self.address,
            char_uuid=char_specifier,
            phase={
                IDENTITY_CONFIG_UUID: "identity",
                STATUS_UUID: "status",
                CLOCK_EXCHANGE_UUID: "clock_exchange",
                TELEMETRY_UUID: "telemetry",
            }.get(char_specifier, "other"),
            duration_ns=time.perf_counter_ns() - started_ns,
            host_monotonic_ns=time.monotonic_ns(),
        )
        if char_specifier == TELEMETRY_UUID:
            self.events.write("telemetry_notify_enabled", node=self.node, address=self.address)

    async def stop_notify(self, char_specifier: str) -> None:
        await self._require_client().stop_notify(char_specifier)


def _pristine_start_status_errors(
    status: Status | None,
    node: NodeId,
    *,
    forbidden_boot_ids: frozenset[int] = frozenset(),
) -> list[str]:
    """Check experiment-only cold-start criteria before telemetry CCC enable."""

    if status is None:
        return ["pre-notify status read is unavailable"]
    errors: list[str] = []
    if status.node_id is not node:
        errors.append(f"status node ID {status.node_id.name} differs from {node.name}")
    if status.boot_id in forbidden_boot_ids:
        errors.append(f"boot ID was already used ({status.boot_id})")
    if status.acquisition_state is not AcquisitionState.ARMED:
        errors.append(
            "acquisition_state is not pristine armed "
            f"({status.acquisition_state.name.lower()})"
        )
    zero_fields = (
        "samples_acquired",
        "packets_generated",
        "sensor_fifo_overruns",
        "firmware_queue_overruns",
        "transport_backpressure_events",
        "samples_dropped_before_packetization",
        "acquisition_buffer_high_water_samples",
        "transport_queue_high_water_packets",
    )
    for field in zero_fields:
        value = getattr(status, field)
        if value != 0:
            errors.append(f"{field} is {value}, expected zero")
    for field in ("last_sample_sequence", "last_packet_sequence"):
        value = getattr(status, field)
        if value != 0xFFFFFFFF:
            errors.append(f"{field} is not the never-produced sentinel ({value})")
    return errors


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


class _SerialOperation:
    def __init__(
        self,
        kind: str,
        mode: str | None = None,
        command: bytes | None = None,
        timeout_s: float = 2.0,
    ) -> None:
        self.kind = kind
        self.mode = mode
        self.command = command
        self.deadline_monotonic = time.monotonic() + timeout_s
        self.cancelled = False
        self.started = False
        self._state_lock = threading.Lock()
        self.completed = threading.Event()
        self.result: dict[str, object] | None = None

    def claim_before_deadline(self) -> bool:
        with self._state_lock:
            if self.cancelled or time.monotonic() > self.deadline_monotonic:
                self.cancelled = True
                return False
            self.started = True
            return True

    def cancel_if_not_started(self) -> None:
        with self._state_lock:
            if not self.started:
                self.cancelled = True


class _PendingControlRequest:
    def __init__(self, mode: str, deadline_monotonic: float) -> None:
        self.mode = mode
        self.deadline_monotonic = deadline_monotonic
        self.completed = threading.Event()
        self.result: dict[str, object] | None = None


class ConnParamControlClient:
    """Bind every CDC transaction to a fresh, nonce-identified firmware session."""

    _READY = re.compile(
        r"READY node_id=(?P<node_id>[12]) session=(?P<session>[0-9a-f]{16})"
    )
    _REPLY = re.compile(
        r"(?P<kind>ACK|ERR) node_id=(?P<node_id>[12]) "
        r"session=(?P<session>[0-9a-f]{16}) tx=(?P<tx>[0-9]+) "
        r"requested=(?P<requested>OFF|ON) selected=(?P<selected>OFF|ON) "
        r"rc=(?P<rc>-?[0-9]+)"
    )
    _MAX_TRANSACTION_ID = (1 << 32) - 1

    def __init__(
        self,
        *,
        node_id: int,
        write: Callable[..., int],
        event_sink: Callable[..., None],
        session_nonce: str | None = None,
        slow_write_threshold_s: float = 0.02,
    ) -> None:
        if node_id not in {1, 2}:
            raise ValueError(f"unsupported control node ID: {node_id}")
        if slow_write_threshold_s < 0:
            raise ValueError("slow-write threshold must be non-negative")
        nonce = secrets.token_hex(8) if session_nonce is None else session_nonce
        if re.fullmatch(r"[0-9a-f]{16}", nonce) is None:
            raise ValueError("CDC session nonce must be 16 lowercase hexadecimal characters")
        self.node_id = node_id
        self.session_nonce = nonce
        self._write = write
        self._event_sink = event_sink
        self._slow_write_threshold_s = slow_write_threshold_s
        self._ready = threading.Event()
        self._ready_result: dict[str, object] | None = None
        self._hello_attempted = False
        self._ready_deadline_monotonic: float | None = None
        self._ready_received_monotonic: float | None = None
        self._session_ready = False
        self._poisoned = False
        self._poison_reason: str | None = None
        self._lock = threading.Lock()
        self._next_tx = 1
        self._pending: dict[int, _PendingControlRequest] = {}

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    @property
    def poisoned(self) -> bool:
        with self._lock:
            return self._poisoned

    def _failed_result(self, error: str, *, tx: int | None = None) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "session": self.session_nonce,
            "tx": tx,
            "requested": None,
            "selected": None,
            "rc": None,
            "acknowledged": False,
            "applied": False,
            "error": error,
        }

    def _poison_locked(self, reason: str) -> None:
        if self._poisoned:
            return
        self._poisoned = True
        self._poison_reason = reason
        self._session_ready = False
        for tx, pending in tuple(self._pending.items()):
            if pending.result is None:
                pending.result = self._failed_result(
                    f"CDC session poisoned: {reason}", tx=tx
                )
            pending.completed.set()
        self._pending.clear()
        if not self._ready.is_set():
            self._ready_result = {
                "node_id": self.node_id,
                "session": self.session_nonce,
                "ready": False,
                "error": reason,
            }
            self._ready.set()

    def begin_session(self, *, timeout_s: float = 5.0) -> dict[str, object]:
        if timeout_s < 0:
            raise ValueError("READY timeout must be non-negative")
        deadline_monotonic = time.monotonic() + timeout_s
        with self._lock:
            if self._hello_attempted:
                reason = self._poison_reason or "HELLO was already attempted"
                return {
                    "node_id": self.node_id,
                    "session": self.session_nonce,
                    "ready": self._session_ready and not self._poisoned,
                    "error": None if self._session_ready else reason,
                }
            self._hello_attempted = True
            self._ready_deadline_monotonic = deadline_monotonic

        command = f"HELLO session={self.session_nonce}\n".encode("ascii")
        started_ns = time.perf_counter_ns()
        try:
            byte_count = self._write(
                command,
                timeout_s=max(0.0, deadline_monotonic - time.monotonic()),
            )
            write_error = (
                None
                if byte_count == len(command)
                else f"partial CDC HELLO write: {byte_count}/{len(command)}"
            )
        except Exception as error:
            byte_count = None
            write_error = f"{type(error).__name__}: {error}"
        duration_ns = time.perf_counter_ns() - started_ns
        self._event_sink(
            "conn_param_control_hello_write",
            node_id=self.node_id,
            session=self.session_nonce,
            command=command.decode("ascii").rstrip("\n"),
            byte_count=byte_count,
            expected_byte_count=len(command),
            duration_ns=duration_ns,
        )
        if write_error is not None:
            with self._lock:
                self._poison_locked(write_error)
                self._ready_result = {
                    "node_id": self.node_id,
                    "session": self.session_nonce,
                    "ready": False,
                    "error": write_error,
                }
                self._ready.set()
            self._event_sink(
                "conn_param_control_hello_write_failure",
                node_id=self.node_id,
                session=self.session_nonce,
                detail=write_error,
            )
            return dict(self._ready_result or self._failed_result(write_error))

        remaining_timeout_s = max(0.0, deadline_monotonic - time.monotonic())
        if not self._ready.wait(remaining_timeout_s):
            with self._lock:
                ready_before_deadline = (
                    self._session_ready
                    and not self._poisoned
                    and self._ready_received_monotonic is not None
                    and self._ready_received_monotonic <= deadline_monotonic
                )
                if ready_before_deadline:
                    result = dict(
                        self._ready_result
                        or self._failed_result("READY missing result")
                    )
                else:
                    self._poison_locked("READY timeout")
                    result = dict(
                        self._ready_result or self._failed_result("READY timeout")
                    )
            if ready_before_deadline:
                return result
            self._event_sink(
                "conn_param_control_ready_timeout",
                node_id=self.node_id,
                session=self.session_nonce,
                timeout_s=timeout_s,
            )
            return result

        with self._lock:
            return dict(self._ready_result or self._failed_result("READY missing result"))

    def wait_ready(self, timeout_s: float) -> bool:
        if not self._ready.wait(timeout_s):
            return False
        with self._lock:
            return self._session_ready and not self._poisoned

    def _fail_for_bad_line(self, event: str, message: str, **details: object) -> None:
        with self._lock:
            self._poison_locked(message)
        self._event_sink(
            event,
            node_id=self.node_id,
            session=self.session_nonce,
            detail=message,
            **details,
        )

    def handle_line(self, line: str) -> None:
        ready_match = self._READY.fullmatch(line)
        if ready_match is not None:
            observed_node_id = int(ready_match.group("node_id"))
            observed_session = ready_match.group("session")
            received_monotonic = time.monotonic()
            with self._lock:
                if not self._hello_attempted:
                    event = "conn_param_control_unrequested_ready"
                elif self._poisoned:
                    event = "conn_param_control_stale_ready"
                elif (
                    self._ready_deadline_monotonic is None
                    or received_monotonic > self._ready_deadline_monotonic
                ):
                    event = "conn_param_control_late_ready"
                    self._poison_locked("READY arrived after the session deadline")
                elif observed_node_id != self.node_id:
                    event = "conn_param_control_wrong_node_ready"
                    self._poison_locked(
                        f"READY node {observed_node_id}, expected node {self.node_id}"
                    )
                elif observed_session != self.session_nonce:
                    event = "conn_param_control_wrong_session_ready"
                    self._poison_locked(
                        "READY session nonce does not match the current HELLO"
                    )
                else:
                    self._session_ready = True
                    self._ready_received_monotonic = received_monotonic
                    self._ready_result = {
                        "node_id": self.node_id,
                        "session": self.session_nonce,
                        "ready": True,
                        "error": None,
                    }
                    self._ready.set()
                    event = "conn_param_control_ready"
            self._event_sink(
                event,
                node_id=self.node_id,
                observed_node_id=observed_node_id,
                session=self.session_nonce,
                observed_session=observed_session,
                line=line,
            )
            return

        reply_match = self._REPLY.fullmatch(line)
        if reply_match is None:
            if line.startswith(("ACK ", "ERR ")):
                self._fail_for_bad_line(
                    "conn_param_request_malformed_reply",
                    "malformed CDC ACK/ERR line",
                    line=line,
                )
            elif line.startswith("ERROR "):
                self._fail_for_bad_line(
                    "conn_param_control_firmware_error",
                    "firmware reported a CDC control parse/overflow error",
                    line=line,
                )
            return

        kind = reply_match.group("kind")
        observed_node_id = int(reply_match.group("node_id"))
        observed_session = reply_match.group("session")
        tx = int(reply_match.group("tx"))
        requested = reply_match.group("requested")
        selected = reply_match.group("selected")
        rc = int(reply_match.group("rc"))
        details = {
            "node_id": observed_node_id,
            "session": observed_session,
            "tx": tx,
            "requested": requested,
            "selected": selected,
            "rc": rc,
            "line": line,
        }
        event: str
        matched_pending: _PendingControlRequest | None = None
        result: dict[str, object] | None = None
        failure_reason: str | None = None
        with self._lock:
            pending = self._pending.get(tx)
            if self._poisoned:
                event = (
                    "conn_param_request_late_ack"
                    if tx < self._next_tx
                    else "conn_param_request_stale_ack"
                )
                failure_reason = self._poison_reason or "CDC session is poisoned"
            elif not self._session_ready:
                event = "conn_param_request_unexpected_ack"
                failure_reason = "ACK arrived before session READY"
            elif observed_node_id != self.node_id:
                event = "conn_param_request_wrong_node_ack"
                failure_reason = (
                    f"ACK node {observed_node_id}, expected node {self.node_id}"
                )
            elif observed_session != self.session_nonce:
                event = "conn_param_request_wrong_session_ack"
                failure_reason = "ACK session nonce does not match current session"
            elif pending is None:
                if tx < self._next_tx:
                    event = "conn_param_request_late_ack"
                    failure_reason = f"late or duplicate ACK for tx={tx}"
                else:
                    event = "conn_param_request_wrong_tx_ack"
                    failure_reason = f"ACK tx={tx} does not match a pending transaction"
            elif time.monotonic() > pending.deadline_monotonic:
                event = "conn_param_request_late_ack"
                failure_reason = f"ACK arrived after the deadline for tx={tx}"
                result = self._failed_result(
                    "ACK arrived after transaction deadline", tx=tx
                )
                self._pending.pop(tx, None)
                pending.result = result
                pending.completed.set()
            else:
                matched_pending = pending
                applied = (
                    kind == "ACK"
                    and requested == pending.mode
                    and selected == pending.mode
                    and rc == 0
                )
                if kind == "ERR":
                    error = f"firmware rejected request with rc={rc}"
                elif requested != pending.mode:
                    error = f"ACK requested {requested}, expected {pending.mode}"
                elif rc != 0:
                    error = f"firmware rejected mode with rc={rc}"
                elif selected != pending.mode:
                    error = f"firmware selected {selected}, expected {pending.mode}"
                else:
                    error = None
                result = {
                    "node_id": self.node_id,
                    "session": self.session_nonce,
                    "tx": tx,
                    "requested": requested,
                    "selected": selected,
                    "rc": rc,
                    "acknowledged": True,
                    "applied": applied,
                    "error": error,
                }
                self._pending.pop(tx, None)
                pending.result = result
                pending.completed.set()
                event = (
                    "conn_param_request_ack"
                    if kind == "ACK"
                    else "conn_param_request_error"
                )
                if not applied:
                    failure_reason = error or "firmware rejected request"
            if failure_reason is not None:
                self._poison_locked(failure_reason)

        self._event_sink(event, **details)
        if failure_reason is not None:
            self._event_sink(
                "conn_param_control_session_poisoned",
                node_id=self.node_id,
                session=self.session_nonce,
                reason=failure_reason,
            )
        if matched_pending is not None and result is not None:
            return

    def request(self, mode: str, *, timeout_s: float = 5.0) -> dict[str, object]:
        if mode not in {"OFF", "ON"}:
            raise ValueError(f"unsupported connection-parameter request mode: {mode}")
        if timeout_s < 0:
            raise ValueError("ACK timeout must be non-negative")
        deadline_monotonic = time.monotonic() + timeout_s

        with self._lock:
            if self._poisoned:
                return self._failed_result(
                    f"CDC session is poisoned: {self._poison_reason}"
                )
            if not self._session_ready:
                return self._failed_result("CDC session is not READY")
            if self._next_tx > self._MAX_TRANSACTION_ID:
                self._poison_locked("CDC transaction ID space is exhausted")
                return self._failed_result(
                    "CDC control transaction ID space is exhausted"
                )
            tx = self._next_tx
            self._next_tx += 1
            pending = _PendingControlRequest(mode, deadline_monotonic)
            self._pending[tx] = pending

        command = (
            f"SET session={self.session_nonce} tx={tx} mode={mode}\n".encode("ascii")
        )
        started_ns = time.perf_counter_ns()
        write_error: str | None = None
        byte_count: int | None = None
        try:
            byte_count = self._write(
                command,
                timeout_s=max(0.0, deadline_monotonic - time.monotonic()),
            )
            if byte_count != len(command):
                write_error = f"partial CDC control write: {byte_count}/{len(command)}"
        except Exception as error:
            write_error = f"{type(error).__name__}: {error}"
        duration_ns = time.perf_counter_ns() - started_ns
        write_details = {
            "node_id": self.node_id,
            "session": self.session_nonce,
            "tx": tx,
            "requested": mode,
            "command": command.decode("ascii").rstrip("\n"),
            "byte_count": byte_count,
            "expected_byte_count": len(command),
            "duration_ns": duration_ns,
            "delayed": duration_ns >= int(self._slow_write_threshold_s * 1e9),
        }

        if write_error is not None:
            with self._lock:
                self._pending.pop(tx, None)
                pending.result = self._failed_result(write_error, tx=tx)
                result = pending.result
                pending.completed.set()
                self._poison_locked(write_error)
            self._event_sink(
                "conn_param_request_write_failure",
                **write_details,
                detail=write_error,
            )
            self._event_sink(
                "conn_param_control_session_poisoned",
                node_id=self.node_id,
                session=self.session_nonce,
                reason=write_error,
            )
            return result

        self._event_sink("conn_param_request_write", **write_details)
        remaining_timeout_s = max(0.0, deadline_monotonic - time.monotonic())
        if not pending.completed.wait(remaining_timeout_s):
            timed_out = False
            with self._lock:
                if pending.result is None:
                    self._pending.pop(tx, None)
                    pending.result = self._failed_result("ACK timeout", tx=tx)
                    pending.completed.set()
                    self._poison_locked(f"ACK timeout for tx={tx}")
                    timed_out = True
                result = pending.result or self._failed_result("ACK timeout", tx=tx)
            if timed_out:
                self._event_sink(
                    "conn_param_request_ack_timeout",
                    node_id=self.node_id,
                    session=self.session_nonce,
                    tx=tx,
                    requested=mode,
                    timeout_s=timeout_s,
                )
                self._event_sink(
                    "conn_param_control_session_poisoned",
                    node_id=self.node_id,
                    session=self.session_nonce,
                    reason=f"ACK timeout for tx={tx}",
                )
            return result

        with self._lock:
            return pending.result or self._failed_result(
                "ACK event completed without a result", tx=tx
            )

class CdcControlGateError(RuntimeError):
    """Raised when a control or CDC capture gate fails before BLE starts."""

    def __init__(
        self,
        message: str,
        *,
        control_results: dict[NodeId, dict[str, object]] | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.control_results = control_results or {}
        self.context = context or {}


class _MatrixCdcCapture:
    """Keep one serial handle open for the matrix and retain exact CDC bytes."""

    def __init__(
        self,
        *,
        node: NodeId,
        port_info: dict[str, object],
        output_dir: Path,
        events: EventLog,
    ) -> None:
        self.node = node
        self.port_info = port_info
        self.events = events
        self._control_lock = threading.Lock()
        self.control = ConnParamControlClient(
            node_id=int(node),
            write=self._write_control_command,
            event_sink=self._write_control_event,
        )
        self.label = f"node-{node.name.lower()}"
        self.bin_path = output_dir / f"{self.label}.cdc.bin"
        self.log_path = output_dir / f"{self.label}.cdc.log"
        self.error: str | None = None
        self.ready = threading.Event()
        self.done = threading.Event()
        self._stop = threading.Event()
        self._operations: queue.Queue[_SerialOperation] = queue.Queue()
        self._line_buffer = bytearray()
        self._event_listeners: set[
            Callable[[NodeId, str, int, str], None]
        ] = set()
        self._event_listeners_lock = threading.Lock()
        self.thread = threading.Thread(
            target=self._run, name=f"matrix-cdc-{self.label}", daemon=True
        )

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self) -> None:
        self.thread.join(timeout=10.0)
        if self.thread.is_alive() and self.error is None:
            self.error = "CDC capture thread did not stop within 10 seconds"

    def wait_control_ready(self, timeout_s: float) -> bool:
        return self.begin_control_session(timeout_s).get("ready") is True

    def begin_control_session(self, timeout_s: float) -> dict[str, object]:
        with self._control_lock:
            control = self.control
        return control.begin_session(timeout_s=timeout_s)

    def begin_fresh_control_session(self, timeout_s: float) -> dict[str, object]:
        """Replace a poisoned or uncertain session with a new nonce-bound one."""

        control = ConnParamControlClient(
            node_id=int(self.node),
            write=self._write_control_command,
            event_sink=self._write_control_event,
        )
        with self._control_lock:
            self.control = control
        return control.begin_session(timeout_s=timeout_s)

    def add_event_listener(
        self, listener: Callable[[NodeId, str, int, str], None]
    ) -> None:
        with self._event_listeners_lock:
            self._event_listeners.add(listener)

    def remove_event_listener(
        self, listener: Callable[[NodeId, str, int, str], None]
    ) -> None:
        with self._event_listeners_lock:
            self._event_listeners.discard(listener)

    def set_mode(self, mode: str, *, timeout_s: float = 5.0) -> dict[str, object]:
        with self._control_lock:
            control = self.control
        return control.request(mode, timeout_s=timeout_s)

    def _write_control_event(self, event: str, **details: object) -> None:
        self.events.write(event, node=self.node, **details)

    def _write_control_command(
        self, command: bytes, *, timeout_s: float = 2.0
    ) -> int:
        if self.done.is_set():
            raise OSError(self.error or f"{self.label} CDC capture is not running")
        operation = _SerialOperation(
            "control_write", command=command, timeout_s=timeout_s
        )
        self._operations.put(operation)
        if not operation.completed.wait(timeout_s):
            operation.cancel_if_not_started()
            raise TimeoutError(
                f"timed out dispatching a CDC write to {self.label} "
                f"within {timeout_s:.3f} seconds"
            )
        result = operation.result or {}
        if "written" not in result:
            raise OSError(str(result.get("error", "serial write returned no result")))
        return int(result["written"])

    def cut(self, *, timeout_s: float = 2.0) -> int:
        operation = _SerialOperation("cut")
        self._operations.put(operation)
        if not operation.completed.wait(timeout_s):
            raise TimeoutError(f"timed out marking {self.label} CDC capture boundary")
        result = operation.result or {}
        if "offset" not in result:
            raise RuntimeError(str(result.get("error", "CDC capture boundary failed")))
        return int(result["offset"])

    def copy_segment(self, start: int, end: int, output_dir: Path) -> dict[str, object]:
        if end < start:
            raise ValueError(f"invalid CDC segment {self.label}: {start}..{end}")
        binary_path = output_dir / f"{self.label}.cdc.bin"
        log_path = output_dir / f"{self.label}.cdc.log"
        data = b""
        if self.bin_path.is_file():
            with self.bin_path.open("rb") as source:
                source.seek(start)
                data = source.read(end - start)
        binary_path.write_bytes(data)
        log_path.write_text(data.decode("utf-8", errors="replace"), encoding="utf-8")
        return {
            "port": self.port_info.get("device"),
            "usb_serial": self.port_info.get("serial_number"),
            "raw_path": binary_path.name,
            "raw_sha256": _sha256(binary_path),
            "raw_bytes": len(data),
            "decoded_log_path": log_path.name,
            "decoded_log_sha256": _sha256(log_path),
            "root_capture_start_offset": start,
            "root_capture_end_offset": end,
            "error": self.error,
        }

    def finalize_text_log(self) -> None:
        if not self.bin_path.exists():
            self.bin_path.touch(exist_ok=True)
        data = self.bin_path.read_bytes()
        with self.log_path.open("x", encoding="utf-8") as stream:
            stream.write(data.decode("utf-8", errors="replace"))

    def metadata(self) -> dict[str, object]:
        return {
            "port": self.port_info.get("device"),
            "usb_serial": self.port_info.get("serial_number"),
            "vid": self.port_info.get("vid"),
            "pid": self.port_info.get("pid"),
            "hwid": self.port_info.get("hwid"),
            "label": self.label,
            "raw_path": self.bin_path.name,
            "raw_sha256": _sha256(self.bin_path) if self.bin_path.exists() else None,
            "raw_bytes": self.bin_path.stat().st_size if self.bin_path.exists() else None,
            "decoded_log_path": self.log_path.name if self.log_path.exists() else None,
            "decoded_log_sha256": _sha256(self.log_path) if self.log_path.exists() else None,
            "error": self.error,
        }

    def _consume(self, raw: object, connection_data: bytes) -> None:
        raw.write(connection_data)  # type: ignore[attr-defined]
        raw.flush()  # type: ignore[attr-defined]
        self._line_buffer.extend(connection_data)
        while b"\n" in self._line_buffer:
            line, _, remainder = self._line_buffer.partition(b"\n")
            self._line_buffer = bytearray(remainder)
            self._handle_line(line.decode("utf-8", errors="replace").rstrip("\r"))
        if len(self._line_buffer) > 8192:
            self._line_buffer.clear()
            self.events.write("cdc_line_buffer_cleared", node=self.node)

    def _handle_line(self, line: str) -> None:
        with self._control_lock:
            self.control.handle_line(line)
        match = re.match(
            r"^Node ([AB]): BLE link event=(connected|disconnected|param_updated)\b",
            line,
        )
        if match is None:
            return
        observed_node = NodeId[match.group(1)]
        event_name = match.group(2)
        captured_monotonic_ns = time.monotonic_ns()
        self.events.write(
            "cdc_firmware_ble_event",
            node=self.node,
            observed_node=observed_node,
            firmware_event=event_name,
            capture_monotonic_ns=captured_monotonic_ns,
            line=line,
        )
        with self._event_listeners_lock:
            listeners = tuple(self._event_listeners)
        for listener in listeners:
            try:
                listener(self.node, event_name, captured_monotonic_ns, line)
            except Exception as error:
                self.events.write(
                    "cdc_firmware_event_listener_error",
                    node=self.node,
                    firmware_event=event_name,
                    detail=f"{type(error).__name__}: {error}",
                )

    def _drain_available(self, connection: object, raw: object) -> None:
        while True:
            available = int(connection.in_waiting)  # type: ignore[attr-defined]
            if available <= 0:
                return
            self._consume(raw, connection.read(available))  # type: ignore[attr-defined]

    def _process_operations(self, connection: object, raw: object) -> None:
        while True:
            try:
                operation = self._operations.get_nowait()
            except queue.Empty:
                return
            if operation.kind == "control_write":
                assert operation.command is not None
                if not operation.claim_before_deadline():
                    operation.result = {
                        "error": "CDC control write expired before serial dispatch"
                    }
                    operation.completed.set()
                    continue
                remaining_s = max(
                    0.0, operation.deadline_monotonic - time.monotonic()
                )
                previous_write_timeout = connection.write_timeout  # type: ignore[attr-defined]
                try:
                    connection.write_timeout = min(  # type: ignore[attr-defined]
                        float(previous_write_timeout), remaining_s
                    )
                    written = connection.write(operation.command)  # type: ignore[attr-defined]
                    connection.flush()  # type: ignore[attr-defined]
                    if time.monotonic() > operation.deadline_monotonic:
                        operation.result = {
                            "error": "CDC control write exceeded its deadline"
                        }
                    else:
                        operation.result = {"written": written}
                except Exception as error:
                    operation.result = {
                        "error": f"{type(error).__name__}: {error}"
                    }
                finally:
                    connection.write_timeout = previous_write_timeout  # type: ignore[attr-defined]
                operation.completed.set()
            elif operation.kind == "cut":
                try:
                    self._drain_available(connection, raw)
                    raw.flush()  # type: ignore[attr-defined]
                    operation.result = {"offset": int(raw.tell())}  # type: ignore[attr-defined]
                except Exception as error:
                    operation.result = {"error": f"{type(error).__name__}: {error}"}
                operation.completed.set()
            else:
                operation.result = {"error": f"unsupported serial operation: {operation.kind}"}
                operation.completed.set()

    def _run(self) -> None:
        try:
            import serial  # type: ignore[import-untyped]

            port = str(self.port_info["device"])
            with self.bin_path.open("xb") as raw:
                with serial.Serial(
                    port,
                    baudrate=115200,
                    timeout=0.1,
                    write_timeout=1.0,
                ) as connection:
                    connection.dtr = True
                    connection.rts = True
                    self.events.write(
                        "cdc_open",
                        node=self.node,
                        port=port,
                        usb_serial=self.port_info.get("serial_number"),
                    )
                    self.ready.set()
                    while not self._stop.is_set():
                        self._process_operations(connection, raw)
                        chunk = connection.read(connection.in_waiting or 1)
                        if chunk:
                            self._consume(raw, chunk)
                    self._drain_available(connection, raw)
                    raw.flush()
        except Exception as error:  # pragma: no cover - physical boundary
            self.error = f"{type(error).__name__}: {error}"
            self.events.write("cdc_error", node=self.node, detail=self.error)
        finally:
            self.ready.set()
            self.done.set()


async def _capture_single_node(
    *,
    target: NodeTarget,
    output_dir: Path,
    client_factory: ClientFactory,
    duration_s: float,
    connection_timeout_s: float,
    recovery_timeout_s: float,
    reconnect_delay_s: float,
    capture_window_callback: CaptureWindowCallback | None = None,
    strict_capture_window: bool = False,
) -> object:
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    recorder = _NodeRecorder(
        target=target,
        sink=_CaptureSink(
            node_id=target.node_id,
            raw_path=raw_dir / f"node-{target.node_id.name.lower()}.kimu",
            events_path=raw_dir / f"node-{target.node_id.name.lower()}.events.ndjson",
        ),
        client_factory=client_factory,
        clock_exchange_count=3,
        clock_response_timeout_s=2.0,
        connection_timeout_s=connection_timeout_s,
        recovery_timeout_s=recovery_timeout_s,
        reconnect_delay_s=reconnect_delay_s,
        monotonic_ns=time.monotonic_ns,
        callback_monotonic_ns=time.perf_counter_ns,
        monotonic_seconds=time.monotonic,
        sleep=asyncio.sleep,
        capture_window_callback=capture_window_callback,
        strict_capture_window=strict_capture_window,
    )
    capture_ready_gate = _CaptureReadyGate(recorders=(recorder,), duration_s=duration_s)
    recorder_task = asyncio.create_task(
        recorder.run(
            capture_ready_gate=capture_ready_gate,
            stop_event=None,
        )
    )
    try:
        return await recorder_task
    finally:
        if not recorder_task.done():
            recorder_task.cancel()
        await asyncio.gather(recorder_task, return_exceptions=True)


async def _disconnect_matrix_clients(
    clients: list[MatrixBleClient], connection_gate: _MatrixConnectionGate
) -> dict[str, object]:
    """Disconnect host clients and confirm every firmware link is down before rest."""

    host_disconnects: list[dict[str, object]] = []
    errors: list[str] = []
    cleanup_cancelled = False
    for client in clients:
        try:
            was_connected = client.is_connected
            _disconnect_result, cancelled = await _await_cleanup_completion(
                client.disconnect()
            )
            cleanup_cancelled |= cancelled
            still_connected = client.is_connected
            disconnect_record: dict[str, object] = {
                "node": client.node.name,
                "disconnect_called": True,
                "was_connected": was_connected,
                "completed": not still_connected,
                "is_connected": still_connected,
            }
            if still_connected:
                detail = f"Node {client.node.name} host BLE session remained connected after disconnect"
                errors.append(detail)
                disconnect_record["error"] = detail
                connection_gate.events.write(
                    "matrix_cleanup_error", node=client.node, detail=detail
                )
            host_disconnects.append(disconnect_record)
        except Exception as error:
            detail = f"Node {client.node.name} host disconnect failed: {type(error).__name__}: {error}"
            errors.append(detail)
            host_disconnects.append(
                {
                    "node": client.node.name,
                    "disconnect_called": True,
                    "completed": False,
                    "is_connected": client.is_connected,
                    "error": f"{type(error).__name__}: {error}",
                }
            )
            connection_gate.events.write("matrix_cleanup_error", node=client.node, detail=detail)

    nodes = tuple(sorted(connection_gate.required_nodes, key=int))
    wait_results, cancelled = await _await_cleanup_completion(
        asyncio.gather(
            *(
                connection_gate.wait_for_peripheral_disconnect(
                    node, timeout_s=ROOT_CAUSE_DISCONNECT_TIMEOUT_S
                )
                for node in nodes
            ),
            return_exceptions=True,
        )
    )
    cleanup_cancelled |= cancelled
    peripheral_disconnects: dict[str, dict[str, object]] = {}
    for node, observed in zip(nodes, wait_results, strict=True):
        if isinstance(observed, BaseException):
            detail = (
                f"Node {node.name} peripheral disconnect confirmation failed: "
                f"{type(observed).__name__}: {observed}"
            )
            errors.append(detail)
            peripheral_disconnects[node.name] = {
                "required": True,
                "observed": False,
                "completed": False,
                "error": detail,
            }
            connection_gate.events.write(
                "matrix_peripheral_disconnect_failure", node=node, detail=detail
            )
        else:
            peripheral_disconnects[node.name] = observed

    completed_ns = time.monotonic_ns()
    connection_gate.events.write(
        "matrix_run_disconnect_complete",
        host_disconnects=host_disconnects,
        peripheral_disconnects=peripheral_disconnects,
        errors=errors,
        disconnect_completed_monotonic_ns=completed_ns,
    )
    return {
        "host_disconnects": host_disconnects,
        "peripheral_disconnects": peripheral_disconnects,
        "disconnect_completed_monotonic_ns": completed_ns,
        "errors": errors,
        "cancelled": cleanup_cancelled,
    }


async def _run_condition(
    *,
    run_dir: Path,
    condition: str,
    run_index: int,
    seconds: float,
    node_a_address: str,
    node_b_address: str,
    expected_node_a_device_id: int,
    expected_node_b_device_id: int,
    request_mode: str,
    set_request_mode_before_run: bool,
    cdc_captures: dict[NodeId, _MatrixCdcCapture],
    plan_path: Path,
    plan_sha256: str,
    completion_driven_tx: bool,
    experiment_profile: str = "connparam_root_cause",
    connection_parameter_request: bool = True,
    require_pristine_start: bool = False,
    forbidden_boot_ids: dict[NodeId, frozenset[int]] | None = None,
    pre_run_control_results: dict[str, dict[str, object]] | None = None,
    cdc_start_offsets: dict[NodeId, int] | None = None,
    connection_timeout_s: float = ROOT_CAUSE_CONNECTION_TIMEOUT_S,
) -> dict[str, object]:
    setup_started_monotonic_ns = time.monotonic_ns()
    if connection_timeout_s <= 0.0:
        raise ValueError("connection timeout must be positive")
    if condition not in CONDITIONS:
        raise ValueError(f"unsupported matrix condition: {condition}")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"matrix run directory is not empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    plan_copy = run_dir / "PREDECLARED_PLAN.md"
    plan_copy.write_bytes(plan_path.read_bytes())
    nodes = _nodes_for_condition(condition)
    connection_order = _connection_order_for_condition(condition)
    first_node = connection_order[0] if len(connection_order) == 2 else None
    events = EventLog(run_dir / "experiment_control.ndjson")
    connection_gate = _MatrixConnectionGate(
        required_nodes=nodes,
        first_node=first_node,
        events=events,
        connection_timeout_s=connection_timeout_s,
    )
    clients: list[MatrixBleClient] = []
    address_by_node = {NodeId.A: node_a_address, NodeId.B: node_b_address}
    expected_id_by_node = {
        NodeId.A: expected_node_a_device_id,
        NodeId.B: expected_node_b_device_id,
    }

    def factory(address: str, disconnected_callback: Callable[[object], None]) -> BleClient:
        node = next(
            (
                candidate
                for candidate, candidate_address in address_by_node.items()
                if candidate_address == address
            ),
            None,
        )
        if node is None:
            raise ValueError(f"unexpected BLE address requested by recorder: {address}")
        client = MatrixBleClient(
            node=node,
            address=address,
            disconnected_callback=disconnected_callback,
            events=events,
            connection_gate=connection_gate,
            require_pristine_start=require_pristine_start,
            forbidden_boot_ids=(forbidden_boot_ids or {}).get(node, frozenset()),
        )
        clients.append(client)
        return client

    cdc_port_map = {
        node.name: cdc_captures[node].port_info.get("device") for node in (NodeId.A, NodeId.B)
    }
    cdc_serial_map = {
        node.name: cdc_captures[node].port_info.get("serial_number")
        for node in (NodeId.A, NodeId.B)
    }
    block_index = (run_index - 1) // len(ROOT_CAUSE_BLOCK_SCHEDULE[0][1]) + 1
    block_run_index = (run_index - 1) % len(ROOT_CAUSE_BLOCK_SCHEDULE[0][1]) + 1
    run_config_schema, run_result_schema, session_prefix = _run_config_schema(
        experiment_profile
    )
    config: dict[str, object] = {
        "schema": run_config_schema,
        "experiment_profile": experiment_profile,
        "created_utc": _utc_now(),
        "run_index": run_index,
        "block_index": block_index,
        "block_run_index": block_run_index,
        "request_mode": request_mode,
        "set_request_mode_before_run": set_request_mode_before_run,
        "condition": condition,
        "nodes": [node.name for node in nodes],
        "connection_order": [node.name for node in connection_order],
        "capture_seconds": seconds,
        "connection_settle_seconds": ROOT_CAUSE_SETUP_SETTLE_S,
        "windows_connect_gatt_setup_timeout_seconds": connection_timeout_s,
        "ble_addresses": {"A": node_a_address, "B": node_b_address},
        "expected_hardware_device_ids": {
            "A": expected_node_a_device_id,
            "B": expected_node_b_device_id,
        },
        "cdc_ports": cdc_port_map,
        "cdc_usb_serials": cdc_serial_map,
        "predeclared_plan_path": str(plan_path),
        "predeclared_plan_sha256": plan_sha256,
        "predeclared_plan_copy": plan_copy.name,
        "runner_path": str(Path(__file__).resolve()),
        "runner_sha256": _sha256(Path(__file__).resolve()),
        "git_head": _git_head(Path(__file__).resolve().parents[1]),
        "python": sys.version,
        "platform": platform.platform(),
        "transport_profile": "completion_driven_tx",
        "change_policy": _change_policy(
            completion_driven_tx,
            connection_parameter_request=connection_parameter_request,
        ),
        "require_pristine_start": require_pristine_start,
        "forbidden_boot_ids_by_node": {
            node.name: sorted(ids)
            for node, ids in (forbidden_boot_ids or {}).items()
        },
    }
    _write_json(run_dir / "run_config.json", config)

    control_results = dict(pre_run_control_results or {})
    result: dict[str, object] = {
        "schema": run_result_schema,
        "run_index": run_index,
        "block_index": block_index,
        "block_run_index": block_run_index,
        "request_mode": request_mode,
        "set_request_mode_before_run": set_request_mode_before_run,
        "condition": condition,
        "nodes": [node.name for node in nodes],
        "started_monotonic_ns": setup_started_monotonic_ns,
        "started_utc": _utc_now(),
        "recorder_result": None,
        "block_mode_control": control_results,
        "cdc_segment_errors": {},
        "error": None,
    }
    capture_offsets = dict(cdc_start_offsets or {})
    firmware_event_listener = connection_gate.note_firmware_event
    listening_captures: list[_MatrixCdcCapture] = []
    cancellation_error: asyncio.CancelledError | None = None
    cleanup_cancelled = False
    try:
        for node in nodes:
            capture = cdc_captures[node]
            capture.add_event_listener(firmware_event_listener)
            listening_captures.append(capture)
        if not capture_offsets:
            try:
                capture_offsets = await _cut_cdc_captures(cdc_captures)
            except CdcControlGateError as error:
                result["error"] = str(error)
                events.write("matrix_run_error", detail=result["error"])
                raise
        if set(capture_offsets) != {NodeId.A, NodeId.B}:
            missing = sorted(node.name for node in {NodeId.A, NodeId.B} - set(capture_offsets))
            raise CdcControlGateError(
                f"CDC capture boundaries missing for Node {', '.join(missing)} before BLE"
            )

        if set_request_mode_before_run:
            failed_controls = [
                node_name
                for node_name in ("A", "B")
                if not isinstance(control_results.get(node_name), dict)
                or control_results[node_name].get("applied") is not True
            ]
            if failed_controls:
                raise CdcControlGateError(
                    f"block mode {request_mode} lacks successful control for "
                    f"Node {', '.join(failed_controls)} before BLE"
                )
            for node_name, ack in control_results.items():
                events.write(
                    "block_request_mode_acknowledgment",
                    node=NodeId[node_name],
                    request_mode=request_mode,
                    **ack,
                )

        events.write(
            "matrix_run_start",
            condition=condition,
            run_index=run_index,
            block_index=block_index,
            request_mode=request_mode,
            nodes=[node.name for node in nodes],
            connection_order=[node.name for node in connection_order],
            connection_settle_seconds=ROOT_CAUSE_SETUP_SETTLE_S,
            seconds=seconds,
            block_mode_control=result["block_mode_control"],
        )
        targets = tuple(
            NodeTarget(
                node_id=node,
                address=address_by_node[node],
                expected_hardware_device_id=expected_id_by_node[node],
            )
            for node in nodes
        )

        def record_capture_window(
            node_id: NodeId,
            start_perf_ns: int,
            deadline_perf_ns: int,
            start_host_ns: int,
            deadline_host_ns: int,
            clock_pair_uncertainty_ns: int,
        ) -> None:
            events.write(
                "matrix_capture_window",
                node=node_id,
                host_monotonic_ns=start_host_ns,
                anchor="shared_recorder_ready_barrier",
                capture_clock_domain="perf_counter_ns",
                capture_start_perf_counter_ns=start_perf_ns,
                capture_deadline_perf_counter_ns=deadline_perf_ns,
                capture_start_host_monotonic_ns=start_host_ns,
                capture_deadline_host_monotonic_ns=deadline_host_ns,
                capture_clock_pair_uncertainty_ns=clock_pair_uncertainty_ns,
                duration_ns=deadline_perf_ns - start_perf_ns,
            )

        if len(targets) == 2:
            recorder = M1BleSessionRecorder(
                targets=targets,
                output_dir=run_dir,
                session_id=f"{session_prefix}-{run_index:02d}-{condition}",
                client_factory=factory,
                connection_timeout_s=connection_timeout_s,
                recovery_timeout_s=DEFAULT_RECOVERY_TIMEOUT_S,
                notes=(
                    f"M1 BLE {experiment_profile}; request mode {request_mode}; "
                    "completion-driven TX enabled."
                ),
            )
            session = await recorder.capture(
                duration_s=seconds,
                capture_window_callback=record_capture_window,
                strict_capture_window=True,
            )
            result["recorder_result"] = {
                "manifest_path": str(session.manifest_path),
                "nodes": {
                    node_id.name: {
                        "raw_path": str(node.raw_path),
                        "events_path": str(node.events_path),
                        "packets": node.packet_count,
                        "samples": node.sample_count,
                        "qc_pass": node.qc_pass,
                    }
                    for node_id, node in session.node_results.items()
                },
            }
        else:
            node = nodes[0]
            single = await _capture_single_node(
                target=targets[0],
                output_dir=run_dir,
                client_factory=factory,
                duration_s=seconds,
                connection_timeout_s=connection_timeout_s,
                recovery_timeout_s=DEFAULT_RECOVERY_TIMEOUT_S,
                reconnect_delay_s=0.25,
                capture_window_callback=record_capture_window,
                strict_capture_window=True,
            )
            result["recorder_result"] = {
                "nodes": {
                    node.name: {
                        "raw_path": str(single.raw_path),
                        "events_path": str(single.events_path),
                        "packets": single.packet_count,
                        "samples": single.sample_count,
                        "qc_pass": single.qc_pass,
                    }
                }
            }
    except asyncio.CancelledError as error:
        cancellation_error = error
        result["error"] = "CancelledError: acquisition run cancelled"
        events.write("matrix_run_error", detail=result["error"])
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        if isinstance(error, CdcControlGateError):
            result["control_gate_failure"] = True
        events.write("matrix_run_error", detail=result["error"])
    finally:
        try:
            cleanup = await _disconnect_matrix_clients(clients, connection_gate)
            result["host_disconnects"] = cleanup["host_disconnects"]
            result["peripheral_disconnects"] = cleanup["peripheral_disconnects"]
            result["disconnect_completed_monotonic_ns"] = cleanup[
                "disconnect_completed_monotonic_ns"
            ]
            disconnect_errors = cleanup["errors"]
            result["disconnect_cleanup_errors"] = disconnect_errors
            cleanup_cancelled |= bool(cleanup["cancelled"])
            if disconnect_errors:
                previous_error = result["error"]
                cleanup_error = "disconnect cleanup failed: " + "; ".join(
                    str(detail) for detail in disconnect_errors
                )
                result["error"] = (
                    f"{previous_error}; {cleanup_error}"
                    if previous_error is not None
                    else cleanup_error
                )
                events.write("matrix_cleanup_error", detail=cleanup_error)
        except Exception as error:
            cleanup_error = f"{type(error).__name__}: {error}"
            result["disconnect_cleanup_errors"] = [cleanup_error]
            result["error"] = (
                f"{result['error']}; disconnect cleanup failed: {cleanup_error}"
                if result["error"] is not None
                else f"disconnect cleanup failed: {cleanup_error}"
            )
            result["disconnect_completed_monotonic_ns"] = time.monotonic_ns()
            events.write("matrix_cleanup_error", detail=cleanup_error)
        for capture in listening_captures:
            capture.remove_event_listener(firmware_event_listener)
        cdc_segments: dict[str, dict[str, object]] = {}
        for node in (NodeId.A, NodeId.B):
            capture = cdc_captures[node]
            start = capture_offsets.get(node)
            if capture.error is not None or capture.done.is_set():
                end: int | None = None
                result["cdc_segment_errors"][node.name] = capture.error or "CDC capture is not running"
            else:
                try:
                    end, cancelled = await _await_cleanup_completion(
                        asyncio.to_thread(capture.cut)
                    )
                    cleanup_cancelled |= cancelled
                except Exception as error:
                    end = None
                    result["cdc_segment_errors"][node.name] = f"{type(error).__name__}: {error}"
            if (start is None) or (end is None):
                cdc_segments[node.name] = capture.copy_segment(0, 0, run_dir)
                cdc_segments[node.name]["error"] = result["cdc_segment_errors"].get(
                    node.name, "CDC segment boundary unavailable"
                )
            else:
                cdc_segments[node.name] = capture.copy_segment(start, end, run_dir)
        result["ended_monotonic_ns"] = time.monotonic_ns()
        result["ended_utc"] = _utc_now()
        result["cdc"] = cdc_segments
        events.write("matrix_run_stop", error=result["error"])
        events.close()

    if cleanup_cancelled and cancellation_error is None:
        result["error"] = "CancelledError: cancellation arrived during run cleanup"
        cancellation_error = asyncio.CancelledError()
    _write_json(run_dir / "run_result.json", result)
    if cancellation_error is not None:
        raise cancellation_error
    return result


async def _run_matrix(args: argparse.Namespace) -> dict[str, object]:
    root_dir: Path = args.root_dir
    default_plan = Path(__file__).with_name("M1_COMPLETION_TX_ROOT_CAUSE_PLAN.md")
    plan_path: Path = args.plan_path or default_plan
    if not plan_path.is_file():
        raise FileNotFoundError(f"predeclared plan does not exist: {plan_path}")
    plan_sha256 = _sha256(plan_path)
    _validate_plan_output_root(plan_sha256, root_dir)
    if root_dir.exists() and any(root_dir.iterdir()):
        raise FileExistsError(f"matrix root directory is not empty: {root_dir}")
    if args.blocks != len(ROOT_CAUSE_BLOCK_SCHEDULE):
        raise ValueError("the locked connection-parameter experiment requires exactly four blocks")
    if args.seconds != ROOT_CAUSE_CAPTURE_S:
        raise ValueError(f"the locked active capture duration is {ROOT_CAUSE_CAPTURE_S:.1f} seconds")
    if args.inter_run_rest_s != ROOT_CAUSE_INTER_RUN_REST_S:
        raise ValueError(f"the locked between-run rest is {ROOT_CAUSE_INTER_RUN_REST_S:.1f} seconds")
    if args.connection_settle_s != ROOT_CAUSE_SETUP_SETTLE_S:
        raise ValueError(
            f"the locked connection settling interval is {ROOT_CAUSE_SETUP_SETTLE_S:.1f} seconds"
        )
    if not args.completion_driven_tx:
        raise ValueError("the locked experiment requires the completion-driven TX diagnostic image")

    repo_root = Path(__file__).resolve().parents[1]
    host_head = _validate_firmware_source_commit(repo_root, args.firmware_source_commit)

    node_a_image: Path = args.firmware_node_a_image
    node_b_image: Path = args.firmware_node_b_image
    if not node_a_image.is_file() or not node_b_image.is_file():
        raise FileNotFoundError("both prebuilt Node A/B UF2 images must exist before acquisition")
    image_info: dict[NodeId, dict[str, object]] = {
        NodeId.A: {
            "source_path": str(node_a_image.resolve()),
            "sha256": _sha256(node_a_image).upper(),
            "size_bytes": node_a_image.stat().st_size,
            "node_id": 1,
        },
        NodeId.B: {
            "source_path": str(node_b_image.resolve()),
            "sha256": _sha256(node_b_image).upper(),
            "size_bytes": node_b_image.stat().st_size,
            "node_id": 2,
        },
    }
    preflash_path: Path = args.preflash_record_path
    if not preflash_path.is_file():
        raise FileNotFoundError("the pre-flash board and image verification record is required")
    preflash_record = json.loads(preflash_path.read_text(encoding="utf-8"))
    if preflash_record.get("plan_sha256", "").upper() != plan_sha256.upper():
        raise ValueError("pre-flash verification record references a different plan")
    preflash_images = preflash_record.get("firmware_images", {})
    preflash_boards = preflash_record.get("boards", {})
    if preflash_record.get("firmware_source_commit") != args.firmware_source_commit:
        raise ValueError("pre-flash record references a different firmware source commit")
    if preflash_record.get("build_configurations_identical") is not True:
        raise ValueError("pre-flash record does not prove matched Node A/B build configurations")
    preflash_build_configs = preflash_record.get("build_configs", {})
    for node in (NodeId.A, NodeId.B):
        config_record = preflash_build_configs.get(node.name, {})
        config_path = Path(config_record.get("path", ""))
        if not config_path.is_file():
            raise FileNotFoundError(f"pre-flash .config for Node {node.name} is missing")
        if _sha256(config_path).upper() != config_record.get("sha256", "").upper():
            raise ValueError(f"pre-flash .config hash for Node {node.name} has changed")
    config_a = Path(preflash_build_configs["A"]["path"]).read_bytes()
    config_b = Path(preflash_build_configs["B"]["path"]).read_bytes()
    if config_a != config_b:
        raise ValueError("Node A/B generated .config files are not byte-identical")
    for node, info in image_info.items():
        image_record = preflash_images.get(node.name, {})
        observed_hash = image_record.get("sha256", "")
        if observed_hash.upper() != info["sha256"]:
            raise ValueError(f"pre-flash image hash for Node {node.name} does not match the build")
        if image_record.get("node_id") != int(node):
            raise ValueError(f"pre-flash image for Node {node.name} has a mismatched node ID")
        if image_record.get("source_commit") != args.firmware_source_commit:
            raise ValueError(f"pre-flash image for Node {node.name} has a mismatched source commit")
        observed_serial = preflash_boards.get(node.name, {}).get("bootloader_usb_serial")
        if observed_serial != ROOT_CAUSE_NODE_USB_SERIALS[node]:
            raise ValueError(f"pre-flash hardware identity for Node {node.name} does not match the plan")
        if preflash_boards.get(node.name, {}).get("board_id") != "Seeed_XIAO_nRF52840_Sense":
            raise ValueError(f"pre-flash board model for Node {node.name} does not match the plan")

    port_info = {
        node: resolve_cdc_port_by_serial(serial)
        for node, serial in ROOT_CAUSE_NODE_USB_SERIALS.items()
    }
    for node, details in port_info.items():
        if details.get("device") is None:
            raise RuntimeError(f"USB serial resolution returned no port for Node {node.name}")

    order = matrix_order(args.blocks)
    root_dir.mkdir(parents=True, exist_ok=True)
    (root_dir / "PREDECLARED_PLAN.md").write_bytes(plan_path.read_bytes())
    (root_dir / "preflash_firmware_and_hardware_check.json").write_bytes(
        preflash_path.read_bytes()
    )
    firmware_dir = root_dir / "firmware"
    firmware_dir.mkdir()
    shutil.copyfile(node_a_image, firmware_dir / "node-a.uf2")
    shutil.copyfile(node_b_image, firmware_dir / "node-b.uf2")
    for node in (NodeId.A, NodeId.B):
        config_path = Path(preflash_build_configs[node.name]["path"])
        shutil.copyfile(config_path, firmware_dir / f"node-{node.name.lower()}.config")

    try:
        from importlib.metadata import version

        host_package_versions = {package: version(package) for package in ("bleak", "pyserial")}
    except Exception as error:
        host_package_versions = {"error": f"{type(error).__name__}: {error}"}

    root_config: dict[str, object] = {
        "schema": "kineimu.m1.ble-connparam-root-cause/1.0",
        "created_utc": _utc_now(),
        "project": "KineIMU Shoulder",
        "objective": "test the predeclared peripheral connection-parameter request factor",
        "output_root": str(root_dir.resolve()),
        "blocks": args.blocks,
        "run_order": list(order),
        "block_schedule": [
            {"block": index, "request_mode": mode, "sequence": list(conditions)}
            for index, (mode, conditions) in enumerate(ROOT_CAUSE_BLOCK_SCHEDULE, start=1)
        ],
        "seconds_per_run": args.seconds,
        "connection_settle_seconds": args.connection_settle_s,
        "inter_run_rest_seconds": args.inter_run_rest_s,
        "m1_filtered_scan_timeout_seconds": ROOT_CAUSE_SCAN_TIMEOUT_S,
        "m1_filtered_scan_cleanup_grace_seconds": M1_SCAN_CLEANUP_GRACE_S,
        "m1_filtered_scan_watchdog_seconds": (
            ROOT_CAUSE_SCAN_TIMEOUT_S + M1_SCAN_CLEANUP_GRACE_S
        ),
        "windows_connect_gatt_setup_timeout_seconds": ROOT_CAUSE_CONNECTION_TIMEOUT_S,
        "predeclared_plan_path": str(plan_path),
        "predeclared_plan_sha256": plan_sha256,
        "predeclared_plan_copy": "PREDECLARED_PLAN.md",
        "preflash_check_path": str(preflash_path.resolve()),
        "preflash_check_sha256": _sha256(preflash_path).upper(),
        "ble_addresses": {"A": args.node_a_address, "B": args.node_b_address},
        "expected_hardware_device_ids": {
            "A": args.expected_node_a_device_id,
            "B": args.expected_node_b_device_id,
        },
        "cdc_ports_resolved_by_usb_serial": {
            node.name: details for node, details in port_info.items()
        },
        "usb_serials": {node.name: serial for node, serial in ROOT_CAUSE_NODE_USB_SERIALS.items()},
        "firmware_images": {
            node.name: {
                **info,
                "experiment_copy_path": f"firmware/node-{node.name.lower()}.uf2",
                "experiment_copy_sha256": _sha256(
                    firmware_dir / f"node-{node.name.lower()}.uf2"
                ).upper(),
            }
            for node, info in image_info.items()
        },
        "firmware_source_commit": args.firmware_source_commit,
        "firmware_build": {
            "board": "xiao_ble/nrf52840/sense",
            "zephyr_version": "v4.4.0",
            "zephyr_commit": "684c9e8f32e4373a21098559f748f06915f950c9",
            "zephyr_sdk": "1.0.1",
            "runtime_mode_control": "KINEIMU_CONN_PARAM_EXPERIMENT=ON",
            "common_config_overlay": "experiments/M1_CONN_PARAM_ROOTCAUSE.overlay.conf",
            "CONFIG_BT_GAP_AUTO_UPDATE_CONN_PARAMS": "n",
            "CONFIG_BT_GAP_PERIPHERAL_PREF_PARAMS": "y (unchanged)",
            "peripheral_preference": "unchanged from Zephyr v4.4.0 project configuration",
            "node_id_definitions": {"A": 1, "B": 2},
        },
        "host": {
            "python": sys.version,
            "platform": platform.platform(),
            "platform_version": platform.version(),
            "platform_release": platform.release(),
            "machine": platform.machine(),
            "packages": host_package_versions,
            "ble_controller": {
                "name": "MediaTek Bluetooth Adapter",
                "instance_id": "USB\\VID_13D3&PID_3563&MI_00\\7&1D754FA2&0&0000",
                "driver_inf": "oem134.inf",
                "driver_version": "1.3.17.169",
                "driver_date": "2026-03-25",
            },
        },
        "git_head": host_head,
        "runner_path": str(Path(__file__).resolve()),
        "runner_sha256": _sha256(Path(__file__).resolve()).upper(),
        "transport_profile": (
            "completion_driven_tx" if args.completion_driven_tx else "baseline_synchronous_notify"
        ),
        "change_policy": _change_policy(args.completion_driven_tx),
    }
    _write_json(root_dir / "matrix_config.json", root_config)

    control_events = EventLog(root_dir / "matrix_control.ndjson")
    cdc_captures = {
        node: _MatrixCdcCapture(
            node=node,
            port_info=port_info[node],
            output_dir=root_dir,
            events=control_events,
        )
        for node in (NodeId.A, NodeId.B)
    }
    for capture in cdc_captures.values():
        capture.start()
    for node, capture in cdc_captures.items():
        if not capture.ready.wait(timeout=10.0):
            capture.error = f"timed out opening serial port {capture.port_info.get('device')}"
            control_events.write("cdc_open_timeout", node=node, detail=capture.error)
        elif capture.error is not None:
            control_events.write("cdc_open_error", node=node, detail=capture.error)

    run_results: list[dict[str, object]] = []
    initial_control_handshake: dict[str, dict[str, object]] = {}
    final_control_cleanup: dict[str, dict[str, object]] = {}
    control_gate_error: str | None = None
    stop_reason: str | None = None
    matrix_cancelled = False
    try:
        try:
            serial_open_failures = [
                f"Node {node.name} CDC capture open gate failed: "
                f"{capture.error or 'serial capture did not open'}"
                for node, capture in cdc_captures.items()
                if capture.error is not None or not capture.ready.is_set() or capture.done.is_set()
            ]
            if serial_open_failures:
                raise CdcControlGateError("; ".join(serial_open_failures))
            initial_control_handshake = await _initial_control_handshake(
                cdc_captures,
                control_events.write,
                timeout_s=5.0,
            )
        except CdcControlGateError as error:
            control_gate_error = str(error)
            stop_reason = control_gate_error
            handshake_context = error.context.get("initial_control_handshake")
            if isinstance(handshake_context, dict):
                initial_control_handshake = {
                    name: value
                    for name, value in handshake_context.items()
                    if isinstance(name, str) and isinstance(value, dict)
                }
            control_events.write("matrix_control_gate_failure", detail=control_gate_error)

        if control_gate_error is None:
            prior_result: dict[str, object] | None = None
            run_index = 0
            for block_index, (request_mode, conditions) in enumerate(
                ROOT_CAUSE_BLOCK_SCHEDULE, start=1
            ):
                block_failed = False
                for position_in_block, condition in enumerate(conditions, start=1):
                    run_index += 1
                    if prior_result is not None:
                        disconnect_ns = int(prior_result["disconnect_completed_monotonic_ns"])
                        target_ns = disconnect_ns + int(
                            ROOT_CAUSE_INTER_RUN_REST_S * 1_000_000_000
                        )
                        remaining_ns = target_ns - time.monotonic_ns()
                        if remaining_ns > 0:
                            await asyncio.sleep(remaining_ns / 1_000_000_000)
                    start_ns = time.monotonic_ns()
                    control_boundary = position_in_block == 1
                    offsets: dict[NodeId, int] = {}
                    try:
                        offsets = await _cut_cdc_captures(cdc_captures)
                        for node, offset in offsets.items():
                            control_events.write(
                                "matrix_run_cdc_boundary",
                                node=node,
                                run_index=run_index,
                                offset=offset,
                            )
                        run_kwargs: dict[str, object] = {
                            "run_dir": root_dir / f"run-{run_index:02d}-{condition}",
                            "condition": condition,
                            "run_index": run_index,
                            "seconds": ROOT_CAUSE_CAPTURE_S,
                            "node_a_address": args.node_a_address,
                            "node_b_address": args.node_b_address,
                            "expected_node_a_device_id": args.expected_node_a_device_id,
                            "expected_node_b_device_id": args.expected_node_b_device_id,
                            "request_mode": request_mode,
                            "set_request_mode_before_run": control_boundary,
                            "cdc_captures": cdc_captures,
                            "plan_path": plan_path,
                            "plan_sha256": plan_sha256,
                            "completion_driven_tx": True,
                            "cdc_start_offsets": offsets,
                        }
                        if control_boundary:
                            current_result = await _run_condition_with_control(
                                request_mode=request_mode,
                                cdc_captures=cdc_captures,
                                events=control_events.write,
                                run_condition=_run_condition,
                                run_kwargs=run_kwargs,
                                timeout_s=5.0,
                                controlled_nodes=(NodeId.A, NodeId.B),
                            )
                        else:
                            current_result = await _run_condition(
                                run_dir=root_dir / f"run-{run_index:02d}-{condition}",
                                condition=condition,
                                run_index=run_index,
                                seconds=ROOT_CAUSE_CAPTURE_S,
                                node_a_address=args.node_a_address,
                                node_b_address=args.node_b_address,
                                expected_node_a_device_id=args.expected_node_a_device_id,
                                expected_node_b_device_id=args.expected_node_b_device_id,
                                request_mode=request_mode,
                                set_request_mode_before_run=False,
                                cdc_captures=cdc_captures,
                                plan_path=plan_path,
                                plan_sha256=plan_sha256,
                                completion_driven_tx=True,
                                cdc_start_offsets=offsets,
                            )
                    except asyncio.CancelledError as error:
                        current_result = {
                            "run_index": run_index,
                            "block_index": block_index,
                            "block_run_index": position_in_block,
                            "request_mode": request_mode,
                            "condition": condition,
                            "set_request_mode_before_run": control_boundary,
                            "cdc_start_offsets": {
                                node.name: offset for node, offset in offsets.items()
                            },
                            "started_monotonic_ns": start_ns,
                            "disconnect_completed_monotonic_ns": time.monotonic_ns(),
                            "error": f"CancelledError: {error}",
                            "cancelled": True,
                        }
                        run_results.append(current_result)
                        control_events.write(
                            "matrix_run_cancelled",
                            run_index=run_index,
                            block_index=block_index,
                            condition=condition,
                            detail=current_result["error"],
                        )
                        raise
                    except Exception as error:
                        if isinstance(error, CdcControlGateError):
                            control_gate_error = str(error)
                            control_events.write(
                                "matrix_control_gate_failure",
                                run_index=run_index,
                                detail=control_gate_error,
                            )
                        control_results = (
                            error.control_results
                            if isinstance(error, CdcControlGateError)
                            else {}
                        )
                        current_result = {
                            "run_index": run_index,
                            "block_index": block_index,
                            "block_run_index": position_in_block,
                            "request_mode": request_mode,
                            "condition": condition,
                            "set_request_mode_before_run": control_boundary,
                            "block_mode_control": {
                                node.name: ack for node, ack in control_results.items()
                            },
                            "cdc_start_offsets": {
                                node.name: offset for node, offset in offsets.items()
                            },
                            "started_monotonic_ns": start_ns,
                            "disconnect_completed_monotonic_ns": time.monotonic_ns(),
                            "error": f"{type(error).__name__}: {error}",
                            "setup_or_capture_exception": True,
                        }
                    if prior_result is not None:
                        prior_disconnect_ns = int(prior_result["disconnect_completed_monotonic_ns"])
                        current_setup_ns = int(current_result["started_monotonic_ns"])
                        prior_result["inter_run_rest_target_seconds"] = ROOT_CAUSE_INTER_RUN_REST_S
                        prior_result["inter_run_rest_observed_seconds"] = (
                            current_setup_ns - prior_disconnect_ns
                        ) / 1_000_000_000
                    run_results.append(current_result)
                    prior_result = current_result
                    if current_result.get("error") is not None:
                        cleanup_errors = current_result.get("disconnect_cleanup_errors", [])
                        cleanup_failed = not isinstance(cleanup_errors, list) or bool(cleanup_errors)
                        run_control_failure = current_result.get("control_gate_failure") is True
                        if run_control_failure and control_gate_error is None:
                            control_gate_error = str(current_result["error"])
                            control_events.write(
                                "matrix_control_gate_failure",
                                run_index=run_index,
                                detail=control_gate_error,
                            )
                        control_failed = (
                            control_gate_error is not None
                            or run_control_failure
                        )
                        if cleanup_failed or control_failed:
                            stop_reason = str(current_result["error"])
                            block_failed = True
                            control_events.write(
                                "matrix_stopped_after_failed_run",
                                run_index=run_index,
                                block_index=block_index,
                                condition=condition,
                                cleanup_failed=cleanup_failed,
                                control_failed=control_failed,
                                detail=stop_reason,
                            )
                            break
                        control_events.write(
                            "matrix_run_failure_continuing_in_locked_order",
                            run_index=run_index,
                            block_index=block_index,
                            condition=condition,
                            detail=str(current_result["error"]),
                        )
                if block_failed:
                    break
    except asyncio.CancelledError as error:
        matrix_cancelled = True
        stop_reason = f"CancelledError: matrix run cancelled ({error})"
        control_events.write("matrix_cancelled", detail=stop_reason)
    finally:
        try:
            final_control_cleanup, cancelled = await _await_cleanup_completion(
                _rollback_control_nodes(
                    cdc_captures,
                    (NodeId.A, NodeId.B),
                    control_events.write,
                    timeout_s=5.0,
                    event_name="matrix_final_control_cleanup",
                )
            )
            if cancelled:
                matrix_cancelled = True
                if stop_reason is None:
                    stop_reason = "CancelledError: cancellation arrived during final OFF cleanup"
        except Exception as error:
            final_control_cleanup = {
                node.name: {
                    "node_id": int(node),
                    "requested": "OFF",
                    "ready": False,
                    "applied": False,
                    "error": f"{type(error).__name__}: {error}",
                }
                for node in (NodeId.A, NodeId.B)
            }
            if stop_reason is None:
                stop_reason = f"final OFF cleanup failed: {type(error).__name__}: {error}"
        for capture in cdc_captures.values():
            capture.stop()
        for capture in cdc_captures.values():
            capture.join()
            capture.finalize_text_log()
        capture_metadata = {
            node.name: capture.metadata() for node, capture in cdc_captures.items()
        }
        control_events.write(
            "matrix_capture_finished",
            run_count=len(run_results),
            cdc=capture_metadata,
        )
        control_events.close()

    _write_json(root_dir / "serial_capture_summary.json", capture_metadata)
    mode_control_results = [
        {
            "block": run["block_index"],
            "request_mode": run["request_mode"],
            "nodes": run.get("block_mode_control", {}),
        }
        for run in run_results
        if run.get("set_request_mode_before_run")
    ]
    result = {
        "schema": "kineimu.m1.ble-connparam-root-cause-result-index/1.0",
        "matrix_config": str(root_dir / "matrix_config.json"),
        "plan_sha256": plan_sha256,
        "run_order": list(order),
        "schedule_attempted_count": len(run_results),
        "scheduled_count": len(order),
        "all_scheduled_runs_attempted": len(run_results) == len(order),
        "initial_control_handshake": initial_control_handshake,
        "final_control_cleanup": final_control_cleanup,
        "cancelled": matrix_cancelled,
        "control_gate_error": control_gate_error,
        "stop_reason": stop_reason,
        "block_mode_control": mode_control_results,
        "serial_capture_summary": capture_metadata,
        "run_results": run_results,
    }
    _write_json(root_dir / "matrix_result.json", result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def _parse_uint64(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid uint64 value: {value}") from error
    if not 0 < parsed < 1 << 64:
        raise argparse.ArgumentTypeError(f"uint64 value must be positive and fit 64 bits: {value}")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-dir", type=Path, default=ROOT_CAUSE_OUTPUT_ROOT)
    parser.add_argument(
        "--plan-path",
        type=Path,
        default=None,
        help="locked root-cause plan; its committed SHA-256 is checked before acquisition",
    )
    parser.add_argument("--node-a-address", required=True)
    parser.add_argument("--node-b-address", required=True)
    parser.add_argument("--expected-node-a-device-id", type=_parse_uint64, required=True)
    parser.add_argument("--expected-node-b-device-id", type=_parse_uint64, required=True)
    parser.add_argument("--firmware-node-a-image", type=Path, required=True)
    parser.add_argument("--firmware-node-b-image", type=Path, required=True)
    parser.add_argument("--firmware-source-commit", required=True)
    parser.add_argument("--preflash-record-path", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument("--inter-run-rest-s", type=float, default=2.0)
    parser.add_argument("--connection-settle-s", type=float, default=10.0)
    parser.add_argument(
        "--completion-driven-tx",
        action="store_true",
        help="required by the locked root-cause plan",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = asyncio.run(_run_matrix(args))
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    all_modes_applied = all(
        node_result.get("applied") is True
        for block in result["block_mode_control"]
        for node_result in block["nodes"].values()
    )
    all_runs_ok = all(run.get("error") is None for run in result["run_results"])
    all_nodes_off = all(
        item.get("applied") is True
        for item in result["final_control_cleanup"].values()
    )
    return (
        0
        if result["all_scheduled_runs_attempted"]
        and all_modes_applied
        and all_runs_ok
        and all_nodes_off
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
