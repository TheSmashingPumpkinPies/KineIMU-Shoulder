"""Release runtime must use bundled inputs, with no developer checkout history."""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stored_replay_defaults_work_without_developer_experiments(tmp_path):
    checkout = tmp_path / "checkout"
    for name in ("kineimu_shoulder", "datasets"):
        shutil.copytree(ROOT / name, checkout / name)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    code = ("import sys; sys.path.insert(0, sys.argv[1]); "
            "from kineimu_shoulder.validation.stored_demo import CP1_ROOT, input_audit; "
            "assert len(input_audit(CP1_ROOT)) == 25")
    completed = subprocess.run([sys.executable, "-I", "-c", code, str(checkout)],
                               cwd=tmp_path, env=env, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_new_benchmark_source_archive_needs_no_historical_run(tmp_path):
    path = ROOT / "benchmarks/demo/run_benchmark.py"
    spec = importlib.util.spec_from_file_location("release_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sources = module.archive_source(tmp_path)
    assert sources and not any(name.startswith("experiments/") for name in sources)
    assert "kineimu_shoulder/validation/stored_demo.py" in sources
