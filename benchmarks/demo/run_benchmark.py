"""Frozen M6 CP3 end-to-end benchmark and read-only evidence recomputation.

No production timing hooks. Parent perf_counter_ns encloses only the Python child.
Correctness uses the existing independent CP2/M5 oracle outside that interval.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import distributions, version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "datasets/samples/m6_synthetic"
SLOTS = ("warmup", "timed01", "timed02", "timed03", "timed04", "timed05")
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
PROTOCOL = "m6-demo-benchmark/1.1"
NODE_SAMPLES = 17208


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def write(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def freeze_inventory(root: Path) -> None:
    write(root / "SHA256SUMS.json", hashes(root))


def verify_inventory(root: Path) -> bool:
    actual = hashes(root)
    actual.pop("SHA256SUMS.json", None)
    if actual != read(root / "SHA256SUMS.json"):
        raise ValueError("batch bytes or membership differ from frozen inventory")
    return True


def protect(output: Path) -> None:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"batch already exists: {output}")
    if output.is_relative_to(ROOT) or ROOT.is_relative_to(output):
        raise ValueError("batch must be outside repository; nested child roots require an external batch")
    if any(part.lower() == "raw" for part in output.parts):
        raise ValueError("protected raw component")
    # Reuse the existing source/input/evidence/junction-aware Demo guard.
    sys.path.insert(0, str(ROOT))
    from kineimu_shoulder.validation.demo import _protect
    _protect(output, SAMPLE)


def child_environment() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("KINEIMU_M1_RAW_ROOT", None)
    env.update(dict.fromkeys(THREADS, "1"))
    return env


def uv_version_allowed(output: str) -> bool:
    # uv includes a build commit/date/target after its semantic version.
    return output.split()[:2] == ["uv", "0.12.5"]


def measure(command: list[str], cwd: Path, env: dict[str, str], logs: Path) -> dict[str, Any]:
    """Open log handles before boundary; preserve ns, PID, return code and both streams."""
    started = datetime.now(UTC).isoformat()
    with (logs / "stdout.log").open("xb") as stdout, (logs / "stderr.log").open("xb") as stderr:
        begin = time.perf_counter_ns()
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
        exit_code = process.wait()
        end = time.perf_counter_ns()
    ns = end - begin
    result = dict(command=command, cwd=str(cwd), launch_pid=process.pid, exit_code=exit_code,
                  started_utc=started, ended_utc=datetime.now(UTC).isoformat(),
                  counter_start_ns=begin, counter_end_ns=end, wall_ns=ns, wall_s=ns / 1e9,
                  node_samples_per_s=NODE_SAMPLES / (ns / 1e9),
                  environment={key: env.get(key) for key in (*THREADS, "KINEIMU_M1_RAW_ROOT")},
                  log_sha256={name: sha256((logs / name).read_bytes()).hexdigest()
                              for name in ("stdout.log", "stderr.log")})
    write(logs / "measurement.json", result)
    return result


def summarize(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    failed = dict(cp3_passed=False, timed_count=sum(r.get("slot") in SLOTS[1:] for r in attempts),
                  wall_s=None, node_samples_per_s=None)
    if [r.get("slot") for r in attempts] != list(SLOTS):
        return failed
    for row in attempts:
        ns = row.get("wall_ns")
        if (row.get("disposition") != "PASS" or row.get("exit_code") != 0 or
                row.get("correctness") is not True or type(ns) is not int or ns <= 0):
            return failed
        if row.get("wall_s") != ns / 1e9 or row.get("node_samples_per_s") != NODE_SAMPLES / (ns / 1e9):
            return failed
    timed = attempts[1:]
    result: dict[str, Any] = dict(cp3_passed=True, timed_count=5)
    for name in ("wall_s", "node_samples_per_s"):
        values = [r[name] for r in timed]
        result[name] = dict(median=statistics.median(values), min=min(values), max=max(values))
    return result


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def probe(command: list[str]) -> dict[str, Any]:
    try:
        p = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        return dict(command=command, exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return dict(command=command, unavailable=str(exc))


def environment(output: Path, env: dict[str, str]) -> dict[str, Any]:
    import contextlib
    import io

    import numpy as np

    config = io.StringIO()
    with contextlib.redirect_stdout(config):
        np.show_config()
    ps = shutil.which("powershell.exe")
    observed: dict[str, Any] = {}
    if ps:
        commands = {
            "machine": "$cpu=Get-CimInstance Win32_Processor; $os=Get-CimInstance Win32_OperatingSystem; "
                       "$cs=Get-CimInstance Win32_ComputerSystem; "
                       "[pscustomobject]@{CPU=@($cpu|Select-Object Name,NumberOfCores,NumberOfLogicalProcessors); "
                       "OS=$os.Caption;Build=$os.BuildNumber;TotalMemoryBytes=$cs.TotalPhysicalMemory;"
                       "FreeMemoryKiB=$os.FreePhysicalMemory}|ConvertTo-Json -Depth 4",
            "background": "Get-Process|Sort-Object CPU -Descending|Select-Object -First 15 "
                          "ProcessName,Id,CPU,WorkingSet64|ConvertTo-Json",
            "storage": "Get-CimInstance Win32_DiskDrive|Select-Object "
                       "Model,MediaType,InterfaceType,Size|ConvertTo-Json",
        }
        observed = {key: probe([ps, "-NoProfile", "-NonInteractive", "-Command", command])
                    for key, command in commands.items()}
    power = shutil.which("powercfg.exe")
    uv = shutil.which("uv")
    return dict(platform=platform.platform(), os=platform.system(), architecture=platform.machine(),
                python=sys.version, python_executable=sys.executable,
                python_executable_sha256=sha256(Path(sys.executable).read_bytes()).hexdigest(),
                logical_cpu_count=os.cpu_count(), observed=observed,
                power=probe([power, "/getactivescheme"]) if power else "unavailable",
                uv=probe([uv, "--version"]) if uv else "unavailable",
                dependencies={d.metadata["Name"]: d.version for d in distributions()},
                numpy_config=config.getvalue(), threadpool_runtime="unavailable: no threadpoolctl dependency",
                environment={key: env.get(key) for key in
                             (*THREADS, "KINEIMU_M1_RAW_ROOT", "PYTHONHASHSEED", "UV_CACHE_DIR")},
                cache_condition="warm OS cache; no flush; fresh process/AHRS each slot",
                working_directory=str(ROOT), storage_root=str(output),
                disk_usage_bytes=shutil.disk_usage(output.parent)._asdict(),
                thermal_state="unavailable", cpu_frequency_during_child="unavailable",
                background_control="ordinary desktop; no exclusive CPU isolation; snapshot only",
                captured_utc=datetime.now(UTC).isoformat())


def auditor() -> Any:
    spec = importlib.util.spec_from_file_location("m6_cp2_audit", ROOT / "experiments/M6_CP2_20260928/audit.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs() -> dict[str, Any]:
    return dict(sample=hashes(SAMPLE), original=hashes(ROOT / "experiments/M5_CP1_20260926/run1"))


def archive_source(output: Path) -> dict[str, str]:
    prior = read(ROOT / "experiments/M6_CP2_20260928/runtime-source-sha256.json")
    names = set(prior) | {"benchmarks/demo/run_benchmark.py", "benchmarks/demo/worker.py",
                          "benchmarks/demo/PROTOCOL.md",
                          "uv.lock", "pyproject.toml", "docs/M6_DEMO_CONTRACT.md",
                          "experiments/M5_CP3_20260926/audit.py", "tests/integration/test_m6_benchmark.py"}
    sources = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(names)}
    with zipfile.ZipFile(output / "runtime-source.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            archive.writestr(name, (ROOT / name).read_bytes())
    write(output / "runtime-source-sha256.json", sources)
    return sources


def collect(output: Path) -> dict[str, Any]:
    output = output.resolve()
    protect(output)
    head = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("formal benchmark requires clean tracked source")
    if sys.version_info[:3] != (3, 12, 14):
        raise ValueError("protocol requires Python 3.12.14")
    for package, expected in {"numpy": "2.5.2", "pandas": "3.0.5", "scipy": "1.18.1",
                              "imufusion": "1.3.3", "imucal": "2.6.0"}.items():
        if version(package) != expected:
            raise ValueError(f"locked dependency mismatch: {package}")
    uv = shutil.which("uv")
    if uv is None or not uv_version_allowed(subprocess.check_output([uv, "--version"], text=True)):
        raise ValueError("protocol requires uv 0.12.5")
    env = child_environment()
    os.environ.update(dict.fromkeys(THREADS, "1"))
    output.mkdir(parents=True)
    write(output / "environment-before.json", environment(output, env))
    source = archive_source(output)
    before = inputs()
    write(output / "inputs-before.json", before)
    write(output / "lock.json", dict(protocol=PROTOCOL, source_head=head, tracked_dirty=False,
                                     source_sha256=source, command=sys.argv, cwd=str(ROOT),
                                     scheduled_slots=list(SLOTS), node_samples=NODE_SAMPLES, packets=4304,
                                     input_files=25, input_bytes=4539058, compute_s="NOT MEASURED"))
    audit = auditor()
    preflight_ok = False
    try:
        preflight = audit.audit_pair(ROOT / "experiments/M6_CP2_20260928/run1",
                                     ROOT / "experiments/M6_CP2_20260928/run2")
        write(output / "preflight-audit.json", preflight)
        preflight_ok = True
    except Exception as exc:
        write(output / "preflight-audit.json", dict(passed=False, error=f"{type(exc).__name__}: {exc}"))
    attempts: list[dict[str, Any]] = []
    warmup_ok = preflight_ok
    for slot in SLOTS:
        if not warmup_ok:
            attempts.append(dict(slot=slot, disposition="NOT RUN", correctness=False,
                                 reason="preflight or warmup failed; frozen protocol stops timed slots"))
            continue
        logs = output / slot
        logs.mkdir()
        child = logs / "demo"
        command = [sys.executable, str(ROOT / "benchmarks/demo/worker.py"), "--output", str(child)]
        row: dict[str, Any] = dict(slot=slot, disposition="FAIL", correctness=False)
        try:
            row.update(measure(command, ROOT, env, logs))
            started = datetime.now(UTC).isoformat()
            if row["exit_code"] != 0:
                raise ValueError(f"child exit {row['exit_code']}")
            worker = read(child / "run.json")
            identity = read(logs / "worker.json")
            assert identity["pid"] == row["launch_pid"] or identity["ppid"] == row["launch_pid"]
            assert identity["process_argv"][1:] == command[1:]
            assert identity["threads"] == dict.fromkeys(THREADS, "1") and identity["external_m1_root"] is None
            row["worker_pid"] = identity["pid"]
            if worker["pid"] != row["worker_pid"] or worker["source"]["head"] != head:
                raise ValueError("worker PID/source differs from launch lock")
            report = audit.audit_run(child) if slot == "warmup" else audit.audit_pair(output / "warmup/demo", child)
            write(logs / "audit.json", dict(operation="audit_run" if slot == "warmup" else "audit_pair",
                                            arguments=[str(child)] if slot == "warmup" else
                                            [str(output / "warmup/demo"), str(child)], exit_code=0,
                                            started_utc=started, ended_utc=datetime.now(UTC).isoformat(),
                                            passed=True, result=report))
            row.update(disposition="PASS", correctness=True)
        except Exception as exc:
            row["reason"] = f"{type(exc).__name__}: {exc}"
            if not (logs / "audit.json").exists():
                write(logs / "audit.json", dict(passed=False, exit_code=1, error=row["reason"]))
        row["retained_sha256"] = hashes(logs)
        attempts.append(row)
        write(logs / "attempt.json", row)
        if slot == "warmup":
            warmup_ok = row["correctness"]
        print(json.dumps(dict(slot=slot, disposition=row["disposition"], wall_s=row.get("wall_s"))), flush=True)
    after = inputs()
    write(output / "inputs-after.json", after)
    write(output / "attempts.json", attempts)
    write(output / "environment-after.json", environment(output, env))
    summary = summarize(attempts)
    stable = before == after and git("rev-parse", "HEAD") == head and not git(
        "status", "--porcelain", "--untracked-files=no") and source == {
            name: sha256((ROOT / name).read_bytes()).hexdigest() for name in source}
    summary.update(inputs_and_source_unchanged=stable, protocol=PROTOCOL, source_head=head)
    summary["cp3_passed"] = summary["cp3_passed"] and stable
    write(output / "summary.json", summary)
    freeze_inventory(output)
    return summary


def recompute(batch: Path) -> dict[str, Any]:
    """Verify all retained bytes, repeat independent numerical audits, derive statistics from raw ns."""
    verify_inventory(batch)
    lock = read(batch / "lock.json")
    assert lock["protocol"] == PROTOCOL and lock["scheduled_slots"] == list(SLOTS)
    assert lock["node_samples"] == NODE_SAMPLES and lock["packets"] == 4304
    source = read(batch / "runtime-source-sha256.json")
    assert source == lock["source_sha256"]
    with zipfile.ZipFile(batch / "runtime-source.zip") as archive:
        assert {name: sha256(archive.read(name)).hexdigest() for name in archive.namelist()} == source
    assert all(sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in source.items())
    assert read(batch / "inputs-before.json") == read(batch / "inputs-after.json") == inputs()
    audit = auditor()
    attempts = read(batch / "attempts.json")
    results = []
    for row in attempts:
        if row["disposition"] == "NOT RUN":
            continue
        logs = batch / row["slot"]
        assert read(logs / "attempt.json") == row
        retained = hashes(logs)
        retained.pop("attempt.json")
        assert retained == row["retained_sha256"]
        m = read(logs / "measurement.json")
        assert all(row[k] == v for k, v in m.items())
        assert m["wall_ns"] == m["counter_end_ns"] - m["counter_start_ns"] > 0
        assert all(sha256((logs / name).read_bytes()).hexdigest() == digest
                   for name, digest in m["log_sha256"].items())
        assert m["environment"] == dict(**dict.fromkeys(THREADS, "1"), KINEIMU_M1_RAW_ROOT=None)
        if row["correctness"]:
            child = logs / "demo"
            worker = read(child / "run.json")
            identity = read(logs / "worker.json")
            assert identity["pid"] == m["launch_pid"] or identity["ppid"] == m["launch_pid"]
            assert identity["process_argv"][1:] == m["command"][1:]
            assert identity["threads"] == dict.fromkeys(THREADS, "1") and identity["external_m1_root"] is None
            assert worker["pid"] == row["worker_pid"] == identity["pid"]
            assert worker["source"]["head"] == lock["source_head"]
            result = (audit.audit_run(child) if row["slot"] == "warmup"
                      else audit.audit_pair(batch / "warmup/demo", child))
            assert result == read(logs / "audit.json")["result"]
            results.append(dict(slot=row["slot"], independently_correct=True))
    summary = summarize(attempts)
    summary.update(inputs_and_source_unchanged=True, protocol=PROTOCOL, source_head=lock["source_head"])
    assert summary == read(batch / "summary.json")
    return dict(summary=summary, inventory_verified=True, independent_audits=results,
                batch_inventory_sha256=sha256((batch / "SHA256SUMS.json").read_bytes()).hexdigest())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--recompute", type=Path,
                        help="read-only audit and statistics; output must be new outside batch")
    args = parser.parse_args()
    try:
        if args.recompute:
            if args.output.resolve().is_relative_to(args.recompute.resolve()):
                raise ValueError("recompute output must be outside frozen batch")
            result = recompute(args.recompute.resolve())
            write(args.output, result)
            print(json.dumps(result["summary"], sort_keys=True))
            return 0 if result["summary"]["cp3_passed"] else 1
        result = collect(args.output)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["cp3_passed"] else 1
    except Exception as exc:
        print(f"CP3 rejected: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
