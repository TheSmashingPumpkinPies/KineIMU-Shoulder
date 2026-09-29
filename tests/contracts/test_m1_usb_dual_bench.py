"""Safety gates for the simultaneous two-port USB bench runner."""

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.m1_usb_dual_bench import (
    assess_pair,
    resolve_ports,
    verify_identity_pilot,
)
from kineimu_shoulder.io.m1_packet import (
    NodeId,
    PacketFlags,
    Sample,
    SampleFlags,
    SamplePacket,
    encode_sample_packet,
)


def test_resolve_ports_uses_hardware_serial_not_com_order() -> None:
    ports = [
        SimpleNamespace(device="COM8", serial_number="B-SERIAL", vid=0x2FE3, pid=0x0004),
        SimpleNamespace(device="COM5", serial_number="A-SERIAL", vid=0x2FE3, pid=0x0004),
    ]
    assert resolve_ports(ports, serial_a="A-SERIAL", serial_b="B-SERIAL") == {
        "A": "COM5", "B": "COM8"
    }


def test_resolve_ports_rejects_ambiguous_identity() -> None:
    ports = [
        SimpleNamespace(device="COM5", serial_number="A-SERIAL", vid=0x2FE3, pid=0x0004),
        SimpleNamespace(device="COM6", serial_number="A-SERIAL", vid=0x2FE3, pid=0x0004),
    ]
    with pytest.raises(ValueError, match="exactly one"):
        resolve_ports(ports, serial_a="A-SERIAL", serial_b="B-SERIAL")


def _node_fixture(root: Path, label: str, hardware_id: str, start: int, stop: int) -> dict[str, object]:
    raw = root / f"node-{label}.usb.bin"
    kimu = root / f"node-{label}.kimu"
    events = root / f"node-{label}.events.ndjson"
    raw.write_bytes(f"Node {label.upper()}: hardware_device_id=0x{hardware_id}\n".encode())
    kimu.write_bytes(b"packet")
    events.write_text(
        json.dumps({"event": "capture_start", "host_monotonic_ns": start}) + "\n"
        + json.dumps({"event": "capture_stop", "host_monotonic_ns": stop,
                      "qc_pass": True, "packet_count": 10, "sample_count": 40}) + "\n",
        encoding="utf-8",
    )
    return {
        "usb_path": str(raw), "kimu_path": str(kimu), "events_path": str(events),
        "usb_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        "kimu_sha256": hashlib.sha256(kimu.read_bytes()).hexdigest(),
        "events_sha256": hashlib.sha256(events.read_bytes()).hexdigest(),
        "packets": 10, "samples": 40, "qc_pass": True, "stream_complete": True,
    }


def test_assess_pair_requires_identity_integrity_and_overlap(tmp_path: Path) -> None:
    a = _node_fixture(tmp_path, "a", "0000000000000001", 1_000_000_000, 16_200_000_000)
    b = _node_fixture(tmp_path, "b", "0000000000000002", 1_020_000_000, 16_220_000_000)
    result = assess_pair(
        a, b, expected_a="0000000000000001", expected_b="0000000000000002",
        scheduled_seconds=15.0,
    )
    assert result["ready"] is True
    assert result["overlap_fraction"] >= 0.995
    assert result["overlap_fraction"] <= 1.0

    raw = Path(str(b["usb_path"]))
    raw.write_bytes(b"Node B: hardware_device_id=0x0000000000000000\n")
    rejected = assess_pair(
        a, b, expected_a="0000000000000001", expected_b="0000000000000002",
        scheduled_seconds=15.0,
    )
    assert rejected["ready"] is False
    assert any("hash" in reason for reason in rejected["reasons"])


