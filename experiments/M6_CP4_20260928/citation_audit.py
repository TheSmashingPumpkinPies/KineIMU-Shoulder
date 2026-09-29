"""Parse the citation draft and report its expected incomplete CFF state."""

import hashlib
import importlib.metadata as metadata
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent


def main() -> None:
    draft = ROOT / "CITATION.cff"
    source = EVIDENCE / "cff-1.2.0-schema.json"
    document = yaml.safe_load(draft.read_text(encoding="utf-8"))
    schema = json.loads(source.read_text(encoding="utf-8"))
    validator = jsonschema.validators.validator_for(schema)
    validator.check_schema(schema)
    errors = sorted(validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(document),
                    key=lambda error: error.message)
    assert len(errors) == 1 and errors[0].validator == "required"
    assert errors[0].message == "'authors' is a required property"
    assert "authors" not in document and "repository-code" not in document and "doi" not in document
    assert document["title"] == "KineIMU Shoulder" and document["version"] == "0.1.0"
    destination = EVIDENCE / "citation-draft-audit.json"
    if destination.exists():
        raise SystemExit("preserve existing audit")
    result = {
        "disposition": "EXPECTED_INCOMPLETE_DRAFT", "yaml_parse": "PASS", "cff_schema_valid": False,
        "errors": [error.message for error in errors],
        "maintainer_gate": "approved authors and public repository/release identity required before CP4",
        "python": sys.version, "executable": sys.executable,
        "tooling": {name: metadata.version(name) for name in ("PyYAML", "jsonschema")},
        "tooling_scope": "Existing external tooling environment; not added to project runtime or lock",
        "citation_sha256": hashlib.sha256(draft.read_bytes()).hexdigest(),
        "schema_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
