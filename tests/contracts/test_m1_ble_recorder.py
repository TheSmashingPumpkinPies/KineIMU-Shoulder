"""Behavioural tests for the M1 host BLE central/recorder."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from experiments import m1_ble_link_matrix
from experiments.m1_transport_experiment import EventLog
from kineimu_shoulder.io.m1_capture import iter_capture_records
from kineimu_shoulder.io.m1_control import (
    AcquisitionState,
    ClockResponse,
    IdentityConfig,
    Status,
    StatusFlags,
    TimestampSource,
    encode_clock_response,
    encode_identity_config,
    encode_status,
)
from kineimu_shoulder.io.m1_packet import (
    NodeId,
    Sample,
    SampleFlags,
    SamplePacket,
    encode_sample_packet,
)

IDENTITY_UUID = "f7d20002-4b49-4e45-494d-552d53484c44"
TELEMETRY_UUID = "f7d20003-4b49-4e45-494d-552d53484c44"
CLOCK_UUID = "f7d20004-4b49-4e45-494d-552d53484c44"
STATUS_UUID = "f7d20005-4b49-4e45-494d-552d53484c44"


def make_identity(node_id: NodeId, hardware_device_id: int) -> bytes:
    return encode_identity_config(
        IdentityConfig(
            node_id=node_id,
            timestamp_source=TimestampSource.MCU_DRDY_ISR,
            firmware_version=(0, 1, 0),
            batch_size=4,
            config_generation=0,
            clock_epoch=0,
            boot_id=0x0102_0304_0506_0708 + int(node_id),
            hardware_device_id=hardware_device_id,
            firmware_git_commit=bytes(range(1, 21)),
            timer_frequency_hz=32_768,
            accel_odr_millihz=104_000,
            gyro_odr_millihz=104_000,
            accel_range_mg=4_000,
            gyro_range_mdps=500_000,
            sensor_registers=bytes(range(19)),
        )
    )


def make_status(
    node_id: NodeId,
    *,
    boot_id: int,
    samples_acquired: int = 0,
    packets_generated: int = 0,
    state: AcquisitionState = AcquisitionState.ARMED,
    flags: StatusFlags | None = None,
    sensor_fifo_overruns: int = 0,
    firmware_queue_overruns: int = 0,
    transport_backpressure_events: int = 0,
    samples_dropped_before_packetization: int = 0,
    last_error_code: int = 0,
    status_sequence: int = 1,
) -> bytes:
    status_flags = flags
    if status_flags is None:
        status_flags = StatusFlags.SENSOR_READY | (
            StatusFlags.SAMPLING_ACTIVE if state is AcquisitionState.STREAMING else StatusFlags.NONE
        )
    return encode_status(
        Status(
            node_id=node_id,
            acquisition_state=state,
            flags=status_flags,
            boot_id=boot_id,
            clock_epoch=0,
            status_sequence=status_sequence,
            last_sample_sequence=0xFFFF_FFFF,
            last_packet_sequence=0xFFFF_FFFF,
            samples_acquired=samples_acquired,
            packets_generated=packets_generated,
            sensor_fifo_overruns=sensor_fifo_overruns,
            firmware_queue_overruns=firmware_queue_overruns,
            transport_backpressure_events=transport_backpressure_events,
            samples_dropped_before_packetization=samples_dropped_before_packetization,
            acquisition_buffer_high_water_samples=0,
            transport_queue_high_water_packets=0,
            last_error_code=last_error_code,
        )
    )


def make_packet(node_id: NodeId, packet_sequence: int, sample_sequence: int) -> bytes:
    return encode_sample_packet(
        SamplePacket(
            node_id=node_id,
            packet_sequence=packet_sequence,
            clock_epoch=0,
            flags=0,
            samples=(
                Sample(
                    sequence=sample_sequence,
                    device_time_us=10_000 + sample_sequence * 10_000,
                    flags=SampleFlags.NONE,
                    accel_raw=(100, -200, 16_000),
                    gyro_raw=(10, -20, 30),
                ),
            ),
        )
    )


class FakeBleClient:
    """A complete deterministic peripheral double at the BLE client boundary."""

    def __init__(
        self,
        *,
        address: str,
        disconnected_callback: Callable[[object], None],
        identity: bytes,
        status_reads: list[bytes],
        hardware_device_id: int,
        mtu_size: int = 127,
        telemetry_payloads: tuple[bytes, ...] = (),
        disconnect_after_first_telemetry: bool = False,
        stop_event: asyncio.Event | None = None,
        connect_error: Exception | None = None,
        disconnect_delay_s: float | None = None,
        connect_delay_s: float = 0.0,
        late_status_after_disconnect: bytes | None = None,
        status_after_callback_quiet: bytes | None = None,
        late_status_after_telemetry_stop: bytes | None = None,
        late_status_after_qc: bytes | None = None,
        capture_window_is_open: Callable[[], bool] | None = None,
    ) -> None:
        self.address = address
        self._disconnected_callback = disconnected_callback
        self._identity = identity
        self._status_reads = list(status_reads)
        self._hardware_device_id = hardware_device_id
        self._telemetry_payloads = telemetry_payloads
        self._disconnect_after_first_telemetry = disconnect_after_first_telemetry
        self._stop_event = stop_event
        self._connect_error = connect_error
        self._disconnect_delay_s = disconnect_delay_s
        self._connect_delay_s = connect_delay_s
        self._late_status_after_disconnect = late_status_after_disconnect
        self._status_after_callback_quiet = status_after_callback_quiet
        self._late_status_after_telemetry_stop = late_status_after_telemetry_stop
        self._late_status_after_qc = late_status_after_qc
        self._capture_window_is_open = capture_window_is_open or (lambda: False)
        self._callbacks: dict[str, Callable[[object, bytearray], None]] = {}
        self._callback_history: dict[str, Callable[[object, bytearray], None]] = {}
        self._status_callback_quiet = False
        self._telemetry_delivered = False
        self.calls: list[tuple[str, str | None, bool | None]] = []
        self.call_timestamps: list[float] = []
        self.is_connected = False
        self.mtu_size = mtu_size

    async def connect(self) -> None:
        self._record_call(("connect", None, None))
        if self._connect_error is not None:
            raise self._connect_error
        if self._connect_delay_s > 0.0:
            await asyncio.sleep(self._connect_delay_s)
        self.is_connected = True

    async def disconnect(self) -> None:
        self._record_call(("disconnect", None, None))
        if self.is_connected:
            self.is_connected = False
            self._disconnected_callback(self)

    async def read_gatt_char(self, char_specifier: str) -> bytes:
        self._record_call(("read", char_specifier, None))
        if char_specifier == IDENTITY_UUID:
            return self._identity
        if char_specifier == STATUS_UUID:
            if self._status_callback_quiet and self._status_after_callback_quiet is not None:
                return self._status_after_callback_quiet
            if not self._status_reads:
                raise AssertionError("unexpected status read")
            return self._status_reads.pop(0)
        raise AssertionError(f"unexpected read: {char_specifier}")

    async def write_gatt_char(
        self,
        char_specifier: str,
        data: bytes,
        *,
        response: bool | None = None,
    ) -> None:
        self._record_call(("write", char_specifier, response))
        assert char_specifier == CLOCK_UUID
        assert response is True
        request_transaction_id = int.from_bytes(data[4:8], "little")
        request_host_send_ns = int.from_bytes(data[8:16], "little")
        response = encode_clock_response(
            ClockResponse(
                transaction_id=request_transaction_id,
                host_send_ns=request_host_send_ns,
                boot_id=0x0102_0304_0506_0708 + int(NodeId.A if self._hardware_device_id == 0xA else NodeId.B),
                clock_epoch=0,
                device_receive_us=100,
                device_indication_queued_us=110,
            )
        )
        self._callbacks[CLOCK_UUID](self, bytearray(response))

    async def start_notify(
        self,
        char_specifier: str,
        callback: Callable[[object, bytearray], None],
    ) -> None:
        self._record_call(("start_notify", char_specifier, None))
        self._callbacks[char_specifier] = callback
        self._callback_history[char_specifier] = callback
        if char_specifier == TELEMETRY_UUID and self._capture_window_is_open():
            self.deliver_telemetry()


    def deliver_telemetry(self) -> None:
        if self._telemetry_delivered:
            return
        self._telemetry_delivered = True
        callback = self._callbacks.get(TELEMETRY_UUID)
        if callback is None:
            return
        for index, payload in enumerate(self._telemetry_payloads):
            callback(self, bytearray(payload))
            if self._stop_event is not None and index == len(self._telemetry_payloads) - 1:
                self._stop_event.set()
            if self._disconnect_after_first_telemetry and index == 0:
                if self._disconnect_delay_s is None:
                    self._disconnect_now()
                else:
                    asyncio.get_running_loop().call_later(
                        self._disconnect_delay_s, self._disconnect_now
                    )
                break

    def _disconnect_now(self) -> None:
        if self.is_connected:
            self.is_connected = False
            self._disconnected_callback(self)
            if self._late_status_after_disconnect is not None:
                status_callback = self._callback_history.get(STATUS_UUID)
                if status_callback is not None:
                    status_callback(self, bytearray(self._late_status_after_disconnect))

    async def stop_notify(self, char_specifier: str) -> None:
        self._record_call(("stop_notify", char_specifier, None))
        self._callbacks.pop(char_specifier, None)
        if char_specifier == TELEMETRY_UUID and self._late_status_after_telemetry_stop is not None:
            status_callback = self._callback_history.get(STATUS_UUID)
            if status_callback is not None:
                status_callback(self, bytearray(self._late_status_after_telemetry_stop))
        if char_specifier == STATUS_UUID:
            self._status_callback_quiet = True
        if char_specifier == CLOCK_UUID and self._late_status_after_qc is not None:
            status_callback = self._callback_history.get(STATUS_UUID)
            if status_callback is not None:
                status_callback(self, bytearray(self._late_status_after_qc))

    def _record_call(self, call: tuple[str, str | None, bool | None]) -> None:
        self.calls.append(call)
        self.call_timestamps.append(time.monotonic())


class FakeBleFactory:
    def __init__(self, client_specs: dict[str, list[dict[str, Any]]]) -> None:
        self._client_specs = client_specs
        self.created: dict[str, list[FakeBleClient]] = {address: [] for address in client_specs}
        self.capture_window_started = False

    def __call__(self, address: str, disconnected_callback: Callable[[object], None]) -> FakeBleClient:
        specs = self._client_specs[address]
        spec = specs.pop(0)
        client = FakeBleClient(
            address=address,
            disconnected_callback=disconnected_callback,
            capture_window_is_open=lambda: self.capture_window_started,
            **spec,
        )
        self.created[address].append(client)
        return client

    def deliver_telemetry(self, node_id: NodeId) -> None:
        self.capture_window_started = True
        expected_hardware_device_id = 0xA if node_id is NodeId.A else 0xB
        for clients in self.created.values():
            for client in clients:
                if client._hardware_device_id == expected_hardware_device_id:
                    client.deliver_telemetry()


def run_capture(
    tmp_path: Path,
    factory: FakeBleFactory,
    *,
    stop_event: asyncio.Event | None,
    duration_s: float = 1.0,
    connection_timeout_s: float = 5.0,
    recovery_timeout_s: float = 10.0,
    reconnect_delay_s: float = 0.25,
    callback_monotonic_ns: Callable[[], int] | None = None,
    capture_window_callback: Callable[[NodeId, int, int, int, int, int], None] | None = None,
) -> Any:
    from kineimu_shoulder.io.m1_ble import M1BleSessionRecorder, NodeTarget

    recorder = M1BleSessionRecorder(
        targets=(
            NodeTarget(node_id=NodeId.A, address="A-address"),
            NodeTarget(node_id=NodeId.B, address="B-address"),
        ),
        output_dir=tmp_path / "session",
        session_id="test-session",
        client_factory=factory,
        clock_exchange_count=1,
        connection_timeout_s=connection_timeout_s,
        recovery_timeout_s=recovery_timeout_s,
        reconnect_delay_s=reconnect_delay_s,
        callback_monotonic_ns=callback_monotonic_ns or time.monotonic_ns,
    )
    def capture_window_opened(
        node_id: NodeId,
        start_ns: int,
        end_ns: int,
        host_start_ns: int,
        host_end_ns: int,
        clock_pair_uncertainty_ns: int,
    ) -> None:
        factory.deliver_telemetry(node_id)
        if capture_window_callback is not None:
            capture_window_callback(
                node_id,
                start_ns,
                end_ns,
                host_start_ns,
                host_end_ns,
                clock_pair_uncertainty_ns,
            )

    return asyncio.run(
        recorder.capture(
            duration_s=duration_s,
            stop_event=stop_event,
            capture_window_callback=capture_window_opened,
            strict_capture_window=True,
        )
    )


def normal_specs(
    node_id: NodeId,
    hardware_device_id: int,
    *,
    stop_event: asyncio.Event | None = None,
    mtu_size: int = 127,
    telemetry_payloads: tuple[bytes, ...] = (),
    disconnect_after_first_telemetry: bool = False,
    status_reads: list[bytes] | None = None,
    connect_error: Exception | None = None,
    disconnect_delay_s: float | None = None,
    connect_delay_s: float = 0.0,
    late_status_after_disconnect: bytes | None = None,
    status_after_callback_quiet: bytes | None = None,
    late_status_after_telemetry_stop: bytes | None = None,
    late_status_after_qc: bytes | None = None,
) -> dict[str, Any]:
    boot_id = 0x0102_0304_0506_0708 + int(node_id)
    return {
        "identity": make_identity(node_id, hardware_device_id),
        "status_reads": status_reads
        or [make_status(node_id, boot_id=boot_id), make_status(node_id, boot_id=boot_id)],
        "hardware_device_id": hardware_device_id,
        "mtu_size": mtu_size,
        "telemetry_payloads": telemetry_payloads,
        "disconnect_after_first_telemetry": disconnect_after_first_telemetry,
        "stop_event": stop_event,
        "connect_error": connect_error,
        "disconnect_delay_s": disconnect_delay_s,
        "connect_delay_s": connect_delay_s,
        "late_status_after_disconnect": late_status_after_disconnect,
        "status_after_callback_quiet": status_after_callback_quiet,
        "late_status_after_telemetry_stop": late_status_after_telemetry_stop,
        "late_status_after_qc": late_status_after_qc,
    }


def test_central_validates_mtu_and_control_plane_before_telemetry(tmp_path: Path) -> None:
    # Source: the frozen M1_ACQUISITION_CONTRACT requires MTU >= 127 and says
    # identity/config and status precede telemetry enablement.
    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                )
            ],
            "B-address": [
                normal_specs(
                    NodeId.B,
                    0xB,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.B, 0, 0),),
                )
            ],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=stop_event)

    for address in ("A-address", "B-address"):
        calls = factory.created[address][0].calls
        identity_read = next(index for index, call in enumerate(calls) if call == ("read", IDENTITY_UUID, None))
        status_read = next(index for index, call in enumerate(calls) if call == ("read", STATUS_UUID, None))
        clock_write = next(index for index, call in enumerate(calls) if call == ("write", CLOCK_UUID, True))
        telemetry_enable = next(
            index for index, call in enumerate(calls) if call == ("start_notify", TELEMETRY_UUID, None)
        )
        assert identity_read < telemetry_enable
        assert status_read < telemetry_enable
        assert clock_write < telemetry_enable

    assert result.manifest_path.exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert [node["node_id"] for node in manifest["nodes"]] == ["A", "B"]
    assert all(node["transport"] == "ble" for node in manifest["nodes"])


def test_telemetry_callback_timing_is_recorded_as_a_sidecar_event(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    packet_a = make_packet(NodeId.A, 0, 0)
    packet_b = make_packet(NodeId.B, 0, 0)
    factory = FakeBleFactory(
        {
            "A-address": [normal_specs(NodeId.A, 0xA, stop_event=stop_event, telemetry_payloads=(packet_a,))],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event, telemetry_payloads=(packet_b,))],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=stop_event)

    events = [
        json.loads(line)
        for line in result.node_results[NodeId.A].events_path.read_text(encoding="utf-8").splitlines()
    ]
    timing_events = [event for event in events if event["event"] == "notify_callback_timing"]

    assert len(timing_events) == 1
    timing = timing_events[0]
    assert timing["callback_index"] == 1
    assert timing["payload_length"] == len(packet_a)
    assert timing["callback_start_monotonic_ns"] <= timing["callback_end_monotonic_ns"]
    assert timing["callback_duration_ns"] == (
        timing["callback_end_monotonic_ns"] - timing["callback_start_monotonic_ns"]
    )


def test_telemetry_callback_timing_uses_high_resolution_callback_clock(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    callback_times = iter(
        (1_000, 1_123, 1_246, 2_000, 2_234, 1_000_001_001, 1_000_001_001)
    )
    packet_a = make_packet(NodeId.A, 0, 0)
    packet_b = make_packet(NodeId.B, 0, 0)
    factory = FakeBleFactory(
        {
            "A-address": [normal_specs(NodeId.A, 0xA, stop_event=stop_event, telemetry_payloads=(packet_a,))],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event, telemetry_payloads=(packet_b,))],
        }
    )

    result = run_capture(
        tmp_path,
        factory,
        stop_event=stop_event,
        callback_monotonic_ns=lambda: next(callback_times),
    )

    timing_events = []
    for node_result in result.node_results.values():
        events = [
            json.loads(line)
            for line in node_result.events_path.read_text(encoding="utf-8").splitlines()
        ]
        timing_events.extend(event for event in events if event["event"] == "notify_callback_timing")

    assert [event["callback_duration_ns"] for event in timing_events] == [123, 234]


def test_default_recorder_callback_timing_does_not_add_capture_window_fields(tmp_path: Path) -> None:
    from kineimu_shoulder.io.m1_ble import NodeTarget, _CaptureSink, _NodeRecorder

    raw_path = tmp_path / "node-a.kimu"
    events_path = tmp_path / "node-a.events.ndjson"
    sink = _CaptureSink(node_id=NodeId.A, raw_path=raw_path, events_path=events_path)
    callback_times = iter((1_000, 1_010))
    recorder = _NodeRecorder(
        target=NodeTarget(node_id=NodeId.A, address="A-address"),
        sink=sink,
        client_factory=lambda _address, _callback: None,
        clock_exchange_count=1,
        clock_response_timeout_s=1.0,
        connection_timeout_s=1.0,
        recovery_timeout_s=1.0,
        reconnect_delay_s=0.0,
        monotonic_ns=lambda: pytest.fail("default callback must not read the capture-window clock"),
        callback_monotonic_ns=lambda: next(callback_times),
        monotonic_seconds=time.monotonic,
        sleep=asyncio.sleep,
    )

    recorder._on_telemetry_notification(None, bytearray(make_packet(NodeId.A, 1, 1)))
    sink.close()
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    timing = next(event for event in events if event["event"] == "notify_callback_timing")

    assert "capture_window_check_perf_counter_ns" not in timing
    assert "capture_window_accepted" not in timing
    from kineimu_shoulder.io.m1_capture import iter_capture_records

    with raw_path.open("rb") as stream:
        records = list(iter_capture_records(stream))
    assert len(records) == 1
    assert records[0].host_monotonic_ns == 1_000


def test_capture_window_excludes_prestart_and_postdeadline_telemetry(tmp_path: Path) -> None:
    from kineimu_shoulder.io.m1_ble import NodeTarget, _CaptureSink, _NodeRecorder

    callback_times = iter((99, 100, 100, 101, 199, 200, 200, 201))
    raw_path = tmp_path / "node-a.kimu"
    events_path = tmp_path / "node-a.events.ndjson"
    sink = _CaptureSink(node_id=NodeId.A, raw_path=raw_path, events_path=events_path)
    recorder = _NodeRecorder(
        target=NodeTarget(node_id=NodeId.A, address="A-address"),
        sink=sink,
        client_factory=lambda _address, _callback: None,
        clock_exchange_count=1,
        clock_response_timeout_s=1.0,
        connection_timeout_s=1.0,
        recovery_timeout_s=1.0,
        reconnect_delay_s=0.0,
        monotonic_ns=iter((1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000)).__next__,
        callback_monotonic_ns=lambda: next(callback_times),
        monotonic_seconds=time.monotonic,
        sleep=asyncio.sleep,
        strict_capture_window=True,
    )
    recorder._capture_window_start_ns = 100
    recorder._capture_window_end_ns = 200

    for sequence in range(4):
        recorder._on_telemetry_notification(None, bytearray(make_packet(NodeId.A, sequence, sequence)))
    sink.close()

    from kineimu_shoulder.io.m1_capture import iter_capture_records

    with raw_path.open("rb") as stream:
        records = list(iter_capture_records(stream))
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    timing = [event for event in events if event["event"] == "notify_callback_timing"]

    assert [record.payload for record in records] == [
        make_packet(NodeId.A, 1, 1),
        make_packet(NodeId.A, 2, 2),
    ]
    assert [record.host_monotonic_ns for record in records] == [100, 199]
    assert sum(event["event"] == "notify" for event in events) == 2
    assert [event["capture_window_accepted"] for event in timing] == [False, True, True, False]
    assert [event["capture_window_check_perf_counter_ns"] for event in timing] == [99, 100, 199, 200]
    assert [event["host_monotonic_ns"] for event in timing] == [99, 100, 199, 200]
    assert [event["callback_start_host_monotonic_ns"] for event in timing] == [1000, 3000, 5000, 7000]


def test_capture_ready_gate_arms_all_windows_before_releasing_waiters(tmp_path: Path) -> None:
    from kineimu_shoulder.io.m1_ble import (
        NodeTarget,
        _CaptureReadyGate,
        _CaptureSink,
        _NodeRecorder,
    )

    recorders = []
    sinks = []
    for node_id in (NodeId.A, NodeId.B):
        raw_path = tmp_path / f"node-{node_id.name.lower()}.kimu"
        events_path = tmp_path / f"node-{node_id.name.lower()}.events.ndjson"
        sink = _CaptureSink(node_id=node_id, raw_path=raw_path, events_path=events_path)
        sinks.append(sink)
        callback_values = iter(
            (10_000_000_000, 10_000_000_001, 10_000_000_002)
            if node_id is NodeId.A
            else (10_000_000_001, 10_000_000_002)
        )
        recorders.append(
            _NodeRecorder(
                target=NodeTarget(node_id=node_id, address=f"{node_id.name}-address"),
                sink=sink,
                client_factory=lambda _address, _callback: None,
                clock_exchange_count=1,
                clock_response_timeout_s=1.0,
                connection_timeout_s=1.0,
                recovery_timeout_s=1.0,
                reconnect_delay_s=0.0,
                monotonic_ns=lambda: 10_000_000_000,
                callback_monotonic_ns=lambda values=callback_values: next(values),
                monotonic_seconds=lambda: 10.0,
                sleep=asyncio.sleep,
                strict_capture_window=True,
            )
        )

    recorders_by_node = {recorder.target.node_id: recorder for recorder in recorders}
    opened: list[tuple[NodeId, int, int, int, int, int]] = []

    def capture_window_opened(
        node_id: NodeId,
        start_ns: int,
        end_ns: int,
        host_start_ns: int,
        host_end_ns: int,
        uncertainty_ns: int,
    ) -> None:
        assert all(
            recorder._capture_window_start_ns == start_ns
            and recorder._capture_window_end_ns == end_ns
            for recorder in recorders
        )
        recorders_by_node[node_id]._on_telemetry_notification(
            None, bytearray(make_packet(node_id, 1, 1))
        )
        opened.append((node_id, start_ns, end_ns, host_start_ns, host_end_ns, uncertainty_ns))

    for recorder in recorders:
        recorder.capture_window_callback = capture_window_opened

    async def wait_for_ready_gate() -> tuple[tuple[float, int | None], tuple[float, int | None]]:
        gate = _CaptureReadyGate(recorders=recorders, duration_s=0.25)
        first_waiter = asyncio.create_task(gate.wait(recorders[0]))
        await asyncio.sleep(0)
        assert not first_waiter.done()
        second_waiter = asyncio.create_task(gate.wait(recorders[1]))
        deadlines = await asyncio.gather(first_waiter, second_waiter)
        return (
            (deadlines[0].monotonic_seconds, deadlines[0].callback_monotonic_ns),
            (deadlines[1].monotonic_seconds, deadlines[1].callback_monotonic_ns),
        )

    assert asyncio.run(wait_for_ready_gate()) == (
        (10.25, 10_250_000_000),
        (10.25, 10_250_000_000),
    )
    assert {item[0] for item in opened} == {NodeId.A, NodeId.B}
    assert len({(item[1], item[2], item[3], item[4]) for item in opened}) == 1

    from kineimu_shoulder.io.m1_capture import iter_capture_records

    for sink in sinks:
        sink.close()
        with sink.raw_path.open("rb") as stream:
            records = list(iter_capture_records(stream))
        assert len(records) == 1
        assert records[0].host_monotonic_ns == 10_000_000_001


def test_dual_node_capture_uses_shared_deadline_after_asymmetric_startup(tmp_path: Path) -> None:
    duration_s = 0.5
    startup_delay_s = 0.2
    stop_tolerance_s = 0.08
    factory = FakeBleFactory(
        {
            "A-address": [normal_specs(NodeId.A, 0xA)],
            "B-address": [
                normal_specs(NodeId.B, 0xB, connect_delay_s=startup_delay_s),
            ],
        }
    )

    capture_windows: list[tuple[NodeId, int, int, int, int, int]] = []

    def record_capture_window(
        node: NodeId,
        start_perf_ns: int,
        deadline_perf_ns: int,
        start_host_ns: int,
        deadline_host_ns: int,
        uncertainty_ns: int,
    ) -> None:
        capture_windows.append(
            (
                node,
                start_perf_ns,
                deadline_perf_ns,
                start_host_ns,
                deadline_host_ns,
                uncertainty_ns,
            )
        )

    run_capture(
        tmp_path,
        factory,
        stop_event=None,
        duration_s=duration_s,
        capture_window_callback=record_capture_window,
    )

    clients = {
        node_id: factory.created[address][0]
        for node_id, address in ((NodeId.A, "A-address"), (NodeId.B, "B-address"))
    }

    def call_time(client: FakeBleClient, call: tuple[str, str | None, bool | None]) -> float:
        call_index = next(index for index, actual in enumerate(client.calls) if actual == call)
        return client.call_timestamps[call_index]

    telemetry_ready = {
        node_id: call_time(client, ("start_notify", TELEMETRY_UUID, None))
        for node_id, client in clients.items()
    }
    telemetry_stopped = {
        node_id: call_time(client, ("stop_notify", TELEMETRY_UUID, None))
        for node_id, client in clients.items()
    }

    # Source: the requested M1 shared-ready-barrier contract. The slower node
    # must receive the complete duration, and both nodes must share one end time.
    assert telemetry_ready[NodeId.B] - telemetry_ready[NodeId.A] >= startup_delay_s - 0.02
    latest_ready = max(telemetry_ready.values())
    assert min(telemetry_stopped.values()) - latest_ready >= duration_s - stop_tolerance_s
    assert abs(telemetry_stopped[NodeId.A] - telemetry_stopped[NodeId.B]) <= stop_tolerance_s
    assert {item[0] for item in capture_windows} == {NodeId.A, NodeId.B}
    assert len({item[1:5] for item in capture_windows}) == 1
    assert all(
        item[2] - item[1] == round(duration_s * 1_000_000_000)
        and item[4] - item[3] == round(duration_s * 1_000_000_000)
        for item in capture_windows
    )


def test_central_rejects_identity_mismatch_before_enabling_telemetry(tmp_path: Path) -> None:
    from kineimu_shoulder.io.m1_ble import IdentityMismatchError, M1BleSessionRecorder, NodeTarget

    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.B,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.B, 0, 0),),
                )
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )
    recorder = M1BleSessionRecorder(
        targets=(
            NodeTarget(node_id=NodeId.A, address="A-address"),
            NodeTarget(node_id=NodeId.B, address="B-address"),
        ),
        output_dir=tmp_path / "session",
        session_id="identity-mismatch",
        client_factory=factory,
        clock_exchange_count=1,
    )

    with pytest.raises(IdentityMismatchError, match="node id"):
        asyncio.run(recorder.capture(duration_s=1.0, stop_event=stop_event))

    assert not any(
        call[0] == "start_notify" and call[1] == TELEMETRY_UUID
        for call in factory.created["A-address"][0].calls
    )


def test_malformed_identity_is_reported_as_host_ble_protocol_error(tmp_path: Path) -> None:
    from kineimu_shoulder.io.m1_ble import BleProtocolError, M1BleSessionRecorder, NodeTarget

    stop_event = asyncio.Event()
    malformed = normal_specs(NodeId.A, 0xA, stop_event=stop_event)
    malformed["identity"] = b"malformed identity"
    factory = FakeBleFactory(
        {
            "A-address": [malformed],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )
    recorder = M1BleSessionRecorder(
        targets=(
            NodeTarget(node_id=NodeId.A, address="A-address"),
            NodeTarget(node_id=NodeId.B, address="B-address"),
        ),
        output_dir=tmp_path / "session",
        session_id="malformed-identity",
        client_factory=factory,
        clock_exchange_count=1,
    )

    with pytest.raises(BleProtocolError, match="identity/config"):
        asyncio.run(recorder.capture(duration_s=1.0, stop_event=stop_event))


def test_central_rejects_att_mtu_below_v1_requirement(tmp_path: Path) -> None:
    from kineimu_shoulder.io.m1_ble import M1BleSessionRecorder, MtuRequirementError, NodeTarget

    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [normal_specs(NodeId.A, 0xA, stop_event=stop_event, mtu_size=126)],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )
    recorder = M1BleSessionRecorder(
        targets=(
            NodeTarget(node_id=NodeId.A, address="A-address"),
            NodeTarget(node_id=NodeId.B, address="B-address"),
        ),
        output_dir=tmp_path / "session",
        session_id="mtu-mismatch",
        client_factory=factory,
        clock_exchange_count=1,
    )

    with pytest.raises(MtuRequirementError, match="127"):
        asyncio.run(recorder.capture(duration_s=1.0, stop_event=stop_event))

    assert not any(
        call[0] == "start_notify"
        for call in factory.created["A-address"][0].calls
        if call[1] == TELEMETRY_UUID
    )


def test_recorder_preserves_malformed_notifications_and_reports_decode_error(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0), b"malformed"),
                )
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=stop_event)

    a_stream = result.node_results[NodeId.A].raw_path.open("rb")
    with a_stream:
        records = list(iter_capture_records(a_stream))
    assert [record.payload for record in records] == [make_packet(NodeId.A, 0, 0), b"malformed"]

    events = [
        json.loads(line)
        for line in result.node_results[NodeId.A].events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(event["event"] == "notify" and event["decode_ok"] for event in events)
    errors = [event for event in events if event["event"] == "decode_error"]
    assert errors and errors[0]["payload_length"] == len(b"malformed")
    assert errors[0]["crc_ok"] is False
    assert errors[0]["raw_stream_offset"] == 12 + len(make_packet(NodeId.A, 0, 0))


def test_clock_exchange_persists_exact_values_and_callback_receive_time(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                )
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=stop_event)

    events = [
        json.loads(line)
        for line in result.node_results[NodeId.A].events_path.read_text(encoding="utf-8").splitlines()
    ]
    requests = [event for event in events if event["event"] == "clock_request"]
    responses = [event for event in events if event["event"] == "clock_response"]
    assert len(requests) == 1
    assert len(responses) == 1
    assert requests[0]["raw_value_hex"]
    assert responses[0]["raw_value_hex"]
    assert responses[0]["decode_ok"] is True
    assert all(
        event["crc_ok"] is True
        for event in events
        if event["event"] in {"config", "clock_request", "clock_response", "status"}
    )
    assert responses[0]["host_receive_monotonic_ns"] == responses[0]["host_monotonic_ns"]
    assert responses[0]["transaction_id"] == requests[0]["transaction_id"]


def test_clock_exchange_finishes_before_status_indication_subscription(tmp_path: Path) -> None:
    factory = FakeBleFactory(
        {
            "A-address": [normal_specs(NodeId.A, 0xA)],
            "B-address": [normal_specs(NodeId.B, 0xB)],
        }
    )

    run_capture(tmp_path, factory, stop_event=asyncio.Event())

    calls = factory.created["A-address"][0].calls
    clock_write_index = next(
        index
        for index, call in enumerate(calls)
        if call == ("write", CLOCK_UUID, True)
    )
    status_notify_index = next(
        index
        for index, call in enumerate(calls)
        if call == ("start_notify", STATUS_UUID, None)
    )
    assert clock_write_index < status_notify_index


def test_reconnect_revalidates_identity_before_accepting_new_telemetry(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                    disconnect_after_first_telemetry=True,
                ),
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 1, 1),),
                ),
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=stop_event, duration_s=2.0)

    clients = factory.created["A-address"]
    assert len(clients) == 2
    second_calls = clients[1].calls
    second_identity = next(index for index, call in enumerate(second_calls) if call == ("read", IDENTITY_UUID, None))
    second_telemetry = next(
        index for index, call in enumerate(second_calls) if call == ("start_notify", TELEMETRY_UUID, None)
    )
    assert second_identity < second_telemetry

    events = [
        json.loads(line)
        for line in result.node_results[NodeId.A].events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(event["event"] == "disconnect" for event in events)
    assert any(event["event"] == "reconnect" for event in events)


def test_late_status_from_disconnected_connection_cannot_abort_reconnect(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    boot_id = 0x0102_0304_0506_0708 + int(NodeId.A)
    late_fatal_status = make_status(
        NodeId.A,
        boot_id=boot_id,
        state=AcquisitionState.ERROR,
        status_sequence=9,
    )
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                    disconnect_after_first_telemetry=True,
                    late_status_after_disconnect=late_fatal_status,
                ),
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 1, 1),),
                ),
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=stop_event, duration_s=2.0)
    events = [
        json.loads(line)
        for line in result.node_results[NodeId.A].events_path.read_text(encoding="utf-8").splitlines()
    ]
    late_status = next(
        event
        for event in events
        if event["event"] == "status" and event["source"] == "indication" and event["status_sequence"] == 9
    )

    # Source: a disconnect boundary invalidates callbacks from the old connection,
    # while the append-only sidecar must retain the late indication with its origin.
    assert late_status["connection_id"] == "a-1"
    assert result.node_results[NodeId.A].packet_count == 2
    assert any(event["event"] == "reconnect" for event in events)


def test_reconnect_rejects_changed_stable_hardware_device_id(tmp_path: Path) -> None:
    from kineimu_shoulder.io.m1_ble import IdentityMismatchError

    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                    disconnect_after_first_telemetry=True,
                ),
                normal_specs(
                    NodeId.A,
                    0xC,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 1, 1),),
                ),
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    with pytest.raises(IdentityMismatchError, match="hardware device ID"):
        run_capture(tmp_path, factory, stop_event=stop_event, duration_s=2.0)

    assert not any(
        call[0] == "start_notify" and call[1] == TELEMETRY_UUID
        for call in factory.created["A-address"][1].calls
    )


def test_disconnect_wakes_capture_when_no_external_stop_event_is_used(tmp_path: Path) -> None:
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                    disconnect_after_first_telemetry=True,
                    disconnect_delay_s=0.005,
                ),
                normal_specs(NodeId.A, 0xA, telemetry_payloads=(make_packet(NodeId.A, 1, 1),)),
            ],
            "B-address": [normal_specs(NodeId.B, 0xB)],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=None, duration_s=0.05)

    assert len(factory.created["A-address"]) == 2
    assert result.node_results[NodeId.A].packet_count == 2


def test_each_connection_establishment_has_a_bounded_timeout(tmp_path: Path) -> None:
    from kineimu_shoulder.io.m1_ble import BleTransportError

    factory = FakeBleFactory(
        {
            "A-address": [normal_specs(NodeId.A, 0xA, connect_delay_s=0.2)],
            "B-address": [normal_specs(NodeId.B, 0xB)],
        }
    )

    started = time.monotonic()
    with pytest.raises(BleTransportError, match="connection establishment timed out"):
        run_capture(
            tmp_path,
            factory,
            stop_event=None,
            connection_timeout_s=0.01,
        )

    assert time.monotonic() - started < 0.15
    # A cancelled/failed WinRT connect can leave a partial GATT session even
    # though ``is_connected`` is already false; abort must still run teardown.
    assert ("disconnect", None, None) in factory.created["A-address"][0].calls


def test_recovery_deadline_is_independent_of_capture_duration(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                    disconnect_after_first_telemetry=True,
                ),
                normal_specs(NodeId.A, 0xA, connect_error=RuntimeError("peripheral not ready")),
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 1, 1),),
                ),
            ],
            "B-address": [normal_specs(NodeId.B, 0xB)],
        }
    )

    result = run_capture(
        tmp_path,
        factory,
        stop_event=stop_event,
        duration_s=0.03,
        connection_timeout_s=0.2,
        recovery_timeout_s=0.2,
        reconnect_delay_s=0.05,
    )

    # Recovery gets its own deadline and restores the stream before teardown,
    # while notifications after the shared capture deadline stay out of raw data.
    assert len(factory.created["A-address"]) == 3
    assert result.node_results[NodeId.A].packet_count == 1
    assert result.node_results[NodeId.A].sample_count == 1
    events = [
        json.loads(line)
        for line in result.node_results[NodeId.A].events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(event["event"] == "recovery_start" for event in events)
    assert any(event["event"] == "telemetry_resume" for event in events)
    assert any(event["event"] == "recovery_complete" for event in events)
    callback_events = [event for event in events if event["event"] == "notify_callback_timing"]
    assert [event["capture_window_accepted"] for event in callback_events] == [True, False]


def test_recovery_deadline_caps_an_in_progress_connection_attempt(tmp_path: Path) -> None:
    from kineimu_shoulder.io.m1_ble import M1BleError

    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                    disconnect_after_first_telemetry=True,
                ),
                normal_specs(NodeId.A, 0xA, connect_delay_s=1.0),
            ],
            "B-address": [normal_specs(NodeId.B, 0xB)],
        }
    )

    started = time.monotonic()
    with pytest.raises(M1BleError, match="recovery deadline expired"):
        run_capture(
            tmp_path,
            factory,
            stop_event=None,
            duration_s=0.01,
            connection_timeout_s=1.0,
            recovery_timeout_s=0.05,
            reconnect_delay_s=0.0,
        )

    assert time.monotonic() - started < 0.2


def test_final_status_is_read_after_telemetry_notify_stops(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                )
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    run_capture(tmp_path, factory, stop_event=stop_event)

    calls = factory.created["A-address"][0].calls
    telemetry_stop = next(index for index, call in enumerate(calls) if call == ("stop_notify", TELEMETRY_UUID, None))
    status_stop = next(index for index, call in enumerate(calls) if call == ("stop_notify", STATUS_UUID, None))
    final_status_read = [
        index for index, call in enumerate(calls) if call == ("read", STATUS_UUID, None)
    ][-1]
    assert telemetry_stop < status_stop < final_status_read


def test_final_status_and_qc_use_snapshot_after_status_callback_quiet(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    boot_id = 0x0102_0304_0506_0708 + int(NodeId.A)
    initial_status = make_status(NodeId.A, boot_id=boot_id, status_sequence=1)
    stale_final_status = make_status(
        NodeId.A,
        boot_id=boot_id,
        samples_acquired=1,
        packets_generated=1,
        firmware_queue_overruns=25,
        status_sequence=2,
    )
    stable_final_status = make_status(
        NodeId.A,
        boot_id=boot_id,
        samples_acquired=1,
        packets_generated=1,
        firmware_queue_overruns=30,
        transport_backpressure_events=1,
        status_sequence=3,
    )
    late_after_qc_status = make_status(
        NodeId.A,
        boot_id=boot_id,
        samples_acquired=1,
        packets_generated=1,
        firmware_queue_overruns=30,
        transport_backpressure_events=1,
        status_sequence=4,
    )
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                    status_reads=[initial_status, stale_final_status],
                    status_after_callback_quiet=stable_final_status,
                    late_status_after_telemetry_stop=stable_final_status,
                    late_status_after_qc=late_after_qc_status,
                )
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=stop_event)
    events = [
        json.loads(line)
        for line in result.node_results[NodeId.A].events_path.read_text(encoding="utf-8").splitlines()
    ]
    status_events = [event for event in events if event["event"] == "status"]
    final_status = next(event for event in status_events if event["source"] == "final")
    qc_summary_index = next(index for index, event in enumerate(events) if event["event"] == "qc_summary")
    qc_summary = events[qc_summary_index]
    final_status_index = events.index(final_status)
    late_status_before_final = next(
        event
        for event in status_events
        if event["source"] == "indication" and event["status_sequence"] == 3
    )
    late_status_after_qc = [
        event
        for index, event in enumerate(status_events)
        if index > status_events.index(final_status) and event["source"] == "indication"
    ][0]

    # Source: M1_ACQUISITION_CONTRACT.md requires every indication to be retained,
    # then requires the final read after telemetry and status notifications stop.
    assert [(event["source"], event["status_sequence"]) for event in status_events] == [
        ("read", 1),
        ("indication", 3),
        ("final", 3),
        ("indication", 4),
    ]
    assert [event["raw_value_hex"] for event in status_events] == [
        initial_status.hex(),
        stable_final_status.hex(),
        stable_final_status.hex(),
        late_after_qc_status.hex(),
    ]
    assert final_status["firmware_queue_overruns"] == 30
    assert final_status["transport_backpressure_events"] == 1
    assert final_status["status_counter_deltas"]["firmware_queue_overruns"] == 30
    assert final_status["status_counter_deltas"]["transport_backpressure_events"] == 1
    assert qc_summary["status_counter_deltas"]["firmware_queue_overruns"] == 30
    assert qc_summary["status_counter_deltas"]["transport_backpressure_events"] == 1
    assert events.index(late_status_before_final) < final_status_index
    assert final_status_index < qc_summary_index < events.index(late_status_after_qc)
    assert result.node_results[NodeId.A].qc_pass is False

    calls = factory.created["A-address"][0].calls
    telemetry_stop = next(index for index, call in enumerate(calls) if call == ("stop_notify", TELEMETRY_UUID, None))
    status_stop = next(index for index, call in enumerate(calls) if call == ("stop_notify", STATUS_UUID, None))
    final_status_read = [index for index, call in enumerate(calls) if call == ("read", STATUS_UUID, None)][-1]
    assert telemetry_stop < status_stop < final_status_read


def test_final_status_read_failure_still_cleans_up_remaining_connection(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    boot_id = 0x0102_0304_0506_0708 + int(NodeId.A)
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                    status_reads=[make_status(NodeId.A, boot_id=boot_id)],
                )
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    with pytest.raises(AssertionError, match="unexpected status read"):
        run_capture(tmp_path, factory, stop_event=stop_event)

    calls = factory.created["A-address"][0].calls
    # Source: teardown must release every remaining subscription and disconnect
    # even when the final status read fails.
    assert ("stop_notify", STATUS_UUID, None) in calls
    assert ("stop_notify", CLOCK_UUID, None) in calls
    assert ("stop_notify", IDENTITY_UUID, None) in calls
    assert ("disconnect", None, None) in calls


def test_manifest_stream_paths_are_relative_to_session_root(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                )
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    from kineimu_shoulder.io.m1_ble import M1BleSessionRecorder, NodeTarget

    session_dir = tmp_path / "raw" / "session"
    recorder = M1BleSessionRecorder(
        targets=(
            NodeTarget(node_id=NodeId.A, address="A-address"),
            NodeTarget(node_id=NodeId.B, address="B-address"),
        ),
        output_dir=session_dir,
        session_id="relative-paths",
        client_factory=factory,
        clock_exchange_count=1,
    )

    def open_capture_window(
        node: NodeId,
        _start_perf_ns: int,
        _deadline_perf_ns: int,
        _start_host_ns: int,
        _deadline_host_ns: int,
        _uncertainty_ns: int,
    ) -> None:
        factory.deliver_telemetry(node)

    result = asyncio.run(
        recorder.capture(
            duration_s=1.0,
            stop_event=stop_event,
            capture_window_callback=open_capture_window,
            strict_capture_window=True,
        )
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["streams"][0]["raw_path"] == "raw/node-a.kimu"
    assert manifest["streams"][0]["transport_events_path"] == "raw/node-a.events.ndjson"


def test_final_status_reconciliation_is_explicit(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    packet = make_packet(NodeId.A, 0, 0)
    boot_id = 0x0102_0304_0506_0708 + int(NodeId.A)
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(packet,),
                    status_reads=[
                        make_status(NodeId.A, boot_id=boot_id),
                        make_status(
                            NodeId.A,
                            boot_id=boot_id,
                            samples_acquired=2,
                            packets_generated=2,
                            state=AcquisitionState.STREAMING,
                        ),
                    ],
                )
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=stop_event)
    events = [
        json.loads(line)
        for line in result.node_results[NodeId.A].events_path.read_text(encoding="utf-8").splitlines()
    ]
    final_status = [
        event for event in events if event["event"] == "status" and event["source"] == "final"
    ][0]

    assert final_status["counter_reconciliation_ok"] is False
    assert final_status["raw_packet_count"] == 1
    assert final_status["raw_sample_count"] == 1
    assert final_status["status_packets_generated"] == 2
    assert final_status["status_samples_acquired"] == 2
    assert result.node_results[NodeId.A].qc_pass is False


def test_status_loss_counters_are_preserved_and_fail_qc(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    boot_id = 0x0102_0304_0506_0708 + int(NodeId.A)
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                    status_reads=[
                        make_status(NodeId.A, boot_id=boot_id),
                        make_status(NodeId.A, boot_id=boot_id, sensor_fifo_overruns=1),
                    ],
                )
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=stop_event)
    events = [
        json.loads(line)
        for line in result.node_results[NodeId.A].events_path.read_text(encoding="utf-8").splitlines()
    ]
    qc_summary = [event for event in events if event["event"] == "qc_summary"][0]

    assert qc_summary["status_counter_deltas"]["sensor_fifo_overruns"] == 1
    assert qc_summary["status_counters_clear"] is False
    assert qc_summary["status_qc_pass"] is False
    assert qc_summary["qc_pass"] is False
    assert result.node_results[NodeId.A].qc_pass is False


def test_zero_sample_node_fails_qc_with_explicit_reason(tmp_path: Path) -> None:
    stop_event = asyncio.Event()
    boot_id_b = 0x0102_0304_0506_0708 + int(NodeId.B)
    factory = FakeBleFactory(
        {
            "A-address": [normal_specs(NodeId.A, 0xA)],
            "B-address": [
                normal_specs(
                    NodeId.B,
                    0xB,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.B, 0, 0),),
                    status_reads=[
                        make_status(NodeId.B, boot_id=boot_id_b),
                        make_status(
                            NodeId.B,
                            boot_id=boot_id_b,
                            samples_acquired=1,
                            packets_generated=1,
                            state=AcquisitionState.STREAMING,
                        ),
                    ],
                )
            ],
        }
    )

    result = run_capture(tmp_path, factory, stop_event=stop_event)
    zero_sample_result = result.node_results[NodeId.A]
    events = [
        json.loads(line)
        for line in zero_sample_result.events_path.read_text(encoding="utf-8").splitlines()
    ]
    qc_summary = [event for event in events if event["event"] == "qc_summary"][0]

    assert zero_sample_result.sample_count == 0
    assert zero_sample_result.qc_pass is False
    assert "no_samples" in qc_summary["qc_reasons"]
    assert result.node_results[NodeId.B].sample_count == 1
    assert result.node_results[NodeId.B].qc_pass is True


def test_discovery_returns_sorted_candidates_without_node_assignment(monkeypatch: pytest.MonkeyPatch) -> None:
    from kineimu_shoulder.io import m1_ble

    class Device:
        def __init__(self, address: str, name: str) -> None:
            self.address = address
            self.name = name

    class Advertisement:
        def __init__(self, rssi: int) -> None:
            self.rssi = rssi

    class Scanner:
        @staticmethod
        async def discover(**kwargs: object) -> dict[str, tuple[Device, Advertisement]]:
            assert kwargs["service_uuids"] == [m1_ble.M1_SERVICE_UUID]
            assert kwargs["return_adv"] is True
            return {
                "B": (Device("B-address", "Node B"), Advertisement(-40)),
                "A": (Device("A-address", "Node A"), Advertisement(-30)),
            }

    class BleakModule:
        BleakScanner = Scanner

    monkeypatch.setattr(m1_ble, "_load_bleak", lambda: BleakModule)

    devices = asyncio.run(m1_ble.discover_m1_devices(timeout_s=1.0))

    assert [(device.address, device.name, device.rssi) for device in devices] == [
        ("A-address", "Node A", -30),
        ("B-address", "Node B", -40),
    ]


def test_cli_builds_explicit_node_targets_from_operator_addresses() -> None:
    from scripts.capture_m1_ble import build_argument_parser, targets_from_args

    args = build_argument_parser().parse_args(
        [
            "--node-a-address",
            "A-address",
            "--node-b-address",
            "B-address",
            "--output-dir",
            "session-output",
            "--session-id",
            "cli-test",
            "--expected-node-a-device-id",
            "0xA",
            "--expected-node-b-device-id",
            "11",
        ]
    )

    targets = targets_from_args(args)

    assert [(target.node_id, target.address, target.expected_hardware_device_id) for target in targets] == [
        (NodeId.A, "A-address", 0xA),
        (NodeId.B, "B-address", 11),
    ]
    assert args.connection_timeout == 5.0
    assert args.recovery_timeout == 10.0


def test_bleak_factory_forwards_explicit_address_and_disconnect_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kineimu_shoulder.io import m1_ble

    captured: dict[str, object] = {}

    class BleakClient:
        def __init__(self, address: str, *, disconnected_callback: Callable[[object], None]) -> None:
            captured["address"] = address
            captured["callback"] = disconnected_callback

    BleakModule = type("BleakModule", (), {"BleakClient": BleakClient})

    def callback(_client: object) -> None:
        captured["callback_arg"] = _client

    monkeypatch.setattr(m1_ble, "_load_bleak", lambda: BleakModule)

    client = m1_ble.create_bleak_client("A-address", callback)
    callback_from_bleak = captured["callback"]
    assert callable(callback_from_bleak)
    callback_from_bleak(object())

    assert captured["address"] == "A-address"
    assert captured["callback"] is not callback
    assert captured["callback_arg"] is client


def test_bleak_factory_releases_winrt_maintain_connection_before_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kineimu_shoulder.io import m1_ble

    captured: dict[str, object] = {"session_closed": False}

    class Session:
        maintain_connection = True

        def close(self) -> None:
            captured["session_closed"] = True

    session = Session()

    class Backend:
        _session = session

    Backend.__module__ = "bleak.backends.winrt.client"

    class BleakClient:
        def __init__(self, _address: str, *, disconnected_callback: Callable[[object], None]) -> None:
            self._backend = Backend()
            self._disconnected_callback = disconnected_callback

        async def disconnect(self) -> None:
            captured["maintain_connection_at_disconnect"] = session.maintain_connection
            captured["backend_session_at_disconnect"] = self._backend._session

    BleakModule = type("BleakModule", (), {"BleakClient": BleakClient})

    monkeypatch.setattr(m1_ble, "_load_bleak", lambda: BleakModule)

    client = m1_ble.create_bleak_client("A-address", lambda _client: None)
    asyncio.run(client.disconnect())

    assert captured == {
        "session_closed": False,
        "maintain_connection_at_disconnect": False,
        "backend_session_at_disconnect": session,
    }


def test_bleak_factory_stops_winrt_notifications_before_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kineimu_shoulder.io import m1_ble

    events: list[object] = []

    class Session:
        maintain_connection = True

    session = Session()

    class Backend:
        _session = session

    Backend.__module__ = "bleak.backends.winrt.client"

    class BleakClient:
        is_connected = True

        def __init__(self, _address: str, *, disconnected_callback: Callable[[object], None]) -> None:
            self._backend = Backend()
            self._disconnected_callback = disconnected_callback

        async def start_notify(self, char_specifier: str, _callback: Callable[..., None]) -> None:
            del char_specifier

        async def stop_notify(self, char_specifier: str) -> None:
            events.append(("stop_notify", char_specifier))

        async def disconnect(self) -> None:
            events.append(("disconnect", session.maintain_connection))

    BleakModule = type("BleakModule", (), {"BleakClient": BleakClient})

    monkeypatch.setattr(m1_ble, "_load_bleak", lambda: BleakModule)

    client = m1_ble.create_bleak_client("A-address", lambda _client: None)

    async def exercise() -> None:
        await client.start_notify(TELEMETRY_UUID, lambda _sender, _data: None)
        await client.disconnect()

    asyncio.run(exercise())

    assert events == [("stop_notify", TELEMETRY_UUID), ("disconnect", False)]


def test_bleak_factory_serializes_notification_stop_with_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kineimu_shoulder.io import m1_ble

    events: list[object] = []
    stop_started = asyncio.Event()
    stop_release = asyncio.Event()

    class Session:
        maintain_connection = True

    session = Session()

    class Backend:
        _session = session

    Backend.__module__ = "bleak.backends.winrt.client"

    class BleakClient:
        is_connected = True

        def __init__(self, _address: str, *, disconnected_callback: Callable[[object], None]) -> None:
            self._backend = Backend()
            self._disconnected_callback = disconnected_callback

        async def start_notify(self, char_specifier: str, _callback: Callable[..., None]) -> None:
            del char_specifier

        async def stop_notify(self, char_specifier: str) -> None:
            events.append(("stop_start", char_specifier))
            stop_started.set()
            await stop_release.wait()
            events.append(("stop_end", char_specifier))

        async def disconnect(self) -> None:
            events.append(("disconnect", session.maintain_connection))
            type(self).is_connected = False

    BleakModule = type("BleakModule", (), {"BleakClient": BleakClient})

    monkeypatch.setattr(m1_ble, "_load_bleak", lambda: BleakModule)

    client = m1_ble.create_bleak_client("A-address", lambda _client: None)

    async def exercise() -> None:
        await client.start_notify(TELEMETRY_UUID, lambda _sender, _data: None)
        disconnect_task = asyncio.create_task(client.disconnect())
        await stop_started.wait()
        duplicate_stop_task = asyncio.create_task(client.stop_notify(TELEMETRY_UUID))
        await asyncio.sleep(0)
        stop_release.set()
        await asyncio.gather(disconnect_task, duplicate_stop_task)

    asyncio.run(exercise())

    assert events == [
        ("stop_start", TELEMETRY_UUID),
        ("stop_end", TELEMETRY_UUID),
        ("disconnect", False),
    ]


def test_bleak_factory_defers_explicit_disconnect_callback_until_close_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kineimu_shoulder.io import m1_ble

    events: list[str] = []

    class Session:
        maintain_connection = True

        def close(self) -> None:
            events.append("session_close")

    session = Session()

    class Backend:
        _session = session

    Backend.__module__ = "bleak.backends.winrt.client"

    class BleakClient:
        is_connected = True

        def __init__(self, _address: str, *, disconnected_callback: Callable[[object], None]) -> None:
            self._backend = Backend()
            self._disconnected_callback = disconnected_callback

        async def disconnect(self) -> None:
            events.append("underlying_start")
            self._disconnected_callback(self)
            events.append("underlying_end")
            type(self).is_connected = False

    BleakModule = type("BleakModule", (), {"BleakClient": BleakClient})

    monkeypatch.setattr(m1_ble, "_load_bleak", lambda: BleakModule)

    client = m1_ble.create_bleak_client("A-address", lambda _client: events.append("callback"))
    asyncio.run(client.disconnect())

    assert events == ["underlying_start", "underlying_end", "callback"]
    assert session.maintain_connection is False


def test_bleak_factory_suppresses_late_winrt_disconnect_callback_after_explicit_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kineimu_shoulder.io import m1_ble

    events: list[str] = []

    class Session:
        maintain_connection = True

        def close(self) -> None:
            events.append("session_close")

    session = Session()

    class Backend:
        _session = session

    Backend.__module__ = "bleak.backends.winrt.client"

    class BleakClient:
        is_connected = True

        def __init__(self, _address: str, *, disconnected_callback: Callable[[object], None]) -> None:
            self._backend = Backend()
            self._disconnected_callback = disconnected_callback

        async def disconnect(self) -> None:
            events.append("underlying_disconnect")
            type(self).is_connected = False

    BleakModule = type("BleakModule", (), {"BleakClient": BleakClient})

    monkeypatch.setattr(m1_ble, "_load_bleak", lambda: BleakModule)

    client = m1_ble.create_bleak_client("A-address", lambda _client: events.append("callback"))
    awaitable_disconnect = client.disconnect()
    asyncio.run(awaitable_disconnect)

    captured_callback = client._client._disconnected_callback
    captured_callback(client._client)

    assert events == ["underlying_disconnect", "callback"]
    assert session.maintain_connection is False


def test_initial_connect_failure_is_wrapped_as_actionable_ble_error(tmp_path: Path) -> None:
    from kineimu_shoulder.io.m1_ble import BleTransportError, M1BleSessionRecorder, NodeTarget

    stop_event = asyncio.Event()
    factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    connect_error=RuntimeError("adapter unavailable"),
                )
            ],
            "B-address": [normal_specs(NodeId.B, 0xB, stop_event=stop_event)],
        }
    )
    recorder = M1BleSessionRecorder(
        targets=(
            NodeTarget(node_id=NodeId.A, address="A-address"),
            NodeTarget(node_id=NodeId.B, address="B-address"),
        ),
        output_dir=tmp_path / "session",
        session_id="connect-error",
        client_factory=factory,
        clock_exchange_count=1,
    )

    with pytest.raises(BleTransportError, match="adapter unavailable"):
        asyncio.run(recorder.capture(duration_s=1.0, stop_event=stop_event))


@pytest.mark.parametrize("first_node", [NodeId.A, NodeId.B])
def test_matrix_second_link_gate_does_not_consume_connect_attempt_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first_node: NodeId,
) -> None:
    from kineimu_shoulder.io.m1_ble import M1BleSessionRecorder, NodeTarget

    monkeypatch.setattr(m1_ble_link_matrix, "ROOT_CAUSE_SETUP_SETTLE_S", 0.01)
    stop_event = asyncio.Event()
    second_node = NodeId.B if first_node is NodeId.A else NodeId.A
    connect_delays = {first_node: 0.18, second_node: 0.12}
    backend_factory = FakeBleFactory(
        {
            "A-address": [
                normal_specs(
                    NodeId.A,
                    0xA,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.A, 0, 0),),
                    connect_delay_s=connect_delays[NodeId.A],
                )
            ],
            "B-address": [
                normal_specs(
                    NodeId.B,
                    0xB,
                    stop_event=stop_event,
                    telemetry_payloads=(make_packet(NodeId.B, 0, 0),),
                    connect_delay_s=connect_delays[NodeId.B],
                )
            ],
        }
    )
    class FreshDevice:
        def __init__(self, address: str) -> None:
            self.address = address
            self.name = f"fresh-{address}"

    async def fresh_device_scan(address: str, *, timeout_s: float) -> FreshDevice:
        assert timeout_s == m1_ble_link_matrix.ROOT_CAUSE_SCAN_TIMEOUT_S
        return FreshDevice(address)

    def fresh_device_factory(
        device: FreshDevice,
        disconnected_callback: Callable[[object], None],
        *,
        services: list[str],
        operation_timing_sink: Callable[..., None],
    ) -> Any:
        assert services == [m1_ble_link_matrix.M1_SERVICE_UUID]
        assert callable(operation_timing_sink)
        return backend_factory(
            str(device.address), disconnected_callback
        )

    monkeypatch.setattr(
        m1_ble_link_matrix, "discover_m1_ble_device", fresh_device_scan
    )
    monkeypatch.setattr(
        m1_ble_link_matrix, "create_bleak_client", fresh_device_factory
    )
    async def capture() -> tuple[Any, m1_ble_link_matrix._MatrixConnectionGate]:
        events = EventLog(tmp_path / f"matrix-control-{first_node.name.lower()}.ndjson")
        connection_gate = m1_ble_link_matrix._MatrixConnectionGate(
            required_nodes=(NodeId.A, NodeId.B),
            first_node=first_node,
            events=events,
        )
        original_note_connected = connection_gate.note_connected

        def note_connected_with_firmware_event(
            node: NodeId, attempt_id: int
        ) -> None:
            connection_gate.note_firmware_event(
                node,
                "connected",
                time.monotonic_ns(),
                f"Node {node.name}: BLE link event=connected firmware_uptime_ms=1000 info_rc=0 "
                "interval_us=30000 latency=0 supervision_timeout_us=420000",
            )
            original_note_connected(node, attempt_id)

        connection_gate.note_connected = note_connected_with_firmware_event  # type: ignore[method-assign]

        def matrix_client_factory(
            address: str,
            disconnected_callback: Callable[[object], None],
        ) -> Any:
            node = NodeId.A if address == "A-address" else NodeId.B
            return m1_ble_link_matrix.MatrixBleClient(
                node=node,
                address=address,
                disconnected_callback=disconnected_callback,
                events=events,
                connection_gate=connection_gate,
            )

        recorder = M1BleSessionRecorder(
            targets=(
                NodeTarget(node_id=NodeId.A, address="A-address"),
                NodeTarget(node_id=NodeId.B, address="B-address"),
            ),
            output_dir=tmp_path / f"session-{first_node.name.lower()}",
            session_id=f"matrix-connect-gate-timeout-{first_node.name.lower()}",
            client_factory=matrix_client_factory,
            clock_exchange_count=1,
            connection_timeout_s=0.25,
        )
        try:
            result = await recorder.capture(duration_s=0.01, stop_event=stop_event)
        finally:
            events.close()
        return result, connection_gate

    result, connection_gate = asyncio.run(capture())

    assert connection_gate.first_connected.is_set()
    assert set(result.node_results) == {NodeId.A, NodeId.B}
