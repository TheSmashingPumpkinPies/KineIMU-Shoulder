"""CP4 E: fresh formal collection of unchanged B/C/segmented-D processors.

Subreports retain their development semantics. Only the separate pair auditor
can accept CP4; a successful collection alone leaves the checkpoint OPEN.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Any

from kineimu_shoulder.validation.baseline import canonical
from kineimu_shoulder.validation.recorded_dual import export_dual, verify_manifest
from kineimu_shoulder.validation.recorded_node import NODE_B, export_recorded
from kineimu_shoulder.validation.stored_demo import CP1_ROOT, export_stored, input_audit

ROOT = Path(__file__).resolve().parents[2]
STAGE_PRODUCTS = {
    "B": {"manifest.json", "report.json"} | {
        f"cases/Q-{t}/{name}" for t in ("F90", "AL90", "AR90", "T-MIX")
        for name in ("result.json", "processed.json.gz", "derived.json.gz", "annotations.json.gz", "errors.json.gz")},
    "C": {"manifest.json", "report.json", "cases/REC-NODE-B/result.json"},
    "D": {"manifest.json", "report.json", "downstream.json", "cases/M1-A/result.json", "cases/M1-B/result.json"},
}
COLLECTION_PRODUCTS = {"manifest.json", "report.json"} | {
    f"{stage}/{name}" for stage, names in STAGE_PRODUCTS.items() for name in names | {"SHA256SUMS.txt"}}


def inventory(root: Path, expected: set[str]) -> dict[str, str]:
    """Verify manifest bytes, required support and absence of unlisted files."""
    found = {}
    for line in (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ")
        path = root / name
        if (name in found or name not in expected or len(digest) != 64
            or not path.resolve().is_relative_to(root.resolve())):
            raise ValueError("unsafe, duplicate or unexpected inventory entry")
        if sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"modified product bytes: {name}")
        found[name] = digest
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if set(found) != expected or actual != expected | {"SHA256SUMS.txt"}:
        raise ValueError("incomplete inventory or unlisted product")
    return found


def compare_pair(one: Path, two: Path, expected: set[str], process_ids: list[int]) -> dict[str, Any]:
    if one.resolve() == two.resolve():
        raise ValueError("distinct output roots required")
    if len(process_ids) != 2 or len(set(process_ids)) != 2 or any(p <= 0 for p in process_ids):
        raise ValueError("two independent process IDs required")
    maps = [inventory(p, expected) for p in (one, two)]
    if maps[0] != maps[1] or any((one/n).read_bytes() != (two/n).read_bytes()
                                for n in expected | {"SHA256SUMS.txt"}):
        raise ValueError("canonical bytes differ between independent collections")
    return dict(canonical_equal=True, canonical_products=len(expected), product_sha256=maps[0])


def protect_output(output: Path, sources: list[Path]) -> None:
    output = output.resolve()
    if output.exists() or any(output.is_relative_to(p.resolve()) or p.resolve().is_relative_to(output)
                              for p in sources):
        raise ValueError("fresh output outside immutable input roots required")


def input_snapshot(external: Path) -> dict[str, Any]:
    node = NODE_B
    digest = sha256(node.path.read_bytes()).hexdigest()
    if digest != node.sha256:
        raise ValueError("original retained Node B hash mismatch")
    return dict(stored_q=input_audit(CP1_ROOT), retained_node_b=digest,
                external=verify_manifest(external))


def assemble_stage(exporter: Callable[..., int], output: Path, staging: Path, **kwargs: Any) -> int:
    """Preserve the existing exporter guard; move only a fresh owned stage."""
    if output.exists() or staging.exists():
        raise ValueError("fresh stage and assembly destination required")
    staging.parent.mkdir(parents=True, exist_ok=True)
    status = exporter(staging, **kwargs)
    # Both paths are explicit, fresh stage locations. Neither operation changes
    # an input or a pre-existing evidence tree; the E envelope owns output.
    staging.rename(output)
    return status


def export_collection(output: Path, external: Path, operation: Path) -> int:
    protect_output(output, [external, CP1_ROOT, NODE_B.path.parent])
    if operation.exists() or operation.resolve().is_relative_to(output.resolve()):
        raise ValueError("fresh operational record outside canonical collection required")
    lock = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT).strip():
        raise ValueError("clean committed source lock required")
    before = input_snapshot(external)
    output.mkdir(parents=True, exist_ok=False)
    staging = Path(tempfile.mkdtemp(prefix=".tmp-m54-e-assembly-", dir=ROOT))
    operation.parent.mkdir(parents=True, exist_ok=True)
    # Runtime identity is operational, never part of canonical numerical bytes.
    with operation.open("xb") as stream:
        stream.write(canonical(dict(pid=os.getpid(), source_lock=lock,
                                    output=str(output.resolve()), staging=str(staging), tracked_dirty=False)))
    statuses = {}
    statuses["B"] = assemble_stage(export_stored, output / "B", staging / "B")
    statuses["C"] = assemble_stage(export_recorded, output / "C", staging / "C")
    statuses["D"] = assemble_stage(export_dual, output / "D", staging / "D", root=external, segmented=True)
    after = input_snapshot(external)
    sources: dict[str, str] = {}
    stages = {}
    for stage, names in STAGE_PRODUCTS.items():
        stages[stage] = inventory(output / stage, names)
        manifest = json.loads((output / stage / "manifest.json").read_bytes())
        if manifest["git_commit"] != lock or manifest["tracked_dirty"]:
            raise ValueError("subprocessor source lock mismatch")
        for name, digest in manifest["source_file_sha256"].items():
            if name in sources and sources[name] != digest:
                raise ValueError("inconsistent source map")
            sources[name] = digest
    for name in ("kineimu_shoulder/validation/formal_replay.py", "tests/integration/test_m5_formal_replay.py",
                 "experiments/M5_CP4_STAGE_E_20260927/audit.py", "experiments/M5_CP4_STAGE_E_20260927/launch.py",
                 "experiments/M5_CP4_STAGE_E2_20260928/audit.py", "experiments/M5_CP4_STAGE_E2_20260928/launch.py",
                 "docs/M5_FORMAL_REPLAY_E2.md",
                 "docs/M5_FORMAL_REPLAY.md", "pyproject.toml"):
        sources[name] = sha256((ROOT/name).read_bytes()).hexdigest()
    complete = all(status == 0 for status in statuses.values()) and before == after
    manifest = dict(schema_version="m5-report/1.0", checkpoint="CP4", stage="E-formal-B-C-D", formal=True,
        git_commit=lock, tracked_dirty=False, source_file_sha256=sources,
        runtime=json.loads((output / "D/manifest.json").read_bytes())["runtime"],
        stages=list(STAGE_PRODUCTS), recorded_processing_version="m5-recorded-segments/1.0",
        input_before=before, input_after=after, stage_product_sha256=stages,
        subreport_semantics="unchanged B/C/D development processors; E is the formal collection envelope")
    report = dict(schema_version="m5-report/1.0", checkpoint="CP4", checkpoint_disposition="OPEN",
        passed=False, collection_complete=complete, stage_exit_codes=statuses,
        required_case_count=7, required_stages=["B", "C", "D"],
        artifact_disposition="complete-formal-collection" if complete else "partial",
        next_gate="separate two-process byte equality and independent full B/C/D audits",
        limitations=["Recorded shoulder outputs unavailable; independent worlds and example calibration.",
                     "No anatomical/clinical accuracy claim; CP5 and overall M5 remain OPEN."])
    for name, value in (("manifest.json", manifest), ("report.json", report)):
        with (output/name).open("xb") as stream:
            stream.write(canonical(value))
    hashes = {name: sha256((output/name).read_bytes()).hexdigest() for name in sorted(COLLECTION_PRODUCTS)}
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in hashes.items()).encode())
    return 0 if complete else 2 if 2 in statuses.values() else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--operation", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(export_collection(args.output, args.root, args.operation))


if __name__ == "__main__":
    main()
