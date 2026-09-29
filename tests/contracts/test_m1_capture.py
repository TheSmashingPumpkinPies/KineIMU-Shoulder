"""Contract tests for the M1 append-only raw capture framing."""

from io import BytesIO

import pytest


class ShortReadBytesIO(BytesIO):
    """Return small chunks even when the parser requests more bytes."""

    def read(self, size: int = -1, /) -> bytes:
        return super().read(min(size, 2) if size >= 0 else size)


def test_capture_record_encoder_matches_frozen_little_endian_layout() -> None:
    from kineimu_shoulder.io.m1_capture import encode_capture_record

    encoded = encode_capture_record(
        b"\xaa\x55",
        host_monotonic_ns=0x0102_0304_0506_0708,
    )

    # Source: protocols/M1_ACQUISITION_CONTRACT.md "Raw capture files":
    # uint32 payload length, uint64 host monotonic ns, then payload, all little-endian.
    assert encoded == bytes.fromhex("020000000807060504030201aa55")


def test_capture_parser_recovers_concatenated_records_and_offsets() -> None:
    from kineimu_shoulder.io.m1_capture import encode_capture_record, iter_capture_records

    first = encode_capture_record(b"abc", host_monotonic_ns=10)
    second = encode_capture_record(b"de", host_monotonic_ns=20)

    records = list(iter_capture_records(BytesIO(first + second)))

    # Source: the frozen outer-record byte layout; offsets are the hand-summed
    # lengths of the preceding 12-byte header and literal payload.
    assert [(record.stream_offset, record.host_monotonic_ns, record.payload) for record in records] == [
        (0, 10, b"abc"),
        (len(first), 20, b"de"),
    ]


def test_capture_record_encoder_rejects_payload_above_project_bound() -> None:
    from kineimu_shoulder.io.m1_capture import CaptureFormatError, encode_capture_record

    with pytest.raises(CaptureFormatError, match="512"):
        encode_capture_record(b"x" * 513, host_monotonic_ns=10)


def test_capture_parser_rejects_oversize_length_before_reading_record_body() -> None:
    from kineimu_shoulder.io.m1_capture import CaptureFormatError, iter_capture_records

    stream = BytesIO(b"\x01\x02\x00\x00" + b"\x00" * 8 + b"x" * 513)

    with pytest.raises(CaptureFormatError, match="513.*512"):
        list(iter_capture_records(stream))

    assert stream.tell() == 4


@pytest.mark.parametrize(
    ("stored", "section", "expected", "actual"),
    [
        (b"\x03\x00", "payload length", 4, 2),
        (b"\x03\x00\x00\x00" + b"\x01" * 4, "host timestamp", 8, 4),
        (b"\x03\x00\x00\x00" + b"\x01" * 8 + b"ab", "payload", 3, 2),
    ],
)
def test_capture_parser_reports_truncated_record_section(
    stored: bytes,
    section: str,
    expected: int,
    actual: int,
) -> None:
    from kineimu_shoulder.io.m1_capture import TruncatedCaptureRecordError, iter_capture_records

    with pytest.raises(TruncatedCaptureRecordError) as captured:
        list(iter_capture_records(BytesIO(stored)))

    # Source: the parameterized literal truncation fixture and frozen field widths.
    assert captured.value.stream_offset == 0
    assert captured.value.section == section
    assert captured.value.expected_bytes == expected
    assert captured.value.actual_bytes == actual


def test_capture_parser_accumulates_short_reads_until_record_is_complete() -> None:
    from kineimu_shoulder.io.m1_capture import encode_capture_record, iter_capture_records

    encoded = encode_capture_record(b"abcdef", host_monotonic_ns=123)

    records = list(iter_capture_records(ShortReadBytesIO(encoded)))

    # Source: literal values supplied to encode_capture_record above.
    assert [(record.host_monotonic_ns, record.payload) for record in records] == [(123, b"abcdef")]


def test_capture_parser_accepts_exactly_512_payload_bytes() -> None:
    from kineimu_shoulder.io.m1_capture import encode_capture_record, iter_capture_records

    payload = bytes(range(256)) * 2
    encoded = encode_capture_record(payload, host_monotonic_ns=123)

    records = list(iter_capture_records(BytesIO(encoded)))

    # Source: protocols/M1_ACQUISITION_CONTRACT.md sets 512 bytes as inclusive.
    assert len(records) == 1
    assert records[0].payload == payload
