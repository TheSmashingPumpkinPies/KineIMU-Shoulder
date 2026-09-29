"""Validation-only CP3 orchestration derived from the locked CP2 runner.

Production stages compute observations. Independent oracle matrices/labels supply
expectations. Failures stay in reports and prevent checkpoint acceptance.
"""

from __future__ import annotations

import gzip
import json
import math
import platform
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from dataclasses import fields, is_dataclass, replace
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree

import numpy as np
from scipy.spatial.transform import Rotation  # type: ignore[import-untyped]

from kineimu_shoulder.calibration import (
    CalibrationArtifact,
    StationarityCriteria,
    apply_calibration,
    estimate_gyro_bias,
)
from kineimu_shoulder.exercise import ExerciseConfig, compute_repetition_metrics, segment_shoulder_repetitions
from kineimu_shoulder.io.m1_capture import encode_capture_record
from kineimu_shoulder.io.m1_packet import NodeId, SampleFlags, encode_sample_packet
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorToNodeTransform
from kineimu_shoulder.io.m2_replay import replay_capture
from kineimu_shoulder.orientation import align_segment, estimate_orientation
from kineimu_shoulder.reconstruction import reconstruct_short_gaps
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
from kineimu_shoulder.validation.baseline import (
    canonical,
    digest,
    distance,
    exact_orientation,
    matrix,
    plain,
    quaternion,
    record,
)
from kineimu_shoulder.validation.manifest import cases, perturbation_for
from kineimu_shoulder.validation.motions import MOTIONS
from kineimu_shoulder.validation.oracle import (
    labels,
    observation_labels,
    proxy,
    segment_matrix,
    sensor_reference,
    summary,
)
from kineimu_shoulder.validation.source import DualSource, generate, packets

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = (1.0, 0.0, 0.0, 0.0)
CONFIG = ExerciseConfig(50000, max_thorax_drift_rad=math.pi / 180)


