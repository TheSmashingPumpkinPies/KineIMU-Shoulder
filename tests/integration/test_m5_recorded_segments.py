"""Approved D processing: conserve observations and never bridge rejected rows."""

import importlib
import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from kineimu_shoulder.io.m1_capture import encode_capture_record
from kineimu_shoulder.io.m1_packet import NodeId, PacketFlags, Sample, SampleFlags, SamplePacket, encode_sample_packet
from kineimu_shoulder.validation.recorded_node import identity_calibration, run_node
from kineimu_shoulder.validation.replay import ReplayInput


def api():
    spec = importlib.util.find_spec("kineimu_shoulder.validation.recorded_segments")
    assert spec is not None, "explicit segmented recorded processing missing"
    return importlib.import_module(spec.name)


def arrays():
    times = np.arange(8, dtype=np.int64)*10000 + 100000
    acc = np.tile([0., 0., 9.80665], (8, 1))
    rate = np.tile([0., 0., np.pi/2], (8, 1))
    flags = [SampleFlags.NONE]*8
    return times, acc, rate, flags


def process(times, acc, rate, flags):
    row = ReplayInput("test", Path("unused"), "1"*64, NodeId.B, 8, 8, (100000, 170000))
    return api().process_segments(times, acc, rate, tuple(flags), artifact=identity_calibration(row))


@pytest.mark.parametrize("bad", [[2], [0], [7], [2, 3], [0, 2, 7], list(range(8))])
def test_every_original_row_survives_with_explicit_nulls_and_world_resets(bad):
    times, acc, rate, flags = arrays()
    for i in bad:
        flags[i] = SampleFlags.GYRO_CLIPPED
    originals = (times.copy(), acc.copy(), rate.copy(), tuple(flags))
    result = process(times, acc, rate, flags)
    p, o = result["processing"], result["orientation"]
    # Independent eight-row construction: exclusion membership is literal input.
    assert p["original_sample_count"] == 8
    assert p["eligible_sample_count"] == 8-len(bad) and p["rejected_sample_count"] == len(bad)
    assert o["timestamp_us"] == times.tolist() and o["valid"] == [i not in bad for i in range(8)]
    assert o["heading_observable"] is False
    for i in range(8):
        if i in bad:
            assert o["quaternion_wn"][i] == [None]*4
            assert result["node_acceleration_mps2"][i] == [None]*3
            assert result["node_angular_rate_rads"][i] == [None]*3
            assert p["segment_index"][i] is None
            assert p["unavailable_reasons"][i] == ["gyro_clipped"]
        else:
            assert p["unavailable_reasons"][i] == []
    segments = p["segments"]
    starts = [i for i in range(8) if i not in bad and (i == 0 or i-1 in bad)]
    assert [s["start_index"] for s in segments] == starts
    assert len({s["world_id"] for s in segments}) == len(starts)
    for s in segments:
        start, end = s["start_index"], s["stop_index"]
        assert all(i not in bad for i in range(start, end))
        assert p["segment_index"][start:end] == [s["segment_index"]]*(end-start)
        # Fresh AHRS initializes identity with no invented first integration dt.
        assert o["quaternion_wn"][start] == [1., 0., 0., 0.]
        assert s["reset_reason"] == ("initial" if start == 0 else "after_rejected_observation")
        assert s["initial_quaternion_wn"] == [1., 0., 0., 0.]
    for actual, original in zip((times, acc, rate), originals[:3], strict=True):
        np.testing.assert_array_equal(actual, original)
    assert tuple(flags) == originals[3]


@pytest.mark.parametrize("kind,reason", [("gyro", "gyro_range_exceeded"), ("acc", "accel_range_exceeded"),
                                        ("acc_flag", "accel_clipped"), ("both", "gyro_clipped")])
def test_flag_and_range_checks_are_independent_and_keep_all_applicable_reasons(kind, reason):
    times, acc, rate, flags = arrays()
    if kind in ("gyro", "both"):
        rate[2, 0] = np.deg2rad(509.04)
    if kind == "acc":
        acc[2, 0] = 4.01*9.80665
    if kind == "acc_flag":
        flags[2] = SampleFlags.ACCEL_CLIPPED
    if kind == "both":
        flags[2] = SampleFlags.GYRO_CLIPPED
    result = process(times, acc, rate, flags)
    reasons = result["processing"]["unavailable_reasons"][2]
    assert reason in reasons
    if kind == "both":
        assert reasons == ["gyro_clipped", "gyro_range_exceeded"]
    assert result["processing"]["rejected_sample_count"] == 1


