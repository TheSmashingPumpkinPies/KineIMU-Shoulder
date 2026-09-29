"""Record an actual preview-verification command, exit and exact combined log."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", type=Path, default=ROOT)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or Path(args.name).name != args.name:
        parser.error("use a simple new record name and a command")
    log = EVIDENCE / f"{args.name}.log"
    record = EVIDENCE / f"{args.name}.json"
    if log.exists() or record.exists():
        parser.error("record already exists; use a new attempt name")
    started = datetime.now(UTC).isoformat()
    with log.open("xb") as stream:
        result = subprocess.run(command, cwd=args.cwd, stdout=stream, stderr=subprocess.STDOUT, check=False)
    data = {
        "command": command, "cwd": str(args.cwd.resolve()),
        "started_utc": started, "ended_utc": datetime.now(UTC).isoformat(),
        "exit_code": result.returncode, "log": log.name,
        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "environment": {name: os.environ.get(name) for name in (
            "KINEIMU_M1_RAW_ROOT", "UV_CACHE_DIR", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"
        )},
    }
    record.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(log.read_text(encoding="utf-8", errors="replace")[-7000:])
    print(f"Recorded {args.name}: exit {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
