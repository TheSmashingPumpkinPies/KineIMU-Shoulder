"""Independent CP3 two-run hashes, arithmetic, oracle/coverage and finite-case audit.

No production or generator imports. Audit consistency can pass while CP3 fails.
"""

import argparse
import gzip
import json
import math
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

import numpy as np

from kineimu_shoulder.validation.oracle import labels
from kineimu_shoulder.validation.oracle import segment_matrix as oracle_segment_matrix


@lru_cache(maxsize=100000)
def segment_matrix(trajectory, node, time):
    value = oracle_segment_matrix(trajectory, node, time)
    value.setflags(write=False)
    return value


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def rotation(q):
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


def principal(a, b):
    r = a.T @ b
    skew = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]]) / 2
    return math.atan2(float(np.linalg.norm(skew)), float((np.trace(r) - 1) / 2))


def independently_turn(vector, rate, seconds):
    # Scalar Rodrigues cross-check; no production or SciPy rotation imports.
    size = float(np.linalg.norm(rate))
    if size == 0:
        return vector.copy()
    axis = rate / size
    angle = -size * seconds
    return (vector * math.cos(angle) + np.cross(axis, vector) * math.sin(angle)
            + axis * np.dot(axis, vector) * (1 - math.cos(angle)))


def audit_reconstruction(row):
    r = row.get("reconstruction")
    if r is None:
        return
    observed = np.array(row["source"]["device_time_us"], dtype=np.int64)
    times = np.array(r["timestamp_us"], dtype=np.int64)
    indices = np.array(r["observed_indices"], dtype=np.int64)
    force = np.array(r["acceleration_mps2"])
    rate = np.array(r["angular_rate_rads"])
    original_force = np.array(row["calibrated_acceleration_mps2"])
    original_rate = np.array(row["calibrated_rate_rads"])
    assert len(indices) == len(observed) and len(times) == len(observed) + len(r["knots"])
    assert (np.diff(times) > 0).all()
    assert np.array_equal(times[indices], observed)
    assert np.array_equal(force[indices], original_force)
    assert np.array_equal(rate[indices], original_rate)
    stream = row["aligned_segment_stream"]
    assert stream["timestamp_us"] == r["timestamp_us"]
    assert np.array_equal(np.array(stream["quaternion_wsegment"])[indices], row["observed_quaternion_wsegment"])
    inserted = set(range(len(times))) - set(indices.tolist())
    for left, right, time, residual in r["knots"]:
        assert right == left + 1 and observed[left] < time < observed[right]
        position = int(np.searchsorted(times, time))
        assert position in inserted
        inserted.remove(position)
        assert np.array_equal(rate[position], original_rate[left])
        early = (time - int(observed[left])) / 1e6
        expected_force = independently_turn(original_force[left], original_rate[left], early)
        assert np.allclose(force[position], expected_force, rtol=0, atol=1e-12)
        predicted = independently_turn(expected_force / np.linalg.norm(expected_force), original_rate[right],
                                       (int(observed[right]) - time) / 1e6)
        target = original_force[right] / np.linalg.norm(original_force[right])
        assert abs(float(np.linalg.norm(predicted - target)) - residual) < 1e-12
        assert residual <= .001
        difference = original_rate[left] - original_rate[right]
        axis = difference / np.linalg.norm(difference)
        g0 = original_force[left] / np.linalg.norm(original_force[left])
        p0, p1 = g0 - axis * np.dot(axis, g0), target - axis * np.dot(axis, target)
        displacement = math.atan2(float(np.dot(axis, np.cross(p1, p0))), float(np.dot(p1, p0)))
        dt = (int(observed[right]) - int(observed[left])) / 1e6
        estimated = (displacement - np.dot(axis, original_rate[right]) * dt) / np.linalg.norm(difference)
        assert time == round(int(observed[left]) + estimated * 1e6)
    assert not inserted


