"""Host BLE central and append-only recorder for the frozen M1 contract.

The BLE client is an adapter boundary.  This module performs no unit or axis
conversion: notification payloads are persisted exactly as received and the
existing M1 packet/control codecs remain the only wire-format authority.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

from kineimu_shoulder.io.m1_capture import CaptureFormatError, encode_capture_record
from kineimu_shoulder.io.m1_control import (
    AcquisitionState,
    ClockRequest,
    ClockResponse,
    IdentityConfig,
    Status,
    StatusFlags,
    TimestampSource,
    decode_clock_response,
    decode_identity_config,
    decode_status,
    encode_clock_request,
)
from kineimu_shoulder.io.m1_packet import NodeId, ProtocolError, crc32c, decode_sample_packet
from kineimu_shoulder.io.m1_qc import SequenceQcReport, audit_capture_stream

M1_SERVICE_UUID = "f7d20001-4b49-4e45-494d-552d53484c44"
M1_SCAN_CLEANUP_GRACE_S = 1.0
IDENTITY_CONFIG_UUID = "f7d20002-4b49-4e45-494d-552d53484c44"
TELEMETRY_UUID = "f7d20003-4b49-4e45-494d-552d53484c44"
CLOCK_EXCHANGE_UUID = "f7d20004-4b49-4e45-494d-552d53484c44"
STATUS_UUID = "f7d20005-4b49-4e45-494d-552d53484c44"

REQUIRED_ATT_MTU = 127
REQUIRED_BATCH_SIZE = 4
DRIVER_NAME = "zephyr/st/lsm6dsl"
REGISTER_ORDER = "kineimu.m1.lsm6ds3trc-registers/1"
DEFAULT_CONNECTION_TIMEOUT_S = 5.0
DEFAULT_RECOVERY_TIMEOUT_S = 10.0

MonotonicNs = Callable[[], int]
MonotonicSeconds = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]
DisconnectCallback = Callable[[object], None]
NotificationCallback = Callable[[object, bytearray], None]
CaptureWindowCallback = Callable[[NodeId, int, int, int, int, int], None]


class BleClient(Protocol):
    """Small subset of the Bleak client boundary used by the recorder."""

    @property
    def is_connected(self) -> bool: ...

    @property
    def mtu_size(self) -> int: ...

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def read_gatt_char(self, char_specifier: str) -> bytes | bytearray: ...

    async def write_gatt_char(
        self,
        char_specifier: str,
        data: bytes,
        *,
        response: bool | None = None,
    ) -> None: ...

    async def start_notify(self, char_specifier: str, callback: NotificationCallback) -> None: ...

    async def stop_notify(self, char_specifier: str) -> None: ...


ClientFactory = Callable[[Any, DisconnectCallback], BleClient]


class M1BleError(RuntimeError):
    """Base class for host-side M1 BLE failures."""


class BleTransportError(M1BleError):
    """Raised when the BLE backend cannot complete a transport operation."""


class BleProtocolError(M1BleError):
    """Raised when a BLE value violates the frozen M1 control contract."""


class BleakUnavailableError(M1BleError):
    """Raised when the optional Bleak capture dependency is not installed."""


class IdentityMismatchError(M1BleError):
    """Raised when a peripheral does not prove the requested A/B identity."""


class MtuRequirementError(M1BleError):
    """Raised when the negotiated ATT MTU cannot carry the v1 contract."""


class ClockExchangeError(M1BleError):
    """Raised when a two-way clock exchange cannot be matched and accepted."""


class StatusValidationError(M1BleError):
    """Raised when a status value does not belong to the accepted device stream."""


class RecorderCaptureError(M1BleError):
    """Raised when a received notification cannot be retained in the raw stream."""


@dataclass(frozen=True, slots=True)
class NodeTarget:
    """An explicit physical address-to-node assignment supplied by the operator."""

    node_id: NodeId
    address: str
    expected_hardware_device_id: int | None = None

    def __post_init__(self) -> None:
        try:
            normalized_node_id = NodeId(self.node_id)
        except (TypeError, ValueError) as error:
            raise ValueError(f"unsupported target node id: {self.node_id!r}") from error
        object.__setattr__(self, "node_id", normalized_node_id)
        if not self.address.strip():
            raise ValueError("BLE target address must not be empty")
        if self.expected_hardware_device_id is not None and not (
            0 < self.expected_hardware_device_id < 1 << 64
        ):
            raise ValueError("expected hardware device ID must fit a positive uint64")


@dataclass(frozen=True, slots=True)
class NodeCaptureResult:
    """Immutable result and provenance for one node's capture files."""

    node_id: NodeId
    config: IdentityConfig
    raw_path: Path
    events_path: Path
    raw_sha256: str
    events_sha256: str
    byte_length: int
    packet_count: int
    sample_count: int
    qc: SequenceQcReport
    qc_pass: bool


@dataclass(frozen=True, slots=True)
class SessionResult:
    """Immutable result for one dual-node recorder session."""

    session_id: str
    manifest_path: Path
    node_results: dict[NodeId, NodeCaptureResult]


class _CaptureSink:
    """Own one node's append-only raw stream and event sidecar."""

    def __init__(self, *, node_id: NodeId, raw_path: Path, events_path: Path) -> None:
        self.node_id = node_id
        self.raw_path = raw_path
        self.events_path = events_path
        self.raw_stream = raw_path.open("xb")
        self.events_stream = events_path.open("x", encoding="utf-8")
        self._closed = False

    def write_event(
        self,
        event_type: str,
        *,
        connection_id: str,
        host_monotonic_ns: int,
        **fields: object,
    ) -> None:
        if self._closed:
            raise RecorderCaptureError("cannot write an event after the capture sink is closed")
        record: dict[str, object] = {
            "event": event_type,
            "node_id": int(self.node_id),
            "connection_id": connection_id,
            "host_monotonic_ns": host_monotonic_ns,
            **fields,
        }
        self.events_stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        self.events_stream.flush()

    def append_notification(self, payload: bytes, *, host_monotonic_ns: int) -> int:
        """Append a notification without interpreting or changing its bytes."""

        if self._closed:
            raise RecorderCaptureError("cannot append a notification after the capture sink is closed")
        stream_offset = self.raw_stream.tell()
        try:
            framed = encode_capture_record(payload, host_monotonic_ns=host_monotonic_ns)
        except CaptureFormatError as error:
            raise RecorderCaptureError(str(error)) from error
        self.raw_stream.write(framed)
        self.raw_stream.flush()
        return stream_offset

    def flush(self) -> None:
        if not self._closed:
            self.raw_stream.flush()
            self.events_stream.flush()

    def close(self) -> None:
        if self._closed:
            return
        self.flush()
        self.raw_stream.close()
        self.events_stream.close()
        self._closed = True


