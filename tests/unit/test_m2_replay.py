"""M2.1 replay gates against independently constructed M1 packets."""

from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from kineimu_shoulder.io.m1_capture import encode_capture_record
from kineimu_shoulder.io.m1_packet import (
    NodeId,
    PacketFlags,
    Sample,
    SampleFlags,
    SamplePacket,
    encode_sample_packet,
)
from kineimu_shoulder.io.m1_qc import QcIssueCode
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorToNodeTransform
from kineimu_shoulder.io.m2_replay import replay_capture


def _config() -> M1RawCountAdapterConfig:
    return M1RawCountAdapterConfig(
        accel_range_g=4.0,
        gyro_range_dps=500.0,
        accel_sensitivity_mg_per_lsb=0.122,
        gyro_sensitivity_mdps_per_lsb=17.5,
        axis_transform=SensorToNodeTransform(
            sensor_axes=("sx", "sy", "sz"),
            node_axes=("nx", "ny", "nz"),
            sensor_to_node=((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
            description="declared +90 degree sensor-to-node rotation",
        ),
    )


def _packet(sequence: int, time_us: int, *, epoch: int = 7, node: NodeId = NodeId.A) -> bytes:
    return encode_sample_packet(
        SamplePacket(
            node_id=node,
            packet_sequence=sequence,
            clock_epoch=epoch,
            flags=PacketFlags.NONE,
            samples=(
                Sample(
                    sequence=sequence,
                    device_time_us=time_us,
                    flags=SampleFlags.ACCEL_CLIPPED if sequence == 1 else SampleFlags.NONE,
                    accel_raw=(100, 0, -20),
                    gyro_raw=(0, 100, 0),
                ),
            ),
        )
    )


def _write(path: Path, *packets: bytes) -> str:
    data = b"".join(
        encode_capture_record(packet, host_monotonic_ns=1000 + index)
        for index, packet in enumerate(packets)
    )
    path.write_bytes(data)
    return sha256(data).hexdigest()


def test_replay_is_repeatable_and_preserves_sensor_si_qc_and_provenance(tmp_path: Path) -> None:
    path = tmp_path / "node-a.kimu"
    digest = _write(path, _packet(0, 10_000), _packet(1, 20_000))

    first = replay_capture(path, expected_sha256=digest, expected_node_id=NodeId.A, config=_config())
    second = replay_capture(path, expected_sha256=digest, expected_node_id=NodeId.A, config=_config())

    assert first.source_sha256 == second.source_sha256 == digest
    assert first.source_path == path
    assert first.node_id is NodeId.A
    assert first.qc == second.qc
    assert first.qc.issues == ()
    assert len(first.epochs) == 1
    epoch = first.epochs[0]
    assert epoch.clock_epoch == 7
    assert epoch.packet_sequences == (0, 1)
    assert epoch.host_monotonic_ns == (1000, 1001)
    assert epoch.sensor_data.sample_sequences == (0, 1)
    assert epoch.sensor_data.device_time_us == (10_000, 20_000)
    assert epoch.sensor_data.sample_flags == (SampleFlags.NONE, SampleFlags.ACCEL_CLIPPED)
    assert epoch.sensor_data.accel_raw_counts.tolist() == [[100, 0, -20], [100, 0, -20]]
    # Literal M1 sensitivities: 0.122 mg/LSB and 17.5 mdps/LSB. The
    # declared nonidentity node transform must not act before calibration.
    np.testing.assert_allclose(epoch.sensor_data.accel_mps2[0], [0.11964113, 0.0, -0.023928226], atol=1e-12)
    np.testing.assert_allclose(epoch.sensor_data.gyro_rads[0], [0.0, 0.03054326190990077, 0.0], atol=1e-12)
    np.testing.assert_array_equal(first.epochs[0].sensor_data.accel_mps2, second.epochs[0].sensor_data.accel_mps2)
    assert path.read_bytes() == b"".join(
        encode_capture_record(packet, host_monotonic_ns=1000 + index)
        for index, packet in enumerate((_packet(0, 10_000), _packet(1, 20_000)))
    )


def test_replay_rejects_bad_source_hash_before_decode(tmp_path: Path) -> None:
    path = tmp_path / "node-a.kimu"
    _write(path, _packet(0, 10_000))
    with pytest.raises(ValueError, match="SHA-256"):
        replay_capture(path, expected_sha256="0" * 64, expected_node_id=NodeId.A, config=_config())


def test_replay_rejects_crc_corruption_even_when_file_hash_matches(tmp_path: Path) -> None:
    path = tmp_path / "node-a.kimu"
    digest = _write(path, _packet(0, 10_000))
    data = bytearray(path.read_bytes())
    data[30] ^= 1
    path.write_bytes(data)
    assert sha256(data).hexdigest() != digest
    with pytest.raises(ValueError, match="decode_error"):
        replay_capture(path, expected_sha256=sha256(data).hexdigest(), expected_node_id=NodeId.A, config=_config())


def test_replay_rejects_wrong_node_even_with_matching_hash(tmp_path: Path) -> None:
    path = tmp_path / "node-a.kimu"
    digest = _write(path, _packet(0, 10_000, node=NodeId.B))
    with pytest.raises(ValueError, match="node_mismatch"):
        replay_capture(path, expected_sha256=digest, expected_node_id=NodeId.A, config=_config())


@pytest.mark.parametrize("times", [(10_000, 10_000), (10_000, 9_000)])
def test_replay_rejects_nonincreasing_time_within_epoch(tmp_path: Path, times: tuple[int, int]) -> None:
    path = tmp_path / "node-a.kimu"
    digest = _write(path, _packet(0, times[0]), _packet(1, times[1]))
    with pytest.raises(ValueError, match="timestamp"):
        replay_capture(path, expected_sha256=digest, expected_node_id=NodeId.A, config=_config())


def test_replay_splits_epoch_and_preserves_qc_boundary(tmp_path: Path) -> None:
    path = tmp_path / "node-a.kimu"
    digest = _write(path, _packet(5, 90_000, epoch=7), _packet(0, 1_000, epoch=8))
    result = replay_capture(path, expected_sha256=digest, expected_node_id=NodeId.A, config=_config())
    assert [epoch.clock_epoch for epoch in result.epochs] == [7, 8]
    assert [epoch.sensor_data.device_time_us for epoch in result.epochs] == [(90_000,), (1_000,)]
    assert [issue.code for issue in result.qc.issues] == [QcIssueCode.EPOCH_CHANGE]
    assert result.qc.timestamp_reordered == 0


def test_replay_keeps_sequence_gap_in_qc_and_sample_order(tmp_path: Path) -> None:
    path = tmp_path / "node-a.kimu"
    digest = _write(path, _packet(0, 10_000), _packet(2, 30_000))
    result = replay_capture(path, expected_sha256=digest, expected_node_id=NodeId.A, config=_config())
    assert result.epochs[0].sensor_data.sample_sequences == (0, 2)
    assert result.epochs[0].sensor_data.device_time_us == (10_000, 30_000)
    assert [(issue.code, issue.missing_count) for issue in result.qc.issues] == [
        (QcIssueCode.MISSING_PACKETS, 1),
        (QcIssueCode.MISSING_SAMPLES, 1),
    ]
