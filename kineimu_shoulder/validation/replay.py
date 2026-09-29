"""CP4 stage A entry and report gates; never grants formal replay acceptance.

Entry decodes a complete immutable input, but does not execute calibration/AHRS.
Stages B–E must supply full products and clean launch/audit before CP4 can pass.
Gate probes consume explicit already-aligned streams; no evidence is inferred.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
from numpy.typing import NDArray

from kineimu_shoulder.exercise import (
    Exercise,
    compute_repetition_metrics,
    segment_shoulder_repetitions,
)
from kineimu_shoulder.io.m1_packet import NodeId
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorToNodeTransform
from kineimu_shoulder.io.m2_replay import replay_capture
from kineimu_shoulder.relative_orientation import (
    ClockMap,
    HeadingRelation,
    SegmentOrientationStream,
    relative_orientation,
)
from kineimu_shoulder.shoulder import AlignmentRecord, Side, long_axis_elevation, relative_angular_speed
from kineimu_shoulder.summary import SummaryContext, summarize_exercise
from kineimu_shoulder.thorax import (
    ThoraxDriftEvidence,
    ThoraxHeadingEvidence,
    compute_thorax_excursion,
    prepare_thorax_common_grid,
)
from kineimu_shoulder.validation.baseline import CONFIG, ROOT, canonical, plain, record


@dataclass(frozen=True)
class ReplayInput:
    """Independent source anchors, never inferred from this runner's products."""

    case_id: str
    path: Path
    sha256: str
    node_id: NodeId
    expected_packets: int
    expected_samples: int
    expected_endpoints_us: tuple[int, int]
    source_type: Literal["recorded", "synthetic"] = "recorded"


def adapter_config() -> M1RawCountAdapterConfig:
    """Recorded M1 sensitivities with declared sensor-to-node identity only."""
    return M1RawCountAdapterConfig(
        accel_range_g=4.0, gyro_range_dps=500.0,
        accel_sensitivity_mg_per_lsb=0.122, gyro_sensitivity_mdps_per_lsb=17.5,
        axis_transform=SensorToNodeTransform(
            sensor_axes=("sensor_x", "sensor_y", "sensor_z"),
            node_axes=("node_x", "node_y", "node_z"),
            sensor_to_node=((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)),
            description="illustrative node axes; no anatomical alignment or shared world",
        ),
    )


def _protect(output: Path, inputs: tuple[ReplayInput, ...]) -> None:
    if output.exists():
        raise FileExistsError(output)
    protected = [ROOT / "datasets", ROOT / "firmware", ROOT / "kineimu_shoulder", ROOT / "tests"]
    protected += [row.path.resolve().parent for row in inputs]
    protected += [parent.parent for row in inputs for parent in row.path.resolve().parents
                  if parent.name.lower() == "raw"]
    # Existing evidence trees remain immutable, including nested formal roots.
    protected += [ROOT / "validation", ROOT / "docs", ROOT / "benchmarks"]
    if (ROOT / "experiments").is_dir():
        protected += [p for p in (ROOT / "experiments").iterdir() if p.is_dir()]
    if (any(part.lower() == "raw" for part in output.parts)
        or output == ROOT or any(output.is_relative_to(p) or p.is_relative_to(output) for p in protected)):
        raise ValueError("output must be outside raw, input/source trees and existing evidence roots")
    ids = [row.case_id for row in inputs]
    if not inputs or len(set(ids)) != len(ids) or any(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) is None for name in ids
    ):
        raise ValueError("required case IDs must be nonempty, unique safe directory names")
    for row in inputs:
        if (re.fullmatch(r"[0-9a-fA-F]{64}", row.sha256) is None
            or not isinstance(row.node_id, NodeId)
            or row.source_type not in ("recorded", "synthetic")
            or row.expected_packets <= 0 or row.expected_samples <= 0
            or row.expected_endpoints_us[0] > row.expected_endpoints_us[1]):
            raise ValueError(f"invalid independent input anchors for case {row.case_id}")


