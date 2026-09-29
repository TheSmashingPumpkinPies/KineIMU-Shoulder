"""Stage C expectations from the retained compatibility record, not M5 output."""

import importlib
import json
import subprocess
import sys
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

from kineimu_shoulder.io.m1_capture import iter_capture_records
from kineimu_shoulder.io.m1_packet import decode_sample_packet


def api():
    spec = importlib.util.find_spec("kineimu_shoulder.validation.recorded_node")
    assert spec is not None, "complete recorded Node B runner is missing"
    return importlib.import_module(spec.name)


def test_full_original_observations_reach_calibration_and_ahrs(monkeypatch):
    module = api()
    seen = []
    estimate = module.estimate_orientation

    def observe(times, acceleration, rate, **kwargs):
        seen.append((times.copy(), acceleration.copy(), rate.copy()))
        return estimate(times, acceleration, rate, **kwargs)

    monkeypatch.setattr(module, "estimate_orientation", observe)
    result = module.run_recorded(module.NODE_B)
    packets = [decode_sample_packet(r.payload) for r in iter_capture_records(BytesIO(module.NODE_B.path.read_bytes()))]
    samples = [s for p in packets for s in p.samples]
    epoch = result["epochs"][0]
    # node_b_20260913_compatibility.md: all 208 packets / 832 samples, original span.
    assert result["stage_disposition"] == "PASSED"
    assert result["qc"]["packets_decoded"] == 208
    assert result["qc"]["samples_decoded"] == 832
    assert result["qc"]["issues"] == []
    assert epoch["device_time_us"][0] == 257030578
    assert epoch["device_time_us"][-1] == 264845581
    assert epoch["packet_sequences"] == list(range(5867, 6075))
    assert epoch["sample_sequences"] == list(range(23468, 24300))
    assert epoch["device_time_us"] == [s.device_time_us for s in samples]
    assert epoch["sample_flags"] == [0] * 832
    assert epoch["packet_flags"] == [0] * 208
    assert len(epoch["host_monotonic_ns"]) == 208
    assert len(seen) == 1 and len(seen[0][0]) == 832
    np.testing.assert_array_equal(seen[0][0], epoch["device_time_us"])
    # SI sensitivities in BACKEND_CONTRACTS / register configuration; identity example.
    acceleration = np.array([s.accel_raw for s in samples]) * (0.122e-3 * 9.80665)
    rate = np.deg2rad(np.array([s.gyro_raw for s in samples]) * 17.5e-3)
    np.testing.assert_allclose(seen[0][1], acceleration, rtol=0, atol=1e-14)
    np.testing.assert_allclose(seen[0][2], rate, rtol=0, atol=1e-14)
    np.testing.assert_array_equal(epoch["sensor_acceleration_mps2"], epoch["node_acceleration_mps2"])
    np.testing.assert_array_equal(epoch["sensor_angular_rate_rads"], epoch["node_angular_rate_rads"])
    q = np.array(epoch["orientation"]["quaternion_wn"])
    assert q.shape == (832, 4) and np.isfinite(q).all()
    np.testing.assert_allclose(np.linalg.norm(q, axis=1), 1, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(q[0], [1, 0, 0, 0])  # Explicit assumed initial world.
    assert epoch["orientation"]["heading_observable"] is False
    assert result["source_sha256_before"] == result["source_sha256_after"] == module.NODE_B.sha256
    assert result["evidence_label"] == "Assumed/Experimental"
    assert result["anatomical_eligible"] is False
    assert result["calibration"]["fit_method"] == "illustrative_identity_no_fit"
    assert result["calibration"]["fit_window_us"] == [0, 1]
    assert result["reconstruction"] == "NOT APPLIED; original observations only"


def test_real_gate_interfaces_keep_single_node_metrics_unavailable(monkeypatch):
    module = api()
    calls = []
    gate = module.gate_report

    def observe(**kwargs):
        calls.append(kwargs)
        return gate(**kwargs)

    monkeypatch.setattr(module, "gate_report", observe)
    result = module.run_recorded(module.NODE_B)
    assert len(calls) == 1
    # Explicit self-input rejection probe: no invented A stream or q_WSegment.
    assert calls[0]["thorax"] is calls[0]["humerus"]
    assert calls[0]["thorax"].node_id == "B"
    for name in ("thorax_clock_map", "humerus_clock_map", "heading_relation", "thorax_alignment",
                 "humerus_alignment", "heading_evidence", "drift_evidence"):
        assert calls[0][name] is None
    downstream = result["downstream"]
    assert downstream["probe_kind"] == "single-node self-input rejection probe; no paired/aligned stream"
    assert downstream["observed_node_ids"] == ["B"]
    assert downstream["common_grid_established"] is False
    assert "thorax_node_missing" in downstream["missing_evidence"]
    gates = downstream["gates"]
    # Existing M2 / M3 contracts and actual M4 propagation.
    assert set(gates["relative"]["reason"]) == {"clock_map_missing"}
    assert set(gates["elevation"]["reason"]) == {"clock_or_heading_missing"}
    assert all(q == [None] * 4 for q in gates["relative"]["quaternion_th"])
    assert gates["elevation"]["elevation_rad"] == [None] * 832
    assert gates["speed"]["relative_angular_speed_rads"] == [None] * 831
    assert not any(gates["relative"]["valid"]) and not any(gates["elevation"]["valid"])
    summary = gates["summary"]
    assert summary["analysis_valid"] is False
    assert summary["valid_count"] is None and summary["proxy_valid_count"] is None
    assert summary["rom_sd"]["value"] is None and summary["rom_sd"]["valid"] is False
    assert gates["elevation"]["anatomical_eligible"] is False
    assert result["motion_accuracy"] == {"value": None, "valid": False, "reason": "no_motion_ground_truth"}


@pytest.mark.parametrize("fault", ["hash", "node", "count", "endpoint", "truncated"])
def test_bad_source_retains_failure_and_never_runs_ahrs(tmp_path, monkeypatch, fault):
    module = api()
    copied = tmp_path / "source" / "node-b.kimu"
    copied.parent.mkdir()
    copied.write_bytes(module.NODE_B.path.read_bytes())
    selected = replace(module.NODE_B, path=copied)
    changes = {"hash": {"sha256": "0" * 64}, "node": {"node_id": module.NodeId.A},
               "count": {"expected_samples": 128}, "endpoint": {"expected_endpoints_us": (0, 264845581)}}
    if fault == "truncated":
        copied.write_bytes(copied.read_bytes()[:-1])
        selected = replace(selected, sha256=sha256(copied.read_bytes()).hexdigest())
    else:
        selected = replace(selected, **changes[fault])
    monkeypatch.setattr(module, "estimate_orientation", lambda *a, **k: pytest.fail("AHRS on invalid input"))
    output = tmp_path / "failed"
    assert module.export_recorded(output, selected=selected) == 1
    result = json.loads((output / "cases/REC-NODE-B/result.json").read_bytes())
    assert result["stage_disposition"] == "FAILED"
    assert result["downstream"]["stage_disposition"] == "NOT RUN"
    assert json.loads((output / "report.json").read_bytes())["failed_case_count"] == 1


@pytest.mark.parametrize("fault", ["absent", "permission", "ahrs", "mutation"])
def test_unavailable_or_changed_input_cannot_pass(tmp_path, monkeypatch, fault):
    module = api()
    copied = tmp_path / "input" / "node-b.kimu"
    copied.parent.mkdir()
    copied.write_bytes(module.NODE_B.path.read_bytes())
    selected = replace(module.NODE_B, path=copied)
    if fault == "absent":
        selected = replace(selected, path=copied.with_name("absent.kimu"))
    elif fault == "permission":
        original = type(copied).read_bytes

        def deny(path):
            if path == copied:
                raise PermissionError("test copy unavailable")
            return original(path)

        monkeypatch.setattr(type(copied), "read_bytes", deny)
    else:
        original = module.estimate_orientation

        def fail(*args, **kwargs):
            if fault == "ahrs":
                raise ValueError("controlled AHRS failure")
            result = original(*args, **kwargs)
            copied.write_bytes(copied.read_bytes() + b"test mutation")
            return result

        monkeypatch.setattr(module, "estimate_orientation", fail)
    output = tmp_path / "attempt"
    assert module.export_recorded(output, selected=selected) == (2 if fault in ("absent", "permission") else 1)
    report = json.loads((output / "report.json").read_bytes())
    assert report["stage_passed"] is False and report["checkpoint_disposition"] == "OPEN"
    assert report["results"][0]["disposition"] == ("BLOCKED" if fault in ("absent", "permission") else "FAILED")


def test_fresh_root_protection_and_complete_hash_inventory(tmp_path):
    module = api()
    first, second = tmp_path / "first", tmp_path / "second"
    assert module.export_recorded(first) == module.export_recorded(second) == 0
    with pytest.raises(FileExistsError):
        module.export_recorded(first)
    with pytest.raises(ValueError):
        module.export_recorded(module.NODE_B.path.parent / "never-created")
    listed = dict((name, digest) for digest, name in
                  (line.split("  ") for line in (first / "SHA256SUMS.txt").read_text().splitlines()))
    assert set(listed) == {"manifest.json", "report.json", "cases/REC-NODE-B/result.json"}
    for name, digest in listed.items():
        content = (first / name).read_bytes()
        assert sha256(content).hexdigest() == digest
        assert content == (second / name).read_bytes()
        assert b"\r" not in content and b"NaN" not in content and str(first).encode() not in content
    report = json.loads((first / "report.json").read_bytes())
    assert report["stage_passed"] is True and report["passed"] is False
    assert report["checkpoint_disposition"] == "OPEN" and report["remaining_stages"] == ["D", "E"]
    assert report["not_run_count"] == 0 and report["case_count"] == 1
    manifest = json.loads((first / "manifest.json").read_bytes())
    assert manifest["formal"] is False and manifest["stage"] == "C-recorded-node-B"
    assert "uv.lock" in manifest["source_file_sha256"]


def test_cli_runs_complete_node_b_without_accepting_cp4(tmp_path):
    output = tmp_path / "cli"
    process = subprocess.run([sys.executable, "-m", "kineimu_shoulder.validation.recorded_node",
                              "--output", str(output)], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    report = json.loads((output / "report.json").read_bytes())
    assert report["stage_passed"] is True and report["checkpoint_disposition"] == "OPEN"


def auditor():
    path = Path(__file__).resolve().parents[2] / "experiments/M5_CP4_STAGE_C_20260927/audit.py"
    assert path.exists(), "independent stage C raw/product auditor is missing"
    spec = importlib.util.spec_from_file_location("cp4_stage_c_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_independent_audit_checks_every_raw_row_and_rejection(tmp_path):
    module = api()
    output = tmp_path / "audit-control"
    assert module.export_recorded(output) == 0
    checked = auditor().audit(output, source=module.NODE_B.path)
    assert checked["passed"] is True
    assert checked["packets_checked"] == 208 and checked["samples_checked"] == 832
    assert checked["ahrs_quaternions_checked"] == 832
    assert checked["downstream_rows_checked"] == 832


@pytest.mark.parametrize("fault", ["si", "time", "quaternion", "reason", "summary", "source-map", "extra"])
def test_independent_audit_rejects_rehashed_product_corruption(tmp_path, fault):
    module = api()
    output = tmp_path / "corrupt"
    assert module.export_recorded(output) == 0
    target = output / ("manifest.json" if fault == "source-map" else "cases/REC-NODE-B/result.json")
    result = json.loads(target.read_bytes())
    if fault == "si":
        result["epochs"][0]["node_angular_rate_rads"][800][0] += .01
    elif fault == "time":
        result["epochs"][0]["device_time_us"][800] += 1
    elif fault == "quaternion":
        result["epochs"][0]["orientation"]["quaternion_wn"][800] = [1, 0, 0, 0]
    elif fault == "reason":
        result["downstream"]["gates"]["relative"]["reason"][800] = "valid"
    elif fault == "summary":
        result["downstream"]["gates"]["summary"]["rom_sd"]["value"] = 0
    elif fault == "source-map":
        result["source_file_sha256"]["uv.lock"] = "0" * 64
    else:
        (output / "unlisted.txt").write_bytes(b"unexpected")
    target.write_bytes(module.canonical(result))
    # Deliberately refresh container/result hashes; semantic audit must still reject.
    report_path = output / "report.json"
    report = json.loads(report_path.read_bytes())
    report["results"][0]["sha256"] = sha256((output / "cases/REC-NODE-B/result.json").read_bytes()).hexdigest()
    report["evidence_index"]["REC-NODE-B"]["sha256"] = report["results"][0]["sha256"]
    report_path.write_bytes(module.canonical(report))
    names = [line.split("  ")[1] for line in (output / "SHA256SUMS.txt").read_text().splitlines()]
    (output / "SHA256SUMS.txt").write_text("".join(
        f"{sha256((output / name).read_bytes()).hexdigest()}  {name}\n" for name in names), encoding="utf-8")
    with pytest.raises(ValueError):
        auditor().audit(output, source=module.NODE_B.path)
