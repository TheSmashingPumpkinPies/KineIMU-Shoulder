"""Validation-only CP2 clean E/S/Q integration; frozen CP0 gates, no tuning.

Production stages compute observations. Independent oracle matrices/labels supply
expectations. Failures stay in reports and prevent checkpoint acceptance.
"""

from __future__ import annotations

import json
import math
import platform
import subprocess
from dataclasses import fields, is_dataclass
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import numpy as np
from scipy.spatial.transform import Rotation  # type: ignore[import-untyped]

from kineimu_shoulder.calibration import CalibrationArtifact, apply_calibration
from kineimu_shoulder.exercise import ExerciseConfig, compute_repetition_metrics, segment_shoulder_repetitions
from kineimu_shoulder.io.m1_capture import encode_capture_record
from kineimu_shoulder.io.m1_packet import NodeId, SampleFlags, encode_sample_packet
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorToNodeTransform
from kineimu_shoulder.io.m2_replay import replay_capture
from kineimu_shoulder.orientation import align_segment, estimate_orientation
from kineimu_shoulder.relative_orientation import (
    ClockMap,
    HeadingRelation,
    SegmentOrientationStream,
    relative_orientation,
)
from kineimu_shoulder.shoulder import AlignmentRecord, Side, long_axis_elevation, relative_angular_speed
from kineimu_shoulder.summary import SummaryContext, compare_summaries, summarize_exercise
from kineimu_shoulder.thorax import (
    ThoraxDriftEvidence,
    ThoraxHeadingEvidence,
    compute_thorax_excursion,
    prepare_thorax_common_grid,
)
from kineimu_shoulder.validation.manifest import cases
from kineimu_shoulder.validation.motions import MOTIONS
from kineimu_shoulder.validation.oracle import labels, proxy, segment_matrix, summary
from kineimu_shoulder.validation.source import generate, packets

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = (1., 0., 0., 0.)
CONFIG = ExerciseConfig(50000, max_thorax_drift_rad=math.pi / 180)


def plain(value: Any) -> Any:
    """Strict JSON including null for unavailable numbers; no ndarray loss."""
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
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(plain(value), sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()


def record(value: Any, *exclude: str) -> dict[str, Any]:
    return {f.name: plain(getattr(value, f.name)) for f in fields(value) if f.name not in exclude}


def matrix(q: Any) -> Any:
    return Rotation.from_quat(np.asarray(q)[..., [1, 2, 3, 0]]).as_matrix()


def quaternion(r: Any) -> Any:
    return Rotation.from_matrix(r).as_quat()[..., [3, 0, 1, 2]]


def distance(a: Any, b: Any) -> float:
    """Stable principal matrix geodesic, avoids acos roundoff at identity."""
    r = np.asarray(a).T @ np.asarray(b)
    skew = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]]) / 2
    return math.atan2(float(np.linalg.norm(skew)), float((np.trace(r) - 1) / 2))


def exact_orientation(trajectory: str, node: str, times_us: Any) -> Any:
    """E symbolic grid input: integer-time ratios, then elementary axis-angle.

    Separate from the continuous floating-time S generator. M4 equality fixtures
    require matching symbolic inputs, not threshold slack or angle snapping.
    """
    motion = MOTIONS[trajectory]
    output = []
    for time_us in times_us:
        start, degrees = 5000000, Fraction(0)
        for cycle in motion.cycles:
            offset = int(time_us) - start
            if 0 < offset <= cycle.rise_us:
                degrees = Fraction(cycle.peak_deg * offset, cycle.rise_us)
                break
            if cycle.rise_us < offset <= cycle.rise_us + cycle.hold_us:
                degrees = Fraction(cycle.peak_deg)
                break
            if cycle.rise_us + cycle.hold_us < offset <= cycle.rise_us + cycle.hold_us + cycle.return_us:
                degrees = Fraction(cycle.peak_deg) * (1 - Fraction(
                    offset - cycle.rise_us - cycle.hold_us, cycle.return_us))
                break
            start += cycle.rise_us + cycle.hold_us + cycle.return_us + cycle.rest_us
        half = float(degrees) * math.pi / 360
        relative = [math.cos(half), 0., 0., 0.]
        relative[1 if motion.axis == "X" else 2] = motion.sign * math.sin(half)
        if motion.thorax == "fixed":
            output.append(IDENTITY if node == "A" else relative)
        else:
            e = float(degrees) * math.pi / 180
            thorax = Rotation.from_euler("ZYX", [e / 18 if motion.thorax == "mixed" else 0,
                                                 -e / 9, e / 30 if motion.thorax == "mixed" else 0])
            segment = thorax if node == "A" else thorax * Rotation.from_quat(relative, scalar_first=True)
            output.append(segment.as_quat(scalar_first=True))
    return np.asarray(output, dtype=np.float64)


