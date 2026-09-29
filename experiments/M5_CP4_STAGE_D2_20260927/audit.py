"""Independent segmented raw/partition/reset audit; no validation runner calls."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import imufusion
import numpy as np

from kineimu_shoulder.io.m1_capture import iter_capture_records
from kineimu_shoulder.io.m1_packet import NodeId, decode_sample_packet

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_HASH = "219a7a2cf07eb962ee3bf4755dc0a49d4ccf48447bb27be1edc08d55f5529ea7"
ANCHORS = [
    ("M1-A", "a", NodeId.A, "9e929d0ac025ea3b7322c3a48668e5f21c83fd7372ba920709c18f124f328db5",
     46943, 187772, 14933068145, 16733174774),
    ("M1-B", "b", NodeId.B, "0ae3f1aa712b915bf5b0f4381cb2391b3619d41bbbc2fe81152f5d32c0e5bc68",
     47856, 191424, 14900951232, 16701005981),
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(actual, expected, message):
    require(np.array_equal(np.asarray(actual), np.asarray(expected)), message)


def check_manifest(root, digest):
    raw = (root / "SHA256SUMS.txt").read_bytes()
    require(sha256(raw).hexdigest() == digest, "external manifest digest")
    expected = {"dual_usb_bench_result.json", "run_config.json", "summary.json"} | {
        f"raw/node-{n}.{s}" for n in "ab" for s in ("events.ndjson", "kimu", "preroll.usb.bin", "usb.bin")}
    checked = {}
    for line in raw.decode().splitlines():
        value, name = line.split("  ")
        require(name in expected and name not in checked, "safe complete external manifest")
        require((root/name).resolve().is_relative_to(root.resolve()), "external path containment")
        require(sha256((root/name).read_bytes()).hexdigest() == value, f"external member {name}")
        checked[name] = value
    require(set(checked) == expected, "eleven required members")
    return dict(disposition="PASSED", manifest_sha256=digest, file_sha256=checked)


def audit(output, *, root, anchors=ANCHORS, manifest_hash=MANIFEST_HASH):
    before = check_manifest(root, manifest_hash)
    inventory = {}
    for line in (output / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ")
        require(name not in inventory and not Path(name).is_absolute() and ".." not in Path(name).parts,
                "safe unique product inventory")
        content = (output/name).read_bytes()
        require(sha256(content).hexdigest() == digest, f"product hash {name}")
        require(content == (json.dumps(json.loads(content), sort_keys=True, indent=2, allow_nan=False)
                            + "\n").encode(), f"canonical bytes {name}")
        inventory[name] = digest
    expected = {"manifest.json", "report.json", "downstream.json"} | {
        f"cases/{a[0]}/result.json" for a in anchors}
    require(set(inventory) == expected, "required canonical products")
    require({p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
            == expected | {"SHA256SUMS.txt"}, "unlisted product")
    manifest = json.loads((output/"manifest.json").read_bytes())
    report = json.loads((output/"report.json").read_bytes())
    require(manifest["stage"] == "D-recorded-dual-USB" and manifest["formal"] is False,
            "development D manifest")
    require(manifest["case_ids"] == [a[0] for a in anchors]
            and manifest["external_manifest_sha256"] == manifest_hash, "input manifest binding")
    require(len(manifest["git_commit"]) == 40 and isinstance(manifest["tracked_dirty"], bool), "launch identity")
    sources = manifest["source_file_sha256"]
    required = {p.relative_to(ROOT).as_posix() for p in (ROOT/"kineimu_shoulder").rglob("*.py")}
    required |= {"uv.lock", "pyproject.toml", "protocols/M5_VALIDATION_CONTRACT.md",
                 "protocols/M5_PROCESSING_V1_1.md", "tests/integration/test_m5_recorded_dual.py",
                 "tests/integration/test_m2_replay_m1_bench.py", "experiments/M5_CP4_STAGE_D_20260927/audit.py"}
    require(required <= set(sources), "source provenance completeness")
    for name, digest in sources.items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "safe source path")
        require(sha256((ROOT/name).read_bytes()).hexdigest() == digest, f"source {name}")
    require(manifest.get("segmented") is True
            and manifest["processing_version"] == "m5-recorded-segments/1.0", "explicit segmented launch")
    require({"protocols/M5_RECORDED_SEGMENTS_V1.md", "protocols/M2_PROCESSING_CONTRACT.md",
             "docs/adr/ADR-011-recorded-quality-segments.md", "tests/integration/test_m5_recorded_segments.py",
             "experiments/M5_CP4_STAGE_D2_20260927/audit.py"} <= set(sources), "segmented source completeness")
    total_samples, total_packets = 0, 0
    total_valid, total_rejected, total_segments = 0, 0, 0
    probe_segments = []
    original_a = None
    for case, short, node, digest, count, n, first, last in anchors:
        raw = (root/f"raw/node-{short}.kimu").read_bytes()
        require(sha256(raw).hexdigest() == digest, "original source digest")
        records = list(iter_capture_records(BytesIO(raw)))
        packets = [decode_sample_packet(r.payload) for r in records]
        samples = [s for p in packets for s in p.samples]
        times = np.asarray([s.device_time_us for s in samples], dtype=np.int64)
        require(len(packets) == count and len(samples) == n, "complete original count")
        require((int(times[0]), int(times[-1])) == (first, last), "independent original endpoints")
        require(all(p.node_id == node and p.clock_epoch == 0 for p in packets), "node/epoch identity")
        result = json.loads((output/f"cases/{case}/result.json").read_bytes())
        require(result["passed"] is True and result["stage_disposition"] == "PASSED"
                and not result["failed_gates"] and result["failed_stage"] is None, "complete node execution")
        require(result["source_sha256_before"] == result["source_sha256_after"]
                == result["expected_source_sha256"] == digest, "node immutable hash")
        require(result["node_id"] == node.name and result["source_type"] == "recorded", "node/source label")
        require(result["qc"]["packets_decoded"] == count and result["qc"]["samples_decoded"] == n
                and not result["qc"]["issues"] and len(result["epochs"]) == 1, "complete QC")
        e = result["epochs"][0]
        for field, expected_rows in (
            ("device_time_us", times), ("sample_sequences", [s.sequence for s in samples]),
            ("packet_sequences", [p.packet_sequence for p in packets]),
            ("sample_flags", [int(s.flags) for s in samples]), ("packet_flags", [int(p.flags) for p in packets]),
            ("host_monotonic_ns", [r.host_monotonic_ns for r in records]),
        ):
            same(e[field], expected_rows, field)
        acc = np.asarray([s.accel_raw for s in samples]) * (0.122e-3*9.80665)
        rate = np.deg2rad(np.asarray([s.gyro_raw for s in samples]) * 17.5e-3)
        for field, reference in (("sensor_acceleration_mps2", acc), ("sensor_angular_rate_rads", rate)):
            require(np.allclose(e[field], reference, rtol=0, atol=1e-14), f"complete SI {field}")
        cal = result["calibration"]
        require(cal["fit_method"] == "illustrative_identity_no_fit" and cal["fit_window_us"] == [0, 1],
                "example calibration contract")
        same(cal["accel_matrix"], np.eye(3), "identity calibration")
        same(cal["accel_bias_mps2"], [0, 0, 0], "zero accel bias assumption")
        same(cal["gyro_bias_rads"], [0, 0, 0], "zero gyro bias assumption")
        require(result["calibration_sha256"] == sha256(json.dumps(
            cal, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
                "calibration hash")
        require(result["evidence_label"] == "Assumed/Experimental" and result["anatomical_eligible"] is False
                and result["motion_accuracy"] == dict(value=None, valid=False, reason="no_motion_ground_truth")
                and result["reconstruction"] == "NOT APPLIED; original observations only", "honest assumptions")
        conf = cal["config"]
        require(conf["accel_range_g"] == 4 and conf["gyro_range_dps"] == 500
                and conf["accel_sensitivity_mg_per_lsb"] == .122
                and conf["gyro_sensitivity_mdps_per_lsb"] == 17.5, "pinned calibration ranges/scales")
        same(conf["sensor_to_node"], np.eye(3), "explicit identity R_NS")
        rejected = []
        for i, sample in enumerate(samples):
            reasons = []
            if int(sample.flags) & 1:
                reasons.append("accel_clipped")
            if int(sample.flags) & 2:
                reasons.append("gyro_clipped")
            if np.any(np.abs(acc[i]) > 4*9.80665*1.001):
                reasons.append("accel_range_exceeded")
            if np.any(np.abs(rate[i]) > np.deg2rad(500)*1.001):
                reasons.append("gyro_range_exceeded")
            rejected.append(reasons)
        eligible = [not reasons for reasons in rejected]
        segments, row_segment = [], [None]*n
        i = 0
        reference = [[None]*4 for _ in range(n)]
        while i < n:
            if not eligible[i]:
                i += 1
                continue
            begin = i
            while i < n and eligible[i]:
                i += 1
            stop, index = i, len(segments)
            segments.append(dict(segment_index=index, start_index=begin, stop_index=stop,
                first_device_time_us=int(times[begin]), last_device_time_us=int(times[stop-1]),
                world_id=f"M1-{node.name}-{digest}-processing-world-{index}",
                reset_reason="initial" if begin == 0 else "after_rejected_observation",
                initial_quaternion_wn=[1., 0., 0., 0.], initial_integration_dt_s=None))
            row_segment[begin:stop] = [index]*(stop-begin)
            reference[begin] = [1., 0., 0., 0.]
            ahrs = imufusion.Ahrs()
            ahrs.set_quaternion(reference[begin])
            ahrs.skip_startup()
            for j in range(begin+1, stop):
                dt = int(times[j])-int(times[j-1])
                require(0 < dt <= 50000, "unbridged original interval")
                ahrs.set_sample_period(dt/1e6)
                ahrs.update_no_magnetometer(np.rad2deg(rate[j]), acc[j]/9.80665)
                quaternion = np.asarray(ahrs.get_quaternion(), dtype=np.float64)
                quaternion /= np.linalg.norm(quaternion)
                reference[j] = quaternion.tolist()
        require(segments, "no invented all-bad node")
        p = e["processing"]
        require(result["processing_contract"] == p["contract"] == "m5-recorded-segments/1.0",
                "segmented processing contract")
        require(p["original_sample_count"] == n and p["eligible_sample_count"] == sum(eligible)
                and p["rejected_sample_count"] == n-sum(eligible), "full original denominator conservation")
        require(p["unavailable_reasons"] == rejected and p["segment_index"] == row_segment
                and p["segments"] == segments, "independent partition/reasons/reset/world provenance")
        require(p["interpolation"] == p["reconstruction"] == "NONE"
                and p["cross_segment_orientation_comparable"] is False, "no hidden repair/continuity")
        orientation = e["orientation"]
        same(orientation["timestamp_us"], times, "full original AHRS support")
        require(orientation["heading_observable"] is False and orientation["valid"] == eligible, "node support mask")
        q = np.asarray(orientation["quaternion_wn"], dtype=np.float64)
        require(q.shape == (n, 4), "full quaternion support")
        mask = np.asarray(eligible)
        require(np.isfinite(q[mask]).all()
                and np.allclose(np.linalg.norm(q[mask], axis=1), 1, rtol=0, atol=1e-12), "normalized eligible q_WN")
        require(np.allclose(q[mask], np.asarray(reference, dtype=np.float64)[mask], rtol=0, atol=1e-12),
                "every independent restarted AHRS quaternion")
        require(all(orientation["quaternion_wn"][j] == [None]*4 for j in range(n) if not eligible[j]),
                "rejected quaternion null")
        for field, vectors in (("node_acceleration_mps2", acc), ("node_angular_rate_rads", rate)):
            actual = np.asarray(e[field], dtype=np.float64)
            require(actual.shape == (n, 3) and np.allclose(actual[mask], vectors[mask], rtol=0, atol=1e-14),
                    "eligible calibrated SI")
            require(all(e[field][j] == [None]*3 for j in range(n) if not eligible[j]), "rejected calibrated SI null")
        probe_segments.append(dict(node_id=node.name, **segments[0]))
        total_valid += sum(eligible)
        total_rejected += n-sum(eligible)
        total_segments += len(segments)
        name = f"cases/{case}/result.json"
        require(report["evidence_index"][case] == dict(path=name, sha256=inventory[name]), "node evidence binding")
        if node == NodeId.A:
            original_a = times
        total_packets += count
        total_samples += n
    d = json.loads((output/"downstream.json").read_bytes())
    require(d["observed_node_ids"] == ["A", "B"] and d["common_grid_established"] is False
            and d["stage_disposition"] == "EXECUTED-UNAVAILABLE" and d["value"] is None and d["valid"] is False,
            "dual missing-evidence rejection probe")
    require(d["probe_segments"] == probe_segments
            and d["probe_scope"] == "first eligible contiguous processing world per node; full A rejection support",
            "no cross-world downstream stream join")
    g = d["gates"]
    n = len(original_a)
    same(g["relative"]["common_time_us"], original_a, "requested original A support")
    for stage, value, size, reason in (("relative", "quaternion_th", n, "clock_map_missing"),
                                      ("elevation", "elevation_rad", n, "clock_or_heading_missing"),
                                      ("speed", "relative_angular_speed_rads", n-1, "clock_or_heading_missing")):
        require(g[stage]["valid"] == [False]*size and g[stage]["reason"] == [reason]*size,
                f"every {stage} rejection")
        require(g[stage][value] == ([[None]*4]*size if stage == "relative" else [None]*size),
                f"every {stage} unavailable numeric")
    for stage, names in (("relative", ("thorax_clock_map", "humerus_clock_map", "heading_relation")),
                         ("elevation", ("thorax_alignment", "humerus_alignment"))):
        require(all(g[stage][key] is None for key in names), "no invented evidence")
    for stage in ("segmentation", "summary"):
        require(g[stage]["analysis_valid"] is False and g[stage]["valid_count"] is None
                and g[stage]["reasons"] == ["clock_or_heading_missing"], "M4 reason propagation")
    summary = g["summary"]
    require(summary["proxy_valid_count"] is None and summary["proxy_unavailable_count"] is None,
            "unavailable proxy counts")
    for name in ("rom_range", "rom_sd", "rom_cv", "active_time_s", "active_cadence"):
        require(summary[name]["value"] is None and summary[name]["valid"] is False, "no rescued metric")
    for values in summary["statistics"].values():
        for item in values:
            require(item["n"] == 0 and all(item[k]["value"] is None and item[k]["valid"] is False
                    for k in ("mean", "maximum")), "no rescued statistic")
    require(summary["analysis_window_duration_s"]["value"] == (int(original_a[-1])-int(original_a[0]))/1e6
            and summary["analysis_window_duration_s"]["evidence_label"] == "Observed", "observed support span")
    require(report["stage_passed"] is True and report["passed"] is False and report["case_count"] == 2
            and report["checkpoint_disposition"] == "OPEN" and report["remaining_stages"] == ["E"]
            and report["not_run_count"] == report["blocked_count"] == report["failed_case_count"] == 0,
            "D only, CP4 OPEN")
    after = check_manifest(root, manifest_hash)
    require(before == after == report["manifest_before"] == report["manifest_after"], "complete pre/post manifest")
    for name, digest in sources.items():
        require(sha256((ROOT/name).read_bytes()).hexdigest() == digest, f"source unchanged {name}")
    return dict(passed=True, stage="D", checkpoint_disposition="OPEN", packets_checked=total_packets,
        samples_checked=total_samples, ahrs_quaternions_checked=total_valid, downstream_rows_checked=n,
        rejected_rows_checked=total_rejected, processing_segments_checked=total_segments,
        canonical_products_checked=len(inventory), external_manifest_before=before, external_manifest_after=after,
        output_file_sha256=inventory, source_file_sha256=sources, source_commit=manifest["git_commit"],
        launch_tracked_dirty=manifest["tracked_dirty"],
        limitations=["complete execution audit; no motion/anatomical accuracy", "development only; CP4 OPEN"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "fresh audit output required")
    result = audit(args.run, root=args.root)
    with args.output.open("xb") as stream:
        stream.write((json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+"\n").encode())


if __name__ == "__main__":
    main()
