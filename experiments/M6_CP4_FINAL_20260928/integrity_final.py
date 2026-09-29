"""Audit final release boundaries, immutable evidence, notices and command records."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent
ENTRY = "d66bf61b51b5fa39a96fbd4f619e3dc63e3d04d4"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_bytes(commit: str, name: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)


def main() -> None:
    destination = EVIDENCE / "integrity-final.json"
    assert not destination.exists(), "preserve prior audits"
    previous = json.loads((EVIDENCE / "integrity-01.json").read_bytes())
    sample = ROOT / "datasets/samples/m6_synthetic"
    for name, expected in previous["sample_inputs"].items():
        path = sample / name
        assert digest(path.read_bytes()) == expected, name
        assert path.read_bytes() == git_bytes(ENTRY, path.relative_to(ROOT).as_posix()), name
    for name in ("README.md", "provenance.json", "LICENSE.md"):
        path = sample / name
        assert path.read_bytes() == git_bytes(ENTRY, path.relative_to(ROOT).as_posix()), name
    for name, expected in previous["old_artifact_and_notice_files"].items():
        assert digest((ROOT / name).read_bytes()) == expected, name

    cp3 = json.loads((ROOT / "experiments/M6_CP3_20260928/SHA256SUMS.json").read_bytes())
    for name, record in cp3["files"].items():
        raw = git_bytes(previous["cp3_old_readme_anchor"], name) if name == "README.md" else (ROOT / name).read_bytes()
        assert len(raw) == record["bytes"] and digest(raw) == record["sha256"], name
    assert len(cp3["files"]) == 556

    inventory = json.loads((ROOT / "docs/release/licenses/inventory.json").read_bytes())
    copied = [entry for dist in inventory["distributions"] for entry in dist["copied_files"]]
    for entry in copied:
        raw = (ROOT / entry["copy"]).read_bytes()
        assert len(raw) == entry["bytes"] and digest(raw) == entry["sha256"], entry["copy"]
    upstream = json.loads((ROOT / "docs/release/licenses/upstream-references.json").read_bytes())
    for entry in upstream:
        raw = (ROOT / entry["path"]).read_bytes()
        assert len(raw) == entry["bytes"] and digest(raw) == entry["sha256"], entry["path"]

    allowed = {"experiments/m1_ble_link_matrix.py", "tests/contracts/test_m1_ble_link_matrix_event_timing.py"}
    changed = set(subprocess.check_output([
        "git", "diff", ENTRY, "HEAD", "--name-only", "--", "kineimu_shoulder", "tests", "protocols", "uv.lock",
        "firmware", "datasets", "experiments/m1_ble_link_matrix.py",
    ], cwd=ROOT, text=True).splitlines())
    assert changed == allowed, changed
    assert not subprocess.check_output([
        "git", "diff", "HEAD", "--", "kineimu_shoulder", "tests", "protocols", "uv.lock", "firmware", "datasets",
        "experiments/m1_ble_link_matrix.py",
    ], cwd=ROOT), "uncommitted protected input change"

    commands = {}
    for path in sorted(EVIDENCE.glob("*.json")):
        record = json.loads(path.read_bytes())
        if isinstance(record, dict) and "command" in record and "log_sha256" in record:
            assert digest((EVIDENCE / record["log"]).read_bytes()) == record["log_sha256"], path.name
            commands[path.name] = record["exit_code"]
    for label in ("candidate01", "candidate02"):
        audit = json.loads((EVIDENCE / f"installation-audit-{label}.json").read_bytes())
        assert audit["status"] == "PASS" and len(audit["records"]) == 8
        assert audit["KINEIMU_M1_RAW_ROOT"] is None and audit["PYTHONPATH"] is None
        for record in audit["records"]:
            assert record["exit_code"] == 0
            assert digest((EVIDENCE / record["log"]).read_bytes()) == record["log_sha256"]
        for name, expected in audit["artifact_sha256"].items():
            assert digest((EVIDENCE / "artifacts" / label / name).read_bytes()) == expected

    result = {
        "status": "PASS", "entry_head": ENTRY,
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "sample_inputs": previous["sample_inputs"], "original_sample_readme_provenance_cc0_annex": "UNCHANGED",
        "previous_artifact_notice_files": previous["old_artifact_and_notice_files"],
        "cp3_frozen_files": len(cp3["files"]), "cp3_original_readme_anchor": previous["cp3_old_readme_anchor"],
        "installed_notice_files": len(copied), "upstream_notice_files": len(upstream),
        "protected_boundary_changes": sorted(changed),
        "change_scope": "experiment-only early-timer-wakeup guard and deterministic test; no physical reacquisition",
        "production_protocols_dependencies_firmware_sample": "UNCHANGED", "command_log_exits": commands,
        "independent_install_commands": 16, "public_publishing": False, "linux": "NOT RUN",
    }
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Integrity PASS: 25 sample originals, {len(copied)} installed notices, 2 upstream notices, "
          f"66 old artifacts/notices, 556 CP3 frozen files, {len(commands)} exact command logs, 16 install commands")


if __name__ == "__main__":
    main()