def _session(
    case: dict[str, Any], source: DualSource, workspace: Path, state: dict[str, Any],
    *, stored_captures: dict[str, tuple[Path, str]] | None = None,
) -> dict[str, Any]:
    """Execute one entire clean session; return evidence even when gates fail."""
    trajectory, path = case["trajectory"], case["path"]
    working = not case["condition"].startswith("CLEAN-") and case["condition"] != "C-APPLY"
    exact = path == "E" and not working
    parameters = case["parameters"]
    if trajectory not in MOTIONS or path not in ("E", "S", "Q"):
        raise ValueError("unknown baseline trajectory/path")
    motion = MOTIONS[trajectory]
    side = cast(Side, motion.side)
    window = (motion.analysis_start_us, motion.analysis_end_us or motion.end_us)
    segmentation_window = window if trajectory == "PARTIAL" else (0, window[1])
    grid = np.arange(segmentation_window[0], window[1] + 1, 10000, dtype=np.int64)
    nodes: dict[str, Any] = {}
    streams, maps, alignments, calibration_hashes = [], [], [], []
    errors: dict[str, Any] = {}
    failed: list[str] = []
    angle_tol = 1e-10 if exact else math.pi / (60 if working else 180)
    speed_tol = 1e-10 if exact else math.pi / (30 if working else 90)
    duration_tol = 1e-12 if exact else 0.20 if working else 0.10
    boundary_tol = 0 if exact else 100000 if working else 50000

    def error(
        name: str, actual: Any, expected: Any, tolerance: float, unit: str, *, gate: bool = True, support: Any = None
    ) -> None:
        a = np.asarray(actual, dtype=float).reshape(-1)
        e = np.asarray(expected, dtype=float).reshape(-1)
        if a.shape != e.shape:
            raise ValueError(f"error support mismatch: {name}")
        valid = np.isfinite(a) & np.isfinite(e)
        delta = a - e
        maximum = float(np.max(np.abs(delta[valid]))) if valid.any() else None
        errors[name] = dict(
            actual=plain(a),
            expected=plain(e),
            signed_error=plain(delta),
            absolute_error=plain(np.abs(delta)),
            n=int(valid.sum()),
            support=plain(support),
            max_abs_error=maximum,
            rmse=float(np.sqrt(np.mean(delta[valid] ** 2))) if valid.any() else None,
            tolerance=tolerance,
            unit=unit,
            gate=gate,
        )
        if gate and ((not valid.all() and not working) or maximum is None or maximum > tolerance):
            failed.append(name)

    state.update(nodes=nodes, errors=errors)
    for node, row in source.nodes.items():
        state["stage"] = "source"
        node_id = NodeId.A if node == "A" else NodeId.B
        transform = SensorToNodeTransform(
            ("SX", "SY", "SZ"),
            ("NX", "NY", "NZ"),
            cast(tuple[tuple[float, float, float], ...], tuple(tuple(float(x) for x in v) for v in row.r_ns)),
            "M5 O3 fixed proper R_NS; node=R_NS sensor",
        )
        config = M1RawCountAdapterConfig(4, 500, 0.122, 17.5, transform)
        times, force, rate = row.device_time_us, row.force_mps2, row.rate_rads
        flags = (SampleFlags(0),) * len(times)
        mutation = parameters.get("mutation", "")
        if node == "B" and mutation in ("accel-clipped", "gyro-clipped"):
            flag_values = list(flags)
            flag_values[650] = SampleFlags.ACCEL_CLIPPED if mutation == "accel-clipped" else SampleFlags.GYRO_CLIPPED
            flags = tuple(flag_values)
        raw_record: dict[str, Any] = dict(
            sequence=row.sequence,
            nominal_time_us=row.nominal_time_us,
            true_time_us=row.true_time_us,
            claimed_time_us=row.claimed_time_us,
            device_time_us=times,
            retained_mask=row.retained_mask,
            acceleration_mps2=force,
            angular_rate_rads=rate,
        )
        replay_metadata = None
        if path == "Q":
            state["stage"] = "replay"
            if stored_captures is None:
                payload = b"".join(
                    encode_capture_record(encode_sample_packet(p),
                                          host_monotonic_ns=p.samples[-1].device_time_us * 1000)
                    for p in packets(row, node)
                )
                capture = workspace / f"{trajectory}-{node}.kimu"
                with capture.open("xb") as stream:
                    stream.write(payload)
                raw_hash = sha256(payload).hexdigest()
            else:
                capture, raw_hash = stored_captures[node]
            replay = replay_capture(capture, expected_sha256=raw_hash, expected_node_id=node_id, config=config)
            epoch = replay.epochs[0]
            data = epoch.sensor_data
            times = np.asarray(data.device_time_us, dtype=np.int64)
            force, rate, flags = data.accel_mps2, data.gyro_rads, data.sample_flags
            raw_record.update(
                device_time_us=times,
                acceleration_mps2=force,
                angular_rate_rads=rate,
                accel_raw_counts=data.accel_raw_counts,
                gyro_raw_counts=data.gyro_raw_counts,
            )
            replay_metadata = dict(
                source_sha256=raw_hash,
                qc=plain(replay.qc),
                packet_sequences=epoch.packet_sequences,
                sample_sequences=data.sample_sequences,
                source_hash_after=sha256(capture.read_bytes()).hexdigest(),
            )
            if replay_metadata["source_hash_after"] != raw_hash:
                failed.append(f"{node}.raw_immutable")
        if path == "E":
            raw_record["exact_quaternion_wsegment"] = (
                row.q_wk
                if source.perturbation.heading_rate_rads
                else exact_orientation(trajectory, node, row.nominal_time_us)
            )
            raw_record["input_recipe"] = (
                "post-alignment world yaw left-multiply isolation; synthetic E"
                if source.perturbation.heading_rate_rads
                else "integer/rational grid axis-angle; exact E isolation"
            )
        source_hash = digest(raw_record)
        # Known parameters originate in the frozen contract, not evaluation
        # motion. Equal artifacts must stay comparable; raw hashes stay lineage.
        parameter_source_hash = sha256((ROOT / "protocols/M5_VALIDATION_CONTRACT.md").read_bytes()).hexdigest()
        artifact = CalibrationArtifact(
            f"m5-cal-{node}",
            node_id,
            "synthetic-LSM6DS3TR-C",
            config,
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            "declared clean SI parameters; no fit on evaluation motion",
            (0, 5000000),
            (parameter_source_hash,),
            "synthetic",
        )
        fit_record = None
        if parameters.get("calibration"):
            artifact = replace(
                artifact,
                accel_matrix=((1.02, 0.0, 0.0), (0.0, 0.98, 0.0), (0.0, 0.0, 1.01)),
                accel_bias_mps2=(0.02, -0.01, 0.03),
                gyro_bias_rads=(0.001, -0.002, 0.003),
            )
        if parameters.get("fit_gyro"):
            state["stage"] = "calibration_fit"
            selection = row.true_time_us <= 5000000
            bias = estimate_gyro_bias(
                force[selection],
                rate[selection],
                times[selection],
                criteria=StationarityCriteria(500, 4.0, 0.1, 0.05, 0.05),
            )
            expected_bias = np.array([0.0, 0.0, parameters["bias_rads"]])
            residual = float(np.linalg.norm(bias - expected_bias))
            fit_record = dict(
                residual_norm_rads=residual,
                expected_bias_rads=expected_bias.tolist(),
                observed_bias_rads=bias.tolist(),
                fit_window_us=[0, 5000000],
            )
            if residual > 0.001:
                failed.append(f"{node}.fit_bias")
            artifact = replace(
                artifact,
                gyro_bias_rads=cast(tuple[float, float, float], tuple(float(x) for x in bias)),
                fit_method="independent frozen stationary window gyro mean",
                source_sha256=(digest(dict(force=force[selection], rate=rate[selection], times=times[selection])),),
            )
        nodes[node] = dict(
            source=plain(raw_record),
            calibration=plain(artifact),
            calibration_fit=fit_record,
            source_sha256=source_hash,
            replay=plain(replay_metadata),
        )
        state["stage"] = "calibration"
        calibrated_acc = calibrated_rate = orientation = reconstruction = None
        stream_times = times
        if path == "E":
            aligned = raw_record["exact_quaternion_wsegment"]
        else:
            calibrated_acc, calibrated_rate = apply_calibration(
                force,
                rate,
                artifact=artifact,
                node_id=node_id,
                sensor_id=artifact.sensor_id,
                config=config,
                sample_flags=flags,
            )
            if parameters.get("calibration"):
                calibration_reference = [sensor_reference(trajectory, node, int(t) / 1e6) for t in row.true_time_us]
                expected_acc = np.array([r[0] for r in calibration_reference]) @ row.r_ns.T
                ideal_row = generate(trajectory).nodes[node]
                expected_rate = ideal_row.rate_rads @ row.r_ns.T
                error(
                    f"{node}.oracle_rate_crosscheck",
                    expected_rate,
                    np.array([r[1] for r in calibration_reference]) @ row.r_ns.T,
                    1e-8,
                    "rad/s",
                    gate=False,
                )
                error(f"{node}.calibration_acceleration", calibrated_acc, expected_acc, 1e-12, "m/s^2")
                error(f"{node}.calibration_rate", calibrated_rate, expected_rate, 1e-12, "rad/s")
            state["stage"] = "ahrs"
            reconstruction = reconstruct_short_gaps(times, calibrated_acc, calibrated_rate, max_gap_s=0.05)
            stream_times = reconstruction.timestamp_us
            orientation = estimate_orientation(
                stream_times, reconstruction.acceleration_mps2, reconstruction.angular_rate_rads,
                max_gap_s=0.05, initial_quaternion_wn=row.q_wn[0],
            )
            aligned = np.asarray([align_segment(q, quaternion(row.r_nk)) for q in orientation.quaternion_wn])
        observed_aligned = aligned if reconstruction is None else aligned[reconstruction.observed_indices]
        # Truth is independently reconstructed from O/F/T matrices, never source q arrays.
        geodesic = [
            distance(segment_matrix(trajectory, node, int(t) / 1e6), r)
            for t, r in zip(row.true_time_us, matrix(observed_aligned), strict=True)
        ]
        selected = (row.true_time_us >= window[0]) & (row.true_time_us <= window[1])
        error(
            f"{node}.orientation",
            np.asarray(geodesic)[selected],
            np.zeros(int(selected.sum())),
            1e-12 if exact else math.pi / (180 if working else 450),
            "rad",
            support=row.true_time_us[selected],
        )
        error(
            f"{node}.initialization",
            [{int(t): g for t, g in zip(row.true_time_us, geodesic, strict=True)}.get(t, np.nan) for t in (0, 5000000)],
            [0.0, 0.0],
            1e-12 if exact else math.pi / (180 if working else 450),
            "rad",
            support=[0, 5000000],
        )
        stream_record = SegmentOrientationStream(
            node, f"clock-{node}", 0, "synthetic-M5-world", source_hash, stream_times, aligned
        )
        lo, hi = int(times[0]), int(times[-1])
        clock = ClockMap(
            node,
            stream_record.clock_id,
            0,
            row.clock_scale,
            row.clock_offset_us,
            lo,
            hi,
            lo,
            hi,
            1.0,
            1.0,
            "known synthetic construction",
            source_hash,
            "supported",
        )
        if parameters.get("map_control") == "wrong" and node == "B":
            clock = replace(clock, slope=1.0, intercept_us=0.0)
        alignment = AlignmentRecord(
            node,
            0,
            "T" if node == "A" else "H",
            side,
            cast(tuple[float, float, float, float], tuple(float(v) for v in quaternion(row.r_nk))),
            f"m5-align-{node}",
            "known synthetic R_NK applied once after AHRS",
            source_hash,
            "H +Z proximal; T +Z superior",
            "current",
            "fixed synthetic mount",
            False,
            "synthetic exact construction",
            "supported",
            "synthetic_ground_truth",
        )
        streams.append(stream_record)
        maps.append(clock)
        alignments.append(alignment)
        calibration_hashes.append(digest(artifact))
        nodes[node] = dict(
            source=plain(raw_record),
            source_sha256=source_hash,
            replay=plain(replay_metadata),
            calibration_fit=fit_record,
            retention=retention(row),
            calibration=plain(artifact),
            calibration_executed=path != "E",
            ahrs_executed=path != "E",
            calibrated_acceleration_mps2=plain(calibrated_acc),
            calibrated_rate_rads=plain(calibrated_rate),
            orientation=plain(orientation),
            reconstruction=plain(reconstruction),
            observed_quaternion_wsegment=plain(observed_aligned),
            aligned_segment_stream=plain(stream_record),
            alignment=plain(alignment),
            clock_map=plain(clock),
        )
    a, b = streams
    aa, ba = alignments
    ca, cb = maps
    heading = HeadingRelation(
        a.world_id, b.world_id, IDENTITY, "known synthetic common world", digest(IDENTITY), "supported"
    )
    evidence_source_hashes = (ca.source_sha256, cb.source_sha256, heading.source_sha256)
    context_alignments = alignments.copy()
    state["stage"] = "evidence"
    a, b, ca, cb, aa, ba, heading = evidence_inputs(case, a, b, ca, cb, aa, ba, heading)
    state["stage"] = "relative"
    relative = relative_orientation(
        a,
        b,
        common_time_us=grid,
        thorax_clock_map=ca,
        humerus_clock_map=cb,
        heading_relation=heading,
        evidence_source_sha256=evidence_source_hashes,
        max_interpolation_gap_us=50000,
        max_timing_uncertainty_us=2000.0,
    )
    state["stage"] = "kinematics"
    shared = dict(
        thorax_alignment=aa, humerus_alignment=ba, side=side, source_type="synthetic", max_sample_gap_us=50000
    )
    elevation = long_axis_elevation(relative, **shared)
    speed = relative_angular_speed(relative, **shared)
    truth_relative = [
        segment_matrix(trajectory, "A", int(t) / 1e6).T @ segment_matrix(trajectory, "B", int(t) / 1e6) for t in grid
    ]
    truth_elevation = [math.atan2(float(np.linalg.norm(r[:2, 2])), float(r[2, 2])) for r in truth_relative]
    truth_speed = [
        distance(x, y) / ((int(t1) - int(t0)) / 1e6)
        for x, y, t0, t1 in zip(truth_relative[:-1], truth_relative[1:], grid[:-1], grid[1:], strict=True)
    ]
    evaluation_rows = grid >= window[0]
    evaluation_intervals = grid[:-1] >= window[0]
    error(
        "elevation",
        elevation.elevation_rad[evaluation_rows],
        np.asarray(truth_elevation)[evaluation_rows],
        angle_tol,
        "rad",
        support=grid[evaluation_rows],
    )
    error(
        "interval_speed",
        speed.relative_angular_speed_rads[evaluation_intervals],
        np.asarray(truth_speed)[evaluation_intervals],
        speed_tol,
        "rad/s",
        support=list(zip(grid[:-1][evaluation_intervals], grid[1:][evaluation_intervals], strict=True)),
    )
    state["stage"] = "segmentation"
    segmentation = segment_shoulder_repetitions(
        elevation,
        speed,
        exercise="abduction" if trajectory in ("AL90", "AR90", "WRONG") else "flexion",
        side=side,
        configuration=CONFIG,
        analysis_window_us=segmentation_window,
        session_id=case["id"],
        protocol_id="m5-perturbation",
        protocol_version="1.0",
        calibration_sha256=(calibration_hashes[0], calibration_hashes[1]),
        processing_sha256=digest({"backend": path, "config": CONFIG.sha256, "processing_version": "m5-processing/1.1"}),
    )
    state["stage"] = "metrics"
    metrics = compute_repetition_metrics(segmentation)
    affected_a = source.perturbation.target in ("A", "SAME", "DIFF")
    drift_bound = abs(source.perturbation.heading_rate_rads) * (window[1] - window[0]) / 1e6 if affected_a else 0.0
    state["stage"] = "thorax"
    trace = prepare_thorax_common_grid(
        a,
        common_time_us=grid,
        clock_map=ca,
        alignment=aa,
        calibration_sha256=calibration_hashes[0],
        configuration=CONFIG,
        max_timing_uncertainty_us=2000.0,
        heading_evidence=ThoraxHeadingEvidence(
            a.world_id, "known synthetic heading", digest(IDENTITY), window, "supported"
        ),
        drift_evidence=ThoraxDriftEvidence(
            a.world_id,
            "known injected yaw bound over evaluation window",
            digest(IDENTITY),
            window,
            drift_bound,
            "supported",
        ),
    )
    state["stage"] = "evidence_trace"
    trace = evidence_trace(case, trace)
    thorax = compute_thorax_excursion(metrics, trace=trace)
    context = SummaryContext(
        "2026-09-27T00:00:00Z" if trajectory == "F90-NEXT" else "2026-09-26T00:00:00Z",
        ("m5-cal-A", "m5-cal-B"),
        cast(tuple[str, str], tuple(digest(record(v, "source_sha256")) for v in context_alignments)),
        ("exact" if path == "E" else "imufusion", "1.0" if path == "E" else version("imufusion"), CONFIG.sha256),
        ("explicit common grid SLERP", "10000us/50000us/2000us"),
        ("m5-sensor-source", "1.0"),
    )
    state["stage"] = "summary"
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
            intersection = max(
                0, min(candidate.end_us, truth["physical_end_us"]) - max(candidate.start_us, truth["physical_start_us"])
            )
            union = max(candidate.end_us, truth["physical_end_us"]) - min(
                candidate.start_us, truth["physical_start_us"]
            )
            if intersection / union >= 0.5:
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
        matches.append(
            dict(
                candidate_id=candidate.id,
                truth_id=prefix,
                valid=candidate.valid,
                eligible=truth["eligible"],
                reasons=candidate.reasons,
                duplicate_overlaps=overlaps[1:],
            )
        )
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
        error(
            f"{prefix}.start_confirmation",
            candidate.start_confirmation_us[-1] if candidate.start_confirmation_us else np.nan,
            truth["confirm_start_us"],
            boundary_tol,
            "us",
        )
        error(
            f"{prefix}.end_confirmation",
            candidate.end_confirmation_us[-1] if candidate.end_confirmation_us else np.nan,
            truth["confirm_end_us"],
            boundary_tol,
            "us",
        )
        p0, p1 = truth["plateau_support_us"]
        error(f"{prefix}.peak_support", max(p0 - candidate.peak_us, candidate.peak_us - p1, 0), 0, boundary_tol, "us")
        error(f"{prefix}.earliest_peak", candidate.peak_us, truth["peak_us"], boundary_tol, "us", gate=exact)
        error(
            f"{prefix}.plane_fraction",
            candidate.plane_fraction,
            1.0,
            1e-12 if exact else 0.05 if working else 0.02,
            "1",
        )
        expected = dict(
            rom_rad=truth["rom_rad"],
            peak_elevation_rad=truth["peak_rad"],
            rep_duration_s=truth["duration_s"],
            elevation_duration_s=truth["rise_s"],
            return_duration_s=truth["return_s"],
            hold_duration_s=truth["hold_s"],
            rep_speed_mean_rads=truth["mean_speed_rads"],
            rep_speed_max_rads=truth["max_speed_rads"],
        )
        # Frozen ownership: estimated maximum can move inside physical plateau.
        # The held plateau intervals are removed from both phases independently.
        peak = truth["peak_us"] if exact else min(p1, max(p0, candidate.peak_us))
        expected["elevation_duration_s"] += (peak - p0) / 1e6 if truth["hold_s"] == 0 else 0
        expected["return_duration_s"] -= (peak - p0) / 1e6 if truth["hold_s"] == 0 else 0
        cycle = motion.cycles[index]
        rise_speed = cycle.peak_deg * math.pi / 180 * 1e6 / cycle.rise_us
        return_speed = cycle.peak_deg * math.pi / 180 * 1e6 / cycle.return_us
        expected.update(
            elevation_speed_mean_rads=rise_speed,
            elevation_speed_max_rads=rise_speed,
            return_speed_mean_rads=return_speed,
            return_speed_max_rads=return_speed,
        )
        if truth["hold_s"]:
            expected.update(hold_speed_mean_rads=0.0, hold_speed_max_rads=0.0)
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
            tolerance = (
                speed_tol
                if metric_value.unit == "rad/s"
                else duration_tol
                if metric_value.unit == "s"
                else (angle_tol * 2 if name == "rom_rad" and not exact else angle_tol)
            )
            error(f"{prefix}.{name}", metric_value.value, expected_value, tolerance, metric_value.unit)
            aggregate_truth.setdefault(name, []).append(expected_value)
            aggregate_tolerances[name] = tolerance
        error(
            f"{prefix}.phase_conservation",
            sum(
                getattr(rep.metrics, name).value
                for name in ("elevation_duration_s", "return_duration_s", "hold_duration_s")
            ),
            rep.metrics.rep_duration_s.value,
            1e-12,
            "s",
        )
        selected_times = grid[(grid >= candidate.start_us) & (grid <= candidate.end_us)]
        # Independently evaluate nominal and estimated endpoint supports separately.
        for support_name, begin, end in (
            ("nominal", truth["start_us"], truth["end_us"]),
            ("estimated", candidate.start_us, candidate.end_us),
        ):
            times_support = grid[(grid >= begin) & (grid <= end)]
            indices = [int(np.searchsorted(grid, t)) for t in times_support[:-1]]
            reference = np.asarray(truth_speed)[indices]
            error(
                f"{prefix}.speed_{support_name}_mean",
                rep.metrics.rep_speed_mean_rads.value,
                np.mean(reference),
                speed_tol,
                "rad/s",
                support=[begin, end],
            )
        if not thorax_rep.extension.valid:
            if drift_bound <= math.pi / 180:
                failed.append(f"{prefix}.proxy_unavailable")
            elif "thorax_drift_exceeded" not in thorax_rep.reasons:
                failed.append(f"{prefix}.proxy_expected_drift_exclusion")
            continue
        p = proxy(trajectory, candidate.start_us, selected_times.tolist())
        nominal_times = grid[(grid >= truth["start_us"]) & (grid <= truth["end_us"])]
        nominal_proxy = proxy(trajectory, truth["start_us"], nominal_times.tolist())
        for component_index, component_name in enumerate(("extension", "lateral_flexion", "axial_rotation")):
            component = getattr(thorax_rep, component_name)
            for attribute, value in (
                ("min_rad", float(p[:, component_index].min())),
                ("max_rad", float(p[:, component_index].max())),
                ("magnitude_rad", float(np.abs(p[:, component_index]).max())),
            ):
                nominal_component = nominal_proxy[:, component_index]
                nominal_value = (
                    float(nominal_component.min())
                    if attribute == "min_rad"
                    else float(nominal_component.max())
                    if attribute == "max_rad"
                    else float(np.abs(nominal_component).max())
                )
                error(
                    f"{prefix}.proxy.{component_name}.{attribute}",
                    getattr(component, attribute),
                    nominal_value,
                    angle_tol,
                    "rad",
                    support=[truth["start_us"], truth["end_us"]],
                )
                error(
                    f"{prefix}.proxy_estimated_support.{component_name}.{attribute}",
                    getattr(component, attribute),
                    value,
                    angle_tol,
                    "rad",
                    support=[candidate.start_us, candidate.end_us],
                )
                key = f"thorax_{component_name}_{attribute}"
                aggregate_truth.setdefault(key, []).append(nominal_value)
                aggregate_tolerances[key] = angle_tol
    missed_ids = [
        r["truth_id"]
        for i, r in enumerate(nominal)
        if r["eligible"]
        and (i in unmatched or not any(m.get("truth_id") == r["truth_id"] and m.get("valid") for m in matches))
    ]
    if missed_ids or false_ids or session_summary.valid_count != expected_summary["valid_count"]:
        failed.append("counts")
    if segmentation.detected_count != len(nominal):
        failed.append("detected_count")
    elapsed = (window[1] - window[0]) / 1e6
    valid_duration = (
        sum(
            int(y) - int(x)
            for x, y, valid in zip(grid[:-1], grid[1:], speed.valid, strict=True)
            if valid and x >= window[0]
        )
        / 1e6
    )
    relative_coverage = valid_duration / elapsed
    proxy_coverage = (
        (session_summary.proxy_valid_count or 0) / session_summary.valid_count if session_summary.valid_count else None
    )
    if relative_coverage < (0.98 if working else 1.0) or (
        drift_bound <= math.pi / 180 and session_summary.valid_count and proxy_coverage != 1.0
    ):
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
    rom_epsilon = 1e-10 if exact else 2 * angle_tol
    for name, actual in (
        (
            "rom_mean_rad",
            session_summary.statistics["rom_rad"][0].mean.value
            if session_summary.statistics.get("rom_rad")
            else np.nan,
        ),
        (
            "rom_max_rad",
            session_summary.statistics["rom_rad"][0].maximum.value
            if session_summary.statistics.get("rom_rad")
            else np.nan,
        ),
        ("rom_range_rad", session_summary.rom_range.value),
        ("rom_sd_rad", session_summary.rom_sd.value),
        ("rom_cv", session_summary.rom_cv.value),
        ("active_s", session_summary.active_time_s.value),
        ("cadence_per_s", session_summary.active_cadence.value),
    ):
        # Existing M4 defines empty active time as the valid sum of zero reps.
        expected_value = 0.0 if name == "active_s" and not expected_summary["valid_count"] else expected_summary[name]
        if expected_value is None:
            if math.isfinite(actual):
                failed.append(f"summary.{name}.null")
            continue
        tolerance = rom_epsilon
        if name in ("rom_range_rad", "rom_sd_rad"):
            tolerance = 1e-10 if exact else 2 * rom_epsilon
        elif name == "rom_cv":
            mu, sd = expected_summary["rom_mean_rad"], expected_summary["rom_sd_rad"]
            tolerance = (
                1e-12
                if exact
                else 2 * rom_epsilon / (mu - rom_epsilon) + (sd * rom_epsilon / (mu * (mu - rom_epsilon)))
            )
        elif name == "active_s":
            tolerance = expected_summary["valid_count"] * duration_tol
        elif name == "cadence_per_s":
            n, total = expected_summary["valid_count"], expected_summary["active_s"]
            delta = n * duration_tol
            tolerance = 1e-12 if exact else n * delta / (total * (total - delta))
        error(
            f"summary.{name}",
            actual,
            expected_value,
            tolerance,
            "s" if name == "active_s" else "s^-1" if name == "cadence_per_s" else "1" if name == "rom_cv" else "rad",
        )
    proxy_reasons = sorted({reason for rep in thorax.repetitions for reason in rep.reasons})
    return dict(
        id=case["id"],
        trajectory=trajectory,
        path=path,
        seed=case["seed"],
        intended_class=case["class"],
        condition=case["condition"],
        target=case["target"],
        perturbation=plain(source.perturbation),
        accuracy_passed=not failed,
        proxy_reasons=proxy_reasons,
        known_yaw_bound_rad=drift_bound,
        relative_reasons=sorted(set(relative.reason)),
        elevation_reasons=sorted(set(elevation.reason)),
        source_type="synthetic",
        anatomical_eligible=False,
        passed=not failed,
        failed_gates=failed,
        stage_disposition="complete",
        counts=dict(
            truth=expected_summary["valid_count"],
            valid=session_summary.valid_count,
            missed=len(missed_ids),
            false=len(false_ids),
        ),
        coverage=dict(
            relative=relative_coverage,
            proxy=proxy_coverage,
            valid_duration_s=valid_duration,
            invalid_duration_s=elapsed - valid_duration,
            denominator_s=elapsed,
            recall=(expected_summary["valid_count"] - len(missed_ids)) / expected_summary["valid_count"]
            if expected_summary["valid_count"]
            else None,
        ),
        matches=matches,
        missed_truth_ids=missed_ids,
        false_candidate_ids=false_ids,
        unmatched_truth_ids=[nominal[i]["truth_id"] for i in sorted(unmatched)],
        errors=errors,
        annotations=dict(
            nominal=nominal,
            summary=expected_summary,
            observation_grid={
                n: observation_labels(trajectory, r.true_time_us.tolist()) for n, r in source.nodes.items()
            },
        ),
        processed=dict(
            evaluation_window_us=window,
            segmentation_context_window_us=segmentation_window,
            nodes=nodes,
            evidence_reference_source_sha256=evidence_source_hashes,
            relative=plain(relative),
            elevation=plain(elevation.elevation_rad),
            elevation_valid=plain(elevation.valid),
            elevation_reason=elevation.reason,
            speed=record(speed, "elevation_result"),
            trace=plain(trace),
        ),
        derived=dict(
            segmentation=record(segmentation, "elevation_result", "angular_speed_result"),
            repetitions=[plain(r) for r in metrics.repetitions],
            proxy=[record(p, "repetition") for p in thorax.repetitions],
            summary=record(session_summary, "input_result"),
        ),
        _summary=session_summary,
    )


