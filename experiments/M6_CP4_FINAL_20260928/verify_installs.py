"""Install a preview wheel and sdist independently, recording all actual commands."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent
UV = Path("uv")


def main() -> int:
    work = Path(sys.argv[1]).resolve()
    artifacts = Path(sys.argv[2]).resolve()
    label = sys.argv[3]
    if Path(label).name != label:
        raise SystemExit("use a simple new attempt label")
    destination = EVIDENCE / f"installation-audit-{label}.json"
    if work.exists() or destination.exists():
        raise SystemExit("preserve existing roots and records; use a new absent root")
    work.mkdir(parents=True)
    records = []
    passed = False

    def run(name: str, command: list[str]) -> None:
        log = EVIDENCE / f"{label}-{name}.log"
        started = datetime.now(UTC).isoformat()
        with log.open("xb") as stream:
            result = subprocess.run(command, cwd=work, stdout=stream, stderr=subprocess.STDOUT, check=False)
        records.append({"name": name, "command": command, "cwd": str(work),
                        "started_utc": started, "ended_utc": datetime.now(UTC).isoformat(),
                        "exit_code": result.returncode, "log": log.name,
                        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()})
        print(f"{name}: exit {result.returncode}", flush=True)
        if result.returncode:
            print(log.read_text(encoding="utf-8", errors="replace")[-5000:], flush=True)
            raise RuntimeError(f"{name} failed; complete original log retained")

    try:
        for kind, filename in (("wheel", "kineimu_shoulder-0.1.0-py3-none-any.whl"),
                               ("sdist", "kineimu_shoulder-0.1.0.tar.gz")):
            env = work / f"{kind}-env"
            python = str(env / "Scripts/python.exe")
            run(f"{kind}-venv", [str(UV), "venv", "--python", "3.12.14", str(env)])
            run(f"{kind}-dependencies", [str(UV), "pip", "install", "--python", python, "--require-hashes",
                                         "--only-binary", ":all:", "-r", str(EVIDENCE / "analysis-requirements.txt")])
            run(f"{kind}-install", [str(UV), "pip", "install", "--python", python, "--no-deps",
                                    str(artifacts / filename)])
            run(f"{kind}-api", [python, "-I", str(EVIDENCE / "installed_api_check.py"), str(ROOT)])
        passed = True
    finally:
        destination.write_text(json.dumps({
            "status": "PASS" if passed else "FAIL", "records": records, "root": str(work),
            "KINEIMU_M1_RAW_ROOT": os.environ.get("KINEIMU_M1_RAW_ROOT"),
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
            "requirements_sha256": hashlib.sha256((EVIDENCE / "analysis-requirements.txt").read_bytes()).hexdigest(),
            "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in artifacts.iterdir() if p.suffix in (".whl", ".gz")},
        }, indent=2) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
