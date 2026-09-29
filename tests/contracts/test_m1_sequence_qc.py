"""Sequence-quality tests for captured M1 telemetry."""

from io import BytesIO

from kineimu_shoulder.io.m1_capture import encode_capture_record
from kineimu_shoulder.io.m1_packet import (
    NodeId,
    PacketFlags,
    Sample,
    SampleFlags,
    SamplePacket,
    encode_sample_packet,
)


def packet(
    packet_sequence: int,
    sample_sequences: tuple[int, ...],
    *,
    clock_epoch: int = 1,
    node_id: NodeId = NodeId.A,
    first_device_time_us: int = 10_000,
) -> SamplePacket:
    return SamplePacket(
        node_id=node_id,
        packet_sequence=packet_sequence,
        clock_epoch=clock_epoch,
        flags=PacketFlags.NONE,
        samples=tuple(
            Sample(
                sequence=sequence,
                device_time_us=first_device_time_us + index * 10_000,
                flags=SampleFlags.NONE,
                accel_raw=(0, 0, 0),
                gyro_raw=(0, 0, 0),
            )
            for index, sequence in enumerate(sample_sequences)
        ),
    )


def capture(*payloads: bytes) -> BytesIO:
    return BytesIO(
        b"".join(
            encode_capture_record(payload, host_monotonic_ns=index + 1)
            for index, payload in enumerate(payloads)
        )
    )


def test_qc_preserves_malformed_payload_and_continues_with_next_record() -> None:
    from kineimu_shoulder.io.m1_qc import QcIssueCode, audit_capture_stream

    stream = capture(b"", encode_sample_packet(packet(7, (100,))))

    report = audit_capture_stream(stream, expected_node_id=NodeId.A)

    # Source: the two literal outer records above contain one malformed value
    # followed by one valid one-sample packet.
    assert report.records_seen == 2
    assert report.packets_decoded == 1
    assert report.samples_decoded == 1
    assert report.decode_errors == 1
    assert [issue.code for issue in report.issues] == [QcIssueCode.DECODE_ERROR]


def test_qc_reports_truncated_tail_after_auditing_complete_records() -> None:
    from kineimu_shoulder.io.m1_qc import QcIssueCode, audit_capture_stream

    complete = capture(encode_sample_packet(packet(7, (100,)))).getvalue()

    report = audit_capture_stream(BytesIO(complete + b"\x02\x00"), expected_node_id=NodeId.A)

    # Source: one complete literal record followed by a two-byte partial length field.
    assert report.records_seen == 1
    assert report.packets_decoded == 1
    assert report.framing_errors == 1
    assert report.issues[-1].code is QcIssueCode.TRUNCATED_RECORD
    assert report.issues[-1].stream_offset == len(complete)


def test_qc_counts_duplicate_reordered_and_missing_packets_without_repair() -> None:
    from kineimu_shoulder.io.m1_qc import QcIssueCode, audit_capture_stream

    payloads = (
        encode_sample_packet(packet(10, (100,), first_device_time_us=10_000)),
        encode_sample_packet(packet(10, (101,), first_device_time_us=20_000)),
        encode_sample_packet(packet(9, (102,), first_device_time_us=30_000)),
        encode_sample_packet(packet(12, (103,), first_device_time_us=40_000)),
    )

    report = audit_capture_stream(capture(*payloads), expected_node_id=NodeId.A)

    # Source: modulo-uint32 hand audit of 10, 10, 9, 12 relative to the
    # advancing frontier: duplicate, reordered, then one missing value (11).
    assert report.packets_decoded == 4
    assert report.packet_duplicates == 1
    assert report.packet_reordered == 1
    assert report.packets_missing == 1
    assert [issue.code for issue in report.issues] == [
        QcIssueCode.DUPLICATE_PACKET,
        QcIssueCode.REORDERED_PACKET,
        QcIssueCode.MISSING_PACKETS,
    ]


def test_qc_counts_duplicate_reordered_and_missing_samples_separately() -> None:
    from kineimu_shoulder.io.m1_qc import QcIssueCode, audit_capture_stream

    payloads = (
        encode_sample_packet(packet(1, (100, 101), first_device_time_us=10_000)),
        encode_sample_packet(packet(2, (101, 99), first_device_time_us=30_000)),
        encode_sample_packet(packet(3, (105,), first_device_time_us=50_000)),
    )

    report = audit_capture_stream(capture(*payloads), expected_node_id=NodeId.A)

    # Source: modulo-uint32 hand audit of 100, 101, 101, 99, 105:
    # one duplicate, one reordered, and missing values 102-104.
    assert report.samples_decoded == 5
    assert report.sample_duplicates == 1
    assert report.sample_reordered == 1
    assert report.samples_missing == 3
    assert [issue.code for issue in report.issues] == [
        QcIssueCode.DUPLICATE_SAMPLE,
        QcIssueCode.REORDERED_SAMPLE,
        QcIssueCode.MISSING_SAMPLES,
    ]


