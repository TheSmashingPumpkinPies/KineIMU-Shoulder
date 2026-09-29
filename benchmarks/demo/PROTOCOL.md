# Benchmark protocol

Current collector: `m6-demo-benchmark/1.2`.
It creates and independently audits two fresh preflight demo runs outside the
timed slots, uses the bundled sample as its single input source, and archives the
actual current source rather than requiring an old experiment checkout.
One warmup and five timed workers retain the workload, timing boundary, numerical
budgets, thread settings, failure retention and statistics defined below.
The historical [report](REPORT.md) remains protocol 1.1 evidence; its results
are unchanged and must not be attributed to the current source.

## Historical measured protocol 1.1

# KineIMU Shoulder — M6 CP3 frozen benchmark protocol

Protocol `m6-demo-benchmark/1.1`, frozen before its formal measurement on 2026-09-28.
This implements the CP0 draft (preserved in the local historical archive) and
M6.3 acceptance (complete record retained in the local evidence archive). No speed threshold is imposed.
The source lock is the clean Git HEAD containing this protocol and runner, recorded
in each batch's `lock.json` before launching any child. Later evidence/state commits
do not change that measurement lock. Never resume or overwrite a consumed batch.

## Fixed workload and measurement

Use the unchanged CP1 sample `datasets/samples/m6_synthetic`: complete F90, AL90,
AR90 and T-MIX stored Q trajectories; eight node streams, 17,208 node-samples,
4,304 packets; 25 necessary files / 4,539,058 bytes (585,136 capture bytes).
Original digest-map SHA-256:
`2aa180e32003f91e57accf1d53c5b4b914e0c9e9c0ab4cdb22db02a3ab0964f9`.
No truncation, generated replacement, seed selection or exact-E workload.
Synthetic only, anatomical_eligible=false; sample INTERNAL ONLY / redistribution pending.

Primary `wall_ns`: parent `time.perf_counter_ns()` immediately before
`subprocess.Popen([sys.executable, benchmarks/demo/worker.py, --output, fresh_root])`,
ending immediately after `process.wait()` returns. Open stdout/stderr handles
before the boundary; preserve both original streams separately. `wall_s=wall_ns/1e9`.
Includes Python process startup/imports, hashing, read/decode/QC, calibration,
reconstruction checks, AHRS, explicit alignment/synchronization, M3/M4, existing
oracle/error calculations, summary and product/hash writes. Excludes uv launcher,
dependency installation, parent environment probes, independent audit and statistics.
Child run.json duration is auxiliary bookkeeping and is not this measurement.
The thin worker writes interpreter PID/parent PID/environment before executing
the unchanged Demo via runpy; that bootstrap overhead is included. Windows venv
python.exe is a redirector: record launch PID separately from worker PID, and
require the worker to be the launched process or its direct child. The pre-lock
diagnostic is retained in experiments/M6_CP3_20260928/pid-diagnosis.log.
Sidecar path is derived from output.parent/worker.json and is not an extra variable
OS argument. Record sys.orig_argv and bind its script/arguments to the launch.
Version1.0 added a variable --identity path that failed the original CP2 command
whitelist even though all numerical products matched. Its complete six-slot batch
remains FAIL, with raw times and withheld successful statistics in
failed diagnosis (complete record retained in the local evidence archive).
Version1.1 changes only sidecar argument plumbing; workload/timing/correctness
budgets and the original CP2 variation whitelist remain unchanged. Never resume1.0.

`compute_s=NOT MEASURED`: the exporter interleaves production and oracle work;
no pure production boundary is available. Do not subtract an estimated overhead
or add production timing hooks. Algorithms, tolerances, dependencies, sensor
schema and hardware remain unchanged.

## Schedule, environment and preflight

Before timing: clean tracked source; Python 3.12.14; installed frozen uv.lock
environment with uv 0.12.5. Record protocol/runner/source/lock/contract hashes and
archive the exact executed source bytes. Record all installed distribution versions,
Python executable/hash, OS/build/architecture, CPU model/physical/logical cores,
memory, storage/disk availability, active power scheme and background process
snapshots before/after. Preserve raw probe command/output/exit; unavailable facts
remain unavailable. NumPy build/BLAS configuration is recorded; live threadpool
identity is unavailable without an extra dependency. Do not add that dependency.

