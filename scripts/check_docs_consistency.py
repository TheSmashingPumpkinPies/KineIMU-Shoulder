"""Check public contracts, navigation and explicitly immutable export members."""

import hashlib
import json
import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Return nonzero for a broken link, archive mutation or stale active contract."""
    errors: list[str] = []
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, text=True
    ).splitlines()
    paths = sorted({ROOT / name for name in names if (ROOT / name).is_file()})
    markdown = [path for path in paths if path.suffix == ".md"]
    for path in markdown:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]\n]+\]\(([^)]+)\)", text):
            target = target.strip().split("#", 1)[0].strip("<>")
            if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            if not (path.parent / unquote(target)).exists():
                errors.append(f"{path.relative_to(ROOT)}: broken link {target}")

    manifest_path = ROOT / "PUBLIC_EXPORT.json"
    immutable_count = 0
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "kineimu-public-export/1.0":
            raise ValueError("unsupported public export schema")
        if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("source_head", "")):
            raise ValueError("missing source identity")
        seen: set[str] = set()
        for entry in manifest["files"]:
            name = entry["path"]
            path = ROOT / name
            if (not isinstance(name, str) or "\\" in name or ":" in name or
                    path.is_absolute() and not path.resolve().is_relative_to(ROOT.resolve()) or
                    ".." in Path(name).parts or Path(name).is_absolute()):
                errors.append(f"unsafe export path: {name}")
                continue
            if name in seen:
                errors.append(f"duplicate export path: {name}")
                continue
            seen.add(name)
            if not entry.get("immutable", False):
                continue
            immutable_count += 1
            if not path.is_file():
                errors.append(f"missing immutable export: {name}")
                continue
            if not path.resolve().is_relative_to(ROOT.resolve()):
                errors.append(f"unsafe export path: {name}")
                continue
            data = path.read_bytes()
            if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["export_sha256"]:
                errors.append(f"changed immutable export: {name}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"invalid public export manifest: {exc}")

    excluded_prefixes = ("docs/reference/", "docs/history/", "firmware/sticks3/", ".agents/", ".codex/")
    excluded_names = {"CURRENT_TASK.md", "HANDOFF.md", "CHANGELOG_DEV.md", "HANDOFF_PROTOCOL.md"}
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        if name in excluded_names or name.startswith(excluded_prefixes) or name in {".env", "id_rsa", "id_ed25519"}:
            errors.append(f"excluded public member: {name}")

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    if project["project"]["name"] != "kineimu_shoulder":
        errors.append("wrong distribution namespace")
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    package_names = {item["name"] for item in lock["package"]}
    if "kineimu-shoulder" not in package_names:
        errors.append("lock missing renamed project")
    if package_names & {"kineimu", "mobgap", "gaitmap", "kielmat"}:
        errors.append("retired package in lock")
    if "gait" in project["project"].get("optional-dependencies", {}):
        errors.append("retired extra")
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("kineimu/") or re.match(
            r"(?:kineimu_shoulder|benchmarks)/(?:gait|posture|activity)/", relative
        ):
            errors.append(f"retired module: {relative}")

    required = {
        "README.md": ["KineIMU Shoulder", "DONE", "physical acquisition validation", "hardware-free"],
        "PROJECT_SCOPE.md": ["Shoulder-only", "humerothoracic", "hardware-tested", "DONE"],
        "HARDWARE_PROFILE.md": [
            "XIAO nRF52840 Sense boards",
            "LSM6DS3TR-C",
            "Zephyr v4.4.0",
            "outside the current V1 mainline",
        ],
        "docs/adr/ADR-008-hardware-tested-software-complete-v1.md": [
            "Status: Accepted",
            "hardware-tested, software-complete V1",
            "Freeze hardware",
            "human-subject",
        ],
        "docs/adr/ADR-006-select-xiao-nrf52840-sense.md": [
            "Status: Accepted",
            "two **Seeed Studio XIAO nRF52840 Sense** boards",
            "USB-C",
            "two-node BLE",
        ],
        "docs/adr/ADR-007-select-upstream-zephyr.md": [
            "Status: Accepted",
            "upstream Zephyr v4.4.0",
            "Zephyr SDK 1.0.1",
            "xiao_ble/nrf52840/sense",
            "nRF Connect SDK is not an active dependency",
        ],
        "MOUNTING_PROTOCOL.md": ["jugular notch", "mid-humerus", "future don/doff"],
        "VALIDATION.md": [
            "Deterministic synthetic validation",
            "Recorded replay validation",
            "motion-capture comparison",
            "outside current V1 validation",
        ],
    }
    for name, terms in required.items():
        required_path = ROOT / name
        if not required_path.is_file():
            errors.append(f"missing required document: {name}")
            continue
        text = required_path.read_text(encoding="utf-8")
        for term in terms:
            if term.casefold() not in text.casefold():
                errors.append(f"{name}: missing {term}")
    spec = (ROOT / "docs/METRICS.md").read_text(encoding="utf-8")
    ids = re.findall(r"^\| (\d+) \|", spec, re.MULTILINE)
    if ids != [str(index) for index in range(1, 13)]:
        errors.append("metric table must contain eight core plus four extension IDs")
    for name in ["README.md", "ARCHITECTURE.md", "PROJECT_SCOPE.md"]:
        text = (ROOT / name).read_text(encoding="utf-8")
        if re.search(r"lower.back|kineimu/|kineimu\.(?:gait|posture)|M[7-9]\s*[—-]", text, re.I):
            errors.append(f"{name}: obsolete active architecture/roadmap")
    for error in errors:
        print(error)
    print(f"Docs check: {len(markdown)} Markdown files, "
          f"{immutable_count} immutable export hashes, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
