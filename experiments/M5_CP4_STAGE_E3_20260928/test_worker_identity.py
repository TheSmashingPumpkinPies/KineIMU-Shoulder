"""Actual Windows venv redirector identity must not replace worker identity."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def api():
    path = Path(__file__).with_name("audit.py")
    assert path.exists(), "independent worker-identity audit correction missing"
    spec = importlib.util.spec_from_file_location("e3_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_venv_redirector_binds_launcher_to_actual_child():
    command = [
        str(ROOT / ".venv/Scripts/python.exe"),
        "-c",
        "import json,os; print(json.dumps(dict(pid=os.getpid(),parent_pid=os.getppid())))",
    ]
    p = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    stdout, _ = p.communicate()
    assert p.returncode == 0
    actual = json.loads(stdout)
    # Directly observed subprocess hierarchy, independent of CP4 output.
    assert actual["pid"] != p.pid and actual["parent_pid"] == p.pid
    identities = api().worker_identities([dict(pid=p.pid, exit_code=0)], [actual], required=1)
    assert identities == [dict(launcher_pid=p.pid, worker_pid=actual["pid"])]


def test_two_distinct_workers_are_required_even_with_distinct_launchers():
    records = [dict(pid=31524, exit_code=0), dict(pid=40000, exit_code=0)]
    # First actual worker26936 is from retained E2 operation evidence. The
    # second worker literal is a deliberate duplicate, never a real CP4 run.
    with pytest.raises(ValueError, match="independent"):
        api().worker_identities(records, [dict(pid=26936), dict(pid=26936)])


def test_actual_worker_ids_are_kept_separate_from_launchers():
    identities = api().worker_identities(
        [dict(pid=31524, exit_code=0), dict(pid=40000, exit_code=0)], [dict(pid=26936), dict(pid=22476)]
    )
    assert identities == [dict(launcher_pid=31524, worker_pid=26936), dict(launcher_pid=40000, worker_pid=22476)]


def test_nonzero_actual_execution_cannot_be_accepted_as_identity_only():
    with pytest.raises(ValueError):
        api().worker_identities([dict(pid=31524, exit_code=1)], [dict(pid=26936)], required=1)
