"""CP4 stage B: complete immutable CP1 Q replay; development evidence only.

Measurements come exclusively from decoded KIMU files. Frozen metadata supplies
explicit synthetic transforms, initialization and clocks; independent O/F/T
labels supply expectations. No generator or packet writer executes this path.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import platform
import subprocess
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import numpy as np

from kineimu_shoulder.io.m1_packet import NodeId
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorToNodeTransform
from kineimu_shoulder.io.m2_replay import replay_capture
from kineimu_shoulder.validation.baseline import ROOT, canonical, plain
from kineimu_shoulder.validation.perturbation import _session
from kineimu_shoulder.validation.replay import ReplayInput, _protect
from kineimu_shoulder.validation.source import DualSource, NodeSource, Perturbation

CP1_ROOT = ROOT / "datasets/samples/m6_synthetic"
# Committed CP1 digest map, anchored independently of caller-selected files.
CP1_MAP_SHA256 = "2aa180e32003f91e57accf1d53c5b4b914e0c9e9c0ab4cdb22db02a3ab0964f9"
TRAJECTORIES = ("F90", "AL90", "AR90", "T-MIX")


def input_audit(input_root: Path) -> dict[str, str]:
    """Bind raw, metadata, observation references and labels to retained CP1."""
    content = (input_root / "SHA256SUMS.json").read_bytes()
    if sha256(content).hexdigest() != CP1_MAP_SHA256:
        raise ValueError("CP1 digest map changed")
    frozen = json.loads(content)
    names = ["annotations.json", "observation-labels.json", "case-manifest.json", "manifest.json"]
    names += [f"{t}/{n}" for t in TRAJECTORIES
              for n in ("A.kimu", "B.kimu", "metadata.json", "A-si.json", "B-si.json")]
    actual = {name: sha256((input_root / name).read_bytes()).hexdigest() for name in names}
    for name, value in actual.items():
        if value != frozen[name]:
            raise ValueError(f"CP1 input digest mismatch: {name}")
    return {"SHA256SUMS.json": CP1_MAP_SHA256, **actual}


def run_stored(trajectory: str, workspace: Path, *, input_root: Path = CP1_ROOT) -> dict[str, Any]:
    """Read all 2151 samples per node and execute the existing processing/1.1 chain."""
    if trajectory not in TRAJECTORIES:
        raise ValueError("unknown stored Q trajectory")
    before = input_audit(input_root)
    metadata = json.loads((input_root / trajectory / "metadata.json").read_bytes())
    references = json.loads((input_root / "annotations.json").read_bytes())[trajectory]
    frozen_cases = json.loads((input_root / "case-manifest.json").read_bytes())
    # CP1 stores the complete frozen expansion as a list.
    case = next(c for c in frozen_cases if c["id"] == f"{trajectory}/CLEAN-Q/SAME/0")
    nodes = {}
    captures = {}
    quantization = {}
    for node in ("A", "B"):
        meta = metadata["nodes"][node]
        observed = json.loads((input_root / trajectory / f"{node}-si.json").read_bytes())
        config = M1RawCountAdapterConfig(4, 500, .122, 17.5, SensorToNodeTransform(
            ("SX", "SY", "SZ"), ("NX", "NY", "NZ"),
            cast(tuple[tuple[float, float, float], ...],
                 tuple(tuple(float(x) for x in row) for row in meta["R_NS"])),
            "frozen CP1 R_NS; node=R_NS sensor",
        ))
        capture = input_root / trajectory / f"{node}.kimu"
        raw_hash = before[f"{trajectory}/{node}.kimu"]
        replay = replay_capture(capture, expected_sha256=raw_hash, expected_node_id=NodeId[node], config=config)
        data = replay.epochs[0].sensor_data
        if (len(replay.epochs) != 1 or replay.qc.issues or replay.qc.packets_decoded != 538
            or replay.qc.samples_decoded != 2151 or meta["sample_count"] != 2151
            or tuple(data.device_time_us) != tuple(observed["device_time_us"])
            or (data.device_time_us[0], data.device_time_us[-1]) != (0, 21500000)
            or tuple(data.sample_sequences) != tuple(range(2151))):
            raise ValueError("stored Q count/time/counter/QC anchors failed")
        if meta["calibration"] != dict(M=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                                        bias_accel_mps2=[0, 0, 0], bias_gyro_rads=[0, 0, 0]):
            raise ValueError("unsupported frozen calibration")
        # Check sensor components against the independently retained pre-Q SI
        # observations; rotations must not alter component half-LSB budgets.
        acceleration_error = float(np.max(np.abs(np.asarray(data.accel_raw_counts) * (.122e-3 * 9.80665)
                                                 - np.asarray(observed["acceleration_mps2"]))))
        rate_error = float(np.max(np.abs(np.asarray(data.gyro_raw_counts) * (17.5e-3 * math.pi / 180)
                                         - np.asarray(observed["angular_rate_rads"]))))
        quantization[node] = dict(acceleration_component_max_mps2=acceleration_error,
                                  rate_component_max_rads=rate_error,
                                  acceleration_half_lsb_mps2=0.00059820565, rate_half_lsb_rads=0.00015271631)
        if acceleration_error > 0.00059820565 + 1e-12 or rate_error > 0.00015271631 + 1e-12:
            raise ValueError("frozen Q half-LSB input gate failed")
        times = np.asarray(data.device_time_us, dtype=np.int64)
        initial = np.asarray([meta["initial_q_WN"]], dtype=float)
        # No truth quaternion time series is supplied to processing.
        nodes[node] = NodeSource(
            sequence=np.asarray(data.sample_sequences, dtype=np.int64),
            nominal_time_us=np.asarray(observed["nominal_time_us"], dtype=np.int64),
            true_time_us=np.asarray(observed["true_time_us"], dtype=np.int64),
            claimed_time_us=np.asarray(observed["claimed_time_us"], dtype=np.int64), device_time_us=times,
            force_mps2=data.accel_mps2, rate_rads=data.gyro_rads,
            q_ws=initial, q_wk=initial, q_wn=initial, r_ns=np.asarray(meta["R_NS"]),
            r_nk=np.asarray(meta["R_NK"]), retained_mask=np.asarray(observed["retained_mask"], dtype=bool),
            clock_scale=meta["clock_scale"], clock_offset_us=meta["clock_offset_us"],
            clock_rounding_residual_us=np.asarray(meta["clock_rounding_residual_us"]),
        )
        captures[node] = (capture, raw_hash)
    source = DualSource(trajectory, Perturbation(), nodes, 100)
    result = _session(case, source, workspace, {}, stored_captures=captures)
    if (plain(result["annotations"]["nominal"]) != references["nominal_m4"]
        or plain(result["annotations"]["summary"]) != references["summary"]):
        raise ValueError("independent labels do not match frozen CP1 annotations")
    after = input_audit(input_root)
    result["input_audit"] = dict(before=before, after=after)
    result["quantization"] = quantization
    result["annotations"]["frozen_motion"] = references["motion"]
    result["annotations"]["frozen_metadata"] = metadata
    result["processing_version"] = "m5-processing/1.1"
    result["replay_kind"] = "immutable stored synthetic Q"
    if before != after:
        result["passed"] = False
        result["failed_gates"].append("immutable_input")
    return result


def export_stored(output: Path, *, input_root: Path = CP1_ROOT) -> int:
    """Claim a fresh development root, retaining all results, including failures.

    Exit 0 means stage B passed, never CP4 acceptance. Missing inputs are BLOCKED
    (exit 2); failed input/numeric gates return 1. E performs formal acceptance.
    """
    output = output.resolve()
    anchors = tuple(ReplayInput(f"Q-{t}-{n}", input_root / t / f"{n}.kimu", "0" * 64,
                               NodeId[n], 538, 2151, (0, 21500000), "synthetic")
                    for t in TRAJECTORIES for n in ("A", "B"))
    _protect(output, anchors)
    output.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}

    def write(name: str, value: Any) -> None:
        content = canonical(value)
        if name.endswith(".gz"):
            content = gzip.compress(content, compresslevel=1, mtime=0)
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
        hashes[name] = sha256(content).hexdigest()

    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "kineimu_shoulder").rglob("*.py"))
    files += ["uv.lock", "protocols/M5_VALIDATION_CONTRACT.md", "protocols/M5_PROCESSING_V1_1.md",
              "tests/fixtures/M5_KNOWN_SENSOR_MOTIONS.md", "tests/integration/test_m5_stored_demo.py",
              "validation/auditors/synthetic.py", "validation/auditors/stored.py",
              "docs/M5_STORED_DEMO.md"]
    write("manifest.json", dict(
        schema_version="m5-report/1.0", checkpoint="CP4", stage="B-stored-Q", formal=False,
        git_commit=git("rev-parse", "HEAD"), tracked_dirty=bool(git("status", "--porcelain", "--untracked-files=no")),
        source_file_sha256={name: sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
        runtime=dict(python=platform.python_version(), platform=platform.platform(),
                     packages={name: version(name) for name in ("numpy", "scipy", "imufusion", "imucal")},
                     thread_environment={name: os.environ.get(name) for name in
                                         ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}),
        case_ids=[f"{t}/CLEAN-Q/SAME/0" for t in TRAJECTORIES], processing_version="m5-processing/1.1",
        input_digest_map_sha256=CP1_MAP_SHA256,
        units=dict(time="us", acceleration="m/s^2", angular_rate="rad/s", orientation="unit quaternion wxyz"),
        configuration=dict(grid_us=10000, max_gap_us=50000, warmup_us=5000000,
                           accel_mg_per_lsb=.122, gyro_mdps_per_lsb=17.5,
                           calibration="frozen known identity", transforms="R_NS before AHRS; R_NK once after AHRS"),
    ))
    rows = []
    worst_errors: dict[str, Any] = {}
    for trajectory in TRAJECTORIES:
        try:
            result = run_stored(trajectory, output, input_root=input_root)
            result.pop("_summary")
        except (FileNotFoundError, PermissionError) as exc:
            result = dict(passed=False, stage_disposition="BLOCKED", error_type=type(exc).__name__)
        except Exception as exc:
            result = dict(passed=False, stage_disposition="FAILED", error_type=type(exc).__name__, error=str(exc))
        name = f"cases/Q-{trajectory}/result.json"
        for key in ("processed", "derived", "annotations", "errors"):
            value = result.pop(key, None)
            write(f"cases/Q-{trajectory}/{key}.json.gz", value)
            if key == "errors":
                result["error_summary"] = {n: {k: r[k] for k in
                    ("n", "max_abs_error", "rmse", "tolerance", "unit", "gate")}
                    for n, r in (value or {}).items()}
        write(name, result)
        for metric, values in result["error_summary"].items():
            maximum = values["max_abs_error"]
            if maximum is not None and (metric not in worst_errors
                                        or maximum > worst_errors[metric]["max_abs_error"]):
                worst_errors[metric] = dict(case_id=f"Q-{trajectory}", **values)
        rows.append(dict(id=f"Q-{trajectory}", passed=result["passed"],
                         disposition=result["stage_disposition"], path=name, sha256=hashes[name],
                         failed_gates=result.get("failed_gates", [])))
    blocked = sum(row["disposition"] == "BLOCKED" for row in rows)
    failed = sum(not row["passed"] and row["disposition"] != "BLOCKED" for row in rows)
    write("report.json", dict(schema_version="m5-report/1.0", checkpoint="CP4", checkpoint_disposition="OPEN",
                              passed=False, stage_passed=all(row["passed"] for row in rows), case_count=4,
                              failed_case_count=failed, blocked_count=blocked, results=rows,
                              not_run_count=blocked, remaining_stages=["C", "D", "E"],
                              artifact_disposition="complete-stage-B" if not failed and not blocked else "partial",
                              requirement_index={requirement: [row["id"] for row in rows] for requirement in
                                  ("immutable-input/QC", "complete-stored-replay", "frozen-label/error-support",
                                   "synthetic-evidence/count/coverage")},
                              evidence_index={row["id"]: dict(path=row["path"], sha256=row["sha256"]) for row in rows},
                              worst_errors=worst_errors,
                              limitations=["Development B only; C/D/E remain required for CP4 acceptance.",
                                           "Synthetic construction; no anatomical or clinical validation."]))
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write("".join(f"{hashes[name]}  {name}\n" for name in sorted(hashes)).encode())
    return 1 if failed else 2 if blocked else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(export_stored(args.output))


if __name__ == "__main__":
    main()
