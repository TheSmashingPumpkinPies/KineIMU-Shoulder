"""Deterministic exact-orientation M2.4/M3 to M4 example; synthetic only.

No AHRS or sensor simulation is implied. CP0 A+B and T4 supply independent
analytical truth; M5 owns noisy sensor/replay validation. Existing stages do
all numerical work; this example assembles and serializes their records.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
from dataclasses import fields, is_dataclass
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import numpy as np

from kineimu_shoulder.exercise import (
    ExerciseConfig,
    compute_repetition_metrics,
    segment_shoulder_repetitions,
)
from kineimu_shoulder.frames import compose_quaternions
from kineimu_shoulder.relative_orientation import (
    ClockMap,
    HeadingRelation,
    SegmentOrientationStream,
    relative_orientation,
)
from kineimu_shoulder.shoulder import AlignmentRecord, long_axis_elevation, relative_angular_speed
from kineimu_shoulder.summary import SummaryContext, compare_summaries, summarize_exercise
from kineimu_shoulder.thorax import (
    ThoraxDriftEvidence,
    ThoraxHeadingEvidence,
    compute_thorax_excursion,
    prepare_thorax_common_grid,
)

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = (1., 0., 0., 0.)
# Frozen CP0 A+B rows, including the reviewed CP4 B speed correction.
TIMES = [-400000, -200000, 0, 200000, 400000, 600000, 800000, 1000000,
         1200000, 1400000, 1600000, 1800000, 2000000, 2200000, 2400000,
         2600000, 2800000, 3000000, 3200000, 3400000, 3600000, 3800000,
         4000000, 4200000, 4400000, 4600000, 4800000, 5000000]
ANGLES = [0, 0, 0, 20, 40, 60, 80, 80, 80, 80, 60, 40, 20, 0, 0,
          0, 0, 0, 20, 40, 60, 60, 60, 60, 40, 20, 0, 0]
PROCESSING_FILES = ["examples/m4_dual_synthetic.py", "kineimu_shoulder/frames/__init__.py",
                    "kineimu_shoulder/relative_orientation.py", "kineimu_shoulder/shoulder/__init__.py",
                    "kineimu_shoulder/exercise.py", "kineimu_shoulder/thorax.py",
                    "kineimu_shoulder/summary.py"]


def plain(value):
    """Preserve nested records; unavailable NaNs become strict JSON nulls."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def canonical(value):
    return (json.dumps(plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def axis(index, degrees):
    q = [math.cos(degrees*math.pi/360), 0., 0., 0.]
    q[index] = math.sin(degrees*math.pi/360)
    return tuple(q)


def alignment(node, segment, side, source_hash):
    return AlignmentRecord(
        node_id=node, epoch=0, segment=segment, side=side, quaternion_nsegment=IDENTITY,
        alignment_id=f"cp5-{node}", method="declared exact synthetic axes", source_sha256=source_hash,
        neutral_pose="arms down; H +Z proximal; T +Z superior", validity="current",
        mounting_validity_statement="one fixed synthetic mount", remounted=False,
        uncertainty="exact synthetic construction", status="supported", axes_basis="synthetic_ground_truth",
    )


def clock(stream, offset):
    lo, hi = int(stream.timestamp_us[0]), int(stream.timestamp_us[-1])
    return ClockMap(stream.node_id, stream.clock_id, 0, 1., offset, lo, hi, lo, hi,
                    0., 0., "exact synthetic affine map", stream.source_sha256, "supported")


def build_artifacts():
    processing_hashes = {name: sha256((ROOT/name).read_bytes()).hexdigest() for name in PROCESSING_FILES}
    processing_hash = digest(processing_hashes)
    lock_hash = sha256((ROOT/"uv.lock").read_bytes()).hexdigest()
    config = ExerciseConfig(500000, max_thorax_drift_rad=math.pi/180)
    calibrations = [{"id": f"cp5-cal-{node}", "source_type": "synthetic",
                     "method": "exact post-alignment orientation input; calibration not executed"}
                    for node in ("A", "B")]
    calibration_hashes = tuple(digest(v) for v in calibrations)
    processed, sessions, summaries, errors = {}, [], [], []

    def error(session_id, metric, actual, expected, unit):
        tolerance = 0 if unit in ("count", "us") else (1e-10 if unit in ("rad", "rad/s") else 1e-12)
        errors.append(dict(session_id=session_id, metric=metric, actual=actual, expected=expected,
                           unit=unit, abs_error=abs(actual-expected), tolerance=tolerance))

    for session_id, exercise, side, motion in (
        ("flexion", "flexion", "left", "flexion"),
        ("left-abduction", "abduction", "left", "abduction"),
        ("right-abduction", "abduction", "right", "abduction"),
        ("wrong-plane", "abduction", "left", "wrong"),
        ("later-flexion", "flexion", "left", "flexion"),
    ):
        later = session_id == "later-flexion"
        times, angles = (TIMES[15:], ANGLES[15:]) if later else (TIMES, ANGLES)
        tq, hq = [], []
        for t, elevation in zip(times, angles, strict=True):
            # CP0 T4 per-rep movement-start baseline, noncommuting thorax motion.
            start, peak, plateau_end, end = ((200000, 800000, 1400000, 2200000) if t < 2600000
                                           else (3200000, 3600000, 4200000, 4800000))
            f = max(0., min(1., (t-start)/(peak-start), (end-t)/(end-plateau_end)))
            thorax = compose_quaternions(axis(3, 30*f),
                                        compose_quaternions(axis(2, -20*f), axis(1, -10*f)))
            relative = axis(2, -elevation) if motion == "flexion" else axis(
                1, elevation if side == "left" and motion != "wrong" else -elevation)
            tq.append(thorax)
            hq.append(compose_quaternions(thorax, relative))
        sources = {}
        streams = []
        for node, quaternions, offset in (("A", tq, 50000), ("B", hq, 100000)):
            source = dict(source_type="synthetic", generator="m4-known-exercises", generator_version="1.0",
                          node_id=node, epoch=0, world_id="W", device_time_us=[t-offset for t in times],
                          quaternion_wsegment_wxyz=quaternions, frame="active scalar-first segment-to-world",
                          source_valid=[True]*len(times), source_reason=["valid"]*len(times))
            sources[node] = source
            streams.append(SegmentOrientationStream(node, f"clock-{node}", 0, "W", digest(source),
                           np.asarray(source["device_time_us"], dtype=np.int64), np.asarray(quaternions)))
        a, b = streams
        a_map, b_map = clock(a, 50000.), clock(b, 100000.)
        heading = HeadingRelation("W", "W", IDENTITY, "known synthetic common world",
                                  digest({"world": "W", "relation": IDENTITY}), "supported")
        aa, ba = alignment("A", "T", side, a.source_sha256), alignment("B", "H", side, b.source_sha256)
        grid = np.asarray(times, dtype=np.int64)
        relative = relative_orientation(a, b, common_time_us=grid, thorax_clock_map=a_map,
                       humerus_clock_map=b_map, heading_relation=heading,
                       max_interpolation_gap_us=500000, max_timing_uncertainty_us=0.)
        shared = dict(thorax_alignment=aa, humerus_alignment=ba, side=side,
                      source_type="synthetic", max_sample_gap_us=500000)
        elevation, speed = long_axis_elevation(relative, **shared), relative_angular_speed(relative, **shared)
        segmentation = segment_shoulder_repetitions(elevation, speed, exercise=exercise, side=side,
                        configuration=config, analysis_window_us=(times[0], times[-1]), session_id=session_id,
                        protocol_id="cp5-exact-synthetic", protocol_version="1.0",
                        calibration_sha256=calibration_hashes, processing_sha256=processing_hash)
        metrics = compute_repetition_metrics(segmentation)
        trace = prepare_thorax_common_grid(a, common_time_us=grid, clock_map=a_map, alignment=aa,
                    calibration_sha256=calibration_hashes[0], configuration=config, max_timing_uncertainty_us=0.,
                    heading_evidence=ThoraxHeadingEvidence("W", "known synthetic heading", heading.source_sha256,
                                                          (times[0], times[-1]), "supported"),
                    drift_evidence=ThoraxDriftEvidence("W", "exact synthetic zero drift", heading.source_sha256,
                                                      (times[0], times[-1]), 0., "supported"))
        proxy = compute_thorax_excursion(metrics, trace=trace)
        # Alignment artifact hash excludes raw lineage consistently with CP4 comparability rules.
        alignment_hashes = tuple(digest({f.name: getattr(v, f.name) for f in fields(v)
                                        if f.name != "source_sha256"}) for v in (aa, ba))
        context = SummaryContext("2026-09-27T00:00:00Z" if later else "2026-09-26T00:00:00Z",
                    tuple(v["id"] for v in calibrations), alignment_hashes,
                    ("exact-orientation", "1.0", config.sha256), ("explicit observed grid", "1.0"),
                    ("m4-known-exercises", "1.0"))
        summary = summarize_exercise(proxy, context=context)
        for name, truth in (("detected_count", 1 if later else 2),
                            ("valid_count", 0 if motion == "wrong" else (1 if later else 2)),
                            ("excluded_count", 2 if motion == "wrong" else 0)):
            error(session_id, name, getattr(summary, name), truth, "count")
        if session_id in ("flexion", "later-flexion"):
            summaries.append(summary)
        input_record = dict(sources=sources, m2=relative, m3_elevation=elevation,
                            m3_speed=speed, thorax_trace=trace, calibrations=calibrations)
        processed[session_id] = input_record
        session = {f.name: getattr(segmentation, f.name) for f in fields(segmentation)
                   if f.name not in ("candidates", "elevation_result", "angular_speed_result")}
        session.update(session_start_utc=context.session_start_utc,
            schema_version="m4-exercise/1.0", source_type="synthetic", units={
                "angles": "rad", "speed": "rad/s", "duration": "s", "time": "int64 microseconds",
                "fraction": "dimensionless", "cadence": "s^-1"},
            processing_file_sha256=processing_hashes, dependency_lock_sha256=lock_hash,
            input_artifact_sha256=digest(input_record),
            original_source_sha256={"A": a.source_sha256, "B": b.source_sha256},
            alignment={"A": aa, "B": ba}, clock_heading={"A": a_map, "B": b_map, "heading": heading},
            summary={f.name: getattr(summary, f.name) for f in fields(summary) if f.name != "input_result"},
            candidates=[dict(**plain(rep.candidate), hold_runs_us=rep.hold_runs_us,
                            elevation_intervals=rep.elevation_intervals, return_intervals=rep.return_intervals,
                            hold_intervals=rep.hold_intervals, metrics=rep.metrics,
                            thorax_proxy={f.name: getattr(p, f.name) for f in fields(p) if f.name != "repetition"})
                        for rep, p in zip(metrics.repetitions, proxy.repetitions, strict=True)])
        sessions.append(session)
        # Independent CP0 A/B/P0 and T4 analytical expectations, never generated from outputs.
        for ordinal, (rep, p) in enumerate(zip(metrics.repetitions, proxy.repetitions, strict=True)):
            if not rep.candidate.valid:
                continue
            is_b = later or ordinal == 1
            for name, truth in (("start_us", 3200000 if is_b else 200000),
                                ("end_us", 4800000 if is_b else 2200000),
                                ("peak_us", 3600000 if is_b else 800000)):
                error(session_id, f"rep{ordinal+1}.{name}", getattr(rep.candidate, name), truth, "us")
            expected = {"rom_rad": (60 if is_b else 80)*math.pi/180,
                "peak_elevation_rad": (60 if is_b else 80)*math.pi/180,
                "rep_duration_s": 1.6 if is_b else 2., "elevation_duration_s": .4 if is_b else .6,
                "return_duration_s": .6 if is_b else .8, "hold_duration_s": .6,
                "rep_speed_mean_rads": (62.5 if is_b else 70)*math.pi/180,
                "rep_speed_max_rads": 100*math.pi/180,
                "elevation_speed_mean_rads": 100*math.pi/180, "elevation_speed_max_rads": 100*math.pi/180,
                "return_speed_mean_rads": 100*math.pi/180, "return_speed_max_rads": 100*math.pi/180,
                "hold_speed_mean_rads": 0., "hold_speed_max_rads": 0.}
            for name, truth in expected.items():
                value = getattr(rep.metrics, name)
                error(session_id, f"rep{ordinal+1}.{name}", value.value, truth, value.unit)
            for name, degrees in (("extension", 20), ("lateral_flexion", 10), ("axial_rotation", 30)):
                error(session_id, f"rep{ordinal+1}.thorax_{name}", getattr(p, name).magnitude_rad,
                      degrees*math.pi/180, "rad")
        if summary.valid_count:
            error(session_id, "rom_mean", summary.statistics["rom_rad"][0].mean.value,
                  (60 if later else 70)*math.pi/180, "rad")
            error(session_id, "active_cadence", summary.active_cadence.value, .625 if later else 5/9, "s^-1")
            if not later:
                error(session_id, "rom_sd", summary.rom_sd.value, 10*math.sqrt(2)*math.pi/180, "rad")
                error(session_id, "rom_cv", summary.rom_cv.value, math.sqrt(2)/7, "dimensionless")
    comparisons = compare_summaries(summaries)
    artifacts = {
        "processed.json": canonical(dict(schema_version="m4-dual-synthetic-processed/1.0", sessions=processed)),
        "derived.json": canonical(dict(schema_version="m4-exercise/1.0", sessions=sessions,
            comparisons=[{f.name: getattr(c, f.name) for f in fields(c) if f.name not in ("earlier", "later")}
                         for c in comparisons])),
    }
    passed = all(e["abs_error"] <= e["tolerance"] for e in errors)
    if not passed:
        raise ValueError("CP5 independent numerical acceptance failed")
    report = dict(schema_version="m4-cp5-acceptance-report/1.0", source_type="synthetic", passed=passed,
        command=".venv/Scripts/python.exe examples/m4_dual_synthetic.py --output-dir <fresh-directory>",
        environment={"python": platform.python_version(), **{p: version(p) for p in ("numpy", "scipy", "pandas")}},
        dependency_lock_sha256=lock_hash, processing_file_sha256=processing_hashes, processing_sha256=processing_hash,
        truth_sha256=sha256((ROOT/"tests/fixtures/M4_KNOWN_EXERCISES.md").read_bytes()).hexdigest(),
        contract_sha256=sha256((ROOT/"protocols/M4_EXERCISE_CONTRACT.md").read_bytes()).hexdigest(),
        configuration=plain(config), configuration_sha256=config.sha256,
        input_artifact_sha256={s["session_id"]: s["input_artifact_sha256"] for s in sessions},
        original_source_sha256={s["session_id"]: s["original_source_sha256"] for s in sessions},
        output_sha256={name: sha256(content).hexdigest() for name, content in artifacts.items()},
        validity_counts={s["session_id"]: {k: s[k] for k in ("detected_count", "valid_count", "excluded_count")}
                         for s in sessions}, numerical_errors=errors,
        evidence={"times": "Observed within synthetic fixture", "metrics": "Derived",
                  "clock_heading_alignment": "supported exact synthetic truth", "validated": False},
        physical_validation="absent", scope="exact post-alignment orientation integration; AHRS not exercised",
        m1_limit="USB pair lacks supported pairwise clock, common heading and measured anatomical alignment",
        next_gate="M5 controlled noise/bias/jitter/loss/drift and recorded replay robustness")
    artifacts["report.json"] = canonical(report)
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    artifacts = build_artifacts()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, content in artifacts.items():
        (args.output_dir/name).write_bytes(content)


if __name__ == "__main__":
    main()
