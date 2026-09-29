"""CP2 integration: independent M5 F0/F1 labels, actual pinned sensor pipeline."""

import importlib

import pytest


def runner():
    # Missing runner must fail as an assertion before its implementation exists.
    spec = importlib.util.find_spec("kineimu_shoulder.validation.baseline")
    assert spec is not None, "CP2 full-chain runner is missing"
    return importlib.import_module(spec.name)


@pytest.mark.parametrize("path", ["E", "S", "Q"])
def test_flexion_full_chain_against_frozen_truth(path, tmp_path):
    result = runner().run_case("F90", path, tmp_path)
    # M5 F1: three complete cycles, full evaluation coverage, 90 degree peak.
    assert result["counts"] == {"truth": 3, "valid": 3, "missed": 0, "false": 0}
    assert result["coverage"]["relative"] == 1.0
    assert result["coverage"]["proxy"] == 1.0
    assert result["passed"], result["failed_gates"]
    assert result["source_type"] == "synthetic"
    assert result["anatomical_eligible"] is False
    assert result["processed"]["nodes"]["B"]["calibration_executed"] == (path != "E")
    assert result["processed"]["nodes"]["B"]["ahrs_executed"] == (path != "E")
    assert "summary.hold_duration_s.mean" in result["errors"]
    assert "summary.thorax_extension_magnitude_rad.mean" in result["errors"]


def test_missing_heading_cannot_pass_by_dropping_numeric_rows(tmp_path):
    result = runner().run_case("F90", "S", tmp_path, missing_heading=True)
    # Contract global evidence gate: no eligible shoulder numbers, no fake zero errors.
    assert result["counts"]["valid"] is None
    assert result["coverage"]["relative"] == 0
    assert result["passed"] is False
    assert result["errors"]["elevation"]["max_abs_error"] is None


def test_export_refuses_existing_root_without_modification(tmp_path):
    root = tmp_path / "existing"
    root.mkdir()
    marker = root / "marker"
    marker.write_bytes(b"immutable")
    with pytest.raises(FileExistsError):
        runner().export(root)
    assert marker.read_bytes() == b"immutable"


def test_false_sensor_alignment_is_detected_against_independent_matrix(monkeypatch, tmp_path):
    module = runner()
    # Omitting post-AHRS R_NK leaves the humeral axis in node coordinates.
    monkeypatch.setattr(module, "align_segment", lambda q, alignment: q)
    result = module.run_case("F90", "S", tmp_path)
    assert result["passed"] is False
    assert "B.orientation" in result["failed_gates"]
    assert result["errors"]["B.orientation"]["max_abs_error"] > 1


def test_all_excluded_cycles_keep_null_metrics_and_zero_active_time(tmp_path):
    result = runner().run_case("WRONG", "E", tmp_path)
    # F6: declared left abduction with right-abduction rotation; 3 plane exclusions.
    assert result["counts"] == {"truth": 0, "valid": 0, "missed": 0, "false": 0}
    assert result["derived"]["summary"]["active_time_s"]["value"] == 0
    assert result["derived"]["summary"]["rom_sd"]["value"] is None
    assert result["passed"], result["failed_gates"]


def test_exact_later_session_uses_rational_grid_crossing(tmp_path):
    result = runner().run_case("F90-NEXT", "E", tmp_path)
    # U1: 100 deg / 1.5 s; 20 deg at exactly 0.30 s, rational nominal grid.
    assert result["derived"]["segmentation"]["candidates"][0]["start_us"] == 5300000
    assert result["passed"], result["failed_gates"]


def test_same_declared_calibration_keeps_later_session_comparable(tmp_path):
    from kineimu_shoulder.summary import compare_summaries

    module = runner()
    earlier = module.run_case("F90", "E", tmp_path)["_summary"]
    later = module.run_case("F90-NEXT", "E", tmp_path)["_summary"]
    pair = compare_summaries([earlier, later])[0]
    assert pair.comparable, pair.differing_keys
    # F1/U1 rational endpoints: (100-10) - (90-9.9) = 9.9 degrees.
    from math import pi

    assert pair.differences["rom_rad"][0].difference.value == pytest.approx(9.9 * pi / 180, abs=2e-10)
