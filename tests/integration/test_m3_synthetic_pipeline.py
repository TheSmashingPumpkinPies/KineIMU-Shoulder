"""CP4: exercise the real dual-node M2.4 to M3 command and its artifacts."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMMAND = ROOT / "examples" / "m3_dual_synthetic.py"


@pytest.mark.integration
def test_dual_synthetic_pipeline_has_known_metrics_and_repeats_byte_for_byte(tmp_path: Path) -> None:
    outputs: list[dict[str, bytes]] = []
    for run in ("first", "second"):
        destination = tmp_path / run
        subprocess.run(
            [sys.executable, str(COMMAND), "--output-dir", str(destination)],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        outputs.append({path.name: path.read_bytes() for path in destination.iterdir()})

    assert outputs[0] == outputs[1]
    assert set(outputs[0]) == {"processed.json", "derived.json", "report.json"}
    processed = json.loads(outputs[0]["processed.json"])
    derived = json.loads(outputs[0]["derived.json"])
    report = json.loads(outputs[0]["report.json"])

    assert processed["schema"] == "m3-dual-synthetic-processed/1.0"
    assert derived["schema"] == "m3-kinematics/1.0"
    assert processed["common_time_us"] == [0, 200000, 700000, 1200000]
    assert processed["valid"] == [True] * 4
    assert processed["reason"] == ["valid"] * 4
    assert processed["evidence_label"] == "Derived"
    assert derived["source_type"] == "synthetic"
    assert derived["anatomical_eligible"] is False
    assert derived["elevation"]["valid"] == [True] * 4
    assert derived["speed"]["valid"] == [True] * 3
    assert derived["interval"]["valid"] is True

    # Independent R0 construction in tests/fixtures/M3_KNOWN_MOTION.md:
    # known Y rotations 0°, 20°, 70°, 30° give 70° ROM over 1.2 s.
    assert derived["elevation"]["rad"] == pytest.approx([0, math.pi / 9, 7 * math.pi / 18, math.pi / 6], abs=1e-10)
    assert derived["interval"]["rom_rad"] == pytest.approx(7 * math.pi / 18, abs=1e-10)
    assert derived["interval"]["elapsed_duration_s"] == pytest.approx(1.2, abs=1e-12)
    # Independent endpoint differences: 20°/0.2 s, 50°/0.5 s, 40°/0.5 s.
    assert derived["speed"]["rad_per_s"] == pytest.approx(
        [5 * math.pi / 9, 5 * math.pi / 9, 4 * math.pi / 9], abs=1e-10,
    )
    assert report["max_abs_elevation_error_rad"] < 1e-10
    assert report["max_abs_speed_error_rads"] < 1e-10
    assert report["abs_rom_error_rad"] < 1e-10
    assert report["abs_duration_error_s"] < 1e-12
    assert report["validity_counts"] == {
        "m2_rows": 4, "m3_elevation_rows": 4, "m3_speed_intervals": 3, "m3_rom_intervals": 1,
    }
    assert report["physical_validation"] == "absent"
