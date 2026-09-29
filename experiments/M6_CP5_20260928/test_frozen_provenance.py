"""Cross-ref comparisons may change recorded identity, never scientific content."""

from pathlib import Path

import verify_products as checker
from collect import CLONE


def test_summary_allows_only_exact_source_head_substitution():
    assert hasattr(checker, "summary_identity_equal"), "missing exact cross-ref HEAD comparison"
    old = (CLONE / "experiments/M6_CP2_20260928/run1/summary.md").read_bytes()
    new = (CLONE / "demo-output-01/summary.md").read_bytes()
    assert old != new
    assert checker.summary_identity_equal(old, new,
                                         "1732b1af274ebf05c241d515ebcc126e65def3cd", checker.HEAD)
    assert not checker.summary_identity_equal(old, new.replace(b"Speed remains rad/s", b"Speed remains deg/s"),
                                             "1732b1af274ebf05c241d515ebcc126e65def3cd", checker.HEAD)
    assert not checker.summary_identity_equal(old, new + b"\nextra claim\n",
                                             "1732b1af274ebf05c241d515ebcc126e65def3cd", checker.HEAD)


def test_python_alias_requires_identical_executable_and_all_other_arguments():
    assert hasattr(checker, "command_identity_equal"), "missing verified Python-alias comparison"
    old = ["<python-installations>/cpython-3.12.14-windows-x86_64-none/python.exe",
           "examples/m6_demo.py", "--output", "old-root"]
    new = ["<python-installations>/cpython-3.12-windows-x86_64-none/python.exe",
           "examples/m6_demo.py", "--output", "new-root"]
    assert Path(old[0]).samefile(new[0])
    assert checker.command_identity_equal(old, new)
    assert not checker.command_identity_equal(old, [*new, "--extra"])
    assert not checker.command_identity_equal(old, [new[0], "different.py", *new[2:]])
    assert not checker.command_identity_equal(old, [str(CLONE / "README.md"), *new[1:]])
