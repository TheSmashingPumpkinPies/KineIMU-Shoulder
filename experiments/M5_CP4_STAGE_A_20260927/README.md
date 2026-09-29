# M5.4 stage A — development entry and evidence-gate delivery

Date: 2026-09-27. Branch: `main`. Baseline:
`ad76ace2713136e3044d2664a9f34376f15d4986`.
This is a stage A tool/test delivery, **not CP4 replay acceptance**.
CP0–CP3 retain acceptance; CP4/CP5 and overall M5 remain OPEN.

The [entry inventory and requirement mapping](../../docs/M5_REPLAY_ENTRY.md)
describes the six required future sessions, eleven node streams, interfaces,
independent anchors, development report and missing-evidence tests. The new
`kineimu_shoulder.validation.replay` module provides an explicit CLI, safe fresh
output claim, complete input decode/QC, original counters/time, pinned source/
node/count/endpoint checks, before/after hash and partial report inventory.
Its entry success cannot become full-chain success: NOT RUN, checkpoint OPEN,
exit 2. Input failure is exit 1; unavailable input/access is BLOCKED/exit 2.
There is no stage A formal mode or exit-0 path.

`gate_report` calls actual M2/M3/M4 stages from explicit aligned synthetic
streams. Isolated missing clock/heading/alignment/drift survives to serialized
records and final summary with null numeric values and exact stage reasons.
Supported synthetic control has the independent frozen F1 three-cycle result.
No production algorithm/backend, raw/schema, truth/seed/gate or hardware change.
This segment runs no formal long recorded replay or new acquisition.

## Verification evidence

| Check | Observed result |
|---|---|
| Initial test-first stage A suite | 21 missing-runner assertion failures, then 21 passed |
| Source label and CLI additions | Two expected failures before implementation; expanded 25 passed |
| Output source-tree/order/canonical controls | 29 passed before the final acquisition-root refinement |
| Acquisition-root sibling guard | Test copy reproduced unsafe allowed path; one failing test, then one passing test after protecting the complete source root |
| Final complete project suite | [full-pytest.log](full-pytest.log): 659 passed, 2 external-M1-data skipped in 396.38 s |

The initial sandbox-only attempt failed with the known pytest Windows temp
WinError 5. Fresh normal-permission basetemps were used. The superseded full
attempt `.tmp-m54-a-full1` was stopped after the path refinement, with its log
and partial products retained; it is not a passing verification run. Final full
command used `.tmp-m54-a-full-final`. The two external skips do not pass CP4.
Detailed final focused/static/docs checks and artifact/source hashes are stored
in `verification.json` alongside the final focused log.
The delivered operational logs are LF-normalized copies for the repository's
text policy; original temp logs are unchanged and their original hashes are
recorded separately. Recorded source/lock/log hashes match staged Git bytes.

```powershell
.venv/Scripts/python.exe -m pytest tests/integration/test_m5_replay_entry.py --basetemp <new-focused-temp> --tb=short -q
.venv/Scripts/python.exe -m pytest --basetemp <new-full-temp> --tb=short -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m mypy --strict kineimu_shoulder
.venv/Scripts/python.exe scripts/check_docs_consistency.py
git diff --check
```

Development fixture/output directories under `.tmp-m54-a-*` remain local and
are not immutable formal CP4 evidence. The full-suite process handle was no
longer available after the interruption in the conversation; the retained
complete pytest summary is the full-suite outcome record, rather than a
fabricated captured process exit code. Final focused exit is captured normally.

Next stage B: test-first read complete retained CP1 F90/AL90/AR90/T-MIX A/B
Q files, independently bind metadata/labels/digests, then connect processing/1.1
calibration, explicit transforms/maps/grid, pinned AHRS and independent errors.
Do not substitute generated Q files or in-memory truth for actual stored replay.
C/D actual node AHRS/unavailable reports, D/E external 11-file pre/post inventory,
and E clean source lock/two-process canonical audit remain required.
Stop after stage A; no push, CP5 closeout or physical hardware action.

Resolve this implementation/evidence commit with
`git log -1 --format=%H -- kineimu_shoulder/validation/replay.py`.
The following dynamic-state commit records that exact source anchor.
