"""Unit tests for the explicit M1 raw-count host adapter."""

import numpy as np

from kineimu_shoulder.io.m1_packet import Sample, SampleFlags
from kineimu_shoulder.io.m1_raw import (
    M1RawCountAdapterConfig,
    SensorToNodeTransform,
    convert_raw_samples,
)


def _identity_config() -> M1RawCountAdapterConfig:
    return M1RawCountAdapterConfig(
        accel_range_g=4.0,
        gyro_range_dps=500.0,
        accel_sensitivity_mg_per_lsb=0.122,
        gyro_sensitivity_mdps_per_lsb=17.50,
        axis_transform=SensorToNodeTransform(
            sensor_axes=("sensor_x", "sensor_y", "sensor_z"),
            node_axes=("node_x", "node_y", "node_z"),
            sensor_to_node=(
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
            ),
            description="identity: sensor register XYZ is declared as node XYZ",
        ),
    )


def test_known_signed_counts_convert_to_si_without_axis_change() -> None:
    sample = Sample(
        sequence=7,
        device_time_us=123_456,
        flags=SampleFlags.NONE,
        accel_raw=(1000, -2000, 3),
        gyro_raw=(1000, -2000, 3),
    )

    converted = convert_raw_samples((sample,), config=_identity_config())

    # Source: LSM6DS3TR-C nominal sensitivities recorded in
    # firmware/xiao_nrf52840_sense/node_a_bringup/src/lsm6dsl_raw.c:
    # 0.122 mg/LSB and 17.50 mdps/LSB.  The SI conversion is
    # mg -> g -> m/s^2 using standard gravity 9.80665 m/s^2, and
    # mdps -> dps -> rad/s using pi/180.
    expected_accel = np.array([1000.0, -2000.0, 3.0]) * 0.122e-3 * 9.80665
    expected_gyro = np.array([1000.0, -2000.0, 3.0]) * 17.50e-3 * np.pi / 180.0
    np.testing.assert_allclose(converted.accel_mps2, expected_accel[None, :], rtol=0.0, atol=1e-12)
    np.testing.assert_allclose(converted.gyro_rads, expected_gyro[None, :], rtol=0.0, atol=1e-12)

    assert converted.device_time_us == (123_456,)
    assert converted.axis_transform.description.startswith("identity")


def test_non_identity_sensor_to_node_transform_is_explicitly_applied() -> None:
    config = _identity_config()
    rotated = M1RawCountAdapterConfig(
        accel_range_g=config.accel_range_g,
        gyro_range_dps=config.gyro_range_dps,
        accel_sensitivity_mg_per_lsb=config.accel_sensitivity_mg_per_lsb,
        gyro_sensitivity_mdps_per_lsb=config.gyro_sensitivity_mdps_per_lsb,
        axis_transform=SensorToNodeTransform(
            sensor_axes=("sensor_x", "sensor_y", "sensor_z"),
            node_axes=("node_x", "node_y", "node_z"),
            sensor_to_node=(
                (0.0, -1.0, 0.0),
                (1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
            ),
            description="declared quarter-turn: node = M * sensor",
        ),
    )
    sample = Sample(
        sequence=1,
        device_time_us=10,
        flags=SampleFlags.NONE,
        accel_raw=(100, 0, 0),
        gyro_raw=(100, 0, 0),
    )

    converted = convert_raw_samples((sample,), config=rotated)

    # Source: the literal sensor_to_node matrix above defines
    # [node_x, node_y, node_z] = [-sensor_y, sensor_x, sensor_z].
    scale = 100.0 * 0.122e-3 * 9.80665
    np.testing.assert_allclose(converted.accel_mps2[0], [0.0, scale, 0.0], rtol=0.0, atol=1e-12)
    assert converted.axis_transform.sensor_axes == ("sensor_x", "sensor_y", "sensor_z")
    assert converted.axis_transform.node_axes == ("node_x", "node_y", "node_z")


def test_adapter_preserves_samples_and_device_timestamps_without_resampling() -> None:
    samples = tuple(
        Sample(
            sequence=index,
            device_time_us=timestamp,
            flags=SampleFlags.NONE,
            accel_raw=(index, 0, 0),
            gyro_raw=(0, index, 0),
        )
        for index, timestamp in enumerate((100, 110, 125))
    )

    converted = convert_raw_samples(samples, config=_identity_config())

    # Source: the literal input sequence and timestamps above are the expected
    # one-to-one adapter output; no interpolation or new timestamp grid exists.
    assert converted.sample_sequences == (0, 1, 2)
    assert converted.device_time_us == (100, 110, 125)
    assert converted.accel_mps2.shape == (3, 3)
    assert converted.gyro_rads.shape == (3, 3)
