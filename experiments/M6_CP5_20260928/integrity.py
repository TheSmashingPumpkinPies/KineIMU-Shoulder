"""Check frozen CP4 delivery in the clone, including the declared Git LF mapping."""

import hashlib
import json
import subprocess

from collect import CLONE, HEAD, hashes, write

if __name__ == "__main__":
    snapshot = json.loads((CLONE / "experiments/M6_CP4_FINAL_20260928/delivery-snapshot.json").read_bytes())
    verified, eol = {}, {}
    for name, expected in snapshot["files"].items():
        raw = (CLONE / name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if "eol_mapping" in expected:
            assert name == "kineimu_shoulder/summary.py"
            assert digest == expected["git_sha256"] and len(raw) == expected["git_bytes"]
            original = (CLONE / expected["runtime_copy"]).read_bytes()
            assert original.replace(b"\r\n", b"\n") == raw
            assert hashlib.sha256(original).hexdigest() == expected["sha256"]
            eol[name] = dict(clone_sha256=digest, cp4_runtime_sha256=expected["sha256"],
                             reason="Fresh Git clone checks out LF; CP4 retained actual CRLF runtime copy unchanged")
        else:
            assert digest == expected["sha256"] and len(raw) == expected["bytes"], name
        verified[name] = digest
    cp4 = json.loads((CLONE / "experiments/M6_CP4_FINAL_20260928/acceptance.json").read_bytes())
    assert cp4["cp4"] == "PASS" and cp4["full_tests"]["passed"] == 879 and cp4["full_tests"]["skipped"] == 0
    candidate = CLONE / "experiments/M6_CP4_FINAL_20260928/artifacts/candidate02"
    assert hashes(candidate) == cp4["artifact_sha256"]
    for record in cp4["required_gates"].values():
        log = CLONE / "experiments/M6_CP4_FINAL_20260928" / record["log"]
        assert record["exit_code"] == 0 and hashlib.sha256(log.read_bytes()).hexdigest() == record["log_sha256"]
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=CLONE, text=True)
    assert not status
    write("clone-integrity.json", dict(
        status="PASS", source_head=HEAD, frozen_cp4_delivery_files=len(verified), files=verified,
        explicit_clone_eol_mapping=eol, cp4_gate_logs_verified=True, cp4_artifact_sha256=hashes(candidate),
        sample_after=hashes(CLONE / "datasets/samples/m6_synthetic"), tracked_status=status,
        external_replay="Not rerun in CP5; retained CP4 full879/0skip with actual external M1 data",
    ))
    print(f"Clone integrity PASS: {len(verified)} CP4 files; known LF mapping explicit; clean tracked tree")