def _entry(row: ReplayInput) -> dict[str, Any]:
    result: dict[str, Any] = dict(
        id=row.case_id, source_name=row.path.name, expected_source_sha256=row.sha256.lower(),
        source_type=row.source_type,
        node_id=row.node_id.name, source_sha256_before=None, source_sha256_after=None,
        expected_packets=row.expected_packets, expected_samples=row.expected_samples,
        expected_endpoints_us=row.expected_endpoints_us, entry_disposition="FAILED", failed_gates=[],
        epochs=[], qc=None, adapter=plain(adapter_config()),
        downstream=dict(value=None, valid=False, reason="full_replay_not_run", stage_disposition="NOT RUN"),
    )
    try:
        result["source_sha256_before"] = sha256(row.path.read_bytes()).hexdigest()
        replay = replay_capture(row.path, expected_sha256=row.sha256,
                                expected_node_id=row.node_id, config=adapter_config())
        result["qc"] = plain(replay.qc)
        result["epochs"] = [dict(
            clock_epoch=epoch.clock_epoch, packet_sequences=epoch.packet_sequences,
            device_time_us=epoch.sensor_data.device_time_us,
            sample_sequences=epoch.sensor_data.sample_sequences,
            sample_flags=plain(epoch.sensor_data.sample_flags),
        ) for epoch in replay.epochs]
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
        result["entry_disposition"] = "FAILED" if result["failed_gates"] else "PASSED"
    except (FileNotFoundError, PermissionError) as exc:
        result.update(entry_disposition="BLOCKED", error_type=type(exc).__name__)
    except Exception as exc:
        # Exceptions remain failures, with no absolute input/output path in canonical bytes.
        result.update(error_type=type(exc).__name__, failed_gates=["input_decode_or_identity"])
    finally:
        if result["source_sha256_before"] is not None:
            try:
                result["source_sha256_after"] = sha256(row.path.read_bytes()).hexdigest()
                if result["source_sha256_before"] != result["source_sha256_after"]:
                    result["failed_gates"].append("source_changed")
                    result["entry_disposition"] = "FAILED"
            except (FileNotFoundError, PermissionError) as exc:
                result.update(entry_disposition="BLOCKED", error_type=type(exc).__name__)
    return result


