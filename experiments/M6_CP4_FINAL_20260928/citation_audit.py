"""Validate approved citation metadata against the retained official CFF schema."""

import hashlib
import importlib.metadata as metadata
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent


def main() -> int:
    source = ROOT / "experiments/M6_CP4_20260928/cff-1.2.0-schema.json"
    expected_schema = "0b8d22140da702d766df318dcff3a91af2f39521298dcf36d76315fd99cc169b"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_schema
    citation = ROOT / "CITATION.cff"
    document = yaml.safe_load(citation.read_text(encoding="utf-8"))
    schema = json.loads(source.read_text(encoding="utf-8"))
    validator = jsonschema.validators.validator_for(schema)
    validator.check_schema(schema)
    errors = sorted(
        validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(document),
        key=lambda error: error.message,
    )
    assert document["authors"] == [{"family-names": "Liao", "given-names": "Hongbo"}]
    assert document["title"] == "KineIMU Shoulder" and document["version"] == "0.1.0"
    assert document["license"] == "MIT"
    assert document["repository-code"] == "https://github.com/TheSmashingPumpkinPies/kineimu-shoulder"
    assert not any(key in document for key in ("date-released", "doi", "identifiers"))
    destination = EVIDENCE / "citation-candidate-audit.json"
    if destination.exists():
        raise SystemExit("preserve existing audit; use a new evidence root")
    result = {
        "status": "PASS" if not errors else "FAIL", "yaml_parse": "PASS", "cff_schema_valid": not errors,
        "errors": [error.message for error in errors], "python": sys.version, "executable": sys.executable,
        "tooling": {name: metadata.version(name) for name in ("PyYAML", "jsonschema")},
        "tooling_scope": "Existing external tooling; no new project dependency or lock change",
        "citation_sha256": hashlib.sha256(citation.read_bytes()).hexdigest(),
        "schema_sha256": expected_schema, "schema_source": str(source.relative_to(ROOT)),
        "schema_license_and_provenance": "experiments/M6_CP4_20260928/cff-upstream-notice-sources.json",
        "repository": "Maintainer-approved destination; public hosting not asserted",
        "publication_date": "omitted because publication has not occurred",
    }
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
