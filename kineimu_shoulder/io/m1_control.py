"""Versioned M1 BLE identity, clock-exchange and status codecs."""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum, IntFlag
from typing import Any

from kineimu_shoulder.io.m1_packet import (
    MAGIC,
    MAX_SAMPLES_PER_PACKET,
    PROTOCOL_VERSION,
    NodeId,
    ProtocolError,
    crc32c,
)

IDENTITY_CONFIG_TYPE = 2
CLOCK_REQUEST_TYPE = 3
CLOCK_RESPONSE_TYPE = 4
STATUS_TYPE = 5

SENSOR_REGISTER_COUNT = 19

_CONTROL_HEADER = struct.Struct("<HBB")
_IDENTITY_CONFIG = struct.Struct("<HBBBBBBBBIIQQ20sIIIII19s")
_CLOCK_REQUEST = struct.Struct("<HBBIQ")
_CLOCK_RESPONSE = struct.Struct("<HBBIQQIQQ")
_STATUS = struct.Struct("<HBBBBHQIIIIQQIIIIIII")
_CRC = struct.Struct("<I")

_KNOWN_STATUS_FLAGS = 0x000F


class TimestampSource(IntEnum):
    """Source of each telemetry sample's device timestamp."""

    MCU_DRDY_ISR = 1
    SENSOR_INTERNAL = 2
    RECONSTRUCTED = 3


class AcquisitionState(IntEnum):
    """Current device acquisition state."""

    IDLE = 0
    ARMED = 1
    STREAMING = 2
    ERROR = 3


class StatusFlags(IntFlag):
    """Latched state reported by the status characteristic."""

    NONE = 0
    SENSOR_READY = 1 << 0
    SAMPLING_ACTIVE = 1 << 1
    FATAL_ERROR_LATCHED = 1 << 2
    COUNTERS_SATURATED = 1 << 3


@dataclass(frozen=True, slots=True)
class IdentityConfig:
    """Stable identity and active acquisition configuration for one boot."""

    node_id: NodeId
    timestamp_source: TimestampSource
    firmware_version: tuple[int, int, int]
    batch_size: int
    config_generation: int
    clock_epoch: int
    boot_id: int
    hardware_device_id: int
    firmware_git_commit: bytes
    timer_frequency_hz: int
    accel_odr_millihz: int
    gyro_odr_millihz: int
    accel_range_mg: int
    gyro_range_mdps: int
    sensor_registers: bytes


@dataclass(frozen=True, slots=True)
class ClockRequest:
    """One host-to-device two-way timestamp exchange request."""

    transaction_id: int
    host_send_ns: int


@dataclass(frozen=True, slots=True)
class ClockResponse:
    """Device timestamps paired with the echoed host request timestamp."""

    transaction_id: int
    host_send_ns: int
    boot_id: int
    clock_epoch: int
    device_receive_us: int
    device_indication_queued_us: int


@dataclass(frozen=True, slots=True)
class Status:
    """Cumulative acquisition and overflow evidence for one device boot."""

    node_id: NodeId
    acquisition_state: AcquisitionState
    flags: StatusFlags
    boot_id: int
    clock_epoch: int
    status_sequence: int
    last_sample_sequence: int
    last_packet_sequence: int
    samples_acquired: int
    packets_generated: int
    sensor_fifo_overruns: int
    firmware_queue_overruns: int
    transport_backpressure_events: int
    samples_dropped_before_packetization: int
    acquisition_buffer_high_water_samples: int
    transport_queue_high_water_packets: int
    last_error_code: int


ControlMessage = IdentityConfig | ClockRequest | ClockResponse | Status


