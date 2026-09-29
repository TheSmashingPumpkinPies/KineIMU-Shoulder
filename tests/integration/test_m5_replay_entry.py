"""CP4 stage A: entry failures cannot become replay acceptance (frozen contract)."""

import importlib
import json
import subprocess
import sys
from dataclasses import replace
from hashlib import sha256

import numpy as np
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
from kineimu_shoulder.relative_orientation import SegmentOrientationStream
from kineimu_shoulder.validation.baseline import run_case


def api():
    spec = importlib.util.find_spec("kineimu_shoulder.validation.replay")
    assert spec is not None, "CP4 validation entry/report runner is missing"
    return importlib.import_module(spec.name)


@pytest.fixture
def capture(tmp_path):
    raw = tmp_path / "inputs" / "raw"
    raw.mkdir(parents=True)
    path = raw / "node-b.kimu"
    # Independent two-sample fixture, M1 framing; original times/counters are literal.
    samples = tuple(Sample(i, 10000 + i * 10000, SampleFlags.NONE,
                           (0, 0, 8197), (0, 0, 0)) for i in range(2))
    packet = SamplePacket(NodeId.B, 0, 0, PacketFlags.NONE, samples)
    path.write_bytes(encode_capture_record(encode_sample_packet(packet), host_monotonic_ns=999))
    return path, sha256(path.read_bytes()).hexdigest()


def spec(capture, **changes):
    path, digest = capture
    return api().ReplayInput("test-B", path, digest, NodeId.B,
                             expected_packets=1, expected_samples=2,
                             expected_endpoints_us=(10000, 20000), source_type="synthetic", **changes)