def test_qc_flags_duplicate_and_reordered_device_timestamps() -> None:
    from kineimu_shoulder.io.m1_qc import QcIssueCode, audit_capture_stream

    payloads = tuple(
        encode_sample_packet(packet(packet_sequence, (99 + packet_sequence,), first_device_time_us=device_time_us))
        for packet_sequence, device_time_us in ((1, 10_000), (2, 10_000), (3, 9_000), (4, 20_000))
    )

    report = audit_capture_stream(capture(*payloads), expected_node_id=NodeId.A)

    # Source: literal device times 10000, 10000, 9000, 20000 compared with
    # the monotonic timestamp frontier.
    assert report.timestamp_duplicates == 1
    assert report.timestamp_reordered == 1
    assert [issue.code for issue in report.issues] == [
        QcIssueCode.DUPLICATE_TIMESTAMP,
        QcIssueCode.REORDERED_TIMESTAMP,
    ]


def test_qc_resets_sequence_frontiers_at_clock_epoch_boundary() -> None:
    from kineimu_shoulder.io.m1_qc import QcIssueCode, audit_capture_stream

    payloads = (
        encode_sample_packet(packet(10, (100,), clock_epoch=7, first_device_time_us=90_000)),
        encode_sample_packet(packet(0, (0,), clock_epoch=8, first_device_time_us=1_000)),
    )

    report = audit_capture_stream(capture(*payloads), expected_node_id=NodeId.A)

    # Source: the frozen contract starts a new sequence/timestamp audit segment
    # when clock_epoch changes; the literal stream contains exactly one change.
    assert report.epoch_changes == 1
    assert report.packet_reordered == 0
    assert report.sample_reordered == 0
    assert report.timestamp_reordered == 0
    assert [issue.code for issue in report.issues] == [QcIssueCode.EPOCH_CHANGE]


def test_qc_flags_wrong_node_without_polluting_expected_node_sequences() -> None:
    from kineimu_shoulder.io.m1_qc import QcIssueCode, audit_capture_stream

    payloads = (
        encode_sample_packet(packet(900, (900,), node_id=NodeId.B)),
        encode_sample_packet(packet(5, (50,), node_id=NodeId.A)),
        encode_sample_packet(packet(6, (51,), node_id=NodeId.A, first_device_time_us=20_000)),
    )

    report = audit_capture_stream(capture(*payloads), expected_node_id=NodeId.A)

    # Source: the literal stream contains one Node B packet and two contiguous
    # Node A packet/sample sequences.
    assert report.packets_decoded == 3
    assert report.node_mismatches == 1
    assert report.packet_reordered == 0
    assert report.packets_missing == 0
    assert report.sample_reordered == 0
    assert report.samples_missing == 0
    assert [issue.code for issue in report.issues] == [QcIssueCode.NODE_MISMATCH]


def test_qc_treats_uint32_counter_wrap_as_continuity() -> None:
    from kineimu_shoulder.io.m1_qc import audit_capture_stream

    payloads = (
        encode_sample_packet(packet(0xFFFF_FFFF, (0xFFFF_FFFF,), first_device_time_us=10_000)),
        encode_sample_packet(packet(0, (0,), first_device_time_us=20_000)),
    )

    report = audit_capture_stream(capture(*payloads), expected_node_id=NodeId.A)

    # Source: unsigned-32 modulo arithmetic defines 0xffffffff -> 0 as +1.
    assert report.packets_decoded == 2
    assert report.samples_decoded == 2
    assert report.issues == ()


def test_qc_reports_oversize_declaration_at_record_start_offset() -> None:
    from kineimu_shoulder.io.m1_qc import QcIssueCode, audit_capture_stream

    complete = capture(encode_sample_packet(packet(1, (1,)))).getvalue()
    oversize_header = b"\x01\x02\x00\x00"

    report = audit_capture_stream(BytesIO(complete + oversize_header), expected_node_id=NodeId.A)

    # Source: the literal little-endian declaration is 513, one byte beyond
    # the frozen 512-byte inclusive parser bound.
    assert report.framing_errors == 1
    assert report.issues[-1].code is QcIssueCode.OVERSIZED_RECORD
    assert report.issues[-1].stream_offset == len(complete)


def test_qc_recognizes_nonadjacent_replays_as_duplicates() -> None:
    from kineimu_shoulder.io.m1_qc import QcIssueCode, audit_capture_stream

    payloads = tuple(
        encode_sample_packet(packet(packet_sequence, (sample_sequence,), first_device_time_us=device_time_us))
        for packet_sequence, sample_sequence, device_time_us in (
            (8, 80, 10_000),
            (9, 81, 20_000),
            (10, 82, 30_000),
            (9, 81, 40_000),
        )
    )

    report = audit_capture_stream(capture(*payloads), expected_node_id=NodeId.A)

    # Source: literal sequence histories 8, 9, 10, 9 and 80, 81, 82, 81;
    # the final values were already observed in the same counter cycle.
    assert report.packet_duplicates == 1
    assert report.packet_reordered == 0
    assert report.sample_duplicates == 1
    assert report.sample_reordered == 0
    assert [issue.code for issue in report.issues] == [
        QcIssueCode.DUPLICATE_PACKET,
        QcIssueCode.DUPLICATE_SAMPLE,
    ]
