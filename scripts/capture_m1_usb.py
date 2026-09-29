"""Capture the Node A v1 packet stream from its USB-C CDC port.

The complete USB byte stream is preserved in ``*.usb.bin``. Valid v1 packet
payloads are written to the frozen outer ``*.kimu`` framing, while diagnostic
bytes and malformed packet candidates remain visible in ``*.events.ndjson``.
This is a USB-C staging recorder; it does not implement the M1 BLE control
plane or silently repair/resample data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, Protocol, TextIO

from kineimu_shoulder.io.m1_capture import encode_capture_record
from kineimu_shoulder.io.m1_packet import NodeId, decode_sample_packet
from kineimu_shoulder.io.m1_qc import SequenceQcReport, audit_capture_stream
from kineimu_shoulder.io.m1_usb import UsbPacketStreamParser


class ReadablePort(Protocol):
    def read(self, size: int) -> bytes: ...


def synchronize_running_stream(
    port: ReadablePort, sink: BinaryIO, *, duration_s: float = 1.0,
    read_size: int = 512, now: Callable[[], float] = time.monotonic,
) -> dict[str, int]:
    """Preserve pre-capture USB bytes while draining backlog to a packet boundary."""
    warmup = UsbPacketStreamParser()
    started = now()
    discarded_bytes = 0
    packets_observed = 0
    last_packet_sequence = -1

    def consume(chunk: bytes) -> None:
        nonlocal discarded_bytes, packets_observed, last_packet_sequence
        if not chunk:
            return
        sink.write(chunk)
        discarded_bytes += len(chunk)
        for packet in warmup.feed(chunk, host_monotonic_ns=int(now() * 1e9)):
            packets_observed += 1
            last_packet_sequence = decode_sample_packet(packet.payload).packet_sequence

    while now() - started < duration_s:
        consume(port.read(read_size))

    deadline = now() + 1.0
    while not warmup.at_packet_boundary and now() < deadline:
        consume(port.read(1))
    if not warmup.at_packet_boundary or packets_observed == 0:
        raise RuntimeError("running USB stream did not reach a valid packet boundary")
    sink.flush()
    return {
        "discarded_bytes": discarded_bytes,
        "packets_observed": packets_observed,
        "last_packet_sequence": last_packet_sequence,
        "preroll_issue_count": len(warmup.issues),
        "preroll_noise_bytes": warmup.noise_bytes,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="USB CDC port, for example COM5")
    parser.add_argument(
        "--output-prefix",
        required=True,
        type=Path,
        help="output path prefix; .usb.bin, .kimu and .events.ndjson are added",
    )
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--packets", type=int, help="stop after this many valid packets")
    parser.add_argument("--node-id", type=int, choices=(1, 2), default=1)
    parser.add_argument("--read-size", type=int, default=512)
    parser.add_argument("--read-timeout", type=float, default=0.25)
    parser.add_argument(
        "--finish-complete-packet", action="store_true",
        help="after the timed window, read at most one second to finish a partial packet",
    )
    parser.add_argument(
        "--synchronize-running-stream", action="store_true",
        help="preserve pre-capture backlog separately and begin at a packet boundary",
    )
    return parser


def _write_event(events: TextIO, event_type: str, **fields: object) -> None:
    record = {"event": event_type, **fields}
    events.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    events.flush()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _qc_pass(report: SequenceQcReport) -> bool:
    return (
        report.decode_errors == 0
        and report.framing_errors == 0
        and report.packets_missing == 0
        and report.samples_missing == 0
        and report.packet_duplicates == 0
        and report.sample_duplicates == 0
        and report.packet_reordered == 0
        and report.sample_reordered == 0
        and report.timestamp_duplicates == 0
        and report.timestamp_reordered == 0
        and report.node_mismatches == 0
    )


def capture(args: argparse.Namespace) -> int:
    if args.seconds <= 0.0:
        raise ValueError("--seconds must be positive")
    if args.packets is not None and args.packets <= 0:
        raise ValueError("--packets must be positive")
    if args.read_size <= 0:
        raise ValueError("--read-size must be positive")
    if args.read_timeout <= 0.0:
        raise ValueError("--read-timeout must be positive")

    try:
        import serial  # type: ignore[import-untyped]
    except ModuleNotFoundError as error:
        raise SystemExit(
            "pyserial is required; install the capture extra with "
            "uv sync --all-extras --frozen"
        ) from error

    prefix = args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    usb_path = prefix.with_suffix(".usb.bin")
    kimu_path = prefix.with_suffix(".kimu")
    events_path = prefix.with_suffix(".events.ndjson")
    preroll_path = prefix.with_suffix(".preroll.usb.bin")

    parser = UsbPacketStreamParser()
    issue_count = 0
    packet_count = 0
    sample_count = 0

    with (
        usb_path.open("xb") as usb_stream,
        kimu_path.open("x+b") as kimu_stream,
        events_path.open("x", encoding="utf-8") as events,
        serial.Serial(args.port, baudrate=115200, timeout=args.read_timeout) as port,
    ):
        port.dtr = True
        preroll_summary: dict[str, int] | None = None
        if args.synchronize_running_stream:
            with preroll_path.open("xb") as preroll_stream:
                preroll_summary = synchronize_running_stream(
                    port, preroll_stream, read_size=args.read_size,
                )
            _write_event(
                events, "pre_capture_sync", **preroll_summary,
                preroll_path=str(preroll_path), preroll_sha256=_sha256(preroll_path),
            )
        capture_start_ns = time.monotonic_ns()
        _write_event(
            events,
            "capture_start",
            port=args.port,
            node_id=args.node_id,
            connection_id=args.port,
            host_monotonic_ns=capture_start_ns,
            duration_s=args.seconds,
            output_usb=str(usb_path),
            output_kimu=str(kimu_path),
        )
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline or (
            args.finish_complete_packet
            and not parser.at_packet_boundary
            and time.monotonic() < deadline + 1.0
        ):
            read_size = args.read_size if time.monotonic() < deadline else 1
            chunk = port.read(read_size)
            if not chunk:
                continue

            host_time_ns = time.monotonic_ns()
            usb_stream.write(chunk)
            usb_stream.flush()
            packets = parser.feed(chunk, host_monotonic_ns=host_time_ns)
            for packet in packets:
                decoded = decode_sample_packet(packet.payload)
                kimu_stream.write(
                    encode_capture_record(
                        packet.payload,
                        host_monotonic_ns=packet.host_monotonic_ns,
                    )
                )
                kimu_stream.flush()
                packet_count += 1
                sample_count += len(decoded.samples)
                _write_event(
                    events,
                    "packet",
                    node_id=int(decoded.node_id),
                    raw_stream_offset=packet.stream_offset,
                    host_monotonic_ns=packet.host_monotonic_ns,
                    payload_length=len(packet.payload),
                    packet_sequence=decoded.packet_sequence,
                    clock_epoch=decoded.clock_epoch,
                    packet_flags=int(decoded.flags),
                    sample_sequences=[sample.sequence for sample in decoded.samples],
                    sample_count=len(decoded.samples),
                )
            while issue_count < len(parser.issues):
                issue = parser.issues[issue_count]
                _write_event(
                    events,
                    issue.code.value,
                    raw_stream_offset=issue.stream_offset,
                    detail=issue.detail,
                    raw_bytes_hex=issue.raw_bytes.hex(),
                )
                issue_count += 1
            if args.packets is not None and packet_count >= args.packets:
                break

        parser.finish()
        while issue_count < len(parser.issues):
            issue = parser.issues[issue_count]
            _write_event(
                events,
                issue.code.value,
                raw_stream_offset=issue.stream_offset,
                detail=issue.detail,
                raw_bytes_hex=issue.raw_bytes.hex(),
            )
            issue_count += 1

        kimu_stream.flush()
        kimu_stream.seek(0)
        qc = audit_capture_stream(
            kimu_stream,
            expected_node_id=NodeId(args.node_id),
        )
        _write_event(
            events,
            "qc_summary",
            node_id=args.node_id,
            connection_id=args.port,
            host_monotonic_ns=time.monotonic_ns(),
            records_seen=qc.records_seen,
            packets_decoded=qc.packets_decoded,
            samples_decoded=qc.samples_decoded,
            decode_errors=qc.decode_errors,
            framing_errors=qc.framing_errors,
            packets_missing=qc.packets_missing,
            samples_missing=qc.samples_missing,
            packet_duplicates=qc.packet_duplicates,
            sample_duplicates=qc.sample_duplicates,
            packet_reordered=qc.packet_reordered,
            sample_reordered=qc.sample_reordered,
            timestamp_duplicates=qc.timestamp_duplicates,
            timestamp_reordered=qc.timestamp_reordered,
            epoch_changes=qc.epoch_changes,
            node_mismatches=qc.node_mismatches,
        )
        _write_event(
            events,
            "capture_stop",
            node_id=args.node_id,
            connection_id=args.port,
            host_monotonic_ns=time.monotonic_ns(),
            packet_count=packet_count,
            sample_count=sample_count,
            noise_bytes=parser.noise_bytes,
            issue_count=len(parser.issues),
            qc_pass=_qc_pass(qc),
            stream_complete=len(parser.issues) == 0,
        )

    summary = {
        "usb_path": str(usb_path),
        "kimu_path": str(kimu_path),
        "events_path": str(events_path),
        "usb_sha256": _sha256(usb_path),
        "kimu_sha256": _sha256(kimu_path),
        "events_sha256": _sha256(events_path),
        "packets": packet_count,
        "samples": sample_count,
        "noise_bytes": parser.noise_bytes,
        "issues": len(parser.issues),
        "qc_pass": _qc_pass(qc),
        "stream_complete": len(parser.issues) == 0,
    }
    if args.synchronize_running_stream:
        summary["preroll_path"] = str(preroll_path)
        summary["preroll_sha256"] = _sha256(preroll_path)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if packet_count else 2


def main() -> int:
    return capture(build_argument_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
