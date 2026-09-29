"""Independent retained CP2 byte/hash, frozen-label and error arithmetic audit.

Run after both processes finish. No generator or production numerical imports.
Never modifies a run directory. Writes only a new external audit artifact.
"""

import argparse
import json
import math
from hashlib import sha256
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit(root, output):
    if output.exists():
        raise FileExistsError(output)
    repo = Path(__file__).resolve().parents[2]
    expected_cases = [row["id"] for row in read(repo / "experiments/M5_CP1_20260926/case-manifest.json")
                      if row["condition"].startswith("CLEAN-")]
    cp1 = read(repo / "experiments/M5_CP1_20260926/run1/annotations.json")
    file_maps = []
    for run in ("run1", "run2"):
        folder = root / run
        manifests = read(folder / "SHA256SUMS.json")
        files = {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        assert set(manifests) == set(files) - {"SHA256SUMS.json"}, (run, "missing/extra files")
        assert all(sha256(files[name]).hexdigest() == value for name, value in manifests.items())
        launch, report = read(folder / "manifest.json"), read(folder / "report.json")
        assert launch["formal"] and not launch["tracked_dirty"]
        assert launch["case_ids"] == expected_cases
        assert report["case_count"] == 30 and report["failed_case_count"] == report["not_run_count"] == 0
        assert report["passed"] and all(c["passed"] and c["record"]["comparable"] for c in report["comparisons"])
        assert len(report["comparisons"]) == 2
        for name, value in launch["source_file_sha256"].items():
            assert sha256((repo / name).read_bytes()).hexdigest() == value, (run, name, "source changed")
        arithmetic_rows = 0
        for case_id in expected_cases:
            trajectory, condition, _, _ = case_id.split("/")
            path = condition.split("-")[-1]
            case = folder / trajectory / path
            result, annotations = read(case / "result.json"), read(case / "annotations.json")
            assert annotations["nominal"] == cp1[trajectory]["nominal_m4"], (case_id, "frozen labels")
            assert result["passed"] and not result["failed_gates"]
            assert result["coverage"]["relative"] == 1.0
            assert result["coverage"]["valid_duration_s"] + result["coverage"]["invalid_duration_s"] == (
                result["coverage"]["denominator_s"])
            assert result["counts"]["missed"] == result["counts"]["false"] == 0
            assert result["counts"]["valid"] == sum(r["eligible"] for r in annotations["nominal"])
            assert result["source_type"] == "synthetic" and not result["anatomical_eligible"]
            if result["counts"]["truth"]:
                assert result["coverage"]["recall"] == result["coverage"]["proxy"] == 1.0
            for name, error in result["errors"].items():
                differences = [a - e for a, e in zip(error["actual"], error["expected"], strict=True)
                               if a is not None and e is not None]
                assert error["n"] == len(differences)
                if differences:
                    maximum = max(abs(d) for d in differences)
                    rmse = math.sqrt(sum(d * d for d in differences) / len(differences))
                    assert maximum == error["max_abs_error"], (case_id, name, "error max")
                    assert math.isclose(rmse, error["rmse"], abs_tol=1e-15, rel_tol=1e-12)
                    for delta, signed, absolute in zip(differences, error["signed_error"],
                                                       error["absolute_error"], strict=True):
                        assert delta == signed and abs(delta) == absolute
                    arithmetic_rows += len(differences)
                if error["gate"]:
                    assert len(differences) == len(error["actual"]) and differences
                    assert error["max_abs_error"] <= error["tolerance"], (case_id, name)
            if path == "Q":
                for node in ("A", "B"):
                    expected = repo / "experiments/M5_CP1_20260926/run1" / trajectory / f"{node}.kimu"
                    actual = case / f"{trajectory}-{node}.kimu"
                    assert actual.read_bytes() == expected.read_bytes(), (case_id, node, "Q input")
        file_maps.append(files)
    assert file_maps[0].keys() == file_maps[1].keys()
    assert all(content == file_maps[1][name] for name, content in file_maps[0].items()), "two-run byte mismatch"
    metadata = read(root / "run1/manifest.json")
    result = dict(passed=True, git_commit=metadata["git_commit"], case_count=30,
                  audit_source_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                  files_per_run=len(file_maps[0]), bytes_per_run=sum(map(len, file_maps[0].values())),
                  checked_error_scalar_rows_per_run=arithmetic_rows,
                  frozen_cp1_labels_equal=True, q_inputs_equal_cp1=True,
                  all_output_bytes_equal=True, all_manifest_hashes_valid=True,
                  source_type="synthetic", anatomical_eligible=False,
                  sha256={name: sha256(content).hexdigest() for name, content in sorted(file_maps[0].items())})
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "sha256"}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.root, args.output)
