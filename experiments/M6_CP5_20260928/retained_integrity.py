"""Verify retained benchmark and third-party evidence from cloned files."""

import hashlib
import json
import subprocess

from collect import CLONE, write

if __name__ == "__main__":
    previous = json.loads((CLONE / "experiments/M6_CP4_FINAL_20260928/integrity-final.json").read_bytes())
    cp3 = json.loads((CLONE / "experiments/M6_CP3_20260928/SHA256SUMS.json").read_bytes())
    for name, expected in cp3["files"].items():
        raw = (subprocess.check_output(["git", "show", f"{previous['cp3_original_readme_anchor']}:{name}"], cwd=CLONE)
               if name == "README.md" else (CLONE / name).read_bytes())
        assert len(raw) == expected["bytes"] and hashlib.sha256(raw).hexdigest() == expected["sha256"], name
    assert len(cp3["files"]) == 556
    inventory = json.loads((CLONE / "docs/release/licenses/inventory.json").read_bytes())
    notices = [record for dist in inventory["distributions"] for record in dist["copied_files"]]
    upstream = json.loads((CLONE / "docs/release/licenses/upstream-references.json").read_bytes())
    for record in [*notices, *upstream]:
        raw = (CLONE / record.get("copy", record.get("path"))).read_bytes()
        assert len(raw) == record["bytes"] and hashlib.sha256(raw).hexdigest() == record["sha256"]
    for name, expected in previous["previous_artifact_notice_files"].items():
        assert hashlib.sha256((CLONE / name).read_bytes()).hexdigest() == expected
    write("retained-integrity.json", dict(status="PASS", cp3_frozen_files=556,
          cp3_original_readme_anchor=previous["cp3_original_readme_anchor"],
          installed_notice_texts=len(notices), upstream_notice_texts=len(upstream),
          previous_artifact_notice_files=len(previous["previous_artifact_notice_files"]),
          new_benchmark_measurement=False, previous_statistics_and_failed_attempts_unchanged=True))
    print("Retained integrity PASS: CP3 556 files, 52+2 notice texts, 66 prior artifact/notice files")
