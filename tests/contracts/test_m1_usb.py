"""Contract tests for the v1 packet stream carried over USB-C CDC."""

from kineimu_shoulder.io.m1_packet import (
    NodeId,
    PacketFlags,
    Sample,
    SampleFlags,
    SamplePacket,
    encode_sample_packet,
)


def sample_packet(packet_sequence: int, sample_sequence: int) -> bytes:
    return encode_sample_packet(
        SamplePacket(
            node_id=NodeId.A,
            packet_sequence=packet_sequence,
            clock_epoch=3,
            flags=PacketFlags.NONE,
            samples=(
                Sample(
                    sequence=sample_sequence,
                    device_time_us=1_000_000 + sample_sequence * 9_615,
                    flags=SampleFlags.NONE,
                    accel_raw=(100, -200, 300),
                    gyro_raw=(-10, 20, -30),
                ),
            ),
        )
    )


def test_usb_parser_reassembles_fragmented_packet_and_keeps_first_byte_time() -> None:
    from kineimu_shoulder.io.m1_usb import UsbPacketStreamParser

    payload = sample_packet(7, 100)
    parser = UsbPacketStreamParser()

    assert parser.feed(payload[:7], host_monotonic_ns=100) == ()
    packets = parser.feed(payload[7:], host_monotonic_ns=200)

    assert [(packet.stream_offset, packet.host_monotonic_ns, packet.payload) for packet in packets] == [
        (0, 100, payload)
    ]
    assert parser.issues == ()


def test_usb_parser_recovers_concatenated_packets_and_stream_offsets() -> None:
    from kineimu_shoulder.io.m1_usb import UsbPacketStreamParser

    first = sample_packet(7, 100)
    second = sample_packet(8, 101)
    parser = UsbPacketStreamParser()

    packets = parser.feed(first + second, host_monotonic_ns=123)

    assert [(packet.stream_offset, packet.payload) for packet in packets] == [
        (0, first),
        (len(first), second),
    ]


def test_usb_parser_skips_diagnostic_preamble_without_changing_packet_bytes() -> None:
    from kineimu_shoulder.io.m1_usb import UsbPacketStreamParser

    preamble = b"Node A: v1 USB packet stream\r\n"
    payload = sample_packet(7, 100)
    parser = UsbPacketStreamParser()

    packets = parser.feed(preamble + payload, host_monotonic_ns=456)

    assert len(packets) == 1
    assert packets[0].stream_offset == len(preamble)
    assert packets[0].payload == payload
    assert parser.noise_bytes == len(preamble)
    assert parser.issues == ()


def test_usb_parser_reports_bad_crc_and_resynchronizes_to_next_packet() -> None:
    from kineimu_shoulder.io.m1_usb import UsbIssueCode, UsbPacketStreamParser

    corrupted = bytearray(sample_packet(7, 100))
    corrupted[20] ^= 0x01
    valid = sample_packet(8, 101)
    parser = UsbPacketStreamParser()

    packets = parser.feed(bytes(corrupted) + valid, host_monotonic_ns=789)

    assert [packet.payload for packet in packets] == [valid]
    assert parser.issues[0].code is UsbIssueCode.DECODE_ERROR
    assert parser.issues[0].stream_offset == 0
    assert parser.issues[0].raw_bytes == bytes(corrupted)


def test_usb_parser_reports_truncated_tail_without_returning_partial_packet() -> None:
    from kineimu_shoulder.io.m1_usb import UsbIssueCode, UsbPacketStreamParser

    payload = sample_packet(7, 100)
    parser = UsbPacketStreamParser()

    assert parser.feed(payload[:10], host_monotonic_ns=999) == ()
    parser.finish()

    assert len(parser.issues) == 1
    assert parser.issues[0].code is UsbIssueCode.TRUNCATED_PACKET
    assert parser.issues[0].stream_offset == 0
    assert parser.issues[0].raw_bytes == payload[:10]


def test_usb_parser_exposes_packet_boundary_for_timed_capture_stop() -> None:
    from kineimu_shoulder.io.m1_usb import UsbPacketStreamParser

    payload = sample_packet(7, 100)
    parser = UsbPacketStreamParser()
    assert parser.at_packet_boundary
    parser.feed(payload[:10], host_monotonic_ns=1)
    assert not parser.at_packet_boundary
    parser.feed(payload[10:], host_monotonic_ns=2)
    assert parser.at_packet_boundary