def test_existing_range_tolerance_is_not_widened_or_narrowed():
    times, acc, rate, flags = arrays()
    rate[2, 0] = np.deg2rad(500)*1.001
    rate[3, 0] = np.nextafter(rate[2, 0], np.inf)
    result = process(times, acc, rate, flags)
    assert result["orientation"]["valid"][2] is True
    assert result["orientation"]["valid"][3] is False


@pytest.mark.parametrize("fault", ["gap", "duplicate", "nonfinite", "zero-acc"])
def test_other_orientation_input_errors_are_not_classified_away(fault):
    times, acc, rate, flags = arrays()
    if fault == "gap":
        times[4:] += 50000
    elif fault == "duplicate":
        times[3] = times[2]
    elif fault == "nonfinite":
        rate[2, 0] = np.nan
    else:
        acc[2] = 0
    with pytest.raises(ValueError):
        process(times, acc, rate, flags)


def fixture(root, *, all_bad=False):
    from kineimu_shoulder.validation.recorded_dual import MEMBERS

    (root/"raw").mkdir(parents=True)
    for name in MEMBERS:
        (root/name).write_bytes(b"immutable constructed sidecar")
    rows = []
    for node in (NodeId.A, NodeId.B):
        start = 100000 if node == NodeId.A else 700000
        path = root/f"raw/node-{node.name.lower()}.kimu"
        content = b"".join(encode_capture_record(encode_sample_packet(SamplePacket(
            node, i, 0, PacketFlags.NONE, (Sample(i, start+i*10000,
            SampleFlags.GYRO_CLIPPED if node == NodeId.B and (all_bad or i == 2) else SampleFlags.NONE,
            (0, 0, 8197), (-29088, 0, 0) if node == NodeId.B and i == 2 else (0, 0, 1000)),))),
            host_monotonic_ns=123+i) for i in range(8))
        path.write_bytes(content)
        rows.append(ReplayInput(f"M1-{node.name}", path, sha256(content).hexdigest(), node, 8, 8,
                                (start, start+70000)))
    manifest = "".join(f"{sha256((root/n).read_bytes()).hexdigest()}  {n}\n" for n in sorted(MEMBERS)).encode()
    (root/"SHA256SUMS.txt").write_bytes(manifest)
    return tuple(rows), sha256(manifest).hexdigest()


def test_segmented_opt_in_complete_replay_and_strict_default_still_rejects(tmp_path):
    from kineimu_shoulder.validation.recorded_dual import export_dual

    root = tmp_path/"input"
    rows, digest = fixture(root)
    assert run_node(rows[1])["passed"] is False
    output = tmp_path/"segmented"
    assert export_dual(output, root=root, inputs=rows, manifest_sha256=digest, segmented=True) == 0
    report = json.loads((output/"report.json").read_bytes())
    assert report["stage_passed"] is True and report["checkpoint_disposition"] == "OPEN"
    result = json.loads((output/"cases/M1-B/result.json").read_bytes())
    e = result["epochs"][0]
    assert e["sample_flags"][2] == 2
    assert e["processing"]["rejected_sample_count"] == 1
    assert result["source_sha256_before"] == result["source_sha256_after"] == rows[1].sha256
    d = json.loads((output/"downstream.json").read_bytes())
    assert d["probe_segments"][1]["stop_index"] == 2
    assert d["gates"]["relative"]["quaternion_th"] == [[None]*4]*8
    assert d["gates"]["summary"]["analysis_valid"] is False
    assert export_dual(tmp_path/"strict", root=root, inputs=rows, manifest_sha256=digest) == 1


def test_all_bad_node_cannot_complete_or_invent_downstream_input(tmp_path):
    from kineimu_shoulder.validation.recorded_dual import export_dual

    root = tmp_path/"input"
    rows, digest = fixture(root, all_bad=True)
    output = tmp_path/"output"
    assert export_dual(output, root=root, inputs=rows, manifest_sha256=digest, segmented=True) == 1
    result = json.loads((output/"cases/M1-B/result.json").read_bytes())
    assert result["epochs"][0]["processing"]["eligible_sample_count"] == 0
    assert result["passed"] is False
    assert json.loads((output/"downstream.json").read_bytes())["stage_disposition"] == "NOT RUN"


