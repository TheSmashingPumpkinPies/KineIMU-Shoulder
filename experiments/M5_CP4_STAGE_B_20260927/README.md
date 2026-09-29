# M5.4 stage B — complete stored dual-node synthetic replay

Stage B delivered at development scope, 4/4 trajectories passed. CP4/CP5 and
overall M5 remain OPEN; C/D/E have not run. Source/tool lock `1da000de1b0652379504572479dc40c993f18696`.
Clean tracked launch, `formal=false`, processing/1.1. Hardware remains frozen.

Eight immutable CP1 run1 KIMU files are replayed completely: 538 packets and
2,151 samples per node, 0–21.5 s, original counters/endpoints retained. Every
trajectory has three valid repetitions, zero missed/false and full relative,
proxy and recall coverage. All frozen clean S/Q gates pass, including input
half-LSB bounds and initialization at 0/5 s. Numerical sources/metadata/labels
and their independently pinned digest map are unchanged before/after reads.

Measured error maxima below derive from retained per-scalar independent errors,
not hardware accuracy or timing benchmarks. Node gates 0.4 degrees, elevation
1 degree, interval speed 2 degrees/s remain unchanged.

| Trajectory | A orientation (deg) | B orientation (deg) | Elevation (deg) | Interval speed (deg/s) |
|---|---:|---:|---:|---:|
| F90 | 0.00000000 | 0.32449483 | 0.32449483 | 0.37298254 |
| AL90 | 0.00000000 | 0.32447197 | 0.32447197 | 0.37292149 |
| AR90 | 0.00000000 | 0.32447197 | 0.32447197 | 0.37292149 |
| T-MIX | 0.03702481 | 0.35199120 | 0.31627717 | 0.36753874 |

[Canonical demo report](../M5_CP4_STAGE_B_DEMO_20260927_02/report.json),
[launch manifest](../M5_CP4_STAGE_B_DEMO_20260927_02/manifest.json),
[independent audit](audit.json), [verification and exact-source map](verification.json).
The audit checks all 22 products and independently recomputes
27160 error scalars, complete denominators,
observed geodesics, O/F/T expectations, original-row conservation, count-to-SI
conversion, R_NS/R_NK application, source hashes and all required files.
It reuses the independently retained CP3 auditor; no production pipeline runs
during audit. Integration corruption control rejects modified test errors.

Full pytest 672 passed/2 external-M1-data skips (695.64 s), captured
exit0 at source 00b8ca1723e45ec6f4278d77985c6613f523997a. After correcting only
the audit's sensor/node SI assumption and docs, all 14 stage B tests pass;
production/numerical runner bytes are unchanged. Ruff, strict mypy28, docs and
whitespace freshly pass. Preliminary focused48 passed before final additive
report/source checks. Earlier sandbox pytest hit known WinError5; normal Windows
permissions and fresh basetemps were used, with no code workaround. Exact logs
are LF-normalized for Git, with original and retained hashes in verification.json.
Test-first red milestones are also recorded there. [Source byte snapshot](source-lock-1da000de.zip)
preserves every launch-hashed file, independently of Git line-ending normalization.

Reproduce from the source lock (restore snapshot bytes where needed), with
OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1 before imports:

```powershell
.venv/Scripts/python.exe -m kineimu_shoulder.validation.stored_demo --output <new-development-root>
.venv/Scripts/python.exe experiments/M5_CP4_STAGE_B_20260927/audit.py <new-development-root> <new-audit.json>
```

Both recorded standalone commands exited0. Never reuse the retained root or
audit file. Source snapshot, checks, complete products and input evidence stay
immutable. All product digests are in SHA256SUMS.txt, excluding itself.
No generator/packet writer/continuous q-truth substitutes for observed replay.
Source lineage, transform/clock/heading construction and evidence limitations
are explicit. No raw, production/backend, public schema, truth/seed/gate or
hardware change. No acquisition or remote publication. Next segment is C,
complete retained Node B and honest downstream unavailable evidence.

The first demo's numerical cases passed but its independent SI-frame audit
failed. [Original attempt inventory/source lock](attempt1.json) and audit log
remain immutable, including all 23 original files. The corrected audit checks
sensor SI before calibration and node SI after R_NS; no data or gate changed.
The successful new source lock used a new _02 root and never repaired attempt1.
