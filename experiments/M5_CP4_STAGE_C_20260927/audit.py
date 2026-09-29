"""Independent stage C raw/product audit; does not call the validation runner.

Recompute sensor SI from packet counts and every q_WN directly with pinned
imufusion using observed intervals. This checks execution, not motion accuracy.
"""

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
DIGEST = "1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(actual, expected, message):
    require(np.array_equal(np.asarray(actual), np.asarray(expected)), message)


def audit(output: Path, *, source: Path) -> dict:
    raw = source.read_bytes()
    before = sha256(raw).hexdigest()
    require(before == DIGEST, "original source digest")
    records = list(iter_capture_records(BytesIO(raw)))
    packets = [decode_sample_packet(r.payload) for r in records]
    samples = [s for p in packets for s in p.samples]
    times = np.array([s.device_time_us for s in samples], dtype=np.int64)
    require(len(packets) == 208 and len(samples) == 832, "complete independent source counts")
    require(all(p.node_id == NodeId.B and p.clock_epoch == 0 for p in packets), "node/epoch")
    require((int(times[0]), int(times[-1])) == (257030578, 264845581), "original endpoints")
    inventory = {}
    for line in (output / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ")
        require(name not in inventory, "duplicate inventory entry")
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "unsafe inventory path")
        require(sha256((output / name).read_bytes()).hexdigest() == digest, f"product hash {name}")
        inventory[name] = digest
    expected = {"manifest.json", "report.json", "cases/REC-NODE-B/result.json"}
    require(set(inventory) == expected, "complete required product inventory")
    require({p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
            == expected | {"SHA256SUMS.txt"}, "unlisted product")
    for name in expected:
        content = (output / name).read_bytes()
        data = json.loads(content)
        encoded = (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(content == encoded, f"canonical bytes {name}")
    manifest = json.loads((output / "manifest.json").read_bytes())
    report = json.loads((output / "report.json").read_bytes())
    result = json.loads((output / "cases/REC-NODE-B/result.json").read_bytes())
    require(manifest["formal"] is False and manifest["stage"] == "C-recorded-node-B", "development manifest")
    require(manifest["case_ids"] == ["REC-NODE-B"], "manifest case completeness")
    require(len(manifest["git_commit"]) == 40 and isinstance(manifest["tracked_dirty"], bool), "launch identity")
    # Check exact declared live source bytes before/after all audit work.
    source_map = manifest["source_file_sha256"]
    required_sources = {p.relative_to(ROOT).as_posix() for p in (ROOT / "kineimu_shoulder").rglob("*.py")}
    required_sources |= {"uv.lock", "pyproject.toml", "protocols/M5_VALIDATION_CONTRACT.md",
                         "protocols/M5_PROCESSING_V1_1.md", "tests/integration/test_m5_recorded_node.py",
                         "experiments/M5_CP4_STAGE_C_20260927/audit.py"}
    require(required_sources <= set(source_map), "incomplete source provenance")
    for name, digest in source_map.items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "unsafe source path")
        require(sha256((ROOT / name).read_bytes()).hexdigest() == digest, f"source bytes {name}")
    require(result["passed"] is True and result["stage_disposition"] == "PASSED"
            and not result["failed_gates"] and result["failed_stage"] is None, "successful execution")
    require(result["source_type"] == "recorded" and result["node_id"] == "B", "source labels")
    require(result["source_sha256_before"] == result["source_sha256_after"]
            == result["expected_source_sha256"] == DIGEST, "immutable source report")
    require(result["qc"]["packets_decoded"] == 208 and result["qc"]["samples_decoded"] == 832
            and result["qc"]["issues"] == [], "complete QC report")
    require(len(result["epochs"]) == 1, "one epoch")
    e = result["epochs"][0]
    require(e["clock_epoch"] == 0, "original epoch")
    same(e["packet_sequences"], [p.packet_sequence for p in packets], "original packet sequence")
    same(e["sample_sequences"], [s.sequence for s in samples], "original sample sequence")
    same(e["packet_flags"], [int(p.flags) for p in packets], "original packet flags")
    same(e["sample_flags"], [int(s.flags) for s in samples], "original sample flags")
    same(e["host_monotonic_ns"], [r.host_monotonic_ns for r in records], "original arrival observation")
    same(e["device_time_us"], times, "original device time")
    acc = np.array([s.accel_raw for s in samples], dtype=float) * (.122e-3 * 9.80665)
    rate = np.deg2rad(np.array([s.gyro_raw for s in samples], dtype=float) * .0175)
    for key, values in (("sensor_acceleration_mps2", acc), ("node_acceleration_mps2", acc),
                        ("sensor_angular_rate_rads", rate), ("node_angular_rate_rads", rate)):
        array = np.asarray(e[key])
        require(array.shape == (832, 3) and np.isfinite(array).all()
                and np.allclose(array, values, rtol=0, atol=1e-14), f"raw count/SI {key}")
    calibration = result["calibration"]
    same(calibration["accel_matrix"], np.eye(3), "identity calibration")
    same(calibration["accel_bias_mps2"], [0, 0, 0], "zero bias assumption")
    same(calibration["gyro_bias_rads"], [0, 0, 0], "zero gyro bias assumption")
    same(calibration["config"]["sensor_to_node"], np.eye(3), "R_NS identity")
    require(calibration["fit_method"] == "illustrative_identity_no_fit"
            and calibration["fit_window_us"] == [0, 1]
            and calibration["source_sha256"] == [DIGEST], "no-fit calibration identity")
    encoded_calibration = json.dumps(calibration, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    require(sha256(encoded_calibration).hexdigest() == result["calibration_sha256"], "calibration hash")
    require(result["evidence_label"] == "Assumed/Experimental" and result["anatomical_eligible"] is False,
            "no evidence upgrade")
    require(result["reconstruction"] == "NOT APPLIED; original observations only", "no hidden reconstruction")
    orientation = e["orientation"]
    same(orientation["timestamp_us"], times, "orientation original support")
    require(orientation["heading_observable"] is False, "unobserved yaw")
    q = np.array(orientation["quaternion_wn"])
    require(q.shape == (832, 4) and np.isfinite(q).all()
            and np.allclose(np.linalg.norm(q, axis=1), 1, rtol=0, atol=1e-12), "unit q_WN support")
    reference = np.empty((832, 4))
    reference[0] = [1, 0, 0, 0]
    ahrs = imufusion.Ahrs()
    ahrs.set_quaternion(reference[0])
    ahrs.skip_startup()
    for index, dt in enumerate(np.diff(times), start=1):
        require(0 < dt <= 50000, "original AHRS interval")
        ahrs.set_sample_period(float(dt) / 1e6)
        ahrs.update_no_magnetometer(np.rad2deg(rate[index]), acc[index] / 9.80665)
        reference[index] = ahrs.get_quaternion()
        reference[index] /= np.linalg.norm(reference[index])
    require(np.allclose(q, reference, rtol=0, atol=1e-12), "complete independent pinned AHRS recomputation")
    d = result["downstream"]
    require(d["probe_kind"] == "single-node self-input rejection probe; no paired/aligned stream"
            and d["observed_node_ids"] == ["B"] and d["common_grid_established"] is False,
            "explicit single node rejection probe")
    require(d["value"] is None and d["valid"] is False
            and d["stage_disposition"] == "EXECUTED-UNAVAILABLE", "unavailable downstream")
    g = d["gates"]
    require(g["relative"]["quaternion_th"] == [[None]*4 for _ in samples]
            and g["relative"]["valid"] == [False]*832
            and g["relative"]["reason"] == ["clock_map_missing"]*832, "actual M2 rejection")
    require(g["elevation"]["elevation_rad"] == [None]*832
            and g["elevation"]["valid"] == [False]*832
            and g["elevation"]["reason"] == ["clock_or_heading_missing"]*832, "actual M3 rejection")
    require(g["speed"]["relative_angular_speed_rads"] == [None]*831
            and g["speed"]["valid"] == [False]*831
            and g["speed"]["reason"] == ["clock_or_heading_missing"]*831, "actual M3 interval rejection")
    for name in ("thorax_clock_map", "humerus_clock_map", "heading_relation"):
        require(g["relative"][name] is None, "no invented M2 evidence")
    for name in ("thorax_alignment", "humerus_alignment"):
        require(g["elevation"][name] is None, "no invented anatomical alignment")
    for stage in ("segmentation", "summary"):
        require(g[stage]["analysis_valid"] is False and g[stage]["valid_count"] is None
                and g[stage]["reasons"] == ["clock_or_heading_missing"], f"M4 propagation {stage}")
    summary = g["summary"]
    require(summary["proxy_valid_count"] is None and summary["proxy_unavailable_count"] is None,
            "no rescued counts")
    for name in ("rom_range", "rom_sd", "rom_cv", "active_time_s", "active_cadence"):
        require(summary[name]["value"] is None and summary[name]["valid"] is False, f"unavailable {name}")
    for values in summary["statistics"].values():
        for item in values:
            require(item["n"] == 0 and all(item[k]["value"] is None and item[k]["valid"] is False
                    for k in ("mean", "maximum")), "unavailable summary metric")
    require(summary["analysis_window_duration_s"]["value"] == (int(times[-1])-int(times[0]))/1e6
            and summary["analysis_window_duration_s"]["evidence_label"] == "Observed", "observed probe duration")
    require(result["motion_accuracy"] == dict(value=None, valid=False, reason="no_motion_ground_truth"),
            "no motion accuracy claim")
    require(report["checkpoint_disposition"] == "OPEN" and report["passed"] is False
            and report["stage_passed"] is True and report["case_count"] == 1
            and report["not_run_count"] == report["blocked_count"] == report["failed_case_count"] == 0
            and report["remaining_stages"] == ["D", "E"], "C only, not CP4 acceptance")
    require(report["results"][0]["sha256"] == report["evidence_index"]["REC-NODE-B"]["sha256"]
            == inventory["cases/REC-NODE-B/result.json"], "report evidence binding")
    after = sha256(source.read_bytes()).hexdigest()
    require(before == after, "source immutable after audit")
    for name, digest in source_map.items():
        require(sha256((ROOT / name).read_bytes()).hexdigest() == digest, f"source unchanged after audit {name}")
    return dict(passed=True, checkpoint="CP4", checkpoint_disposition="OPEN", stage="C",
                source_sha256_before=before, source_sha256_after=after, packets_checked=208, samples_checked=832,
                ahrs_quaternions_checked=832, downstream_rows_checked=832, canonical_products_checked=3,
                output_file_sha256=inventory, source_file_sha256=source_map,
                source_commit=manifest["git_commit"], launch_tracked_dirty=manifest["tracked_dirty"],
                limitations=["independent execution/support audit, not motion accuracy",
                             "development C only; no CP4 acceptance"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("audit output must be absent")
    checked = audit(args.run, source=ROOT / "firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary.kimu")
    with args.output.open("xb") as stream:
        stream.write((json.dumps(checked, sort_keys=True, indent=2, allow_nan=False)+"\n").encode())


if __name__ == "__main__":
    main()
