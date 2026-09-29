"""Reproducible two-node synthetic M2.4 to M3 kinematics example."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from hashlib import sha256
from math import cos, pi, sin
from pathlib import Path

import numpy as np

from kineimu_shoulder.relative_orientation import (
    ClockMap,
    HeadingRelation,
    SegmentOrientationStream,
    relative_orientation,
)
from kineimu_shoulder.shoulder import (
    AlignmentRecord,
    interval_rom_duration,
    long_axis_elevation,
    relative_angular_speed,
)

ROOT = Path(__file__).resolve().parents[1]
GRID = [0, 200_000, 700_000, 1_200_000]
MAX_GAP_US = 500_000
QX_60 = (cos(pi / 6), sin(pi / 6), 0.0, 0.0)
IDENTITY = (1.0, 0.0, 0.0, 0.0)


def _qy(degrees: int) -> tuple[float, float, float, float]:
    half = degrees * pi / 360
    return (cos(half), 0.0, sin(half), 0.0)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _source(
    node: str, device_times: list[int], quaternions: list[tuple[float, float, float, float]],
) -> dict[str, object]:
    return {
        "source_type": "synthetic", "node_id": node, "epoch": 0,
        "device_time_us": device_times, "quaternion_wsegment_wxyz": quaternions,
        "construction": "exact trigonometric two-node rotation fixture",
    }


def _alignment(node: str, segment: str, source_hash: str) -> AlignmentRecord:
    return AlignmentRecord(
        node_id=node, epoch=0, segment=segment, side="right", quaternion_nsegment=IDENTITY,
        alignment_id=f"cp4-synthetic-{node.lower()}", method="declared exact synthetic axes",
        source_sha256=source_hash, neutral_pose="arms down; H +Z proximal; T +Z superior",
        validity="current", mounting_validity_statement="one fixed synthetic mount for this epoch",
        remounted=False, uncertainty="exact synthetic construction", status="supported",
        axes_basis="synthetic_ground_truth",
    )


def build_artifacts() -> dict[str, bytes]:
    """Construct sources, run M2.4 and M3, then serialize evidence and metrics."""
    a_source = _source("A", [-50_000, 150_000, 650_000, 1_150_000], [QX_60] * 4)
    b_source = _source("B", [-100_000, 300_000, 700_000, 1_100_000], [_qy(v) for v in (0, 40, 80, 30)])
    a_hash, b_hash = sha256(_canonical(a_source)).hexdigest(), sha256(_canonical(b_source)).hexdigest()
    a = SegmentOrientationStream(
        node_id="A", clock_id="synthetic-a-clock", epoch=0, world_id="Wa", source_sha256=a_hash,
        timestamp_us=np.asarray(a_source["device_time_us"], dtype=np.int64),
        quaternion_wsegment=np.asarray(a_source["quaternion_wsegment_wxyz"], dtype=np.float64),
    )
    b = SegmentOrientationStream(
        node_id="B", clock_id="synthetic-b-clock", epoch=0, world_id="Wb", source_sha256=b_hash,
        timestamp_us=np.asarray(b_source["device_time_us"], dtype=np.int64),
        quaternion_wsegment=np.asarray(b_source["quaternion_wsegment_wxyz"], dtype=np.float64),
    )
    a_map = ClockMap(
        node_id="A", clock_id=a.clock_id, epoch=0, slope=1.0, intercept_us=50_000.0,
        fit_device_start_us=-50_000, fit_device_end_us=1_150_000,
        valid_device_start_us=-50_000, valid_device_end_us=1_150_000,
        uncertainty_us=0.0, heldout_residual_us=0.0,
        method="exact synthetic affine map, independently declared", source_sha256=a_hash, status="supported",
    )
    b_map = ClockMap(
        node_id="B", clock_id=b.clock_id, epoch=0, slope=1.0, intercept_us=100_000.0,
        fit_device_start_us=-100_000, fit_device_end_us=1_100_000,
        valid_device_start_us=-100_000, valid_device_end_us=1_100_000,
        uncertainty_us=0.0, heldout_residual_us=0.0,
        method="exact synthetic affine map, independently declared", source_sha256=b_hash, status="supported",
    )
    heading = HeadingRelation(
        thorax_world_id="Wa", humerus_world_id="Wb", quaternion_thorax_world_humerus_world=QX_60,
        method="known synthetic world relation Qx(+60 deg)",
        source_sha256=sha256(_canonical({"world_relation_wxyz": QX_60, "worlds": ["Wa", "Wb"]})).hexdigest(),
        status="supported",
    )
    a_alignment = _alignment("A", "T", a_hash)
    b_alignment = _alignment("B", "H", b_hash)
    config = {
        "common_time_us": GRID, "max_interpolation_gap_us": MAX_GAP_US,
        "max_timing_uncertainty_us": 0.0, "max_sample_gap_us": MAX_GAP_US,
        "interval": [0, 1_200_000], "side": "right", "source_type": "synthetic",
        "a_clock_map": asdict(a_map), "b_clock_map": asdict(b_map),
        "heading_relation": asdict(heading),
        "thorax_alignment": asdict(a_alignment), "humerus_alignment": asdict(b_alignment),
    }
    config_hash = sha256(_canonical(config)).hexdigest()
    relative = relative_orientation(
        a, b, common_time_us=np.asarray(GRID, dtype=np.int64),
        thorax_clock_map=a_map, humerus_clock_map=b_map, heading_relation=heading,
        max_interpolation_gap_us=MAX_GAP_US, max_timing_uncertainty_us=0.0,
    )
    shared = dict(
        thorax_alignment=a_alignment, humerus_alignment=b_alignment,
        side="right", source_type="synthetic", max_sample_gap_us=MAX_GAP_US,
    )
    elevation = long_axis_elevation(relative, **shared)
    speed = relative_angular_speed(relative, **shared)
    interval = interval_rom_duration(relative, start_time_us=0, end_time_us=1_200_000, **shared)
    if not (bool(relative.valid.all()) and bool(elevation.valid.all()) and bool(speed.valid.all()) and interval.valid):
        raise ValueError("CP4 fixture produced an invalid result")

    processed = {
        "schema": "m3-dual-synthetic-processed/1.0", "source_type": "synthetic",
        "source_sha256": {"thorax": a_hash, "humerus": b_hash}, "configuration_sha256": config_hash,
        "sources": {"thorax": a_source, "humerus": b_source}, "configuration": config,
        "common_time_us": relative.common_time_us.tolist(), "quaternion_th_wxyz": relative.quaternion_th.tolist(),
        "valid": relative.valid.tolist(), "reason": relative.reason, "evidence_label": relative.evidence_label,
        "interpolation": relative.interpolation,
        "time_semantics": "observed source device times; common grid derived from declared exact synthetic clock maps",
    }
    derived = {
        "schema": "m3-kinematics/1.0", "source_type": "synthetic", "side": "right",
        "source_sha256": {"thorax": a_hash, "humerus": b_hash}, "configuration_sha256": config_hash,
        "alignment": {"thorax": asdict(a_alignment), "humerus": asdict(b_alignment)},
        "clock_heading": {"thorax": asdict(a_map), "humerus": asdict(b_map), "heading": asdict(heading)},
        "max_sample_gap_us": MAX_GAP_US, "anatomical_eligible": elevation.anatomical_eligible,
        "evidence_label": elevation.evidence_label,
        "elevation": {
            "definition_version": elevation.definition_version, "unit": "rad", "common_time_us": GRID,
            "rad": elevation.elevation_rad.tolist(), "valid": elevation.valid.tolist(), "reason": elevation.reason,
        },
        "speed": {
            "definition_version": speed.definition_version, "unit": "rad/s",
            "quantity": speed.quantity_description, "start_time_us": speed.start_time_us.tolist(),
            "end_time_us": speed.end_time_us.tolist(), "rad_per_s": speed.relative_angular_speed_rads.tolist(),
            "valid": speed.valid.tolist(), "reason": speed.reason,
        },
        "interval": {
            "definition_version": interval.definition_version, "start_time_us": interval.start_time_us,
            "end_time_us": interval.end_time_us, "rom_rad": interval.rom_rad, "rom_unit": "rad",
            "elapsed_duration_s": interval.elapsed_duration_s, "duration_unit": "s",
            "valid": interval.valid, "reason": interval.reason,
            "first_invalid_row_index": interval.first_invalid_row_index,
            "invalid_row_reasons": interval.invalid_row_reasons,
        },
    }
    artifacts = {"processed.json": _canonical(processed), "derived.json": _canonical(derived)}
    expected_elevation = np.asarray([0.0, pi / 9, 7 * pi / 18, pi / 6])
    expected_speed = np.asarray([5 * pi / 9, 5 * pi / 9, 4 * pi / 9])
    report = {
        "schema": "m3-cp4-acceptance-report/1.0", "source_type": "synthetic",
        "fixture_truth": "tests/fixtures/M3_KNOWN_MOTION.md R0; endpoint differences derived in CP4 test",
        "source_sha256": {"thorax": a_hash, "humerus": b_hash}, "configuration_sha256": config_hash,
        "dependency_lock_sha256": sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "output_sha256": {name: sha256(content).hexdigest() for name, content in artifacts.items()},
        "validity_counts": {
            "m2_rows": int(relative.valid.sum()), "m3_elevation_rows": int(elevation.valid.sum()),
            "m3_speed_intervals": int(speed.valid.sum()), "m3_rom_intervals": int(interval.valid),
        },
        "max_abs_elevation_error_rad": float(np.max(np.abs(elevation.elevation_rad - expected_elevation))),
        "max_abs_speed_error_rads": float(np.max(np.abs(speed.relative_angular_speed_rads - expected_speed))),
        "abs_rom_error_rad": abs(interval.rom_rad - 7 * pi / 18),
        "abs_duration_error_s": abs(interval.elapsed_duration_s - 1.2),
        "evidence": {
            "source_times": "Observed within generated synthetic fixture", "metrics": "Derived",
            "clock_heading_alignment": "supported exact synthetic truth; no physical measurement",
            "assumed_experimental": "none in this fixture; illustrative synthetic construction",
            "validated": False,
        },
        "physical_validation": "absent",
        "m1_limit": "M1 USB pair lacks supported pairwise clock, common heading and measured anatomical alignment",
    }
    artifacts["report.json"] = _canonical(report)
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if any(part.lower() == "raw" for part in output.parts):
        parser.error("output directory must be outside raw/")
    if output.exists() and any(output.iterdir()):
        parser.error("output directory must be absent or empty")
    artifacts = build_artifacts()
    output.mkdir(parents=True, exist_ok=True)
    for name, content in artifacts.items():
        (output / name).write_bytes(content)


if __name__ == "__main__":
    main()
