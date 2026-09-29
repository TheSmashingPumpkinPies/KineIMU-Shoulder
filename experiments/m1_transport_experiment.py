"""Run the separately scoped M1 BLE transport experiments.

This file is an experiment driver, not production firmware or a recorder
protocol change.  It wraps the existing M1 recorder, preserves its immutable
raw streams, captures exact CDC bytes, and records only the predeclared test
stimulus in a separate control sidecar.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from kineimu_shoulder.io.m1_ble import (
    TELEMETRY_UUID,
    M1BleSessionRecorder,
    NodeTarget,
    create_bleak_client,
)
from kineimu_shoulder.io.m1_packet import NodeId


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


class EventLog:
    """Append-only JSONL log for the test stimulus and host orchestration."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream = path.open("x", encoding="utf-8")
        self._lock = threading.Lock()

    def write(self, event: str, *, node: NodeId | None = None, **fields: object) -> None:
        record: dict[str, object] = {
            "event": event,
            "host_monotonic_ns": time.monotonic_ns(),
            "utc": _utc_now(),
        }
        if node is not None:
            record["node"] = node.name
        record.update(fields)
        with self._lock:
            self._stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            self._stream.flush()

    def close(self) -> None:
        with self._lock:
            self._stream.close()


class SerialCapture:
    """Capture exact USB CDC bytes without interpreting or rewriting them."""

    def __init__(self, *, port: str, output_dir: Path, label: str, events: EventLog) -> None:
        self.port = port
        self.output_dir = output_dir
        self.label = label
        self.events = events
        self.bin_path = output_dir / f"{label}.cdc.bin"
        self.log_path = output_dir / f"{label}.cdc.log"
        self._stop = threading.Event()
        self.ready = threading.Event()
        self.done = threading.Event()
        self.error: str | None = None
        self.thread = threading.Thread(target=self._run, name=f"cdc-{label}", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self) -> None:
        self.thread.join(timeout=10.0)
        if self.thread.is_alive() and self.error is None:
            self.error = "CDC capture thread did not stop within 10 seconds"

    def _run(self) -> None:
        try:
            import serial  # type: ignore[import-untyped]

            with (
                self.bin_path.open("xb") as raw,
                serial.Serial(self.port, baudrate=115200, timeout=0.2) as connection,
            ):
                connection.dtr = True
                connection.rts = True
                self.events.write("cdc_open", port=self.port, label=self.label)
                self.ready.set()
                while not self._stop.is_set():
                    chunk = connection.read(connection.in_waiting or 1)
                    if chunk:
                        raw.write(chunk)
                        raw.flush()
                raw.flush()
                self.events.write(
                    "cdc_close",
                    port=self.port,
                    label=self.label,
                    byte_length=self.bin_path.stat().st_size,
                )
        except Exception as error:  # pragma: no cover - physical boundary
            self.error = f"{type(error).__name__}: {error}"
            self.events.write("cdc_error", port=self.port, label=self.label, detail=self.error)
            self.ready.set()
        finally:
            self.done.set()

    def finalize_text_log(self) -> None:
        data = self.bin_path.read_bytes()
        with self.log_path.open("x", encoding="utf-8") as stream:
            stream.write(data.decode("utf-8", errors="replace"))

    def metadata(self) -> dict[str, object]:
        result: dict[str, object] = {
            "port": self.port,
            "label": self.label,
            "raw_path": self.bin_path.name,
            "raw_sha256": _sha256(self.bin_path) if self.bin_path.exists() else None,
            "raw_bytes": self.bin_path.stat().st_size if self.bin_path.exists() else None,
            "decoded_log_path": self.log_path.name if self.log_path.exists() else None,
            "decoded_log_sha256": _sha256(self.log_path) if self.log_path.exists() else None,
            "error": self.error,
        }
        return result


