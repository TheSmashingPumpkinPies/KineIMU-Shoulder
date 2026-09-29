"""Independent CP4 pair audit, reusing unchanged complete B/C/D numerical auditors.

No formal_replay helper or numerical runner is imported. Audit outputs live
outside both immutable canonical collections.
"""

import argparse
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "experiments/M5_CP4_STAGE_E2_20260928"
EXTERNAL = Path("<external-data>/kineimu_m1_usb_30min_20260925_01")
STAGES = {
    "B": {"manifest.json", "report.json"}
    | {
        f"cases/Q-{t}/{n}"
        for t in ("F90", "AL90", "AR90", "T-MIX")
        for n in ("result.json", "processed.json.gz", "derived.json.gz", "annotations.json.gz", "errors.json.gz")
    },
    "C": {"manifest.json", "report.json", "cases/REC-NODE-B/result.json"},
    "D": {"manifest.json", "report.json", "downstream.json", "cases/M1-A/result.json", "cases/M1-B/result.json"},
}
EXPECTED = {"manifest.json", "report.json"} | {
    f"{s}/{n}" for s, names in STAGES.items() for n in names | {"SHA256SUMS.txt"}
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def product_map(root, expected):
    found = {}
    for line in (root / "SHA256SUMS.txt").read_text().splitlines():
        value, name = line.split("  ")
        require(name in expected and name not in found, "safe unique required product")
        require((root / name).resolve().is_relative_to(root.resolve()), "contained product")
        require(digest(root / name) == value, "product byte hash")
        found[name] = value
    require(set(found) == expected, "complete canonical support")
    require(
        {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} == expected | {"SHA256SUMS.txt"},
        "no unlisted products",
    )
    return found


def compare_canonical(one, two, expected):
    require(one.resolve() != two.resolve(), "distinct formal roots")
    first, second = product_map(one, expected), product_map(two, expected)
    require(first == second, "identical product digests")
    for name in expected | {"SHA256SUMS.txt"}:
        require((one / name).read_bytes() == (two / name).read_bytes(), "identical canonical bytes")
    return dict(canonical_equal=True, canonical_products=len(expected), product_sha256=first)


def audit_pair(one, two, launch, archive):
    execution = read(launch)
    require(
        execution["source_lock"] == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "unchanged launch HEAD",
    )
    runs = execution["runs"]
    require(len(runs) == 2 and all(r["exit_code"] == 0 for r in runs), "both actual complete executions")
    require(runs[0]["pid"] != runs[1]["pid"] and all(r["pid"] > 0 for r in runs), "independent processes")
    for i, run in enumerate((one, two)):
        record = runs[i]
        operation = read(EVIDENCE / record["operation"])
        require(operation["pid"] == record["pid"] and operation["output"] == str(run.resolve()), "worker identity")
        require(operation["source_lock"] == execution["source_lock"] and not operation["tracked_dirty"], "clean worker")
        require(digest(EVIDENCE / record["log"]) == record["log_sha256"], "execution log bytes")
        require(
            record["command"]
            == [
                sys.executable,
                "-m",
                "kineimu_shoulder.validation.formal_replay",
                "--output",
                run.relative_to(ROOT).as_posix(),
                "--operation",
                (EVIDENCE / record["operation"]).relative_to(ROOT).as_posix(),
                "--root",
                str(EXTERNAL),
            ],
            "complete launch command",
        )
    checks = read(EVIDENCE / "checks.json")
    require(set(checks) == {"focused", "full", "ruff", "mypy", "docs", "whitespace"}, "required checks")
    for item in checks.values():
        require(item["exit_code"] == 0 and digest(EVIDENCE / item["path"]) == item["sha256"], "check exit/log")
    full = (EVIDENCE / checks["full"]["path"]).read_text()
    require(
        " skipped" not in full and " failed" not in full and " passed" in full, "full suite no skipped required input"
    )
    equality = compare_canonical(one, two, EXPECTED)
    manifest = read(one / "manifest.json")
    require(manifest["formal"] is True and manifest["stage"] == "E-formal-B-C-D", "formal E envelope")
    require(not manifest["tracked_dirty"] and manifest["git_commit"] == execution["source_lock"], "clean source lock")
    require(manifest["recorded_processing_version"] == "m5-recorded-segments/1.0", "approved D contract")
    require(
        manifest["input_before"] == manifest["input_after"] == execution["input_before"] == execution["input_after"],
        "all input snapshots before/after",
    )
    sources = manifest["source_file_sha256"]
    with ZipFile(archive) as zipped:
        require(
            set(zipped.namelist()) == set(sources) and len(zipped.namelist()) == len(sources),
            "exact source ZIP inventory",
        )
        for name, value in sources.items():
            require(sha256(zipped.read(name)).hexdigest() == value == digest(ROOT / name), "exact source bytes")
    numerical = []
    for index, run in enumerate((one, two), 1):
        report = read(run / "report.json")
        require(
            report["collection_complete"] and report["stage_exit_codes"] == dict(B=0, C=0, D=0), "complete collection"
        )
        require(
            report["required_case_count"] == 7 and report["artifact_disposition"] == "complete-formal-collection",
            "all seven cases",
        )
        for name in ("manifest.json", "report.json"):
            data = read(run / name)
            require(
                (run / name).read_bytes()
                == (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(),
                "canonical envelope",
            )
        for stage in STAGES:
            sub = read(run / stage / "manifest.json")
            require(
                sub["git_commit"] == execution["source_lock"] and not sub["tracked_dirty"], "subprocessor clean lock"
            )
            require(
                product_map(run / stage, STAGES[stage]) == manifest["stage_product_sha256"][stage],
                "complete stage binding",
            )
            require(all(sources[n] == d for n, d in sub["source_file_sha256"].items()), "complete source binding")
        outputs = {s: EVIDENCE / f"run{index}-audit-{s}.json" for s in STAGES}
        commands = {
            "B": [
                sys.executable,
                "experiments/M5_CP4_STAGE_B_20260927/audit.py",
                (run / "B").relative_to(ROOT).as_posix(),
                outputs["B"].relative_to(ROOT).as_posix(),
            ],
            "C": [
                sys.executable,
                "experiments/M5_CP4_STAGE_C_20260927/audit.py",
                "--run",
                str(run / "C"),
                "--output",
                str(outputs["C"]),
            ],
            "D": [
                sys.executable,
                "experiments/M5_CP4_STAGE_D2_20260927/audit.py",
                "--run",
                str(run / "D"),
                "--root",
                str(EXTERNAL),
                "--output",
                str(outputs["D"]),
            ],
        }
        for stage, command in commands.items():
            log = EVIDENCE / f"run{index}-audit-{stage}.log"
            with log.open("xb") as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            original_log = log.read_bytes()
            log.write_bytes(original_log.decode("utf-8-sig").replace("\r\n", "\n").encode())
            require(result.returncode == 0, f"independent {stage} audit exit {result.returncode}; preserve log")
            data = read(outputs[stage])
            require(data.get("passed", data.get("audit_passed")) is True, "independent numerical pass")
            numerical.append(
                dict(
                    run=index,
                    stage=stage,
                    command=command,
                    exit_code=result.returncode,
                    path=outputs[stage].name,
                    sha256=digest(outputs[stage]),
                    log_sha256=digest(log),
                    original_log_sha256=sha256(original_log).hexdigest(),
                )
            )
    # Each numerical auditor rechecks original sources at both ends, including
    # all eleven external members for D; compare their direct observations.
    for index in (1, 2):
        d = read(EVIDENCE / f"run{index}-audit-D.json")
        require(
            d["samples_checked"] == 379196
            and d["ahrs_quaternions_checked"] == 379195
            and d["rejected_rows_checked"] == 1
            and d["processing_segments_checked"] == 3
            and d["downstream_rows_checked"] == 187772
            and d["packets_checked"] == 94799,
            "complete D support",
        )
        require(
            d["external_manifest_before"] == d["external_manifest_after"] == manifest["input_before"]["external"],
            "independent original manifest",
        )
        c = read(EVIDENCE / f"run{index}-audit-C.json")
        require(c["samples_checked"] == 832 and c["ahrs_quaternions_checked"] == 832, "complete C support")
    require(compare_canonical(one, two, EXPECTED) == equality, "unchanged products after audit")
    return dict(
        schema_version="m5-report/1.0",
        checkpoint="CP4",
        checkpoint_disposition="PASS",
        passed=True,
        source_lock=execution["source_lock"],
        formal=True,
        independent_processes=2,
        canonical_comparison=equality,
        independent_numerical_audits=numerical,
        input_before=manifest["input_before"],
        input_after=manifest["input_after"],
        source_archive_sha256=digest(archive),
        source_files_checked=len(sources),
        limitations=[
            "Recorded shoulder values remain unavailable; no anatomical/clinical validation.",
            "D uses approved independent worlds with one preserved rejected row.",
            "CP5 and overall M5 remain OPEN; hardware remains frozen.",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("one", "two", "launch", "archive", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "fresh audit output")
    result = audit_pair(args.one, args.two, args.launch, args.archive)
    with args.output.open("xb") as stream:
        stream.write((json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())
    print("CP4 PASS: two complete independent collections, canonical equality, six complete numerical audits")


if __name__ == "__main__":
    main()
