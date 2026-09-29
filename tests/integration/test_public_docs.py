"""Public docs gates must work without private archives and reject real corruption."""

import importlib.util
import json
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def public_tree(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    required = [
        "README.md", "PROJECT_SCOPE.md", "HARDWARE_PROFILE.md", "MOUNTING_PROTOCOL.md",
        "VALIDATION.md", "docs/METRICS.md",
        "ARCHITECTURE.md", "pyproject.toml", "uv.lock",
        "docs/adr/ADR-006-select-xiao-nrf52840-sense.md",
        "docs/adr/ADR-007-select-upstream-zephyr.md",
        "docs/adr/ADR-008-hardware-tested-software-complete-v1.md",
    ]
    for name in required:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        # Preserve contract text but remove unrelated navigation in this isolated fixture.
        import re
        text = (ROOT / name).read_text(encoding="utf-8")
        text = re.sub(r"\[([^\]\n]+)\]\([^)]+\)", r"\1", text)
        target.write_text(text, encoding="utf-8")
    payload = tmp_path / "datasets/bench-fixture.kimu"
    payload.parent.mkdir()
    payload.write_bytes(b"immutable synthetic fixture for an integrity control")
    manifest = {
        "schema": "kineimu-public-export/1.0", "source_head": "1" * 40,
        "files": [{"path": "datasets/bench-fixture.kimu", "immutable": True,
                   "export_sha256": sha256(payload.read_bytes()).hexdigest(),
                   "bytes": payload.stat().st_size}],
    }
    (tmp_path / "PUBLIC_EXPORT.json").write_text(json.dumps(manifest), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("public_docs", ROOT / "scripts/check_docs_consistency.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    return tmp_path, module


def test_public_clone_needs_no_private_reference_or_handoff(public_tree):
    root, checker = public_tree
    assert not (root / "docs/reference").exists()
    assert not (root / "CURRENT_TASK.md").exists()
    try:
        assert checker.main() == 0
    except FileNotFoundError as exc:
        pytest.fail(f"Public checker still requires private source files: {exc}")


def test_immutable_input_tampering_is_rejected(public_tree, capsys):
    root, checker = public_tree
    (root / "datasets/bench-fixture.kimu").write_bytes(b"corrupted fixture")
    assert checker.main() == 1
    assert "changed immutable export" in capsys.readouterr().out


def test_missing_immutable_member_is_rejected(public_tree, capsys):
    root, checker = public_tree
    (root / "datasets/bench-fixture.kimu").unlink()
    assert checker.main() == 1
    assert "missing immutable export" in capsys.readouterr().out


def test_public_navigation_still_rejects_broken_links(public_tree, capsys):
    root, checker = public_tree
    with (root / "README.md").open("a", encoding="utf-8") as stream:
        stream.write("\n[Missing evidence](absent-evidence.json)\n")
    assert checker.main() == 1
    assert "broken link absent-evidence.json" in capsys.readouterr().out


def test_export_manifest_cannot_escape_checkout(public_tree, capsys):
    root, checker = public_tree
    path = root / "PUBLIC_EXPORT.json"
    manifest = json.loads(path.read_text())
    manifest["files"][0]["path"] = "../outside.kimu"
    path.write_text(json.dumps(manifest))
    assert checker.main() == 1
    assert "unsafe export path" in capsys.readouterr().out


def test_private_handoff_cannot_enter_public_tree(public_tree, capsys):
    root, checker = public_tree
    (root / "HANDOFF.md").write_text("Private source history", encoding="utf-8")
    assert checker.main() == 1
    assert "excluded public member" in capsys.readouterr().out
