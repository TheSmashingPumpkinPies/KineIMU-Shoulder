"""CP4 stage D: full immutable M1 dual USB replay. Development only; CP4 OPEN."""

from __future__ import annotations

import argparse
import os
import platform
import re
import subprocess
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from kineimu_shoulder.io.m1_packet import NodeId
from kineimu_shoulder.relative_orientation import SegmentOrientationStream
from kineimu_shoulder.summary import SummaryContext
from kineimu_shoulder.validation.baseline import CONFIG, ROOT, canonical, plain
from kineimu_shoulder.validation.recorded_node import run_node
from kineimu_shoulder.validation.replay import ReplayInput, _protect, adapter_config, gate_report

# Immutable M1 manifest and independent M2 bench tests / M5.4 plan.
MANIFEST_SHA256 = "219a7a2cf07eb962ee3bf4755dc0a49d4ccf48447bb27be1edc08d55f5529ea7"
MEMBERS = {"dual_usb_bench_result.json", "run_config.json", "summary.json"} | {
    f"raw/node-{node}.{suffix}" for node in "ab"
    for suffix in ("events.ndjson", "kimu", "preroll.usb.bin", "usb.bin")
}


def m1_inputs(root: Path) -> tuple[ReplayInput, ...]:
    return (
        ReplayInput("M1-A", root / "raw/node-a.kimu",
            "9e929d0ac025ea3b7322c3a48668e5f21c83fd7372ba920709c18f124f328db5",
            NodeId.A, 46943, 187772, (14933068145, 16733174774)),
        ReplayInput("M1-B", root / "raw/node-b.kimu",
            "0ae3f1aa712b915bf5b0f4381cb2391b3619d41bbbc2fe81152f5d32c0e5bc68",
            NodeId.B, 47856, 191424, (14900951232, 16701005981)),
    )


def verify_manifest(root: Path, expected_sha256: str = MANIFEST_SHA256) -> dict[str, Any]:
    """Read-only strict eleven-member manifest check; exceptions remain explicit."""
    raw = (root / "SHA256SUMS.txt").read_bytes()
    digest = sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("external manifest hash mismatch")
    listed: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ValueError("malformed external manifest")
        value, name = match.groups()
        path = root / name
        if (name not in MEMBERS or name in listed or not path.resolve().is_relative_to(root.resolve())
            or path.is_symlink()):
            raise ValueError("duplicate, unexpected or unsafe external manifest member")
        actual = sha256(path.read_bytes()).hexdigest()
        if actual != value:
            raise ValueError(f"external member hash mismatch: {name}")
        listed[name] = actual
    if set(listed) != MEMBERS:
        raise ValueError("external manifest must contain all eleven members")
    if sha256((root / "SHA256SUMS.txt").read_bytes()).hexdigest() != digest:
        raise ValueError("external manifest changed during inspection")
    return dict(disposition="PASSED", manifest_sha256=digest, file_sha256=listed)


def _manifest_check(root: Path, digest: str) -> dict[str, Any]:
    try:
        return verify_manifest(root, digest)
    except (FileNotFoundError, PermissionError) as exc:
        return dict(disposition="BLOCKED", error_type=type(exc).__name__)
    except (OSError, ValueError, UnicodeError) as exc:
        return dict(disposition="FAILED", error_type=type(exc).__name__, reason=str(exc))


