"""Aggregate actual final CP4 gates without discarding earlier failures."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent


def main() -> None:
    output = EVIDENCE / "acceptance.json"
    assert not output.exists(), "keep previous acceptance records"
    required = ["citation-01", "sync-01", "settle-green-01", "ruff-final-08", "mypy-fix-02",
                "docs-final-04", "full-02", "build-02", "archives-02", "installs-command-02",
                "integrity-command-02", "source-proof-02", "whitespace-final-01"]
    records = {}
    for name in required:
        record = json.loads((EVIDENCE / f"{name}.json").read_bytes())
        assert record["exit_code"] == 0, name
        raw = (EVIDENCE / record["log"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["log_sha256"], name
        records[name] = record
    full = (EVIDENCE / records["full-02"]["log"]).read_text(encoding="utf-8")
    match = re.search(r"=+ (879) passed in ([0-9.]+)s(?: \([^)]*\))? =+", full)
    assert match, "complete regression must have 879 passed and no failed/skipped tests"
    assert records["full-02"]["environment"]["KINEIMU_M1_RAW_ROOT"] == (
        "<external-data>/kineimu_m1_usb_30min_20260925_01"
    )
    citation = json.loads((EVIDENCE / "citation-candidate-audit.json").read_bytes())
    assert citation["cff_schema_valid"] is True and not citation["errors"]
    assert citation["citation_sha256"] == hashlib.sha256((ROOT / "CITATION.cff").read_bytes()).hexdigest()
    archive = json.loads((EVIDENCE / "archive-candidate-02.json").read_bytes())
    assert archive["status"] == "PASS" and not archive["errors"]
    assert archive["source_files_verified"] == 34 and archive["notice_files_required"] == 57
    install = json.loads((EVIDENCE / "installation-audit-candidate02.json").read_bytes())
    assert install["status"] == "PASS" and len(install["records"]) == 8
    for record in install["records"]:
        assert record["exit_code"] == 0
        assert hashlib.sha256((EVIDENCE / record["log"]).read_bytes()).hexdigest() == record["log_sha256"]
    for name, expected in install["artifact_sha256"].items():
        assert hashlib.sha256((EVIDENCE / "artifacts/candidate02" / name).read_bytes()).hexdigest() == expected
    integrity = json.loads((EVIDENCE / "integrity-final.json").read_bytes())
    assert integrity["status"] == "PASS"
    prior_failures = {}
    for name in ("ruff-01", "settle-red-01", "full-01"):
        record = json.loads((EVIDENCE / f"{name}.json").read_bytes())
        assert record["exit_code"] != 0
        assert hashlib.sha256((EVIDENCE / record["log"]).read_bytes()).hexdigest() == record["log_sha256"]
        prior_failures[name] = record
    result = {
        "cp4": "PASS", "version": "0.1.0", "copyright": "2026 Hongbo Liao", "license": "MIT",
        "sample_license": "CC0-1.0 for exact selected originals", "author": "Hongbo Liao",
        "public_destination": "TheSmashingPumpkinPies/kineimu-shoulder", "published": False,
        "required_gates": records, "retained_expected_failures": prior_failures,
        "full_tests": {"passed": 879, "failed": 0, "skipped": 0, "seconds": float(match[2])},
        "artifact_sha256": install["artifact_sha256"], "independent_final_install_commands": 8,
        "limits": {"cp5": "OPEN", "linux": "NOT RUN", "human_clinical_validation": "outside scope"},
        "git_delivery_proof": "subsequent verify_candidate run against delivery-snapshot.json",
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("CP4 PASS: approved decisions, CFF schema, docs, 879 full tests, Ruff/mypy, build/archive, "
          "independent installs and integrity; CP5 OPEN, Linux NOT RUN, not published")


if __name__ == "__main__":
    main()
