# M4.5 / CP5 — deterministic integration and acceptance

Date: 2026-09-26 (Asia/Shanghai). Branch: `main`.
Integration scope: exact post-alignment synthetic M2.4 → M3 → M4.
No sensor calibration/AHRS, physical anatomy or clinical validation is claimed.
M4 numerical production algorithms are unchanged by this checkpoint.

## Acceptance disposition

The [example](../../examples/m4_dual_synthetic.py) constructs the frozen
[A/B and T4 truths](../../tests/fixtures/M4_KNOWN_EXERCISES.md), with explicit
A/B offset maps, common heading and synthetic alignment. Five sessions cover
flexion, left/right abduction, wrong-plane exclusion and a later B-only flexion
comparison. M2.4 relative orientation, M3 elevation/speed, M4 segmentation,
metrics, explicit common-grid thorax preparation, proxy, summaries and
comparison execute through the existing production APIs.

Two independent runs in the frozen environment produced identical bytes in
all three outputs. 169 independently expected error rows pass: angle/speed
1e-10 rad/rad/s, duration/CV/cadence 1e-12 in their respective units; integer
counts and time boundaries exactly. The [integration test](../../tests/integration/test_m4_synthetic_pipeline.py)
also compares independent processes with different `PYTHONHASHSEED`, verifies
canonical encoding, content hashes, SI/null values, original QC/interpolation,
counts/exclusion reasons, numerical truths, comparison and overwrite refusal.

M4.0–M4.5 / CP0–CP5 are accepted at synthetic numerical/evidence scope after
the final project verification below passed. M5 remains the separate controlled
noise, bias, jitter, loss, drift and recorded-replay robustness milestone.
Hardware remains frozen and the M1 pair remains ineligible for anatomical
output without supported pairwise clock, common heading and measured alignment.

## Frozen environment and exact commands

CPython3.12.14; uv0.12.5; NumPy2.5.2; SciPy1.18.1; pandas3.0.5.
The pinned dev tools are pytest9.1.1, Ruff0.16.6 and mypy2.3.1.
The installed uv was outside the shell PATH; its absolute path was used to
verify and synchronize the lock offline. Normal filesystem permissions were
needed to read the existing uv cache. Only the local editable project was
rebuilt; dependency pins and `uv.lock` did not change.

```powershell
& uv --version
& uv sync --all-extras --frozen --offline
.venv/Scripts/python.exe examples/m4_dual_synthetic.py --output-dir experiments/M4_CP5_20260926/run1
.venv/Scripts/python.exe examples/m4_dual_synthetic.py --output-dir experiments/M4_CP5_20260926/run2
.venv/Scripts/python.exe -c "from pathlib import Path; r=Path('experiments/M4_CP5_20260926'); a={p.name:p.read_bytes() for p in (r/'run1').iterdir()}; b={p.name:p.read_bytes() for p in (r/'run2').iterdir()}; assert a==b"
```

Destinations must not exist. Reproduce into new directories; preserve these
retained artifacts. Locked environments on other platforms need their own
two-run proof; these hashes are for the recorded Windows environment.
JSON has UTF-8, sorted keys, compact separators, one LF, strict finite/null
encoding. `report.json` hashes processed/derived; its own digest is external.

| Output (same in run1 and run2) | Bytes | SHA-256 |
|---|---:|---|
| processed.json | 138261 | bfde8669a77beb855f228cb83b8388049734c60ff087d67070fb056179e68759 |
| derived.json | 117489 | 4e2ab094c3c8b23a321d188dd09da4b367f0fc41ff06d8e7f0ba7ab2fc03be8c |
| report.json | 31436 | 7dc94615f7a6e522775c60f40ccfbbeada8d8e3573c348d78676a2436e048375 |

Read processed (complete record retained in the local evidence archive), derived (complete record retained in the local evidence archive) and
acceptance JSON (complete record retained in the local evidence archive); [usage/export documentation](../M6_TECHNICAL_REPORT.md)
describes the batch envelope and content addressing. The report retains each
source/input hash, processing-file hash and complete threshold configuration.

