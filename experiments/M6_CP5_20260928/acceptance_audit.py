"""Accept CP5 only from actual complete command, product, install and skip evidence."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

from collect import CLONE, HEAD, hashes, write
from run_check import EVIDENCE, ROOT


def read(name):
    return json.loads((EVIDENCE / name).read_bytes())


if __name__ == "__main__":
    names = (
        "clone-01", "sync-analysis-01", "runtime-analysis-01", "help-01", "demo-01", "demo-02",
        "pair-audit-01", "sync-all-extras-01", "full-01", "ruff-clone-01", "mypy-clone-01",
        "docs-clone-01", "whitespace-clone-01", "build-clone-01", "archives-clone-01",
        "installations-command-01", "integrity-01", "retained-integrity-command-01",
        "frozen-compare-command-03", "provenance-green-01", "artifact-copy-command-02",
        "ruff-final-02", "docs-final-02", "whitespace-final-02", "docs-focused-01",
    )
    records = {}
    for name in names:
        record = read(f"{name}.json")
        assert record["exit_code"] == 0, name
        assert hashlib.sha256((EVIDENCE / record["log"]).read_bytes()).hexdigest() == record["log_sha256"], name
        assert record["environment"]["KINEIMU_M1_RAW_ROOT"] is None
        assert record["environment"]["PYTHONPATH"] is None
        records[name] = record
    junit = ET.parse(EVIDENCE / "full-junit.xml").getroot()
    cases = junit.findall(".//testcase")
    skips = [dict(classname=case.attrib["classname"], name=case.attrib["name"],
                  reason=case.find("skipped").attrib["message"]) for case in cases if case.find("skipped") is not None]
    assert len(cases) == 879 and len(skips) == 2
    assert not junit.findall(".//failure") and not junit.findall(".//error")
    assert all(row["classname"] == "tests.integration.test_m2_replay_m1_bench" for row in skips)
    assert all(row["reason"] == "set KINEIMU_M1_RAW_ROOT to the immutable M1 bench root" for row in skips)
    pair = read("pair-audit.json")
    assert pair["cp2_passed"] and pair["equal_canonical_products"] == 22 and pair["equal_summary"]
    frozen = read("frozen-products-03.json")
    assert frozen["status"] == "PASS" and len(frozen["exact_equal_scientific_products_and_summary"]) == 21
    assert frozen["summary_equal_after_exact_source_head_substitution"] and frozen["run_other_fields_equal"]
    for name in ("clone-integrity.json", "retained-integrity.json", "archive-review.json", "artifact-copy-02.json"):
        assert read(name)["status"] == "PASS", name
    installation = read("installation-audit-clone-build-01.json")
    assert installation["status"] == "PASS" and len(installation["records"]) == 8
    for record in installation["records"]:
        assert record["exit_code"] == 0
        assert hashlib.sha256((EVIDENCE / record["log"]).read_bytes()).hexdigest() == record["log_sha256"]
    assert installation["artifact_sha256"] == hashes(EVIDENCE / "artifacts/clone-build-02")
    before = read("clone-preflight.json")["sample_files_before"]
    assert before == read("sample-after-demos.json") == hashes(CLONE / "datasets/samples/m6_synthetic")
    assert before == hashes(ROOT / "datasets/samples/m6_synthetic")
    for number in (1, 2):
        assert hashes(CLONE / f"demo-output-{number:02}") == hashes(EVIDENCE / f"run{number}")
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CLONE, text=True).strip() == HEAD
    assert not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=CLONE)
    previous_failures = {}
    for name in ("helper-ruff-01", "helper-ruff-03", "frozen-products-01", "provenance-red-01",
                 "docs-final-01", "dynamic-docs-red-01"):
        record = read(f"{name}.json")
        assert record["exit_code"] != 0
        assert hashlib.sha256((EVIDENCE / record["log"]).read_bytes()).hexdigest() == record["log_sha256"]
        previous_failures[name] = record
    write("acceptance.json", dict(
        cp5="PASS", m6="DONE at local V1 acceptance scope", version="0.1.0", source_head=HEAD,
        required_gates=records, tests=dict(passed=877, skipped=2, failed=0, errors=0, collected=879),
        expected_skips=skips, demo_skips=0, independent_install_commands=8,
        retained_expected_failures=previous_failures,
        unrecorded_driver_failures=("See ATTEMPTS.md: result/command-name collision "
                                    "and partial copy .gitignore; retained"),
        rebuilt_artifact_sha256=installation["artifact_sha256"],
        cp4_maintainer_regression="879 passed / 0 skips; actual external M1 root; preserved separately",
        sample_files_unchanged=len(before), runtime_git_exact_files=frozen["runtime_files"],
        linux="NOT RUN", hardware="frozen; no device access required", external_sensor_data="not used by CP5",
        public_repository_created=False, pushed=False, tagged=False, github_release=False, pypi_uploaded=False,
        coverage="COVERAGE.md", report="REPORT.md",
        committed_byte_proof="Separate delivery snapshot/proof after commit",
    ))
    print("CP5 PASS: README fresh-clone pair, frozen science, full877+2 expected skips, checks, build and two installs")
