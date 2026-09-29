"""Capture original installed third-party license texts for review, not legal approval."""

import hashlib
import importlib.metadata as metadata
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "docs/release/licenses"
DIRECT = {"numpy", "scipy", "pandas", "imucal", "imufusion", "bleak", "pyserial"}
RUNTIME = {"python-dateutil", "six", "tzdata", "typing-extensions"}


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> None:
    if (DESTINATION / "inventory.json").exists():
        raise SystemExit("inventory exists; preserve the snapshot rather than overwrite")
    records = []
    for dist in sorted(metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
        name = normalized(dist.metadata["Name"])
        if name == "kineimu-shoulder":
            continue
        copies = []
        for member in dist.files or []:
            member_name = str(member).replace("\\", "/")
            basename = member.name.lower()
            if not (
                ".dist-info/licenses/" in member_name
                or basename.startswith(("license", "copying", "notice"))
                and not basename.endswith((".py", ".pyc"))
            ):
                continue
            original = Path(dist.locate_file(member))
            if not original.is_file():
                continue
            target = DESTINATION / f"{name}-{dist.version}" / (member_name + ".txt")
            target.parent.mkdir(parents=True, exist_ok=True)
            data = original.read_bytes()
            target.write_bytes(data)
            assert target.read_bytes() == data
            copies.append({
                "distribution_member": member_name,
                "copy": target.relative_to(ROOT).as_posix(),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
        role = "direct" if name in DIRECT else "runtime-transitive" if (
            name in RUNTIME or name.startswith("winrt-")
        ) else "development-tool-or-transitive"
        records.append({
            "name": dist.metadata["Name"], "version": dist.version, "role": role,
            "metadata_license_expression": dist.metadata.get("License-Expression"),
            "metadata_license_first_line": (dist.metadata.get("License") or "").split("\n")[0],
            "license_classifiers": [c for c in dist.metadata.get_all("Classifier", []) if "License" in c],
            "project_urls": dist.metadata.get_all("Project-URL", []),
            "copied_files": copies,
            "installed_text_status": "RETAINED" if copies else "NOT_SUPPLIED_BY_INSTALLED_DISTRIBUTION",
        })
    result = {
        "purpose": "Third-party notice review; no project license or public release approval",
        "platform": sys.platform, "python": sys.version,
        "source": "Existing locked all-extras development environment; original distribution members",
        "uv_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "distributions": records,
    }
    (DESTINATION / "inventory.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Retained {sum(len(r['copied_files']) for r in records)} notice files for {len(records)} distributions")


if __name__ == "__main__":
    main()