def test_entry_report_is_complete_but_cannot_pass_unexecuted_replay(capture, tmp_path):
    module = api()
    output = tmp_path / "run"
    before = capture[0].read_bytes()
    assert module.export_entry(output, (spec(capture),)) == 2
    report = json.loads((output / "report.json").read_bytes())
    entry = json.loads((output / "cases/test-B/entry.json").read_bytes())
    # Contract: actual full-chain execution is mandatory; entry/QC alone is NOT RUN.
    assert report["checkpoint_disposition"] == "OPEN"
    assert report["passed"] is False
    assert report["not_run_count"] == 1
    assert report["results"][0]["stage_disposition"] == "NOT RUN"
    assert entry["entry_disposition"] == "PASSED"
    assert entry["source_type"] == "synthetic"
    assert entry["source_sha256_before"] == entry["source_sha256_after"] == capture[1]
    assert entry["qc"]["samples_decoded"] == 2
    assert entry["epochs"][0]["device_time_us"] == [10000, 20000]
    assert entry["epochs"][0]["sample_sequences"] == [0, 1]
    assert entry["downstream"]["valid"] is False
    assert entry["downstream"]["value"] is None
    assert capture[0].read_bytes() == before
    # Hash inventory binds every canonical artifact, excluding itself.
    listed = {}
    for line in (output / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ")
        listed[name] = digest
        assert sha256((output / name).read_bytes()).hexdigest() == digest
    assert set(listed) == {"manifest.json", "report.json", "cases/test-B/entry.json"}
    assert report["evidence_index"]["test-B"]["sha256"] == listed["cases/test-B/entry.json"]
    assert report["requirement_index"]["immutable-input/QC"] == ["test-B"]
    assert report["requirement_index"]["complete-replay"] == ["test-B"]
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert len(manifest["git_commit"]) == 40
    assert isinstance(manifest["tracked_dirty"], bool)
    assert "uv.lock" in manifest["source_file_sha256"]
    assert manifest["formal"] is False
    assert manifest["schema_version"] == "m5-report/1.0"
    for name in listed:
        content = (output / name).read_bytes()
        assert b"\r" not in content and content.endswith(b"\n")
        assert str(output).encode() not in content


@pytest.mark.parametrize("missing", ["file", "permission"])
def test_missing_required_input_is_blocked_without_skip(capture, tmp_path, monkeypatch, missing):
    module = api()
    selected = spec(capture)
    if missing == "file":
        selected = replace(selected, path=capture[0].with_name("absent.kimu"))
    else:
        original = type(capture[0]).read_bytes

        def denied(path):
            if path == capture[0]:
                raise PermissionError("controlled unavailable input")
            return original(path)

        monkeypatch.setattr(type(capture[0]), "read_bytes", denied)
    output = tmp_path / "blocked"
    assert module.export_entry(output, (selected,)) == 2
    report = json.loads((output / "report.json").read_bytes())
    assert report["blocked_count"] == 1 and report["not_run_count"] == 1
    assert report["results"][0]["stage_disposition"] == "BLOCKED"
    assert report["passed"] is False


@pytest.mark.parametrize("fault", ["hash", "node", "count", "endpoint"])
def test_bad_input_fails_with_partial_evidence(capture, tmp_path, fault):
    selected = spec(capture)
    changes = {"hash": {"sha256": "0" * 64}, "node": {"node_id": NodeId.A},
               "count": {"expected_samples": 3}, "endpoint": {"expected_endpoints_us": (0, 20000)}}
    output = tmp_path / fault
    assert api().export_entry(output, (replace(selected, **changes[fault]),)) == 1
    report = json.loads((output / "report.json").read_bytes())
    assert report["failed_case_count"] == 1 and report["passed"] is False
    assert report["results"][0]["stage_disposition"] == "FAILED"
    assert (output / "SHA256SUMS.txt").exists()
    assert sha256(capture[0].read_bytes()).hexdigest() == capture[1]


def test_post_read_mutation_fails_even_if_decoder_succeeded(capture, tmp_path, monkeypatch):
    module = api()
    original = module.replay_capture

    def mutate(path, **kwargs):
        result = original(path, **kwargs)
        path.write_bytes(path.read_bytes() + b"changed test copy")
        return result

    monkeypatch.setattr(module, "replay_capture", mutate)
    output = tmp_path / "mutated"
    assert module.export_entry(output, (spec(capture),)) == 1
    entry = json.loads((output / "cases/test-B/entry.json").read_bytes())
    assert entry["source_sha256_after"] != entry["source_sha256_before"]
    assert "source_changed" in entry["failed_gates"]


@pytest.mark.parametrize("kind", ["empty", "occupied", "input-tree", "capture-root", "raw-name", "ancestor"])
def test_output_protection_precedes_input_read(capture, tmp_path, monkeypatch, kind):
    module = api()
    roots = {"empty": tmp_path / "existing", "occupied": tmp_path / "occupied",
             "input-tree": capture[0].parent / "processed",
             "capture-root": capture[0].parent.parent / "processed",
             "raw-name": tmp_path / "other" / "RAW" / "run", "ancestor": tmp_path}
    output = roots[kind]
    if kind in ("empty", "occupied"):
        output.mkdir()
    marker = output / "marker"
    if kind == "occupied":
        marker.write_bytes(b"immutable")
    reads = []
    original = type(capture[0]).read_bytes

    def read(path):
        if path == capture[0]:
            reads.append(path)
        return original(path)

    monkeypatch.setattr(type(capture[0]), "read_bytes", read)
    with pytest.raises((FileExistsError, ValueError)):
        module.export_entry(output, (spec(capture),))
    assert reads == []
    if kind == "occupied":
        assert marker.read_bytes() == b"immutable"
    if kind in ("input-tree", "capture-root", "raw-name"):
        assert not output.exists()


@pytest.mark.parametrize("parent", ["firmware", "datasets", "docs/validation"])
def test_repository_sources_and_old_formal_evidence_are_protected(capture, parent):
    module = api()
    output = module.ROOT / parent / "m54-never-created"
    with pytest.raises(ValueError):
        module.export_entry(output, (spec(capture),))
    assert not output.exists()


def test_entry_canonical_bytes_do_not_depend_on_output_root(capture, tmp_path):
    module = api()
    first, second = tmp_path / "first", tmp_path / "second"
    assert module.export_entry(first, (spec(capture),)) == 2
    assert module.export_entry(second, (spec(capture),)) == 2
    for path in first.rglob("*"):
        if path.is_file():
            assert path.read_bytes() == (second / path.relative_to(first)).read_bytes()


def test_duplicate_case_ids_rejected_before_claim(capture, tmp_path):
    output = tmp_path / "duplicate"
    with pytest.raises(ValueError, match="case"):
        api().export_entry(output, (spec(capture), spec(capture)))
    assert not output.exists()


def test_case_id_cannot_escape_output(capture, tmp_path):
    output = tmp_path / "unsafe"
    with pytest.raises(ValueError, match="case"):
        api().export_entry(output, (replace(spec(capture), case_id="../../escape"),))
    assert not output.exists()


def test_cli_exit_and_report_agree_for_required_input(capture, tmp_path):
    config = tmp_path / "inputs.json"
    config.write_text(json.dumps([dict(case_id="test-B", path=str(capture[0]), sha256=capture[1],
                                     node_id="B", expected_packets=1, expected_samples=2,
                                     expected_endpoints_us=[10000, 20000], source_type="synthetic")]))
    output = tmp_path / "cli"
    process = subprocess.run([sys.executable, "-m", "kineimu_shoulder.validation.replay",
                              "--input-spec", str(config), "--output", str(output)],
                             capture_output=True, text=True)
    assert process.returncode == 2, process.stderr
    assert (output / "report.json").exists()
    assert json.loads((output / "report.json").read_bytes())["checkpoint_disposition"] == "OPEN"


def test_empty_required_set_cannot_create_success_report(tmp_path):
    output = tmp_path / "empty-set"
    with pytest.raises(ValueError, match="case"):
        api().export_entry(output, ())
    assert not output.exists()


@pytest.fixture(scope="module")
def supported(tmp_path_factory):
    # F1 frozen independent truth: 3 complete F90 cycles; uses existing exact pipeline.
    result = run_case("F90", "E", tmp_path_factory.mktemp("gate-fixture"))
    summary = result["_summary"]
    trace = summary.input_result.trace
    elevation = summary.input_result.metrics.segmentation.elevation_result
    relative = elevation.relative_orientation
    streams = []
    for node in ("A", "B"):
        row = result["processed"]["nodes"][node]["aligned_segment_stream"]
        streams.append(SegmentOrientationStream(
            row["node_id"], row["clock_id"], row["epoch"], row["world_id"], row["source_sha256"],
            np.array(row["timestamp_us"], dtype=np.int64), np.array(row["quaternion_wsegment"])))
    return dict(thorax=streams[0], humerus=streams[1], common_time_us=relative.common_time_us,
                thorax_clock_map=relative.thorax_clock_map, humerus_clock_map=relative.humerus_clock_map,
                heading_relation=relative.heading_relation, thorax_alignment=elevation.thorax_alignment,
                humerus_alignment=elevation.humerus_alignment, heading_evidence=trace.heading_evidence,
                drift_evidence=trace.drift_evidence, context=summary.context,
                calibration_sha256=summary.input_result.metrics.segmentation.calibration_sha256,
                source_type="synthetic", side="left", exercise="flexion")


def test_supported_control_reaches_final_report(supported):
    result = api().gate_report(**supported)
    assert result["summary"]["valid_count"] == 3  # Frozen F1 truth, not runner-derived expectation.
    assert result["summary"]["analysis_valid"] is True
    assert result["summary"]["proxy_valid_count"] == 3


@pytest.mark.parametrize(("missing", "stage", "reason"), [
    ("thorax_clock_map", "relative", "clock_map_missing"),
    ("humerus_clock_map", "relative", "clock_map_missing"),
    ("heading_relation", "relative", "heading_missing"),
    ("humerus_alignment", "elevation", "alignment_missing"),
    ("thorax_alignment", "elevation", "alignment_missing"),
    ("drift_evidence", "thorax", "thorax_drift_unbounded"),
    ("heading_evidence", "thorax", "thorax_heading_missing"),
])
def test_isolated_missing_evidence_survives_to_final_report(supported, missing, stage, reason):
    result = api().gate_report(**(supported | {missing: None}))
    # Literal existing M2/M3/M4 reasons mandated by immutable replay contract.
    if stage in ("relative", "elevation"):
        assert set(result[stage]["reason"]) == {reason}
        assert not any(result[stage]["valid"])
        numeric = "quaternion_th" if stage == "relative" else "elevation_rad"
        assert all(value is None or value == [None] * 4 for value in result[stage][numeric])
        assert result["summary"]["analysis_valid"] is False
        assert result["summary"]["valid_count"] is None
        assert result["summary"]["rom_sd"]["value"] is None
        assert result["summary"]["rom_sd"]["valid"] is False
    else:
        assert result["summary"]["proxy_valid_count"] == 0
        assert result["summary"]["proxy_unavailable_count"] == 3
        for rep in result["thorax"]["repetitions"]:
            assert reason in rep["reasons"]
            assert rep["extension"]["valid"] is False
            assert rep["extension"]["magnitude_rad"] is None
    # Strict canonical JSON, including all exact upstream reasons; no NaN rescue.
    encoded = api().canonical(result)
    assert b"NaN" not in encoded and reason.encode() in encoded