def run_case(trajectory: str, path: str, workspace: Path, *, missing_heading: bool = False) -> dict[str, Any]:
    """Execute one entire clean session; return evidence even when gates fail."""
    if trajectory not in MOTIONS or path not in ("E", "S", "Q"):
        raise ValueError("unknown baseline trajectory/path")
    source = generate(trajectory)
    motion = MOTIONS[trajectory]
    side = cast(Side, motion.side)
    window = (motion.analysis_start_us, motion.analysis_end_us or motion.end_us)
    segmentation_window = window if trajectory == "PARTIAL" else (0, window[1])
    grid = np.arange(segmentation_window[0], window[1] + 1, 10000, dtype=np.int64)
    nodes: dict[str, Any] = {}
    streams, maps, alignments, calibration_hashes = [], [], [], []
    errors: dict[str, Any] = {}
    failed: list[str] = []
    angle_tol = 1e-10 if path == "E" else math.pi / 180
    speed_tol = 1e-10 if path == "E" else math.pi / 90
    duration_tol = 1e-12 if path == "E" else .10
    boundary_tol = 0 if path == "E" else 50000

    def error(name: str, actual: Any, expected: Any, tolerance: float, unit: str,
              *, gate: bool = True, support: Any = None) -> None:
        a = np.asarray(actual, dtype=float).reshape(-1)
        e = np.asarray(expected, dtype=float).reshape(-1)
        if a.shape != e.shape:
            raise ValueError(f"error support mismatch: {name}")
        valid = np.isfinite(a) & np.isfinite(e)
        delta = a - e
        maximum = float(np.max(np.abs(delta[valid]))) if valid.any() else None
        errors[name] = dict(actual=plain(a), expected=plain(e), signed_error=plain(delta),
                            absolute_error=plain(np.abs(delta)), n=int(valid.sum()), support=plain(support),
                            max_abs_error=maximum, rmse=float(np.sqrt(np.mean(delta[valid]**2)))
                            if valid.any() else None, tolerance=tolerance, unit=unit, gate=gate)
        if gate and (not valid.all() or maximum is None or maximum > tolerance):
            failed.append(name)

    for node, row in source.nodes.items():
        node_id = NodeId.A if node == "A" else NodeId.B
        transform = SensorToNodeTransform(("SX", "SY", "SZ"), ("NX", "NY", "NZ"),
                                         cast(tuple[tuple[float, float, float], ...],
                                              tuple(tuple(float(x) for x in v) for v in row.r_ns)),
                                         "M5 O3 fixed proper R_NS; node=R_NS sensor")
        config = M1RawCountAdapterConfig(4, 500, .122, 17.5, transform)
        times, force, rate = row.device_time_us, row.force_mps2, row.rate_rads
        flags = (SampleFlags(0),) * len(times)
        raw_record: dict[str, Any] = dict(sequence=row.sequence, nominal_time_us=row.nominal_time_us,
                                        true_time_us=row.true_time_us, claimed_time_us=row.claimed_time_us,
                                        device_time_us=times, retained_mask=row.retained_mask,
                                        acceleration_mps2=force, angular_rate_rads=rate)
        replay_metadata = None
        if path == "Q":
            payload = b"".join(encode_capture_record(encode_sample_packet(p),
                               host_monotonic_ns=p.samples[-1].device_time_us * 1000) for p in packets(row, node))
            capture = workspace / f"{trajectory}-{node}.kimu"
            with capture.open("xb") as stream:
                stream.write(payload)
            raw_hash = sha256(payload).hexdigest()
            replay = replay_capture(capture, expected_sha256=raw_hash, expected_node_id=node_id, config=config)
            epoch = replay.epochs[0]
            data = epoch.sensor_data
            times = np.asarray(data.device_time_us, dtype=np.int64)
            force, rate, flags = data.accel_mps2, data.gyro_rads, data.sample_flags
            raw_record.update(device_time_us=times, acceleration_mps2=force, angular_rate_rads=rate,
                              accel_raw_counts=data.accel_raw_counts, gyro_raw_counts=data.gyro_raw_counts)
            replay_metadata = dict(source_sha256=raw_hash, qc=plain(replay.qc),
                                   packet_sequences=epoch.packet_sequences, sample_sequences=data.sample_sequences,
                                   source_hash_after=sha256(capture.read_bytes()).hexdigest())
            if replay_metadata["source_hash_after"] != raw_hash:
                failed.append(f"{node}.raw_immutable")
        if path == "E":
            raw_record["exact_quaternion_wsegment"] = exact_orientation(trajectory, node, row.nominal_time_us)
            raw_record["input_recipe"] = "integer/rational grid axis-angle; exact E isolation"
        source_hash = digest(raw_record)
        # Known parameters originate in the frozen contract, not evaluation
        # motion. Equal artifacts must stay comparable; raw hashes stay lineage.
        parameter_source_hash = sha256((ROOT / "protocols/M5_VALIDATION_CONTRACT.md").read_bytes()).hexdigest()
        artifact = CalibrationArtifact(f"m5-cal-{node}", node_id, "synthetic-LSM6DS3TR-C", config,
                                       ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)), (0., 0., 0.), (0., 0., 0.),
                                       "declared clean SI parameters; no fit on evaluation motion", (0, 5000000),
                                       (parameter_source_hash,), "synthetic")
        calibrated_acc = calibrated_rate = orientation = None
        if path == "E":
            aligned = raw_record["exact_quaternion_wsegment"]
        else:
            calibrated_acc, calibrated_rate = apply_calibration(force, rate, artifact=artifact, node_id=node_id,
                sensor_id=artifact.sensor_id, config=config, sample_flags=flags)
            orientation = estimate_orientation(times, calibrated_acc, calibrated_rate, max_gap_s=.05,
                                              initial_quaternion_wn=row.q_wn[0])
            aligned = np.asarray([align_segment(q, quaternion(row.r_nk)) for q in orientation.quaternion_wn])
        # Truth is independently reconstructed from O/F/T matrices, never source q arrays.
        geodesic = [distance(segment_matrix(trajectory, node, int(t) / 1e6), r)
                    for t, r in zip(row.true_time_us, matrix(aligned), strict=True)]
        selected = (row.true_time_us >= window[0]) & (row.true_time_us <= window[1])
        error(f"{node}.orientation", np.asarray(geodesic)[selected], np.zeros(int(selected.sum())),
              1e-12 if path == "E" else math.pi / 450, "rad", support=row.true_time_us[selected])
        error(f"{node}.initialization", [geodesic[0], geodesic[500]], [0., 0.],
              1e-12 if path == "E" else math.pi / 450, "rad", support=[0, 5000000])
        stream_record = SegmentOrientationStream(node, f"clock-{node}", 0, "synthetic-M5-world", source_hash,
                                                times, aligned)
        lo, hi = int(times[0]), int(times[-1])
        clock = ClockMap(node, stream_record.clock_id, 0, row.clock_scale, row.clock_offset_us, lo, hi, lo, hi,
                         1., 1., "known synthetic construction", source_hash, "supported")
        alignment = AlignmentRecord(node, 0, "T" if node == "A" else "H", side,
                                    cast(tuple[float, float, float, float],
                                         tuple(float(v) for v in quaternion(row.r_nk))), f"m5-align-{node}",
                                    "known synthetic R_NK applied once after AHRS", source_hash,
                                    "H +Z proximal; T +Z superior", "current", "fixed synthetic mount", False,
                                    "synthetic exact construction", "supported", "synthetic_ground_truth")
        streams.append(stream_record)
        maps.append(clock)
        alignments.append(alignment)
        calibration_hashes.append(digest(artifact))
        nodes[node] = dict(source=plain(raw_record), source_sha256=source_hash, replay=plain(replay_metadata),
                           calibration=plain(artifact), calibration_executed=path != "E", ahrs_executed=path != "E",
                           calibrated_acceleration_mps2=plain(calibrated_acc),
                           calibrated_rate_rads=plain(calibrated_rate),
                           orientation=plain(orientation), aligned_segment_stream=plain(stream_record),
                           alignment=plain(alignment), clock_map=plain(clock))
    a, b = streams
    aa, ba = alignments
    ca, cb = maps
    heading = HeadingRelation(a.world_id, b.world_id, IDENTITY, "known synthetic common world", digest(IDENTITY),
                              "supported")
    relative = relative_orientation(a, b, common_time_us=grid, thorax_clock_map=ca, humerus_clock_map=cb,
        heading_relation=None if missing_heading else heading, max_interpolation_gap_us=50000,
        max_timing_uncertainty_us=2000.)
    shared = dict(thorax_alignment=aa, humerus_alignment=ba, side=side,
                  source_type="synthetic", max_sample_gap_us=50000)
    elevation = long_axis_elevation(relative, **shared)  # type: ignore[arg-type]
    speed = relative_angular_speed(relative, **shared)  # type: ignore[arg-type]
    truth_relative = [segment_matrix(trajectory, "A", int(t) / 1e6).T @
                      segment_matrix(trajectory, "B", int(t) / 1e6) for t in grid]
    truth_elevation = [math.atan2(float(np.linalg.norm(r[:2, 2])), float(r[2, 2])) for r in truth_relative]
    truth_speed = [distance(x, y) / ((int(t1) - int(t0)) / 1e6)
                   for x, y, t0, t1 in zip(truth_relative[:-1], truth_relative[1:], grid[:-1], grid[1:], strict=True)]
    evaluation_rows = grid >= window[0]
    evaluation_intervals = grid[:-1] >= window[0]
    error("elevation", elevation.elevation_rad[evaluation_rows], np.asarray(truth_elevation)[evaluation_rows],
          angle_tol, "rad", support=grid[evaluation_rows])
    error("interval_speed", speed.relative_angular_speed_rads[evaluation_intervals],
          np.asarray(truth_speed)[evaluation_intervals], speed_tol, "rad/s",
          support=list(zip(grid[:-1][evaluation_intervals], grid[1:][evaluation_intervals], strict=True)))
    segmentation = segment_shoulder_repetitions(elevation, speed, exercise="abduction" if trajectory in
        ("AL90", "AR90", "WRONG") else "flexion", side=side, configuration=CONFIG,
        analysis_window_us=segmentation_window,
        session_id=f"{trajectory}-CLEAN-{path}", protocol_id="m5-clean", protocol_version="1.0",
        calibration_sha256=(calibration_hashes[0], calibration_hashes[1]),
        processing_sha256=digest({"backend": path, "config": CONFIG.sha256}))
    metrics = compute_repetition_metrics(segmentation)
    trace = prepare_thorax_common_grid(a, common_time_us=grid, clock_map=ca, alignment=aa,
        calibration_sha256=calibration_hashes[0], configuration=CONFIG, max_timing_uncertainty_us=2000.,
        heading_evidence=ThoraxHeadingEvidence(a.world_id, "known synthetic heading", heading.source_sha256,
                                             segmentation_window, "supported"),
        drift_evidence=ThoraxDriftEvidence(a.world_id, "known synthetic zero drift", heading.source_sha256,
                                         segmentation_window, 0., "supported"))
    thorax = compute_thorax_excursion(metrics, trace=trace)
    context = SummaryContext("2026-09-27T00:00:00Z" if trajectory == "F90-NEXT" else "2026-09-26T00:00:00Z",
        ("m5-cal-A", "m5-cal-B"), cast(tuple[str, str],
                                      tuple(digest(record(v, "source_sha256")) for v in alignments)),
        ("exact" if path == "E" else "imufusion", "1.0" if path == "E" else version("imufusion"), CONFIG.sha256),
        ("explicit common grid SLERP", "10000us/50000us/2000us"), ("m5-sensor-source", "1.0"))
    session_summary = summarize_exercise(thorax, context=context)
    nominal, expected_summary = labels(trajectory), summary(trajectory)
    unmatched = set(range(len(nominal)))
    aggregate_truth: dict[str, list[float]] = {}
    aggregate_tolerances: dict[str, float] = {}
    matches: list[dict[str, Any]] = []
    false_ids: list[int] = []
    for rep, thorax_rep in zip(metrics.repetitions, thorax.repetitions, strict=True):
        candidate = rep.candidate
        overlaps = []
        for i in sorted(unmatched):
            truth = nominal[i]
            intersection = max(0, min(candidate.end_us, truth["physical_end_us"]) -
                               max(candidate.start_us, truth["physical_start_us"]))
            union = (max(candidate.end_us, truth["physical_end_us"]) -
                     min(candidate.start_us, truth["physical_start_us"]))
            if intersection / union >= .5:
                overlaps.append(i)
        if not overlaps:
            if candidate.valid:
                false_ids.append(candidate.id)
            matches.append(dict(candidate_id=candidate.id, truth_id=None, reasons=candidate.reasons))
            continue
        index = overlaps[0]
        unmatched.remove(index)
        truth = nominal[index]
        prefix = truth["truth_id"]
        matches.append(dict(candidate_id=candidate.id, truth_id=prefix, valid=candidate.valid,
                            eligible=truth["eligible"], reasons=candidate.reasons, duplicate_overlaps=overlaps[1:]))
        if not truth["eligible"]:
            if candidate.valid or truth["expected_exclusion"] not in candidate.reasons:
                failed.append(f"{prefix}.exclusion")
            for metric_field in fields(rep.metrics):
                if getattr(rep.metrics, metric_field.name).valid:
                    failed.append(f"{prefix}.excluded_numeric")
            continue
        if not candidate.valid:
            failed.append(f"{prefix}.missed")
            continue
        for name in ("start_us", "end_us"):
            error(f"{prefix}.{name}", getattr(candidate, name), truth[name], boundary_tol, "us")
        error(f"{prefix}.start_confirmation", candidate.start_confirmation_us[-1]
              if candidate.start_confirmation_us else np.nan, truth["confirm_start_us"], boundary_tol, "us")
        error(f"{prefix}.end_confirmation", candidate.end_confirmation_us[-1]
              if candidate.end_confirmation_us else np.nan, truth["confirm_end_us"], boundary_tol, "us")
        p0, p1 = truth["plateau_support_us"]
        error(f"{prefix}.peak_support", max(p0 - candidate.peak_us, candidate.peak_us - p1, 0), 0, boundary_tol, "us")
        error(f"{prefix}.earliest_peak", candidate.peak_us, truth["peak_us"], boundary_tol, "us", gate=path == "E")
        error(f"{prefix}.plane_fraction", candidate.plane_fraction, 1., 1e-12 if path == "E" else .02, "1")
        expected = dict(rom_rad=truth["rom_rad"], peak_elevation_rad=truth["peak_rad"],
                        rep_duration_s=truth["duration_s"], elevation_duration_s=truth["rise_s"],
                        return_duration_s=truth["return_s"], hold_duration_s=truth["hold_s"],
                        rep_speed_mean_rads=truth["mean_speed_rads"], rep_speed_max_rads=truth["max_speed_rads"])
        # Frozen ownership: estimated maximum can move inside physical plateau.
        # The held plateau intervals are removed from both phases independently.
        peak = truth["peak_us"] if path == "E" else min(p1, max(p0, candidate.peak_us))
        expected["elevation_duration_s"] += (peak - p0) / 1e6 if truth["hold_s"] == 0 else 0
        expected["return_duration_s"] -= (peak - p0) / 1e6 if truth["hold_s"] == 0 else 0
        cycle = motion.cycles[index]
        rise_speed = cycle.peak_deg * math.pi / 180 * 1e6 / cycle.rise_us
        return_speed = cycle.peak_deg * math.pi / 180 * 1e6 / cycle.return_us
        expected.update(elevation_speed_mean_rads=rise_speed, elevation_speed_max_rads=rise_speed,
                        return_speed_mean_rads=return_speed, return_speed_max_rads=return_speed)
        if truth["hold_s"]:
            expected.update(hold_speed_mean_rads=0., hold_speed_max_rads=0.)
        else:
            for name in ("hold_speed_mean_rads", "hold_speed_max_rads"):
                if getattr(rep.metrics, name).valid or getattr(rep.metrics, name).reason != "empty_phase":
                    failed.append(f"{prefix}.{name}.availability")
        if index and nominal[index - 1]["eligible"]:
            expected["preceding_rest_duration_s"] = (truth["start_us"] - nominal[index - 1]["end_us"]) / 1e6
        elif rep.metrics.preceding_rest_duration_s.valid:
            failed.append(f"{prefix}.rest_availability")
        for name, expected_value in expected.items():
            metric_value = getattr(rep.metrics, name)
            tolerance = speed_tol if metric_value.unit == "rad/s" else duration_tol if metric_value.unit == "s" else (
                angle_tol * 2 if name == "rom_rad" and path != "E" else angle_tol)
            error(f"{prefix}.{name}", metric_value.value, expected_value, tolerance, metric_value.unit)
            aggregate_truth.setdefault(name, []).append(expected_value)
            aggregate_tolerances[name] = tolerance
        error(f"{prefix}.phase_conservation", sum(getattr(rep.metrics, name).value for name in
              ("elevation_duration_s", "return_duration_s", "hold_duration_s")), rep.metrics.rep_duration_s.value,
              1e-12, "s")
        selected_times = grid[(grid >= candidate.start_us) & (grid <= candidate.end_us)]
        # Independently evaluate nominal and estimated endpoint supports separately.
        for support_name, begin, end in (("nominal", truth["start_us"], truth["end_us"]),
                                          ("estimated", candidate.start_us, candidate.end_us)):
            times_support = grid[(grid >= begin) & (grid <= end)]
            indices = [int(np.searchsorted(grid, t)) for t in times_support[:-1]]
            reference = np.asarray(truth_speed)[indices]
            error(f"{prefix}.speed_{support_name}_mean", rep.metrics.rep_speed_mean_rads.value,
                  np.mean(reference), speed_tol, "rad/s", support=[begin, end])
        p = proxy(trajectory, candidate.start_us, selected_times.tolist())
        nominal_times = grid[(grid >= truth["start_us"]) & (grid <= truth["end_us"])]
        nominal_proxy = proxy(trajectory, truth["start_us"], nominal_times.tolist())
        for component_index, component_name in enumerate(("extension", "lateral_flexion", "axial_rotation")):
            component = getattr(thorax_rep, component_name)
            for attribute, value in (("min_rad", float(p[:, component_index].min())),
                                      ("max_rad", float(p[:, component_index].max())),
                                      ("magnitude_rad", float(np.abs(p[:, component_index]).max()))):
                nominal_component = nominal_proxy[:, component_index]
                nominal_value = (float(nominal_component.min()) if attribute == "min_rad" else
                                 float(nominal_component.max()) if attribute == "max_rad" else
                                 float(np.abs(nominal_component).max()))
                error(f"{prefix}.proxy.{component_name}.{attribute}", getattr(component, attribute),
                      nominal_value, angle_tol, "rad", support=[truth["start_us"], truth["end_us"]])
                error(f"{prefix}.proxy_estimated_support.{component_name}.{attribute}",
                      getattr(component, attribute), value, angle_tol, "rad",
                      support=[candidate.start_us, candidate.end_us])
                key = f"thorax_{component_name}_{attribute}"
                aggregate_truth.setdefault(key, []).append(nominal_value)
                aggregate_tolerances[key] = angle_tol
    missed_ids = [r["truth_id"] for i, r in enumerate(nominal) if r["eligible"] and
                  (i in unmatched or not any(m.get("truth_id") == r["truth_id"] and m.get("valid") for m in matches))]
    if missed_ids or false_ids or session_summary.valid_count != expected_summary["valid_count"]:
        failed.append("counts")
    if segmentation.detected_count != len(nominal):
        failed.append("detected_count")
    elapsed = (window[1] - window[0]) / 1e6
    valid_duration = sum(int(y) - int(x) for x, y, valid in
                         zip(grid[:-1], grid[1:], speed.valid, strict=True) if valid and x >= window[0]) / 1e6
    relative_coverage = valid_duration / elapsed
    proxy_coverage = ((session_summary.proxy_valid_count or 0) / session_summary.valid_count
                      if session_summary.valid_count else None)
    if relative_coverage != 1. or (session_summary.valid_count and proxy_coverage != 1.):
        failed.append("coverage")
    for key, values in aggregate_truth.items():
        groups = session_summary.statistics[key]
        if len(groups) != 1 or groups[0].n != len(values):
            failed.append(f"summary.{key}.support")
            continue
        for quantity, expected_value in (("mean", sum(values) / len(values)), ("maximum", max(values))):
            scalar = getattr(groups[0], quantity)
            error(f"summary.{key}.{quantity}", scalar.value, expected_value, aggregate_tolerances[key], scalar.unit)
    # Summaries: n-1 SD, conservative CP0 CV and cadence formulas, null controls.
    rom_epsilon = 1e-10 if path == "E" else math.pi / 90
    for name, actual in (("rom_mean_rad", session_summary.statistics["rom_rad"][0].mean.value
                          if session_summary.statistics.get("rom_rad") else np.nan),
                         ("rom_max_rad", session_summary.statistics["rom_rad"][0].maximum.value
                          if session_summary.statistics.get("rom_rad") else np.nan),
                         ("rom_range_rad", session_summary.rom_range.value),
                         ("rom_sd_rad", session_summary.rom_sd.value),
                         ("rom_cv", session_summary.rom_cv.value),
                         ("active_s", session_summary.active_time_s.value),
                         ("cadence_per_s", session_summary.active_cadence.value)):
        # Existing M4 defines empty active time as the valid sum of zero reps.
        expected_value = 0. if name == "active_s" and not expected_summary["valid_count"] else expected_summary[name]
        if expected_value is None:
            if math.isfinite(actual):
                failed.append(f"summary.{name}.null")
            continue
        tolerance = rom_epsilon
        if name in ("rom_range_rad", "rom_sd_rad"):
            tolerance = 1e-10 if path == "E" else 2 * rom_epsilon
        elif name == "rom_cv":
            mu, sd = expected_summary["rom_mean_rad"], expected_summary["rom_sd_rad"]
            tolerance = 1e-12 if path == "E" else 2 * rom_epsilon / (mu - rom_epsilon) + (
                sd * rom_epsilon / (mu * (mu - rom_epsilon)))
        elif name == "active_s":
            tolerance = expected_summary["valid_count"] * duration_tol
        elif name == "cadence_per_s":
            n, total = expected_summary["valid_count"], expected_summary["active_s"]
            delta = n * duration_tol
            tolerance = 1e-12 if path == "E" else n * delta / (total * (total - delta))
        error(f"summary.{name}", actual, expected_value, tolerance, "s" if name == "active_s" else
              "s^-1" if name == "cadence_per_s" else "1" if name == "rom_cv" else "rad")
    return dict(id=f"{trajectory}/CLEAN-{path}/SAME/0", trajectory=trajectory, path=path, seed=0, intended_class="C",
                source_type="synthetic", anatomical_eligible=False, passed=not failed, failed_gates=failed,
                stage_disposition="complete", counts=dict(truth=expected_summary["valid_count"],
                valid=session_summary.valid_count, missed=len(missed_ids), false=len(false_ids)),
                coverage=dict(relative=relative_coverage, proxy=proxy_coverage, valid_duration_s=valid_duration,
                invalid_duration_s=elapsed - valid_duration, denominator_s=elapsed,
                recall=(expected_summary["valid_count"] - len(missed_ids)) / expected_summary["valid_count"]
                if expected_summary["valid_count"] else None),
                matches=matches, missed_truth_ids=missed_ids, false_candidate_ids=false_ids,
                unmatched_truth_ids=[nominal[i]["truth_id"] for i in sorted(unmatched)], errors=errors,
                annotations=dict(nominal=nominal, summary=expected_summary),
                processed=dict(evaluation_window_us=window, segmentation_context_window_us=segmentation_window,
                nodes=nodes, relative=plain(relative), elevation=plain(elevation.elevation_rad),
                elevation_valid=plain(elevation.valid), elevation_reason=elevation.reason,
                speed=record(speed, "elevation_result"), trace=plain(trace)),
                derived=dict(segmentation=record(segmentation, "elevation_result", "angular_speed_result"),
                repetitions=[plain(r) for r in metrics.repetitions],
                proxy=[record(p, "repetition") for p in thorax.repetitions],
                summary=record(session_summary, "input_result")), _summary=session_summary)