Every Python child gets OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1
before imports and has KINEIMU_M1_RAW_ROOT removed. Keep ordinary desktop conditions;
no exclusive CPU reservation, cache flush or frequency/thermal control. This is a
warm OS cache experiment with fresh processes and AHRS, not cold disk measurement.

Run the retained CP2 pair's independent audit before any benchmark child. Failure
records all six slots NOT RUN. Then execute one complete `warmup`, independently
audit it, and sequentially execute exactly `timed01` through `timed05`, each with
a new Python process and output root. Warmup failure blocks all timed slots.
Any timed failure is retained; continue the remaining scheduled slots, with no
replacement or extra repeats. Unexpected launch/audit exceptions remain FAIL.
Record all commands, cwd, UTC bounds, monotonic ns bounds, PID, exit and log hashes.
Parent-controlled output roots are outside the repository so nested Demo children
satisfy existing source/evidence guards. This resolves the draft's output-location
choice; the workload, schedule and timing boundary are unchanged.

## Correctness and acceptance

Post-wait audit is outside timing. Use the unchanged independent
`validation/auditors/demo.py`, which calls the frozen M5 CP3 numerical
oracle. Warmup uses `audit_run`; each timed child uses `audit_pair(warmup, child)`.
Check exit0, complete four-Q stage, worker/source identity, 25-input before/after
hashes, all output membership/checksums, calibration/frames/AHRS, QC/timing,
counts/support/null/reasons/evidence labels and original numerical budgets.
Pair checks enforce 22 canonical products, inner indexes and summary equality,
all 24 other top product hashes and the exact CP2 run-field variation whitelist.
The independent auditor recomputes 27,160 error scalars per child. Worker sidecar
PID must equal run.json PID; its launch/parent relationship is independently recorded.

Preserve full six Demo roots and all audits/logs. Sample and original CP1 inputs
must match before/after; source hashes, HEAD and tracked-clean state must remain
unchanged. Batch inventory hashes every retained file except itself and caches.
Any failed slot, gate, identity, checksum, input/source mutation or missing repeat
makes CP3 FAIL. Successful-performance statistics are withheld on failure.
No outlier deletion, fastest-only selection or reclassification of a failed batch.
Any correction requires a new committed source lock and a new batch; preserve the
failed batch. Protocol-semantic changes require a new protocol version.

## Statistics and reproducibility

Successful batch: exclude warmup; use all five timed attempts. Median is the third
sorted value; min/max are endpoints. Optional end-to-end rate for each attempt is
`node_samples_per_s=17208/(wall_ns/1e9)`; summarize those five individual rates by
median/min/max. No confidence interval from five repeats. This rate includes
validation and I/O overhead and is not live throughput, real-time latency, a
real-time factor or pure algorithm speed. The four timelines are separate exercises.

Retain raw integer ns, derived s/rates including failures, environments, commands,
inputs, source ZIP, product hashes and independent audit results. REPORT.md must
identify exact source/batch/inventory/platform and derive every performance value
from attempts.json. Rounded presentation uses six decimal places; JSON retains
full precision. Windows is measured separately; Linux remains NOT RUN unless
actually executed. CI configuration is not execution evidence.

Setup from clone root (installation outside timing):

```powershell
uv sync --extra analysis --frozen
# Use an absent external root; this batch becomes immutable once launched.
uv run --frozen python benchmarks/demo/run_benchmark.py --output "$env:TEMP/kineimu-m6-cp3-batch-01"
# Recompute with a NEW output outside the frozen batch, including independent numerical audit.
uv run --frozen python benchmarks/demo/run_benchmark.py --recompute "$env:TEMP/kineimu-m6-cp3-batch-01" --output recomputed-cp3-01.json
```

`--recompute` verifies full membership/bytes, ZIP/source/input binding, raw counter
difference, launch/worker identity, logs, original audits and re-executed numerical
audits, then derives summary from raw ns and compares the retained summary. It
writes only the new result file. Repository evidence copies must be exact-byte
copies of the original batch. Frozen SHA256SUMS.json is not updated for later
state/proof records. No publication, hardware or human-subject work is implied.