class ExperimentBleClient:
    """Bleak boundary wrapper used only to log and schedule test stimuli."""

    def __init__(
        self,
        *,
        node: NodeId,
        address: str,
        disconnected_callback: Callable[[object], None],
        events: EventLog,
        callback_delay_s: float,
        disconnect_after_s: float | None,
        disconnect_hold_s: float,
        state: dict[str, object],
    ) -> None:
        self.node = node
        self.address = address
        self.events = events
        self.callback_delay_s = callback_delay_s
        self.disconnect_after_s = disconnect_after_s
        self.disconnect_hold_s = disconnect_hold_s
        self.state = state

        def on_underlying_disconnected(_underlying_client: object) -> None:
            # Bleak supplies its own client instance to the callback. The
            # session recorder tracks this wrapper instance, so translate the
            # callback identity at the experiment boundary.
            disconnected_callback(self)

        self._client = create_bleak_client(address, on_underlying_disconnected)
        self._stimulus_task: asyncio.Task[None] | None = None

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    @property
    def mtu_size(self) -> int:
        return self._client.mtu_size

    async def connect(self) -> None:
        hold_until_value = self.state.get("reconnect_hold_until_s", 0.0)
        hold_until = hold_until_value if isinstance(hold_until_value, float) else 0.0
        if bool(self.state.get("disconnect_fired", False)) and hold_until > time.monotonic():
            wait_s = hold_until - time.monotonic()
            self.events.write("reconnect_hold_start", node=self.node, wait_s=wait_s)
            await asyncio.sleep(wait_s)
            self.events.write("reconnect_hold_end", node=self.node)
        self.events.write("ble_connect_call", node=self.node, address=self.address)
        await self._client.connect()
        self.events.write("ble_connect_return", node=self.node, address=self.address)

    async def disconnect(self) -> None:
        self.events.write("ble_disconnect_call", node=self.node, address=self.address)
        await self._client.disconnect()

    async def read_gatt_char(self, char_specifier: str) -> bytes | bytearray:
        return await self._client.read_gatt_char(char_specifier)

    async def write_gatt_char(
        self,
        char_specifier: str,
        data: bytes,
        *,
        response: bool | None = None,
    ) -> None:
        await self._client.write_gatt_char(char_specifier, data, response=response)

    async def start_notify(
        self,
        char_specifier: str,
        callback: Callable[[object, bytearray], None],
    ) -> None:
        wrapped_callback = callback
        if char_specifier == TELEMETRY_UUID and self.callback_delay_s > 0.0:
            def delayed_callback(sender: object, data: bytearray) -> None:
                delay_start = time.monotonic_ns()
                time.sleep(self.callback_delay_s)
                self.events.write(
                    "telemetry_callback_delay",
                    node=self.node,
                    delay_s=self.callback_delay_s,
                    start_monotonic_ns=delay_start,
                    end_monotonic_ns=time.monotonic_ns(),
                    payload_length=len(data),
                )
                callback(sender, data)

            wrapped_callback = delayed_callback
        await self._client.start_notify(char_specifier, wrapped_callback)
        if char_specifier == TELEMETRY_UUID:
            self.events.write(
                "telemetry_notify_enabled",
                node=self.node,
                address=self.address,
                callback_delay_s=self.callback_delay_s,
            )
            if self.disconnect_after_s is not None and not bool(self.state.get("schedule_created", False)):
                self.state["schedule_created"] = True
                self._stimulus_task = asyncio.create_task(self._disconnect_later())

    async def stop_notify(self, char_specifier: str) -> None:
        await self._client.stop_notify(char_specifier)

    async def _disconnect_later(self) -> None:
        assert self.disconnect_after_s is not None
        await asyncio.sleep(self.disconnect_after_s)
        if not self.is_connected:
            self.events.write("stimulus_disconnect_skipped", node=self.node, reason="already_disconnected")
            return
        self.state["disconnect_fired"] = True
        self.state["reconnect_hold_until_s"] = time.monotonic() + self.disconnect_hold_s
        self.events.write(
            "stimulus_disconnect_request",
            node=self.node,
            planned_after_s=self.disconnect_after_s,
            planned_hold_s=self.disconnect_hold_s,
        )
        await self._client.disconnect()
        self.events.write("stimulus_disconnect_return", node=self.node)


