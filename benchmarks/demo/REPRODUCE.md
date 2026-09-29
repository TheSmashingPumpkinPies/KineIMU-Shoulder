# Benchmark reproduction

## New collection

Install the locked analysis environment in a clean checkout. Choose a new
output directory outside the repository. Current protocol 1.2 generates its own
preflight pair, then one warmup and five timed runs; every failure remains recorded.
Do not run tests or edit source during measurement.

```powershell
uv sync --extra analysis --frozen
uv run --frozen python benchmarks/demo/run_benchmark.py --output "$env:TEMP/kineimu-benchmark-new"
uv run --frozen python benchmarks/demo/run_benchmark.py --recompute "$env:TEMP/kineimu-benchmark-new" --output "$env:TEMP/kineimu-benchmark-audit.json"
```

Python 3.12.14 and uv 0.12.5 are required. Ensure `uv` is on the child PATH.
The full new batch is self-contained with hashes, actual source archive, outputs
and independent audits. An existing output path is rejected.

## Historical timing statistics

The [report](REPORT.md) belongs to the original protocol 1.1 measured source.
The retained counter records and logs below reproduce its unchanged statistics.
This arithmetic is separate from full historical scientific/inventory acceptance,
which requires the complete local evidence archive. The large repeated derived
products are intentionally omitted from the public working tree.

```python
import hashlib, json, statistics
from pathlib import Path
root = Path("benchmarks/demo/reference/batch01")
rows = json.loads((root / "attempts.json").read_text())
expected = json.loads((root / "summary.json").read_text())
assert [r["slot"] for r in rows] == ["warmup", "timed01", "timed02", "timed03", "timed04", "timed05"]
for row in rows:
    folder = root / row["slot"]
    measure = json.loads((folder / "measurement.json").read_text())
    for key in ("counter_start_ns", "counter_end_ns", "wall_ns", "wall_s", "node_samples_per_s", "exit_code"):
        assert row[key] == measure[key]
    assert row["wall_ns"] == row["counter_end_ns"] - row["counter_start_ns"]
    assert row["wall_s"] == row["wall_ns"] / 1e9
    assert row["node_samples_per_s"] == 17208 / row["wall_s"]
    for name, digest in row["log_sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
for metric in ("wall_s", "node_samples_per_s"):
    values = [row[metric] for row in rows[1:]]
    observed = dict(median=statistics.median(values), min=min(values), max=max(values))
    assert observed == expected[metric]
    print(metric, observed)
```

The warmup is excluded; no timed observation is removed or replaced.
