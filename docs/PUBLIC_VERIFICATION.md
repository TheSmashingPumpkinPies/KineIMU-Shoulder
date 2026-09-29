# Audited public-copy verification

Date: 2026-09-29. Final Windows audited-copy verification: PASS. Transfer and
remote Linux CI remain OPEN until their actual checks. The reviewed copies are
authorized by ADR-015; no tag, Release, DOI or PyPI publication is declared.

An independent no-hardlink clone and new environment executed local reviewed-copy
checkpoint `7dd991878b5e8b40d6fab12cb3a58a37155c9b6a`, with CPython3.12.14,
uv0.12.5 and frozen all-extras dependencies. This is a local execution identity,
not a claim that that preparation commit is available in public history.
`PYTHONPATH` and `KINEIMU_M1_RAW_ROOT` were unset. Final report/index changes are
separate from numerical execution; every production/test/example/reference input
was compared byte-for-byte with the executed clone. Final documentation integrity
is checked again before transfer. Packages bind the final actual source/docs bytes.

| Gate | Actual result |
|---|---|
| Full final pytest | 883 passed, 2 expected external M1 skips;674.99s |
| Ruff | PASS |
| Strict mypy |33package source files and1benchmark source file PASS |
| Executed docs/integrity |194Markdown files,1089immutable hashes,0errors |
| Two new Demo processes | Both exit0;4trajectories and26files per run |
| Independent numerical/determinism audit |27160error scalars/run;22canonical products, summaries/indexes equal |
| Reviewed historical benchmark |54source members and6independent audits; original statistics reproduced exactly |
| Final packages | New wheel/sdist;34source members/57notice files verified;2new isolated installations and analytical API checks PASS |

Two optional physical replay skips do not establish external capture replay
acceptance. Original M0–M6 acceptance remains historical and is not relabeled.
Historical benchmark counters/timings, failed batches and original experimental
dispositions are unchanged. See [audit](PUBLIC_AUDIT.md) and
[benchmark reproduction](PUBLIC_BENCHMARK.md).

## Preserved preparation failures

The first final full suite had882passed,2expectedskips and1failure: Windows
denied a temporary-directory rename after its experimental computation passed.
The original failed staging/logs remain private. The unchanged module passed in
isolation, then the complete unchanged suite passed with a new shorter temporary
root. No scientific code, assertion, budget or skip rule was relaxed.

The first package archive audit found a README CRLF/standard metadata LF mismatch.
Only the public README line endings were normalized; the first failed build/logs
were retained, then a new build passed the original archive and installation
assertions. Privacy/hash preparation failures are retained privately, alongside
untouched originals and complete original/public SHA-256 correspondence.

```powershell
uv sync --all-extras --frozen
uv run --frozen pytest -q --basetemp <unused-short-temporary-directory>
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen mypy benchmarks/demo/run_benchmark.py
uv run --frozen python scripts/check_docs_consistency.py
uv run --frozen python examples/m6_demo.py --output <unused-output-01>
uv run --frozen python examples/m6_demo.py --output <unused-output-02>
uv run --frozen python experiments/M6_CP2_20260928/audit.py --run1 <output-01> --run2 <output-02> --output <unused-audit.json>
uv build
```

Bracketed arguments are placeholders to replace with new paths. Actual command
exit codes, log digests and package digests are recorded in
[PUBLIC_VERIFICATION.json](PUBLIC_VERIFICATION.json). Private absolute paths,
original device identifiers, original/public mappings and preparation Git history
are not imported into the public repository. Its initial commit starts new history.
