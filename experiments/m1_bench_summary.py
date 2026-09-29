"""Create a read-only stability summary for an M1 uninterrupted bench run."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO, cast

from kineimu_shoulder.io.m1_capture import CaptureFormatError, iter_capture_records
from kineimu_shoulder.io.m1_packet import NodeId, PacketFlags, ProtocolError, decode_sample_packet
from kineimu_shoulder.io.m1_qc import QcIssueCode, audit_capture_stream

type JSON = dict[str, object]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_events(path: Path) -> list[JSON]:
    events: list[JSON] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object at {path}:{line_number}")
            events.append(cast(JSON, value))
    return events


def _decoded_timing(stream: BinaryIO, expected_node_id: NodeId) -> JSON:
    host_packet_times_ns: list[int] = []
    device_times_by_epoch: dict[int, list[int]] = defaultdict(list)
    device_samples_by_epoch: dict[int, list[tuple[int, int]]] = defaultdict(list)
    packet_flag_counts: Counter[str] = Counter()
    try:
        for record in iter_capture_records(stream):
            try:
                packet = decode_sample_packet(record.payload)
            except ProtocolError:
                continue
            if packet.node_id is not expected_node_id:
                continue
            host_packet_times_ns.append(record.host_monotonic_ns)
            device_times_by_epoch[packet.clock_epoch].extend(
                sample.device_time_us for sample in packet.samples
            )
            device_samples_by_epoch[packet.clock_epoch].extend(
                (sample.sequence, sample.device_time_us) for sample in packet.samples
            )
            for flag in (
                PacketFlags.SENSOR_FIFO_OVERRUN,
                PacketFlags.FIRMWARE_QUEUE_OVERRUN,
                PacketFlags.TRANSPORT_BACKPRESSURE,
                PacketFlags.DISCONTINUITY_BEFORE_FIRST_SAMPLE,
            ):
                if packet.flags & flag:
                    assert flag.name is not None
                    packet_flag_counts[flag.name.lower()] += 1
    except CaptureFormatError:
        pass

    host_gaps_ns = [
        current - previous
        for previous, current in zip(host_packet_times_ns, host_packet_times_ns[1:], strict=False)
    ]
    epoch_summaries: list[JSON] = []
    for epoch, times_us in sorted(device_times_by_epoch.items()):
        intervals_us = [
            current - previous
            for previous, current in zip(times_us, times_us[1:], strict=False)
            if current > previous
        ]
        contiguous_intervals_us = [
            current_time - previous_time
            for (previous_sequence, previous_time), (current_sequence, current_time)
            in zip(device_samples_by_epoch[epoch], device_samples_by_epoch[epoch][1:], strict=False)
            if ((current_sequence - previous_sequence) & 0xFFFF_FFFF) == 1
            and current_time > previous_time
        ]
        median_interval_us = (
            statistics.median(contiguous_intervals_us) if contiguous_intervals_us else None
        )
        deviations_us = sorted(
            abs(interval - median_interval_us) for interval in contiguous_intervals_us
        ) if median_interval_us is not None else []
        p99_deviation_us = (
            deviations_us[math.ceil(0.99 * len(deviations_us)) - 1]
            if deviations_us else None
        )
        duration_s = (times_us[-1] - times_us[0]) / 1_000_000.0 if len(times_us) >= 2 else 0.0
        effective_rate_hz = (len(times_us) - 1) / duration_s if duration_s > 0.0 else None
        epoch_summaries.append(
            {
                "clock_epoch": epoch,
                "sample_count": len(times_us),
                "first_device_time_us": times_us[0] if times_us else None,
                "last_device_time_us": times_us[-1] if times_us else None,
                "device_duration_s": duration_s,
                "effective_sample_rate_hz": effective_rate_hz,
                "maximum_sample_interval_us": max(intervals_us, default=None),
                "median_contiguous_interval_us": median_interval_us,
                "p99_absolute_interval_deviation_us": p99_deviation_us,
                "maximum_absolute_interval_deviation_us": max(deviations_us, default=None),
            }
        )
    only_epoch = epoch_summaries[0] if len(epoch_summaries) == 1 else None
    return {
        "clock_epoch_count": len(epoch_summaries),
        "epochs": epoch_summaries,
        "effective_sample_rate_hz": only_epoch.get("effective_sample_rate_hz")
        if only_epoch is not None
        else None,
        "maximum_sample_interval_us": max(
            (
                cast(int, epoch["maximum_sample_interval_us"])
                for epoch in epoch_summaries
                if epoch["maximum_sample_interval_us"] is not None
            ),
            default=None,
        ),
        "p99_absolute_interval_deviation_us": max(
            (
                cast(float, epoch["p99_absolute_interval_deviation_us"])
                for epoch in epoch_summaries
                if epoch["p99_absolute_interval_deviation_us"] is not None
            ), default=None,
        ),
        "maximum_absolute_interval_deviation_us": max(
            (
                cast(float, epoch["maximum_absolute_interval_deviation_us"])
                for epoch in epoch_summaries
                if epoch["maximum_absolute_interval_deviation_us"] is not None
            ), default=None,
        ),
        "packet_flag_counts": dict(packet_flag_counts),
        "maximum_inter_packet_gap_ns": max(host_gaps_ns, default=None),
        "first_host_packet_time_ns": host_packet_times_ns[0] if host_packet_times_ns else None,
        "last_host_packet_time_ns": host_packet_times_ns[-1] if host_packet_times_ns else None,
        "host_packet_span_s": (
            (host_packet_times_ns[-1] - host_packet_times_ns[0]) / 1_000_000_000.0
            if len(host_packet_times_ns) >= 2
            else None
        ),
    }


def summarize_stream(
    raw_path: Path,
    events_path: Path,
    *,
    expected_node_id: NodeId,
    scheduled_duration_s: float,
    configured_rate_hz: float,
    samples_per_packet: int,
) -> JSON:
    """Summarize immutable raw and event streams without repairing either input."""

    if scheduled_duration_s <= 0.0:
        raise ValueError("scheduled_duration_s must be positive")
    if configured_rate_hz <= 0.0:
        raise ValueError("configured_rate_hz must be positive")
    if samples_per_packet <= 0:
        raise ValueError("samples_per_packet must be positive")

    with raw_path.open("rb") as stream:
        qc = audit_capture_stream(stream, expected_node_id=expected_node_id)
    with raw_path.open("rb") as stream:
        timing = _decoded_timing(stream, expected_node_id)
    events = _read_events(events_path)
    event_counts = Counter(str(event.get("event")) for event in events)
    host_error_event_types = {
        name: count for name, count in event_counts.items() if "error" in name.casefold()
    }

    expected_sample_count = round(scheduled_duration_s * configured_rate_hz)
    expected_packet_count = math.ceil(expected_sample_count / samples_per_packet)
    packet_opportunities = qc.packets_decoded + qc.packets_missing
    packet_loss_rate = (
        qc.packets_missing / packet_opportunities if packet_opportunities > 0 else None
    )
    recording_integrity_pass = (
        qc.decode_errors == 0
        and qc.framing_errors == 0
        and qc.packet_duplicates == 0
        and qc.packet_reordered == 0
        and qc.sample_duplicates == 0
        and qc.sample_reordered == 0
        and qc.timestamp_duplicates == 0
        and qc.timestamp_reordered == 0
        and qc.node_mismatches == 0
        and qc.epoch_changes == 0
    )
    return {
        "node_id": expected_node_id.name,
        "scheduled_duration_s": scheduled_duration_s,
        "configured_rate_hz": configured_rate_hz,
        "samples_per_packet": samples_per_packet,
        "expected_sample_count": expected_sample_count,
        "expected_packet_count": expected_packet_count,
        "received_sample_count": qc.samples_decoded,
        "received_packet_count": qc.packets_decoded,
        "dropped_sample_count": qc.samples_missing,
        "maximum_consecutive_missing_samples": max(
            (issue.missing_count for issue in qc.issues if issue.code is QcIssueCode.MISSING_SAMPLES),
            default=0,
        ),
        "dropped_packet_count": qc.packets_missing,
        "packet_loss_rate": packet_loss_rate,
        "scheduled_sample_completion_ratio": (
            qc.samples_decoded / expected_sample_count if expected_sample_count > 0 else None
        ),
        "malformed_packet_count": qc.decode_errors,
        "framing_error_count": qc.framing_errors,
        "timestamp_duplicate_count": qc.timestamp_duplicates,
        "timestamp_reordered_count": qc.timestamp_reordered,
        "timestamp_monotonic": qc.timestamp_duplicates == 0 and qc.timestamp_reordered == 0,
        "disconnect_count": event_counts["disconnect"],
        "reconnect_event_count": event_counts["reconnect"],
        "host_error_event_count": sum(host_error_event_types.values()),
        "host_error_event_types": host_error_event_types,
        "event_type_counts": dict(event_counts),
        **timing,
        "recording_integrity_pass": recording_integrity_pass,
        "raw_path": str(raw_path),
        "raw_sha256": _sha256(raw_path),
        "events_path": str(events_path),
        "events_sha256": _sha256(events_path),
    }


def summarize_run(
    run_dir: Path,
    *,
    scheduled_duration_s: float,
    configured_rate_hz: float,
    samples_per_packet: int,
) -> JSON:
    """Summarize both required node streams in one completed bench directory."""

    nodes = {
        node_id.name: summarize_stream(
            run_dir / "raw" / f"node-{node_id.name.lower()}.kimu",
            run_dir / "raw" / f"node-{node_id.name.lower()}.events.ndjson",
            expected_node_id=node_id,
            scheduled_duration_s=scheduled_duration_s,
            configured_rate_hz=configured_rate_hz,
            samples_per_packet=samples_per_packet,
        )
        for node_id in (NodeId.A, NodeId.B)
    }
    return {
        "schema": "kineimu.m1.dual-device-bench-summary/0.1",
        "measurement_scope": "uninterrupted physical dual-device acquisition stability",
        "raw_policy": "read-only; no repair, filtering, interpolation, or resampling",
        "nodes": nodes,
        "pairwise_timing": {
            "status": "not_measured_by_this_summary",
            "reason": (
                "Offset, relative drift, and synchronization residuals require the separate "
                "clock-mapping artifact and held-out common events."
            ),
        },
    }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--scheduled-seconds", type=float, default=1800.0)
    parser.add_argument("--configured-rate-hz", type=float, default=104.0)
    parser.add_argument("--samples-per-packet", type=int, default=4)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    output = args.output or args.run_dir / "summary.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing summary: {output}")
    summary = summarize_run(
        args.run_dir,
        scheduled_duration_s=args.scheduled_seconds,
        configured_rate_hz=args.configured_rate_hz,
        samples_per_packet=args.samples_per_packet,
    )
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
