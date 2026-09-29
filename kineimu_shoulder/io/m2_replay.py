"""Read-only, provenance-checked M1 capture input for M2 processing."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from kineimu_shoulder.io.m1_capture import iter_capture_records
from kineimu_shoulder.io.m1_packet import NodeId, PacketFlags, Sample, decode_sample_packet
from kineimu_shoulder.io.m1_qc import QcIssueCode, SequenceQcReport, audit_capture_stream
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorImuData, convert_sensor_samples

_REJECT_ISSUES = frozenset(
    {
        QcIssueCode.DECODE_ERROR,
        QcIssueCode.TRUNCATED_RECORD,
        QcIssueCode.OVERSIZED_RECORD,
        QcIssueCode.FRAMING_ERROR,
        QcIssueCode.NODE_MISMATCH,
        QcIssueCode.DUPLICATE_TIMESTAMP,
        QcIssueCode.REORDERED_TIMESTAMP,
    }
)


@dataclass(frozen=True, slots=True)
class ReplayEpoch:
    """One uninterrupted device clock, preserving packet and sample order."""

    clock_epoch: int
    packet_sequences: tuple[int, ...]
    packet_flags: tuple[PacketFlags, ...]
    host_monotonic_ns: tuple[int, ...]
    sensor_data: SensorImuData


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Per-node sensor-frame SI input with source and QC evidence."""

    source_path: Path
    source_sha256: str
    node_id: NodeId
    config: M1RawCountAdapterConfig
    qc: SequenceQcReport
    epochs: tuple[ReplayEpoch, ...]


def replay_capture(
    path: Path,
    *,
    expected_sha256: str,
    expected_node_id: NodeId,
    config: M1RawCountAdapterConfig,
) -> ReplayResult:
    """Verify one immutable framed ``.kimu`` file and expose sensor-frame SI.

    Bad framing, CRC, identity and nonincreasing intra-epoch time fail closed.
    Other M1 sequence issues stay visible in ``qc``; epoch changes split output.
    No timestamps or samples are repaired, resampled or written to the source.
    """

    raw = path.read_bytes()
    actual_sha256 = sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256.lower():
        raise ValueError(f"source SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}")

    qc = audit_capture_stream(BytesIO(raw), expected_node_id=expected_node_id)
    for issue in qc.issues:
        if issue.code in _REJECT_ISSUES:
            raise ValueError(f"replay rejected {issue.code.value} at byte {issue.stream_offset}: {issue.detail}")
    if qc.packets_decoded == 0:
        raise ValueError("replay requires at least one decoded M1 packet")

    epochs: list[ReplayEpoch] = []
    epoch_id: int | None = None
    packet_sequences: list[int] = []
    packet_flags: list[PacketFlags] = []
    host_times: list[int] = []
    samples: list[Sample] = []

    def finish_epoch() -> None:
        if epoch_id is not None:
            epochs.append(
                ReplayEpoch(
                    clock_epoch=epoch_id,
                    packet_sequences=tuple(packet_sequences),
                    packet_flags=tuple(packet_flags),
                    host_monotonic_ns=tuple(host_times),
                    sensor_data=convert_sensor_samples(samples, config=config),
                )
            )

    for record in iter_capture_records(BytesIO(raw)):
        packet = decode_sample_packet(record.payload)
        if epoch_id != packet.clock_epoch:
            finish_epoch()
            epoch_id = packet.clock_epoch
            packet_sequences = []
            packet_flags = []
            host_times = []
            samples = []
        packet_sequences.append(packet.packet_sequence)
        packet_flags.append(packet.flags)
        host_times.append(record.host_monotonic_ns)
        samples.extend(packet.samples)
    finish_epoch()

    return ReplayResult(
        source_path=path,
        source_sha256=actual_sha256,
        node_id=expected_node_id,
        config=config,
        qc=qc,
        epochs=tuple(epochs),
    )
