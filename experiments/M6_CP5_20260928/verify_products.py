"""Retain exact CP5 outputs and compare them with frozen CP2 scientific products."""

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from collect import CLONE, HEAD, hashes, write
from run_check import EVIDENCE


def read(path):
    return json.loads(path.read_bytes())


def summary_identity_equal(old, new, old_head, new_head):
    before = f"source HEAD: `{old_head}`".encode()
    after = f"source HEAD: `{new_head}`".encode()
    return old.count(before) == new.count(after) == 1 and old.replace(before, after) == new


def command_identity_equal(old, new):
    old, new = copy.deepcopy(old), copy.deepcopy(new)
    if not old or not new or not Path(old[0]).samefile(new[0]):
        return False
    old[0] = new[0] = str(Path(old[0]).resolve())
    for command in (old, new):
        if command.count("--output") != 1 or command.index("--output") + 1 >= len(command):
            return False
        command[command.index("--output") + 1] = "<output>"
    return old == new


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", default="01", choices=("01", "02", "03"))
    attempt = parser.parse_args().attempt
    baseline = CLONE / "experiments/M6_CP2_20260928/run1"
    retained = {}
    for number in (1, 2):
        source, destination = CLONE / f"demo-output-{number:02}", EVIDENCE / f"run{number}"
        if not destination.exists():
            shutil.copytree(source, destination)
        before, after = hashes(source), hashes(destination)
        assert before == after and len(before) == 26
        retained[f"run{number}"] = dict(original=str(source), files=before)
    if not (EVIDENCE / "retained-products.json").exists():
        write("retained-products.json", retained)
    else:
        assert read(EVIDENCE / "retained-products.json") == retained
    fresh = CLONE / "demo-output-01"
    compared = ["replay/report.json"]
    compared += [p.relative_to(baseline).as_posix() for p in sorted((baseline / "replay/cases").rglob("*"))
                 if p.is_file()]
    assert len(compared) == 21
    equal = {name: hashlib.sha256((fresh / name).read_bytes()).hexdigest() for name in compared
             if (fresh / name).read_bytes() == (baseline / name).read_bytes()}
    mismatches = sorted(set(compared) - set(equal))
    old_manifest, new_manifest = read(baseline / "replay/manifest.json"), read(fresh / "replay/manifest.json")
    manifest_variation = {}
    previous_head = old_manifest["git_commit"]
    assert previous_head == "1732b1af274ebf05c241d515ebcc126e65def3cd" and new_manifest["git_commit"] == HEAD
    changed_sources = {name for name in old_manifest["source_file_sha256"].keys() |
                       new_manifest["source_file_sha256"].keys()
                       if old_manifest["source_file_sha256"].get(name) != new_manifest["source_file_sha256"].get(name)}
    assert changed_sources == {"kineimu_shoulder/summary.py"}
    for key in ("git_commit", "source_file_sha256"):
        manifest_variation[key] = dict(baseline=old_manifest.pop(key), fresh=new_manifest.pop(key))
    assert old_manifest == new_manifest
    old, new = read(baseline / "run.json"), read(fresh / "run.json")
    summary_equal = summary_identity_equal((baseline / "summary.md").read_bytes(),
                                          (fresh / "summary.md").read_bytes(), previous_head, HEAD)
    changes = {}
    for key in ("output_absolute_path", "input_root", "started_utc", "ended_utc", "duration_s", "pid"):
        changes[key] = dict(baseline=old.pop(key), fresh=new.pop(key))
    assert command_identity_equal(old["command"], new["command"])
    resolved_python = str(Path(new["command"][0]).resolve())
    changes["command"] = dict(baseline=old.pop("command"), fresh=new.pop("command"),
                              python_alias_samefile=True, resolved_python=resolved_python)
    for key in ("head", "file_sha256"):
        changes[f"source.{key}"] = dict(baseline=old["source"].pop(key), fresh=new["source"].pop(key))
    for key in ("replay/manifest.json", "replay/SHA256SUMS.txt", "summary.md"):
        changes[f"product_sha256.{key}"] = dict(baseline=old["product_sha256"].pop(key),
                                                fresh=new["product_sha256"].pop(key))
    run_fields_equal = old == new
    source_map = copy.deepcopy(read(fresh / "run.json")["source"]["file_sha256"])
    source_map.update(read(fresh / "replay/manifest.json")["source_file_sha256"])
    source_map["experiments/M6_CP2_20260928/audit.py"] = hashlib.sha256(
        (CLONE / "experiments/M6_CP2_20260928/audit.py").read_bytes()).hexdigest()
    runtime_bytes = {}
    for name, expected in source_map.items():
        raw = (CLONE / name).read_bytes()
        git = subprocess.check_output(["git", "show", f"{HEAD}:{name}"], cwd=CLONE)
        assert raw == git and hashlib.sha256(raw).hexdigest() == expected, name
        runtime_bytes[name] = raw
    archive_name = f"runtime-source-attempt{attempt}.zip"
    with zipfile.ZipFile(EVIDENCE / archive_name, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in runtime_bytes.items():
            archive.writestr(name, raw)
    with zipfile.ZipFile(EVIDENCE / archive_name) as archive:
        assert {name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()} == source_map
    write(f"runtime-source-sha256-{attempt}.json", source_map)
    write(f"frozen-products-{attempt}.json", dict(
        status="PASS" if not mismatches and run_fields_equal and summary_equal else "FAIL",
        baseline="experiments/M6_CP2_20260928/run1", source_head=HEAD,
        exact_equal_scientific_products_and_summary=equal, mismatches=mismatches,
        summary_equal_after_exact_source_head_substitution=summary_equal,
        manifest_other_fields_equal=True, manifest_provenance_variation=manifest_variation,
        run_other_fields_equal=run_fields_equal, cross_clone_provenance_variation=changes,
        same_clone_pair_whitelist="Unchanged CP2 auditor: only output/command output arg/UTC/duration/PID",
        runtime_files=len(source_map), runtime_files_equal_committed_git=True,
        runtime_source_archive=archive_name,
    ))
    assert not mismatches and run_fields_equal and summary_equal
    print(f"Frozen baseline PASS: {len(equal)} exact scientific products; summary changes only HEAD; "
          f"source ZIP {len(source_map)} Git-exact files")
