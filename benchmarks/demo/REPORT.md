# KineIMU Shoulder — M6.3 end-to-end performance report

2026-09-28 / Windows measurement and required repository verification gates PASS.
Exact committed-byte proof is generated after the frozen delivery commit in
`experiments/M6_CP3_20260928/committed-evidence.json`; delivery/source identities
are distinct. Dynamic state records final CP3 acceptance after that proof.

Protocol: [m6-demo-benchmark/1.1](PROTOCOL.md). Measurement source lock: `3e0647c4f53803abf134fee68659f63ca006e407`.
Formal run: batch03; repository exact-byte delivery copy: [batch01](../../experiments/M6_CP3_20260928/batch01/summary.json). Earlier invocations/failed1.0 results remain separate and are not replacement repeats.
Frozen batch inventory SHA-256: `8c60adc45de79f654db9cbac9d664b39885ca6355e784c6648688fd0056aa708`;203 retained files including the index itself.

## Measured scope

Complete F90/AL90/AR90/T-MIX stored synthetic sensor replay;8 node streams,17,208 node-samples and4,304 packets per child. Required input25 files/4,539,058 bytes (585,136 capture bytes). Original input map SHA-256: `2aa180e32003f91e57accf1d53c5b4b914e0c9e9c0ab4cdb22db02a3ab0964f9`.
Parent perf_counter_ns immediately before Python worker Popen / immediately after wait. Includes Python/identity bootstrap/imports, hashes, input/decode/QC, calibration/AHRS, explicit alignment/synchronization, M3/M4, existing oracle/errors, report and product writes. Excludes uv/installation and parent environment/audit/statistics work. Pure production compute_s=NOT MEASURED. No estimated overhead subtraction.
One warmup and five sequential timed processes; fresh AHRS/output roots; no cache flush. Warm OS cache, ordinary desktop background, no exclusive CPU isolation. Reported rate is serial four-trajectory end-to-end processing rate including validation/I/O; no live throughput, real-time factor/latency or pure algorithm-speed claim.

## All scheduled results

[Raw attempts](../../experiments/M6_CP3_20260928/batch01/attempts.json) retain integer counter bounds, ns, full-precision s/rates, commands, launcher/worker identity, exits, logs and audits.

| Slot | wall_ns | wall_s | node-samples/s | Exit / correctness | Statistical use |
|---|---:|---:|---:|---|---|
| warmup | 82647692600 | 82.647693 | 208.209080 | 0 / PASS | excluded warmup |
| timed01 | 89574702300 | 89.574702 | 192.107811 | 0 / PASS | included |
| timed02 | 87636487600 | 87.636488 | 196.356569 | 0 / PASS | included |
| timed03 | 66313346900 | 66.313347 | 259.495272 | 0 / PASS | included |
| timed04 | 69773775800 | 69.773776 | 246.625610 | 0 / PASS | included |
| timed05 | 63186371100 | 63.186371 | 272.337210 | 0 / PASS | included |

| Five timed attempts | Median | Min | Max |
|---|---:|---:|---:|
| End-to-end wall_s | 69.773776 | 63.186371 | 89.574702 |
| End-to-end node-samples/s | 246.625610 | 192.107811 | 272.337210 |

wall_s=wall_ns/1e9; rate=17208/(wall_ns/1e9), individually per attempt. Median is the third sorted value; min/max are endpoints of all five. Warmup is excluded; no outlier dropped, fastest-only selection, failed-slot replacement or confidence interval. All displayed performance numbers use six decimals; JSON retains full precision. The observed min/max describe this five-repeat desktop batch; frequency/thermal state was not measured, so no cause of variation is claimed.

## Machine and runtime

- OS: Microsoft Windows 11 家庭版 中文版; build `26200`; architecture `AMD64`.
- CPU: AMD Ryzen 7 7735H with Radeon Graphics; 8 physical / 16 logical cores.
- OS-reported physical memory: 16369221632 bytes; free memory before: 4020252 KiB. After snapshot retained separately.
- Power: `电源方案 GUID: 27fa6203-3987-4dcc-918d-748559d549ec  (Performance)` (observed scheme, not measured effective frequency).
- Python3.12.14; uv0.12.5; NumPy2.5.2, SciPy1.18.1, pandas3.0.5, imufusion1.3.3, imucal2.6.0.
- OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1 before each child imports; external M1 root removed. These are configured limits; live threadpool size is unavailable.
- C: external temp storage, D: source checkout; disk model/media/free space, Python executable/hash, all installed distribution versions, raw probe command/output/exit and background process snapshots are in the environment records. NumPy build/BLAS configuration retained; live threadpool identity unavailable. The optional PyYAML formatting warning is preserved; no dependency added.

