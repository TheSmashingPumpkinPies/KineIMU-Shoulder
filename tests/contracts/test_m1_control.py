"""Executable contracts for the M1 BLE control-plane characteristics."""

from dataclasses import replace
from importlib import import_module
from types import ModuleType

import pytest

CONFIG_GOLDEN_HEX = (
    "4b49010201010001000402000000030000000807060504030201"
    "18171615141312110102030405060708090a0b0c0d0e0f1011121314"
    "40420f004096010040960100a00f000020a10700"
    "000102030405060708090a0b0c0d0e0f101112ce5c85b0"
)
CLOCK_REQUEST_GOLDEN_HEX = "4b490103090000001581e97df41022111dd88d59"
CLOCK_RESPONSE_GOLDEN_HEX = (
    "4b490104090000001581e97df41022110807060504030201"
    "03000000b168de3a00000000ce68de3a000000009e964ea6"
)
STATUS_GOLDEN_HEX = (
    "4b49010501020300080706050403020103000000040000006400000018000000"
    "6500000000000000190000000000000000000000010000000200000003000000"
    "040000000500000006000000c92c930f"
)


def control() -> ModuleType:
    """Load the wished-for public module while keeping the first RED a test failure."""

    try:
        return import_module("kineimu_shoulder.io.m1_control")
    except ModuleNotFoundError:
        pytest.fail("M1 BLE control-plane codec is not implemented")


def config_fixture(module: ModuleType) -> object:
    return module.IdentityConfig(
        node_id=module.NodeId.A,
        timestamp_source=module.TimestampSource.MCU_DRDY_ISR,
        firmware_version=(0, 1, 0),
        batch_size=4,
        config_generation=2,
        clock_epoch=3,
        boot_id=0x0102_0304_0506_0708,
        hardware_device_id=0x1112_1314_1516_1718,
        firmware_git_commit=bytes(range(1, 21)),
        timer_frequency_hz=1_000_000,
        accel_odr_millihz=104_000,
        gyro_odr_millihz=104_000,
        accel_range_mg=4_000,
        gyro_range_mdps=500_000,
        sensor_registers=bytes(range(19)),
    )


def test_identity_config_has_a_stable_golden_wire_layout() -> None:
    module = control()
    config = config_fixture(module)

    encoded = module.encode_identity_config(config)

    # Hand-derived from the little-endian field table in M1_ACQUISITION_CONTRACT;
    # CRC-32C is independently anchored by test_m1_packet.py's standard check value.
    assert encoded.hex() == CONFIG_GOLDEN_HEX
    assert module.decode_identity_config(encoded) == config


def test_clock_exchange_preserves_host_and_device_timestamps() -> None:
    module = control()
    request = module.ClockRequest(transaction_id=9, host_send_ns=1_234_567_890_123_456_789)
    response = module.ClockResponse(
        transaction_id=9,
        host_send_ns=1_234_567_890_123_456_789,
        boot_id=0x0102_0304_0506_0708,
        clock_epoch=3,
        device_receive_us=987_654_321,
        device_indication_queued_us=987_654_350,
    )

    encoded_request = module.encode_clock_request(request)
    encoded_response = module.encode_clock_response(response)

    # Literal vectors protect message type, timestamp units, order and widths.
    assert encoded_request.hex() == CLOCK_REQUEST_GOLDEN_HEX
    assert encoded_response.hex() == CLOCK_RESPONSE_GOLDEN_HEX
    assert module.decode_clock_request(encoded_request) == request
    assert module.decode_clock_response(encoded_response) == response


def test_status_exposes_cumulative_loss_and_buffer_evidence() -> None:
    module = control()
    assert "acquisition_buffer_high_water_samples" in module.Status.__dataclass_fields__
    assert "transport_queue_high_water_packets" in module.Status.__dataclass_fields__
    status = module.Status(
        node_id=module.NodeId.A,
        acquisition_state=module.AcquisitionState.STREAMING,
        flags=module.StatusFlags.SENSOR_READY | module.StatusFlags.SAMPLING_ACTIVE,
        boot_id=0x0102_0304_0506_0708,
        clock_epoch=3,
        status_sequence=4,
        last_sample_sequence=100,
        last_packet_sequence=24,
        samples_acquired=101,
        packets_generated=25,
        sensor_fifo_overruns=0,
        firmware_queue_overruns=1,
        transport_backpressure_events=2,
        samples_dropped_before_packetization=3,
        acquisition_buffer_high_water_samples=4,
        transport_queue_high_water_packets=5,
        last_error_code=6,
    )

    encoded = module.encode_status(status)

    assert encoded.hex() == STATUS_GOLDEN_HEX
    assert module.decode_status(encoded) == status


@pytest.mark.parametrize(
    "encoder_and_value",
    [
        lambda module: (module.encode_identity_config, config_fixture(module)),
        lambda module: (
            module.encode_clock_request,
            module.ClockRequest(transaction_id=9, host_send_ns=1_234_567_890_123_456_789),
        ),
        lambda module: (
            module.encode_clock_response,
            module.ClockResponse(
                transaction_id=9,
                host_send_ns=1_234_567_890_123_456_789,
                boot_id=0x0102_0304_0506_0708,
                clock_epoch=3,
                device_receive_us=987_654_321,
                device_indication_queued_us=987_654_350,
            ),
        ),
    ],
)
def test_control_decoders_reject_crc_corruption(encoder_and_value: object) -> None:
    module = control()
    encoder, value = encoder_and_value(module)
    encoded = bytearray(encoder(value))
    encoded[8] ^= 0x01

    with pytest.raises(module.ProtocolError, match="CRC"):
        module.decode_control_message(bytes(encoded))


def test_identity_config_rejects_an_ambiguous_register_snapshot() -> None:
    module = control()
    config = config_fixture(module)
    invalid = module.IdentityConfig(
        **{
            **{field: getattr(config, field) for field in config.__dataclass_fields__},
            "sensor_registers": b"\x00",
        }
    )

    with pytest.raises(module.ProtocolError, match="19 bytes"):
        module.encode_identity_config(invalid)


def test_identity_config_rejects_a_non_semantic_firmware_version() -> None:
    module = control()
    config = replace(config_fixture(module), firmware_version=(0, 1))

    with pytest.raises(module.ProtocolError, match="three unsigned bytes"):
        module.encode_identity_config(config)


def test_identity_config_rejects_an_unknown_node_id() -> None:
    module = control()
    config = replace(config_fixture(module), node_id=99)

    with pytest.raises(module.ProtocolError, match="node id"):
        module.encode_identity_config(config)


@pytest.mark.parametrize("field", ["boot_id", "hardware_device_id"])
def test_identity_config_rejects_a_zero_device_identity(field: str) -> None:
    module = control()
    config = replace(config_fixture(module), **{field: 0})

    with pytest.raises(module.ProtocolError, match=field.replace("_", " ")):
        module.encode_identity_config(config)
