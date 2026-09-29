"""CP4 B: frozen CP1 disk inputs, independent F1/Q labels and budgets."""

import gzip
import importlib
import json
import shutil
import subprocess
import sys
from hashlib import sha256

import pytest


def runner():
    spec = importlib.util.find_spec("kineimu_shoulder.validation.stored_demo")
    assert spec is not None, "complete stored Q replay is missing"
    return importlib.import_module(spec.name)


def test_independent_frame_audit_of_retained_complete_demo(tmp_path):
    module = runner()
    # Actual retained observations remain in sensor axes until apply_calibration;
    # the independent audit must compare R_NS against calibrated node SI.
    process = subprocess.run([sys.executable, str(module.ROOT / "experiments/M5_CP4_STAGE_B_20260927/audit.py"),
                              "experiments/M5_CP4_STAGE_B_DEMO_20260927", str(tmp_path / "audit.json")],
                             cwd=module.ROOT, capture_output=True, text=True)
    assert process.returncode == 0, process.stdout + process.stderr


@pytest.mark.parametrize("trajectory", ["F90", "AL90", "AR90", "T-MIX"])
def test_complete_stored_pair_without_generating_measurements(trajectory, tmp_path, monkeypatch):
    module = runner()
    from kineimu_shoulder.validation import perturbation, source

    def forbidden(*args, **kwargs):
        pytest.fail("stored replay must not generate or encode replacement measurements")

    monkeypatch.setattr(perturbation, "generate", forbidden)
    monkeypatch.setattr(perturbation, "packets", forbidden)
    monkeypatch.setattr(source, "generate", forbidden)
    result = module.run_stored(trajectory, tmp_path)
    # Frozen F1 and CP1 README: 3 complete repetitions, 2151 samples/538 packets,
    # full 5–21.5 s evaluation, no false/missed reps, clean S/Q budgets.
    assert result["counts"] == dict(truth=3, valid=3, missed=0, false=0)
    assert result["coverage"]["relative"] == result["coverage"]["proxy"] == 1.0
    assert result["passed"], result["failed_gates"]
    assert result["source_type"] == "synthetic"
    assert result["anatomical_eligible"] is False
    assert result["input_audit"]["before"] == result["input_audit"]["after"]
    for node in ("A", "B"):
        data = result["processed"]["nodes"][node]
        assert data["calibration_executed"] and data["ahrs_executed"]
        assert data["replay"]["qc"]["samples_decoded"] == 2151
        assert data["replay"]["qc"]["packets_decoded"] == 538
        assert data["source"]["device_time_us"][0] == 0
        assert data["source"]["device_time_us"][-1] == 21500000
        assert data["replay"]["source_sha256"] == result["input_audit"]["before"][f"{trajectory}/{node}.kimu"]
    # Q quantization error is nonzero; error gates must use actual decoded input.
    assert result["errors"]["B.orientation"]["max_abs_error"] > 0
    assert result["errors"]["elevation"]["n"] == 1651
    assert result["errors"]["interval_speed"]["n"] == 1650
    # Frozen Q half-LSB sensor-component bounds (contract quantization section).
    for node in ("A", "B"):
        quantization = result["quantization"][node]
        assert quantization["acceleration_component_max_mps2"] <= 0.00059820565 + 1e-12
        assert quantization["rate_component_max_rads"] <= 0.00015271631 + 1e-12
    assert not list(tmp_path.rglob("*.kimu"))


@pytest.mark.parametrize("target", ["F90/B.kimu", "F90/metadata.json", "annotations.json", "SHA256SUMS.json",
                                   "manifest.json", "observation-labels.json", "case-manifest.json", "F90/A-si.json"])
def test_rejects_changed_disk_input_before_processing(target, tmp_path):
    module = runner()
    copied = tmp_path / "inputs"
    shutil.copytree(module.CP1_ROOT, copied)
    path = copied / target
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="digest"):
        module.run_stored("F90", tmp_path, input_root=copied)


def test_export_keeps_cp4_open_and_binds_all_products(tmp_path):
    module = runner()
    output = tmp_path / "development"
    assert module.export_stored(output) == 0
    report = json.loads((output / "report.json").read_text())
    assert report["stage_passed"] and report["checkpoint_disposition"] == "OPEN"
    assert report["passed"] is False
    assert report["requirement_index"]["complete-stored-replay"] == ["Q-F90", "Q-AL90", "Q-AR90", "Q-T-MIX"]
    assert report["case_count"] == 4 and report["failed_case_count"] == 0
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["formal"] is False
    assert manifest["processing_version"] == "m5-processing/1.1"
    # Existing independent CP3 auditor recomputes O/F/T matrices, geodesics,
    # arithmetic, retention and full support, without invoking the pipeline.
    spec = importlib.util.spec_from_file_location("cp3_audit", module.ROOT / "experiments/M5_CP3_20260926/audit.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    for trajectory in ("F90", "AL90", "AR90", "T-MIX"):
        case = dict(id=f"{trajectory}/CLEAN-Q/SAME/0", trajectory=trajectory,
                    parameters={}, target="SAME", **{"class": "C"})
        assert audit.audit_case(output / f"cases/Q-{trajectory}", case) > 0
    for line in (output / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ")
        assert sha256((output / name).read_bytes()).hexdigest() == digest
    # Independent arithmetic audit must reject corruption in a test-only output.
    errors_path = output / "cases/Q-F90/errors.json.gz"
    original_errors = errors_path.read_bytes()
    changed = json.loads(gzip.decompress(original_errors))
    changed["elevation"]["absolute_error"][0] += 0.01
    errors_path.write_bytes(gzip.compress(json.dumps(changed).encode(), mtime=0))
    with pytest.raises(AssertionError):
        audit.audit_case(output / "cases/Q-F90", dict(id="F90/CLEAN-Q/SAME/0", trajectory="F90"))
    errors_path.write_bytes(original_errors)
    before = (output / "report.json").read_bytes()
    with pytest.raises(FileExistsError):
        module.export_stored(output)
    assert (output / "report.json").read_bytes() == before
