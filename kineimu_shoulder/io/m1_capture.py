"""M1 append-only raw capture framing.

This module preserves notification payloads exactly as received. Telemetry decoding
and sequence quality control are separate concerns.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from dataclasses import dataclass
from typing import BinaryIO

_PAYLOAD_LENGTH = struct.Struct("<I")
_HOST_TIME = struct.Struct("<Q")
_RECORD_HEADER = struct.Struct("<IQ")
MAX_CAPTURE_PAYLOAD_SIZE = 512


class CaptureFormatError(ValueError):
    """Raised when outer raw-capture framing violates the M1 contract."""


class OversizedCaptureRecordError(CaptureFormatError):
    """Describe a declared payload that exceeds the allocation bound."""

    def __init__(self, *, stream_offset: int, payload_length: int) -> None:
        self.stream_offset = stream_offset
        self.payload_length = payload_length
        super().__init__(
            f"capture payload length {payload_length} at byte offset {stream_offset} "
            f"exceeds the {MAX_CAPTURE_PAYLOAD_SIZE}-byte project limit"
        )


class TruncatedCaptureRecordError(CaptureFormatError):
    """Describe an incomplete final capture record without discarding its location."""

    def __init__(
        self,
        *,
        stream_offset: int,
        section: str,
        expected_bytes: int,
        actual_bytes: int,
    ) -> None:
        self.stream_offset = stream_offset
        self.section = section
        self.expected_bytes = expected_bytes
        self.actual_bytes = actual_bytes
        super().__init__(
            f"truncated capture record at byte offset {stream_offset}: {section} "
            f"requires {expected_bytes} bytes, found {actual_bytes}"
        )


@dataclass(frozen=True, slots=True)
class CaptureRecord:
    """One outer record and its byte offset in the raw stream."""

    stream_offset: int
    host_monotonic_ns: int
    payload: bytes


def encode_capture_record(payload: bytes, *, host_monotonic_ns: int) -> bytes:
    """Encode one M1 outer capture record without interpreting its payload."""

    if len(payload) > MAX_CAPTURE_PAYLOAD_SIZE:
        raise CaptureFormatError(
            f"capture payload length {len(payload)} exceeds the {MAX_CAPTURE_PAYLOAD_SIZE}-byte project limit"
        )
    return _RECORD_HEADER.pack(len(payload), host_monotonic_ns) + payload


def iter_capture_records(stream: BinaryIO) -> Iterator[CaptureRecord]:
    """Yield capture records from the stream in stored order."""

    stream_offset = 0
    while length_bytes := _read_exact(stream, _PAYLOAD_LENGTH.size):
        if len(length_bytes) != _PAYLOAD_LENGTH.size:
            raise TruncatedCaptureRecordError(
                stream_offset=stream_offset,
                section="payload length",
                expected_bytes=_PAYLOAD_LENGTH.size,
                actual_bytes=len(length_bytes),
            )
        payload_length = _PAYLOAD_LENGTH.unpack(length_bytes)[0]
        if payload_length > MAX_CAPTURE_PAYLOAD_SIZE:
            raise OversizedCaptureRecordError(
                stream_offset=stream_offset,
                payload_length=payload_length,
            )
        host_time_bytes = _read_exact(stream, _HOST_TIME.size)
        if len(host_time_bytes) != _HOST_TIME.size:
            raise TruncatedCaptureRecordError(
                stream_offset=stream_offset,
                section="host timestamp",
                expected_bytes=_HOST_TIME.size,
                actual_bytes=len(host_time_bytes),
            )
        host_monotonic_ns = _HOST_TIME.unpack(host_time_bytes)[0]
        payload = _read_exact(stream, payload_length)
        if len(payload) != payload_length:
            raise TruncatedCaptureRecordError(
                stream_offset=stream_offset,
                section="payload",
                expected_bytes=payload_length,
                actual_bytes=len(payload),
            )
        yield CaptureRecord(
            stream_offset=stream_offset,
            host_monotonic_ns=host_monotonic_ns,
            payload=payload,
        )
        stream_offset += _RECORD_HEADER.size + payload_length


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)
