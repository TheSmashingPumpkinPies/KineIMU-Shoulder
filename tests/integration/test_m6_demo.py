"""Frozen M6 CP2 contract: real stored replay, strict exits and readable evidence."""

import gzip
import importlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "datasets/samples/m6_synthetic"


def runner():
    spec = importlib.util.find_spec("kineimu_shoulder.validation.demo")
    assert spec is not None, "M6 thin demo wrapper is missing"
    return importlib.import_module(spec.name)


def verify_index(root):
    entries = {}
    for line in (root / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ")
        assert name not in entries
        assert sha256((root / name).read_bytes()).hexdigest() == digest
        entries[name] = digest
    assert set(entries) == {p.relative_to(root).as_posix() for p in root.rglob("*")
                            if p.is_file() and p != root / "SHA256SUMS.txt"}
    return entries


def independent_auditor():
    path = ROOT / "validation/auditors/demo.py"
    assert path.exists(), "independent CP2 pair auditor is missing"
    spec = importlib.util.spec_from_file_location("m6_pair_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_independent_auditor_refuses_incomplete_success_claim(tmp_path):
    audit = independent_auditor()
    (tmp_path / "run.json").write_text(json.dumps(dict(demo_passed=True, exit_code=0)))
    with pytest.raises((AssertionError, ValueError, FileNotFoundError)):
        audit.audit_run(tmp_path, require_clean=False)


@pytest.mark.parametrize("path", ["docs/new", "scripts/new", "examples/new", "benchmarks/new", "protocols/new",
                                  "integrations/new", ".github/new", ".git/new", ".agents/new", ".codex/new",
                                  "datasets/new", "firmware/new", "tests/new", "experiments/new",
                                  "kineimu_shoulder/new", "other-new", "demo-output-new/nested", "raw/new"])
def test_rejects_unsafe_output_before_creating_anything(path):
    module = runner()
    output = ROOT / path
    assert not output.exists()
    assert module.run_demo(output) == 1
    assert not output.exists()


def test_existing_file_and_directory_are_never_overwritten(tmp_path):
    module = runner()
    for output in (tmp_path / "file", tmp_path / "directory"):
        if output.name == "file":
            output.write_bytes(b"retained")
        else:
            output.mkdir()
            (output / "keep").write_bytes(b"retained")
        assert module.run_demo(output) == 1
        assert (output if output.is_file() else output / "keep").read_bytes() == b"retained"


@pytest.mark.parametrize("change,exit_code", [("missing", 2), ("tampered", 1)])
def test_input_refusal_before_mkdir(change, exit_code, tmp_path):
    module = runner()
    inputs = tmp_path / "inputs"
    shutil.copytree(SAMPLE, inputs)
    capture = inputs / "F90/B.kimu"
    if change == "missing":
        capture.unlink()
    else:
        capture.write_bytes(capture.read_bytes() + b"corrupt")
    output = tmp_path / "out"
    assert module.run_demo(output, input_root=inputs) == exit_code
    assert not output.exists()


def test_raw_component_and_input_ancestors_protected(tmp_path):
    module = runner()
    inputs = tmp_path / "new-parent/inputs"
    # Absent input ancestor must be refused as an output before input auditing.
    assert module.run_demo(inputs.parent, input_root=inputs) == 1
    output = tmp_path / "RAW/new"
    assert module.run_demo(output) == 1
    assert not output.exists()


def test_resolved_link_cannot_enter_repository_sources(tmp_path):
    module = runner()
    link = tmp_path / "link"
    if sys.platform == "win32":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(ROOT / "docs")],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        link.symlink_to(ROOT / "docs", target_is_directory=True)
    assert module.run_demo(link / "new-demo") == 1
    assert not (ROOT / "docs/new-demo").exists()


def test_interrupted_export_retains_partial_root_and_not_run_reasons(tmp_path, monkeypatch):
    module = runner()
    from kineimu_shoulder.validation import stored_demo

    def interrupted(output, *, input_root):
        output.mkdir()
        (output / "partial.txt").write_bytes(b"preserved")
        raise RuntimeError("controlled processing interruption")

    monkeypatch.setattr(stored_demo, "export_stored", interrupted)
    output = tmp_path / "out"
    assert module.run_demo(output) == 1
    assert (output / "replay/partial.txt").read_bytes() == b"preserved"
    run = json.loads((output / "run.json").read_bytes())
    assert not run["demo_passed"] and run["disposition"] == "FAILED"
    assert len(run["trajectories"]) == 4
    assert all(row["disposition"] == "NOT RUN" and row["reason"] for row in run["trajectories"])
    verify_index(output)
    assert module.run_demo(output) == 1


def test_numerical_failure_takes_priority_over_blocked(tmp_path, monkeypatch):
    module = runner()
    from kineimu_shoulder.validation import stored_demo

    def mixed(output, *, input_root):
        output.mkdir()
        for name, disposition in (("F90", "FAILED"), ("AL90", "BLOCKED")):
            folder = output / f"cases/Q-{name}"
            folder.mkdir(parents=True)
            (folder / "result.json").write_text(json.dumps(dict(passed=False, stage_disposition=disposition,
                                                                 failed_gates=["controlled_gate"])))
        return 2

    monkeypatch.setattr(stored_demo, "export_stored", mixed)
    output = tmp_path / "out"
    assert module.run_demo(output) == 1
    run = json.loads((output / "run.json").read_bytes())
    assert run["exit_code"] == 1 and not run["demo_passed"]
    assert run["trajectories"][0]["disposition"] == "FAILED"
    assert run["trajectories"][1]["disposition"] == "BLOCKED"
    assert "controlled_gate" in run["trajectories"][0]["failed_gates"]


def test_blocked_export_and_lost_input_still_retain_failure_record(tmp_path, monkeypatch):
    module = runner()
    from kineimu_shoulder.validation import stored_demo

    inputs = tmp_path / "inputs"
    shutil.copytree(SAMPLE, inputs)

    def blocked(output, *, input_root):
        output.mkdir()
        (input_root / "F90/B.kimu").unlink()
        raise FileNotFoundError("controlled loss of required input")

    monkeypatch.setattr(stored_demo, "export_stored", blocked)
    output = tmp_path / "out"
    assert module.run_demo(output, input_root=inputs) == 2
    run = json.loads((output / "run.json").read_bytes())
    assert not run["demo_passed"] and run["exit_code"] == 2
    assert run["input_sha256_after"] is None
    assert run["failed_gates"]
    assert all(row["disposition"] == "NOT RUN" and row["reason"] for row in run["trajectories"])
    verify_index(output)


def test_cli_help_usage_and_existing_output(tmp_path):
    entry = ROOT / "examples/m6_demo.py"
    assert entry.exists(), "M6 one-command entry is missing"
    for args, code in ((["--help"], 0), ([], 2), (["--unknown"], 2), (["--output", str(tmp_path)], 1)):
        process = subprocess.run([sys.executable, str(entry), *args], cwd=tmp_path,
                                 capture_output=True, text=True)
        assert process.returncode == code, process.stdout + process.stderr
    # No site packages: help works; missing scientific dependencies are BLOCKED, never success.
    output = tmp_path / "without-dependencies"
    process = subprocess.run([sys.executable, "-S", str(entry), "--output", str(output)],
                             cwd=tmp_path, capture_output=True, text=True)
    assert process.returncode == 2 and "BLOCKED" in process.stderr
    assert not output.exists()


def test_complete_demo_reads_sample_without_generating_observations(tmp_path, monkeypatch):
    module = runner()
    from kineimu_shoulder.validation import perturbation, source, stored_demo

    def forbidden(*args, **kwargs):
        pytest.fail("stored Demo must never generate or encode replacement sensor observations")

    monkeypatch.setattr(perturbation, "generate", forbidden)
    monkeypatch.setattr(perturbation, "packets", forbidden)
    monkeypatch.setattr(source, "generate", forbidden)
    before = stored_demo.input_audit(SAMPLE)
    output = tmp_path / "demo"
    assert module.run_demo(output, command=[sys.executable, str(ROOT / "examples/m6_demo.py"),
                                           "--output", str(output)]) == 0
    assert before == stored_demo.input_audit(SAMPLE)
    entries = verify_index(output)
    assert len(entries) == 25
    assert len(verify_index(output / "replay")) == 22
    assert not list(output.rglob("*.kimu"))
    run = json.loads((output / "run.json").read_bytes())
    assert run["contract_id"] == "m6-demo-contract/1.0"
    assert run["demo_passed"] and run["exit_code"] == 0
    assert run["input_sha256_before"] == run["input_sha256_after"] == before
    report = json.loads((output / "replay/report.json").read_bytes())
    assert report["stage_passed"] and not report["passed"] and report["checkpoint_disposition"] == "OPEN"
    for trajectory in ("F90", "AL90", "AR90", "T-MIX"):
        folder = output / f"replay/cases/Q-{trajectory}"
        result = json.loads((folder / "result.json").read_bytes())
        # Frozen CP1 / M5 contract: full clean Q, three reps, complete support and no false/missed reps.
        assert result["counts"] == dict(truth=3, valid=3, missed=0, false=0)
        assert result["coverage"]["relative"] == result["coverage"]["proxy"] == 1
        assert result["error_summary"]["elevation"]["n"] == 1651
        assert result["error_summary"]["interval_speed"]["n"] == 1650
        processed = json.loads(gzip.decompress((folder / "processed.json.gz").read_bytes()))
        for node in ("A", "B"):
            row = processed["nodes"][node]
            assert row["calibration_executed"] and row["ahrs_executed"]
            assert row["replay"]["qc"]["samples_decoded"] == 2151
            assert row["replay"]["qc"]["packets_decoded"] == 538
            assert not row["replay"]["qc"]["issues"]
        derived = json.loads(gzip.decompress((folder / "derived.json.gz").read_bytes()))
        summary = (output / "summary.md").read_text(encoding="utf-8")
        # Display is a unit conversion of each actual exported summary mean, never nominal 90 degrees.
        mean_rom = derived["summary"]["statistics"]["rom_rad"][0]["mean"]["value"]
        assert f"{math.degrees(mean_rom):.6f} deg" in summary
    assert "anatomical_eligible=false" in summary and "Assumed" in summary
    assert "ddof=1" in summary and "thorax" in summary
    assert "partial_start" in summary and "interrupted" in summary
    audited = independent_auditor().audit_run(output, require_clean=False)
    # Existing locked M5 independent audit on complete clean Q: 27,160 scalar checks per full four-Q run.
    assert audited["independently_recomputed_error_scalars"] == 27160
    # Pair comparison allows exactly the six declared process metadata fields.
    other = tmp_path / "second"
    shutil.copytree(output, other)
    second_run = json.loads((other / "run.json").read_bytes())
    second_run.update(pid=second_run["pid"] + 1, output_absolute_path=str(other), duration_s=123.0,
                      started_utc="2026-09-28T00:00:00+00:00", ended_utc="2026-09-28T00:02:03+00:00")
    second_run["command"][-1] = str(other)
    content = json.dumps(second_run, sort_keys=True, indent=2).encode()
    (other / "run.json").write_bytes(content)
    second_index = (other / "SHA256SUMS.txt").read_text().splitlines()
    (other / "SHA256SUMS.txt").write_text("\n".join(
        f"{sha256(content).hexdigest()}  run.json" if line.endswith("  run.json") else line
        for line in second_index) + "\n", encoding="utf-8")
    assert independent_auditor().audit_pair(output, other, require_clean=False)["cp2_passed"]
    second_run["undeclared_process_field"] = "must not be silently excluded"
    content = json.dumps(second_run, sort_keys=True, indent=2).encode()
    (other / "run.json").write_bytes(content)
    (other / "SHA256SUMS.txt").write_text("\n".join(
        f"{sha256(content).hexdigest()}  run.json" if line.endswith("  run.json") else line
        for line in second_index) + "\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        independent_auditor().audit_pair(output, other, require_clean=False)
    # Invalid/null metrics must keep their reason; rendering must never turn them into zero.
    derived["summary"]["rom_sd"].update(value=None, valid=False, reason="insufficient_repetitions")
    (folder / "derived.json.gz").write_bytes(gzip.compress(json.dumps(derived).encode(), mtime=0))
    assert "unavailable (insufficient_repetitions)" in module.render_summary(output / "replay")
    with pytest.raises(AssertionError):
        independent_auditor().audit_run(output, require_clean=False)