class _NodeRecorder:
    """Run one node's connection state machine against a BLE client factory."""

    def __init__(
        self,
        *,
        target: NodeTarget,
        sink: _CaptureSink,
        client_factory: ClientFactory,
        clock_exchange_count: int,
        clock_response_timeout_s: float,
        connection_timeout_s: float,
        recovery_timeout_s: float,
        reconnect_delay_s: float,
        monotonic_ns: MonotonicNs,
        callback_monotonic_ns: MonotonicNs,
        monotonic_seconds: MonotonicSeconds,
        sleep: Sleep,
        capture_window_callback: CaptureWindowCallback | None = None,
        strict_capture_window: bool = False,
    ) -> None:
        self.target = target
        self.sink = sink
        self.client_factory = client_factory
        self.clock_exchange_count = clock_exchange_count
        self.clock_response_timeout_s = clock_response_timeout_s
        self.connection_timeout_s = connection_timeout_s
        self.recovery_timeout_s = recovery_timeout_s
        self.reconnect_delay_s = reconnect_delay_s
        self.monotonic_ns = monotonic_ns
        self.callback_monotonic_ns = callback_monotonic_ns
        self.monotonic_seconds = monotonic_seconds
        self.sleep = sleep
        self.capture_window_callback = capture_window_callback
        self.strict_capture_window = strict_capture_window

        self.client: BleClient | None = None
        self.connection_attempt = 0
        self.connection_id = ""
        self.disconnected = asyncio.Event()
        self.telemetry_enabled = False
        self.clock_responses: asyncio.Queue[tuple[ClockResponse | None, str | None]] = asyncio.Queue()
        self.pending_error: M1BleError | None = None
        self._status_callback_generation: int | None = None
        self.initial_config: IdentityConfig | None = None
        self.current_config: IdentityConfig | None = None
        self.initial_status: Status | None = None
        self.final_status: Status | None = None
        self.packet_count = 0
        self.sample_count = 0
        self._telemetry_callback_count = 0
        self._qc: SequenceQcReport | None = None
        self._qc_pass_result: bool | None = None
        self._capture_window_start_ns: int | None = None
        self._capture_window_end_ns: int | None = None

    async def run(
        self,
        *,
        capture_ready_gate: _CaptureReadyGate,
        stop_event: asyncio.Event | None,
    ) -> NodeCaptureResult:
        primary_error: BaseException | None = None
        try:
            await self._start_connection(is_reconnect=False)
            deadline = await capture_ready_gate.wait(self)
            while self._capture_time_remaining_s(deadline) > 0.0:
                self._raise_pending_error()
                if stop_event is not None and stop_event.is_set():
                    break
                if self.disconnected.is_set():
                    recovery_started = self.monotonic_seconds()
                    recovery_deadline = recovery_started + self.recovery_timeout_s
                    self.sink.write_event(
                        "recovery_start",
                        connection_id=self.connection_id,
                        host_monotonic_ns=self.monotonic_ns(),
                        recovery_timeout_s=self.recovery_timeout_s,
                        recovery_deadline_monotonic_s=recovery_deadline,
                    )
                    await self._reconnect_until(recovery_deadline, stop_event)
                    if self.telemetry_enabled and not self.disconnected.is_set():
                        self.sink.write_event(
                            "recovery_complete",
                            connection_id=self.connection_id,
                            host_monotonic_ns=self.monotonic_ns(),
                            recovery_elapsed_s=self.monotonic_seconds() - recovery_started,
                        )
                    continue
                await self._wait_for_stop_or_disconnect(deadline, stop_event)
                self._raise_pending_error()
        except BaseException as error:
            primary_error = error
            raise
        finally:
            try:
                await self._finish_connection()
            except BaseException:
                if primary_error is None:
                    raise
            finally:
                self.sink.close()

        if self.initial_config is None or self._qc is None or self._qc_pass_result is None:
            raise RecorderCaptureError("capture completed without identity/config and QC state")
        return NodeCaptureResult(
            node_id=self.target.node_id,
            config=self.initial_config,
            raw_path=self.sink.raw_path,
            events_path=self.sink.events_path,
            raw_sha256=_sha256(self.sink.raw_path),
            events_sha256=_sha256(self.sink.events_path),
            byte_length=self.sink.raw_path.stat().st_size,
            packet_count=self.packet_count,
            sample_count=self.sample_count,
            qc=self._qc,
            qc_pass=self._qc_pass_result,
        )

    async def _start_connection(
        self,
        *,
        is_reconnect: bool,
        connection_timeout_s: float | None = None,
    ) -> None:
        attempt_timeout_s = (
            self.connection_timeout_s
            if connection_timeout_s is None
            else connection_timeout_s
        )
        self.connection_attempt += 1
        self.connection_id = f"{self.target.node_id.name.lower()}-{self.connection_attempt}"
        self.disconnected = asyncio.Event()
        self.telemetry_enabled = False
        self._status_callback_generation = None
        self.clock_responses = asyncio.Queue()
        self.pending_error = None
        self.client = None
        try:
            self.client = self.client_factory(self.target.address, self._on_disconnected)
            wait_for_connect_slot = getattr(self.client, "wait_for_connect_slot", None)
            if wait_for_connect_slot is not None:
                # Matrix-runner ordering is setup coordination, not BLE connection
                # time. Do not charge that gate against the connection-attempt timeout.
                await wait_for_connect_slot()
            await asyncio.wait_for(self.client.connect(), timeout=attempt_timeout_s)
            self.sink.write_event(
                "reconnect" if is_reconnect else "connect",
                connection_id=self.connection_id,
                host_monotonic_ns=self.monotonic_ns(),
                address=self.target.address,
                attempt=self.connection_attempt,
            )
            mtu = int(self.client.mtu_size)
            self.sink.write_event(
                "mtu",
                connection_id=self.connection_id,
                host_monotonic_ns=self.monotonic_ns(),
                mtu=mtu,
                required_mtu=REQUIRED_ATT_MTU,
                accepted=mtu >= REQUIRED_ATT_MTU,
            )
            if mtu < REQUIRED_ATT_MTU:
                raise MtuRequirementError(
                    f"negotiated ATT MTU {mtu} is below the M1 requirement of {REQUIRED_ATT_MTU}"
                )

            await self.client.start_notify(IDENTITY_CONFIG_UUID, self._on_identity_notification)
            await self.client.start_notify(CLOCK_EXCHANGE_UUID, self._on_clock_notification)

            config = await self._read_identity(source="read")
            self._validate_identity(config)
            self.current_config = config

            status = await self._read_status(source="read")
            self._validate_status(status, config)
            if self.initial_status is None:
                self.initial_status = status

            await self._perform_clock_exchanges(config)
            # The firmware serializes status and clock indications through one
            # bounded indication slot. Keep status CCC disabled until the clock
            # exchange has finished so a periodic status indication cannot make
            # the first clock write fail with ATT Insufficient Resources.
            status_callback_generation = self.connection_attempt
            self._status_callback_generation = status_callback_generation
            await self.client.start_notify(
                STATUS_UUID,
                self._make_status_notification_callback(
                    generation=status_callback_generation,
                    connection_id=self.connection_id,
                ),
            )
            await self.client.start_notify(TELEMETRY_UUID, self._on_telemetry_notification)
            self.telemetry_enabled = True
            if is_reconnect:
                self.sink.write_event(
                    "telemetry_resume",
                    connection_id=self.connection_id,
                    host_monotonic_ns=self.monotonic_ns(),
                )
            self._raise_pending_error()
        except TimeoutError as error:
            await self._abort_connection()
            raise BleTransportError(
                f"BLE connection establishment timed out after {attempt_timeout_s} "
                f"seconds for {self.target.address}"
            ) from error
        except (M1BleError, ProtocolError):
            await self._abort_connection()
            raise
        except Exception as error:
            await self._abort_connection()
            raise BleTransportError(
                f"BLE connection setup failed for {self.target.address}: {error}"
            ) from error
        except BaseException:
            await self._abort_connection()
            raise

    async def _reconnect_until(self, deadline: float, stop_event: asyncio.Event | None) -> None:
        self.client = None
        self.telemetry_enabled = False
        self._status_callback_generation = None
        while self.monotonic_seconds() < deadline:
            if stop_event is not None and stop_event.is_set():
                return
            remaining = deadline - self.monotonic_seconds()
            if remaining <= 0.0:
                break
            try:
                await self._start_connection(
                    is_reconnect=True,
                    connection_timeout_s=min(self.connection_timeout_s, remaining),
                )
                return
            except (IdentityMismatchError, MtuRequirementError, ClockExchangeError, StatusValidationError):
                raise
            except BleTransportError as error:
                self.sink.write_event(
                    "decode_error",
                    connection_id=self.connection_id,
                    host_monotonic_ns=self.monotonic_ns(),
                    detail=f"reconnect attempt failed: {error}",
                    phase="reconnect",
                )
                remaining = deadline - self.monotonic_seconds()
                if remaining <= 0.0:
                    raise M1BleError("BLE recovery deadline expired") from error
                await self.sleep(min(self.reconnect_delay_s, remaining))
        raise M1BleError("BLE recovery deadline expired")

    async def _wait_for_stop_or_disconnect(
        self,
        deadline: _CaptureDeadline,
        stop_event: asyncio.Event | None,
    ) -> None:
        remaining = max(0.0, self._capture_time_remaining_s(deadline))
        disconnect_task = asyncio.create_task(self.disconnected.wait())
        tasks: set[asyncio.Task[bool]] = {disconnect_task}
        stop_task: asyncio.Task[bool] | None = None
        if stop_event is not None:
            stop_task = asyncio.create_task(stop_event.wait())
            tasks.add(stop_task)
        try:
            await asyncio.wait(
                tasks,
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def _capture_time_remaining_s(self, deadline: _CaptureDeadline) -> float:
        if deadline.callback_monotonic_ns is not None:
            return (
                deadline.callback_monotonic_ns - self.callback_monotonic_ns()
            ) / 1_000_000_000
        return deadline.monotonic_seconds - self.monotonic_seconds()

    async def _finish_connection(self) -> None:
        client = self.client
        if client is None:
            return
        status_stop_attempted = False
        try:
            if self.telemetry_enabled:
                await client.stop_notify(TELEMETRY_UUID)
                self.telemetry_enabled = False

                # Invalidate the callback before asking the backend to unregister it.  A
                # backend may deliver an already queued indication while stop_notify is
                # in flight; that value remains an event, but cannot alter finalization.
                self._status_callback_generation = None
                status_stop_attempted = True
                try:
                    await client.stop_notify(STATUS_UUID)
                except Exception as error:
                    self._write_teardown_error(STATUS_UUID, error)
                    raise

                self.final_status = await self._read_status(source="final")
                if self.current_config is not None:
                    self._validate_status(self.final_status, self.current_config)
                self._write_qc_summary()
        finally:
            if not status_stop_attempted:
                self._status_callback_generation = None
                status_stop_attempted = True
                try:
                    await client.stop_notify(STATUS_UUID)
                except Exception as error:
                    self._write_teardown_error(STATUS_UUID, error)
            for char_uuid in (CLOCK_EXCHANGE_UUID, IDENTITY_CONFIG_UUID):
                try:
                    await client.stop_notify(char_uuid)
                except Exception as error:
                    self._write_teardown_error(char_uuid, error)
            try:
                if client.is_connected:
                    await client.disconnect()
            except Exception as error:
                self.sink.write_event(
                    "decode_error",
                    connection_id=self.connection_id,
                    host_monotonic_ns=self.monotonic_ns(),
                    detail=f"disconnect failed during teardown: {error}",
                    phase="stop",
                )
            finally:
                self.client = None

    async def _abort_connection(self) -> None:
        client = self.client
        self.client = None
        self.telemetry_enabled = False
        self._status_callback_generation = None
        if client is not None:
            try:
                await client.disconnect()
            except Exception as error:
                self.sink.write_event(
                    "decode_error",
                    connection_id=self.connection_id,
                    host_monotonic_ns=self.monotonic_ns(),
                    detail=f"abort disconnect failed: {error}",
                    phase="abort",
                )

    async def _read_identity(self, *, source: str) -> IdentityConfig:
        if self.client is None:
            raise M1BleError("cannot read identity/config without an active client")
        raw = bytes(await self.client.read_gatt_char(IDENTITY_CONFIG_UUID))
        host_time_ns = self.monotonic_ns()
        try:
            config = decode_identity_config(raw)
        except ProtocolError as error:
            self._write_control_event("config", raw, source=source, host_time_ns=host_time_ns, error=error)
            raise BleProtocolError(f"invalid identity/config value: {error}") from error
        self._write_control_event("config", raw, source=source, host_time_ns=host_time_ns, decoded=config)
        return config

    async def _read_status(self, *, source: str) -> Status:
        if self.client is None:
            raise M1BleError("cannot read status without an active client")
        raw = bytes(await self.client.read_gatt_char(STATUS_UUID))
        host_time_ns = self.monotonic_ns()
        try:
            status = decode_status(raw)
        except ProtocolError as error:
            self._write_control_event("status", raw, source=source, host_time_ns=host_time_ns, error=error)
            raise BleProtocolError(f"invalid status value: {error}") from error
        reconciliation_fields = (
            _status_reconciliation_fields(
                self.initial_status,
                status,
                raw_packet_count=self.packet_count,
                raw_sample_count=self.sample_count,
            )
            if source == "final"
            else {}
        )
        self._write_control_event(
            "status",
            raw,
            source=source,
            host_time_ns=host_time_ns,
            decoded=status,
            extra_fields=reconciliation_fields,
        )
        return status

    async def _perform_clock_exchanges(self, config: IdentityConfig) -> None:
        if self.client is None:
            raise M1BleError("cannot exchange clocks without an active client")
        for index in range(self.clock_exchange_count):
            transaction_id = (self.connection_attempt << 16) | (index + 1)
            host_send_ns = self.monotonic_ns()
            request = ClockRequest(transaction_id=transaction_id, host_send_ns=host_send_ns)
            raw_request = encode_clock_request(request)
            self._write_control_event(
                "clock_request",
                raw_request,
                source="write",
                host_time_ns=host_send_ns,
                decoded=request,
            )
            await self.client.write_gatt_char(CLOCK_EXCHANGE_UUID, raw_request, response=True)
            try:
                response, error_text = await asyncio.wait_for(
                    self.clock_responses.get(), timeout=self.clock_response_timeout_s
                )
            except TimeoutError as error:
                raise ClockExchangeError(
                    f"clock exchange transaction {transaction_id} timed out after "
                    f"{self.clock_response_timeout_s} seconds"
                ) from error
            if error_text is not None or response is None:
                raise ClockExchangeError(
                    f"clock exchange transaction {transaction_id} returned an invalid response: {error_text}"
                )
            if response.transaction_id != transaction_id or response.host_send_ns != host_send_ns:
                raise ClockExchangeError(
                    f"clock exchange response does not match transaction {transaction_id}"
                )
            if response.boot_id != config.boot_id or response.clock_epoch != config.clock_epoch:
                raise ClockExchangeError(
                    f"clock exchange transaction {transaction_id} belongs to a different boot/epoch"
                )

    def _on_disconnected(self, _client: object) -> None:
        host_time_ns = self.monotonic_ns()
        if self.client is None or _client is not self.client:
            return
        if self.disconnected.is_set():
            return
        self._status_callback_generation = None
        self.sink.write_event(
            "disconnect",
            connection_id=self.connection_id,
            host_monotonic_ns=host_time_ns,
            address=self.target.address,
        )
        self.disconnected.set()

    def _on_identity_notification(self, _sender: object, data: bytearray) -> None:
        host_time_ns = self.monotonic_ns()
        raw = bytes(data)
        try:
            config = decode_identity_config(raw)
        except ProtocolError as error:
            self._write_control_event("config", raw, source="indication", host_time_ns=host_time_ns, error=error)
            self.pending_error = M1BleError(f"invalid identity/config indication: {error}")
            return
        self._write_control_event("config", raw, source="indication", host_time_ns=host_time_ns, decoded=config)
        try:
            self._validate_identity(config)
        except M1BleError as error:
            self.pending_error = error

    def _make_status_notification_callback(
        self,
        *,
        generation: int,
        connection_id: str,
    ) -> NotificationCallback:
        def callback(sender: object, data: bytearray) -> None:
            self._on_status_notification(
                sender,
                data,
                generation=generation,
                connection_id=connection_id,
            )

        return callback

    def _on_status_notification(
        self,
        _sender: object,
        data: bytearray,
        *,
        generation: int,
        connection_id: str,
    ) -> None:
        host_time_ns = self.monotonic_ns()
        raw = bytes(data)
        callback_is_current = generation == self._status_callback_generation
        try:
            status = decode_status(raw)
        except ProtocolError as error:
            self._write_control_event(
                "status",
                raw,
                source="indication",
                host_time_ns=host_time_ns,
                connection_id=connection_id,
                error=error,
            )
            if callback_is_current:
                self.pending_error = M1BleError(f"invalid status indication: {error}")
            return
        self._write_control_event(
            "status",
            raw,
            source="indication",
            host_time_ns=host_time_ns,
            connection_id=connection_id,
            decoded=status,
        )
        if callback_is_current and self.current_config is not None:
            try:
                self._validate_status(status, self.current_config)
            except M1BleError as error:
                self.pending_error = error

    def _on_clock_notification(self, _sender: object, data: bytearray) -> None:
        host_receive_ns = self.monotonic_ns()
        raw = bytes(data)
        try:
            response = decode_clock_response(raw)
        except ProtocolError as error:
            self._write_control_event(
                "clock_response",
                raw,
                source="indication",
                host_time_ns=host_receive_ns,
                host_receive_monotonic_ns=host_receive_ns,
                error=error,
            )
            self.clock_responses.put_nowait((None, str(error)))
            return
        self._write_control_event(
            "clock_response",
            raw,
            source="indication",
            host_time_ns=host_receive_ns,
            host_receive_monotonic_ns=host_receive_ns,
            decoded=response,
        )
        self.clock_responses.put_nowait((response, None))

    def _on_telemetry_notification(self, _sender: object, data: bytearray) -> None:
        self._telemetry_callback_count += 1
        callback_index = self._telemetry_callback_count
        callback_start_ns = self.callback_monotonic_ns()
        host_callback_start_ns = self.monotonic_ns() if self.strict_capture_window else None
        host_time_ns = callback_start_ns
        window_start_ns = self._capture_window_start_ns
        window_end_ns = self._capture_window_end_ns
        capture_window_accepted = (
            not self.strict_capture_window
            or (
                window_start_ns is not None
                and window_end_ns is not None
                and window_start_ns <= callback_start_ns < window_end_ns
            )
        )
        payload = bytes(data)
        try:
            if not capture_window_accepted:
                return
            try:
                stream_offset = self.sink.append_notification(payload, host_monotonic_ns=host_time_ns)
            except RecorderCaptureError as error:
                self.sink.write_event(
                    "decode_error",
                    connection_id=self.connection_id,
                    host_monotonic_ns=host_time_ns,
                    raw_stream_offset=None,
                    payload_length=len(payload),
                    crc_ok=_crc_status(payload),
                    decode_ok=False,
                    detail=str(error),
                    raw_payload_hex=payload.hex(),
                )
                self.pending_error = error
                return
            try:
                packet = decode_sample_packet(payload)
            except ProtocolError as error:
                self.sink.write_event(
                    "decode_error",
                    connection_id=self.connection_id,
                    host_monotonic_ns=host_time_ns,
                    raw_stream_offset=stream_offset,
                    payload_length=len(payload),
                    crc_ok=_crc_status(payload),
                    decode_ok=False,
                    detail=str(error),
                )
                return

            node_mismatch = packet.node_id is not self.target.node_id
            self.sink.write_event(
                "notify",
                connection_id=self.connection_id,
                host_monotonic_ns=host_time_ns,
                raw_stream_offset=stream_offset,
                payload_length=len(payload),
                decode_ok=True,
                crc_ok=True,
                packet_node_id=int(packet.node_id),
                node_mismatch=node_mismatch,
                packet_sequence=packet.packet_sequence,
                clock_epoch=packet.clock_epoch,
                packet_flags=int(packet.flags),
                sample_sequences=[sample.sequence for sample in packet.samples],
                sample_count=len(packet.samples),
            )
            if node_mismatch:
                return
            self.packet_count += 1
            self.sample_count += len(packet.samples)
        finally:
            callback_end_ns = self.callback_monotonic_ns()
            timing_fields: dict[str, object] = {}
            host_end_ns: int | None = None
            if self.strict_capture_window:
                host_end_ns = self.monotonic_ns()
                timing_fields = {
                    "capture_clock_domain": "perf_counter_ns",
                    "capture_window_check_perf_counter_ns": callback_start_ns,
                    "capture_window_accepted": capture_window_accepted,
                    "callback_start_perf_counter_ns": callback_start_ns,
                    "callback_end_perf_counter_ns": callback_end_ns,
                    "callback_start_host_monotonic_ns": host_callback_start_ns,
                    "callback_end_host_monotonic_ns": host_end_ns,
                }
            self.sink.write_event(
                "notify_callback_timing",
                connection_id=self.connection_id,
                host_monotonic_ns=host_time_ns,
                callback_index=callback_index,
                callback_start_monotonic_ns=callback_start_ns,
                callback_end_monotonic_ns=callback_end_ns,
                callback_duration_ns=callback_end_ns - callback_start_ns,
                payload_length=len(payload),
                **timing_fields,
            )

    def _write_qc_summary(self) -> None:
        self.sink.flush()
        with self.sink.raw_path.open("rb") as raw_stream:
            report = audit_capture_stream(raw_stream, expected_node_id=self.target.node_id)
        self._qc = report
        status_fields = _status_reconciliation_fields(
            self.initial_status,
            self.final_status,
            raw_packet_count=self.packet_count,
            raw_sample_count=self.sample_count,
        )
        qc_reasons: list[str] = []
        if self.sample_count == 0:
            qc_reasons.append("no_samples")
        sequence_qc_pass = _qc_pass(report)
        self._qc_pass_result = sequence_qc_pass and bool(status_fields["status_qc_pass"])
        self.sink.write_event(
            "qc_summary",
            connection_id=self.connection_id,
            host_monotonic_ns=self.monotonic_ns(),
            records_seen=report.records_seen,
            packets_decoded=report.packets_decoded,
            samples_decoded=report.samples_decoded,
            decode_errors=report.decode_errors,
            framing_errors=report.framing_errors,
            packets_missing=report.packets_missing,
            samples_missing=report.samples_missing,
            packet_duplicates=report.packet_duplicates,
            sample_duplicates=report.sample_duplicates,
            packet_reordered=report.packet_reordered,
            sample_reordered=report.sample_reordered,
            timestamp_duplicates=report.timestamp_duplicates,
            timestamp_reordered=report.timestamp_reordered,
            epoch_changes=report.epoch_changes,
            node_mismatches=report.node_mismatches,
            qc_reasons=qc_reasons,
            **status_fields,
            qc_pass=self._qc_pass_result,
        )

    def _write_teardown_error(self, characteristic_uuid: str, error: Exception) -> None:
        self.sink.write_event(
            "decode_error",
            connection_id=self.connection_id,
            host_monotonic_ns=self.monotonic_ns(),
            detail=f"stop notification failed for {characteristic_uuid}: {error}",
            characteristic_uuid=characteristic_uuid,
            phase="stop",
        )

    def _write_control_event(
        self,
        event_type: str,
        raw: bytes,
        *,
        source: str,
        host_time_ns: int,
        decoded: object | None = None,
        error: Exception | None = None,
        extra_fields: Mapping[str, object] | None = None,
        connection_id: str | None = None,
        **fields: object,
    ) -> None:
        event_fields: dict[str, object] = {
            "source": source,
            "raw_value_hex": raw.hex(),
            "crc_ok": _crc_status(raw),
            "decode_ok": error is None,
            **fields,
        }
        if extra_fields is not None:
            event_fields.update(extra_fields)
        if decoded is not None:
            event_fields.update(_control_fields(decoded))
        if error is not None:
            event_fields["detail"] = str(error)
        self.sink.write_event(
            event_type,
            connection_id=self.connection_id if connection_id is None else connection_id,
            host_monotonic_ns=host_time_ns,
            **event_fields,
        )

    def _validate_identity(self, config: IdentityConfig) -> None:
        if config.node_id is not self.target.node_id:
            raise IdentityMismatchError(
                f"identity/config node id {config.node_id.name} does not match target node id "
                f"{self.target.node_id.name}"
            )
        if config.batch_size != REQUIRED_BATCH_SIZE:
            raise IdentityMismatchError(
                f"identity/config batch size {config.batch_size} does not match required v1 batch size "
                f"{REQUIRED_BATCH_SIZE}"
            )
        if config.firmware_git_commit == bytes(20):
            raise IdentityMismatchError("identity/config firmware Git commit must be nonzero")
        if (
            self.target.expected_hardware_device_id is not None
            and config.hardware_device_id != self.target.expected_hardware_device_id
        ):
            raise IdentityMismatchError(
                "identity/config hardware device ID does not match the explicit target assignment"
            )
        if self.initial_config is None:
            self.initial_config = config
            return
        if config.hardware_device_id != self.initial_config.hardware_device_id:
            raise IdentityMismatchError("reconnected peripheral reported a different hardware device ID")
        if _configuration_signature(config) != _configuration_signature(self.initial_config):
            raise IdentityMismatchError("reconnected peripheral reported a different active configuration")

    @staticmethod
    def _validate_status(status: Status, config: IdentityConfig) -> None:
        if status.node_id is not config.node_id:
            raise StatusValidationError("status node id does not match identity/config")
        if status.boot_id != config.boot_id:
            raise StatusValidationError("status boot ID does not match identity/config")
        if status.clock_epoch != config.clock_epoch:
            raise StatusValidationError("status clock epoch does not match identity/config")
        if status.acquisition_state is AcquisitionState.ERROR or status.flags & StatusFlags.FATAL_ERROR_LATCHED:
            raise StatusValidationError("device status reports a fatal acquisition error")

    def _raise_pending_error(self) -> None:
        if self.pending_error is not None:
            raise self.pending_error

    def _arm_capture_window(self, start_ns: int, end_ns: int) -> None:
        if not self.strict_capture_window:
            raise M1BleError("cannot arm a capture window when strict enforcement is disabled")
        if end_ns <= start_ns:
            raise M1BleError("capture-window deadline must follow its start")
        self._capture_window_start_ns = start_ns
        self._capture_window_end_ns = end_ns


@dataclass(frozen=True, slots=True)
class _CaptureDeadline:
    monotonic_seconds: float
    callback_monotonic_ns: int | None


class _CaptureReadyGate:
    """Arm strict capture bounds synchronously before releasing ready recorders."""

    def __init__(self, *, recorders: Sequence[_NodeRecorder], duration_s: float) -> None:
        if not recorders:
            raise ValueError("capture-ready gate requires at least one recorder")
        if duration_s <= 0.0:
            raise ValueError("capture duration must be positive")
        self.recorders = tuple(recorders)
        self._recorder_ids = {id(recorder) for recorder in self.recorders}
        if len(self._recorder_ids) != len(self.recorders):
            raise ValueError("capture-ready gate recorders must be distinct")
        self.duration_s = duration_s
        self._arrived: set[int] = set()
        self._ready = asyncio.Event()
        self._deadline: _CaptureDeadline | None = None
        self._error: BaseException | None = None

    async def wait(self, recorder: _NodeRecorder) -> _CaptureDeadline:
        recorder_id = id(recorder)
        if recorder_id not in self._recorder_ids:
            raise M1BleError("recorder is not registered with this capture-ready gate")
        if recorder_id in self._arrived:
            raise M1BleError("recorder arrived at the capture-ready gate more than once")
        self._arrived.add(recorder_id)
        if len(self._arrived) == len(self.recorders):
            try:
                self._open_capture_window()
            except BaseException as error:
                self._error = error
                self._ready.set()
                raise
        else:
            await self._ready.wait()

        if self._error is not None:
            raise self._error
        if self._deadline is None:
            raise M1BleError("capture-ready gate released without a deadline")
        return self._deadline

    def _open_capture_window(self) -> None:
        strict_modes = {recorder.strict_capture_window for recorder in self.recorders}
        if len(strict_modes) != 1:
            raise M1BleError("capture-ready gate recorders disagree on strict window enforcement")
        strict_capture_window = strict_modes.pop()
        if not strict_capture_window and any(
            recorder.capture_window_callback is not None for recorder in self.recorders
        ):
            raise M1BleError("capture-window callback requires strict capture-window enforcement")

        start_seconds = self.recorders[0].monotonic_seconds()
        deadline_seconds = start_seconds + self.duration_s
        deadline_callback_ns: int | None = None
        if strict_capture_window:
            host_start_before_ns = self.recorders[0].monotonic_ns()
            start_ns = self.recorders[0].callback_monotonic_ns()
            host_start_after_ns = self.recorders[0].monotonic_ns()
            host_start_ns = host_start_before_ns
            host_deadline_ns = host_start_ns + round(self.duration_s * 1_000_000_000)
            clock_pair_uncertainty_ns = host_start_after_ns - host_start_before_ns
            end_ns = start_ns + round(self.duration_s * 1_000_000_000)
            deadline_callback_ns = end_ns
            for recorder in self.recorders:
                recorder._arm_capture_window(start_ns, end_ns)
            for recorder in self.recorders:
                if recorder.capture_window_callback is not None:
                    recorder.capture_window_callback(
                        recorder.target.node_id,
                        start_ns,
                        end_ns,
                        host_start_ns,
                        host_deadline_ns,
                        clock_pair_uncertainty_ns,
                    )

        self._deadline = _CaptureDeadline(deadline_seconds, deadline_callback_ns)
        self._ready.set()


class M1BleSessionRecorder:
    """Coordinate two explicit BLE node targets and create a v0.1 manifest."""

    def __init__(
        self,
        *,
        targets: Sequence[NodeTarget],
        output_dir: Path,
        session_id: str,
        client_factory: ClientFactory | None = None,
        clock_exchange_count: int = 3,
        clock_response_timeout_s: float = 2.0,
        connection_timeout_s: float = DEFAULT_CONNECTION_TIMEOUT_S,
        recovery_timeout_s: float = DEFAULT_RECOVERY_TIMEOUT_S,
        reconnect_delay_s: float = 0.25,
        monotonic_ns: MonotonicNs = time.monotonic_ns,
        callback_monotonic_ns: MonotonicNs = time.perf_counter_ns,
        monotonic_seconds: MonotonicSeconds = time.monotonic,
        sleep: Sleep = asyncio.sleep,
        test_side: str | None = None,
        mounting_protocol_version: str | None = None,
        notes: str | None = None,
    ) -> None:
        if len(targets) != 2:
            raise ValueError("M1 BLE session requires exactly two node targets")
        target_ids = {target.node_id for target in targets}
        if target_ids != {NodeId.A, NodeId.B}:
            raise ValueError("M1 BLE session targets must contain exactly Node A and Node B")
        if len({target.address for target in targets}) != len(targets):
            raise ValueError("M1 BLE session target addresses must be distinct")
        if not session_id.strip():
            raise ValueError("session ID must not be empty")
        if not 1 <= clock_exchange_count <= 32:
            raise ValueError("clock exchange count must be between 1 and 32")
        if clock_response_timeout_s <= 0.0:
            raise ValueError("clock response timeout must be positive")
        if connection_timeout_s <= 0.0:
            raise ValueError("connection establishment timeout must be positive")
        if recovery_timeout_s <= 0.0:
            raise ValueError("recovery timeout must be positive")
        if reconnect_delay_s < 0.0:
            raise ValueError("reconnect delay must not be negative")
        if test_side not in {None, "left", "right"}:
            raise ValueError("test side must be left, right or null")

        self.targets = tuple(sorted(targets, key=lambda target: int(target.node_id)))
        self.output_dir = output_dir
        self.session_id = session_id
        self.client_factory = client_factory or create_bleak_client
        self.clock_exchange_count = clock_exchange_count
        self.clock_response_timeout_s = clock_response_timeout_s
        self.connection_timeout_s = connection_timeout_s
        self.recovery_timeout_s = recovery_timeout_s
        self.reconnect_delay_s = reconnect_delay_s
        self.monotonic_ns = monotonic_ns
        self.callback_monotonic_ns = callback_monotonic_ns
        self.monotonic_seconds = monotonic_seconds
        self.sleep = sleep
        self.test_side = test_side
        self.mounting_protocol_version = mounting_protocol_version
        self.notes = notes

    async def capture(
        self,
        *,
        duration_s: float,
        stop_event: asyncio.Event | None = None,
        capture_window_callback: CaptureWindowCallback | None = None,
        strict_capture_window: bool = False,
    ) -> SessionResult:
        if duration_s <= 0.0:
            raise ValueError("capture duration must be positive")
        raw_dir = self.output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        recorders = [
            _NodeRecorder(
                target=target,
                sink=_CaptureSink(
                    node_id=target.node_id,
                    raw_path=raw_dir / f"node-{target.node_id.name.lower()}.kimu",
                    events_path=raw_dir / f"node-{target.node_id.name.lower()}.events.ndjson",
                ),
                client_factory=self.client_factory,
                clock_exchange_count=self.clock_exchange_count,
                clock_response_timeout_s=self.clock_response_timeout_s,
                connection_timeout_s=self.connection_timeout_s,
                recovery_timeout_s=self.recovery_timeout_s,
                reconnect_delay_s=self.reconnect_delay_s,
                monotonic_ns=self.monotonic_ns,
                callback_monotonic_ns=self.callback_monotonic_ns,
                monotonic_seconds=self.monotonic_seconds,
                sleep=self.sleep,
                capture_window_callback=capture_window_callback,
                strict_capture_window=strict_capture_window,
            )
            for target in self.targets
        ]
        capture_ready_gate = _CaptureReadyGate(recorders=recorders, duration_s=duration_s)
        tasks = [
            asyncio.create_task(
                recorder.run(
                    capture_ready_gate=capture_ready_gate,
                    stop_event=stop_event,
                )
            )
            for recorder in recorders
        ]
        try:
            results = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        node_results = {result.node_id: result for result in results}
        manifest = {
            "schema_version": "kineimu.m1.session/0.1",
            "example_only": False,
            "session_id": self.session_id,
            "created_utc": _utc_now(),
            "test_side": self.test_side,
            "protocol_version": "kineimu.m1.ble/1",
            "mounting_protocol_version": self.mounting_protocol_version,
            "nodes": [_manifest_node(node_results[target.node_id].config) for target in self.targets],
            "streams": [_manifest_stream(node_results[target.node_id], self.output_dir) for target in self.targets],
            "clock_mapping_artifacts": [],
            "notes": self.notes,
        }
        manifest_path = self.output_dir / "session.json"
        with manifest_path.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        return SessionResult(
            session_id=self.session_id,
            manifest_path=manifest_path,
            node_results=node_results,
        )

@dataclass(frozen=True, slots=True)
class DiscoveredBleDevice:
    """A scanner result; discovery order and name are never a node assignment."""

    address: str
    name: str | None
    rssi: int | None


async def discover_m1_devices(*, timeout_s: float = 5.0) -> tuple[DiscoveredBleDevice, ...]:
    """Discover peripherals advertising the M1 service without assigning A/B roles."""

    if timeout_s <= 0.0:
        raise ValueError("BLE discovery timeout must be positive")
    bleak = _load_bleak()
    scanner = bleak.BleakScanner
    discovered: Any = await scanner.discover(
        timeout=timeout_s,
        service_uuids=[M1_SERVICE_UUID],
        return_adv=True,
    )
    devices: list[DiscoveredBleDevice] = []
    if isinstance(discovered, dict):
        values = discovered.values()
        for item in values:
            device, advertisement = item
            devices.append(
                DiscoveredBleDevice(
                    address=str(device.address),
                    name=getattr(device, "name", None),
                    rssi=getattr(advertisement, "rssi", None),
                )
            )
    else:
        for device in discovered:
            devices.append(
                DiscoveredBleDevice(
                    address=str(device.address),
                    name=getattr(device, "name", None),
                    rssi=getattr(device, "rssi", None),
                )
            )
    return tuple(sorted(devices, key=lambda device: device.address))


async def discover_m1_ble_device(address: str, *, timeout_s: float = 5.0) -> Any:
    """Return the exact fresh Bleak BLEDevice found by an M1-filtered scan."""

    if not address:
        raise ValueError("BLE address must be non-empty")
    if timeout_s <= 0.0:
        raise ValueError("BLE discovery timeout must be positive")
    scanner = _load_bleak().BleakScanner
    discovered: Any = await asyncio.wait_for(
        scanner.discover(
            timeout=timeout_s,
            service_uuids=[M1_SERVICE_UUID],
            return_adv=True,
        ),
        # Bleak's discover() first waits for timeout_s, then stops the scanner
        # while leaving its async context. Allow bounded time for that cleanup
        # instead of cancelling it at the exact same deadline as the scan.
        timeout=timeout_s + M1_SCAN_CLEANUP_GRACE_S,
    )
    if isinstance(discovered, Mapping):
        devices = [item[0] for item in discovered.values()]
    else:
        devices = list(discovered)
    matches = [
        device
        for device in devices
        if str(getattr(device, "address", "")).casefold() == address.casefold()
    ]
    if len(matches) != 1:
        raise BleTransportError(
            f"M1 scan expected one fresh BLEDevice for {address}, found {len(matches)}"
        )
    return matches[0]


class _BleakClientAdapter:
    """Keep backend-specific disconnect handling outside the recorder state machine."""

    def __init__(
        self,
        client: Any,
        disconnected_callback: DisconnectCallback,
        operation_timing_sink: Callable[..., None] | None = None,
    ) -> None:
        self._client = client
        self._disconnected_callback = disconnected_callback
        self._operation_timing_sink = operation_timing_sink
        self._explicit_disconnect_in_progress = False
        self._disconnect_callback_pending = False
        self._ignore_late_disconnect_callbacks = False
        self._active_notifications: list[str] = []
        self._operation_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return bool(self._client.is_connected)

    @property
    def mtu_size(self) -> int:
        return int(self._client.mtu_size)

    async def connect(self) -> None:
        connect_started_ns = time.perf_counter_ns()
        backend = getattr(self._client, "_backend", None)
        get_services = getattr(backend, "_get_services", None)
        original_get_services = get_services
        timing_sink = self._operation_timing_sink
        timing_hook_installed = False
        first_gatt_started_ns: int | None = None
        last_gatt_finished_ns: int | None = None
        gatt_call_count = 0

        if (
            timing_sink is not None
            and backend is not None
            and callable(original_get_services)
        ):
            async def timed_get_services(*args: object, **kwargs: object) -> Any:
                nonlocal first_gatt_started_ns, last_gatt_finished_ns, gatt_call_count
                started_ns = time.perf_counter_ns()
                if first_gatt_started_ns is None:
                    first_gatt_started_ns = started_ns
                gatt_call_count += 1
                try:
                    return await original_get_services(*args, **kwargs)
                finally:
                    finished_ns = time.perf_counter_ns()
                    last_gatt_finished_ns = finished_ns
                    timing_sink(
                        "ble_gatt_service_discovery",
                        call_index=gatt_call_count,
                        duration_ns=finished_ns - started_ns,
                        setup_elapsed_ns_before_gatt=started_ns - connect_started_ns,
                        host_monotonic_ns=time.monotonic_ns(),
                    )

            backend._get_services = timed_get_services
            timing_hook_installed = True
        elif (
            timing_sink is not None
            and backend is not None
            and type(backend).__module__.startswith("bleak.backends.winrt")
        ):
            timing_sink(
                "ble_gatt_service_discovery_timing_unavailable",
                host_monotonic_ns=time.monotonic_ns(),
                backend=type(backend).__qualname__,
            )
            raise BleTransportError(
                "Bleak WinRT backend lacks the GATT discovery timing hook"
            )

        error: str | None = None
        try:
            await self._client.connect()
        except asyncio.CancelledError:
            error = "CancelledError: connect was cancelled"
            raise
        except Exception as caught:
            error = f"{type(caught).__name__}: {caught}"
            raise
        finally:
            finished_ns = time.perf_counter_ns()
            if timing_hook_installed and backend is not None:
                backend._get_services = original_get_services
            if timing_sink is not None:
                timing_sink(
                    "ble_connect_total",
                    duration_ns=finished_ns - connect_started_ns,
                    os_connect_setup_ns=(
                        None
                        if first_gatt_started_ns is None
                        else first_gatt_started_ns - connect_started_ns
                    ),
                    post_gatt_setup_ns=(
                        None
                        if last_gatt_finished_ns is None
                        else finished_ns - last_gatt_finished_ns
                    ),
                    gatt_call_count=gatt_call_count,
                    succeeded=error is None,
                    error=error,
                    host_monotonic_ns=time.monotonic_ns(),
                )

    async def disconnect(self) -> None:
        async with self._operation_lock:
            was_connected = bool(getattr(self._client, "is_connected", False))
            self._disconnect_callback_pending = False
            self._ignore_late_disconnect_callbacks = False
            self._explicit_disconnect_in_progress = True
            try:
                try:
                    await self._stop_winrt_notifications()
                finally:
                    _release_winrt_maintain_connection(self._client)
                    await self._client.disconnect()
            finally:
                self._explicit_disconnect_in_progress = False
                should_notify = was_connected or self._disconnect_callback_pending
                self._disconnect_callback_pending = False
                self._ignore_late_disconnect_callbacks = True
                self._active_notifications.clear()
                if should_notify:
                    self._disconnected_callback(self)

    def _handle_disconnected(self) -> None:
        if self._explicit_disconnect_in_progress:
            self._disconnect_callback_pending = True
            return
        if self._ignore_late_disconnect_callbacks:
            return
        self._disconnected_callback(self)

    async def read_gatt_char(self, char_specifier: str) -> bytes | bytearray:
        return cast(bytes | bytearray, await self._client.read_gatt_char(char_specifier))

    async def write_gatt_char(
        self,
        char_specifier: str,
        data: bytes,
        *,
        response: bool | None = None,
    ) -> None:
        await self._client.write_gatt_char(char_specifier, data, response=response)

    async def start_notify(self, char_specifier: str, callback: NotificationCallback) -> None:
        async with self._operation_lock:
            await self._client.start_notify(char_specifier, callback)
            if char_specifier not in self._active_notifications:
                self._active_notifications.append(char_specifier)

    async def stop_notify(self, char_specifier: str) -> None:
        async with self._operation_lock:
            if char_specifier not in self._active_notifications:
                return
            await self._client.stop_notify(char_specifier)
            self._active_notifications.remove(char_specifier)

    async def _stop_winrt_notifications(self) -> None:
        if not _is_winrt_client(self._client):
            return
        for char_specifier in tuple(self._active_notifications):
            try:
                await self._client.stop_notify(char_specifier)
            except Exception:
                # Disconnect must still release the GATT session if a CCCD write
                # races a link loss or a partially-created notification handle.
                pass
            finally:
                if char_specifier in self._active_notifications:
                    self._active_notifications.remove(char_specifier)


def _is_winrt_client(client: Any) -> bool:
    backend = getattr(client, "_backend", None)
    return backend is not None and type(backend).__module__.startswith("bleak.backends.winrt")


def _release_winrt_maintain_connection(client: Any) -> None:
    """Release WinRT's keep-connected flag before Bleak closes its GATT session.

    Bleak 3.x synthesizes its disconnect callback before closing the WinRT
    session.  Setting ``maintain_connection`` false first lets the peripheral
    observe the link release while Bleak retains its normal teardown order:
    notification handlers, services, GATT session, and requester.  Keeping
    that order is important when telemetry notifications are active.
    """

    if not _is_winrt_client(client):
        return
    backend = client._backend
    session = getattr(backend, "_session", None)
    if session is None:
        return
    try:
        session.maintain_connection = False
    except (AttributeError, OSError, RuntimeError):
        # The regular Bleak disconnect path remains the fallback if the
        # optional WinRT property is unavailable or already closed.
        return



def create_bleak_client(
    device: Any,
    disconnected_callback: DisconnectCallback,
    *,
    services: Sequence[str] | None = None,
    operation_timing_sink: Callable[..., None] | None = None,
) -> BleClient:
    """Create the real Bleak client lazily so codec/QC users need no BLE extra."""

    bleak = _load_bleak()
    client_type = bleak.BleakClient
    adapter_holder: dict[str, _BleakClientAdapter] = {}

    def on_disconnected(_client: object) -> None:
        adapter = adapter_holder.get("adapter")
        if adapter is not None:
            adapter._handle_disconnected()

    client_kwargs: dict[str, object] = {"disconnected_callback": on_disconnected}
    if services is not None:
        client_kwargs["services"] = list(services)
    client = client_type(device, **client_kwargs)
    adapter = _BleakClientAdapter(
        client, disconnected_callback, operation_timing_sink=operation_timing_sink
    )
    adapter_holder["adapter"] = adapter
    return adapter


def _load_bleak() -> Any:
    try:
        return importlib.import_module("bleak")
    except ModuleNotFoundError as error:
        raise BleakUnavailableError(
            "Bleak is required for host BLE capture; install the ble extra with "
            "uv sync --extra ble --frozen"
        ) from error


def _configuration_signature(config: IdentityConfig) -> tuple[object, ...]:
    return (
        config.node_id,
        config.timestamp_source,
        config.firmware_version,
        config.batch_size,
        config.config_generation,
        config.hardware_device_id,
        config.firmware_git_commit,
        config.timer_frequency_hz,
        config.accel_odr_millihz,
        config.gyro_odr_millihz,
        config.accel_range_mg,
        config.gyro_range_mdps,
        config.sensor_registers,
    )


def _control_fields(value: object) -> dict[str, object]:
    if isinstance(value, IdentityConfig):
        return {
            "node_id": int(value.node_id),
            "timestamp_source": _timestamp_source_name(value.timestamp_source),
            "firmware_version": list(value.firmware_version),
            "batch_size": value.batch_size,
            "config_generation": value.config_generation,
            "clock_epoch": value.clock_epoch,
            "boot_id": value.boot_id,
            "hardware_device_id": value.hardware_device_id,
            "firmware_git_commit": value.firmware_git_commit.hex(),
            "timer_frequency_hz": value.timer_frequency_hz,
            "accel_odr_millihz": value.accel_odr_millihz,
            "gyro_odr_millihz": value.gyro_odr_millihz,
            "accel_range_mg": value.accel_range_mg,
            "gyro_range_mdps": value.gyro_range_mdps,
            "sensor_registers_hex": value.sensor_registers.hex(),
        }
    if isinstance(value, ClockRequest):
        return {
            "transaction_id": value.transaction_id,
            "host_send_ns": value.host_send_ns,
        }
    if isinstance(value, ClockResponse):
        return {
            "transaction_id": value.transaction_id,
            "host_send_ns": value.host_send_ns,
            "boot_id": value.boot_id,
            "clock_epoch": value.clock_epoch,
            "device_receive_us": value.device_receive_us,
            "device_indication_queued_us": value.device_indication_queued_us,
        }
    if isinstance(value, Status):
        return {
            "node_id": int(value.node_id),
            "acquisition_state": _acquisition_state_name(value.acquisition_state),
            "status_flags": int(value.flags),
            "boot_id": value.boot_id,
            "clock_epoch": value.clock_epoch,
            "status_sequence": value.status_sequence,
            "last_sample_sequence": value.last_sample_sequence,
            "last_packet_sequence": value.last_packet_sequence,
            "samples_acquired": value.samples_acquired,
            "packets_generated": value.packets_generated,
            "sensor_fifo_overruns": value.sensor_fifo_overruns,
            "firmware_queue_overruns": value.firmware_queue_overruns,
            "transport_backpressure_events": value.transport_backpressure_events,
            "samples_dropped_before_packetization": value.samples_dropped_before_packetization,
            "acquisition_buffer_high_water_samples": value.acquisition_buffer_high_water_samples,
            "transport_queue_high_water_packets": value.transport_queue_high_water_packets,
            "last_error_code": value.last_error_code,
        }
    raise TypeError(f"unsupported control value type: {type(value).__name__}")


def _timestamp_source_name(value: TimestampSource) -> str:
    return {
        TimestampSource.MCU_DRDY_ISR: "mcu_drdy_isr",
        TimestampSource.SENSOR_INTERNAL: "sensor_internal",
        TimestampSource.RECONSTRUCTED: "reconstructed",
    }[value]


def _acquisition_state_name(value: AcquisitionState) -> str:
    return {
        AcquisitionState.IDLE: "idle",
        AcquisitionState.ARMED: "armed",
        AcquisitionState.STREAMING: "streaming",
        AcquisitionState.ERROR: "error",
    }[value]


_STATUS_LOSS_COUNTERS = (
    "sensor_fifo_overruns",
    "firmware_queue_overruns",
    "transport_backpressure_events",
    "samples_dropped_before_packetization",
)


def _status_reconciliation_fields(
    initial: Status | None,
    final: Status | None,
    *,
    raw_packet_count: int,
    raw_sample_count: int,
) -> dict[str, object]:
    if initial is None or final is None:
        return {
            "status_reconciliation_available": False,
            "status_qc_pass": False,
        }

    packet_delta = final.packets_generated - initial.packets_generated
    sample_delta = final.samples_acquired - initial.samples_acquired
    counter_deltas = {
        name: int(getattr(final, name)) - int(getattr(initial, name))
        for name in _STATUS_LOSS_COUNTERS
    }
    counters_saturated = bool(
        (initial.flags | final.flags) & StatusFlags.COUNTERS_SATURATED
    )
    status_counters_clear = (
        not counters_saturated
        and final.last_error_code == 0
        and all(delta == 0 for delta in counter_deltas.values())
    )
    counter_reconciliation_ok = (
        packet_delta == raw_packet_count
        and sample_delta == raw_sample_count
        and all(delta >= 0 for delta in counter_deltas.values())
    )
    return {
        "status_reconciliation_available": True,
        "counter_baseline_packets_generated": initial.packets_generated,
        "counter_baseline_samples_acquired": initial.samples_acquired,
        "status_packets_generated": final.packets_generated,
        "status_samples_acquired": final.samples_acquired,
        "status_packet_delta": packet_delta,
        "status_sample_delta": sample_delta,
        "raw_packet_count": raw_packet_count,
        "raw_sample_count": raw_sample_count,
        "status_counter_deltas": counter_deltas,
        "status_counters_saturated": counters_saturated,
        "status_counters_clear": status_counters_clear,
        "status_last_error_code": final.last_error_code,
        "counter_reconciliation_ok": counter_reconciliation_ok,
        "status_qc_pass": counter_reconciliation_ok and status_counters_clear,
    }


def _manifest_node(config: IdentityConfig) -> dict[str, object]:
    node_name = config.node_id.name
    is_thorax = config.node_id is NodeId.A
    return {
        "node_id": node_name,
        "role": "thorax" if is_thorax else "upper_arm",
        "device_id": f"{config.hardware_device_id:016x}",
        "board_model": "Seeed Studio XIAO nRF52840 Sense",
        "board_revision": None,
        "imu_model": "LSM6DS3TR-C",
        "firmware_version": ".".join(str(part) for part in config.firmware_version),
        "firmware_git_commit": config.firmware_git_commit.hex(),
        "driver": DRIVER_NAME,
        "transport": "ble",
        "clock_id": f"nrf52840-device-{config.hardware_device_id:016x}",
        "clock_epoch_initial": config.clock_epoch,
        "timestamp_source": _timestamp_source_name(config.timestamp_source),
        "sampling_rate_hz_nominal": 100,
        "accel_odr_hz": config.accel_odr_millihz / 1000.0,
        "gyro_odr_hz": config.gyro_odr_millihz / 1000.0,
        "accel_range_g": config.accel_range_mg / 1000.0,
        "gyro_range_dps": config.gyro_range_mdps / 1000.0,
        "filter_config": {
            "register_order": REGISTER_ORDER,
            "register_snapshot_hex": config.sensor_registers.hex(),
        },
        "calibration_id": None,
        "alignment_id": None,
        "placement": "thorax" if is_thorax else "upper_arm",
    }


def _manifest_stream(result: NodeCaptureResult, session_root: Path) -> dict[str, object]:
    return {
        "node_id": result.node_id.name,
        "raw_path": _manifest_relative_path(result.raw_path, session_root),
        "raw_sha256": result.raw_sha256,
        "transport_events_path": _manifest_relative_path(result.events_path, session_root),
        "transport_events_sha256": result.events_sha256,
        "byte_length": result.byte_length,
        "packet_count": result.packet_count,
        "sample_count": result.sample_count,
    }


def _manifest_relative_path(path: Path, session_root: Path) -> str:
    try:
        return path.relative_to(session_root).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _crc_status(raw: bytes) -> bool | None:
    """Return CRC validity when the trailing CRC field is available."""

    if len(raw) < 4:
        return None
    return crc32c(raw[:-4]) == int.from_bytes(raw[-4:], "little")


def _qc_pass(report: SequenceQcReport) -> bool:
    return (
        report.samples_decoded > 0
        and report.decode_errors == 0
        and report.framing_errors == 0
        and report.packets_missing == 0
        and report.samples_missing == 0
        and report.packet_duplicates == 0
        and report.sample_duplicates == 0
        and report.packet_reordered == 0
        and report.sample_reordered == 0
        and report.timestamp_duplicates == 0
        and report.timestamp_reordered == 0
        and report.node_mismatches == 0
    )
