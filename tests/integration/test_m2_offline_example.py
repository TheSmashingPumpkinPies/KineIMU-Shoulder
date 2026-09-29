"""End-to-end M2.5 replay of known motion and an immutable M1 excerpt."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "examples/m2_offline_replay.py"
RECORDED = ROOT / "firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary.kimu"
RECORDED_SHA256 = "1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201"


def _run(output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_offline_example_replays_twice_with_identical_evidenced_outputs(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    before = hashlib.sha256(RECORDED.read_bytes()).hexdigest()
    assert before == RECORDED_SHA256  # Retained M1 config.json source hash.

    for output in (first, second):
        completed = _run(output)
        assert completed.returncode == 0, completed.stderr
        assert {p.name for p in output.iterdir()} == {"synthetic.json", "m1_node_b.json", "report.json"}
    assert hashlib.sha256(RECORDED.read_bytes()).hexdigest() == before
    for name in ("synthetic.json", "m1_node_b.json", "report.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()

    synthetic = json.loads((first / "synthetic.json").read_text(encoding="utf-8"))
    recorded = json.loads((first / "m1_node_b.json").read_text(encoding="utf-8"))
    report = json.loads((first / "report.json").read_text(encoding="utf-8"))
    assert synthetic["sample_count"] == 101
    # Analytical fixture: constant +pi/2 rad/s about Z for 1 s gives +90° yaw.
    assert synthetic["quaternion_wn"][-1][0] == pytest.approx(2**-0.5, abs=3e-5)
    assert synthetic["quaternion_wn"][-1][3] == pytest.approx(2**-0.5, abs=3e-5)
    assert synthetic["heading_observable"] is False
    assert recorded["sample_count"] == 128
    assert recorded["source_sha256"] == RECORDED_SHA256
    # Retained M1 stream begins at sample sequence 23468; excerpt must preserve it.
    assert recorded["sample_sequence"][0] == 23468
    assert len(recorded["device_time_us"]) == 128
    assert report["m1_qc"]["packets_decoded"] == 208
    assert report["m1_qc"]["samples_decoded"] == 832
    assert report["m1_qc"]["issues"] == []
    assert report["dependency_lock_sha256"] == hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest()
    for name in ("synthetic.json", "m1_node_b.json"):
        assert report["output_sha256"][name] == hashlib.sha256((first / name).read_bytes()).hexdigest()
    assert "Assumed/Experimental" in recorded["evidence_status"]


def test_offline_example_refuses_raw_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "raw" / "example"
    completed = _run(output)
    assert completed.returncode != 0
    assert not output.exists()
