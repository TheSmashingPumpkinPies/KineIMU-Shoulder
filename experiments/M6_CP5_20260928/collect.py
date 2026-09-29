"""Execute README demo acceptance from an untouched clone and a new project venv."""

import hashlib
import json
import subprocess

from run_check import EVIDENCE, PYTHON, ROOT, UV, WORK, environment, record

CLONE = WORK / "kineimu-shoulder"
HEAD = "e55d68b537987f4a2cc2ac6d2ad58e15e077ed15"


def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def write(name, value):
    with (EVIDENCE / name).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")


def run(name, command):
    assert record(name, command, CLONE) == 0, name


if __name__ == "__main__":
    env = environment()
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CLONE, text=True).strip()
    assert actual == HEAD
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=CLONE, text=True)
    assert not status and not (CLONE / ".venv").exists()
    assert not (CLONE / ".git/objects/info/alternates").exists()
    assert all(env.get(key) is None for key in ("KINEIMU_M1_RAW_ROOT", "PYTHONPATH", "VIRTUAL_ENV"))
    sample = CLONE / "datasets/samples/m6_synthetic"
    original = ROOT / "datasets/samples/m6_synthetic"
    assert hashes(sample) == hashes(original)
    assert not (sample / "F90/A.kimu").samefile(original / "F90/A.kimu")
    write("clone-preflight.json", dict(
        source_head=actual, clone=str(CLONE), tracked_and_untracked_status=status,
        venv_initially_absent=True, git_alternates_absent=True, sample_samefile=False,
        clone_source="Local committed Git repository; --no-hardlinks; no workspace files copied",
        uv_cache_initially_absent=not (WORK / "uv-cache").exists(),
        python=str(PYTHON), environment={k: env.get(k) for k in
            ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "KINEIMU_M1_RAW_ROOT", "UV_CACHE_DIR", "UV_PYTHON")},
        hardware="No live capture or device connection invoked; default is bundled synthetic replay",
        sample_files_before=hashes(sample), uv_lock_sha256=hashlib.sha256((CLONE / "uv.lock").read_bytes()).hexdigest(),
    ))
    run("sync-analysis-01", [UV, "sync", "--extra", "analysis", "--frozen"])
    runtime = (
        "import importlib.metadata as m,json,os,sys; from pathlib import Path; import kineimu_shoulder; "
        "assert sys.version_info[:3]==(3,12,14); "
        "assert Path(sys.prefix).resolve()==(Path.cwd()/'.venv').resolve(); "
        "assert all(os.getenv(k) is None for k in ('PYTHONPATH','KINEIMU_M1_RAW_ROOT')); "
        "assert Path(kineimu_shoulder.__file__).resolve().is_relative_to(Path.cwd()); "
        "print(json.dumps(dict(executable=sys.executable,prefix=sys.prefix,base_prefix=sys.base_prefix,"
        "package_path=kineimu_shoulder.__file__,pyvenv_cfg=Path(sys.prefix,'pyvenv.cfg').read_text(),"
        "packages={d.metadata['Name']:d.version for d in m.distributions()}),indent=2))"
    )
    run("runtime-analysis-01", [UV, "run", "--frozen", "python", "-c", runtime])
    run("help-01", [UV, "run", "--frozen", "python", "examples/m6_demo.py", "--help"])
    for number in (1, 2):
        run(f"demo-{number:02}", [UV, "run", "--frozen", "python", "examples/m6_demo.py",
                                "--output", f"demo-output-{number:02}"])
    run("pair-audit-01", [UV, "run", "--frozen", "python", "experiments/M6_CP2_20260928/audit.py",
                          "--run1", "demo-output-01", "--run2", "demo-output-02",
                          "--output", str(EVIDENCE / "pair-audit.json")])
    assert hashes(sample) == hashes(original)
    write("sample-after-demos.json", hashes(sample))
    run("sync-all-extras-01", [UV, "sync", "--all-extras", "--frozen"])
    print("CP5 README pair audited; ready for complete checks", flush=True)