def test_current_stream_can_use_verified_same_board_pilot(tmp_path: Path) -> None:
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    a = _node_fixture(pilot, "a", "0000000000000001", 1_000_000_000, 16_200_000_000)
    b = _node_fixture(pilot, "b", "0000000000000002", 1_020_000_000, 16_220_000_000)
    provenance = {
        "scheduled_seconds": 15.0,
        "serials": {"A": "A-SERIAL", "B": "B-SERIAL"},
        "ports": {"A": "COM5", "B": "COM8"},
        "hardware_ids": {"A": "0000000000000001", "B": "0000000000000002"},
        "firmware_images": {"A": {"sha256": "a-image"}, "B": {"sha256": "b-image"}},
        "firmware_source_commit": "source",
    }
    (pilot / "run_config.json").write_text(json.dumps(provenance), encoding="utf-8")
    (pilot / "dual_usb_bench_result.json").write_text(
        json.dumps({"provenance": provenance, "assessment": {"ready": True,
                   "node_a": a, "node_b": b}}), encoding="utf-8",
    )
    kwargs = {
        "pilot_dir": pilot,
        "serials": provenance["serials"],
        "ports": provenance["ports"],
        "hardware_ids": provenance["hardware_ids"],
        "image_hashes": {"A": "a-image", "B": "b-image"},
        "source_commit": "source",
    }
    evidence = verify_identity_pilot(**kwargs)
    assert evidence["pilot_result_sha256"] == hashlib.sha256(
        (pilot / "dual_usb_bench_result.json").read_bytes()
    ).hexdigest()

    current = tmp_path / "current"
    current.mkdir()
    current_a = _node_fixture(current, "a", "0000000000000001", 1_000_000_000, 16_200_000_000)
    current_b = _node_fixture(current, "b", "0000000000000002", 1_020_000_000, 16_220_000_000)
    for summary in (current_a, current_b):
        raw = Path(str(summary["usb_path"]))
        raw.write_bytes(b"already-running binary stream")
        summary["usb_sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
        preroll = raw.with_suffix(".preroll.usb.bin")
        preroll.write_bytes(b"old bytes explicitly saved before capture")
        summary["preroll_path"] = str(preroll)
        summary["preroll_sha256"] = hashlib.sha256(preroll.read_bytes()).hexdigest()
    live_only = assess_pair(
        current_a, current_b, expected_a="0000000000000001",
        expected_b="0000000000000002", scheduled_seconds=15.0,
    )
    assert live_only["ready"] is False
    resumed = assess_pair(
        current_a, current_b, expected_a="0000000000000001",
        expected_b="0000000000000002", scheduled_seconds=15.0,
        prior_identity_verified=True,
    )
    assert resumed["ready"] is True

    Path(str(a["usb_path"])).write_bytes(b"tampered pilot")
    with pytest.raises(ValueError, match="pilot"):
        verify_identity_pilot(**kwargs)


def test_running_stream_preroll_preserves_bytes_and_starts_at_boundary() -> None:
    from scripts.capture_m1_usb import synchronize_running_stream

    def packet(sequence: int, sample_sequence: int) -> bytes:
        return encode_sample_packet(SamplePacket(
            node_id=NodeId.A, packet_sequence=sequence, clock_epoch=0,
            flags=PacketFlags.NONE, samples=(Sample(
                sequence=sample_sequence, device_time_us=sample_sequence * 9615,
                flags=SampleFlags.NONE, accel_raw=(1, 2, 3), gyro_raw=(4, 5, 6),
            ),),
        ))

    first = packet(399, 1596)
    live = packet(6900, 27600)
    chunks = [b"partial-old-tail" + first[:15], first[15:] + live[:9], live[9:]]

    class FakePort:
        def read(self, size: int) -> bytes:
            if not chunks:
                return b""
            chunk = chunks.pop(0)
            if size == 1 and len(chunk) > 1:
                chunks.insert(0, chunk[1:])
                return chunk[:1]
            return chunk

    ticks = iter(float(index) / 100.0 for index in range(300))
    sink = io.BytesIO()
    result = synchronize_running_stream(
        FakePort(), sink, duration_s=0.05, read_size=512,
        now=lambda: next(ticks),
    )
    assert sink.getvalue() == b"partial-old-tail" + first + live
    assert result["packets_observed"] == 2
    assert result["last_packet_sequence"] == 6900
    assert result["discarded_bytes"] == len(sink.getvalue())
