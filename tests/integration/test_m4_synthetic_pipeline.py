"""CP5 catches nondeterminism, dropped provenance and incorrect SI/export metrics."""

import json
import os
import subprocess
import sys
from hashlib import sha256
from math import pi, sqrt
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_cp5_two_processes_canonical_truth_and_lineage(tmp_path):
    outputs = []
    for run in ("first", "second"):
        directory = tmp_path / run
        env = dict(os.environ, PYTHONHASHSEED="17" if run == "first" else "83")
        subprocess.run([sys.executable, str(ROOT / "examples/m4_dual_synthetic.py"),
                        "--output-dir", str(directory)], cwd=ROOT, env=env, check=True)
        outputs.append({p.name: p.read_bytes() for p in directory.iterdir()})
    assert outputs[0] == outputs[1]
    assert set(outputs[0]) == {"processed.json", "derived.json", "report.json"}
    parsed = {k: json.loads(v, parse_constant=lambda s: pytest.fail(f"nonstandard JSON {s}"))
              for k, v in outputs[0].items()}
    for name, value in parsed.items():
        assert outputs[0][name] == (json.dumps(value, sort_keys=True, separators=(",", ":"),
                                             allow_nan=False) + "\n").encode()
    report = parsed["report.json"]
    assert report["dependency_lock_sha256"] == sha256((ROOT / "uv.lock").read_bytes()).hexdigest()
    for name, digest in report["output_sha256"].items():
        assert digest == sha256(outputs[0][name]).hexdigest()
    assert report["physical_validation"] == "absent"
    assert report["passed"] and report["numerical_errors"]
    assert all(row["abs_error"] <= row["tolerance"] for row in report["numerical_errors"])
    assert any(row["metric"] == "valid_count" and row["unit"] == "count"
               and row["tolerance"] == 0 for row in report["numerical_errors"])
    assert any(row["metric"] == "rep1.peak_us" and row["expected"] == 800000
               and row["tolerance"] == 0 for row in report["numerical_errors"])
    derived = parsed["derived.json"]
    assert derived["schema_version"] == "m4-exercise/1.0"
    for session in derived["sessions"]:
        processed = parsed["processed.json"]["sessions"][session["session_id"]]
        assert session["input_artifact_sha256"] == sha256(
            (json.dumps(processed, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()
        assert processed["thorax_trace"]["source_valid"] == [True] * len(processed["m2"]["common_time_us"])
        assert processed["m2"]["interpolation"]
        for node, source in processed["sources"].items():
            assert session["original_source_sha256"][node] == sha256(
                (json.dumps(source, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()
        assert session["anatomical_eligible"] is False
        if session["session_id"] == "wrong-plane":
            assert session["valid_count"] == 0 and session["excluded_count"] == 2
            assert session["candidates"][0]["metrics"]["rom_rad"]["value"] is None
            assert "plane_mismatch" in session["candidates"][0]["reasons"]
            continue
        if session["session_id"] == "later-flexion":
            assert session["valid_count"] == 1
            assert session["summary"]["rom_sd"]["value"] is None
            continue
        # CP0 A+B/U2: (80+60)/2, sample SD sqrt(100+100), active 2+1.6 s.
        assert (session["detected_count"], session["valid_count"], session["excluded_count"]) == (2, 2, 0)
        summary = session["summary"]
        assert summary["statistics"]["rom_rad"][0]["mean"]["value"] == pytest.approx(70*pi/180, abs=1e-10)
        assert summary["rom_sd"]["value"] == pytest.approx(10*sqrt(2)*pi/180, abs=1e-10)
        assert summary["active_cadence"]["value"] == pytest.approx(5/9, abs=1e-12)
        # CP0 T4: Rz(30) Ry(-20) Rx(-10), moving thorax cancels in q_TH.
        rep = session["candidates"][0]
        assert (rep["start_us"], rep["end_us"], rep["peak_us"]) == (200000, 2200000, 800000)
        assert rep["metrics"]["hold_duration_s"]["value"] == pytest.approx(.6, abs=1e-12)
        for axis, degrees in (("extension", 20), ("lateral_flexion", 10), ("axial_rotation", 30)):
            assert rep["thorax_proxy"][axis]["magnitude_rad"] == pytest.approx(degrees*pi/180, abs=1e-10)
    comparison = derived["comparisons"][0]
    assert comparison["comparable"] and comparison["differing_keys"] == []
    # Later B-only mean60 minus earlier A+B mean70; no recovery interpretation.
    assert comparison["differences"]["rom_rad"][0]["difference"]["value"] == pytest.approx(-10*pi/180, abs=1e-10)
    # Existing destinations are protected against overwriting retained outputs.
    subprocess_result = subprocess.run([sys.executable, str(ROOT / "examples/m4_dual_synthetic.py"),
                                       "--output-dir", str(tmp_path / "first")], cwd=ROOT, capture_output=True)
    assert subprocess_result.returncode != 0
    assert {p.name: p.read_bytes() for p in (tmp_path / "first").iterdir()} == outputs[0]
