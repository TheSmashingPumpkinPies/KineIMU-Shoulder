"""Run the M1 CDC session, parameter and acquisition physical gates.

This experiment-only runner uses the matrix client's fresh, service-filtered
BLEDevice path and records every input/output under a new evidence directory.
It does not modify production recorder defaults or the public data schema.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import re
import sys
import time
from collections.abc import Awaitable
from pathlib import Path
from typing import Any, cast

from kineimu_shoulder.io.m1_ble import (
    DEFAULT_RECOVERY_TIMEOUT_S,
    IDENTITY_CONFIG_UUID,
    REQUIRED_ATT_MTU,
    NodeTarget,
)
from kineimu_shoulder.io.m1_packet import NodeId
from validation.acquisition_ble import (
    ROOT_CAUSE_CONNECTION_TIMEOUT_S,
    ROOT_CAUSE_DISCONNECT_TIMEOUT_S,
    ROOT_CAUSE_NODE_USB_SERIALS,
    ROOT_CAUSE_SETUP_SETTLE_S,
    MatrixBleClient,
    _capture_single_node,
    _MatrixCdcCapture,
    _MatrixConnectionGate,
    _utc_now,
    _write_json,
    resolve_cdc_port_by_serial,
)
from validation.transport_experiment import EventLog

_decode_identity_config: Any = getattr(  # noqa: B009
    importlib.import_module("kineimu_shoulder.io.m1_ble"), "decode_identity_config"
)

NODE_ADDRESSES = {
    NodeId.A: "02:00:00:00:00:01",
    NodeId.B: "02:00:00:00:00:02",
}
NODE_DEVICE_IDS = {
    NodeId.A: int("0000000000000001", 16),
    NodeId.B: int("0000000000000002", 16),
}
TRANSACTION_TIMEOUT_S = 0.5
SESSION_READY_TIMEOUT_S = 3.0
CAPTURE_DURATION_S = 15.0
_TRACE_PATTERN = re.compile(
    r"^Node (?P<node>[AB]): acquisition trace callback=(?P<callback>[0-9]+) "
    r".*?raw_try=(?P<raw_try>[0-9]+) raw_ok=(?P<raw_ok>[0-9]+) "
    r".*?notify_calls=(?P<notify_calls>[0-9]+)\b"
)
_COUNTER_FIELDS = ("callback", "raw_try", "raw_ok", "notify_calls")
_ACTIVE_CDC_CAPTURES: dict[NodeId, _MatrixCdcCapture] = {}


async def await_thread_to_completion(function: Any, *args: Any, **kwargs: Any) -> Any:
    """Do not detach serial work if the awaiting asyncio task is cancelled."""

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


async def await_cleanup_to_completion(awaitable: Awaitable[Any]) -> tuple[Any, bool]:
    """Finish a cleanup operation even if the caller is cancelled meanwhile."""

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


def evaluate_parameter_window(window: dict[str, Any]) -> dict[str, Any]:
    """Apply the fixed full-window and target-tuple gate to captured events."""

    anchor = int(window["connected_host_monotonic_ns"])
    firmware_anchor = int(window["connected_firmware_uptime_ms"])
    duration_s = float(window["window_duration_s"])
    deadline = anchor + int(duration_s * 1_000_000_000)
    duration_ms = int(round(duration_s * 1_000))
    updates = [
        dict(update)
        for update in window.get("updates", [])
        if ((int(update["firmware_uptime_ms"]) - firmware_anchor) & 0xFFFFFFFF)
        <= duration_ms
    ]
    target = dict(window["target_tuple"])
    target_observed = any(
        update.get("interval_us") == target["interval_us"]
        and update.get("latency") == target["latency"]
        and update.get("supervision_timeout_us") == target["supervision_timeout_us"]
        for update in updates
    )
    observed_s = float(window.get("observed_duration_s", 0.0))
    peripheral_connected_for_full_window = bool(
        window.get("peripheral_connected_for_full_window", True)
    )
    complete = observed_s >= duration_s and peripheral_connected_for_full_window
    disposition = "inconclusive" if not complete else ("passed" if target_observed else "failed")
    return {
        "disposition": disposition,
        "passed": disposition == "passed",
        "anchor": window.get("anchor"),
        "connected_host_monotonic_ns": anchor,
        "connected_firmware_uptime_ms": firmware_anchor,
        "window_duration_s": duration_s,
        "observed_duration_s": observed_s,
        "window_complete": complete,
        "peripheral_connected_for_full_window": peripheral_connected_for_full_window,
        "deadline_monotonic_ns": deadline,
        "deadline_firmware_uptime_ms": (firmware_anchor + duration_ms) & 0xFFFFFFFF,
        "firmware_timebase": window.get(
            "firmware_timebase", "k_uptime_get_32 milliseconds"
        ),
        "updates": updates,
        "updates_in_window": len(updates),
        "target_tuple": target,
        "target_observed": target_observed,
    }


def parse_acquisition_trace(text: str, *, node_name: str) -> list[dict[str, int]]:
    """Extract firmware diagnostic snapshots for the requested physical node."""

    if node_name not in {"A", "B"}:
        raise ValueError("node_name must be A or B")
    snapshots: list[dict[str, int]] = []
    for line in text.splitlines():
        match = _TRACE_PATTERN.search(line.strip())
        if match is None or match.group("node") != node_name:
            continue
        snapshots.append(
            {field: int(match.group(field)) for field in _COUNTER_FIELDS}
        )
    return snapshots


def evaluate_acquisition_artifacts(
    capture: Any,
    trace_snapshots: list[dict[str, int]],
    *,
    duration_s: float = CAPTURE_DURATION_S,
) -> dict[str, Any]:
    """Check raw capture, sidecar QC and firmware trace counter progress."""

    raw_path = Path(capture.raw_path)
    events_path = Path(capture.events_path)
    raw_bytes = raw_path.stat().st_size if raw_path.is_file() else 0
    events_bytes = events_path.stat().st_size if events_path.is_file() else 0
    packet_count = int(getattr(capture, "packet_count", 0))
    sample_count = int(getattr(capture, "sample_count", 0))
    if duration_s <= 0:
        raise ValueError("capture duration must be positive")
    qc = getattr(capture, "qc", None)
    raw_qc_decode_errors = int(getattr(qc, "decode_errors", 0))
    framing_errors = int(getattr(qc, "framing_errors", 0))
    raw_qc_node_mismatches = int(getattr(qc, "node_mismatches", 0))
    crc_error_events = 0
    sidecar_decode_errors = 0
    sidecar_node_mismatches = 0
    if events_path.is_file():
        for raw_line in events_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            record = json.loads(raw_line)
            event = record.get("event")
            if event == "decode_error":
                sidecar_decode_errors += 1
                if record.get("crc_ok") is False:
                    crc_error_events += 1
            if record.get("node_mismatch") is True:
                sidecar_node_mismatches += 1
    trace_increase = {
        field: len(trace_snapshots) >= 2
        and int(trace_snapshots[-1].get(field, 0)) > int(trace_snapshots[0].get(field, 0))
        for field in _COUNTER_FIELDS
    }
    checks = {
        "valid_packets": packet_count > 0,
        "raw_stream_nonempty": raw_bytes > 0,
        "event_sidecar_nonempty": events_bytes > 0,
        "crc_errors": crc_error_events == 0,
        "decode_errors": raw_qc_decode_errors == 0 and sidecar_decode_errors == 0,
        "framing_errors": framing_errors == 0,
        "node_mismatches": raw_qc_node_mismatches == 0 and sidecar_node_mismatches == 0,
        "trace_counter_delta": len(trace_snapshots) >= 2 and all(trace_increase.values()),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "valid_packets": packet_count,
        "sample_count": sample_count,
        "capture_duration_s": duration_s,
        "packet_rate_hz": packet_count / duration_s,
        "sample_rate_hz": sample_count / duration_s,
        "raw_bytes": raw_bytes,
        "event_sidecar_bytes": events_bytes,
        "crc_error_events": crc_error_events,
        "decode_errors_by_source": {
            "raw_qc": raw_qc_decode_errors,
            "event_sidecar": sidecar_decode_errors,
        },
        "framing_errors_raw_qc": framing_errors,
        "node_mismatches_by_source": {
            "raw_qc": raw_qc_node_mismatches,
            "event_sidecar": sidecar_node_mismatches,
        },
        "trace_snapshots": trace_snapshots,
        "trace_counter_increased": trace_increase,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _capture_files(directory: Path) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            files[str(path.relative_to(directory))] = {
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
    return files


def _start_cdc_capture(
    node: NodeId, output_dir: Path, events: EventLog
) -> tuple[_MatrixCdcCapture, dict[str, object]]:
    previous = _ACTIVE_CDC_CAPTURES.get(node)
    if previous is not None:
        if previous.thread.is_alive():
            raise RuntimeError(
                f"Node {node.name} still has an active CDC capture worker"
            )
        _ACTIVE_CDC_CAPTURES.pop(node, None)
    port_info = resolve_cdc_port_by_serial(ROOT_CAUSE_NODE_USB_SERIALS[node])
    capture = _MatrixCdcCapture(
        node=node, port_info=port_info, output_dir=output_dir, events=events
    )
    _ACTIVE_CDC_CAPTURES[node] = capture
    capture.start()
    if not capture.ready.wait(timeout=10.0) or capture.error is not None:
        capture.stop()
        capture.join()
        if capture.thread.is_alive():
            raise RuntimeError(
                f"Node {node.name} CDC open timed out and its worker remains active"
            )
        try:
            capture.finalize_text_log()
        finally:
            if _ACTIVE_CDC_CAPTURES.get(node) is capture:
                _ACTIVE_CDC_CAPTURES.pop(node, None)
        raise RuntimeError(
            f"Node {node.name} CDC open failed: {capture.error or 'open timeout'}"
        )
    return capture, port_info


def _stop_cdc_capture(capture: _MatrixCdcCapture) -> None:
    capture.stop()
    capture.join()
    if capture.thread.is_alive():
        raise RuntimeError(
            f"Node {capture.node.name} CDC capture worker is still active after join"
        )
    capture.finalize_text_log()
    if _ACTIVE_CDC_CAPTURES.get(capture.node) is capture:
        _ACTIVE_CDC_CAPTURES.pop(capture.node, None)
    if capture.error is not None:
        raise RuntimeError(capture.error)


def _control_transaction(
    capture: _MatrixCdcCapture, mode: str, *, timeout_s: float
) -> dict[str, Any]:
    started = time.perf_counter()
    result = capture.set_mode(mode, timeout_s=timeout_s)
    elapsed_s = time.perf_counter() - started
    result = {**result, "elapsed_s": elapsed_s}
    if (
        result.get("applied") is not True
        or result.get("acknowledged") is not True
        or elapsed_s > timeout_s
    ):
        raise RuntimeError(
            f"Node {capture.node.name} {mode} control failed within "
            f"{timeout_s:.3f}s: {result}"
        )
    return result


async def _disconnect_and_confirm_off(
    node: NodeId,
    clients: list[MatrixBleClient],
    capture: _MatrixCdcCapture,
    connection_gate: _MatrixConnectionGate,
) -> dict[str, Any]:
    """Disconnect every host client, wait for the matching firmware event, then OFF."""

    disconnects: list[dict[str, Any]] = []
    errors: list[str] = []
    cleanup_cancelled = False
    for client in clients:
        try:
            _disconnect_result, cancelled = await await_cleanup_to_completion(
                client.disconnect()
            )
            cleanup_cancelled |= cancelled
            disconnects.append(
                {"is_connected": client.is_connected, "completed": not client.is_connected}
            )
        except Exception as error:
            detail = f"disconnect failed: {type(error).__name__}: {error}"
            errors.append(detail)
            disconnects.append(
                {
                    "is_connected": client.is_connected,
                    "completed": False,
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    try:
        peripheral_disconnect, cancelled = await await_cleanup_to_completion(
            connection_gate.wait_for_peripheral_disconnect(
                node, timeout_s=ROOT_CAUSE_DISCONNECT_TIMEOUT_S
            )
        )
        cleanup_cancelled |= cancelled
    except Exception as error:
        peripheral_disconnect = {
            "required": True,
            "observed": False,
            "completed": False,
            "error": f"{type(error).__name__}: {error}",
        }
        errors.append(peripheral_disconnect["error"])

    cleanup_off: dict[str, Any] | None = None
    if capture.error is None and not capture.done.is_set():
        try:
            if peripheral_disconnect["completed"] is not True:
                raise RuntimeError(
                    "OFF cleanup skipped because peripheral disconnect was not confirmed"
                )
            cleanup_off, cancelled = await await_cleanup_to_completion(
                await_thread_to_completion(
                    _control_transaction,
                    capture,
                    "OFF",
                    timeout_s=TRANSACTION_TIMEOUT_S,
                )
            )
            cleanup_cancelled |= cancelled
        except Exception as error:
            detail = f"OFF cleanup failed: {type(error).__name__}: {error}"
            errors.append(detail)
            cleanup_off = {"applied": False, "error": detail}

    return {
        "disconnects": disconnects,
        "peripheral_disconnect": peripheral_disconnect,
        "cleanup_off": cleanup_off,
        "errors": errors,
        "cancelled": cleanup_cancelled,
    }


def _force_off_fresh_session(
    node: NodeId, output_dir: Path, events: EventLog
) -> dict[str, Any]:
    output_dir.mkdir(parents=True)
    capture, port_info = _start_cdc_capture(node, output_dir, events)
    result: dict[str, Any] = {
        "port": port_info,
        "ready": None,
        "off": None,
        "error": None,
    }
    try:
        ready = capture.begin_control_session(timeout_s=SESSION_READY_TIMEOUT_S)
        result["ready"] = ready
        if ready.get("ready") is not True:
            raise RuntimeError(f"fresh cleanup HELLO/READY failed: {ready}")
        result["off"] = _control_transaction(
            capture, "OFF", timeout_s=TRANSACTION_TIMEOUT_S
        )
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            _stop_cdc_capture(capture)
        except Exception as error:
            result["close_error"] = f"{type(error).__name__}: {error}"
    result["cdc"] = capture.metadata()
    result["passed"] = (
        result["error"] is None
        and result.get("close_error") is None
        and result["off"] is not None
        and result["off"].get("applied") is True
    )
    return result


def _gate1_node(node: NodeId, root: Path, events: EventLog) -> dict[str, Any]:
    node_root = root / f"node-{node.name.lower()}"
    node_root.mkdir(parents=True, exist_ok=True)
    sessions: list[dict[str, Any]] = []
    session_dir1 = node_root / "session-01"
    session_dir1.mkdir()
    capture1, port1 = _start_cdc_capture(node, session_dir1, events)
    first_session: str | None = None
    old_command: bytes | None = None
    old_ack_line: str | None = None
    mode_results: list[dict[str, Any]] = []
    try:
        ready1 = capture1.begin_control_session(timeout_s=SESSION_READY_TIMEOUT_S)
        if ready1.get("ready") is not True:
            raise RuntimeError(f"Node {node.name} first HELLO/READY failed: {ready1}")
        first_session = str(ready1["session"])
        for mode in ("OFF", "ON", "OFF"):
            result = _control_transaction(
                capture1, mode, timeout_s=TRANSACTION_TIMEOUT_S
            )
            mode_results.append(result)
            if mode == "ON":
                old_command = (
                    f"SET session={first_session} tx={result['tx']} mode=ON\n"
                ).encode("ascii")
                old_ack_line = (
                    f"ACK node_id={int(node)} session={first_session} "
                    f"tx={result['tx']} requested=ON selected=ON rc=0"
                )
    finally:
        _stop_cdc_capture(capture1)
        sessions.append({"session": 1, "ready": ready1 if "ready1" in locals() else None, "cdc": capture1.metadata()})

    session_dir2 = node_root / "session-02"
    session_dir2.mkdir()
    capture2, port2 = _start_cdc_capture(node, session_dir2, events)
    second_ready: dict[str, object] | None = None
    host_stale_ack_rejected = False
    try:
        second_ready = capture2.begin_control_session(timeout_s=SESSION_READY_TIMEOUT_S)
        if second_ready.get("ready") is not True:
            raise RuntimeError(f"Node {node.name} reopened HELLO/READY failed: {second_ready}")
        if second_ready.get("session") == first_session:
            raise RuntimeError(f"Node {node.name} session nonce did not change after reopen")
        assert old_ack_line is not None
        capture2.control.handle_line(old_ack_line)
        host_stale_ack_rejected = capture2.control.poisoned
        if not host_stale_ack_rejected:
            raise RuntimeError(f"Node {node.name} accepted an ACK from the prior session")
    finally:
        _stop_cdc_capture(capture2)
        sessions.append({"session": 2, "ready": second_ready, "cdc": capture2.metadata()})

    session_dir3 = node_root / "session-03"
    session_dir3.mkdir()
    capture3, port3 = _start_cdc_capture(node, session_dir3, events)
    third_ready: dict[str, object] | None = None
    old_command_rejected = False
    try:
        third_ready = capture3.begin_control_session(timeout_s=SESSION_READY_TIMEOUT_S)
        if third_ready.get("ready") is not True:
            raise RuntimeError(f"Node {node.name} third HELLO/READY failed: {third_ready}")
        assert old_command is not None
        expected = capture3._write_control_command(
            old_command, timeout_s=TRANSACTION_TIMEOUT_S
        )
        if expected != len(old_command):
            raise RuntimeError(
                f"Node {node.name} stale session write was partial: {expected}/{len(old_command)}"
            )
        deadline = time.monotonic() + TRANSACTION_TIMEOUT_S
        while time.monotonic() < deadline:
            if capture3.control.poisoned:
                old_command_rejected = True
                break
            time.sleep(0.005)
        raw_log = capture3.bin_path.read_bytes().decode("utf-8", errors="replace")
        expected_error = f"ERR node_id={int(node)} session={first_session} "
        if (
            not old_command_rejected
            or expected_error not in raw_log
            or "rc=-13" not in raw_log
        ):
            raise RuntimeError(
                f"Node {node.name} firmware did not reject the old-session command"
            )
    finally:
        _stop_cdc_capture(capture3)
        sessions.append({"session": 3, "ready": third_ready, "cdc": capture3.metadata()})

    session_dir4 = node_root / "session-04"
    session_dir4.mkdir()
    capture4, port4 = _start_cdc_capture(node, session_dir4, events)
    fourth_ready: dict[str, object] | None = None
    final_off: dict[str, Any] | None = None
    try:
        fourth_ready = capture4.begin_control_session(timeout_s=SESSION_READY_TIMEOUT_S)
        if fourth_ready.get("ready") is not True:
            raise RuntimeError(f"Node {node.name} cleanup HELLO/READY failed: {fourth_ready}")
        final_off = _control_transaction(
            capture4, "OFF", timeout_s=TRANSACTION_TIMEOUT_S
        )
    finally:
        _stop_cdc_capture(capture4)
        sessions.append({"session": 4, "ready": fourth_ready, "off": final_off, "cdc": capture4.metadata()})

    node_result: dict[str, Any] = {
        "node": node.name,
        "usb_serial": ROOT_CAUSE_NODE_USB_SERIALS[node],
        "ports_by_session": [port1, port2, port3, port4],
        "off_on_off": mode_results,
        "reopen_ready": second_ready,
        "new_nonce_after_reopen": bool(
            second_ready and second_ready.get("session") != first_session
        ),
        "host_stale_ack_rejected": host_stale_ack_rejected,
        "firmware_old_session_command_rejected": old_command_rejected,
        "cleanup_off": final_off,
        "sessions": sessions,
        "passed": all(
            float(result["elapsed_s"]) <= TRANSACTION_TIMEOUT_S
            for result in [*mode_results, final_off or {}]
        )
        and host_stale_ack_rejected
        and old_command_rejected
        and bool(second_ready and second_ready.get("ready") is True)
        and bool(final_off and final_off.get("applied") is True),
    }
    return node_result


async def _parameter_gate_node(
    node: NodeId, output_dir: Path, events: EventLog
) -> dict[str, Any]:
    cdc, port_info = _start_cdc_capture(node, output_dir, events)
    connection_gate = _MatrixConnectionGate(
        required_nodes=(node,), first_node=None, events=events
    )
    cdc.add_event_listener(connection_gate.note_firmware_event)
    client = MatrixBleClient(
        node=node,
        address=NODE_ADDRESSES[node],
        disconnected_callback=lambda _client: None,
        events=events,
        connection_gate=connection_gate,
    )
    result: dict[str, Any] = {
        "node": node.name,
        "usb_serial": ROOT_CAUSE_NODE_USB_SERIALS[node],
        "cdc_port": port_info,
        "identity": None,
        "mtu": None,
        "control_on": None,
        "parameter_window": None,
        "disconnect": None,
        "peripheral_disconnect": None,
        "control_off": None,
        "error": None,
    }
    cleanup_cancelled = False
    try:
        session = await await_thread_to_completion(
            cdc.begin_control_session, timeout_s=SESSION_READY_TIMEOUT_S
        )
        if session.get("ready") is not True:
            raise RuntimeError(f"HELLO/READY failed: {session}")
        result["session"] = session
        result["control_on"] = await await_thread_to_completion(
            _control_transaction, cdc, "ON", timeout_s=TRANSACTION_TIMEOUT_S
        )
        await client.wait_for_connect_slot()
        await asyncio.wait_for(
            client.connect(), timeout=ROOT_CAUSE_CONNECTION_TIMEOUT_S
        )
        identity_started_ns = time.perf_counter_ns()
        identity = _decode_identity_config(
            bytes(await client.read_gatt_char(IDENTITY_CONFIG_UUID))
        )
        if identity.node_id is not node or identity.hardware_device_id != NODE_DEVICE_IDS[node]:
            raise RuntimeError(
                f"identity mismatch: node={identity.node_id.name}, "
                f"hardware_id={identity.hardware_device_id:016x}"
            )
        result["identity"] = {
            "node_id": identity.node_id.name,
            "hardware_device_id": f"{identity.hardware_device_id:016x}",
            "duration_ns": time.perf_counter_ns() - identity_started_ns,
        }
        mtu = client.mtu_size
        result["mtu"] = {"value": mtu, "required": REQUIRED_ATT_MTU, "passed": mtu >= REQUIRED_ATT_MTU}
        if mtu < REQUIRED_ATT_MTU:
            raise RuntimeError(f"ATT MTU {mtu} is below {REQUIRED_ATT_MTU}")
        try:
            await connection_gate.wait_for_settle(ROOT_CAUSE_SETUP_SETTLE_S)
        except Exception:
            if node in connection_gate.peripheral_connected_at:
                raw_window = connection_gate.parameter_window_result(
                    node, ROOT_CAUSE_SETUP_SETTLE_S
                )
                result["parameter_window"] = evaluate_parameter_window(raw_window)
            raise
        raw_window = connection_gate.parameter_window_result(
            node, ROOT_CAUSE_SETUP_SETTLE_S
        )
        result["parameter_window"] = evaluate_parameter_window(raw_window)
        if result["parameter_window"]["disposition"] != "passed":
            raise RuntimeError(
                f"parameter window gate {result['parameter_window']['disposition']}"
            )
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        cleanup = await _disconnect_and_confirm_off(
            node, [client], cdc, connection_gate
        )
        cleanup_cancelled |= cleanup["cancelled"]
        result["disconnect"] = cleanup["disconnects"][0]
        result["peripheral_disconnect"] = cleanup["peripheral_disconnect"]
        result["control_off"] = cleanup["cleanup_off"]
        if cleanup["errors"] and result["error"] is None:
            result["error"] = "; ".join(cleanup["errors"])
        cdc.remove_event_listener(connection_gate.note_firmware_event)
        try:
            _stop_result, cancelled = await await_cleanup_to_completion(
                asyncio.to_thread(_stop_cdc_capture, cdc)
            )
            cleanup_cancelled |= cancelled
        except Exception as error:
            if result["error"] is None:
                result["error"] = f"CDC close failed: {type(error).__name__}: {error}"
        if result["control_off"] is None or result["control_off"].get("applied") is not True:
            try:
                if result["peripheral_disconnect"]["completed"] is not True:
                    raise RuntimeError(
                        "fresh-session OFF cleanup skipped because peripheral "
                        "disconnect was not confirmed"
                    )
                result["fresh_session_cleanup"], cancelled = await await_cleanup_to_completion(
                    await_thread_to_completion(
                        _force_off_fresh_session,
                        node,
                        output_dir / "cleanup-recovery",
                        events,
                    )
                )
                cleanup_cancelled |= cancelled
            except Exception as error:
                result["fresh_session_cleanup"] = {
                    "passed": False,
                    "error": f"{type(error).__name__}: {error}",
                }
        result["cdc"] = cdc.metadata()
        _write_json(output_dir / "node_gate_partial.json", result)
        if cleanup_cancelled:
            raise asyncio.CancelledError
    result["passed"] = (
        result["error"] is None
        and result["parameter_window"] is not None
        and result["parameter_window"]["disposition"] == "passed"
        and result["control_off"] is not None
        and result["control_off"].get("applied") is True
        and result["peripheral_disconnect"] is not None
        and result["peripheral_disconnect"].get("completed") is True
        and result.get("fresh_session_cleanup", {}).get("passed", True) is True
        and result["disconnect"] is not None
        and result["disconnect"].get("completed") is True
        and result["disconnect"].get("is_connected") is False
    )
    result["cdc"] = cdc.metadata()
    _write_json(output_dir / "node_gate_result.json", result)
    return result


async def _acquisition_gate_node(
    node: NodeId, output_dir: Path, events: EventLog
) -> dict[str, Any]:
    cdc, port_info = _start_cdc_capture(node, output_dir, events)
    connection_gate = _MatrixConnectionGate(
        required_nodes=(node,), first_node=None, events=events
    )
    cdc.add_event_listener(connection_gate.note_firmware_event)
    clients: list[MatrixBleClient] = []

    def client_factory(address: str, disconnected_callback: Any) -> MatrixBleClient:
        if address != NODE_ADDRESSES[node]:
            raise ValueError(f"unexpected BLE address {address} for Node {node.name}")
        client = MatrixBleClient(
            node=node,
            address=address,
            disconnected_callback=disconnected_callback,
            events=events,
            connection_gate=connection_gate,
        )
        clients.append(client)
        return client

    result: dict[str, Any] = {
        "node": node.name,
        "usb_serial": ROOT_CAUSE_NODE_USB_SERIALS[node],
        "cdc_port": port_info,
        "capture_seconds": CAPTURE_DURATION_S,
        "control_off": None,
        "capture": None,
        "trace": None,
        "error": None,
        "disconnects": [],
        "peripheral_disconnect": None,
        "cleanup_off": None,
    }
    capture_result: Any | None = None
    cleanup_cancelled = False
    try:
        session = await await_thread_to_completion(
            cdc.begin_control_session, timeout_s=SESSION_READY_TIMEOUT_S
        )
        if session.get("ready") is not True:
            raise RuntimeError(f"HELLO/READY failed: {session}")
        result["session"] = session
        result["control_off"] = await await_thread_to_completion(
            _control_transaction, cdc, "OFF", timeout_s=TRANSACTION_TIMEOUT_S
        )
        target = NodeTarget(
            node_id=node,
            address=NODE_ADDRESSES[node],
            expected_hardware_device_id=NODE_DEVICE_IDS[node],
        )

        def record_capture_window(
            node_id: NodeId,
            start_perf_ns: int,
            deadline_perf_ns: int,
            start_host_ns: int,
            deadline_host_ns: int,
            clock_pair_uncertainty_ns: int,
        ) -> None:
            _record_capture_window(
                events,
                node_id,
                start_perf_ns,
                deadline_perf_ns,
                start_host_ns,
                deadline_host_ns,
                clock_pair_uncertainty_ns,
            )

        capture_result = await _capture_single_node(
            target=target,
            output_dir=output_dir / "capture",
            client_factory=client_factory,
            duration_s=CAPTURE_DURATION_S,
            connection_timeout_s=ROOT_CAUSE_CONNECTION_TIMEOUT_S,
            recovery_timeout_s=DEFAULT_RECOVERY_TIMEOUT_S,
            reconnect_delay_s=0.25,
            capture_window_callback=record_capture_window,
            strict_capture_window=True,
        )
        cdc_text = cdc.bin_path.read_bytes().decode("utf-8", errors="replace")
        trace_snapshots = parse_acquisition_trace(cdc_text, node_name=node.name)
        result["trace"] = trace_snapshots
        result["capture"] = evaluate_acquisition_artifacts(
            capture_result, trace_snapshots, duration_s=CAPTURE_DURATION_S
        )
        captured = cast(Any, capture_result)
        config = captured.config
        result["identity"] = {
            "node_id": config.node_id.name,
            "hardware_device_id": f"{config.hardware_device_id:016x}",
            "passed": (
                config.node_id is node
                and config.hardware_device_id == NODE_DEVICE_IDS[node]
            ),
        }
        capture_events_path = Path(captured.events_path)
        capture_events = [
            json.loads(line)
            for line in capture_events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        mtu_records = [item for item in capture_events if item.get("event") == "mtu"]
        result["mtu"] = {
            "records": mtu_records,
            "passed": bool(mtu_records)
            and all(
                int(item.get("mtu", 0)) >= REQUIRED_ATT_MTU
                and item.get("accepted") is True
                for item in mtu_records
            ),
        }
        if result["identity"]["passed"] is not True or result["mtu"]["passed"] is not True:
            result["capture"]["passed"] = False
            result["capture"]["failed_checks"].append("identity_or_mtu")
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        raw_dir = output_dir / "capture" / "raw"
        result["partial_files"] = {
            str(path.relative_to(output_dir)): {
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in sorted(raw_dir.rglob("*"))
            if path.is_file()
        } if raw_dir.exists() else {}
    finally:
        cleanup = await _disconnect_and_confirm_off(
            node, clients, cdc, connection_gate
        )
        cleanup_cancelled |= cleanup["cancelled"]
        result["disconnects"] = cleanup["disconnects"]
        result["peripheral_disconnect"] = cleanup["peripheral_disconnect"]
        result["cleanup_off"] = cleanup["cleanup_off"]
        if cleanup["errors"] and result["error"] is None:
            result["error"] = "; ".join(cleanup["errors"])
        cdc.remove_event_listener(connection_gate.note_firmware_event)
        try:
            _stop_result, cancelled = await await_cleanup_to_completion(
                asyncio.to_thread(_stop_cdc_capture, cdc)
            )
            cleanup_cancelled |= cancelled
        except Exception as error:
            if result["error"] is None:
                result["error"] = f"CDC close failed: {type(error).__name__}: {error}"
        if (
            result.get("cleanup_off", {}).get("applied") is not True
            and result.get("peripheral_disconnect", {}).get("completed") is True
        ):
            try:
                result["fresh_session_cleanup"], cancelled = await await_cleanup_to_completion(
                    await_thread_to_completion(
                        _force_off_fresh_session,
                        node,
                        output_dir / "cleanup-recovery",
                        events,
                    )
                )
                cleanup_cancelled |= cancelled
            except Exception as error:
                result["fresh_session_cleanup"] = {
                    "passed": False,
                    "error": f"{type(error).__name__}: {error}",
                }
        result["cdc"] = cdc.metadata()
        _write_json(output_dir / "node_gate_partial.json", result)
        if cleanup_cancelled:
            raise asyncio.CancelledError
    result["passed"] = (
        result["error"] is None
        and isinstance(result["capture"], dict)
        and result["capture"].get("passed") is True
        and result.get("identity", {}).get("passed") is True
        and result.get("mtu", {}).get("passed") is True
        and result.get("cleanup_off", {}).get("applied") is True
        and result.get("peripheral_disconnect", {}).get("completed") is True
        and result.get("fresh_session_cleanup", {}).get("passed", True) is True
        and all(item.get("completed") is True for item in result["disconnects"])
    )
    result["cdc"] = cdc.metadata()
    _write_json(output_dir / "node_gate_result.json", result)
    return result


def _record_capture_window(
    events: EventLog,
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


async def run_gates(output_root: Path, *, gate: str = "all") -> dict[str, Any]:
    if gate not in {"all", "1", "2", "3"}:
        raise ValueError("gate must be all, 1, 2 or 3")
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"physical gate evidence directory is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    events = EventLog(output_root / "physical_gates.ndjson")
    report: dict[str, Any] = {
        "schema": "kineimu.m1.physical-gates/1.0",
        "created_utc": _utc_now(),
        "output_root": str(output_root.resolve()),
        "gate_requested": gate,
        "gate1": None,
        "gate2": None,
        "gate3": None,
    }
    cancellation: asyncio.CancelledError | None = None
    try:
        if gate in {"all", "1"}:
            results = {}
            for node in (NodeId.A, NodeId.B):
                try:
                    results[node.name] = await await_thread_to_completion(
                        _gate1_node,
                        node,
                        output_root / "gate1",
                        events,
                    )
                except asyncio.CancelledError:
                    try:
                        await await_thread_to_completion(
                            _force_off_fresh_session,
                            node,
                            output_root
                            / "gate1"
                            / f"node-{node.name.lower()}"
                            / "cancel-cleanup",
                            events,
                        )
                    except Exception:
                        pass
                    raise
                except Exception as error:
                    failure = f"{type(error).__name__}: {error}"
                    try:
                        recovery = await await_thread_to_completion(
                            _force_off_fresh_session,
                            node,
                            output_root
                            / "gate1"
                            / f"node-{node.name.lower()}"
                            / "failure-cleanup",
                            events,
                        )
                    except Exception as cleanup_error:
                        recovery = {
                            "passed": False,
                            "error": f"{type(cleanup_error).__name__}: {cleanup_error}",
                        }
                    results[node.name] = {
                        "passed": False,
                        "error": failure,
                        "fresh_session_cleanup": recovery,
                    }
            report["gate1"] = results
            _write_json(output_root / "gate1_result.json", results)
            if not all(item.get("passed") is True for item in results.values()):
                report["stop_reason"] = "Gate 1 CDC session reopen failed for at least one node"
        if gate in {"all", "2"} and (gate != "all" or report.get("stop_reason") is None):
            results = {}
            for node in (NodeId.A, NodeId.B):
                node_dir = output_root / "gate2" / f"node-{node.name.lower()}"
                node_dir.mkdir(parents=True)
                try:
                    results[node.name] = await _parameter_gate_node(node, node_dir, events)
                except Exception as error:
                    results[node.name] = {"passed": False, "error": f"{type(error).__name__}: {error}"}
            report["gate2"] = results
            _write_json(output_root / "gate2_result.json", results)
            if not all(item.get("passed") is True for item in results.values()):
                report["stop_reason"] = "Gate 2 parameter smoke failed for at least one node"
        if gate in {"all", "3"} and (gate != "all" or report.get("stop_reason") is None):
            results = {}
            for node in (NodeId.A, NodeId.B):
                node_dir = output_root / "gate3" / f"node-{node.name.lower()}"
                node_dir.mkdir(parents=True)
                try:
                    results[node.name] = await _acquisition_gate_node(node, node_dir, events)
                except Exception as error:
                    results[node.name] = {"passed": False, "error": f"{type(error).__name__}: {error}"}
            report["gate3"] = results
            _write_json(output_root / "gate3_result.json", results)
            if not all(item.get("passed") is True for item in results.values()):
                report["stop_reason"] = "Gate 3 acquisition smoke failed for at least one node"
    except asyncio.CancelledError as error:
        cancellation = error
        report["cancelled"] = True
        report["stop_reason"] = "physical gate run cancelled after cleanup"
    finally:
        events.close()
    report["passed"] = report.get("stop_reason") is None
    _write_json(output_root / "physical_gates_result.json", report)
    manifest = {
        "schema": "kineimu.m1.physical-gates-manifest/1.0",
        "created_utc": _utc_now(),
        "result_sha256": _sha256(output_root / "physical_gates_result.json"),
        "manifest_hash_sidecar": "manifest.sha256",
        "self_entry_excluded_to_avoid_recursive_hash": True,
        "files": _capture_files(output_root),
    }
    _write_json(output_root / "manifest.json", manifest)
    (output_root / "manifest.sha256").write_text(
        f"{_sha256(output_root / 'manifest.json')}  manifest.json\n",
        encoding="ascii",
    )
    if cancellation is not None:
        raise cancellation
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--gate", choices=("all", "1", "2", "3"), default="all")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = asyncio.run(run_gates(args.output_root, gate=args.gate))
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("passed") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
