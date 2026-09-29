"""Captured checks, then one immutable CP4 formal pair and separate audit."""

import json
import os
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent
FORMAL = ROOT / "experiments/M5_CP4_FORMAL2_20260928"
EXTERNAL = Path("<external-data>/kineimu_m1_usb_30min_20260925_01")
ENV = dict(
    os.environ,
    KINEIMU_M1_RAW_ROOT=str(EXTERNAL),
    PYTHONPATH=str(ROOT),
    OPENBLAS_NUM_THREADS="1",
    OMP_NUM_THREADS="1",
    MKL_NUM_THREADS="1",
)


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def command(name, argv):
    log = EVIDENCE / f"{name}.log"
    start = time.perf_counter()
    with log.open("xb") as stream:
        process = subprocess.Popen(argv, cwd=ROOT, env=ENV, stdout=stream, stderr=subprocess.STDOUT)
        code = process.wait()
    original = log.read_bytes()
    log.write_bytes(original.decode("utf-8-sig").replace("\r\n", "\n").encode())
    record = dict(
        command=argv,
        exit_code=code,
        pid=process.pid,
        elapsed_s=time.perf_counter() - start,
        path=log.name,
        sha256=sha256(log.read_bytes()).hexdigest(),
        original_sha256=sha256(original).hexdigest(),
    )
    print(name, "exit", code, "pid", process.pid, flush=True)
    return record


def checks():
    assert not (EVIDENCE / "checks.json").exists()
    commands = {
        "focused": [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/test_m5_formal_replay.py",
            "tests/integration/test_m5_stored_demo.py",
            "tests/integration/test_m5_recorded_node.py",
            "tests/integration/test_m5_recorded_dual.py",
            "tests/integration/test_m5_recorded_segments.py",
            "tests/integration/test_m2_replay_m1_bench.py",
            "--basetemp",
            ".tmp-m54-e2-focused",
            "--tb=short",
        ],
        "full": [sys.executable, "-m", "pytest", "--basetemp", ".tmp-m54-e2-full", "--tb=short"],
        "ruff": [sys.executable, "-m", "ruff", "check", "."],
        "mypy": [sys.executable, "-m", "mypy", "--strict", "kineimu_shoulder"],
        "docs": [sys.executable, "scripts/check_docs_consistency.py"],
        "whitespace": ["git", "diff", "--check"],
    }
    result = {}
    for name, argv in commands.items():
        result[name] = command(name, argv)
        if result[name]["exit_code"]:
            write(EVIDENCE / "checks-failed.json", result)
            raise SystemExit(1)
    write(EVIDENCE / "checks.json", result)


def launch():
    sys.path.insert(0, str(ROOT))
    from kineimu_shoulder.validation.formal_replay import input_snapshot

    assert not FORMAL.exists(), "formal pair root already consumed"
    assert not (EVIDENCE / "execution.json").exists()
    assert subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT) == b""
    source_lock = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    verified = json.loads((EVIDENCE / "checks.json").read_bytes())
    assert all(
        r["exit_code"] == 0 and sha256((EVIDENCE / r["path"]).read_bytes()).hexdigest() == r["sha256"]
        for r in verified.values()
    )
    before = input_snapshot(EXTERNAL)
    runs = []
    for i in (1, 2):
        operation = f"run{i}-operation.json"
        argv = [
            sys.executable,
            "-m",
            "kineimu_shoulder.validation.formal_replay",
            "--output",
            f"experiments/M5_CP4_FORMAL2_20260928/run{i}",
            "--operation",
            f"experiments/M5_CP4_STAGE_E2_20260928/{operation}",
            "--root",
            str(EXTERNAL),
        ]
        result = command(f"run{i}", argv)
        runs.append(
            dict(
                command=argv,
                exit_code=result["exit_code"],
                pid=result["pid"],
                elapsed_s=result["elapsed_s"],
                operation=operation,
                log=result["path"],
                log_sha256=result["sha256"],
            )
        )
        write(EVIDENCE / f"run{i}-execution.json", runs[-1])
        if result["exit_code"]:
            write(
                EVIDENCE / "execution-failed.json",
                dict(
                    source_lock=source_lock,
                    runs=runs,
                    input_before=before,
                    input_after=input_snapshot(EXTERNAL),
                    disposition="FAILED; preserve entire attempt",
                    partial_file_sha256={
                        p.relative_to(FORMAL).as_posix(): sha256(p.read_bytes()).hexdigest()
                        for p in FORMAL.rglob("*")
                        if p.is_file()
                    },
                ),
            )
            raise SystemExit(1)
    after = input_snapshot(EXTERNAL)
    write(EVIDENCE / "execution.json", dict(source_lock=source_lock, runs=runs, input_before=before, input_after=after))
    assert before == after
    manifest = json.loads((FORMAL / "run1/manifest.json").read_bytes())
    archive = EVIDENCE / f"source-lock-{source_lock[:8]}.zip"
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as zipped:
        for name, value in sorted(manifest["source_file_sha256"].items()):
            data = (ROOT / name).read_bytes()
            assert sha256(data).hexdigest() == value
            zipped.writestr(name, data)
    argv = [
        sys.executable,
        "experiments/M5_CP4_STAGE_E2_20260928/audit.py",
        "--one",
        str(FORMAL / "run1"),
        "--two",
        str(FORMAL / "run2"),
        "--launch",
        str(EVIDENCE / "execution.json"),
        "--archive",
        str(archive),
        "--output",
        str(EVIDENCE / "audit.json"),
    ]
    result = command("pair-audit", argv)
    write(EVIDENCE / "audit-execution.json", result)
    write(
        EVIDENCE / "verification.json",
        dict(
            source_lock=source_lock,
            checkpoint_disposition="PASS" if result["exit_code"] == 0 else "FAILED; preserve attempt",
            recorded_processing_version="m5-recorded-segments/1.0",
            execution_file="execution.json",
            input_before=before,
            input_after=input_snapshot(EXTERNAL),
            source_archive=dict(
                path=archive.name,
                sha256=sha256(archive.read_bytes()).hexdigest(),
                source_file_sha256=manifest["source_file_sha256"],
            ),
            output_file_sha256={
                p.relative_to(FORMAL).as_posix(): sha256(p.read_bytes()).hexdigest()
                for p in FORMAL.rglob("*")
                if p.is_file()
            },
            audit_exit_code=result["exit_code"],
            checks=verified,
        ),
    )
    assert subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT) == b""
    raise SystemExit(result["exit_code"])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("checks", "launch"):
        raise SystemExit("usage: launch.py checks|launch")
    checks() if sys.argv[1] == "checks" else launch()
