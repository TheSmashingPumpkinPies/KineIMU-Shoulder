# Contributing to KineIMU Shoulder

Read [project scope](PROJECT_SCOPE.md), [architecture](ARCHITECTURE.md) and
[contributor instructions](AGENTS.md). File focused issues and pull requests at
https://github.com/TheSmashingPumpkinPies/KineIMU-Shoulder.

Use Python3.12.14 and uv0.12.5, install with `uv sync --all-extras --frozen`, and run
`uv run --frozen pytest`, `uv run --frozen ruff check .`, `uv run --frozen mypy`,
`uv run --frozen python scripts/check_docs_consistency.py` and `uv build`.
Keep pytest temporary files outside the checkout. Two optional physical replay tests
skip without the external M1 raw root; report skips explicitly.

Numerical changes need known-input tests and explicit units/frame conventions. Cite
independent expected values, preserve deterministic seeds and compare scientific
outputs before claiming correctness. Record environment, source revision and input
hashes for formal experiments. Do not overwrite frozen data, reports or failed runs.

Preserve MIT notices for original Python code/documents, existing Apache-2.0 firmware
headers and original third-party texts. The sample CC0 annex has a specific member
list. See [public provenance](docs/PUBLIC_EXPORT.md) and [evidence availability](docs/PUBLIC_EVIDENCE.md)
before adding data or changing archival materials. No human/clinical claims, schema
changes or expanded V1 scope without a recorded maintainer decision.
