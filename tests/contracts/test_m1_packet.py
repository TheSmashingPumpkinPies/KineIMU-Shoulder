"""Executable contract tests for the M1 BLE sample packet."""

from dataclasses import replace

import pytest

from kineimu_shoulder.io.m1_packet import (
    MAX_SAMPLES_PER_PACKET,
    NodeId,
    PacketFlags,
    ProtocolError,
    Sample,
    SampleFlags,
    SamplePacket,
    crc32c,
    decode_sample_packet,
    encode_sample_packet,
    required_att_mtu,
)

# Hand-checked little-endian fixture. The CRC-32C implementation is independently
# anchored below to the standard "123456789" check value.
GOLDEN_PACKET_HEX = (
    "4b490101010100000700000002000000"
    "640000004e61bc00000000000000640038ff803e0a00ecff1e00"
    "ff633586"
)


def sample_packet() -> SamplePacket:
    return SamplePacket(
        node_id=NodeId.A,
        packet_sequence=7,
        clock_epoch=2,
        flags=PacketFlags.NONE,
        samples=(
            Sample(
                sequence=100,
                device_time_us=12_345_678,
                flags=SampleFlags.NONE,
                accel_raw=(100, -200, 16_000),
                gyro_raw=(10, -20, 30),
            ),
        ),
    )


def test_crc32c_matches_standard_check_value() -> None:
    # CRC-32C/Castagnoli check value for the ASCII string "123456789".
    assert crc32c(b"123456789") == 0xE306_9283


def test_encoder_matches_m1_golden_packet() -> None:
    assert encode_sample_packet(sample_packet()).hex() == GOLDEN_PACKET_HEX


def test_decoder_recovers_every_transmitted_field() -> None:
    assert decode_sample_packet(bytes.fromhex(GOLDEN_PACKET_HEX)) == sample_packet()


def test_decoder_rejects_corrupted_packet() -> None:
    corrupted = bytearray.fromhex(GOLDEN_PACKET_HEX)
    corrupted[20] ^= 0x01

    with pytest.raises(ProtocolError, match="CRC"):
        decode_sample_packet(bytes(corrupted))


def test_encoder_rejects_more_than_four_samples() -> None:
    packet = sample_packet()
    too_many = replace(packet, samples=packet.samples * (MAX_SAMPLES_PER_PACKET + 1))

    with pytest.raises(ProtocolError, match="sample count"):
        encode_sample_packet(too_many)


@pytest.mark.parametrize(
    ("sample_count", "expected_mtu"),
    [(1, 49), (4, 127)],
)
def test_required_att_mtu_includes_notification_overhead(
    sample_count: int,
    expected_mtu: int,
) -> None:
    assert required_att_mtu(sample_count) == expected_mtu