def export_entry(output: Path, inputs: tuple[ReplayInput, ...]) -> int:
    """Atomically claim a development root, retain every entry and NOT RUN status.

    Exit 1 on an input failure; otherwise exit 2 because full replay is pending.
    There is deliberately no formal flag or success/CP4 PASS path at stage A.
    """
    output = output.resolve()
    _protect(output, inputs)

    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    sources = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "kineimu_shoulder").rglob("*.py"))
    sources += ["uv.lock", "protocols/M5_VALIDATION_CONTRACT.md", "protocols/M5_PROCESSING_V1_1.md",
                "tests/fixtures/M5_KNOWN_SENSOR_MOTIONS.md", "datasets/samples/m6_synthetic/case-manifest.json",
                "tests/integration/test_m5_replay_entry.py", "protocols/M5_VALIDATION_CONTRACT.md"]
    manifest = dict(
        schema_version="m5-report/1.0", checkpoint="CP4", stage="A-entry-only", formal=False,
        git_commit=git("rev-parse", "HEAD"),
        tracked_dirty=bool(git("status", "--porcelain", "--untracked-files=no")),
        source_file_sha256={name: sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
        runtime=dict(python=platform.python_version(), platform=platform.platform(),
                     packages={name: version(name) for name in ("numpy", "scipy", "imufusion", "imucal")}),
        case_ids=[row.case_id for row in inputs], configuration=plain(adapter_config()),
        input_anchors=[dict(id=row.case_id, source_name=row.path.name, source_type=row.source_type,
                           node_id=row.node_id.name, sha256=row.sha256.lower(),
                           packets=row.expected_packets, samples=row.expected_samples,
                           endpoints_us=row.expected_endpoints_us) for row in inputs],
        processing="read-only M1 framing/QC/sensor-SI; calibration/AHRS/M3/M4 NOT RUN",
        units=dict(time="us", acceleration="m/s^2", angular_rate="rad/s"),
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
    results = []
    evidence = {}
    for row in inputs:
        entry = _entry(row)
        name = f"cases/{row.case_id}/entry.json"
        write(name, entry)
        evidence[row.case_id] = dict(path=name, sha256=hashes[name])
        status = entry["entry_disposition"]
        results.append(dict(id=row.case_id, entry_disposition=status,
                            stage_disposition="NOT RUN" if status == "PASSED" else status,
                            failed_gates=entry["failed_gates"]))
    failed = sum(r["stage_disposition"] == "FAILED" for r in results)
    blocked = sum(r["stage_disposition"] == "BLOCKED" for r in results)
    write("report.json", dict(
        schema_version="m5-report/1.0", checkpoint="CP4", checkpoint_disposition="OPEN", passed=False,
        results=results, case_count=len(inputs), failed_case_count=failed, blocked_count=blocked,
        not_run_count=len(inputs), artifact_disposition="partial", evidence_index=evidence,
        requirement_index={name: [r.case_id for r in inputs] for name in ("immutable-input/QC", "complete-replay")},
        limitations=["Stage A only; complete calibration/AHRS/downstream and formal launch/audit remain NOT RUN.",
                     "No anatomical, motion-accuracy or clinical validation from recorded source identity."],
    ))
    with (output / "SHA256SUMS.txt").open("xb") as stream:
        stream.write("".join(f"{hashes[name]}  {name}\n" for name in sorted(hashes)).encode())
    return 1 if failed else 2


def gate_report(
    *, thorax: SegmentOrientationStream, humerus: SegmentOrientationStream,
    common_time_us: NDArray[np.int64], thorax_clock_map: ClockMap | None, humerus_clock_map: ClockMap | None,
    heading_relation: HeadingRelation | None, thorax_alignment: AlignmentRecord | None,
    humerus_alignment: AlignmentRecord | None, heading_evidence: ThoraxHeadingEvidence | None,
    drift_evidence: ThoraxDriftEvidence | None, context: SummaryContext,
    calibration_sha256: tuple[str, str], source_type: str, side: Side, exercise: Exercise,
) -> dict[str, Any]:
    """Run actual M2/M3/M4 gates and serialize their records without rescuing values.

    Callers supply an explicit common grid and already-aligned streams. This
    function does not infer clocks, transform node axes, fit heading or drift.
    """
    relative = relative_orientation(
        thorax, humerus, common_time_us=common_time_us,
        thorax_clock_map=thorax_clock_map, humerus_clock_map=humerus_clock_map,
        heading_relation=heading_relation, max_interpolation_gap_us=50000, max_timing_uncertainty_us=2000.,
    )
    shared = dict(thorax_alignment=thorax_alignment, humerus_alignment=humerus_alignment,
                  side=side, source_type=source_type, max_sample_gap_us=50000)
    elevation = long_axis_elevation(relative, **shared)  # type: ignore[arg-type]
    speed = relative_angular_speed(relative, **shared)  # type: ignore[arg-type]
    segmentation = segment_shoulder_repetitions(
        elevation, speed, exercise=exercise, side=side, configuration=CONFIG,
        analysis_window_us=(int(common_time_us[0]), int(common_time_us[-1])),
        session_id="cp4-gate-probe", protocol_id="m5-replay", protocol_version="1.0",
        calibration_sha256=calibration_sha256,
        processing_sha256=sha256(canonical(dict(configuration=plain(CONFIG), source_type=source_type))).hexdigest(),
    )
    metrics = compute_repetition_metrics(segmentation)
    trace = prepare_thorax_common_grid(
        thorax, common_time_us=common_time_us, clock_map=thorax_clock_map, alignment=thorax_alignment,
        calibration_sha256=calibration_sha256[0], configuration=CONFIG, max_timing_uncertainty_us=2000.,
        heading_evidence=heading_evidence, drift_evidence=drift_evidence,
    )
    thorax_result = compute_thorax_excursion(metrics, trace=trace)
    summary = summarize_exercise(thorax_result, context=context)
    return dict(relative=plain(relative), elevation=record(elevation, "relative_orientation"),
                speed=record(speed, "relative_orientation"), segmentation=record(
                    segmentation, "elevation_result", "angular_speed_result"),
                metrics=record(metrics, "segmentation"), trace=record(trace, "original_stream"),
                thorax=record(thorax_result, "metrics", "trace"), summary=record(summary, "input_result"))


def main() -> None:
    """Explicit development entry only; input spec is a validation-local JSON list."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        rows = json.loads(args.input_spec.read_text(encoding="utf-8"))
        selected = tuple(ReplayInput(
            case_id=row["case_id"], path=Path(row["path"]), sha256=row["sha256"], node_id=NodeId[row["node_id"]],
            expected_packets=row["expected_packets"], expected_samples=row["expected_samples"],
            expected_endpoints_us=(row["expected_endpoints_us"][0], row["expected_endpoints_us"][1]),
            source_type=cast(Literal["recorded", "synthetic"], row["source_type"]),
        ) for row in rows)
        status = export_entry(args.output, selected)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        parser.error(str(exc))
    raise SystemExit(status)


if __name__ == "__main__":
    main()
