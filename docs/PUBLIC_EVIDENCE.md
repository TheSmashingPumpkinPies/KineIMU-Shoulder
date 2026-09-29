# Evidence availability

This curated repository contains the complete hardware-free Demo/sample, CP1
synthetic validation inputs, independent M1–M6 auditors needed by tests, selected
bench capture fixtures and the original six-slot M6 benchmark batch including its
raw counters, environment, logs, source ZIP and hashes. Failed benchmark attempts
remain distinguishable. These are research records, not human-subject validation.

## Historical acceptance and current candidate

[M1 acquisition report](../experiments/M1_DUAL_USB_30MIN_RESULT_20260925.md),
[M2 known-input/replay](../experiments/M2_REPLAY_20260925/README.md),
[M3](../experiments/M3_CP4_20260925/README.md), [M4](../experiments/M4_CP5_20260926/README.md),
[M5 coverage](../experiments/M5_CP5_20260928/COVERAGE.md),
[historical fresh-clone report](../experiments/M6_CP5_20260928/REPORT.md), and
[benchmark protocol/results](../benchmarks/demo/REPORT.md) describe their original
source identities. Their counts/claims are historical; current export verification
is separate in [PUBLIC_VERIFICATION.md](PUBLIC_VERIFICATION.md).

## Not distributed in this source snapshot

Full private task/handoff history, legacy project pack and StickS3, repeated multi-GB
M5 derived runs, full external30-minute acquisition root, local SDK/environment,
compiled firmware binaries and machine-local scratch are omitted. Smaller summaries
and scientific limitations remain. Historical links to unavailable internal artifacts
are replaced by this availability index with their original target retained in the
export change record; no missing evidence is reclassified as measured or passed.

The optional two full physical replay tests require a separately supplied immutable
M1 raw root. A fresh clone must show their expected skips and cannot claim those tests
ran. For full archived evidence, contact the maintainer through the repository; no
public downloadable archive is asserted here. Small board fixtures do not supply
pairwise timing/heading/anatomical alignment or clinical accuracy.

## Recompute historical performance

The original source ZIP in the retained benchmark is the exact executed54-member
source, not necessarily today's files. Use the reconstruction procedure in
[PUBLIC_BENCHMARK.md](PUBLIC_BENCHMARK.md); it keeps original hashes and counter gates.
Do not change old maps or splice new files into a historical measured source.

## Historical local packages

Two old locally built wheel/sdist pairs are not distributed. Their original archive/audit and failure reports remain historical evidence; no final package acceptance is inferred from them. Final packages are rebuilt and independently installed from the audited public source.