def retention(row: Any) -> dict[str, Any]:
    original = len(row.retained_mask)
    original_packets = (original + 3) // 4
    retained_packets = len(np.unique(row.sequence // 4))
    return dict(
        original_samples=original,
        retained_samples=len(row.sequence),
        lost_samples=original - len(row.sequence),
        original_packets=original_packets,
        retained_packets=retained_packets,
        lost_packets=original_packets - retained_packets,
        sample_fraction=len(row.sequence) / original if original else None,
    )


def evidence_inputs(
    case: dict[str, Any], a: Any, b: Any, ca: Any, cb: Any, aa: Any, ba: Any, heading: Any
) -> tuple[Any, ...]:
    mutation = case["parameters"].get("mutation", "")
    records = {"map-A": ca, "map-B": cb, "align-A": aa, "align-B": ba, "heading": heading}
    for name, item in list(records.items()):
        if mutation == name:
            records[name] = None
        elif mutation.startswith(name + "-"):
            field = mutation[len(name) + 1 :]
            changes: dict[str, Any] = {
                "hash": {"source_sha256": "0" * 64},
                "node": {"node_id": "B" if name.endswith("A") else "A"},
                "epoch": {"epoch": 1},
                "side": {"side": "right"},
                "world": {"world_id": "synthetic-M5-world:wrong"},
                "assumed": {"status": "assumed"},
                "remount": {"remounted": True},
            }
            if field == "expired":
                changes[field] = {"valid_device_end_us": 4999999} if name.startswith("map") else {"validity": "expired"}
            if name == "heading" and field == "world":
                changes[field] = {"humerus_world_id": "synthetic-M5-world:wrong"}
            records[name] = replace(item, **changes[field])
    if mutation.startswith("uncertainty-"):
        records["map-A"] = replace(ca, uncertainty_us=1000.0)
        records["map-B"] = replace(cb, uncertainty_us=float(int(mutation.split("-")[-1]) - 1000))
    return a, b, records["map-A"], records["map-B"], records["align-A"], records["align-B"], records["heading"]


def evidence_trace(case: dict[str, Any], trace: Any) -> Any:
    mutation = case["parameters"].get("mutation", "")
    if mutation == "trace":
        return None
    if mutation.startswith("drift-"):
        if mutation == "drift-uncovered":
            drift = replace(trace.drift_evidence, covered_window_us=(0, labels("F90")[0]["end_us"] - 1))
        else:
            bound = math.pi / 180 + {"below": -1e-6, "equal": 0.0, "above": 1e-6}[mutation.split("-")[1]]
            drift = replace(trace.drift_evidence, bound_rad=bound)
        return prepare_thorax_common_grid(
            trace.original_stream,
            common_time_us=trace.common_time_us,
            clock_map=trace.clock_map,
            alignment=trace.alignment,
            calibration_sha256=trace.calibration_sha256,
            configuration=CONFIG,
            max_timing_uncertainty_us=2000.0,
            heading_evidence=trace.heading_evidence,
            drift_evidence=drift,
        )
    if mutation.startswith("trace-"):
        field = mutation.split("-", 1)[1]
        changes: dict[str, Any] = {
            "node": {"node_id": "B"},
            "hash": {"source_sha256": "0" * 64},
            "epoch": {"epoch": 1},
            "world": {"world_id": "synthetic-M5-world:wrong"},
            "side": {"side": "right"},
        }
        stream = replace(trace.original_stream, **changes[field])
        return prepare_thorax_common_grid(
            stream,
            common_time_us=trace.common_time_us,
            clock_map=trace.clock_map,
            alignment=trace.alignment,
            calibration_sha256=trace.calibration_sha256,
            configuration=CONFIG,
            max_timing_uncertainty_us=2000.0,
            heading_evidence=trace.heading_evidence,
            drift_evidence=trace.drift_evidence,
        )
    return trace


def rejection_expected(case: dict[str, Any], stage: str, exc: Exception) -> bool:
    condition = case["condition"]
    message = str(exc)
    if condition.startswith(("L-S-BURST", "L-P-BURST", "GAP-50001-S")):
        return stage == "ahrs" and isinstance(exc, ValueError) and message == "observed timestamp gap exceeds max_gap_s"
    if condition.startswith(("J-S-X", "J-T-X")):
        return (
            stage == "ahrs"
            and isinstance(exc, ValueError)
            and message == "timestamp_us must increase strictly within an epoch"
        )
    if condition.startswith("EV-") and isinstance(exc, TypeError):
        return stage in ("evidence", "evidence_trace") and "unexpected keyword argument" in message
    expected = {
        "duplicate-time": ("ahrs", "timestamp_us must increase strictly within an epoch"),
        "reverse-time": ("ahrs", "timestamp_us must increase strictly within an epoch"),
        "empty": ("calibration", "acceleration must have shape (N,3) with N>0, got (0, 3)"),
        "nan-force": ("calibration", "acceleration must be finite"),
        "inf-force": ("calibration", "acceleration must be finite"),
        "nan-rate": ("calibration", "gyroscope must be finite"),
        "inf-rate": ("calibration", "gyroscope must be finite"),
        "zero-force": ("ahrs", "acceleration magnitude must be nonzero for six-axis orientation"),
        "accel-range": ("calibration", "sensor values exceed configured range"),
        "gyro-range": ("calibration", "sensor values exceed configured range"),
        "accel-clipped": ("calibration", "clipped samples cannot be used for calibration"),
        "gyro-clipped": ("calibration", "clipped samples cannot be used for calibration"),
    }
    mutation = case["parameters"].get("mutation")
    return isinstance(exc, ValueError) and expected.get(mutation) == (stage, message)


def mutate_source(case: dict[str, Any], source: DualSource) -> DualSource:
    mutation = case["parameters"].get("mutation", "")
    nodes = source.nodes.copy()
    if case["implementation"] == "irregular-grid":
        from kineimu_shoulder.validation.source import _geometry

        for node, row in nodes.items():
            keep = ~((row.nominal_time_us >= 6500000) & (row.nominal_time_us < 6540000))
            times = row.nominal_time_us[keep].copy()
            times[times == 6540000] = 6490000 + case["parameters"]["gap_us"]
            f, g, qs, qk, _, _ = _geometry(case["trajectory"], node, times.astype(float) / 1e6)
            qn = (Rotation.from_quat(qk, scalar_first=True) * Rotation.from_matrix(row.r_nk).inv()).as_quat(
                scalar_first=True
            )
            nodes[node] = replace(
                row,
                sequence=row.sequence[keep],
                nominal_time_us=times,
                true_time_us=times,
                claimed_time_us=times,
                device_time_us=times,
                force_mps2=f,
                rate_rads=g,
                q_ws=qs,
                q_wk=qk,
                q_wn=qn,
                retained_mask=keep,
                clock_rounding_residual_us=row.clock_rounding_residual_us[keep],
            )
    elif case["implementation"] == "input-mutation":
        row = nodes["B"]
        f, g, t = row.force_mps2.copy(), row.rate_rads.copy(), row.device_time_us.copy()
        if mutation in ("empty", "one-row"):
            indices = np.arange(0 if mutation == "empty" else 1)
            changes = {
                k: getattr(row, k)[indices]
                for k in (
                    "sequence",
                    "nominal_time_us",
                    "true_time_us",
                    "claimed_time_us",
                    "device_time_us",
                    "force_mps2",
                    "rate_rads",
                    "q_ws",
                    "q_wk",
                    "q_wn",
                    "clock_rounding_residual_us",
                )
            }
            nodes["B"] = replace(row, **changes)
        else:
            if mutation == "duplicate-time":
                t[650] = t[649]
            elif mutation == "reverse-time":
                t[650] = t[649] - 1
            elif mutation in ("nan-force", "inf-force"):
                f[650, 0] = np.nan if mutation.startswith("nan") else np.inf
            elif mutation in ("nan-rate", "inf-rate"):
                g[650, 0] = np.nan if mutation.startswith("nan") else np.inf
            elif mutation == "zero-force":
                f[650] = 0
            elif mutation == "accel-range":
                f[650, 0] = 50
            elif mutation == "gyro-range":
                g[650, 0] = 10
            nodes["B"] = replace(row, force_mps2=f, rate_rads=g, device_time_us=t)
    return replace(source, nodes=nodes)


def evaluate_evidence(case: dict[str, Any], result: dict[str, Any]) -> bool:
    mutation = case["parameters"]["mutation"]
    relative_reasons = result["relative_reasons"]
    elevation_reasons = result["elevation_reasons"]
    proxy_reasons = result["proxy_reasons"]
    if mutation in ("uncertainty-1999", "uncertainty-2000", "drift-below", "drift-equal") or mutation.endswith(
        "assumed"
    ):
        if not result["accuracy_passed"]:
            return False
        if mutation.endswith("assumed"):
            labels_found = {
                result["processed"]["relative"]["evidence_label"],
                result["processed"]["speed"]["evidence_label"],
            }
            return "Assumed/Experimental" in labels_found
        return True
    if mutation == "trace":
        return (
            result["counts"]["valid"] == 3
            and result["coverage"]["proxy"] == 0
            and "thorax_trace_missing" in proxy_reasons
        )
    if mutation.startswith("trace-"):
        return (
            result["counts"]["valid"] == 3
            and result["coverage"]["proxy"] == 0
            and "thorax_trace_incompatible" in proxy_reasons
        )
    if mutation in ("drift-above", "drift-uncovered"):
        reason = "thorax_drift_exceeded" if mutation == "drift-above" else "thorax_drift_unbounded"
        return result["counts"]["valid"] == 3 and result["coverage"]["proxy"] == 0 and reason in proxy_reasons
    if mutation.startswith("map-"):
        reason = "clock_map_missing" if mutation in ("map-A", "map-B") else "clock_map_incompatible"
        if mutation.endswith("expired"):
            return result["coverage"]["relative"] == 0 and result["counts"]["valid"] in (0, None)
        return result["coverage"]["relative"] == 0 and reason in relative_reasons
    if mutation.startswith("align-"):
        reason = (
            "alignment_missing"
            if mutation in ("align-A", "align-B")
            else ("alignment_expired" if mutation.endswith(("expired", "remount")) else "alignment_incompatible")
        )
        return result["coverage"]["relative"] == 0 and reason in elevation_reasons
    if mutation == "uncertainty-2001":
        return result["coverage"]["relative"] == 0 and "clock_uncertainty" in relative_reasons
    if mutation.startswith("heading"):
        reason = "heading_missing" if mutation == "heading" else "heading_incompatible"
        return result["coverage"]["relative"] == 0 and reason in relative_reasons
    return False


def run(case: dict[str, Any], workspace: Path) -> dict[str, Any]:
    """Retain observations, supports and every failure; expected rejection is stage-specific."""
    workspace.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {"stage": "source"}
    p = perturbation_for(case) if case["implementation"] == "sensor-source" else None
    source = mutate_source(case, generate(case["trajectory"], p))
    try:
        with memoized_session():
            result = _session(case, source, workspace, state)
        result.pop("_summary", None)
        if case["class"] == "stress":
            # Stress completion does not assert accuracy. Bad-time exceptions allowed only above.
            result["passed"] = True
            result["stage_disposition"] = "stress_completed"
            result["limitation"] = (
                "Known injected bias/yaw and dishonest clock maps are not automatically observable by six-axis AHRS."
            )
        elif case["class"] == "evidence":
            result["passed"] = evaluate_evidence(case, result)
            if not result["passed"]:
                result["failed_gates"].append("expected_evidence_disposition")
            result["stage_disposition"] = "evidence_gate" if result["passed"] else "evidence_failure"
        elif case["implementation"] == "irregular-grid" and case["parameters"]["gap_us"] <= 50000:
            # CP1 class boundary freezes stage acceptance, not a new accuracy promise at a knot gap.
            result["passed"] = result["coverage"]["relative"] == 1.0 and result["counts"]["valid"] == 3
            result["stage_disposition"] = "gap_equality_or_below_accepted"
        elif case["condition"] == "GAP-50001-E":
            result["passed"] = "interpolation_gap" in result["relative_reasons"] and result["coverage"]["relative"] < 1
            result["stage_disposition"] = "downstream_gap_boundary"
        elif case["condition"] == "INPUT-one-row":
            result["passed"] = result["coverage"]["relative"] == 0 and result["counts"]["valid"] in (0, None)
        return result
    except Exception as exc:
        expected = rejection_expected(case, state["stage"], exc)
        nominal = labels(case["trajectory"])
        eligible = [r["truth_id"] for r in nominal if r["eligible"]]
        motion = MOTIONS[case["trajectory"]]
        duration = ((motion.analysis_end_us or motion.end_us) - motion.analysis_start_us) / 1e6
        return dict(
            id=case["id"],
            trajectory=case["trajectory"],
            condition=case["condition"],
            target=case["target"],
            path=case["path"],
            seed=case["seed"],
            intended_class=case["class"],
            passed=expected,
            accuracy_passed=False,
            stage_disposition="expected_rejection" if expected else "unexpected_exception",
            exception_stage=state["stage"],
            exception_type=type(exc).__name__,
            message=str(exc),
            failed_gates=[] if expected else ["execution"],
            counts=dict(truth=len(eligible), valid=None, missed=len(eligible), false=0),
            coverage=dict(
                relative=0.0,
                proxy=None,
                recall=0.0 if eligible else None,
                valid_duration_s=0.0,
                invalid_duration_s=duration,
                denominator_s=duration,
            ),
            missed_truth_ids=eligible,
            false_candidate_ids=[],
            matches=[],
            errors=state.get("errors", {}),
            annotations=dict(nominal=nominal, summary=summary(case["trajectory"])),
            processed=dict(nodes=state.get("nodes", {}), rejected_source=plain(source)),
            derived=None,
            source_type="synthetic",
            anatomical_eligible=False,
        )


def _worker(job: tuple[dict[str, Any], str]) -> dict[str, Any]:
    case, folder = job
    result = run(case, Path(folder))
    hashes = {}
    for key in ("processed", "derived", "annotations", "errors"):
        raw = canonical(result.pop(key, None))
        payload = gzip.compress(raw, compresslevel=1, mtime=0)
        filename = key + ".json.gz"
        (Path(folder) / filename).write_bytes(payload)
        hashes[filename] = sha256(payload).hexdigest()
        if key == "errors":
            result["error_summary"] = (
                {
                    n: {k: r[k] for k in ("n", "max_abs_error", "rmse", "tolerance", "unit", "gate")}
                    for n, r in json.loads(raw).items()
                }
                if raw != b"null\n"
                else {}
            )
    payload = canonical(result)
    (Path(folder) / "result.json").write_bytes(payload)
    hashes["result.json"] = sha256(payload).hexdigest()
    for capture in Path(folder).glob("*.kimu"):
        hashes[capture.name] = sha256(capture.read_bytes()).hexdigest()
    result["artifacts"] = {str(Path(folder).name) + "/" + name: h for name, h in hashes.items()}
    return result


def export(output: Path, *, formal: bool = True, workers: int = 4) -> bool:
    """Finite matrix from frozen manifest; fresh processes and roots, never overwrite."""
    output = output.resolve()
    if output.exists():
        raise FileExistsError(output)
    import os

    protected = [
        ROOT / "datasets",
        ROOT / "firmware/xiao_nrf52840_sense/evidence",
        ROOT / "experiments/M5_CP1_20260926",
        ROOT / "experiments/M5_CP2_20260926",
        Path(os.environ.get("KINEIMU_M1_RAW_ROOT", "<external-data>/kineimu_m1_usb_30min_20260925_01")),
    ]
    if output == ROOT or any(output.is_relative_to(root.resolve()) for root in protected):
        raise ValueError("output must be outside raw/source evidence trees")

    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    if formal and dirty:
        raise ValueError("formal CP3 requires clean committed tracked source")
    pinned = {"numpy": "2.5.2", "scipy": "1.18.1", "pandas": "3.0.5", "imufusion": "1.3.3", "imucal": "2.6.0"}
    if formal and (platform.python_version() != "3.12.14" or any(version(k) != v for k, v in pinned.items())):
        raise ValueError("formal CP3 requires frozen runtime/versions")
    files = [str(p.relative_to(ROOT)).replace("\\", "/") for p in sorted((ROOT / "kineimu_shoulder").rglob("*.py"))]
    files += [
        "uv.lock",
        "protocols/M5_VALIDATION_CONTRACT.md",
        "protocols/M5_PROCESSING_V1_1.md",
        "tests/fixtures/M5_KNOWN_SENSOR_MOTIONS.md",
        "experiments/M5_CP1_20260926/case-manifest.json",
        "examples/m5_perturbation.py",
        "tests/unit/test_m4_segmentation.py",
        "tests/unit/test_m4_metrics.py",
        "tests/unit/test_m4_thorax.py",
        "tests/unit/test_m4_summary.py",
        "tests/unit/test_m2_replay.py",
    ]
    files += [str(p.relative_to(ROOT)).replace("\\", "/") for p in sorted((ROOT / "tests").rglob("*.py"))]
    files += [
        "experiments/M5_CP3_20260926/audit.py",
        "experiments/M5_CP3_20260926/diagnostics.json",
        "experiments/M5_CP3_20260926/partial-attempts.json",
    ]
    tracked = set(git("ls-files").splitlines())
    if formal and any(f not in tracked for f in files):
        raise ValueError("uncommitted source file")
    matrix_cases = cases()
    frozen = json.loads((ROOT / "experiments/M5_CP1_20260926/case-manifest.json").read_text())
    frozen_rows = frozen["cases"] if isinstance(frozen, dict) else frozen
    if frozen_rows != matrix_cases:
        raise ValueError("case manifest differs from frozen CP1")
    output.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}

    def write(name: str, value: Any) -> None:
        payload = canonical(value)
        with (output / name).open("xb") as stream:
            stream.write(payload)
        hashes[name] = sha256(payload).hexdigest()

    write(
        "manifest.json",
        dict(
            checkpoint="CP3",
            schema_version="m5-report/1.0",
            previous_attempts_artifact="experiments/M5_CP3_20260926/partial-attempts.json",
            previous_failed_complete_run="experiments/M5_CP3_20260926/formal4",
            formal=formal,
            git_commit=git("rev-parse", "HEAD"),
            tracked_dirty=dirty,
            case_ids=[r["id"] for r in matrix_cases],
            source_file_sha256={f: sha256((ROOT / f).read_bytes()).hexdigest() for f in files},
            runtime=dict(
                python=platform.python_version(), platform=platform.platform(),
                packages={k: version(k) for k in pinned},
                thread_environment={
                    k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
                },
            ),
            artifact_codec="gzip deterministic mtime=0; payload canonical UTF8 LF JSON",
            source_type="synthetic",
            anatomical_eligible=False,
            working_coverage_min=0.98,
            configuration=plain(CONFIG),
            processing="M5 processing/1.1: explicit short-gap transition reconstruction; pinned AHRS unchanged",
        ),
    )
    selected = [
        r
        for r in matrix_cases
        if r["implementation"]
        in ("sensor-source", "exact-source", "irregular-grid", "input-mutation", "evidence-mutation")
    ]
    fixture_cases = [r for r in matrix_cases if fixture_selector(r) is not None]
    unsupported = fixture_cases
    selected = [r for r in selected if r not in unsupported]
    results = []
    jobs = [(r, str(output / f"case-{matrix_cases.index(r):04d}")) for r in selected]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for index, result in enumerate(pool.map(_worker, jobs, chunksize=1)):
            hashes.update(result["artifacts"])
            results.append(result)
            print(
                f"{index + 1}/{len(selected)} {result['id']} {result['stage_disposition']} passed={result['passed']}",
                flush=True,
            )
    fixture_outcomes = execute_fixtures(output)
    write("fixture-results.json", fixture_outcomes)
    for case in fixture_cases:
        selector = fixture_selector(case)
        matched = [r for r in fixture_outcomes if selector is not None and selector(r)]
        results.append(
            dict(
                id=case["id"],
                intended_class=case["class"],
                passed=bool(matched) and all(r["passed"] for r in matched),
                stage_disposition="existing_frozen_fixture",
                fixture_tests=matched,
                control_id=case["control_id"],
                error_summary={},
                artifacts={"fixture-results.json": hashes["fixture-results.json"]},
                failed_gates=[] if matched and all(r["passed"] for r in matched) else ["fixture_execution"],
            )
        )
    for r in matrix_cases:
        if r["id"] not in {v["id"] for v in results}:
            results.append(
                dict(
                    id=r["id"],
                    intended_class=r["class"],
                    passed=False,
                    stage_disposition="not_run",
                    failed_gates=["recipe_not_executed"],
                    error_summary={},
                    artifacts={},
                )
            )
    results.sort(key=lambda r: [c["id"] for c in matrix_cases].index(r["id"]))
    passed = all(r["passed"] for r in results)
    worst = sorted(
        [
            dict(case=r["id"], metric=name, **error)
            for r in results
            for name, error in r.get("error_summary", {}).items()
            if error["gate"] and error["max_abs_error"] is not None and error["tolerance"] > 0
        ],
        key=lambda r: r["max_abs_error"] / r["tolerance"],
        reverse=True,
    )[:30]
    requirements = {
        family: [c["id"] for c in matrix_cases if c["condition"].startswith(family)]
        for family in (
            "CLEAN-",
            "N-A-",
            "N-G-",
            "B-C-",
            "B-R-",
            "J-S-",
            "J-T-",
            "L-S-",
            "L-P-",
            "D-C-",
            "D-H-",
            "I-",
            "C-",
            "GAP-",
            "INPUT-",
            "EV-",
            "M4-",
        )
    }

    write(
        "report.json",
        dict(
            checkpoint="CP3",
            schema_version="m5-report/1.0",
            passed=passed,
            case_count=len(results),
            failed_case_count=sum(not r["passed"] and r["stage_disposition"] != "not_run" for r in results),
            not_run_count=sum(r["stage_disposition"] == "not_run" for r in results),
            results=results,
            worst_normalized_errors=worst,
            requirement_index=requirements,
            limitations=(
                "Finite synthetic design only. Stress completion is not accuracy PASS. "
                "No anatomical/clinical validation. CP4/CP5 remain separate."
            ),
        ),
    )
    write("SHA256SUMS.json", hashes.copy())
    return passed


@contextmanager
def memoized_session() -> Any:
    """Cache only identical pure calls in one immutable validation session.

    No backend state or raw data is cached across cases. Underlying production
    code is unchanged and every distinct input still executes its full checks.
    Canonical equality to uncached execution is a mandatory regression.
    """
    import inspect
    from contextlib import ExitStack
    from unittest.mock import patch

    import kineimu_shoulder.exercise as exercise_module
    import kineimu_shoulder.shoulder as shoulder_module
    import kineimu_shoulder.summary as summary_module
    import kineimu_shoulder.thorax as thorax_module

    namespace = sys.modules[__name__]
    functions = (
        ("segment_matrix", (namespace,)),
        ("long_axis_elevation", (namespace, exercise_module, shoulder_module)),
        ("relative_angular_speed", (namespace, exercise_module)),
        ("interval_rom_duration", (exercise_module, shoulder_module)),
        ("segment_shoulder_repetitions", (namespace, exercise_module)),
        ("compute_repetition_metrics", (namespace, exercise_module, summary_module, thorax_module)),
        ("compute_thorax_excursion", (namespace, summary_module, thorax_module)),
    )

    def frozen(value: Any) -> None:
        if isinstance(value, np.ndarray):
            value.setflags(write=False)
        elif is_dataclass(value):
            for field in fields(value):
                frozen(getattr(value, field.name))
        elif isinstance(value, (tuple, list)):
            for item in value:
                frozen(item)

    def wrap(function: Any) -> Any:
        cache: dict[Any, Any] = {}
        retained: list[Any] = []
        signature = inspect.signature(function)

        def call(*args: Any, **kwargs: Any) -> Any:
            binding = signature.bind(*args, **kwargs)
            binding.apply_defaults()
            key = []
            for name, value in binding.arguments.items():
                frozen(value)
                retained.append(value)
                try:
                    hash(value)
                    token = value
                except TypeError:
                    token = ("identity", id(value))
                key.append((name, token))
            identity = tuple(key)
            if identity not in cache:
                cache[identity] = function(*args, **kwargs)
                frozen(cache[identity])
            return cache[identity]

        return call

    with ExitStack() as stack:
        for name, modules in functions:
            original = getattr(modules[0], name)
            wrapped = wrap(original)
            for module in modules:
                stack.enter_context(patch.object(module, name, wrapped))
        yield


def fixture_selector(case: dict[str, Any]) -> Any:
    """Map predeclared reusable M4/M1 constructions to actual collected tests."""
    recipe = case["implementation"]
    mutation = case["parameters"].get("mutation", "")
    if recipe == "existing-M4-fixture":
        family = case["parameters"]["fixture"][0]
        name = {"C": "test_m4_segmentation", "P": "test_m4_metrics", "T": "test_m4_thorax", "U": "test_m4_summary"}[
            family
        ]
        # Whole corresponding frozen suite is a superset: includes equality sides,
        # malformed cases and original exact independent expectations for each ID.
        return lambda row: name in row["class"]
    if mutation in ("epoch-reset", "crc", "hash", "node"):
        names = {
            "epoch-reset": "splits_epoch",
            "crc": "crc_corruption",
            "hash": "bad_source_hash",
            "node": "wrong_node",
        }
        return lambda row: "test_m2_replay" in row["class"] and names[mutation] in row["name"]
    if mutation in ("singularity-T8", "branch-T9"):
        selected = "singular" if mutation.startswith("singularity") else "branch"
        return lambda row: "test_m4_thorax" in row["class"] and "t8_t9" in row["name"] and selected in row["name"]
    if mutation.startswith("comparison-"):
        # All U7 context/upstream key tests include exact changed-key rejection.
        return lambda row: "test_m4_summary" in row["class"] and "u7_" in row["name"]
    return None


def execute_fixtures(output: Path) -> list[dict[str, Any]]:
    """Retain normalized assertions, excluding operational times from products."""
    files = [
        "tests/unit/test_m4_segmentation.py",
        "tests/unit/test_m4_metrics.py",
        "tests/unit/test_m4_thorax.py",
        "tests/unit/test_m4_summary.py",
        "tests/unit/test_m2_replay.py",
    ]
    operational = output / "operational"
    operational.mkdir()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *files,
            "--basetemp",
            str(operational / "tmp"),
            "--junitxml",
            str(operational / "junit.xml"),
            "--tb=short",
            "-q",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    (operational / "pytest.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if not (operational / "junit.xml").exists():
        return [dict(name="fixture-launch", **{"class": "launch"}, passed=False, exit_code=completed.returncode)]
    rows = []
    for item in ElementTree.parse(operational / "junit.xml").iter("testcase"):
        rows.append(
            dict(
                name=item.attrib["name"],
                **{"class": item.attrib["classname"]},
                passed=not any(item.find(key) is not None for key in ("failure", "error", "skipped")),
            )
        )
    return sorted(rows, key=lambda row: (row["class"], row["name"]))