def encode_identity_config(config: IdentityConfig) -> bytes:
    """Encode the identity/config characteristic value."""

    _enum_value(NodeId, int(config.node_id), "node id")
    _enum_value(TimestampSource, int(config.timestamp_source), "timestamp source")
    if len(config.firmware_version) != 3:
        raise ProtocolError("firmware version must contain exactly three unsigned bytes")
    major, minor, patch = config.firmware_version
    for name, value in (("firmware major", major), ("firmware minor", minor), ("firmware patch", patch)):
        _validate_unsigned(value, 8, name)
    if not 1 <= config.batch_size <= MAX_SAMPLES_PER_PACKET:
        raise ProtocolError(f"batch size must be between 1 and {MAX_SAMPLES_PER_PACKET}")
    _validate_unsigned(config.config_generation, 32, "config generation")
    _validate_unsigned(config.clock_epoch, 32, "clock epoch")
    _validate_positive_unsigned(config.boot_id, 64, "boot id")
    _validate_positive_unsigned(config.hardware_device_id, 64, "hardware device id")
    if len(config.firmware_git_commit) != 20:
        raise ProtocolError("firmware git commit must contain exactly 20 bytes")
    if len(config.sensor_registers) != SENSOR_REGISTER_COUNT:
        raise ProtocolError(f"sensor register snapshot must contain exactly {SENSOR_REGISTER_COUNT} bytes")
    for name, value in (
        ("timer frequency", config.timer_frequency_hz),
        ("accelerometer ODR", config.accel_odr_millihz),
        ("gyroscope ODR", config.gyro_odr_millihz),
        ("accelerometer range", config.accel_range_mg),
        ("gyroscope range", config.gyro_range_mdps),
    ):
        _validate_positive_unsigned(value, 32, name)

    return _pack_with_crc(
        _IDENTITY_CONFIG,
        MAGIC,
        PROTOCOL_VERSION,
        IDENTITY_CONFIG_TYPE,
        int(config.node_id),
        int(config.timestamp_source),
        major,
        minor,
        patch,
        config.batch_size,
        config.config_generation,
        config.clock_epoch,
        config.boot_id,
        config.hardware_device_id,
        config.firmware_git_commit,
        config.timer_frequency_hz,
        config.accel_odr_millihz,
        config.gyro_odr_millihz,
        config.accel_range_mg,
        config.gyro_range_mdps,
        config.sensor_registers,
    )


def decode_identity_config(data: bytes) -> IdentityConfig:
    """Decode and validate an identity/config characteristic value."""

    values = _unpack_control(data, _IDENTITY_CONFIG, IDENTITY_CONFIG_TYPE)
    (
        _,
        _,
        _,
        node_raw,
        timestamp_source_raw,
        major,
        minor,
        patch,
        batch_size,
        config_generation,
        clock_epoch,
        boot_id,
        hardware_device_id,
        firmware_git_commit,
        timer_frequency_hz,
        accel_odr_millihz,
        gyro_odr_millihz,
        accel_range_mg,
        gyro_range_mdps,
        sensor_registers,
    ) = values
    config = IdentityConfig(
        node_id=_enum_value(NodeId, node_raw, "node id"),
        timestamp_source=_enum_value(TimestampSource, timestamp_source_raw, "timestamp source"),
        firmware_version=(major, minor, patch),
        batch_size=batch_size,
        config_generation=config_generation,
        clock_epoch=clock_epoch,
        boot_id=boot_id,
        hardware_device_id=hardware_device_id,
        firmware_git_commit=firmware_git_commit,
        timer_frequency_hz=timer_frequency_hz,
        accel_odr_millihz=accel_odr_millihz,
        gyro_odr_millihz=gyro_odr_millihz,
        accel_range_mg=accel_range_mg,
        gyro_range_mdps=gyro_range_mdps,
        sensor_registers=sensor_registers,
    )
    encode_identity_config(config)
    return config


def encode_clock_request(request: ClockRequest) -> bytes:
    """Encode one clock-exchange write-with-response value."""

    _validate_unsigned(request.transaction_id, 32, "transaction id")
    _validate_unsigned(request.host_send_ns, 64, "host send timestamp")
    return _pack_with_crc(
        _CLOCK_REQUEST,
        MAGIC,
        PROTOCOL_VERSION,
        CLOCK_REQUEST_TYPE,
        request.transaction_id,
        request.host_send_ns,
    )


