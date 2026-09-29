# CP4 E2 — fresh-stage assembly after preserved entry failure

Continuation: 2026-09-28. Original E1 source lock
`f2e0d5d6a2d327ec5aeb3842172320a142fad5f7` failed before B processing because
the envelope had created an experiment tree before invoking exporters inside
it. Their existing immutable-evidence guard correctly rejected that destination.
No B/C/D numerical work or CP4 audit ran in E1; run2 was NOT RUN.

The original root `experiments/M5_CP4_FORMAL_20260927` is consumed and immutable.
Original commands/exits/source lock, unchanged raw snapshots, full partial map
and exact source ZIP remain in `experiments/M5_CP4_STAGE_E_20260927`.

The test-first E2 correction changes collection assembly only. Each unchanged
B/C/D exporter writes into a fresh owned staging directory outside experiments.
On completion that fresh stage is moved into the owned E collection. Existing
raw/source/experiment protection is still exercised and unchanged. The staging
directory and process identity are operational data, excluded from canonical
bytes. Never move or overwrite a pre-existing evidence tree.

Scope of reacceptance: all E guards, complete original Node B assembly regression,
focused B/C/D/external-M1 tests, full Python checks, two new complete formal
collections, identical canonical support, complete original hashes and all
six independent numerical audits. No calibration/backend/production/truth/
seed/threshold/raw/public schema changes; D retains ADR-011 segmentation.

Fresh roots frozen before launch:
`experiments/M5_CP4_FORMAL2_20260928/run1` and `run2`, both absent. Tools and new
evidence are in [E2 evidence](../experiments/M5_CP4_STAGE_E2_20260928/README.md).
The [original E requirement mapping](M5_FORMAL_REPLAY.md) and B/C/D subreport
semantics remain active. E2 is a new complete attempt, never reclassification
of the E1 failure. CP4 stays OPEN pending audit; CP5 remains separate.
