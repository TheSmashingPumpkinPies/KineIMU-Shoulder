"""Stage B delivery check, reusing the independently locked CP3 auditor."""
import importlib.util
import json
import math
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cp3_audit", ROOT / "validation/auditors/synthetic.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
run = ROOT / sys.argv[1]
output = ROOT / sys.argv[2]
assert not output.exists()
manifest = audit.read(run / "manifest.json")
report = audit.read(run / "report.json")
assert manifest["formal"] is False and not manifest["tracked_dirty"]
assert manifest["processing_version"] == "m5-processing/1.1"
assert report["stage_passed"] and report["checkpoint_disposition"] == "OPEN"
assert report["case_count"] == 4 and report["failed_case_count"] == report["blocked_count"] == 0
products = {}
for line in (run / "SHA256SUMS.txt").read_text().splitlines():
    digest, name = line.split("  ")
    assert name not in products and sha256((run / name).read_bytes()).hexdigest() == digest
    products[name] = digest
assert set(products) == {p.relative_to(run).as_posix() for p in run.rglob("*")
                         if p.is_file() and p.name != "SHA256SUMS.txt"}
assert len(products) == 22
cp1 = ROOT / "datasets/samples/m6_synthetic"
expected_map = json.loads((cp1 / "SHA256SUMS.json").read_bytes())
assert sha256((cp1 / "SHA256SUMS.json").read_bytes()).hexdigest() == manifest["input_digest_map_sha256"]
scalars = 0
cases = []
for trajectory in ("F90", "AL90", "AR90", "T-MIX"):
    folder = run / f"cases/Q-{trajectory}"
    result = audit.read(folder / "result.json")
    processed = audit.read(folder / "processed.json.gz")
    errors = audit.read(folder / "errors.json.gz")
    annotations = audit.read(folder / "annotations.json.gz")
    frozen_labels = audit.read(cp1 / "annotations.json")[trajectory]
    assert annotations["nominal"] == frozen_labels["nominal_m4"]
    assert annotations["summary"] == frozen_labels["summary"]
    assert result["passed"] and not result["failed_gates"]
    assert result["input_audit"]["before"] == result["input_audit"]["after"]
    for name, digest in result["input_audit"]["before"].items():
        assert sha256((cp1 / name).read_bytes()).hexdigest() == digest
        if name != "SHA256SUMS.json":
            assert digest == expected_map[name]
    assert result["counts"] == dict(truth=3, valid=3, missed=0, false=0)
    assert errors["elevation"]["n"] == 1651 and errors["interval_speed"]["n"] == 1650
    assert processed["evaluation_window_us"] == [5000000, 21500000]
    metadata = audit.read(cp1 / trajectory / "metadata.json")
    for node in ("A", "B"):
        row = processed["nodes"][node]
        source = row["source"]
        replay = row["replay"]
        assert row["calibration_executed"] and row["ahrs_executed"]
        assert replay["qc"]["packets_decoded"] == 538 and replay["qc"]["samples_decoded"] == 2151
        assert replay["sample_sequences"] == source["sequence"] == list(range(2151))
        assert replay["packet_sequences"] == list(range(538))
        assert source["device_time_us"] == list(range(0, 21500001, 10000))
        assert replay["source_sha256"] == replay["source_hash_after"] == expected_map[f"{trajectory}/{node}.kimu"]
        assert not row["reconstruction"]["knots"]
        meta = metadata["nodes"][node]
        transform = audit.np.array(meta["R_NS"])
        acc = audit.np.array(source["accel_raw_counts"]) * (0.122e-3 * 9.80665)
        gyro = audit.np.array(source["gyro_raw_counts"]) * (17.5e-3 * math.pi / 180)
        # Replay preserves sensor SI; calibration applies identity parameters in
        # sensor axes, then R_NS once to produce the node SI supplied to AHRS.
        assert audit.np.allclose(acc, source["acceleration_mps2"], rtol=0, atol=1e-12)
        assert audit.np.allclose(gyro, source["angular_rate_rads"], rtol=0, atol=1e-12)
        assert audit.np.allclose(acc @ transform.T, row["calibrated_acceleration_mps2"], rtol=0, atol=1e-12)
        assert audit.np.allclose(gyro @ transform.T, row["calibrated_rate_rads"], rtol=0, atol=1e-12)
        assert audit.np.allclose(row["orientation"]["quaternion_wn"][0], meta["initial_q_WN"],
                                 rtol=0, atol=1e-15)
        for qn, qk in zip(row["orientation"]["quaternion_wn"], row["observed_quaternion_wsegment"], strict=True):
            assert audit.np.allclose(audit.rotation(qn) @ meta["R_NK"], audit.rotation(qk), rtol=0, atol=1e-14)
    case = dict(id=f"{trajectory}/CLEAN-Q/SAME/0", trajectory=trajectory,
                parameters={}, target="SAME", **{"class": "C"})
    scalars += audit.audit_case(folder, case)
    cases.append(dict(trajectory=trajectory, counts=result["counts"], coverage=result["coverage"],
                      error_summary=result["error_summary"], quantization=result["quantization"]))
content = dict(stage="B", checkpoint="CP4", checkpoint_disposition="OPEN", audit_passed=True,
               git_commit=manifest["git_commit"], canonical_files=len(products), product_sha256=products,
               independently_recomputed_error_scalars=scalars, cases=cases)
with output.open("x", encoding="utf-8", newline="\n") as stream:
    stream.write(json.dumps(content, sort_keys=True, indent=2) + "\n")
print(json.dumps(dict(audit_passed=True, cases=4, files=len(products), error_scalars=scalars)))
