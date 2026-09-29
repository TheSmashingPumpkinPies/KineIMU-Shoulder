# M5.3 CP3 processing/1.1 reacceptance — PASSED

User authorized revised processing and complete reacceptance on 2026-09-27;
see [ADR-010](../../docs/adr/ADR-010-explicit-short-gap-reconstruction.md) and
[processing contract](../../protocols/M5_PROCESSING_V1_1.md). Every frozen
raw input, truth, seed and numerical gate remains unchanged. The independent
[corner support proof](corner-support-proof.json) explains the need for an
explicit observable-transition reconstruction stage. Pinned AHRS is unchanged.

Both formal1/run1 and run2 pass 1,142/1,142 cases, zero failed/not-run.
589 working-domain cases have 100% relative coverage/recall and zero false or
missed repetitions; 297 stress diagnostics do not assert accuracy acceptance.
All previous 46 failures pass. [Full result table](CP3_all_cases.csv),
[previous failures](CP3_resolved_failures.csv), [summary](CP3_resolution_summary.json).

Independent [audit](formal1-audit.json): 5,380 canonical files and
1,984,934,060 bytes/run, 13,844,981 recomputed error scalars/run;
all product bytes identical. The auditor separately checks scalar truth,
coverage/retention denominators, reconstructed knot observability/force/rates,
original-row conservation, evidence references and source/product hashes.

Source/tool lock `01c4e23bd82bcbec6ae775bf6db6c67471fa6ac3`; both launch manifests formal=true and
tracked_dirty=false with the same 86-file source map. Exact launch source bytes
are retained in [source-lock-01c4e23.zip](source-lock-01c4e23.zip), SHA256
`bad69498250d231c3768055e8fcdcc2c0abee4ff1ba0b073844f466fb0f300de`.
[Source-byte retention](source-byte-retention.json) explains Git line-ending
normalization and verifies each snapshot member against both launch manifests.

Run from the source-lock checkout using the original pinned Python environment,
with PYTHONPATH set to the checkout. Set OPENBLAS_NUM_THREADS=1,
OMP_NUM_THREADS=1, MKL_NUM_THREADS=1 **before imports** (all captured in manifest).
Two independent commands, each with three workers, six workers total:

```text
python examples/m5_perturbation.py --output experiments/M5_CP3_UNBLOCK_20260927/formal1/run1 --workers 3
python examples/m5_perturbation.py --output experiments/M5_CP3_UNBLOCK_20260927/formal1/run2 --workers 3
python experiments/M5_CP3_20260926/audit.py --root experiments/M5_CP3_UNBLOCK_20260927/formal1 --output experiments/M5_CP3_UNBLOCK_20260927/formal1-audit.json
```

Never reuse existing roots. The 1,064 numerical/evidence sessions plus 78
frozen-fixture cases form the complete 1,142-case report. Fixture assertions
are recorded separately; operational pytest scratch is excluded from canonical
inventories and Git. Full tests: 629 passed, two external M1-data skips;
Ruff, strict mypy 26 source files, document consistency and whitespace pass.

Old [formal4 and partial roots](../M5_CP3_20260926/README.md) stay immutable.
[Development attempt inventories](development-attempts.json) retain failed
provenance comparison: both 46-case runs passed with identical error bytes,
but changed processing provenance correctly prevented formal acceptance.
Only this clean-lock complete formal1 pair accepts CP3.

CP4/CP5 and overall M5 remain OPEN. This is finite synthetic validation with
explicit reconstruction assumptions, not anatomical/clinical validation or
real-replay acceptance. Hardware remains frozen.


## Committed-byte retention

Exact retained-evidence commit: `739714f3d0363478f78bf94ef5ece58bd9071371`.
Retained-byte verification PASSED: both 5,380-file Git product maps equal and
match audited disk bytes. All 56 raw capture hashes/run equal old formal4;
frozen contract/truth/manifest hashes unchanged. Exact source ZIP matches Git.
See experiments/M5_CP3_UNBLOCK_20260927/committed-evidence.json.

[Retention proof](committed-evidence.json). For exact-byte reproduction,
restore all 86 source ZIP members over the source-lock checkout before the
commands above; Git normalization otherwise changes launch source hashes.