def decode_clock_request(data: bytes) -> ClockRequest:
    """Decode one clock-exchange request."""

    _, _, _, transaction_id, host_send_ns = _unpack_control(data, _CLOCK_REQUEST, CLOCK_REQUEST_TYPE)
    return ClockRequest(transaction_id=transaction_id, host_send_ns=host_send_ns)


def encode_clock_response(response: ClockResponse) -> bytes:
    """Encode one clock-exchange indication value."""

    for name, value, bits in (
        ("transaction id", response.transaction_id, 32),
        ("host send timestamp", response.host_send_ns, 64),
        ("clock epoch", response.clock_epoch, 32),
        ("device receive timestamp", response.device_receive_us, 64),
        ("device indication timestamp", response.device_indication_queued_us, 64),
    ):
        _validate_unsigned(value, bits, name)
    _validate_positive_unsigned(response.boot_id, 64, "boot id")
    if response.device_indication_queued_us < response.device_receive_us:
        raise ProtocolError("device indication timestamp precedes device receive timestamp")
    return _pack_with_crc(
        _CLOCK_RESPONSE,
        MAGIC,
        PROTOCOL_VERSION,
        CLOCK_RESPONSE_TYPE,
        response.transaction_id,
        response.host_send_ns,
        response.boot_id,
        response.clock_epoch,
        response.device_receive_us,
        response.device_indication_queued_us,
    )


def decode_clock_response(data: bytes) -> ClockResponse:
    """Decode one clock-exchange response."""

    values = _unpack_control(data, _CLOCK_RESPONSE, CLOCK_RESPONSE_TYPE)
    response = ClockResponse(
        transaction_id=values[3],
        host_send_ns=values[4],
        boot_id=values[5],
        clock_epoch=values[6],
        device_receive_us=values[7],
        device_indication_queued_us=values[8],
    )
    if response.device_indication_queued_us < response.device_receive_us:
        raise ProtocolError("device indication timestamp precedes device receive timestamp")
    _validate_positive_unsigned(response.boot_id, 64, "boot id")
    return response


def encode_status(status: Status) -> bytes:
    """Encode one status read/indication value."""

    _enum_value(NodeId, int(status.node_id), "node id")
    _enum_value(AcquisitionState, int(status.acquisition_state), "acquisition state")
    _validate_flags(int(status.flags), _KNOWN_STATUS_FLAGS, "status")
    for name, value, bits in (
        ("clock epoch", status.clock_epoch, 32),
        ("status sequence", status.status_sequence, 32),
        ("last sample sequence", status.last_sample_sequence, 32),
        ("last packet sequence", status.last_packet_sequence, 32),
        ("samples acquired", status.samples_acquired, 64),
        ("packets generated", status.packets_generated, 64),
        ("sensor FIFO overruns", status.sensor_fifo_overruns, 32),
        ("firmware queue overruns", status.firmware_queue_overruns, 32),
        ("transport backpressure events", status.transport_backpressure_events, 32),
        ("samples dropped before packetization", status.samples_dropped_before_packetization, 32),
        ("acquisition buffer high-water samples", status.acquisition_buffer_high_water_samples, 32),
        ("transport queue high-water packets", status.transport_queue_high_water_packets, 32),
        ("last error code", status.last_error_code, 32),
    ):
        _validate_unsigned(value, bits, name)
    _validate_positive_unsigned(status.boot_id, 64, "boot id")
    return _pack_with_crc(
        _STATUS,
        MAGIC,
        PROTOCOL_VERSION,
        STATUS_TYPE,
        int(status.node_id),
        int(status.acquisition_state),
        int(status.flags),
        status.boot_id,
        status.clock_epoch,
        status.status_sequence,
        status.last_sample_sequence,
        status.last_packet_sequence,
        status.samples_acquired,
        status.packets_generated,
        status.sensor_fifo_overruns,
        status.firmware_queue_overruns,
        status.transport_backpressure_events,
        status.samples_dropped_before_packetization,
        status.acquisition_buffer_high_water_samples,
        status.transport_queue_high_water_packets,
        status.last_error_code,
    )


