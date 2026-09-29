# Validation reproduction

Run from a repository clone with CPython 3.12.14, uv 0.12.5 and frozen dependencies.
Outputs must use fresh paths; never overwrite input, raw or failed evidence.

```powershell
uv sync --all-extras --frozen
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen mypy benchmarks/demo/run_benchmark.py
uv run --frozen python scripts/check_docs_consistency.py
uv build
```

Two physical replay tests require the complete original external M1 USB recording.
Set `KINEIMU_M1_RAW_ROOT` only to a real, hash-verified recording directory. Without
it, those tests report expected skips. The bundled Node B stationary recording
is exercised separately. Synthetic evidence does not establish anatomical accuracy.

## Stored sample and independent numerical audit

```powershell
uv run --frozen python examples/m6_demo.py --output "$env:TEMP/kineimu-demo-one"
uv run --frozen python examples/m6_demo.py --output "$env:TEMP/kineimu-demo-two"
uv run --frozen python validation/auditors/demo.py --run1 "$env:TEMP/kineimu-demo-one" --run2 "$env:TEMP/kineimu-demo-two" --output "$env:TEMP/kineimu-demo-audit.json"
```

The independent audit recomputes analytical rotations, geodesic/error arithmetic,
coverage and retained support, and checks canonical product equality. It does not
derive expected values from production geometry or metrics. Choose unused paths
for every attempt; failures remain recorded.

## Baseline and robustness

Commands and the predeclared 1,142-case design are in [VALIDATION.md](../../VALIDATION.md).
The [contract](../../protocols/M5_VALIDATION_CONTRACT.md) freezes labels, seeds,
budgets and supported domains. The [coverage record](coverage.md) states the
accepted tested scope. Full original runs and prior failed dispositions remain in
the local evidence archive; a fresh run records its own source lock and results.
Do not substitute archived data paths into current commands or weaken source checks.

For performance collection and retained historical timing arithmetic, use the
[benchmark reproduction guide](../../benchmarks/demo/REPRODUCE.md).
