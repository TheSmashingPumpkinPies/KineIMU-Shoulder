"""Two independent processes; exact M1 parser/count/bytes and overwrite protection."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kineimu_shoulder.io.m1_packet import NodeId, decode_sample_packet
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorToNodeTransform
from kineimu_shoulder.io.m1_usb import UsbPacketStreamParser
from kineimu_shoulder.io.m2_replay import replay_capture

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_two_process_canonical_demo_and_immutable_output(tmp_path):
    outputs = [tmp_path / "first", tmp_path / "second"]
    for root in outputs:
        result = subprocess.run(
            [sys.executable, "examples/m5_sensor_source.py", "--output", str(root)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    first = {p.relative_to(outputs[0]).as_posix(): p.read_bytes() for p in outputs[0].rglob("*") if p.is_file()}
    second = {p.relative_to(outputs[1]).as_posix(): p.read_bytes() for p in outputs[1].rglob("*") if p.is_file()}
    assert first == second
    hashes = json.loads(first["SHA256SUMS.json"])
    for name, digest in hashes.items():
        assert hashlib.sha256(first[name]).hexdigest() == digest
    for trajectory in ("F90", "AL90", "AR90", "T-MIX"):
        for node in ("A", "B"):
            stream = first[f"{trajectory}/{node}.bin"]
            parser = UsbPacketStreamParser()
            packets = parser.feed(stream, host_monotonic_ns=0)
            parser.finish()
            assert not parser.issues
            samples = [s for packet in packets for s in decode_sample_packet(packet.payload).samples]
            assert len(samples) == 2151
            assert samples[-1].sequence == 2150
            assert samples[-1].device_time_us == 21500000
            framed = outputs[0] / trajectory / f"{node}.kimu"
            metadata = json.loads(first[f"{trajectory}/metadata.json"])
            matrix = metadata["nodes"][node]["R_NS"]
            config = M1RawCountAdapterConfig(
                4,
                500,
                0.122,
                17.5,
                SensorToNodeTransform(
                    ("sx", "sy", "sz"), ("nx", "ny", "nz"), tuple(tuple(r) for r in matrix), "synthetic CP1 axes"
                ),
            )
            replayed = replay_capture(
                framed,
                expected_sha256=hashes[f"{trajectory}/{node}.kimu"],
                expected_node_id=NodeId[node],
                config=config,
            )
            assert len(replayed.epochs) == 1
            assert replayed.epochs[0].sensor_data.sample_sequences == tuple(range(2151))
            assert not replayed.qc.issues
    repeated = subprocess.run(
        [sys.executable, "examples/m5_sensor_source.py", "--output", str(outputs[0])], cwd=ROOT, capture_output=True
    )
    assert repeated.returncode != 0
    assert first == {p.relative_to(outputs[0]).as_posix(): p.read_bytes() for p in outputs[0].rglob("*") if p.is_file()}