def auditor():
    path = Path(__file__).resolve().parents[2]/"validation/auditors/recorded_segments.py"
    spec = importlib.util.spec_from_file_location("cp4_stage_d2_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, "audit"), "independent partition/reset audit missing"
    return module


def audit_small(output, root, rows, digest):
    anchors = [(r.case_id, r.node_id.name.lower(), r.node_id, r.sha256, 8, 8,
                *r.expected_endpoints_us) for r in rows]
    return auditor().audit(output, root=root, anchors=anchors, manifest_hash=digest)


def test_independent_audit_recomputes_each_world_without_runner_calls(tmp_path, monkeypatch):
    from kineimu_shoulder.validation.recorded_dual import export_dual

    root = tmp_path/"input"
    rows, digest = fixture(root)
    output = tmp_path/"output"
    assert export_dual(output, root=root, inputs=rows, manifest_sha256=digest, segmented=True) == 0

    def forbidden(*args, **kwargs):
        pytest.fail("auditor used processing implementation")

    monkeypatch.setattr(api(), "process_segments", forbidden)
    checked = audit_small(output, root, rows, digest)
    # Independently constructed 8 A + 8 B, one bad B row, three fresh worlds.
    assert checked["samples_checked"] == 16 and checked["ahrs_quaternions_checked"] == 15
    assert checked["rejected_rows_checked"] == 1 and checked["processing_segments_checked"] == 3
    assert checked["downstream_rows_checked"] == 8 and checked["passed"] is True


@pytest.mark.parametrize("fault", ["flag", "si", "null", "reason", "valid", "segment", "reset",
                                  "world", "quaternion", "probe", "support", "summary"])
def test_segmented_audit_rejects_rehashed_semantic_corruption(tmp_path, fault):
    from kineimu_shoulder.validation.baseline import canonical
    from kineimu_shoulder.validation.recorded_dual import export_dual

    root = tmp_path/"input"
    rows, digest = fixture(root)
    output = tmp_path/"output"
    assert export_dual(output, root=root, inputs=rows, manifest_sha256=digest, segmented=True) == 0
    target = output/("downstream.json" if fault in ("probe", "support", "summary") else "cases/M1-B/result.json")
    data = json.loads(target.read_bytes())
    if fault in ("probe", "support", "summary"):
        if fault == "probe":
            data["probe_segments"][1]["stop_index"] = 8
        elif fault == "support":
            data["gates"]["relative"]["common_time_us"][2] += 1
        else:
            data["gates"]["summary"]["valid_count"] = 0
    else:
        e = data["epochs"][0]
        if fault == "flag":
            e["sample_flags"][2] = 0
        elif fault == "si":
            e["sensor_angular_rate_rads"][2][0] = 0
        elif fault == "null":
            e["node_angular_rate_rads"][2] = [0, 0, 0]
        elif fault == "reason":
            e["processing"]["unavailable_reasons"][2] = ["gyro_clipped"]
        elif fault == "valid":
            e["orientation"]["valid"][2] = True
        elif fault == "segment":
            e["processing"]["segment_index"][2] = 0
        elif fault == "reset":
            e["processing"]["segments"][1]["reset_reason"] = "initial"
        elif fault == "world":
            e["processing"]["segments"][1]["world_id"] = e["processing"]["segments"][0]["world_id"]
        else:
            e["orientation"]["quaternion_wn"][3] = e["orientation"]["quaternion_wn"][1]
    target.write_bytes(canonical(data))
    report_path = output/"report.json"
    report = json.loads(report_path.read_bytes())
    report["evidence_index"]["M1-B"]["sha256"] = sha256((output/"cases/M1-B/result.json").read_bytes()).hexdigest()
    report["downstream_evidence"]["sha256"] = sha256((output/"downstream.json").read_bytes()).hexdigest()
    report_path.write_bytes(canonical(report))
    names = [line.split("  ")[1] for line in (output/"SHA256SUMS.txt").read_text().splitlines()]
    (output/"SHA256SUMS.txt").write_text("".join(
        f"{sha256((output/n).read_bytes()).hexdigest()}  {n}\n" for n in names), encoding="utf-8")
    with pytest.raises(ValueError):
        audit_small(output, root, rows, digest)
