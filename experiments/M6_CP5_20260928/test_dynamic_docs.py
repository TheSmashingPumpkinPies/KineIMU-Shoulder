"""A resumable current task must describe today's stage, not historical M1 holds."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def checker(monkeypatch, task):
    spec = importlib.util.spec_from_file_location("docs_checker", ROOT / "scripts/check_docs_consistency.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = Path.read_text

    def read(path, *args, **kwargs):
        if path == ROOT / "CURRENT_TASK.md":
            return task
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    return module


def test_release_handoff_does_not_require_superseded_hardware_hold(monkeypatch):
    task = "# KineIMU Shoulder — M6.5 / CP5\nHEAD e55d68b5\nExact next action: verify candidate.\n"
    assert checker(monkeypatch, task).main() == 0


def test_current_task_requires_a_resumable_next_action(monkeypatch, capsys):
    assert checker(monkeypatch, "# KineIMU Shoulder\nHEAD e55d68b5\n").main() == 1
    assert "CURRENT_TASK.md: missing Exact next action" in capsys.readouterr().out
