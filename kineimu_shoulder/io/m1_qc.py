"""Offline sequence quality control for immutable M1 capture streams."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import BinaryIO

from kineimu_shoulder.io.m1_capture import (
    CaptureFormatError,
    OversizedCaptureRecordError,
    TruncatedCaptureRecordError,
    iter_capture_records,
)
from kineimu_shoulder.io.m1_packet import NodeId, ProtocolError, decode_sample_packet


class QcIssueCode(StrEnum):
    """Stable machine-readable issue categories produced by the sequence audit."""

    DECODE_ERROR = "decode_error"
    TRUNCATED_RECORD = "truncated_record"
    OVERSIZED_RECORD = "oversized_record"
    FRAMING_ERROR = "framing_error"
    DUPLICATE_PACKET = "duplicate_packet"
    REORDERED_PACKET = "reordered_packet"
    MISSING_PACKETS = "missing_packets"
    DUPLICATE_SAMPLE = "duplicate_sample"
    REORDERED_SAMPLE = "reordered_sample"
    MISSING_SAMPLES = "missing_samples"
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    REORDERED_TIMESTAMP = "reordered_timestamp"
    EPOCH_CHANGE = "epoch_change"
    NODE_MISMATCH = "node_mismatch"


@dataclass(frozen=True, slots=True)
class QcIssue:
    """One capture or sequence problem, located in the immutable raw stream."""

    code: QcIssueCode
    stream_offset: int
    detail: str
    previous: int | None = None
    current: int | None = None
    missing_count: int = 0


@dataclass(frozen=True, slots=True)
class SequenceQcReport:
    """Aggregate sequence evidence without filtering or repairing raw records."""

    records_seen: int
    packets_decoded: int
    samples_decoded: int
    decode_errors: int
    framing_errors: int
    packet_duplicates: int
    packet_reordered: int
    packets_missing: int
    sample_duplicates: int
    sample_reordered: int
    samples_missing: int
    timestamp_duplicates: int
    timestamp_reordered: int
    epoch_changes: int
    node_mismatches: int
    issues: tuple[QcIssue, ...]


def audit_capture_stream(stream: BinaryIO, *, expected_node_id: NodeId) -> SequenceQcReport:
    """Decode every framed payload and retain explicit errors for malformed values."""

    records_seen = 0
    packets_decoded = 0
    samples_decoded = 0
    decode_errors = 0
    framing_errors = 0
    packet_duplicates = 0
    packet_reordered = 0
    packets_missing = 0
    sample_duplicates = 0
    sample_reordered = 0
    samples_missing = 0
    timestamp_duplicates = 0
    timestamp_reordered = 0
    epoch_changes = 0
    node_mismatches = 0
    last_clock_epoch: int | None = None
    last_packet_sequence: int | None = None
    last_sample_sequence: int | None = None
    last_device_time_us: int | None = None
    seen_packet_sequences: set[int] = set()
    seen_sample_sequences: set[int] = set()
    issues: list[QcIssue] = []

    records = iter_capture_records(stream)
    while True:
        try:
            record = next(records)
        except StopIteration:
            break
        except CaptureFormatError as error:
            framing_errors += 1
            if isinstance(error, TruncatedCaptureRecordError):
                code = QcIssueCode.TRUNCATED_RECORD
            elif isinstance(error, OversizedCaptureRecordError):
                code = QcIssueCode.OVERSIZED_RECORD
            else:
                code = QcIssueCode.FRAMING_ERROR
            issues.append(
                QcIssue(
                    code=code,
                    stream_offset=getattr(error, "stream_offset", stream.tell()),
                    detail=str(error),
                )
            )
            break

        records_seen += 1
        try:
            decoded = decode_sample_packet(record.payload)
        except ProtocolError as error:
            decode_errors += 1
            issues.append(
                QcIssue(
                    code=QcIssueCode.DECODE_ERROR,
                    stream_offset=record.stream_offset,
                    detail=str(error),
                )
            )
            continue

        packets_decoded += 1
        samples_decoded += len(decoded.samples)
        if decoded.node_id is not expected_node_id:
            node_mismatches += 1
            issues.append(
                QcIssue(
                    code=QcIssueCode.NODE_MISMATCH,
                    stream_offset=record.stream_offset,
                    detail=f"decoded node {decoded.node_id.name} does not match expected node {expected_node_id.name}",
                    current=int(decoded.node_id),
                )
            )
            continue

        if last_clock_epoch is None:
            last_clock_epoch = decoded.clock_epoch
        elif decoded.clock_epoch != last_clock_epoch:
            previous_epoch = last_clock_epoch
            epoch_changes += 1
            last_clock_epoch = decoded.clock_epoch
            last_packet_sequence = None
            last_sample_sequence = None
            last_device_time_us = None
            seen_packet_sequences.clear()
            seen_sample_sequences.clear()
            issues.append(
                QcIssue(
                    code=QcIssueCode.EPOCH_CHANGE,
                    stream_offset=record.stream_offset,
                    detail=f"clock epoch changed from {previous_epoch} to {decoded.clock_epoch}",
                    previous=previous_epoch,
                    current=decoded.clock_epoch,
                )
            )

        if last_packet_sequence is None:
            last_packet_sequence = decoded.packet_sequence
        else:
            previous = last_packet_sequence
            distance = (decoded.packet_sequence - previous) & 0xFFFF_FFFF
            if decoded.packet_sequence < previous and 0 < distance < 0x8000_0000:
                seen_packet_sequences.clear()
            if decoded.packet_sequence in seen_packet_sequences:
                packet_duplicates += 1
                issues.append(
                    QcIssue(
                        code=QcIssueCode.DUPLICATE_PACKET,
                        stream_offset=record.stream_offset,
                        detail=(
                            f"packet sequence {decoded.packet_sequence} was already observed "
                            "in this epoch and counter cycle"
                        ),
                        previous=previous,
                        current=decoded.packet_sequence,
                    )
                )
            elif 0 < distance < 0x8000_0000:
                last_packet_sequence = decoded.packet_sequence
                if distance > 1:
                    missing = distance - 1
                    packets_missing += missing
                    issues.append(
                        QcIssue(
                            code=QcIssueCode.MISSING_PACKETS,
                            stream_offset=record.stream_offset,
                            detail=f"{missing} packet sequence value(s) missing before {decoded.packet_sequence}",
                            previous=previous,
                            current=decoded.packet_sequence,
                            missing_count=missing,
                        )
                    )
            else:
                packet_reordered += 1
                issues.append(
                    QcIssue(
                        code=QcIssueCode.REORDERED_PACKET,
                        stream_offset=record.stream_offset,
                        detail=f"packet sequence {decoded.packet_sequence} arrived behind frontier {previous}",
                        previous=previous,
                        current=decoded.packet_sequence,
                    )
                )
        seen_packet_sequences.add(decoded.packet_sequence)

        for sample in decoded.samples:
            if last_sample_sequence is None:
                last_sample_sequence = sample.sequence
            else:
                previous = last_sample_sequence
                distance = (sample.sequence - previous) & 0xFFFF_FFFF
                if sample.sequence < previous and 0 < distance < 0x8000_0000:
                    seen_sample_sequences.clear()
                if sample.sequence in seen_sample_sequences:
                    sample_duplicates += 1
                    issues.append(
                        QcIssue(
                            code=QcIssueCode.DUPLICATE_SAMPLE,
                            stream_offset=record.stream_offset,
                            detail=(
                                f"sample sequence {sample.sequence} was already observed "
                                "in this epoch and counter cycle"
                            ),
                            previous=previous,
                            current=sample.sequence,
                        )
                    )
                elif 0 < distance < 0x8000_0000:
                    last_sample_sequence = sample.sequence
                    if distance > 1:
                        missing = distance - 1
                        samples_missing += missing
                        issues.append(
                            QcIssue(
                                code=QcIssueCode.MISSING_SAMPLES,
                                stream_offset=record.stream_offset,
                                detail=f"{missing} sample sequence value(s) missing before {sample.sequence}",
                                previous=previous,
                                current=sample.sequence,
                                missing_count=missing,
                            )
                        )
                else:
                    sample_reordered += 1
                    issues.append(
                        QcIssue(
                            code=QcIssueCode.REORDERED_SAMPLE,
                            stream_offset=record.stream_offset,
                            detail=f"sample sequence {sample.sequence} arrived behind frontier {previous}",
                            previous=previous,
                            current=sample.sequence,
                        )
                    )
            seen_sample_sequences.add(sample.sequence)

            if last_device_time_us is None:
                last_device_time_us = sample.device_time_us
            elif sample.device_time_us == last_device_time_us:
                timestamp_duplicates += 1
                issues.append(
                    QcIssue(
                        code=QcIssueCode.DUPLICATE_TIMESTAMP,
                        stream_offset=record.stream_offset,
                        detail=f"device timestamp {sample.device_time_us} duplicates the timestamp frontier",
                        previous=last_device_time_us,
                        current=sample.device_time_us,
                    )
                )
            elif sample.device_time_us > last_device_time_us:
                last_device_time_us = sample.device_time_us
            else:
                timestamp_reordered += 1
                issues.append(
                    QcIssue(
                        code=QcIssueCode.REORDERED_TIMESTAMP,
                        stream_offset=record.stream_offset,
                        detail=f"device timestamp {sample.device_time_us} is behind frontier {last_device_time_us}",
                        previous=last_device_time_us,
                        current=sample.device_time_us,
                    )
                )

    return SequenceQcReport(
        records_seen=records_seen,
        packets_decoded=packets_decoded,
        samples_decoded=samples_decoded,
        decode_errors=decode_errors,
        framing_errors=framing_errors,
        packet_duplicates=packet_duplicates,
        packet_reordered=packet_reordered,
        packets_missing=packets_missing,
        sample_duplicates=sample_duplicates,
        sample_reordered=sample_reordered,
        samples_missing=samples_missing,
        timestamp_duplicates=timestamp_duplicates,
        timestamp_reordered=timestamp_reordered,
        epoch_changes=epoch_changes,
        node_mismatches=node_mismatches,
        issues=tuple(issues),
    )