def _parse_uint64(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid uint64 value: {value}") from error
    if not 0 < parsed < 1 << 64:
        raise argparse.ArgumentTypeError(f"uint64 value must be positive and fit 64 bits: {value}")
    return parsed


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("pressure", "recovery", "bench"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--node-a-address", required=True)
    parser.add_argument("--node-b-address", required=True)
    parser.add_argument("--expected-node-a-device-id", type=_parse_uint64, required=True)
    parser.add_argument("--expected-node-b-device-id", type=_parse_uint64, required=True)
    parser.add_argument("--predeclared-plan", type=Path, required=True)
    parser.add_argument("--cdc-port-a", default="COM5")
    parser.add_argument("--cdc-port-b", default="COM8")
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--callback-delay-ms", type=float, default=0.0)
    parser.add_argument("--disconnect-a-after-s", type=float)
    parser.add_argument("--disconnect-b-after-s", type=float)
    parser.add_argument("--disconnect-hold-s", type=float, default=3.0)
    parser.add_argument("--reconnect-delay-s", type=float, default=0.25)
    parser.add_argument("--notes", required=True)
    return parser


async def _run(args: argparse.Namespace) -> dict[str, object]:
    output_dir: Path = args.output_dir
    if output_dir.exists():
        if any(output_dir.iterdir()):
            raise FileExistsError(f"experiment output directory is not empty: {output_dir}")
    else:
        output_dir.mkdir(parents=True)
    if args.seconds <= 0.0:
        raise ValueError("--seconds must be positive")
    if args.callback_delay_ms < 0.0:
        raise ValueError("--callback-delay-ms must not be negative")
    if args.disconnect_hold_s < 0.0:
        raise ValueError("--disconnect-hold-s must not be negative")
    plan_path: Path = args.predeclared_plan
    if not plan_path.is_file():
        raise FileNotFoundError(f"predeclared plan does not exist: {plan_path}")
    plan_sha256 = _sha256(plan_path)
    plan_copy_path = output_dir / "PREDECLARED_PLAN.md"
    with plan_copy_path.open("xb") as plan_copy:
        plan_copy.write(plan_path.read_bytes())
    events = EventLog(output_dir / "experiment_control.ndjson")
    repo_root = Path(__file__).resolve().parents[1]
    delay_s = args.callback_delay_ms / 1000.0
    plan: dict[NodeId, float | None] = {
        NodeId.A: args.disconnect_a_after_s if args.mode == "recovery" else None,
        NodeId.B: args.disconnect_b_after_s if args.mode == "recovery" else None,
    }
    states: dict[NodeId, dict[str, object]] = {NodeId.A: {}, NodeId.B: {}}
    clients: list[ExperimentBleClient] = []

    def factory(address: str, disconnected_callback: Callable[[object], None]) -> ExperimentBleClient:
        if address == args.node_a_address:
            node = NodeId.A
        elif address == args.node_b_address:
            node = NodeId.B
        else:
            raise ValueError(f"unexpected BLE address requested by recorder: {address}")
        client = ExperimentBleClient(
            node=node,
            address=address,
            disconnected_callback=disconnected_callback,
            events=events,
            callback_delay_s=delay_s,
            disconnect_after_s=plan[node],
            disconnect_hold_s=args.disconnect_hold_s,
            state=states[node],
        )
        clients.append(client)
        return client

    serial_captures = [
        SerialCapture(port=args.cdc_port_a, output_dir=output_dir, label="node-a", events=events),
        SerialCapture(port=args.cdc_port_b, output_dir=output_dir, label="node-b", events=events),
    ]
    config = {
        "created_utc": _utc_now(),
        "mode": args.mode,
        "session_id": args.session_id,
        "seconds": args.seconds,
        "callback_delay_ms": args.callback_delay_ms,
        "disconnect_a_after_s": args.disconnect_a_after_s,
        "disconnect_b_after_s": args.disconnect_b_after_s,
        "disconnect_hold_s": args.disconnect_hold_s,
        "reconnect_delay_s": args.reconnect_delay_s,
        "ble_addresses": {"A": args.node_a_address, "B": args.node_b_address},
        "cdc_ports": {"A": args.cdc_port_a, "B": args.cdc_port_b},
        "notes": args.notes,
        "predeclared_plan_path": str(plan_path),
        "predeclared_plan_sha256": plan_sha256,
        "predeclared_plan_copy": plan_copy_path.name,
        "runner_path": str(Path(__file__).resolve()),
        "runner_sha256": _sha256(Path(__file__).resolve()),
        "git_head": _git_head(repo_root),
        "python": sys.version,
        "platform": platform.platform(),
    }
    with (output_dir / "run_config.json").open("x", encoding="utf-8") as stream:
        json.dump(config, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")

    for capture in serial_captures:
        capture.start()
    for capture in serial_captures:
        if not capture.ready.wait(timeout=10.0):
            raise TimeoutError(f"timed out opening CDC port {capture.port}")
        if capture.error is not None:
            raise RuntimeError(f"unable to capture CDC port {capture.port}: {capture.error}")

    started_ns = time.monotonic_ns()
    events.write("experiment_start", mode=args.mode, session_id=args.session_id, seconds=args.seconds)
    recorder = M1BleSessionRecorder(
        targets=(
            NodeTarget(
                node_id=NodeId.A,
                address=args.node_a_address,
                expected_hardware_device_id=args.expected_node_a_device_id,
            ),
            NodeTarget(
                node_id=NodeId.B,
                address=args.node_b_address,
                expected_hardware_device_id=args.expected_node_b_device_id,
            ),
        ),
        output_dir=output_dir,
        session_id=args.session_id,
        client_factory=factory,
        reconnect_delay_s=args.reconnect_delay_s,
        notes=args.notes,
    )
    result: dict[str, object] = {
        "mode": args.mode,
        "session_id": args.session_id,
        "started_monotonic_ns": started_ns,
        "started_utc": _utc_now(),
        "recorder_result": None,
        "error": None,
    }
    try:
        session = await recorder.capture(duration_s=args.seconds)
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
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}"
        events.write("experiment_error", detail=result["error"])
    finally:
        for client in clients:
            if client._stimulus_task is not None and not client._stimulus_task.done():
                client._stimulus_task.cancel()
        await asyncio.gather(
            *[
                client._stimulus_task
                for client in clients
                if client._stimulus_task is not None
            ],
            return_exceptions=True,
        )
        for capture in serial_captures:
            capture.stop()
        for capture in serial_captures:
            capture.join()
            if capture.bin_path.exists():
                capture.finalize_text_log()
    result["ended_monotonic_ns"] = time.monotonic_ns()
    result["ended_utc"] = _utc_now()
    result["cdc"] = {capture.label: capture.metadata() for capture in serial_captures}
    with (output_dir / "run_result.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    events.write("experiment_stop", error=result["error"])
    events.close()
    result["control_log_sha256"] = _sha256(output_dir / "experiment_control.ndjson")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def main() -> int:
    args = build_argument_parser().parse_args()
    result = asyncio.run(_run(args))
    return 0 if result["error"] is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