def audit_case(folder, case):
    annotations = read(folder / "annotations.json.gz")
    errors = read(folder / "errors.json.gz")
    processed = read(folder / "processed.json.gz")
    derived = read(folder / "derived.json.gz")
    result = read(folder / "result.json")
    assert annotations["nominal"] == labels(case["trajectory"]), (case["id"], "independent frozen labels")
    truth_n = sum(r["eligible"] for r in annotations["nominal"])
    assert result["counts"]["truth"] == truth_n
    coverage = result["coverage"]
    assert math.isclose(
        coverage["valid_duration_s"] + coverage["invalid_duration_s"], coverage["denominator_s"], abs_tol=1e-12
    )
    assert result["source_type"] == "synthetic" and result["anatomical_eligible"] is False
    arithmetic = 0
    for name, e in errors.items():
        assert len(e["actual"]) == len(e["expected"]) == len(e["signed_error"]) == len(e["absolute_error"])
        differences = []
        for actual, expected, signed, absolute in zip(
            e["actual"], e["expected"], e["signed_error"], e["absolute_error"], strict=True
        ):
            if actual is None or expected is None:
                assert signed is None and absolute is None
                continue
            delta = actual - expected
            assert delta == signed and abs(delta) == absolute, (case["id"], name, "signed error")
            differences.append(delta)
        assert e["n"] == len(differences)
        if differences:
            assert max(abs(d) for d in differences) == e["max_abs_error"]
            assert math.isclose(
                math.sqrt(sum(d * d for d in differences) / len(differences)), e["rmse"], rel_tol=1e-12, abs_tol=1e-15
            )
        else:
            assert e["max_abs_error"] is None and e["rmse"] is None
        arithmetic += len(differences)
    if derived is not None:
        references = processed.get("evidence_reference_source_sha256")
        if references is not None:
            for node in ("A", "B"):
                row = processed["nodes"][node]
                payload = (json.dumps(row["source"], sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
                assert sha256(payload).hexdigest() == row["source_sha256"]
            identity = (json.dumps([1.0, 0.0, 0.0, 0.0], indent=2) + "\n").encode()
            assert references == [processed["nodes"]["A"]["source_sha256"],
                                  processed["nodes"]["B"]["source_sha256"], sha256(identity).hexdigest()]
            relative = processed["relative"]
            for index, name in enumerate(("thorax_clock_map", "humerus_clock_map", "heading_relation")):
                item = relative[name]
                if item is not None and item["source_sha256"] != references[index]:
                    assert not any(relative["valid"])
                    reason = "clock_map_incompatible" if index < 2 else "heading_incompatible"
                    assert set(relative["reason"]) == {reason}
        grid = processed["relative"]["common_time_us"]
        speed = processed["speed"]
        begin = processed["evaluation_window_us"][0]
        valid_us = sum(y - x for x, y, v in zip(grid[:-1], grid[1:], speed["valid"], strict=True) if v and x >= begin)
        assert valid_us / 1e6 == coverage["valid_duration_s"]
        assert math.isclose(coverage["relative"], valid_us / 1e6 / coverage["denominator_s"], abs_tol=1e-15)
        drift = processed["trace"]["drift_evidence"] if processed["trace"] is not None else None
        if drift is not None and case["parameters"].get("heading_rate_rads"):
            expected_bound = (
                abs(case["parameters"]["heading_rate_rads"])
                * (drift["covered_window_us"][1] - drift["covered_window_us"][0])
                / 1e6
                if case["target"] in ("A", "SAME", "DIFF")
                else 0.0
            )
            assert drift["bound_rad"] == expected_bound
        actual_valid = derived["summary"]["valid_count"]
        assert result["counts"]["valid"] == actual_valid
        if actual_valid:
            assert coverage["proxy"] == (derived["summary"]["proxy_valid_count"] or 0) / actual_valid
        observed = errors["elevation"]
        support = observed["support"]
        rows = {t: v for t, v in zip(grid, processed["elevation"], strict=True)}
        assert observed["actual"] == [rows[t] for t in support]
        expected = []
        for t in support:
            r = segment_matrix(case["trajectory"], "A", t / 1e6).T @ segment_matrix(case["trajectory"], "B", t / 1e6)
            expected.append(math.atan2(float(np.linalg.norm(r[:2, 2])), float(r[2, 2])))
        assert np.allclose(observed["expected"], expected, rtol=0, atol=1e-15)
        expected_speed = []
        for t0, t1 in errors["interval_speed"]["support"]:
            r0 = segment_matrix(case["trajectory"], "A", t0 / 1e6).T @ segment_matrix(case["trajectory"], "B", t0 / 1e6)
            r1 = segment_matrix(case["trajectory"], "A", t1 / 1e6).T @ segment_matrix(case["trajectory"], "B", t1 / 1e6)
            expected_speed.append(principal(r0, r1) / ((t1 - t0) / 1e6))
        assert np.allclose(errors["interval_speed"]["expected"], expected_speed, rtol=0, atol=1e-12)
        # Independently recompute orientation geodesics at TRUE observation times.
        for node, row in processed["nodes"].items():
            audit_reconstruction(row)
            times = row["source"]["true_time_us"]
            quaternions = row.get("observed_quaternion_wsegment", row["aligned_segment_stream"]["quaternion_wsegment"])
            values = {
                t: principal(segment_matrix(case["trajectory"], node, t / 1e6), rotation(q))
                for t, q in zip(times, quaternions, strict=True)
            }
            initialization = errors[node + ".initialization"]
            for t, actual in zip(initialization["support"], initialization["actual"], strict=True):
                expected = values.get(t)
                assert (actual is None and expected is None) or (
                    actual is not None and expected is not None and abs(actual - expected) < 3e-15
                )
            e = errors[node + ".orientation"]
            assert np.allclose(e["actual"], [values[t] for t in e["support"]], rtol=0, atol=3e-15)
            retention = row["retention"]
            assert retention["lost_samples"] == retention["original_samples"] - len(times)
            sequence = row["source"]["sequence"]
            assert retention["lost_packets"] == retention["original_packets"] - len({i // 4 for i in sequence})
    if case["class"] in ("C", "W") and result["passed"]:
        minimum = 0.98 if case["class"] == "W" else 1.0
        assert coverage["relative"] >= minimum, (case["id"], "coverage")
        assert result["counts"]["missed"] == result["counts"]["false"] == 0
        if truth_n:
            assert coverage["recall"] == coverage["proxy"] == 1.0
        for name, e in errors.items():
            if e["gate"]:
                assert e["n"] > 0 and e["max_abs_error"] is not None and e["max_abs_error"] <= e["tolerance"], (
                    case["id"],
                    name,
                )
                if case["class"] == "C":
                    assert e["n"] == len(e["actual"])
    return arithmetic


def audit(root, output):
    if output.exists():
        raise FileExistsError(output)
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("audit output must be outside immutable formal root")
    repo = Path(__file__).resolve().parents[2]
    matrix = read(repo / "experiments/M5_CP1_20260926/case-manifest.json")
    expected_ids = [c["id"] for c in matrix]
    partial = read(repo / "experiments/M5_CP3_20260926/partial-attempts.json")
    for attempt in [partial, *partial.get("additional_attempts", [])]:
        for run, record in attempt["runs"].items():
            for name, h in record["files"].items():
                assert sha256((repo / attempt["root"] / run / name).read_bytes()).hexdigest() == h, (
                    "partial altered",
                    run,
                    name,
                )
    maps = []
    totals = []
    for run in ("run1", "run2"):
        folder = root / run
        checksums = read(folder / "SHA256SUMS.json")
        products = {
            p.relative_to(folder).as_posix(): p
            for p in folder.rglob("*")
            if p.is_file() and "operational" not in p.relative_to(folder).parts
        }
        assert set(checksums) == set(products) - {"SHA256SUMS.json"}, (run, "inventory")
        actual = {name: sha256(p.read_bytes()).hexdigest() for name, p in products.items()}
        assert all(actual[name] == h for name, h in checksums.items())
        launch, report = read(folder / "manifest.json"), read(folder / "report.json")
        assert launch["formal"] and not launch["tracked_dirty"]
        assert launch["case_ids"] == expected_ids == [r["id"] for r in report["results"]]
        assert report["case_count"] == len(matrix) and report["not_run_count"] == 0
        for name, h in launch["source_file_sha256"].items():
            assert sha256((repo / name).read_bytes()).hexdigest() == h, ("source changed", name)
        scalars = 0
        for index, (case, result) in enumerate(zip(matrix, report["results"], strict=True)):
            if result["stage_disposition"] == "existing_frozen_fixture":
                assert result["fixture_tests"] and result["passed"] == all(t["passed"] for t in result["fixture_tests"])
            else:
                scalars += audit_case(folder / f"case-{index:04d}", case)
            for name, h in result["artifacts"].items():
                assert checksums[name] == h
        assert report["passed"] == all(r["passed"] for r in report["results"])
        assert report["failed_case_count"] == sum(not r["passed"] for r in report["results"])
        maps.append(actual)
        totals.append(scalars)
    assert maps[0] == maps[1], "two independent canonical product maps differ"
    assert totals[0] == totals[1]
    report = read(root / "run1/report.json")
    result = dict(
        audit_passed=True,
        checkpoint_passed=report["passed"],
        git_commit=read(root / "run1/manifest.json")["git_commit"],
        case_count=len(matrix),
        not_run_count=0,
        failed_case_count=report["failed_case_count"],
        files_per_run=len(maps[0]),
        bytes_per_run=sum(p.stat().st_size for name, p in products.items()),
        checked_error_scalars_per_run=totals[0],
        all_product_bytes_equal=True,
        independent_oracle_and_coverage_checked=True,
        sha256=maps[0],
        audit_source_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "sha256"}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.root, args.output)