def dual_gates(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Actual A/B inputs on separate worlds/clocks, no anatomical transform.

    Request rejection on A's original timestamps solely as diagnostic support;
    these are NOT an established common grid. Missing clock gates precede any
    interpolation/composition, so q_WN cannot be misused as q_WSegment.
    """
    streams = []
    probe_segments = []
    for result in results:
        node = result["node_id"]
        epoch = result["epochs"][0]
        start, stop, world = 0, len(epoch["device_time_us"]), f"M1-{node}-independent-world"
        if "processing" in epoch:
            segment = epoch["processing"]["segments"][0]
            start, stop, world = segment["start_index"], segment["stop_index"], segment["world_id"]
            probe_segments.append(dict(node_id=node, **segment))
        streams.append(SegmentOrientationStream(node, f"M1-{node}-device-clock", epoch["clock_epoch"],
            world, result["source_sha256_before"],
            np.asarray(epoch["device_time_us"][start:stop], dtype=np.int64),
            np.asarray(epoch["orientation"]["quaternion_wn"][start:stop], dtype=np.float64)))
    missing = sha256(b"absent alignment; no anatomical artifact").hexdigest()
    context = SummaryContext(None, tuple(r["calibration"]["calibration_id"] for r in results),
        (missing, missing), ("imufusion", version("imufusion"), CONFIG.sha256),
        ("unestablished; rejection probe on original A times", "no clock map or resampling"), None)
    support = np.asarray(results[0]["epochs"][0]["device_time_us"], dtype=np.int64)
    gates = gate_report(thorax=streams[0], humerus=streams[1], common_time_us=support,
        thorax_clock_map=None, humerus_clock_map=None, heading_relation=None,
        thorax_alignment=None, humerus_alignment=None, heading_evidence=None, drift_evidence=None,
        context=context, calibration_sha256=(results[0]["calibration_sha256"], results[1]["calibration_sha256"]),
        source_type="recorded", side="left", exercise="flexion")
    if (any(gates["relative"]["valid"]) or any(gates["elevation"]["valid"])
        or any(gates["speed"]["valid"]) or gates["summary"]["analysis_valid"]
        or gates["summary"]["valid_count"] is not None
        or set(gates["relative"]["reason"]) != {"clock_map_missing"}
        or set(gates["elevation"]["reason"]) != {"clock_or_heading_missing"}):
        raise ValueError("dual recorded missing-evidence rejection failed")
    report = dict(stage_disposition="EXECUTED-UNAVAILABLE", valid=False, value=None,
        reason="missing_pairwise_clock_heading_alignment_drift_evidence", observed_node_ids=["A", "B"],
        common_grid_established=False, probe_kind="dual-node rejection on original A timestamp support",
        diagnostic_side_exercise="left/flexion interface parameters only; no observed task/side claim",
        input_frames="independent q_WN; no R_NK or established q_WSegment; rejection only",
        missing_evidence=["clock_map_missing", "heading_missing", "alignment_missing",
                          "thorax_heading_missing", "thorax_drift_unbounded"], gates=gates)
    if probe_segments:
        report["probe_segments"] = probe_segments
        report["probe_scope"] = "first eligible contiguous processing world per node; full A rejection support"
    return report


def export_dual(output: Path, *, root: Path, inputs: tuple[ReplayInput, ...] | None = None,
                manifest_sha256: str = MANIFEST_SHA256, segmented: bool = False) -> int:
    """Claim fresh root, retain full/partial products and full pre/post manifest."""
    root, output = root.resolve(), output.resolve()
    selected = m1_inputs(root) if inputs is None else inputs
    _protect(output, selected)
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("output must be outside the entire external acquisition root")
    if len(selected) != 2 or [r.node_id for r in selected] != [NodeId.A, NodeId.B]:
        raise ValueError("stage D requires A and B independently identified in that order")
    if any(r.path.resolve() != root / f"raw/node-{r.node_id.name.lower()}.kimu" for r in selected):
        raise ValueError("inputs must be bound to manifest members")
    files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "kineimu_shoulder").rglob("*.py"))
    files += ["uv.lock", "pyproject.toml", "protocols/M5_VALIDATION_CONTRACT.md",
              "protocols/M5_PROCESSING_V1_1.md", "protocols/M5_VALIDATION_CONTRACT.md",
              "docs/validation/acquisition.md",
              "tests/integration/test_m5_recorded_dual.py", "tests/integration/test_m2_replay_m1_bench.py",
              "validation/auditors/recorded_dual.py"]
    if segmented:
        files += ["protocols/M5_RECORDED_SEGMENTS_V1.md", "protocols/M2_PROCESSING_CONTRACT.md",
                  "docs/adr/ADR-011-recorded-quality-segments.md",
                  "tests/integration/test_m5_recorded_segments.py", "validation/auditors/recorded_segments.py"]
    manifest = dict(schema_version="m5-report/1.0", checkpoint="CP4", stage="D-recorded-dual-USB", formal=False,
        git_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        tracked_dirty=bool(subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True).strip()),
        source_file_sha256={n: sha256((ROOT/n).read_bytes()).hexdigest() for n in files},
        runtime=dict(python=platform.python_version(), platform=platform.platform(),
            packages={n: version(n) for n in ("numpy", "scipy", "imufusion", "imucal")},
            thread_environment={n: os.environ.get(n) for n in
                                ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}),
        case_ids=[r.case_id for r in selected], external_manifest_sha256=manifest_sha256,
        input_anchors=[dict(id=r.case_id, node_id=r.node_id.name, sha256=r.sha256,
            packets=r.expected_packets, samples=r.expected_samples, endpoints_us=r.expected_endpoints_us)
            for r in selected], configuration=plain(adapter_config()), max_gap_s=.05,
        initial_quaternion_wn=[1., 0., 0., 0.],
        processing="original sensor SI -> example identity calibration/R_NS -> independent pinned node AHRS",
        processing_version="m5-processing/1.1; original-only recorded path; reconstruction not applied",
        units=dict(time="us", acceleration="m/s^2", angular_rate="rad/s", orientation="active q_WN wxyz"))
    if segmented:
        manifest.update(processing="original SI -> explicit quality partition -> original calibration/R_NS "
                        "and fresh pinned AHRS per eligible contiguous interval; rejected rows null",
                        processing_version="m5-recorded-segments/1.0", segmented=True)
    output.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}

    def write(name: str, value: Any) -> None:
        content = canonical(value)
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
        hashes[name] = sha256(content).hexdigest()

    write("manifest.json", manifest)
    before = _manifest_check(root, manifest_sha256)
    summaries = []
    downstream: dict[str, Any] = dict(stage_disposition="NOT RUN", value=None, valid=False,
                                     reason="required_node_or_manifest_not_completed")
    try:
        if before["disposition"] == "PASSED":
            results = []
            for row in selected:
                result = run_node(row, segmented=True) if segmented else run_node(row)
                name = f"cases/{row.case_id}/result.json"
                write(name, result)
                summaries.append(dict(id=row.case_id, disposition=result["stage_disposition"],
                    passed=result["passed"], failed_gates=result["failed_gates"], path=name, sha256=hashes[name]))
                results.append(result)
            if all(r["passed"] for r in results):
                downstream = dual_gates(results)
        else:
            summaries = [dict(id=r.case_id, disposition=before["disposition"], passed=False,
                              failed_gates=["external-manifest"]) for r in selected]
    except Exception as exc:
        downstream.update(stage_disposition="FAILED", error_type=type(exc).__name__)
    after = _manifest_check(root, manifest_sha256)
    passed = (before == after and before["disposition"] == "PASSED" and len(summaries) == 2
              and all(r["passed"] for r in summaries) and downstream["stage_disposition"] == "EXECUTED-UNAVAILABLE")
    blocked = (before["disposition"] == "BLOCKED" or after["disposition"] == "BLOCKED"
               or any(r["disposition"] == "BLOCKED" for r in summaries))
    write("downstream.json", downstream)
    write("report.json", dict(schema_version="m5-report/1.0", checkpoint="CP4", checkpoint_disposition="OPEN",
        passed=False, stage_passed=passed, remaining_stages=["E"], case_count=2, results=summaries,
        manifest_before=before, manifest_after=after, blocked_count=2 if blocked else 0,
        failed_case_count=0 if passed or blocked else max(1, sum(not r["passed"] for r in summaries)),
        not_run_count=2 if before["disposition"] != "PASSED" else sum("path" not in r for r in summaries),
        artifact_disposition="complete-stage-D" if passed else "partial",
        evidence_index={r["id"]: dict(path=r["path"], sha256=r["sha256"]) for r in summaries if "path" in r},
        downstream_evidence=dict(path="downstream.json", sha256=hashes["downstream.json"]),
        requirement_index={n: [r.case_id for r in selected] for n in
                           ("immutable-eleven-member-manifest", "complete-node-AHRS", "downstream-unavailable")},
        limitations=["Development D only; formal two-process B/C/D stage E required for CP4 acceptance.",
                     "Identity example calibration; independent yaw, no common time/heading or anatomical transform.",
                     "No motion truth, shoulder accuracy or clinical validation from the M1 bench."]))
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write("".join(f"{hashes[n]}  {n}\n" for n in sorted(hashes)).encode())
    return 0 if passed else 2 if blocked else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--segmented", action="store_true", help="explicit ADR-011 quality partition and AHRS reset")
    args = parser.parse_args()
    root = os.environ.get("KINEIMU_M1_RAW_ROOT")
    if root is None:
        parser.error("set KINEIMU_M1_RAW_ROOT to the immutable external M1 root")
    try:
        status = export_dual(args.output, root=Path(root), segmented=args.segmented)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    raise SystemExit(status)


if __name__ == "__main__":
    main()
