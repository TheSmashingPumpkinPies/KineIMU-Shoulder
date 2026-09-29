"""Bind preview artifacts, checks and unchanged historical evidence to exact bytes."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from kineimu_shoulder.validation.stored_demo import input_audit

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent
CP3_ANCHOR = "e2c4bf26f82014ca5bde7f0deca18bd622c8062a"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    destination = EVIDENCE / "preview-audit.json"
    if destination.exists():
        raise SystemExit("preserve existing audit; use a new version/root")
    artifacts = []
    for attempt in ("01", "02", "03"):
        target = EVIDENCE / "artifacts" / f"attempt{attempt}"
        target.mkdir(parents=True, exist_ok=False)
        for original in sorted((ROOT / "dist" / f"m6-review-{attempt}").iterdir()):
            retained = target / original.name
            shutil.copyfile(original, retained)
            assert retained.read_bytes() == original.read_bytes()
            artifacts.append({"attempt": attempt, "original": original.relative_to(ROOT).as_posix(),
                              "retained": retained.relative_to(ROOT).as_posix(), "bytes": retained.stat().st_size,
                              "sha256": digest(retained), "status": "FINAL_INTERNAL_PREVIEW" if attempt == "03"
                              else "SUPERSEDED_INTERNAL_ATTEMPT"})
    for record in json.loads((EVIDENCE / "archive-green-03.json").read_text())["artifacts"]:
        assert digest(Path(record["path"])) == record["sha256"]
    installs = json.loads((EVIDENCE / "installation-audit-attempt03.json").read_text())
    assert installs["status"] == "PASS" and len(installs["records"]) == 8
    for record in installs["records"]:
        assert record["exit_code"] == 0 and digest(EVIDENCE / record["log"]) == record["log_sha256"]
    required_checks = ("full-01", "ruff-final-02", "mypy-02", "build-03", "archives-green-03", "installs-attempt03")
    for name in required_checks:
        record = json.loads((EVIDENCE / f"{name}.json").read_text())
        assert record["exit_code"] == 0 and digest(EVIDENCE / record["log"]) == record["log_sha256"]
    full = (EVIDENCE / "full-01.log").read_text(encoding="utf-8")
    assert "878 passed" in full and "skipped" not in full
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", "kineimu_shoulder", "tests", "protocols",
                    "uv.lock", "firmware", "datasets"], cwd=ROOT, check=True)
    sample = input_audit(ROOT / "datasets/samples/m6_synthetic")
    assert len(sample) == 25
    snapshot = json.loads((ROOT / "docs/release/licenses/inventory.json").read_text())
    assert snapshot["uv_lock_sha256"] == digest(ROOT / "uv.lock")
    notice_count = 0
    for dist in snapshot["distributions"]:
        for member in dist["copied_files"]:
            path = ROOT / member["copy"]
            assert path.stat().st_size == member["bytes"] and digest(path) == member["sha256"]
            notice_count += 1
    references = json.loads((ROOT / "docs/release/licenses/upstream-references.json").read_text())
    for member in references:
        assert member["status"] == "RETAINED_VERSION_TAG_REFERENCE"
        assert digest(ROOT / member["path"]) == member["sha256"]
    historical = json.loads((ROOT / "experiments/M6_CP3_20260928/SHA256SUMS.json").read_text())["files"]
    for name, record in historical.items():
        # CP4 legitimately edits the landing README; its CP3 bytes remain at the exact accepted Git anchor.
        data = subprocess.check_output(["git", "show", f"{CP3_ANCHOR}:{name}"], cwd=ROOT) if name == "README.md" \
            else (ROOT / name).read_bytes()
        assert len(data) == record["bytes"] and hashlib.sha256(data).hexdigest() == record["sha256"], name
    result = {
        "status": "PASS", "cp4_status": "OPEN_MAINTAINER_REVIEW", "public_release": False,
        "artifacts": artifacts, "required_checks": list(required_checks), "install_commands_verified": 8,
        "pytest": {"passed": 878, "skipped": 0, "actual_external_m1_root": installs.get("KINEIMU_M1_RAW_ROOT")},
        "sample_input_hashes": sample, "sample_public_permission": "PENDING_INTERNAL_ONLY",
        "original_installed_notice_files": notice_count, "version_tag_notice_files": len(references),
        "cp3_frozen_records_verified": len(historical), "cp3_anchor": CP3_ANCHOR,
        "cp3_current_readme_policy": "old exact bytes verified from accepted Git anchor; new CP4 README independent",
        "unchanged_git_boundaries": ["kineimu_shoulder", "tests", "protocols", "uv.lock", "firmware", "datasets"],
        "final_artifact_metadata": "0.1.0; license grant and citation authors not approved",
    }
    # Full-regression root comes from the actual test record, independently from the install environment.
    result["pytest"]["actual_external_m1_root"] = json.loads(
        (EVIDENCE / "full-01.json").read_text()
    )["environment"]["KINEIMU_M1_RAW_ROOT"]
    assert result["pytest"]["actual_external_m1_root"] == "<external-data>/kineimu_m1_usb_30min_20260925_01"
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Preview PASS: {len(sample)} original inputs, {notice_count}+{len(references)} license texts, "
          f"{len(historical)} CP3 frozen records, six retained artifacts; CP4 still OPEN")


if __name__ == "__main__":
    main()
