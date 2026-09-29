# CP4 audit correction — preserve both complete E2 numerical runs

2026-09-28: both independent E2 B/C/D collections at source lock
`a72bdd18dd3567bb3b043c4cd6c75b16b7311cf9` returned exit0. The pair auditor
failed before numerical audits because it compared `Popen.pid` (the Windows
venv redirector) to `os.getpid()` (the actual Python worker). E2 launch PIDs
31524/7288 and worker PIDs26936/22476 are retained separately in unchanged
execution/operation records. They are two complete independent workers.

An independent real-subprocess probe reproduces the redirector/child hierarchy
with `os.getppid()`. Test-first guards require positive, distinct actual worker
IDs, distinct launcher IDs and successful executions. A failed execution or
duplicate actual worker still fails. No identity field is edited or invented
for the completed formal runs.

Correction scope: independent auditing only. E3 reads unchanged E2 products,
source ZIP, commands, source lock, input/output hashes and operation records.
It separates launcher and worker IDs, verifies the original numerical source
map against both current disk and exact source-lock Git blobs, and records a
separate committed audit-tool lock and exact tool ZIP. All canonical outputs,
original E2 source/tools and failed audit/log/report remain immutable.

Reacceptance requires the actual runtime hierarchy probe, identity/corruption
guards, required Ruff/mypy/docs/whitespace checks and all six complete B/C/D
independent audits plus canonical byte equality. The full762/no-skip and
focused103 source checks remain bound to the unchanged E2 numerical source;
new auditor tests are separate. No numerical tolerance, scientific evidence
gate, calibration, backend, raw, schema or accepted processing contract changes.
No additional collection is needed to correct this operational audit defect.
The same two complete collections must satisfy every original CP4 requirement.

The new audit is retained separately in
`experiments/M5_CP4_STAGE_E3_20260928`; it does not reclassify or overwrite
the original failed E2 auditor result. CP4 remains OPEN until the new complete
audit passes. CP5/overall M5/hardware work remain outside this segment.
