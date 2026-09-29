"""CP4 E guards: a duplicate or incomplete collection cannot earn acceptance."""

import importlib
from hashlib import sha256

import pytest


def api():
    spec = importlib.util.find_spec("kineimu_shoulder.validation.formal_replay")
    assert spec is not None, "formal B/C/D collection guard missing"
    return importlib.import_module(spec.name)


def fixture(root):
    root.mkdir()
    (root / "result.json").write_bytes(b'{"value": null}\n')
    digest = sha256(b'{"value": null}\n').hexdigest()
    (root / "SHA256SUMS.txt").write_text(f"{digest}  result.json\n", encoding="utf-8")
    return root


def test_complete_inventory_checks_actual_bytes_and_entire_support(tmp_path):
    root = fixture(tmp_path / "run")
    # Hand-written fixture bytes, independent of the inventory implementation.
    assert api().inventory(root, {"result.json"}) == {
        "result.json": sha256(b'{"value": null}\n').hexdigest()}


@pytest.mark.parametrize("damage", ["modified", "missing", "unlisted", "duplicate", "traversal", "omitted"])
def test_inventory_rejects_hash_or_complete_support_corruption(tmp_path, damage):
    root = fixture(tmp_path / "run")
    if damage == "modified":
        (root / "result.json").write_bytes(b'{}\n')
    elif damage == "missing":
        (root / "result.json").unlink()
    elif damage == "unlisted":
        (root / "extra.json").write_bytes(b'{}\n')
    elif damage == "duplicate":
        p = root / "SHA256SUMS.txt"
        p.write_text(p.read_text()*2)
    elif damage == "traversal":
        (root / "SHA256SUMS.txt").write_text("0"*64 + "  ../escape.json\n")
    else:
        (root / "SHA256SUMS.txt").write_text("")
    with pytest.raises((ValueError, FileNotFoundError)):
        api().inventory(root, {"result.json"})


def test_pair_requires_two_distinct_processes_and_exact_canonical_bytes(tmp_path):
    one, two = fixture(tmp_path / "one"), fixture(tmp_path / "two")
    assert api().compare_pair(one, two, {"result.json"}, [101, 102])["canonical_equal"]
    with pytest.raises(ValueError, match="independent"):
        api().compare_pair(one, two, {"result.json"}, [101, 101])
    with pytest.raises(ValueError, match="distinct"):
        api().compare_pair(one, one, {"result.json"}, [101, 102])
    (two / "result.json").write_bytes(b'{"value": 1}\n')
    digest = sha256(b'{"value": 1}\n').hexdigest()
    (two / "SHA256SUMS.txt").write_text(f"{digest}  result.json\n")
    with pytest.raises(ValueError, match="bytes"):
        api().compare_pair(one, two, {"result.json"}, [101, 102])


def test_existing_or_raw_output_is_rejected_before_creation(tmp_path):
    source = tmp_path / "raw"
    source.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError):
        api().protect_output(out, [source])
    with pytest.raises(ValueError):
        api().protect_output(source / "processed", [source])
    assert not (source / "processed").exists()
    with pytest.raises(ValueError):
        api().protect_output(tmp_path, [source])


def test_formal_assembly_preserves_existing_evidence_guard_and_replays_full_node(tmp_path, monkeypatch):
    from kineimu_shoulder.validation import replay
    from kineimu_shoulder.validation.recorded_node import NODE_B, export_recorded

    claimed = tmp_path / "experiments" / "formal" / "run1"
    claimed.mkdir(parents=True)
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    before = NODE_B.path.read_bytes()
    with pytest.raises(ValueError, match="existing evidence"):
        export_recorded(claimed / "C")
    helper = getattr(api(), "assemble_stage", None)
    assert helper is not None, "collection must assemble outside protected experiment trees"
    staging = tmp_path / "staging" / "C"
    assert helper(export_recorded, claimed / "C", staging) == 0
    import json
    data = json.loads((claimed / "C/cases/REC-NODE-B/result.json").read_bytes())
    # Complete retained source anchors from the M5.4 replay plan, not a new run.
    assert data["epochs"][0]["orientation"]["timestamp_us"][0] == 257030578
    assert len(data["epochs"][0]["orientation"]["quaternion_wn"]) == 832
    assert NODE_B.path.read_bytes() == before
    assert not staging.exists()
    with pytest.raises(ValueError, match="existing evidence"):
        export_recorded(claimed / "C-new")


@pytest.mark.parametrize("damage", ["none", "modified", "omitted", "unlisted"])
def test_separate_auditor_rejects_pair_corruption_independently(tmp_path, damage):
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "experiments/M5_CP4_STAGE_E_20260927/audit.py"
    assert path.exists(), "separate E auditor missing"
    spec = spec_from_file_location("cp4_e_audit", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    one, two = fixture(tmp_path / "one"), fixture(tmp_path / "two")
    if damage == "modified":
        (two / "result.json").write_bytes(b'{}\n')
    elif damage == "omitted":
        (two / "SHA256SUMS.txt").write_text("")
    elif damage == "unlisted":
        (two / "extra").write_bytes(b"x")
    if damage == "none":
        assert module.compare_canonical(one, two, {"result.json"})["canonical_equal"]
    else:
        with pytest.raises(ValueError):
            module.compare_canonical(one, two, {"result.json"})