def export(output: Path, *, formal: bool = True) -> bool:
    """Claim a new output root, run all 30 frozen clean cases, retain failures."""
    output = output.resolve()
    if output.exists():
        raise FileExistsError(output)
    if output == ROOT or output.is_relative_to(ROOT / "datasets"):
        raise ValueError("output root must be outside source datasets")
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    if formal and dirty:
        raise ValueError("formal CP2 requires clean committed tracked code")
    source_files = [str(p.relative_to(ROOT)).replace("\\", "/") for p in sorted(
        (ROOT / "kineimu_shoulder").rglob("*.py"))]
    source_files += ["uv.lock", "protocols/M5_VALIDATION_CONTRACT.md", "tests/fixtures/M5_KNOWN_SENSOR_MOTIONS.md",
                     "datasets/samples/m6_synthetic/case-manifest.json", "examples/m5_baseline.py"]
    previous_attempts_path = "experiments/M5_CP2_20260926/partial-attempts.json"
    if (ROOT / previous_attempts_path).exists():
        source_files.append(previous_attempts_path)
    tracked = set(git("ls-files").splitlines())
    if formal and any(name not in tracked for name in source_files):
        raise ValueError("formal CP2 requires every processing/source file in the committed code lock")
    pinned = {"numpy": "2.5.2", "scipy": "1.18.1", "pandas": "3.0.5", "imufusion": "1.3.3", "imucal": "2.6.0"}
    if formal and (platform.python_version() != "3.12.14" or any(version(p) != v for p, v in pinned.items())):
        raise ValueError("formal CP2 requires the frozen Python/AHRS/calibration versions")
    output.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}

    def write(name: str, value: Any) -> None:
        content = canonical(value)
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
        hashes[name] = sha256(content).hexdigest()

    def compact(result: dict[str, Any]) -> dict[str, Any]:
        trimmed = {key: value for key, value in result.items() if key != "errors"}
        trimmed["error_summary"] = {name: {key: row[key] for key in
            ("n", "max_abs_error", "rmse", "tolerance", "unit", "gate")}
            for name, row in result.get("errors", {}).items()}
        return trimmed

    selected = [row for row in cases() if row["condition"].startswith("CLEAN-")]
    write("manifest.json", dict(schema_version="m5-report/1.0", checkpoint="CP2", formal=formal,
        git_commit=git("rev-parse", "HEAD"), tracked_dirty=dirty, configuration=plain(CONFIG),
        previous_attempts_artifact=previous_attempts_path if previous_attempts_path in source_files else None,
        source_type="synthetic", anatomical_eligible=False, case_ids=[r["id"] for r in selected],
        source_file_sha256={name: sha256((ROOT / name).read_bytes()).hexdigest() for name in source_files},
        runtime=dict(python=platform.python_version(), platform=platform.platform(),
                     packages={p: version(p) for p in pinned}),
        backend="fresh Ahrs; synthetic initial q_WN; skip_startup; defaults not exposed; no magnetometer",
        warmup_window_us=[0, 5000000], grid_step_us=10000, interpolation="explicit SLERP",
        max_interpolation_gap_us=50000, max_ahrs_gap_s=.05, max_timing_uncertainty_us=2000,
        units=dict(angle="rad", speed="rad/s", time="us", duration="s")))
    results, summaries = [], {}
    for case in selected:
        trajectory, path = case["trajectory"], case["path"]
        folder = output / trajectory / path
        folder.mkdir(parents=True)
        try:
            result = run_case(trajectory, path, folder)
            summaries[trajectory, path] = result.pop("_summary")
            for name in ("processed", "derived", "annotations"):
                write(f"{trajectory}/{path}/{name}.json", result.pop(name))
            write(f"{trajectory}/{path}/result.json", result)
        except Exception as exc:
            result = dict(id=case["id"], passed=False, stage_disposition="unexpected_exception",
                          exception_type=type(exc).__name__, message=str(exc), failed_gates=["execution"])
            write(f"{trajectory}/{path}/result.json", result)
        results.append(compact(result))
    comparisons = []
    for path in ("E", "S"):
        if ("F90", path) in summaries and ("F90-NEXT", path) in summaries:
            pair = compare_summaries([summaries["F90", path], summaries["F90-NEXT", path]])[0]
            truth = summary("F90-NEXT")["rom_mean_rad"] - summary("F90")["rom_mean_rad"]
            observed = pair.differences["rom_rad"][0].difference.value if pair.differences else None
            tolerance = 2e-10 if path == "E" else 2 * math.pi / 90
            passed = pair.comparable and observed is not None and abs(observed - truth) <= tolerance
            comparisons.append(dict(path=path, record=record(pair, "earlier", "later"),
                                    expected_rom_difference_rad=truth, tolerance=tolerance, passed=passed))
    passed = len(results) == 30 and all(r["passed"] for r in results) and len(comparisons) == 2 and all(
        c["passed"] for c in comparisons)
    evidence_index = {row["id"]: {kind: dict(path=f"{row['trajectory']}/{row['path']}/{kind}.json",
        sha256=hashes.get(f"{row['trajectory']}/{row['path']}/{kind}.json"))
        for kind in ("processed", "derived", "annotations", "result")} for row in selected}
    requirement_index = {name: [r["id"] for r in selected] for name in
        ("ROM/peak", "repetitions/exclusions", "phase/hold/rest durations", "3D speed", "ROM variability",
         "thorax excursion proxy", "QC/evidence/coverage", "calibration/AHRS initialization")}
    requirement_index["longitudinal comparison"] = [f"{t}/CLEAN-{p}/SAME/0"
        for t in ("F90", "F90-NEXT") for p in ("E", "S")]
    worst = sorted([dict(case=r["id"], metric=name, **row) for r in results
                    for name, row in r["error_summary"].items() if row["gate"] and row["max_abs_error"] is not None
                    and row["tolerance"] > 0],
                   key=lambda row: row["max_abs_error"] / row["tolerance"], reverse=True)[:20]
    write("report.json", dict(schema_version="m5-report/1.0", checkpoint="CP2", passed=passed,
        case_count=len(results), failed_case_count=sum(not r["passed"] for r in results), not_run_count=0,
        failed_comparison_count=sum(not c["passed"] for c in comparisons),
        results=results, comparisons=comparisons, requirement_index=requirement_index, evidence_index=evidence_index,
        worst_normalized_errors=worst,
        limitations="Synthetic numerical/evidence scope; no physical/anatomical/clinical validation. CP3-CP5 open."))
    # Bind Q capture bytes too, including partial inputs, excluding the manifest itself.
    for capture in output.rglob("*.kimu"):
        hashes[str(capture.relative_to(output)).replace("\\", "/")] = sha256(capture.read_bytes()).hexdigest()
    write("SHA256SUMS.json", hashes.copy())
    return passed