| Identity | SHA-256 |
|---|---|
| uv.lock | ff2893aaa21f7ec97dfe487ca4c0e80af18d45e1293e47e28cd696feaf8d7c3e |
| processing file-hash map | 2af0522a5d0cd8b7f7b05cb64da89c29841f5c6889c16e84d159f05acbf030ef |
| frozen contract | 9b9cb01245451557e31515110502d48d05877fb5d666affdc603b1ebcc42587f |
| reviewed CP0 A/B/T4 truth | 7ecccadea01033101ea4245f8328e849cfa0aade0c59d7798ce0995322bcc4f9 |
| ExerciseConfig | 08d448dad1c977fa24fb68bd971993df4914c8ad01f345b471cc1e148337760d |

## Independent numerical results

A has80° ROM/peak, [0.2,2.2] s, earliest peak0.8 s, rise0.6 s, hold0.6 s,
return0.8 s; mean/max3-D speed70/100°/s. B has60° ROM/peak,
[3.2,4.8] s, earliest peak3.6 s, rise0.4 s, hold0.6 s, return0.6 s;
mean/max speed62.5/100°/s. All moving phase means/maxima are100°/s;
hold means/maxima are0. SI conversion is explicitly pi/180.

A+B ROM mean70°, sample SD10sqrt(2)°, CVsqrt(2)/7, active duration3.6 s,
active cadence5/9 s^-1. Each T4 proxy has extension20°, lateral10°, axial30°
relative to its movement-start baseline. Wrong-plane session retains two
excluded envelopes with null metrics and plane_mismatch. Later B-only mean60°
minus earlier70° is -10° with both n; this is a descriptive difference.

| Error family | Observed maximum absolute error | Acceptance tolerance |
|---|---:|---:|
| angles/ROM/proxy/SD | 2.220446049250313e-16 rad | 1e-10 rad |
| speed | 2.4424906541753444e-15 rad/s | 1e-10 rad/s |
| durations | 0 s | 1e-12 s |
| CV | 1.6653345369377348e-16 | 1e-12 |
| cadence | 0 s^-1 | 1e-12 s^-1 |
| counts/boundaries | 0 | exact |

No direct-input tolerance was substituted for AHRS accuracy. The example
starts at exact segment orientation; backend sensor/AHRS and perturbation
validation remain their documented independent gates.

## Test-first and verification record

Initial focused red run failed because the CP5 example did not exist. A
sandbox run first reproduced WinError5 accessing pytest's own basetemp;
normal-permission red/green runs resolved that environmental failure.
The first integration exposed incorrect source-hash file paths (frames and
shoulder are packages), then a T4 source-construction mistake: thorax began
returning during the arm plateau, causing floating-point cancellation to
select a later maximum. Holding thorax constant throughout the frozen plateau
restored the exact earliest-peak assertion without modifying production rules,
thresholds or oracle rows. A second red cycle caught absent exact count/time
error rows in the report; adding these gates produced green.

```powershell
.venv/Scripts/python.exe -m pytest tests/integration/test_m4_synthetic_pipeline.py -q --tb=short --basetemp .tmp-m45-final-focused-approved
.venv/Scripts/python.exe -m pytest --basetemp .tmp-m45-full-approved-20260926 --tb=short
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m mypy --strict kineimu_shoulder
.venv/Scripts/python.exe scripts/check_docs_consistency.py
git diff --check
```

Final focused1 passed; final full557 passed/2 skipped in52.53 s, exit0.
Ruff passed with normal permissions (no traversal warnings); strict mypy
passed18 source files. Docs consistency passed172 accessible Markdown files
in the sandbox and800 with normal permissions,39 immutable archive hashes,
0 errors. Counts include pre-existing scratch Markdown under normal
permissions. Whitespace checks passed. No source/test/lock changes followed
the final full run; state/docs were checked again before closeout commits.
The initial full run had556 passed/2 skipped and one docs-link failure because
the newly linked acceptance report was still being written. After creating
the report and confirming links, the complete rerun passed. Two external M1
replay tests require KINEIMU_M1_RAW_ROOT and are skipped when it is absent.
No hardware/firmware, raw/public acquisition schema, dependency or M2/M3
interface changed. The exact implementation commit is recorded in
[HANDOFF.md — historical availability](../PUBLIC_AUDIT.md#not-distributed-in-this-source-snapshot); content identity is recorded above.

## Exact next action

Start M5 by drafting its controlled perturbation and recorded-replay validation
plan against the accepted M2/M3/M4 contracts. Fix independent truths,
uncertainty/evidence boundaries and acceptance gates before new numerical
validation work. No physical acquisition or hardware reopening is needed.

Public-export note: unavailable internal navigation is redirected to the evidence-availability index; scientific claims and original target names are retained by the export record.