def decode_status(data: bytes) -> Status:
    """Decode one status read/indication value."""

    values = _unpack_control(data, _STATUS, STATUS_TYPE)
    _validate_flags(values[5], _KNOWN_STATUS_FLAGS, "status")
    status = Status(
        node_id=_enum_value(NodeId, values[3], "node id"),
        acquisition_state=_enum_value(AcquisitionState, values[4], "acquisition state"),
        flags=StatusFlags(values[5]),
        boot_id=values[6],
        clock_epoch=values[7],
        status_sequence=values[8],
        last_sample_sequence=values[9],
        last_packet_sequence=values[10],
        samples_acquired=values[11],
        packets_generated=values[12],
        sensor_fifo_overruns=values[13],
        firmware_queue_overruns=values[14],
        transport_backpressure_events=values[15],
        samples_dropped_before_packetization=values[16],
        acquisition_buffer_high_water_samples=values[17],
        transport_queue_high_water_packets=values[18],
        last_error_code=values[19],
    )
    _validate_positive_unsigned(status.boot_id, 64, "boot id")
    return status


def decode_control_message(data: bytes) -> ControlMessage:
    """Dispatch one control-plane value by its declared message type."""

    if len(data) < _CONTROL_HEADER.size + _CRC.size:
        raise ProtocolError("control message is shorter than the minimum value")
    _, _, message_type = _CONTROL_HEADER.unpack(data[: _CONTROL_HEADER.size])
    decoders: dict[int, Callable[[bytes], ControlMessage]] = {
        IDENTITY_CONFIG_TYPE: decode_identity_config,
        CLOCK_REQUEST_TYPE: decode_clock_request,
        CLOCK_RESPONSE_TYPE: decode_clock_response,
        STATUS_TYPE: decode_status,
    }
    decoder = decoders.get(message_type)
    if decoder is None:
        raise ProtocolError(f"unsupported control message type: {message_type}")
    return decoder(data)


def _pack_with_crc(packet_struct: struct.Struct, *values: object) -> bytes:
    payload = packet_struct.pack(*values)
    return payload + _CRC.pack(crc32c(payload))


def _unpack_control(data: bytes, packet_struct: struct.Struct, expected_type: int) -> tuple[Any, ...]:
    expected_size = packet_struct.size + _CRC.size
    if len(data) != expected_size:
        raise ProtocolError(f"control message length must be exactly {expected_size} bytes")
    payload = data[:-_CRC.size]
    received_crc = _CRC.unpack(data[-_CRC.size :])[0]
    if crc32c(payload) != received_crc:
        raise ProtocolError("control message CRC-32C mismatch")
    magic, version, message_type = _CONTROL_HEADER.unpack(payload[: _CONTROL_HEADER.size])
    if magic != MAGIC:
        raise ProtocolError("control message magic does not identify KineIMU Shoulder")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version: {version}")
    if message_type != expected_type:
        raise ProtocolError(f"unexpected control message type: {message_type}")
    return packet_struct.unpack(payload)


def _enum_value[EnumT: IntEnum](enum_type: type[EnumT], value: int, field: str) -> EnumT:
    try:
        return enum_type(value)
    except ValueError as error:
        raise ProtocolError(f"unsupported {field}: {value}") from error


def _validate_positive_unsigned(value: int, bits: int, field: str) -> None:
    _validate_unsigned(value, bits, field)
    if value == 0:
        raise ProtocolError(f"{field} must be positive")


def _validate_unsigned(value: int, bits: int, field: str) -> None:
    if not 0 <= value < 1 << bits:
        raise ProtocolError(f"{field} must fit unsigned {bits}-bit")


def _validate_flags(value: int, known_mask: int, field: str) -> None:
    if value & ~known_mask:
        raise ProtocolError(f"{field} flags contain reserved bits")
