"""Replay a versioned, repository-retained M1 Node B recording."""

from pathlib import Path

import pytest

from kineimu_shoulder.io.m1_packet import NodeId
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorToNodeTransform
from kineimu_shoulder.io.m2_replay import replay_capture

pytestmark = pytest.mark.integration


def test_recorded_node_b_replays_with_pinned_hash_and_original_timing() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary.kimu"
    )
    config = M1RawCountAdapterConfig(
        accel_range_g=4.0,
        gyro_range_dps=500.0,
        accel_sensitivity_mg_per_lsb=0.122,
        gyro_sensitivity_mdps_per_lsb=17.5,
        axis_transform=SensorToNodeTransform(
            sensor_axes=("sensor_x", "sensor_y", "sensor_z"),
            node_axes=("node_x", "node_y", "node_z"),
            sensor_to_node=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            description="declared identity for retained M1 smoke input",
        ),
    )
    digest = "1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201"
    first = replay_capture(path, expected_sha256=digest, expected_node_id=NodeId.B, config=config)
    second = replay_capture(path, expected_sha256=digest, expected_node_id=NodeId.B, config=config)

    # Counts/hash are fixed in tests/fixtures/acquisition/node-config.json.
    assert first.source_sha256 == second.source_sha256 == digest
    assert first.qc == second.qc
    assert first.qc.issues == ()
    assert first.qc.packets_decoded == 208
    assert first.qc.samples_decoded == 832
    assert len(first.epochs) == 1
    assert first.epochs[0].sensor_data.device_time_us == second.epochs[0].sensor_data.device_time_us
    assert all(
        later > earlier
        for earlier, later in zip(
            first.epochs[0].sensor_data.device_time_us,
            first.epochs[0].sensor_data.device_time_us[1:],
            strict=False,
        )
    )
