"""CP3 regression gates against frozen independent labels."""

import importlib
from math import pi

import pytest


def runner():
    spec = importlib.util.find_spec("kineimu_shoulder.validation.perturbation")
    assert spec is not None, "CP3 runner missing"
    return importlib.import_module(spec.name)


def case(condition, target="SAME", seed=0, trajectory="F90"):
    from kineimu_shoulder.validation.manifest import cases

    return next(r for r in cases() if r["id"] == f"{trajectory}/{condition}/{target}/{seed}")


def test_working_noise_keeps_frozen_truth_and_w_gates(tmp_path):
    r = runner().run(case("N-G-H", seed=1103), tmp_path)
    assert r["counts"]["truth"] == 3
    assert r["coverage"]["denominator_s"] == 16.5
    assert r["errors"]["interval_speed"]["tolerance"] == pi / 30
    assert r["errors"]["B.orientation"]["tolerance"] == pi / 180
    assert r["annotations"]["nominal"][0]["start_us"] == 5340000


def test_packet_periodic_preserves_sequences_and_loss_counts(tmp_path):
    r = runner().run(case("L-P-PER", "B"), tmp_path)
    n = r["processed"]["nodes"]["B"]
    assert n["retention"]["lost_samples"] == 64
    assert n["retention"]["lost_packets"] == 16
    assert r["coverage"]["denominator_s"] == 16.5
    assert r["annotations"]["nominal"][0]["truth_id"] == "F90:rep-1"


def test_burst_rejects_ahrs_without_rescued_numbers(tmp_path):
    r = runner().run(case("L-S-BURST", "B"), tmp_path)
    assert r["passed"]
    assert r["stage_disposition"] == "expected_rejection"
    assert r["exception_stage"] == "ahrs"
    assert r["coverage"]["relative"] == 0
    assert "elevation" not in r["errors"] and "interval_speed" not in r["errors"]
    assert r["counts"]["missed"] == 3


def test_world_common_yaw_relative_invariant_but_proxy_excluded(tmp_path):
    r = runner().run(case("D-H-X-world"), tmp_path)
    assert r["errors"]["elevation"]["max_abs_error"] < 1e-12
    assert r["counts"]["valid"] == 3
    assert r["coverage"]["proxy"] == 0
    assert "thorax_drift_exceeded" in r["proxy_reasons"]
    assert r["accuracy_passed"] is False


def test_fit_independent_warmup_and_known_apply(tmp_path):
    r = runner().run(case("C-FIT-H", seed=2207), tmp_path)
    for n in r["processed"]["nodes"].values():
        assert n["calibration"]["fit_window_us"] == [0, 5000000]
        assert n["calibration_fit"]["residual_norm_rads"] <= 0.001
    a = runner().run(case("C-APPLY"), tmp_path)
    assert a["passed"], a["failed_gates"]
    assert a["errors"]["B.calibration_acceleration"]["max_abs_error"] <= 1e-12


def test_export_rejects_existing_output(tmp_path):
    with pytest.raises(FileExistsError):
        runner().export(tmp_path)


def test_session_memo_has_identical_canonical_outputs(monkeypatch, tmp_path):
    from contextlib import nullcontext

    module = runner()
    r = module.run(case("N-G-H", seed=5519), tmp_path)
    monkeypatch.setattr(module, "memoized_session", nullcontext)
    uncached = module.run(case("N-G-H", seed=5519), tmp_path)
    assert module.canonical(r) == module.canonical(uncached)


@pytest.mark.parametrize("condition", ["EV-align-A-assumed-E", "EV-map-A-assumed-E"])
def test_assumed_evidence_retains_experimental_label(condition, tmp_path):
    r = runner().run(case(condition), tmp_path)
    assert r["passed"], r.get("message", r["failed_gates"])
    assert r["anatomical_eligible"] is False


def test_hash_control_blocks_unresolved_evidence(tmp_path):
    r = runner().run(case("EV-map-A-hash-E"), tmp_path)
    assert r["passed"], r["failed_gates"]
    assert r["coverage"]["relative"] == 0
    assert r["counts"]["valid"] in (0, None)


