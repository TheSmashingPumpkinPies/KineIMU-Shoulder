"""M6 CP1 packaging: frozen CP0 input contract, no processing or generation."""

import json
import shutil
from hashlib import sha256
from pathlib import Path

import pytest

from kineimu_shoulder.io.m1_packet import NodeId
from kineimu_shoulder.io.m2_replay import replay_capture
from kineimu_shoulder.validation.replay import adapter_config
from kineimu_shoulder.validation.stored_demo import input_audit, run_stored

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "datasets/samples/m6_synthetic"
TRAJECTORIES = ("F90", "AL90", "AR90", "T-MIX")
NAMES = (
    "SHA256SUMS.json", "annotations.json", "observation-labels.json", "case-manifest.json", "manifest.json",
) + tuple(
    f"{trajectory}/{name}" for trajectory in TRAJECTORIES
    for name in ("A.kimu", "B.kimu", "metadata.json", "A-si.json", "B-si.json")
)


def test_sample_matches_independently_frozen_cp0_inventory():
    # Expected identity/size comes from committed CP0 inventory, not this copy.
    inventory = json.loads((ROOT / "tests/fixtures/demo/input-inventory.json").read_bytes())
    expected = {row["path"]: row["sha256"] for row in inventory["inputs"]}
    before = {name: sha256((SAMPLE / name).read_bytes()).hexdigest() for name in NAMES}
    assert input_audit(SAMPLE) == expected == before
    assert sum((SAMPLE / name).stat().st_size for name in NAMES) == 4539058
    assert {name: sha256((SAMPLE / name).read_bytes()).hexdigest() for name in NAMES} == before


def test_provenance_covers_selection_omissions_and_source_lock():
    provenance = json.loads((SAMPLE / "provenance.json").read_bytes())
    frozen = json.loads((SAMPLE / "SHA256SUMS.json").read_bytes())
    selected = {row["path"]: row["sha256"] for row in provenance["selected_files"]}
    omitted = {row["path"]: row["sha256"] for row in provenance["unshipped_map_members"]}
    assert selected == input_audit(SAMPLE)
    assert {k: v for k, v in selected.items() if k != "SHA256SUMS.json"} | omitted == frozen
    assert len(omitted) == 12 and not (omitted.keys() & selected.keys())
    assert all(not (SAMPLE / name).exists() for name in omitted)
    assert provenance["source_type"] == "synthetic" and provenance["anatomical_eligible"] is False
    assert provenance["license_status"] == "INTERNAL ONLY / public redistribution pending"
    # Original CP1 manifest and CP0 contract record the generation source lock.
    assert provenance["generation_source_commit"] == "ee0741334e430c7cf8b5b9845d0a9b48426fecad"
    assert [row["id"] for row in provenance["trajectories"]] == list(TRAJECTORIES)
    for row in provenance["selected_files"]:
        assert row["bytes"] == (SAMPLE / row["path"]).stat().st_size


@pytest.mark.parametrize("trajectory", TRAJECTORIES)
@pytest.mark.parametrize("node", ("A", "B"))
def test_sample_capture_is_complete_sensor_input(trajectory, node):
    hashes = input_audit(SAMPLE)
    capture = SAMPLE / trajectory / f"{node}.kimu"
    replay = replay_capture(capture, expected_sha256=hashes[f"{trajectory}/{node}.kimu"],
                            expected_node_id=NodeId[node], config=adapter_config())
    # CP0 contract section 1: each stream 538 packets/2151 rows, 0–21.5 s, no issues.
    assert len(replay.epochs) == 1 and not replay.qc.issues
    assert replay.qc.packets_decoded == 538 and replay.qc.samples_decoded == 2151
    data = replay.epochs[0].sensor_data
    assert (data.device_time_us[0], data.device_time_us[-1]) == (0, 21500000)
    assert tuple(data.sample_sequences) == tuple(range(2151))


@pytest.mark.parametrize("name", NAMES)
def test_missing_sample_member_is_refused(name, tmp_path):
    copied = tmp_path / "input"
    shutil.copytree(SAMPLE, copied)
    (copied / name).unlink()
    with pytest.raises(FileNotFoundError):
        input_audit(copied)


@pytest.mark.parametrize("name", NAMES)
def test_changed_sample_member_is_refused_before_processing(name, tmp_path):
    copied = tmp_path / "input"
    shutil.copytree(SAMPLE, copied)
    path = copied / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="digest"):
        run_stored("F90", tmp_path / "output", input_root=copied)
    assert not (tmp_path / "output").exists()


def test_recomputed_map_cannot_authorize_changed_observations(tmp_path):
    copied = tmp_path / "input"
    shutil.copytree(SAMPLE, copied)
    path = copied / "F90/B.kimu"
    path.write_bytes(path.read_bytes() + b"\x00")
    map_path = copied / "SHA256SUMS.json"
    forged = json.loads(map_path.read_bytes())
    forged["F90/B.kimu"] = sha256(path.read_bytes()).hexdigest()
    map_path.write_text(json.dumps(forged), encoding="utf-8")
    with pytest.raises(ValueError, match="digest map changed"):
        input_audit(copied)


@pytest.mark.parametrize("trajectory", ("UNKNOWN", "F90-30", "../F90"))
def test_unsupported_sample_trajectory_is_refused(trajectory, tmp_path):
    with pytest.raises(ValueError, match="unknown stored Q trajectory"):
        run_stored(trajectory, tmp_path / "output", input_root=SAMPLE)
    assert not (tmp_path / "output").exists()
