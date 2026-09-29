"""Stage D: complete streams and all eleven immutable manifest members.

Small constructed packets exercise orchestration; real M1 anchors remain in
test_m2_replay_m1_bench.py and the retained standalone development run.
"""

import importlib
import json
from dataclasses import replace
from hashlib import sha256
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
from kineimu_shoulder.validation.replay import ReplayInput

NAMES = ["dual_usb_bench_result.json", "run_config.json", "summary.json"] + [
    f"raw/node-{node}.{suffix}" for node in "ab"
    for suffix in ("events.ndjson", "kimu", "preroll.usb.bin", "usb.bin")
]


def api():
    spec = importlib.util.find_spec("kineimu_shoulder.validation.recorded_dual")
    assert spec is not None, "complete M1 dual replay runner missing"
    return importlib.import_module(spec.name)


def fixture(root):
    (root / "raw").mkdir(parents=True)
    for name in NAMES:
        (root / name).write_bytes(b"immutable test sidecar")
    rows = []
    for node, name, start in ((NodeId.A, "a", 100000), (NodeId.B, "b", 700000)):
        path = root / f"raw/node-{name}.kimu"
        content = b"".join(encode_capture_record(encode_sample_packet(SamplePacket(
            node_id=node, packet_sequence=i, clock_epoch=0, flags=PacketFlags.NONE,
            samples=(Sample(sequence=i, device_time_us=start+i*10000, flags=SampleFlags.NONE,
                            accel_raw=(0, 0, 8197), gyro_raw=(0, 0, 0)),),
        )), host_monotonic_ns=123+i) for i in range(4))
        path.write_bytes(content)
        rows.append(ReplayInput(f"M1-{node.name}", path, sha256(content).hexdigest(), node, 4, 4,
                                (start, start+30000)))
    manifest = "".join(f"{sha256((root/n).read_bytes()).hexdigest()}  {n}\n" for n in sorted(NAMES)).encode()
    (root / "SHA256SUMS.txt").write_bytes(manifest)
    return tuple(rows), sha256(manifest).hexdigest()


def test_complete_dual_nodes_and_real_missing_evidence_report(tmp_path):
    module = api()
    root = tmp_path / "input"
    rows, digest = fixture(root)
    output = tmp_path / "output"
    assert module.export_dual(output, root=root, inputs=rows, manifest_sha256=digest) == 0
    report = json.loads((output / "report.json").read_bytes())
    assert report["stage_passed"] is True and report["checkpoint_disposition"] == "OPEN"
    assert report["remaining_stages"] == ["E"] and report["passed"] is False
    assert report["manifest_before"] == report["manifest_after"]
    assert len(report["manifest_before"]["file_sha256"]) == 11
    for row in rows:
        result = json.loads((output / f"cases/{row.case_id}/result.json").read_bytes())
        # Hand-constructed static input: four original samples on distinct clocks.
        assert result["passed"] is True and result["qc"]["samples_decoded"] == 4
        assert result["epochs"][0]["device_time_us"] == list(range(*(
            (100000, 140000, 10000) if row.node_id == NodeId.A else (700000, 740000, 10000))))
        assert result["epochs"][0]["orientation"]["quaternion_wn"] == [[1., 0., 0., 0.]]*4
        assert result["anatomical_eligible"] is False
    downstream = json.loads((output / "downstream.json").read_bytes())
    assert downstream["observed_node_ids"] == ["A", "B"]
    assert downstream["common_grid_established"] is False
    gates = downstream["gates"]
    assert gates["relative"]["reason"] == ["clock_map_missing"]*4
    assert gates["relative"]["quaternion_th"] == [[None]*4]*4
    assert gates["elevation"]["elevation_rad"] == [None]*4
    assert gates["speed"]["relative_angular_speed_rads"] == [None]*3
    assert gates["summary"]["analysis_valid"] is False
    assert gates["summary"]["valid_count"] is None
    assert gates["summary"]["reasons"] == ["clock_or_heading_missing"]
    assert gates["summary"]["rom_range"]["value"] is None
    with pytest.raises(FileExistsError):
        module.export_dual(output, root=root, inputs=rows, manifest_sha256=digest)
    with pytest.raises(ValueError):
        module.export_dual(root / "processed", root=root, inputs=rows, manifest_sha256=digest)


@pytest.mark.parametrize("fault", ["sidecar", "missing", "manifest", "duplicate", "traversal", "short"])
def test_all_manifest_members_gate_before_any_ahrs(tmp_path, monkeypatch, fault):
    module = api()
    root = tmp_path / "input"
    rows, digest = fixture(root)
    manifest = root / "SHA256SUMS.txt"
    if fault == "sidecar":
        (root / "summary.json").write_bytes(b"changed")
    elif fault == "missing":
        (root / "run_config.json").unlink()
    elif fault == "manifest":
        manifest.write_bytes(manifest.read_bytes()+b"\n")
    else:
        lines = manifest.read_text().splitlines()
        if fault == "duplicate":
            lines[-1] = lines[0]
        elif fault == "traversal":
            lines[-1] = "0"*64 + "  ../outside"
        else:
            lines.pop()
        manifest.write_text("\n".join(lines)+"\n", encoding="utf-8")
        digest = sha256(manifest.read_bytes()).hexdigest()
    monkeypatch.setattr(module, "run_node", lambda *a, **k: pytest.fail("AHRS before manifest gate"))
    output = tmp_path / "attempt"
    assert module.export_dual(output, root=root, inputs=rows, manifest_sha256=digest) == (
        2 if fault == "missing" else 1)
    report = json.loads((output / "report.json").read_bytes())
    assert report["stage_passed"] is False and report["not_run_count"] == 2


