"""Verify the frozen preview's exact Git and disk bytes at its delivery anchor."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = "experiments/M6_CP4_20260928/source-snapshot.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("keep existing proof; select a new output")
    commit = subprocess.check_output(["git", "rev-parse", "--verify", f"{args.commit}^{{commit}}"],
                                     cwd=ROOT, text=True).strip()
    raw = subprocess.check_output(["git", "show", f"{commit}:{SNAPSHOT}"], cwd=ROOT)
    assert raw == (ROOT / SNAPSHOT).read_bytes()
    snapshot = json.loads(raw)
    records = {}
    mappings = {}
    for name, expected in snapshot["files"].items():
        git = subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)
        disk = (ROOT / name).read_bytes()
        assert len(disk) == expected["bytes"], name
        if git != disk:
            assert name == "kineimu_shoulder/summary.py", name
            assert expected["eol_mapping"] == "runtime CRLF to Git LF only"
            assert disk.replace(b"\r\n", b"\n") == git
            assert (ROOT / expected["runtime_copy"]).read_bytes() == disk
            assert len(git) == expected["git_bytes"]
            assert hashlib.sha256(git).hexdigest() == expected["git_sha256"]
            mappings[name] = {"git_sha256": expected["git_sha256"], "disk_sha256": expected["sha256"],
                              "method": expected["eol_mapping"], "runtime_copy": expected["runtime_copy"]}
        sha256 = hashlib.sha256(disk).hexdigest()
        assert sha256 == expected["sha256"], name
        records[name] = sha256
    result = {
        "status": "PASS", "commit": commit, "frozen_files_verified": len(records), "files": records,
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "explicit_eol_mappings": mappings,
        "cp4": "OPEN_MAINTAINER_REVIEW", "public_release": False,
        "scope": snapshot["scope"],
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Committed preview bytes PASS: {len(records)} files at {commit}; CP4 still OPEN")


if __name__ == "__main__":
    main()
