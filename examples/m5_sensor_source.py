"""CP1 source/annotation export, not a CP2/CP3 pipeline acceptance runner."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Any

import imufusion

from kineimu_shoulder.io.m1_capture import encode_capture_record
from kineimu_shoulder.io.m1_packet import encode_sample_packet
from kineimu_shoulder.validation.manifest import cases
from kineimu_shoulder.validation.motions import MOTIONS
from kineimu_shoulder.validation.oracle import labels, observation_labels, summary
from kineimu_shoulder.validation.source import ACCEL_LSB, GYRO_LSB, generate, packets

ROOT = Path(__file__).resolve().parents[1]
DEMOS = ("F90", "AL90", "AR90", "T-MIX")


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def export(output: Path) -> None:
    """Atomically claim absent output root; preserve all partial files on failure."""
    output = output.resolve()
    if output == ROOT or output.is_relative_to(ROOT / "datasets"):
        raise ValueError("output must not be the repository or a source dataset root")
    # Source tool has no external raw input. CP4 runner must also protect its selected raw root.
    output.mkdir(parents=True, exist_ok=False)
    file_hashes = {}

    def write(name: str, content: bytes) -> None:
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
        file_hashes[name] = sha256(content).hexdigest()

    source_files = [
        "protocols/M5_VALIDATION_CONTRACT.md",
        "tests/fixtures/M5_KNOWN_SENSOR_MOTIONS.md",
        "uv.lock",
        "examples/m5_sensor_source.py",
        "kineimu_shoulder/io/m1_packet.py",
        "kineimu_shoulder/io/m1_capture.py",
        "kineimu_shoulder/io/m2_replay.py",
        "datasets/samples/m6_synthetic/case-manifest.json",
    ]
    source_files += [
        str(p.relative_to(ROOT)).replace("\\", "/") for p in sorted((ROOT / "kineimu_shoulder/validation").glob("*.py"))
    ]
    manifest = {
        "version": "m5-source/1.0",
        "source_type": "synthetic",
        "anatomical_eligible": False,
        "checkpoint_scope": "CP1 source tools only; CP2-CP5 not run",
        "git_commit": git("rev-parse", "HEAD"),
        "tracked_dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            **{name: version(name) for name in ("numpy", "scipy", "imufusion", "imucal")},
        },
        "backend": {
            "settings": "not exposed by installed Ahrs API",
            "public_api": sorted(n for n in dir(imufusion.Ahrs()) if not n.startswith("_")),
            "processing": (
                "fresh Ahrs; initial synthetic q_WN; skip_startup; no set_settings; "
                "no magnetometer; no CP1 AHRS execution"
            ),
        },
        "source_hashes": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in source_files},
        "sample_hz": 100,
        "gravity_mps2": 9.80665,
        "translation_mps2": [0, 0, 0],
        "lever_arm_m": [0, 0, 0],
        "gyro_rule": "left derivative at knots; otherwise continuous right-endpoint observation",
        "quantization": {
            "accel_lsb_mps2": ACCEL_LSB,
            "gyro_lsb_rads": GYRO_LSB,
            "rounding": "ties-to-even",
            "clipping": "reject",
            "samples_per_packet": 4,
        },
        "demo_trajectories": list(DEMOS),
    }
    write("manifest.json", canonical(manifest))
    write("case-manifest.json", canonical(cases()))
    # All baseline labels, including partial/wrong/quiet/long, are separate from observed samples.
    write(
        "annotations.json",
        canonical(
            {
                name: {"motion": asdict(motion), "nominal_m4": labels(name), "summary": summary(name)}
                for name, motion in MOTIONS.items()
            }
        ),
    )
    for trajectory in DEMOS:
        data = generate(trajectory)
        index = list(MOTIONS).index(trajectory)
        utc = datetime(2026, 9, 26, tzinfo=UTC) + timedelta(minutes=index)
        metadata: dict[str, Any] = {
            "source_type": "synthetic",
            "anatomical_eligible": False,
            "nodes": {},
            "session_start_utc": utc.isoformat().replace("+00:00", "Z"),
            "host_time_rule": "synthetic last packet sample time * 1000 ns; not a clock-map observation",
        }
        truth: dict[str, Any] = {}
        for node, row in data.nodes.items():
            write(f"{trajectory}/{node}.bin", b"".join(encode_sample_packet(p) for p in packets(row, node)))
            write(
                f"{trajectory}/{node}.kimu",
                b"".join(
                    encode_capture_record(
                        encode_sample_packet(p), host_monotonic_ns=p.samples[-1].device_time_us * 1000
                    )
                    for p in packets(row, node)
                ),
            )
            # SI input and exact quaternion isolation source remain separately named paths.
            write(
                f"{trajectory}/{node}-si.json",
                canonical(
                    {
                        "sequence": row.sequence.tolist(),
                        "nominal_time_us": row.nominal_time_us.tolist(),
                        "true_time_us": row.true_time_us.tolist(),
                        "claimed_time_us": row.claimed_time_us.tolist(),
                        "device_time_us": row.device_time_us.tolist(),
                        "acceleration_mps2": row.force_mps2.tolist(),
                        "angular_rate_rads": row.rate_rads.tolist(),
                        "retained_mask": row.retained_mask.tolist(),
                    }
                ),
            )
            truth[node] = {"q_ws": row.q_ws.tolist(), "q_wn": row.q_wn.tolist(), "q_wk": row.q_wk.tolist()}
            metadata["nodes"][node] = {
                "R_NS": row.r_ns.tolist(),
                "R_NK": row.r_nk.tolist(),
                "initial_q_WN": row.q_wn[0].tolist(),
                "clock_scale": row.clock_scale,
                "clock_offset_us": row.clock_offset_us,
                "clock_uncertainty_us": 1,
                "clock_rounding_residual_us": row.clock_rounding_residual_us.tolist(),
                "sample_count": len(row.sequence),
                "epoch": 0,
                "common_world_id": "synthetic-M5-world",
                "heading_status": "synthetic-construction",
                "calibration": {
                    "M": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                    "bias_accel_mps2": [0, 0, 0],
                    "bias_gyro_rads": [0, 0, 0],
                },
            }
        write(f"{trajectory}/exact-orientations.json", canonical(truth))
        write(f"{trajectory}/metadata.json", canonical(metadata))
    # Independent oracle nominal and observation labels agree only for this clean fixed grid.
    write(
        "observation-labels.json",
        canonical({name: observation_labels(name, generate(name).nodes["B"].true_time_us.tolist()) for name in DEMOS}),
    )
    write("SHA256SUMS.json", canonical(file_hashes))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.output)
