"""Deterministic M2 single-node replay example; run with ``--output-dir``.

The M1 example uses an illustrative identity calibration. It is node-frame
orientation only and supplies no anatomical alignment or absolute heading.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import numpy as np

from kineimu_shoulder.calibration import CalibrationArtifact, apply_calibration
from kineimu_shoulder.io.m1_packet import NodeId, SampleFlags
from kineimu_shoulder.io.m1_raw import M1RawCountAdapterConfig, SensorToNodeTransform
from kineimu_shoulder.io.m2_replay import replay_capture
from kineimu_shoulder.orientation import estimate_orientation

ROOT = Path(__file__).resolve().parents[1]
RECORDED = ROOT / "firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary.kimu"
RECORDED_SHA256 = "1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201"
MAX_GAP_S = 0.05
EXCERPT_SAMPLES = 128


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _config() -> M1RawCountAdapterConfig:
    return M1RawCountAdapterConfig(
        accel_range_g=4.0,
        gyro_range_dps=500.0,
        accel_sensitivity_mg_per_lsb=0.122,
        gyro_sensitivity_mdps_per_lsb=17.5,
        axis_transform=SensorToNodeTransform(
            sensor_axes=("sensor_x", "sensor_y", "sensor_z"),
            node_axes=("node_x", "node_y", "node_z"),
            sensor_to_node=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            description="illustrative identity axes; anatomical mounting not measured",
        ),
    )


def _identity_calibration(node: NodeId, source_sha256: str, config: M1RawCountAdapterConfig) -> CalibrationArtifact:
    return CalibrationArtifact(
        calibration_id=f"m2.5-example-identity-{node.name.lower()}",
        node_id=node,
        sensor_id="LSM6DS3TR-C" if node is NodeId.B else "synthetic-imu",
        config=config,
        accel_matrix=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        accel_bias_mps2=(0.0, 0.0, 0.0),
        gyro_bias_rads=(0.0, 0.0, 0.0),
        fit_method="illustrative_identity_no_fit",
        fit_window_us=(0, 1),
        source_sha256=(source_sha256,),
        validity="Example only; no physical calibration fit or transfer accuracy claim",
    )


def _process(
    *,
    node: NodeId,
    source_sha256: str,
    times: tuple[int, ...],
    sequences: tuple[int, ...],
    flags: tuple[SampleFlags, ...],
    accel: np.ndarray,
    gyro: np.ndarray,
    config: M1RawCountAdapterConfig,
) -> dict[str, object]:
    calibration = _identity_calibration(node, source_sha256, config)
    node_accel, node_gyro = apply_calibration(
        accel,
        gyro,
        artifact=calibration,
        node_id=node,
        sensor_id=calibration.sensor_id,
        config=config,
        sample_flags=flags,
    )
    orientation = estimate_orientation(
        np.asarray(times, dtype=np.int64), node_accel, node_gyro, max_gap_s=MAX_GAP_S
    )
    return {
        "schema": "m2-offline-example/1.0",
        "node_id": node.name,
        "source_sha256": source_sha256,
        "sample_count": len(times),
        "sample_sequence": sequences,
        "device_time_us": times,
        "quaternion_wn": orientation.quaternion_wn.tolist(),
        "quaternion_order": "wxyz",
        "rotation": "active node-to-independent-world q_WN",
        "heading_observable": orientation.heading_observable,
        "calibration_id": calibration.calibration_id,
        "calibration_method": calibration.fit_method,
        "calibration_artifact": json.loads(calibration.to_json()),
        "sensor_to_node": config.axis_transform.sensor_to_node,
        "initial_quaternion_wn": (1.0, 0.0, 0.0, 0.0),
        "max_gap_s": MAX_GAP_S,
        "evidence_status": "Assumed/Experimental (identity calibration and node axes; heading unobserved)",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output: Path = args.output_dir.resolve()
    if any(part.lower() == "raw" for part in output.parts):
        parser.error("output directory must be outside raw/")
    if output.exists() and any(output.iterdir()):
        parser.error("output directory must be absent or empty")

    config = _config()
    times = tuple(range(0, 1_000_001, 10_000))
    synthetic_accel = np.tile([0.0, 0.0, 9.80665], (len(times), 1))
    synthetic_gyro = np.tile([0.0, 0.0, np.pi / 2], (len(times), 1))
    synthetic_fixture = {
        "kind": "known +90 deg Z turn at constant angular rate",
        "device_time_us": times,
        "acceleration_mps2": synthetic_accel.tolist(),
        "angular_rate_rads": synthetic_gyro.tolist(),
    }
    synthetic_hash = sha256(_canonical(synthetic_fixture)).hexdigest()
    synthetic = _process(
        node=NodeId.A,
        source_sha256=synthetic_hash,
        times=times,
        sequences=tuple(range(len(times))),
        flags=(SampleFlags.NONE,) * len(times),
        accel=synthetic_accel,
        gyro=synthetic_gyro,
        config=config,
    )

    replay = replay_capture(RECORDED, expected_sha256=RECORDED_SHA256, expected_node_id=NodeId.B, config=config)
    if len(replay.epochs) != 1 or len(replay.epochs[0].sensor_data.device_time_us) < EXCERPT_SAMPLES:
        raise ValueError("retained M1 example must have one epoch and at least 128 samples")
    epoch = replay.epochs[0]
    data = epoch.sensor_data
    recorded = _process(
        node=NodeId.B,
        source_sha256=replay.source_sha256,
        times=data.device_time_us[:EXCERPT_SAMPLES],
        sequences=data.sample_sequences[:EXCERPT_SAMPLES],
        flags=data.sample_flags[:EXCERPT_SAMPLES],
        accel=data.accel_mps2[:EXCERPT_SAMPLES],
        gyro=data.gyro_rads[:EXCERPT_SAMPLES],
        config=config,
    )
    recorded["source_path"] = RECORDED.relative_to(ROOT).as_posix()
    recorded["clock_epoch"] = epoch.clock_epoch
    recorded["excerpt_selection"] = "first 128 decoded samples from one retained M1 node B epoch"

    artifacts = {"synthetic.json": _canonical(synthetic), "m1_node_b.json": _canonical(recorded)}
    report = {
        "schema": "m2-offline-report/1.0",
        "synthetic_fixture_sha256": synthetic_hash,
        "m1_source_path": RECORDED.relative_to(ROOT).as_posix(),
        "m1_source_sha256": replay.source_sha256,
        "dependency_lock_sha256": sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "dependency_versions": {name: version(name) for name in ("numpy", "scipy", "imucal", "imufusion")},
        "m1_qc": asdict(replay.qc),
        "m1_qc_scope": "complete retained 832-sample source; orientation artifact uses its first 128 samples",
        "processing": "sensor SI -> illustrative identity calibration -> declared identity R_NS -> six-axis AHRS",
        "max_gap_s": MAX_GAP_S,
        "output_sha256": {name: sha256(content).hexdigest() for name, content in artifacts.items()},
        "limitations": [
            "M1 excerpt has no measured calibration or anatomical mounting transform.",
            "The identity calibration artifact's (0,1) fit window is a schema placeholder, not measured fit evidence.",
            "Six-axis static gravity does not observe yaw; orientation can drift with gyro bias.",
            "No pairwise clock map or common heading is established; no humerothoracic result is emitted.",
        ],
    }
    artifacts["report.json"] = _canonical(report)
    output.mkdir(parents=True, exist_ok=True)
    for name, content in artifacts.items():
        (output / name).write_bytes(content)


if __name__ == "__main__":
    main()
