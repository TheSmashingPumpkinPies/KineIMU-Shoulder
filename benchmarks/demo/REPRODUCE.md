# KineIMU Shoulder — reproduce M6 CP3 performance evidence

Read [protocol1.1](PROTOCOL.md) and [performance report](REPORT.md) first.
Successful measurement source: `3e0647c4f53803abf134fee68659f63ca006e407`.
Formal external run is batch03; its repository exact-byte copy is
`experiments/M6_CP3_20260928/batch01`. Earlier batch01 invocation was preflight
rejected; complete protocol1.0 batch02 remains separately under `failed-batch02`.
No failed repeat was replaced in a batch or promoted into successful statistics.

## Audit retained results and recompute all performance numbers

From the repository root with its frozen environment; choose a new output file:

```powershell
uv run --frozen python benchmarks/demo/run_benchmark.py --recompute experiments/M6_CP3_20260928/batch01 --output recomputed-cp3-new.json
```

The audit verifies every batch file/membership against SHA256SUMS.json, all54
runtime source ZIP members against the current executed source bytes, the original
input/sample hashes, raw counter deltas/log bytes, launch/worker/OS-command identity,
original audit output and a fresh numerical audit of each complete child. It
checks the unchanged CP2 pair whitelist and derives statistics from each raw ns.
The resulting summary must match the original; exit0 requires all gates PASS.
Only the new audit output is written; batch files remain immutable. Original and
copy produced identical independently recomputed JSON in original-recompute.json
and retained-recompute.json. Exact displayed values were separately checked using
rational arithmetic and independent sorting in report-values-audit.json.

If later development changes an archived source member, use a separate checkout
at the measurement source commit and pass the retained batch's absolute path.
Install that checkout's frozen dependencies. Verify all member hashes first;
runtime-source.zip retains actual executed bytes, including line endings.
Do not reset the active workspace or weaken hash checks to make a later version
look like the measurement lock. Evidence delivery commit and measurement commit
are different: the measured source existed before the later batch evidence commit.
This reproduction is Windows retained-evidence acceptance, not CP5 fresh-environment
or Linux execution proof.

For manual performance arithmetic, take the five timed wall_ns values from
attempts.json (exclude warmup), sort wall_ns/1e9 and select index2 for median;
min/max are endpoints. For each rate use17208/(wall_ns/1e9), then independently
sort those five rates and take third/endpoints. Raw counter_start_ns/counter_end_ns
must also reproduce wall_ns. Report uses six decimals; raw JSON has full precision.
Do not use child run.json duration or substitute17208/mean(wall_s).

## Run a new batch

Use an isolated clean checkout of the intended source, with frozen dependencies
already installed. No hardware or external M1 root is required. Installations,
environment probes, parent audit and statistics stay outside child timing.

```powershell
uv sync --extra analysis --frozen
uv --version
python --version
# Verify uv resolves inside the Python environment as well as in the outer shell.
uv run --frozen python -c "import shutil; print(shutil.which('uv'))"
# Pick a root that does not exist; keep it outside the repository/raw/evidence trees.
uv run --frozen python benchmarks/demo/run_benchmark.py --output "$env:TEMP/kineimu-m6-cp3-new-batch"
```

On the measured host, pinned uv is `uv` and was
initially absent from PATH. The successful invocation prepended only that process's
PATH before running the explicit pinned binary:

```powershell
$env:PATH="$env:USERPROFILE/.local/bin;$env:PATH"
& "$env:USERPROFILE/.local/bin/uv.exe" run --frozen python benchmarks/demo/run_benchmark.py --output "$env:TEMP/kineimu-m6-cp3-new-batch"
```

Use Python3.12.14/uv0.12.5 and the pinned analysis versions. Never overwrite a
consumed root. The parent sets all three numerical thread environment variables
to1 before each child imports and removes KINEIMU_M1_RAW_ROOT. One warmup precedes
five sequential independent timed workers. Sidecar identity is derived from each
output's parent; the only varying OS argument is --output, preserving CP2's exact
whitelist. Windows venv launcher and worker PIDs may differ; direct parent/child
relationship plus worker sidecar/run.json PID and actual argv are checked.

Do not edit source or run tests during timing. Cache is not flushed; record power,
storage, memory and ordinary background conditions. If a warmup fails, all timed
slots are NOT RUN. Timed failures remain FAIL and remaining scheduled slots run;
there is no replacement or outlier deletion. Successful statistics are withheld
on any correctness/identity/source/input/integrity failure. Corrections need a new
committed source/protocol lock and new batch; preserve all earlier attempts.
A later source run records its own HEAD and is not the historical measured batch.
New wall times need not be identical on the same desktop; no speed target is used.

## Repository verification and delivery

After timing ends, use an external pytest basetemp because Demo protects repository
subdirectories. Full maintainer regression uses the already existing M1 raw root;
this is read-only verification, not physical collection:

```powershell
$env:KINEIMU_M1_RAW_ROOT='<external-data>/kineimu_m1_usb_30min_20260925_01'
uv run --frozen pytest --basetemp "$env:TEMP/kineimu-m6-cp3-new-full-tests"
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen mypy benchmarks/demo/run_benchmark.py
uv run --frozen python scripts/check_docs_consistency.py
git diff --check
uv build
```

Use a fresh test root. Do not set an absent external raw path and claim all replay
tests ran; a clone without that optional data must report its actual skips.
All invocation commands/exits/raw logs are retained by check-tool.txt. Failed
repository-local temp tests, PATH preflight, protocol1.0 pair comparisons and
test/type/build/doc attempts remain separately recorded with original hashes.

The batch inventory is frozen independently of the later delivery snapshot.
Delivery SHA256SUMS.json covers source/tests/guides/report/README and evidence,
excluding itself, dynamic state and later committed proof. committed-evidence.json
is generated after the delivery commit and binds its Git blobs to exact disk bytes.
It is not a source of benchmark statistics. Dynamic files record the final HEAD
and next action; they do not rewrite the protocol, sample, original budgets or maps.
CP4 licensing/packaging and CP5 fresh clone remain separate gates; sample INTERNAL
ONLY, hardware frozen, Linux NOT RUN, no publication or human-subject action.
