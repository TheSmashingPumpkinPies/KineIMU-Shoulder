"""Check real preview archives against original sources and notice bytes."""

import argparse
import hashlib
import json
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("preserve old audits; select a new output")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    stem = f"kineimu_shoulder-{project['version']}"
    wheel = args.artifacts / f"{stem}-py3-none-any.whl"
    sdist = args.artifacts / f"{stem}.tar.gz"
    dist_info = f"{stem}.dist-info"
    share = f"{stem}.data/data/share/kineimu-shoulder/third-party/"
    errors = []
    source_files = [p for p in (ROOT / "kineimu_shoulder").rglob("*") if p.suffix == ".py" or p.name == "py.typed"]
    notices = [p for p in (ROOT / "docs/release/licenses").rglob("*") if p.is_file()]
    with zipfile.ZipFile(wheel) as whl, tarfile.open(sdist) as tar:
        wheel_files = {name: whl.read(name) for name in whl.namelist()}
        sdist_files = {}
        for member in tar.getmembers():
            if member.isfile():
                stream = tar.extractfile(member)
                assert stream is not None
                sdist_files[member.name.removeprefix(stem + "/")] = stream.read()
        for path in source_files:
            relative = path.relative_to(ROOT).as_posix()
            for kind, files in (("wheel", wheel_files), ("sdist", sdist_files)):
                if files.get(relative) != path.read_bytes():
                    errors.append(f"{kind}: missing/changed source {relative}")
        for path in notices:
            relative = path.relative_to(ROOT / "docs/release/licenses").as_posix()
            if wheel_files.get(share + relative) != path.read_bytes():
                errors.append(f"wheel: missing/changed third-party notice {relative}")
            if sdist_files.get("docs/release/licenses/" + relative) != path.read_bytes():
                errors.append(f"sdist: missing/changed third-party notice {relative}")
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            if wheel_files.get(f"{dist_info}/licenses/{name}") != (ROOT / name).read_bytes():
                errors.append(f"wheel: missing/changed root {name}")
        for name in ("README.md", "LICENSE", "CITATION.cff", "THIRD_PARTY_NOTICES.md", "pyproject.toml",
                     "docs/M6_TECHNICAL_REPORT.md", "docs/release/REVIEW.md", "docs/release/PACKAGING.md"):
            if sdist_files.get(name) != (ROOT / name).read_bytes():
                errors.append(f"sdist: missing/changed document {name}")
        for kind, files in (("wheel", wheel_files), ("sdist", sdist_files)):
            for name in files:
                if name.startswith(("examples/", "datasets/", "tests/", "experiments/", "firmware/", ".git/")):
                    errors.append(f"{kind}: unexpected repository/demo asset {name}")
        message = BytesParser().parsebytes(wheel_files[f"{dist_info}/METADATA"])
        assert message["Name"] == project["name"] and message["Version"] == project["version"]
        assert message["Summary"] == project["description"]
        assert message["Requires-Python"] == "<3.13,>=3.12"
        assert not message["License-Expression"] and not message["Author"] and not message["Author-email"]
        assert set(message.get_all("Provides-Extra")) == set(project["optional-dependencies"])
        expected_dependencies = set(project["dependencies"])
        for extra, requirements in project["optional-dependencies"].items():
            expected_dependencies.update(f"{requirement}; extra == '{extra}'" for requirement in requirements)
        assert set(message.get_all("Requires-Dist")) == expected_dependencies
        assert set(message.get_all("License-File")) == {"LICENSE", "THIRD_PARTY_NOTICES.md"}
        assert "\n\n" in wheel_files[f"{dist_info}/METADATA"].decode()
        readme = wheel_files[f"{dist_info}/METADATA"].split(b"\n\n", 1)[1]
        assert readme.rstrip(b"\n") == (ROOT / "README.md").read_bytes().rstrip(b"\n")
        assert "entry_points.txt" not in {Path(name).name for name in wheel_files}
        inventory = {
            "status": "PASS" if not errors else "FAIL", "errors": errors,
            "source_files_verified": len(source_files), "notice_files_required": len(notices),
            "artifacts": [{"path": str(path.resolve()), "bytes": path.stat().st_size,
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                          for path in (wheel, sdist)],
            "wheel_members": {k: hashlib.sha256(v).hexdigest() for k, v in wheel_files.items()},
            "sdist_members": {k: hashlib.sha256(v).hexdigest() for k, v in sdist_files.items()},
            "metadata": {k: message.get_all(k) for k in ("Name", "Version", "Summary", "Requires-Python",
                         "Requires-Dist", "Provides-Extra", "License-File", "License-Expression")},
        }
    args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"Archive review: {inventory['status']}, {len(errors)} errors")
    if errors:
        print("\n".join(errors[:6]))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
