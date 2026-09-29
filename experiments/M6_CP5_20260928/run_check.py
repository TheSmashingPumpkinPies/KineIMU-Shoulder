"""Record CP5 commands in a sanitized environment without rewriting earlier attempts."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent
WORK = Path(os.environ["TEMP"]) / "kineimu-m6-cp5-20260928-01"
PYTHON = Path("<python-installations>/cpython-3.12.14-windows-x86_64-none/python.exe")
UV = "uv"
CLEARED = (
    "KINEIMU_M1_RAW_ROOT", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV",
    "UV_PROJECT_ENVIRONMENT", "UV_WORKING_DIR", "UV_PROJECT", "CONDA_PREFIX",
)


def environment():
    env = os.environ.copy()
    for name in CLEARED:
        env.pop(name, None)
    env.update(UV_CACHE_DIR=str(WORK / "uv-cache"), UV_PYTHON=str(PYTHON),
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    return env


def record(name, command, cwd):
    log, target = EVIDENCE / f"{name}.log", EVIDENCE / f"{name}.json"
    if log.exists() or target.exists():
        raise FileExistsError(name)
    env = environment()
    start = datetime.now(UTC).isoformat()
    with log.open("xb") as stream:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    data = dict(command=command, cwd=str(Path(cwd).resolve()), started_utc=start,
                ended_utc=datetime.now(UTC).isoformat(), exit_code=result.returncode,
                log=log.name, log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
                acceptance_source_head="e55d68b537987f4a2cc2ac6d2ad58e15e077ed15",
                environment={key: env.get(key) for key in (*CLEARED, "UV_PYTHON", "UV_CACHE_DIR",
                             "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")})
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(data, indent=2) + "\n")
    print(log.read_text(encoding="utf-8", errors="replace")[-2500:], flush=True)
    print(f"Recorded {name}: exit {result.returncode}", flush=True)
    return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or Path(args.name).name != args.name:
        parser.error("simple unused record name and command required")
    raise SystemExit(record(args.name, command, args.cwd))
