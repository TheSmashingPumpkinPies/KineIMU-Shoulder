"""CP4 stage C: complete immutable Node B replay and explicit rejection probe.

Node q_WN is Assumed/Experimental. The downstream self-input probe supplies
the same B stream twice solely to exercise missing-evidence interfaces, with
no maps/heading/alignments. It is not a paired or anatomically aligned stream.
Exit 0 delivers this development stage only; CP4 remains OPEN until stage E.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from kineimu_shoulder.calibration import CalibrationArtifact, apply_calibration
from kineimu_shoulder.io.m1_packet import NodeId
from kineimu_shoulder.io.m2_replay import replay_capture
from kineimu_shoulder.orientation import estimate_orientation
from kineimu_shoulder.relative_orientation import SegmentOrientationStream
from kineimu_shoulder.summary import SummaryContext
from kineimu_shoulder.validation.baseline import CONFIG, ROOT, canonical, plain
from kineimu_shoulder.validation.replay import ReplayInput, _protect, adapter_config, gate_report

# Independent anchors: node_b_20260913_compatibility.md, M2 replay test, M5.4 plan.
NODE_B = ReplayInput(
    "REC-NODE-B", ROOT / "firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary.kimu",
    "1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201",
    NodeId.B, 208, 832, (257030578, 264845581), "recorded",
)


def identity_calibration(row: ReplayInput) -> CalibrationArtifact:
    """Same no-fit example contract as M2.5; (0,1) is a schema placeholder."""
    return CalibrationArtifact(
        calibration_id=f"cp4-example-identity-{row.node_id.name}", node_id=row.node_id,
        sensor_id="LSM6DS3TR-C", config=adapter_config(),
        accel_matrix=((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)),
        accel_bias_mps2=(0., 0., 0.), gyro_bias_rads=(0., 0., 0.),
        fit_method="illustrative_identity_no_fit", fit_window_us=(0, 1), source_sha256=(row.sha256.lower(),),
        validity="Example only; no physical fit, measured uncertainty or calibration accuracy claim",
    )


def run_recorded(row: ReplayInput) -> dict[str, Any]:
    """Stage C single-B rejection probe, preserving its original contract."""
    return _run_recorded(row, single_b_probe=True)


def run_node(row: ReplayInput, *, segmented: bool = False) -> dict[str, Any]:
    """Complete independent recorded node AHRS; no downstream pair is inferred."""
    return _run_recorded(row, single_b_probe=False, segmented=segmented)


def _run_recorded(row: ReplayInput, *, single_b_probe: bool, segmented: bool = False) -> dict[str, Any]:
    """Read all original observations; retain partial evidence on any failure."""
    result: dict[str, Any] = dict(
        id=row.case_id, node_id=row.node_id.name, source_type=row.source_type,
        expected_source_sha256=row.sha256.lower(), source_sha256_before=None, source_sha256_after=None,
        expected_packets=row.expected_packets, expected_samples=row.expected_samples,
        expected_endpoints_us=list(row.expected_endpoints_us), stage_disposition="FAILED", passed=False,
        failed_gates=[], failed_stage="input", epochs=[], qc=None,
        downstream=dict(stage_disposition="NOT RUN", value=None, valid=False, reason="node_replay_not_completed"),
        evidence_label="Assumed/Experimental", anatomical_eligible=False,
        reconstruction="NOT APPLIED; original observations only",
        motion_accuracy=dict(value=None, valid=False, reason="no_motion_ground_truth"),
        assumptions=["identity calibration with zero bias; not fitted to this capture",
                     "fit_window_us=(0,1) is a schema placeholder, not fit evidence",
                     "sensor-to-node R_NS identity; no anatomical R_NK is applied",
                     "initial q_WN=(1,0,0,0) defines an independent arbitrary world",
                     "six-axis static gravity does not establish yaw, AP/ML or common heading",
                     "no measured uncertainty, motion truth, anatomical or clinical validation"],
    )
    try:
        if row.source_type != "recorded" or (single_b_probe and row.node_id != NodeId.B):
            raise ValueError("stage C requires recorded Node B")
        result["source_sha256_before"] = sha256(row.path.read_bytes()).hexdigest()
        replay = replay_capture(row.path, expected_sha256=row.sha256, expected_node_id=row.node_id,
                                config=adapter_config())
        result["qc"] = plain(replay.qc)
        result["epochs"] = [dict(
            clock_epoch=e.clock_epoch, packet_sequences=list(e.packet_sequences), packet_flags=plain(e.packet_flags),
            host_monotonic_ns=list(e.host_monotonic_ns), device_time_us=list(e.sensor_data.device_time_us),
            sample_sequences=list(e.sensor_data.sample_sequences), sample_flags=plain(e.sensor_data.sample_flags),
            sensor_acceleration_mps2=plain(e.sensor_data.accel_mps2),
            sensor_angular_rate_rads=plain(e.sensor_data.gyro_rads),
        ) for e in replay.epochs]
        for name, actual, expected in (
            ("packet_count", replay.qc.packets_decoded, row.expected_packets),
            ("sample_count", replay.qc.samples_decoded, row.expected_samples),
            ("epoch_count", len(replay.epochs), 1),
            ("endpoints", (replay.epochs[0].sensor_data.device_time_us[0],
                           replay.epochs[-1].sensor_data.device_time_us[-1]), row.expected_endpoints_us),
        ):
            if actual != expected:
                result["failed_gates"].append(name)
        if replay.qc.issues:
            result["failed_gates"].append("qc")
        if result["failed_gates"]:
            return result
        artifact = identity_calibration(row)
        calibration_hash = sha256(artifact.to_json().encode()).hexdigest()
        result["calibration"] = json.loads(artifact.to_json())
        result["calibration_sha256"] = calibration_hash
        epoch = replay.epochs[0]
        data = epoch.sensor_data
        result["failed_stage"] = "calibration"
        if segmented:
            from kineimu_shoulder.validation.recorded_segments import CONTRACT, process_segments

            result["processing_contract"] = CONTRACT
            processed = process_segments(np.asarray(data.device_time_us, dtype=np.int64),
                data.accel_mps2, data.gyro_rads, data.sample_flags, artifact=artifact)
            result["epochs"][0].update(processed)
            if not processed["processing"]["segments"]:
                raise ValueError("no eligible recorded observation for node AHRS")
            result["assumptions"].append("fresh independent world per eligible interval; no cross-segment continuity")
            result.update(stage_disposition="PASSED", passed=True, failed_stage=None)
            result["downstream"] = dict(stage_disposition="DEFERRED-TO-DUAL-REPORT", value=None,
                valid=False, reason="independent_processing_worlds_not_anatomically_aligned")
            return result
        node_acc, node_rate = apply_calibration(
            data.accel_mps2, data.gyro_rads, artifact=artifact, node_id=row.node_id,
            sensor_id=artifact.sensor_id, config=replay.config, sample_flags=data.sample_flags,
        )
        times = np.asarray(data.device_time_us, dtype=np.int64)
        result["epochs"][0].update(node_acceleration_mps2=plain(node_acc), node_angular_rate_rads=plain(node_rate))
        result["failed_stage"] = "orientation"
        orientation = estimate_orientation(times, node_acc, node_rate, max_gap_s=.05)
        if (not np.array_equal(orientation.timestamp_us, times)
            or orientation.quaternion_wn.shape != (len(times), 4)
            or not bool(np.isfinite(orientation.quaternion_wn).all())
            or not bool(np.allclose(np.linalg.norm(orientation.quaternion_wn, axis=1), 1., rtol=0, atol=1e-12))
            or orientation.heading_observable):
            raise ValueError("complete orientation/support/unobserved-heading gate failed")
        result["epochs"][0]["orientation"] = plain(orientation)
        if not single_b_probe:
            result.update(stage_disposition="PASSED", passed=True, failed_stage=None)
            result["downstream"] = dict(stage_disposition="DEFERRED-TO-DUAL-REPORT", value=None,
                                        valid=False, reason="independent_node_not_anatomically_aligned")
            return result
        # No phantom A, identity clock map, segment transform or shared world.
        # This is an explicitly named rejection-only probe, not a dual-node analysis.
        stream = SegmentOrientationStream("B", "recorded-B-device-clock", epoch.clock_epoch,
            "recorded-B-independent-world", replay.source_sha256, times, orientation.quaternion_wn)
        missing_hash = sha256(b"absent alignment / calibration; no artifact").hexdigest()
        context = SummaryContext(None, ("absent-thorax-calibration", artifact.calibration_id),
            (missing_hash, missing_hash), ("imufusion", version("imufusion"), CONFIG.sha256),
            ("unestablished; rejection probe on original B times", "no clock map or resampling"), None)
        result["failed_stage"] = "downstream"
        gates = gate_report(
            thorax=stream, humerus=stream, common_time_us=times,
            thorax_clock_map=None, humerus_clock_map=None, heading_relation=None,
            thorax_alignment=None, humerus_alignment=None, heading_evidence=None, drift_evidence=None,
            context=context, calibration_sha256=(missing_hash, calibration_hash),
            source_type="recorded", side="left", exercise="flexion",
        )
        result["downstream"] = dict(
            stage_disposition="EXECUTED-UNAVAILABLE", value=None, valid=False,
            reason="single_node_missing_pair_and_evidence",
            probe_kind="single-node self-input rejection probe; no paired/aligned stream",
            observed_node_ids=["B"], common_grid_established=False,
            diagnostic_side_exercise="left/flexion interface parameters only; no observed task/side claim",
            source_bindings="both gate slots reference B solely for rejection; no A source exists",
            missing_evidence=["thorax_node_missing", "clock_map_missing", "heading_missing", "alignment_missing",
                              "thorax_trace_missing", "thorax_heading_missing", "thorax_drift_unbounded"],
            gates=gates,
        )
        if (any(gates["relative"]["valid"]) or any(gates["elevation"]["valid"])
            or any(gates["speed"]["valid"]) or gates["summary"]["analysis_valid"]
            or gates["summary"]["valid_count"] is not None
            or set(gates["relative"]["reason"]) != {"clock_map_missing"}
            or set(gates["elevation"]["reason"]) != {"clock_or_heading_missing"}):
            raise ValueError("recorded missing-evidence rejection gate failed")
        result.update(stage_disposition="PASSED", passed=True, failed_stage=None)
    except (FileNotFoundError, PermissionError) as exc:
        result.update(stage_disposition="BLOCKED", error_type=type(exc).__name__, passed=False)
    except Exception as exc:
        result.update(stage_disposition="FAILED", passed=False, error_type=type(exc).__name__)
        result["failed_gates"].append(f"{result['failed_stage']}_error")
    finally:
        if result["source_sha256_before"] is not None:
            try:
                result["source_sha256_after"] = sha256(row.path.read_bytes()).hexdigest()
                if result["source_sha256_after"] != result["source_sha256_before"]:
                    result["failed_gates"].append("source_changed")
                    result.update(stage_disposition="FAILED", passed=False, failed_stage="immutable-input")
            except (FileNotFoundError, PermissionError) as exc:
                result.update(stage_disposition="BLOCKED", error_type=type(exc).__name__, passed=False)
    return result


def export_recorded(output: Path, *, selected: ReplayInput = NODE_B) -> int:
    """Claim a fresh C development root. Preserve failure/blocked partials."""
    output = output.resolve()
    _protect(output, (selected,))

    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "kineimu_shoulder").rglob("*.py"))
    files += ["uv.lock", "pyproject.toml", "protocols/M5_VALIDATION_CONTRACT.md", "protocols/M5_PROCESSING_V1_1.md",
              "tests/fixtures/M5_KNOWN_SENSOR_MOTIONS.md", "experiments/M5_CP1_20260926/case-manifest.json",
              "tests/integration/test_m5_recorded_node.py", "M5_4_REPLAY_PLAN.md", "docs/M5_RECORDED_NODE.md",
              "experiments/M5_CP4_STAGE_C_20260927/audit.py",
              "firmware/xiao_nrf52840_sense/evidence/node_b_20260913_compatibility.md"]
    manifest = dict(
        schema_version="m5-report/1.0", checkpoint="CP4", stage="C-recorded-node-B", formal=False,
        git_commit=git("rev-parse", "HEAD"), tracked_dirty=bool(git("status", "--porcelain", "--untracked-files=no")),
        source_file_sha256={name: sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
        runtime=dict(python=platform.python_version(), platform=platform.platform(),
            packages={name: version(name) for name in ("numpy", "scipy", "imufusion", "imucal")},
            thread_environment={name: os.environ.get(name) for name in
                                ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}),
        case_ids=[selected.case_id], input_anchors=[dict(id=selected.case_id, source_name=selected.path.name,
            sha256=selected.sha256.lower(), node_id=selected.node_id.name, source_type=selected.source_type,
            packets=selected.expected_packets, samples=selected.expected_samples,
            endpoints_us=selected.expected_endpoints_us)],
        configuration=plain(adapter_config()),
        processing="complete original sensor SI -> example calibration/R_NS -> pinned independent node AHRS",
        processing_version="m5-processing/1.1; original-only recorded path; reconstruction not applied",
        max_gap_s=.05, initial_quaternion_wn=[1., 0., 0., 0.],
        units=dict(time="us", acceleration="m/s^2", angular_rate="rad/s", orientation="active q_WN wxyz"),
    )
    output.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}

    def write(name: str, value: Any) -> None:
        content = canonical(value)
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
        hashes[name] = sha256(content).hexdigest()

    write("manifest.json", manifest)
    result = run_recorded(selected)
    name = f"cases/{selected.case_id}/result.json"
    write(name, result)
    status = result["stage_disposition"]
    write("report.json", dict(
        schema_version="m5-report/1.0", checkpoint="CP4", checkpoint_disposition="OPEN", passed=False,
        stage_passed=result["passed"], case_count=1, failed_case_count=int(status == "FAILED"),
        blocked_count=int(status == "BLOCKED"), not_run_count=int(status == "BLOCKED"), remaining_stages=["D", "E"],
        results=[dict(id=selected.case_id, disposition=status, passed=result["passed"],
                      failed_gates=result["failed_gates"], path=name, sha256=hashes[name])],
        artifact_disposition="complete-stage-C" if result["passed"] else "partial",
        evidence_index={selected.case_id: dict(path=name, sha256=hashes[name])},
        requirement_index={r: [selected.case_id] for r in
                           ("immutable-input/QC", "complete-node-AHRS", "explicit-assumptions",
                            "downstream-unavailable")},
        limitations=["Development stage C only; D/E are required for CP4 acceptance.",
                     "No paired stream/common grid or segment alignment; rejection-only self-input gate probe.",
                     "Identity example and independent arbitrary yaw; no motion accuracy or anatomical validation."],
    ))
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write("".join(f"{hashes[n]}  {n}\n" for n in sorted(hashes)).encode())
    return 1 if status == "FAILED" else 2 if status == "BLOCKED" else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        status = export_recorded(args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    raise SystemExit(status)


if __name__ == "__main__":
    main()
