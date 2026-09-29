"""Optional read-only replay gate for the immutable external M1 USB bench."""

import os
from pathlib import Path

import pytest

from kineimu_shoulder.io.m1_packet import NodeId
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorToNodeTransform
from kineimu_shoulder.io.m2_replay import replay_capture

pytestmark = pytest.mark.integration

_ROOT = os.environ.get("KINEIMU_M1_RAW_ROOT")


@pytest.mark.skipif(_ROOT is None, reason="set KINEIMU_M1_RAW_ROOT to the immutable M1 bench root")
@pytest.mark.parametrize(
    ("node", "name", "digest", "packet_count", "sample_count", "first_us", "last_us"),
    [
        (
            NodeId.A,
            "node-a.kimu",
            "9e929d0ac025ea3b7322c3a48668e5f21c83fd7372ba920709c18f124f328db5",
            46_943,
            187_772,
            14_933_068_145,
            16_733_174_774,
        ),
        (
            NodeId.B,
            "node-b.kimu",
            "0ae3f1aa712b915bf5b0f4381cb2391b3619d41bbbc2fe81152f5d32c0e5bc68",
            47_856,
            191_424,
            14_900_951_232,
            16_701_005_981,
        ),
    ],
)
def test_m1_bench_replay_preserves_hash_identity_time_and_qc(
    node: NodeId,
    name: str,
    digest: str,
    packet_count: int,
    sample_count: int,
    first_us: int,
    last_us: int,
) -> None:
    assert _ROOT is not None
    path = Path(_ROOT) / "raw" / name
    config = M1RawCountAdapterConfig(
        accel_range_g=4.0,
        gyro_range_dps=500.0,
        accel_sensitivity_mg_per_lsb=0.122,
        gyro_sensitivity_mdps_per_lsb=17.5,
        axis_transform=SensorToNodeTransform(
            sensor_axes=("sensor_x", "sensor_y", "sensor_z"),
            node_axes=("node_x", "node_y", "node_z"),
            sensor_to_node=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            description="declared sensor-frame identity for replay gate",
        ),
    )

    result = replay_capture(path, expected_sha256=digest, expected_node_id=node, config=config)

    # Source: immutable M1 SHA256SUMS.txt and independently audited summary.json.
    assert result.source_sha256 == digest
    assert result.node_id is node
    assert result.qc.issues == ()
    assert result.qc.packets_decoded == packet_count
    assert result.qc.samples_decoded == sample_count
    assert len(result.epochs) == 1
    assert result.epochs[0].clock_epoch == 0
    assert result.epochs[0].sensor_data.device_time_us[0] == first_us
    assert result.epochs[0].sensor_data.device_time_us[-1] == last_us
