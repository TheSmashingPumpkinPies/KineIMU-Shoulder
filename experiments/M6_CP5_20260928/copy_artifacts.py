"""Preserve only built wheel/sdist bytes, keeping the first partial copy untouched."""

import hashlib
import shutil
import tarfile
import zipfile

from collect import CLONE, write
from run_check import EVIDENCE, WORK


def members(path):
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return {name: archive.read(name) for name in archive.namelist()}
    with tarfile.open(path) as archive:
        return {member.name: archive.extractfile(member).read() for member in archive.getmembers() if member.isfile()}


if __name__ == "__main__":
    source = WORK / "build-01"
    destination = EVIDENCE / "artifacts/clone-build-02"
    destination.mkdir(parents=True, exist_ok=False)
    original = CLONE / "experiments/M6_CP4_FINAL_20260928/artifacts/candidate02"
    copied, differences = {}, {}
    for path in source.iterdir():
        if path.suffix not in (".whl", ".gz"):
            continue
        target = destination / path.name
        shutil.copyfile(path, target)
        assert path.read_bytes() == target.read_bytes()
        copied[path.name] = dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        old, new = members(original / path.name), members(path)
        assert old.keys() == new.keys()
        differences[path.name] = [name for name in old if old[name] != new[name]]
        expected = ({"kineimu_shoulder/summary.py", "kineimu_shoulder-0.1.0.dist-info/RECORD"}
                    if path.suffix == ".whl" else {"kineimu_shoulder-0.1.0/kineimu_shoulder/summary.py"})
        assert set(differences[path.name]) == expected
        summary = next(name for name in expected if name.endswith("summary.py"))
        assert old[summary].replace(b"\r\n", b"\n") == new[summary]
    assert len(copied) == 2
    write("artifact-copy-02.json", dict(status="PASS", copied_artifacts=copied, cp4_member_differences=differences,
          reason="Declared summary.py Git LF checkout; CP4 CRLF bytes unchanged; wheel RECORD follows source bytes",
          source=str(source), retained=str(destination),
          previous_partial="artifacts/clone-build-01 retained with uv build .gitignore; not authoritative"))
    print("Artifact copy PASS: both archives byte-identical; only declared LF source and wheel RECORD differ from CP4")
