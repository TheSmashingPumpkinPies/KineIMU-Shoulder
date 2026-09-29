"""Read-only CP2 pair audit; numerical oracle stays in the locked M5 CP3 auditor."""

import argparse
import copy
import importlib.util
import json
import math
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "datasets/samples/m6_synthetic"
TRAJECTORIES = ("F90", "AL90", "AR90", "T-MIX")
spec = importlib.util.spec_from_file_location("cp3_audit", ROOT / "experiments/M5_CP3_20260926/audit.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def index(root):
    expected = {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
                for p in root.rglob("*") if p.is_file() and p != root / "SHA256SUMS.txt"}
    actual = {}
    for line in (root / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ")
        assert name not in actual and name in expected and digest == expected[name]
        actual[name] = digest
    assert actual == expected
    return actual


def audit_run(root, *, require_clean=True):
    root = Path(root).resolve()
    products = index(root)
    expected = {"run.json", "summary.md", "replay/SHA256SUMS.txt", "replay/manifest.json", "replay/report.json"}
    expected |= {f"replay/cases/Q-{t}/{name}" for t in TRAJECTORIES for name in
                 ("result.json", "processed.json.gz", "derived.json.gz", "annotations.json.gz", "errors.json.gz")}
    assert set(products) == expected and len(products) == 25
    assert not list(root.rglob("*.kimu"))
    run = oracle.read(root / "run.json")
    manifest = oracle.read(root / "replay/manifest.json")
    report = oracle.read(root / "replay/report.json")
    assert run["demo_passed"] and run["exit_code"] == 0 and run["disposition"] == "complete"
    assert run["contract_id"] == "m6-demo-contract/1.0" and not run["failed_gates"]
    assert run["processing_version"] == manifest["processing_version"] == "m5-processing/1.1"
    assert run["source"]["head"] == manifest["git_commit"]
    assert run["runtime"] == manifest["runtime"]
    assert [r["id"] for r in run["trajectories"]] == [f"Q-{t}" for t in TRAJECTORIES]
    assert all(r["disposition"] == "complete" and not r["failed_gates"] for r in run["trajectories"])
    if require_clean:
        assert not run["source"]["tracked_dirty"] and not manifest["tracked_dirty"]
    for hashes in (run["source"]["file_sha256"], manifest["source_file_sha256"]):
        assert all(sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
    assert run["product_sha256"] == {name: digest for name, digest in products.items() if name != "run.json"}
    replay_products = index(root / "replay")
    assert len(replay_products) == 22
    assert report["stage_passed"] and not report["passed"] and report["checkpoint_disposition"] == "OPEN"
    assert report["case_count"] == 4 and report["failed_case_count"] == report["blocked_count"] == 0
    assert report["not_run_count"] == 0 and manifest["formal"] is False
    # Independently frozen CP1 map anchor; neither wrapper nor mutable map supplies identity.
    map_bytes = (SAMPLE / "SHA256SUMS.json").read_bytes()
    map_hash = sha256(map_bytes).hexdigest()
    assert map_hash == "2aa180e32003f91e57accf1d53c5b4b914e0c9e9c0ab4cdb22db02a3ab0964f9"
    frozen = json.loads(map_bytes)
    before = run["input_sha256_before"]
    assert len(before) == 25 and before == run["input_sha256_after"]
    assert all(sha256((SAMPLE / name).read_bytes()).hexdigest() == digest for name, digest in before.items())
    assert before == {name: map_hash if name == "SHA256SUMS.json" else frozen[name] for name in before}
    scalars = 0
    cases = []
    summary_text = (root / "summary.md").read_text(encoding="utf-8")
    for trajectory in TRAJECTORIES:
        folder = root / f"replay/cases/Q-{trajectory}"
        result = oracle.read(folder / "result.json")
        processed = oracle.read(folder / "processed.json.gz")
        derived = oracle.read(folder / "derived.json.gz")
        errors = oracle.read(folder / "errors.json.gz")
        annotations = oracle.read(folder / "annotations.json.gz")
        labels = oracle.read(SAMPLE / "annotations.json")[trajectory]
        metadata = oracle.read(SAMPLE / trajectory / "metadata.json")
        assert annotations["nominal"] == labels["nominal_m4"] and annotations["summary"] == labels["summary"]
        assert result["passed"] and result["accuracy_passed"] and not result["failed_gates"]
        assert result["source_type"] == "synthetic" and result["anatomical_eligible"] is False
        assert result["input_audit"] == dict(before=before, after=before)
        assert result["counts"] == dict(truth=3, valid=3, missed=0, false=0)
        assert result["coverage"]["relative"] == result["coverage"]["proxy"] == result["coverage"]["recall"] == 1
        assert errors["elevation"]["n"] == 1651 and errors["interval_speed"]["n"] == 1650
        assert processed["evaluation_window_us"] == [5000000, 21500000]
        assert processed["segmentation_context_window_us"] == [0, 21500000]
        for node in ("A", "B"):
            row = processed["nodes"][node]
            source, replay = row["source"], row["replay"]
            assert row["calibration_executed"] and row["ahrs_executed"]
            assert not replay["qc"]["issues"] and replay["qc"]["packets_decoded"] == 538
            assert replay["qc"]["samples_decoded"] == 2151
            assert replay["sample_sequences"] == source["sequence"] == list(range(2151))
            assert replay["packet_sequences"] == list(range(538))
            assert source["device_time_us"] == list(range(0, 21500001, 10000))
            assert replay["source_sha256"] == replay["source_hash_after"] == before[f"{trajectory}/{node}.kimu"]
            assert not row["reconstruction"]["knots"]
            meta = metadata["nodes"][node]
            transform = oracle.np.array(meta["R_NS"])
            acc = oracle.np.array(source["accel_raw_counts"]) * (0.122e-3 * 9.80665)
            gyro = oracle.np.array(source["gyro_raw_counts"]) * (17.5e-3 * math.pi / 180)
            assert oracle.np.allclose(acc, source["acceleration_mps2"], rtol=0, atol=1e-12)
            assert oracle.np.allclose(gyro, source["angular_rate_rads"], rtol=0, atol=1e-12)
            assert oracle.np.allclose(acc @ transform.T, row["calibrated_acceleration_mps2"], rtol=0, atol=1e-12)
            assert oracle.np.allclose(gyro @ transform.T, row["calibrated_rate_rads"], rtol=0, atol=1e-12)
            assert oracle.np.allclose(row["orientation"]["quaternion_wn"][0], meta["initial_q_WN"], rtol=0, atol=1e-15)
            for qn, qk in zip(row["orientation"]["quaternion_wn"], row["observed_quaternion_wsegment"], strict=True):
                assert oracle.np.allclose(oracle.rotation(qn) @ meta["R_NK"], oracle.rotation(qk), rtol=0, atol=1e-14)
        case = dict(id=f"{trajectory}/CLEAN-Q/SAME/0", trajectory=trajectory, parameters={}, target="SAME",
                    **{"class": "C"})
        scalars += oracle.audit_case(folder, case)
        mean = derived["summary"]["statistics"]["rom_rad"][0]["mean"]["value"]
        assert f"{math.degrees(mean):.6f} deg" in summary_text
        cases.append(dict(trajectory=trajectory, counts=result["counts"], coverage=result["coverage"],
                          error_summary=result["error_summary"], quantization=result["quantization"]))
    return dict(audit_passed=True, source_head=manifest["git_commit"], product_sha256=products,
                independently_recomputed_error_scalars=scalars, cases=cases,
                oracle_source_sha256=sha256((ROOT / "experiments/M5_CP3_20260926/audit.py").read_bytes()).hexdigest())


def audit_pair(first, second, *, require_clean=True):
    a, b = audit_run(first, require_clean=require_clean), audit_run(second, require_clean=require_clean)
    comparable = []
    for audited in (a, b):
        value = copy.deepcopy(audited)
        # run.json includes the explicitly variable process metadata. Its own
        # integrity was checked above; all its other fields are compared below.
        value["product_sha256"].pop("run.json")
        comparable.append(value)
    assert comparable[0] == comparable[1]
    run1 = copy.deepcopy(oracle.read(Path(first) / "run.json"))
    run2 = copy.deepcopy(oracle.read(Path(second) / "run.json"))
    # Complete contract whitelist: every other run field must compare equal.
    for run in (run1, run2):
        for name in ("output_absolute_path", "started_utc", "ended_utc", "duration_s", "pid"):
            run.pop(name)
        command = run["command"]
        assert command.count("--output") == 1
        command[command.index("--output") + 1] = "<output>"
    assert run1 == run2
    assert oracle.read(Path(first) / "run.json")["pid"] != oracle.read(Path(second) / "run.json")["pid"]
    return dict(cp2_passed=True, runs=[a, b], equal_canonical_products=22, equal_inner_indexes=True,
                equal_summary=True, equal_other_top_product_hashes=24, other_run_fields_equal=True,
                permitted_variation=["output_absolute_path", "command:--output value", "started_utc",
                                     "ended_utc", "duration_s", "pid"], linux_execution="NOT RUN")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run1", required=True, type=Path)
    parser.add_argument("--run2", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit_pair(args.run1, args.run2)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(dict(cp2_passed=True, cases_per_run=4, error_scalars_per_run=27160,
                         equal_canonical_products=22, summary_equal=True)))