def test_independent_auditor_catches_error_arithmetic_tamper(tmp_path):
    import gzip
    import importlib.util
    import json
    from pathlib import Path

    module = runner()
    folder = tmp_path / "case"
    module._worker((case("N-G-L", seed=1103), str(folder)))
    spec = importlib.util.spec_from_file_location(
        "cp3_auditor", Path(module.ROOT) / "validation/auditors/synthetic.py"
    )
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    assert auditor.audit_case(folder, case("N-G-L", seed=1103)) > 0
    path = folder / "errors.json.gz"
    errors = json.loads(gzip.decompress(path.read_bytes()))
    errors["elevation"]["absolute_error"][0] = 1.0
    path.write_bytes(gzip.compress(module.canonical(errors), mtime=0))
    with pytest.raises(AssertionError):
        auditor.audit_case(folder, case("N-G-L", seed=1103))


def test_working_clock_roundoff_preserves_exact_integer_endpoint(tmp_path):
    r = runner().run(case("D-C-H-minus-exact", "B", trajectory="AL90"), tmp_path)
    assert r["coverage"]["relative"] == 1.0
    assert r["counts"]["valid"] == 3
    assert None not in r["errors"]["elevation"]["actual"]
    assert r["errors"]["elevation"]["n"] == len(r["errors"]["elevation"]["actual"])
    assert r["passed"], r["failed_gates"]


def test_known_yaw_bound_binds_its_declared_evaluation_window(tmp_path):
    r = runner().run(case("D-H-H-world"), tmp_path)
    evidence = r["processed"]["trace"]["drift_evidence"]
    assert evidence["covered_window_us"] == [5000000, 21500000]
    assert evidence["bound_rad"] == pytest.approx(0.02 * pi / 180 * 16.5)
    assert "zero drift" not in evidence["method"]


def test_uncovered_drift_retains_exact_upstream_reason(tmp_path):
    r = runner().run(case("EV-drift-uncovered-E"), tmp_path)
    assert r["passed"], r["failed_gates"]
    assert r["counts"]["valid"] == 3
    assert r["coverage"]["proxy"] == 0
    assert "thorax_drift_unbounded" in r["proxy_reasons"]


def test_one_row_cannot_invent_warmup_observation(tmp_path):
    r = runner().run(case("INPUT-one-row"), tmp_path)
    assert r["passed"]
    assert r["errors"]["B.initialization"]["support"] == [0, 5000000]
    assert r["errors"]["B.initialization"]["actual"][1] is None
    assert r["errors"]["B.initialization"]["n"] == 1
    assert r["errors"]["B.orientation"]["max_abs_error"] is None


def test_world_yaw_recipe_identifies_isolation_path(tmp_path):
    r = runner().run(case("D-H-L-world"), tmp_path)
    assert "world yaw" in r["processed"]["nodes"]["A"]["source"]["input_recipe"]


def test_long_clock_exact_map_preserves_censored_terminal_candidate(tmp_path):
    r = runner().run(case("D-C-H-minus-exact", "B", trajectory="F90L"), tmp_path)
    assert r["passed"], r["failed_gates"]
    assert r["counts"]["valid"] == 54
    assert r["coverage"]["relative"] == 1.0


@pytest.mark.parametrize("condition,target,seed", [
    ("L-S-ONE", "B", 0), ("L-P-ONE", "B", 0), ("I-JL", "SAME", 1103),
])
def test_explicit_gap_reconstruction_keeps_original_losses_and_frozen_gates(condition, target, seed, tmp_path):
    r = runner().run(case(condition, target, seed), tmp_path)
    assert r["passed"], r["failed_gates"]
    assert r["errors"]["interval_speed"]["max_abs_error"] <= pi / 30
    assert r["processed"]["nodes"]["B"]["retention"]["lost_samples"] > 0
    assert r["processed"]["nodes"]["B"]["reconstruction"]["knots"]


def test_independent_auditor_catches_inserted_rate_tamper(tmp_path):
    import gzip
    import importlib.util
    import json
    from pathlib import Path

    module = runner()
    folder = tmp_path / "case"
    c = case("L-P-ONE", "B")
    module._worker((c, str(folder)))
    spec = importlib.util.spec_from_file_location("cp3_reconstruction_auditor",
                                               Path(module.ROOT) / "validation/auditors/synthetic.py")
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    assert auditor.audit_case(folder, c) > 0
    path = folder / "processed.json.gz"
    processed = json.loads(gzip.decompress(path.read_bytes()))
    reconstructed = processed["nodes"]["B"]["reconstruction"]
    knot = reconstructed["knots"][0][2]
    inserted = reconstructed["timestamp_us"].index(knot)
    reconstructed["angular_rate_rads"][inserted][0] += .1
    path.write_bytes(gzip.compress(module.canonical(processed), mtime=0))
    with pytest.raises(AssertionError):
        auditor.audit_case(folder, c)
