"""Incremental parser for the v1 sample-packet stream over USB-C CDC.

The firmware writes the frozen v1 packet payloads consecutively to the CDC
byte stream. CDC does not preserve write boundaries, so this parser finds the
packet magic, reads the sample count from the fixed header, and validates the
complete candidate with the shared packet codec. It reports discarded
diagnostic bytes and malformed candidates without changing valid payloads.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from kineimu_shoulder.io.m1_packet import (
	CRC_SIZE,
	HEADER_SIZE,
	MAGIC,
	MAX_SAMPLES_PER_PACKET,
	PROTOCOL_VERSION,
	SAMPLE_PACKET_TYPE,
	SAMPLE_SIZE,
	ProtocolError,
	decode_sample_packet,
)

_MAGIC_BYTES = MAGIC.to_bytes(2, "little")
_SAMPLE_COUNT_OFFSET = 5


class UsbIssueCode(StrEnum):
    """Stable issue categories for a raw USB-C byte stream."""

    INVALID_HEADER = "invalid_header"
    DECODE_ERROR = "decode_error"
    TRUNCATED_PACKET = "truncated_packet"


@dataclass(frozen=True, slots=True)
class UsbStreamIssue:
    """One malformed or incomplete candidate in the raw USB byte stream."""

    code: UsbIssueCode
    stream_offset: int
    detail: str
    raw_bytes: bytes


@dataclass(frozen=True, slots=True)
class UsbPacket:
    """One validated v1 packet and its first-byte host arrival timestamp."""

    stream_offset: int
    host_monotonic_ns: int
    payload: bytes


class UsbPacketStreamParser:
    """Incrementally recover validated v1 packet payloads from CDC bytes."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._buffer_start_offset = 0
        self._total_bytes_seen = 0
        self._chunk_spans: deque[tuple[int, int]] = deque()
        self._issues: list[UsbStreamIssue] = []
        self._noise_bytes = 0

    @property
    def issues(self) -> tuple[UsbStreamIssue, ...]:
        """Return malformed-candidate evidence in stream order."""

        return tuple(self._issues)

    @property
    def noise_bytes(self) -> int:
        """Return bytes discarded before a candidate magic value."""

        return self._noise_bytes

    @property
    def at_packet_boundary(self) -> bool:
        """True when no candidate packet bytes remain from prior reads."""

        return not self._buffer

    def feed(self, data: bytes, *, host_monotonic_ns: int) -> tuple[UsbPacket, ...]:
        """Feed one read chunk and return every complete valid packet found."""

        if not data:
            return ()
        self._buffer.extend(data)
        self._chunk_spans.append((len(data), host_monotonic_ns))
        self._total_bytes_seen += len(data)
        return tuple(self._drain())

    def finish(self) -> None:
        """Finalize the stream and report an incomplete magic-prefixed tail."""

        # ``feed`` drains every complete packet. A final non-magic suffix is
        # diagnostic/preamble noise; only a magic-prefixed suffix is a packet
        # truncation that must remain visible to the caller.
        self._drain()
        if not self._buffer:
            return
        magic_index = self._buffer.find(_MAGIC_BYTES)
        if magic_index < 0:
            self._discard(len(self._buffer), count_as_noise=True)
            return
        if magic_index > 0:
            self._discard(magic_index, count_as_noise=True)
        if self._buffer:
            raw_bytes = bytes(self._buffer)
            self._issues.append(
                UsbStreamIssue(
                    code=UsbIssueCode.TRUNCATED_PACKET,
                    stream_offset=self._buffer_start_offset,
                    detail=(
                        f"truncated USB packet at byte offset {self._buffer_start_offset}: "
                        f"found {len(raw_bytes)} bytes"
                    ),
                    raw_bytes=raw_bytes,
                )
            )
            self._discard(len(self._buffer))

    def _drain(self) -> list[UsbPacket]:
        packets: list[UsbPacket] = []
        while self._buffer:
            magic_index = self._buffer.find(_MAGIC_BYTES)
            if magic_index < 0:
                # Keep one possible first magic byte for a split two-byte
                # signature across reads.
                keep = 1 if self._buffer[-1] == _MAGIC_BYTES[0] else 0
                discard = len(self._buffer) - keep
                if discard:
                    self._discard(discard, count_as_noise=True)
                break
            if magic_index:
                self._discard(magic_index, count_as_noise=True)
                continue

            if len(self._buffer) < HEADER_SIZE:
                break
            if (
                self._buffer[2] != PROTOCOL_VERSION
                or self._buffer[3] != SAMPLE_PACKET_TYPE
                or not 1 <= self._buffer[_SAMPLE_COUNT_OFFSET] <= MAX_SAMPLES_PER_PACKET
            ):
                self._record_invalid_header()
                self._discard(1)
                continue

            sample_count = self._buffer[_SAMPLE_COUNT_OFFSET]
            expected_size = HEADER_SIZE + SAMPLE_SIZE * sample_count + CRC_SIZE
            if len(self._buffer) < expected_size:
                break

            payload = bytes(self._buffer[:expected_size])
            try:
                decode_sample_packet(payload)
            except ProtocolError as error:
                self._issues.append(
                    UsbStreamIssue(
                        code=UsbIssueCode.DECODE_ERROR,
                        stream_offset=self._buffer_start_offset,
                        detail=str(error),
                        raw_bytes=payload,
                    )
                )
                # Drop one byte only; the next valid magic is still available
                # for deterministic recovery after a corrupted candidate.
                self._discard(1)
                continue

            packets.append(
                UsbPacket(
                    stream_offset=self._buffer_start_offset,
                    host_monotonic_ns=self._first_byte_host_time(),
                    payload=payload,
                )
            )
            self._discard(expected_size)
        return packets

    def _record_invalid_header(self) -> None:
        raw_bytes = bytes(self._buffer[:HEADER_SIZE])
        self._issues.append(
            UsbStreamIssue(
                code=UsbIssueCode.INVALID_HEADER,
                stream_offset=self._buffer_start_offset,
                detail="USB packet header has unsupported version, type or sample count",
                raw_bytes=raw_bytes,
            )
        )

    def _first_byte_host_time(self) -> int:
        return self._chunk_spans[0][1]

    def _discard(self, count: int, *, count_as_noise: bool = False) -> None:
        if count <= 0:
            return
        if count > len(self._buffer):
            raise ValueError("cannot discard more bytes than buffered")
        del self._buffer[:count]
        self._buffer_start_offset += count
        if count_as_noise:
            self._noise_bytes += count

        remaining = count
        while remaining:
            span_length, host_time = self._chunk_spans[0]
            if remaining >= span_length:
                remaining -= span_length
                self._chunk_spans.popleft()
            else:
                self._chunk_spans[0] = (span_length - remaining, host_time)
                remaining = 0
