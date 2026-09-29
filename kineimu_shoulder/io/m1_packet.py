"""Versioned M1 BLE sample-packet codec.

The packet carries immutable sensor counts and device timestamps. Unit and axis
conversion belongs in the host adapter, where the session manifest records the
configuration needed to reproduce it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum, IntFlag

MAGIC = 0x494B
PROTOCOL_VERSION = 1
SAMPLE_PACKET_TYPE = 1
MAX_SAMPLES_PER_PACKET = 4

_HEADER = struct.Struct("<HBBBBHII")
_SAMPLE = struct.Struct("<IQHhhhhhh")
_CRC = struct.Struct("<I")

HEADER_SIZE = _HEADER.size
SAMPLE_SIZE = _SAMPLE.size
CRC_SIZE = _CRC.size

_KNOWN_PACKET_FLAGS = 0x000F
_KNOWN_SAMPLE_FLAGS = 0x0007


class ProtocolError(ValueError):
    """Raised when a packet violates the M1 wire contract."""


class NodeId(IntEnum):
    """Stable on-wire node identity."""

    A = 1
    B = 2


class PacketFlags(IntFlag):
    """Conditions observed since the preceding packet."""

    NONE = 0
    SENSOR_FIFO_OVERRUN = 1 << 0
    FIRMWARE_QUEUE_OVERRUN = 1 << 1
    TRANSPORT_BACKPRESSURE = 1 << 2
    DISCONTINUITY_BEFORE_FIRST_SAMPLE = 1 << 3


class SampleFlags(IntFlag):
    """Quality flags applying to one sensor sample."""

    NONE = 0
    ACCEL_CLIPPED = 1 << 0
    GYRO_CLIPPED = 1 << 1
    TIMESTAMP_RECONSTRUCTED = 1 << 2


@dataclass(frozen=True, slots=True)
class Sample:
    """One immutable raw IMU sample."""

    sequence: int
    device_time_us: int
    flags: SampleFlags
    accel_raw: tuple[int, int, int]
    gyro_raw: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class SamplePacket:
    """One BLE notification payload containing one to four samples."""

    node_id: NodeId
    packet_sequence: int
    clock_epoch: int
    flags: PacketFlags
    samples: tuple[Sample, ...]


def crc32c(data: bytes) -> int:
    """Return CRC-32C/Castagnoli using the reflected polynomial."""

    crc = 0xFFFF_FFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F6_3B78 if crc & 1 else 0)
    return crc ^ 0xFFFF_FFFF


def required_att_mtu(sample_count: int) -> int:
    """Return the minimum ATT MTU for one notification without ATT truncation."""

    _validate_sample_count(sample_count)
    return HEADER_SIZE + SAMPLE_SIZE * sample_count + CRC_SIZE + 3


def encode_sample_packet(packet: SamplePacket) -> bytes:
    """Encode and validate a sample packet."""

    sample_count = len(packet.samples)
    _validate_sample_count(sample_count)
    _validate_unsigned(packet.packet_sequence, 32, "packet sequence")
    _validate_unsigned(packet.clock_epoch, 32, "clock epoch")
    _validate_flags(int(packet.flags), _KNOWN_PACKET_FLAGS, "packet")

    payload = bytearray(
        _HEADER.pack(
            MAGIC,
            PROTOCOL_VERSION,
            SAMPLE_PACKET_TYPE,
            int(packet.node_id),
            sample_count,
            int(packet.flags),
            packet.packet_sequence,
            packet.clock_epoch,
        )
    )
    for sample in packet.samples:
        _validate_unsigned(sample.sequence, 32, "sample sequence")
        _validate_unsigned(sample.device_time_us, 64, "device timestamp")
        _validate_flags(int(sample.flags), _KNOWN_SAMPLE_FLAGS, "sample")
        raw_values = (*sample.accel_raw, *sample.gyro_raw)
        for value in raw_values:
            if not -32_768 <= value <= 32_767:
                raise ProtocolError("raw sensor count must fit signed 16-bit")
        payload.extend(
            _SAMPLE.pack(
                sample.sequence,
                sample.device_time_us,
                int(sample.flags),
                *raw_values,
            )
        )

    return bytes(payload) + _CRC.pack(crc32c(bytes(payload)))


def decode_sample_packet(data: bytes) -> SamplePacket:
    """Decode a packet and reject corruption or unsupported fields."""

    if len(data) < HEADER_SIZE + SAMPLE_SIZE + CRC_SIZE:
        raise ProtocolError("packet is shorter than the minimum sample packet")

    payload = data[:-CRC_SIZE]
    received_crc = _CRC.unpack(data[-CRC_SIZE:])[0]
    if crc32c(payload) != received_crc:
        raise ProtocolError("packet CRC-32C mismatch")

    magic, version, packet_type, node_raw, sample_count, flags_raw, packet_sequence, clock_epoch = _HEADER.unpack(
        payload[:HEADER_SIZE]
    )
    if magic != MAGIC:
        raise ProtocolError("packet magic does not identify KineIMU Shoulder")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version: {version}")
    if packet_type != SAMPLE_PACKET_TYPE:
        raise ProtocolError(f"unsupported packet type: {packet_type}")
    _validate_sample_count(sample_count)
    expected_size = HEADER_SIZE + SAMPLE_SIZE * sample_count + CRC_SIZE
    if len(data) != expected_size:
        raise ProtocolError("packet length does not match sample count")
    _validate_flags(flags_raw, _KNOWN_PACKET_FLAGS, "packet")

    try:
        node_id = NodeId(node_raw)
    except ValueError as error:
        raise ProtocolError(f"unsupported node id: {node_raw}") from error

    samples: list[Sample] = []
    offset = HEADER_SIZE
    for _ in range(sample_count):
        sequence, device_time_us, sample_flags_raw, *raw_values = _SAMPLE.unpack(
            payload[offset : offset + SAMPLE_SIZE]
        )
        _validate_flags(sample_flags_raw, _KNOWN_SAMPLE_FLAGS, "sample")
        samples.append(
            Sample(
                sequence=sequence,
                device_time_us=device_time_us,
                flags=SampleFlags(sample_flags_raw),
                accel_raw=(raw_values[0], raw_values[1], raw_values[2]),
                gyro_raw=(raw_values[3], raw_values[4], raw_values[5]),
            )
        )
        offset += SAMPLE_SIZE

    return SamplePacket(
        node_id=node_id,
        packet_sequence=packet_sequence,
        clock_epoch=clock_epoch,
        flags=PacketFlags(flags_raw),
        samples=tuple(samples),
    )


def _validate_sample_count(sample_count: int) -> None:
    if not 1 <= sample_count <= MAX_SAMPLES_PER_PACKET:
        raise ProtocolError(f"sample count must be between 1 and {MAX_SAMPLES_PER_PACKET}")


def _validate_unsigned(value: int, bits: int, field: str) -> None:
    if not 0 <= value < 1 << bits:
        raise ProtocolError(f"{field} must fit unsigned {bits}-bit")


def _validate_flags(value: int, known_mask: int, field: str) -> None:
    if value & ~known_mask:
        raise ProtocolError(f"{field} flags contain reserved bits")
