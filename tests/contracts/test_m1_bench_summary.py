"""Contracts for the M1 uninterrupted dual-device bench profile."""

from __future__ import annotations

import json
from pathlib import Path

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
from validation.acquisition_summary import summarize_stream
from validation.transport_audit import check_plan_parameters
from validation.transport_experiment import build_argument_parser


def _packet(packet_sequence: int, first_sample_sequence: int) -> bytes:
    samples = tuple(
        Sample(
            sequence=first_sample_sequence + offset,
            device_time_us=(first_sample_sequence + offset) * 10_000,
            flags=SampleFlags.NONE,
            accel_raw=(0, 0, 16_000),
            gyro_raw=(0, 0, 0),
        )
        for offset in range(4)
    )
    return encode_sample_packet(
        SamplePacket(
            node_id=NodeId.A,
            packet_sequence=packet_sequence,
            clock_epoch=0,
            flags=PacketFlags.NONE,
            samples=samples,
        )
    )


def test_bench_profile_is_an_explicit_runner_mode() -> None:
    parser = build_argument_parser()

    args = parser.parse_args(
        [
            "--mode",
            "bench",
            "--output-dir",
            "out",
            "--session-id",
            "bench-test",
            "--node-a-address",
            "a",
            "--node-b-address",
            "b",
            "--expected-node-a-device-id",
            "1",
            "--expected-node-b-device-id",
            "2",
            "--predeclared-plan",
            "plan.md",
            "--seconds",
            "1800",
            "--notes",
            "uninterrupted bench",
        ]
    )

    assert args.mode == "bench"


def test_bench_plan_check_rejects_short_or_stimulated_runs() -> None:
    valid = {
        "mode": "bench",
        "seconds": 1800.0,
        "callback_delay_ms": 0.0,
        "disconnect_a_after_s": None,
        "disconnect_b_after_s": None,
        "disconnect_hold_s": 3.0,
    }

    assert check_plan_parameters(valid)["pass"] is True
    assert check_plan_parameters({**valid, "seconds": 1799.0})["mismatches"] == ["seconds"]
    assert check_plan_parameters({**valid, "callback_delay_ms": 1.0})["mismatches"] == [
        "callback_delay_ms"
    ]


def test_stream_summary_reports_hand_derived_rate_counts_and_gaps(tmp_path: Path) -> None:
    raw_path = tmp_path / "node-a.kimu"
    events_path = tmp_path / "node-a.events.ndjson"
    raw_path.write_bytes(
        encode_capture_record(_packet(0, 0), host_monotonic_ns=1_000_000_000)
        + encode_capture_record(_packet(1, 4), host_monotonic_ns=1_040_000_000)
    )
    events_path.write_text(
        "\n".join(
            json.dumps({"event": event})
            for event in ("connect", "disconnect", "reconnect", "notification_error")
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_stream(
        raw_path,
        events_path,
        expected_node_id=NodeId.A,
        scheduled_duration_s=0.08,
        configured_rate_hz=100.0,
        samples_per_packet=4,
    )

    # Hand-derived fixture: 8 samples at 10 ms spacing span 70 ms, so
    # (8 - 1) / 0.07 s = 100 Hz; two packets arrive 40 ms apart.
    assert summary["expected_sample_count"] == 8
    assert summary["expected_packet_count"] == 2
    assert summary["received_sample_count"] == 8
    assert summary["received_packet_count"] == 2
    assert summary["effective_sample_rate_hz"] == pytest.approx(100.0)
    assert summary["maximum_sample_interval_us"] == 10_000
    assert summary["maximum_inter_packet_gap_ns"] == 40_000_000
    assert summary["host_packet_span_s"] == pytest.approx(0.04)
    assert summary["packet_loss_rate"] == pytest.approx(0.0)
    assert summary["timestamp_monotonic"] is True
    assert summary["disconnect_count"] == 1
    assert summary["reconnect_event_count"] == 1
    assert summary["host_error_event_count"] == 1
    assert summary["host_error_event_types"] == {"notification_error": 1}


def test_stream_summary_keeps_corrupt_payload_as_malformed_evidence(tmp_path: Path) -> None:
    raw_path = tmp_path / "node-a.kimu"
    events_path = tmp_path / "node-a.events.ndjson"
    corrupt = bytearray(_packet(0, 0))
    corrupt[-1] ^= 0x01
    raw_path.write_bytes(encode_capture_record(bytes(corrupt), host_monotonic_ns=1))
    events_path.write_text("", encoding="utf-8")

    summary = summarize_stream(
        raw_path,
        events_path,
        expected_node_id=NodeId.A,
        scheduled_duration_s=1.0,
        configured_rate_hz=100.0,
        samples_per_packet=4,
    )

    assert summary["malformed_packet_count"] == 1
    assert summary["received_packet_count"] == 0
    assert summary["recording_integrity_pass"] is False


def test_stream_summary_reports_contiguous_interval_deviation_and_packet_flags(tmp_path: Path) -> None:
    raw_path = tmp_path / "node-a.kimu"
    events_path = tmp_path / "node-a.events.ndjson"
    packet = SamplePacket(
        node_id=NodeId.A,
        packet_sequence=0,
        clock_epoch=0,
        flags=PacketFlags.FIRMWARE_QUEUE_OVERRUN,
        samples=tuple(
            Sample(
                sequence=index,
                device_time_us=timestamp,
                flags=SampleFlags.NONE,
                accel_raw=(0, 0, 0),
                gyro_raw=(0, 0, 0),
            )
            for index, timestamp in enumerate((0, 10_000, 20_000, 31_000))
        ),
    )
    raw_path.write_bytes(encode_capture_record(encode_sample_packet(packet), host_monotonic_ns=1))
    events_path.write_text("", encoding="utf-8")

    summary = summarize_stream(
        raw_path, events_path, expected_node_id=NodeId.A,
        scheduled_duration_s=0.04, configured_rate_hz=100, samples_per_packet=4,
    )
    assert summary["p99_absolute_interval_deviation_us"] == 1_000
    assert summary["maximum_absolute_interval_deviation_us"] == 1_000
    assert summary["maximum_consecutive_missing_samples"] == 0
    assert summary["packet_flag_counts"]["firmware_queue_overrun"] == 1
