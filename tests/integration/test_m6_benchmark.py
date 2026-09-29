"""M6 CP3: analytical statistics, failure retention and evidence tamper controls."""

import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def runner():
    path = ROOT / "benchmarks/demo/run_benchmark.py"
    assert path.exists(), "CP3 benchmark runner is missing"
    spec = importlib.util.spec_from_file_location("m6_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rows():
    return [dict(slot=slot, disposition="PASS", exit_code=0, correctness=True,
                 wall_ns=seconds * 1_000_000_000, wall_s=float(seconds),
                 node_samples_per_s=17208 / seconds)
            for slot, seconds in zip(("warmup", "timed01", "timed02", "timed03", "timed04", "timed05"),
                                     (99, 5, 1, 4, 2, 3), strict=True)]


def test_statistics_exclude_warmup_and_use_each_reciprocal():
    summary = runner().summarize(rows())
    # Hand arithmetic: sorted seconds 1,2,3,4,5; N/3=5736, N/5=3441.6.
    assert summary == dict(cp3_passed=True, timed_count=5,
                           wall_s=dict(median=3.0, min=1.0, max=5.0),
                           node_samples_per_s=dict(median=5736.0, min=3441.6, max=17208.0))


@pytest.mark.parametrize("change", ["failed", "warmup", "missing", "duplicate", "ns", "seconds", "rate"])
def test_incomplete_or_inconsistent_attempts_cannot_publish_statistics(change):
    attempts = rows()
    if change == "failed":
        attempts[3].update(disposition="FAIL", correctness=False, exit_code=1)
    elif change == "warmup":
        attempts[0]["correctness"] = False
    elif change == "missing":
        attempts.pop()
    elif change == "duplicate":
        attempts[-1]["slot"] = "timed01"
    elif change == "ns":
        attempts[2]["wall_ns"] = 0
    elif change == "seconds":
        attempts[2]["wall_s"] = 20.0
    else:
        attempts[2]["node_samples_per_s"] = 20.0
    assert runner().summarize(attempts)["cp3_passed"] is False


@pytest.mark.parametrize("name", ["benchmarks/new", "experiments/new", "datasets/new", "demo-output-benchmark"])
def test_batch_output_cannot_overlap_repository(name):
    with pytest.raises(ValueError):
        runner().protect(ROOT / name)
    assert not (ROOT / name).exists()


def test_existing_batch_is_preserved(tmp_path):
    (tmp_path / "keep").write_bytes(b"immutable")
    with pytest.raises(FileExistsError):
        runner().protect(tmp_path)
    assert (tmp_path / "keep").read_bytes() == b"immutable"


def test_child_failure_retains_command_pid_threads_and_both_streams(tmp_path):
    module = runner()
    env = module.child_environment()
    command = [sys.executable, "-c",
               "import os,sys; print(os.getpid()); "
               "print(','.join(os.environ[k] for k in "
               "['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'])); "
               "print('failure retained',file=sys.stderr); sys.exit(7)"]
    result = module.measure(command, tmp_path, env, tmp_path)
    assert result["exit_code"] == 7 and result["command"] == command
    assert result["wall_ns"] > 0 and result["wall_s"] == result["wall_ns"] / 1e9
    stdout = (tmp_path / "stdout.log").read_text().splitlines()
    assert int(stdout[0]) > 0 and int(stdout[0]) != os.getpid()
    assert result["launch_pid"] > 0 and result["launch_pid"] != os.getpid()
    assert stdout[1] == "1,1,1"
    assert (tmp_path / "stderr.log").read_text().strip() == "failure retained"
    assert env.get("KINEIMU_M1_RAW_ROOT") is None
    assert json.loads((tmp_path / "measurement.json").read_bytes()) == result


def test_worker_identity_binds_actual_python_to_launch_and_preserves_failure(tmp_path):
    module = runner()
    worker = ROOT / "benchmarks/demo/worker.py"
    assert worker.exists(), "CP3 worker identity wrapper is missing"
    output = tmp_path / "existing"
    output.mkdir()
    command = [sys.executable, str(worker), "--output", str(output)]
    measured = module.measure(command, ROOT, module.child_environment(), tmp_path)
    identity = json.loads((tmp_path / "worker.json").read_bytes())
    assert measured["exit_code"] == 1  # Demo refuses the existing output, untouched.
    assert identity["pid"] == measured["launch_pid"] or identity["ppid"] == measured["launch_pid"]
    assert identity["threads"] == dict(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    assert identity["external_m1_root"] is None


@pytest.mark.parametrize("change", ["changed", "added", "missing"])
def test_inventory_verification_detects_byte_and_membership_changes(change, tmp_path):
    module = runner()
    product = tmp_path / "product"
    product.write_bytes(b"frozen bytes")
    module.freeze_inventory(tmp_path)
    assert module.verify_inventory(tmp_path)
    if change == "changed":
        product.write_bytes(b"tampered bytes")
    elif change == "added":
        (tmp_path / "undeclared").write_bytes(b"extra")
    else:
        product.unlink()
    with pytest.raises(ValueError):
        module.verify_inventory(tmp_path)


def test_summary_does_not_mutate_retained_attempts():
    attempts = rows()
    original = copy.deepcopy(attempts)
    runner().summarize(attempts)
    assert attempts == original


@pytest.mark.parametrize("text,allowed", [("uv 0.12.5 (210d1f678 2026-08-14 x86_64-pc-windows-msvc)", True),
                                          ("uv 0.12.4 (older build)", False), ("unknown", False)])
def test_uv_version_gate_accepts_real_build_metadata_and_rejects_wrong_version(text, allowed):
    assert runner().uv_version_allowed(text) is allowed


def test_actual_worker_command_varies_only_in_demo_output_for_pair_whitelist(tmp_path):
    module = runner()
    worker = ROOT / "benchmarks/demo/worker.py"
    commands = []
    for name in ("first", "second"):
        logs = tmp_path / name
        output = logs / "existing"
        output.mkdir(parents=True)
        measured = module.measure([sys.executable, str(worker), "--output", str(output)],
                                  ROOT, module.child_environment(), logs)
        assert measured["exit_code"] == 1  # Existing Demo output refusal, not argparse failure.
        identity = json.loads((logs / "worker.json").read_bytes())
        command = identity["process_argv"]
        assert command[1:] == [str(worker), "--output", str(output)]
        command[command.index("--output") + 1] = "<output>"
        commands.append(command)
    # CP2's frozen whitelist permits only the --output value to change in argv.
    assert commands[0] == commands[1]