[Environment before](../../experiments/M6_CP3_20260928/batch01/environment-before.json) · [environment after](../../experiments/M6_CP3_20260928/batch01/environment-after.json) · [source/input/runtime lock](../../experiments/M6_CP3_20260928/batch01/lock.json).

## Correctness and provenance

All six children exit0 and pass existing numerical/QC/support/labels/coordinate/time/count gates. Independent audit recomputes27,160 error scalars per child; each trajectory3 valid repetitions, missed=false=0, relative/recall/proxy coverage1. Each timed pair with warmup has22 canonical products, summary and inner index equal,24 other top hashes equal, and all non-whitelisted run fields equal. Original37 and sample28 files unchanged. All54 source ZIP members verified; source HEAD/tracked cleanliness and byte hashes match before/after. No code/tests edited during successful batch03.
Original and retained copies each underwent a fresh independent full numerical/counter/checksum audit; their recomputation JSON is identical. The independent report-values check uses exact rational arithmetic and independently sorted values, comparing floating output within two ULPs solely for arithmetic rounding, not a changed scientific tolerance.

[Original recompute](../../experiments/M6_CP3_20260928/original-recompute.json) · [retained recompute](../../experiments/M6_CP3_20260928/retained-recompute.json) · [independent displayed-value audit](../../experiments/M6_CP3_20260928/report-values-audit.json).

## Prior failures and limits

Preflight batch01 at1e6f98b4: uv absent from Python PATH, output root/children never created, six slots NOT RUN. Protocol1.0 batch02 ataddcdd7f: all six measured, numerical products equal; five timed comparisons FAIL because --identity varied in actual sys.orig_argv. Successful statistics remain null. Original203-file failed root/copy/source/commands/times/logs remain. Its diagnosis also records a brief test-only draft edit/restoration; it is not clean-source acceptance. Protocol1.1 changes only output-derived sidecar argument plumbing and binds actual argv; original CP2 whitelist and scientific gates unchanged. This report uses only the complete separately committed protocol1.1 batch.
[Preflight rejection](../../experiments/M6_CP3_20260928/preflight-rejection-batch01.json) · [failed batch](../../experiments/M6_CP3_20260928/failed-batch02/summary.json) · [failed diagnosis](../../experiments/M6_CP3_20260928/failed-diagnosis.json).

First full regression invocation used a repository-local pytest basetemp, producing868 pass/6 existing Demo guard failures. All48 CP2/CP3 tests passed with external temp, then23 final CP3 regressions passed. The final external-temp retry passed all878 tests with the actual external M1 root and zero skips. Ruff, strict package mypy33 plus runner1, docs/39 archive hashes/whitespace and pinned sdist/wheel build pass. Exact commands/exits/raw logs are retained; committed-byte proof is a separate post-delivery record. Other failed test/type/build/doc attempts are retained.
Synthetic/humerothoracic research only, anatomical_eligible=false, sample INTERNAL ONLY pending redistribution. No anatomical/clinical/glenohumeral/scapular accuracy claim. Static gravity does not establish full heading. Hardware frozen; no acquisition. Linux NOT RUN; CP4/CP5 and overall M6 remain OPEN. The unchanged Demo retains historical CP2 limitation text; new benchmark acceptance is defined by this separate protocol/evidence/report.

## Recompute

From clone root with frozen dependencies; use a NEW audit output:

```powershell
uv run --frozen python benchmarks/demo/run_benchmark.py --recompute experiments/M6_CP3_20260928/batch01 --output recomputed-cp3-new.json
```

This verifies complete bytes/membership, input/source ZIP binding, every counter delta, worker/command/logs, original and freshly re-executed numerical audits, then derives statistics from raw ns and compares summary. Only the new audit file is written. See [reproduction guide](REPRODUCE.md) for setup, fresh timing and failure retention.
