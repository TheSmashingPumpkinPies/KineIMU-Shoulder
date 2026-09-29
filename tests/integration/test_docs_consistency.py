"""Repository-level contract for active documentation invariants."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_active_documents_follow_the_accepted_v1_boundary() -> None:
    repository = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "scripts/check_docs_consistency.py"],
        cwd=repository,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