def test_post_read_sidecar_mutation_cannot_pass(tmp_path, monkeypatch):
    module = api()
    root = tmp_path / "input"
    rows, digest = fixture(root)
    original = module.run_node

    def mutate(row):
        result = original(row)
        (root / "summary.json").write_bytes(b"changed during replay")
        return result

    monkeypatch.setattr(module, "run_node", mutate)
    output = tmp_path / "attempt"
    assert module.export_dual(output, root=root, inputs=rows, manifest_sha256=digest) == 1
    report = json.loads((output / "report.json").read_bytes())
    assert report["stage_passed"] is False and report["manifest_after"]["disposition"] == "FAILED"


def test_missing_external_root_is_blocked_and_retains_report(tmp_path):
    module = api()
    output = tmp_path / "attempt"
    assert module.export_dual(output, root=tmp_path / "absent") == 2
    report = json.loads((output / "report.json").read_bytes())
    assert report["blocked_count"] == 2 and report["not_run_count"] == 2


@pytest.mark.parametrize("fault", ["count", "node", "permission", "ahrs", "gate"])
def test_node_or_gate_failure_preserves_partial_and_never_passes(tmp_path, monkeypatch, fault):
    module = api()
    root = tmp_path / "input"
    rows, digest = fixture(root)
    if fault == "count":
        rows = (rows[0], replace(rows[1], expected_samples=5))
    elif fault == "node":
        rows = (rows[1], rows[0])
        with pytest.raises(ValueError):
            module.export_dual(tmp_path / "output", root=root, inputs=rows, manifest_sha256=digest)
        return
    elif fault == "permission":
        original = type(root).read_bytes

        def deny(path):
            if path == root / "summary.json":
                raise PermissionError("unreadable test member")
            return original(path)

        monkeypatch.setattr(type(root), "read_bytes", deny)
    else:
        def fail(*args, **kwargs):
            raise ValueError("controlled failure")

        if fault == "ahrs":
            monkeypatch.setattr(importlib.import_module("kineimu_shoulder.validation.recorded_node"),
                                "estimate_orientation", fail)
        else:
            monkeypatch.setattr(module, "gate_report", fail)
    output = tmp_path / "output"
    assert module.export_dual(output, root=root, inputs=rows, manifest_sha256=digest) == (
        2 if fault == "permission" else 1)
    report = json.loads((output/"report.json").read_bytes())
    assert report["stage_passed"] is False and report["artifact_disposition"] == "partial"


def auditor():
    path = Path(__file__).resolve().parents[2] / "validation/auditors/recorded_dual.py"
    spec = importlib.util.spec_from_file_location("cp4_stage_d_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def small_audit(module, output, root, rows, digest):
    anchors = [(r.case_id, r.node_id.name.lower(), r.node_id, r.sha256, 4, 4,
                r.expected_endpoints_us[0], r.expected_endpoints_us[1]) for r in rows]
    return module.audit(output, root=root, anchors=anchors, manifest_hash=digest)


def test_independent_audit_checks_both_complete_streams(tmp_path):
    module = api()
    root = tmp_path / "input"
    rows, digest = fixture(root)
    output = tmp_path / "output"
    assert module.export_dual(output, root=root, inputs=rows, manifest_sha256=digest) == 0
    checked = small_audit(auditor(), output, root, rows, digest)
    # Literal construction above: 4 A + 4 B samples/packets, no paired time map.
    assert checked["passed"] is True and checked["samples_checked"] == 8
    assert checked["ahrs_quaternions_checked"] == 8 and checked["downstream_rows_checked"] == 4
    assert checked["canonical_products_checked"] == 5


@pytest.mark.parametrize("fault", ["si", "time", "quaternion", "reason", "summary", "source-map", "extra"])
def test_independent_audit_rejects_rehashed_semantic_corruption(tmp_path, fault):
    module = api()
    root = tmp_path / "input"
    rows, digest = fixture(root)
    output = tmp_path / "output"
    assert module.export_dual(output, root=root, inputs=rows, manifest_sha256=digest) == 0
    name = "cases/M1-B/result.json" if fault in ("si", "time", "quaternion") else (
        "manifest.json" if fault == "source-map" else "downstream.json")
    target = output / name
    data = json.loads(target.read_bytes())
    if fault == "si":
        data["epochs"][0]["node_acceleration_mps2"][3][0] += .01
    elif fault == "time":
        data["epochs"][0]["device_time_us"][3] += 1
    elif fault == "quaternion":
        data["epochs"][0]["orientation"]["quaternion_wn"][3] = [0, 1, 0, 0]
    elif fault == "reason":
        data["gates"]["relative"]["reason"][3] = "valid"
    elif fault == "summary":
        data["gates"]["summary"]["rom_range"]["value"] = 0
    elif fault == "source-map":
        data["source_file_sha256"]["uv.lock"] = "0"*64
    else:
        (output / "extra.txt").write_bytes(b"unexpected")
    target.write_bytes(module.canonical(data))
    report_path = output / "report.json"
    report = json.loads(report_path.read_bytes())
    report["evidence_index"]["M1-B"]["sha256"] = sha256((output/"cases/M1-B/result.json").read_bytes()).hexdigest()
    report["downstream_evidence"]["sha256"] = sha256((output/"downstream.json").read_bytes()).hexdigest()
    report_path.write_bytes(module.canonical(report))
    names = [line.split("  ")[1] for line in (output/"SHA256SUMS.txt").read_text().splitlines()]
    (output/"SHA256SUMS.txt").write_text("".join(
        f"{sha256((output/n).read_bytes()).hexdigest()}  {n}\n" for n in names), encoding="utf-8")
    with pytest.raises(ValueError):
        small_audit(auditor(), output, root, rows, digest)
