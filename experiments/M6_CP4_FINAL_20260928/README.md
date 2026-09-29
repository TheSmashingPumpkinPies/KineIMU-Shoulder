> Public distribution note: the historical local package files are excluded; their audit results and failed attempts below remain the original historical records. Rebuild final packages from the reviewed public source.

# M6.4 / CP4 — licensed release packaging PASS

2026-09-28, Windows, version **0.1.0**. All maintainer decisions are accepted:
English README / Chinese technical report, original code/docs **MIT**,
Copyright (c) **2026 Hongbo Liao**, citation author **Hongbo Liao**, selected
original sample **CC0-1.0**, destination **TheSmashingPumpkinPies/kineimu-shoulder**.
Affiliation/ORCID omitted; no publication date/DOI is invented.
[ADR-012](../../docs/adr/ADR-012-release-documentation-and-license-selection.md)
and [review decisions](../../docs/release/REVIEW.md) record the authority.

## Accepted gates

[Acceptance audit](acceptance.json) binds actual commands, exits and log hashes.

| Gate | Final result / actual record |
|---|---|
| Citation | Official CFF1.2.0 complete schema, valid YAML and approved fields; [audit](citation-candidate-audit.json) |
| Environment | CPython3.12.14, uv0.12.5; all-extras frozen sync; dependency lock unchanged; [sync](sync-01.json) |
| Full regression | **879 passed / 0 failed / 0 skipped**, 810.53s; actual external M1 raw root; [record](full-02.json), [log](full-02.log) |
| Static checks | Ruff [final08](ruff-final-08.json), strict mypy33 files [record](mypy-fix-02.json) |
| Documentation | 1,278 Markdown / 39 immutable archive hashes / 0 errors at docs-final-04; [record](docs-final-04.json); closing docs checked separately |
| Build | Pinned sdist then wheel from sdist; [record](build-02.json) |
| Archives | 34 original package/typing inputs, 57 shared notice files, exact root notices/docs and approved metadata; [audit](archive-candidate-02.json) |
| Independent installs | Two fresh external venvs, hash-locked dependency wheels, no-deps project install, isolated actual analytical APIs/metadata/notices; **8 commands PASS**; [audit](installation-audit-candidate02.json) |
| Integrity |25 original sample inputs, original provenance/README/CC0 annex, 52 installed notices,2 upstream notices,66 previous artifacts/notices,556 CP3 frozen files; [audit](integrity-final.json) |
| Source byte binding | 143 inputs verified at source commit; [proof](committed-source-final.json); final current docs and evidence bound by delivery snapshot and subsequent Git proof |
| Whitespace | [check](whitespace-final-01.json) PASS; staged closing check recorded separately |

## Authoritative artifacts

Source/build/full-regression commit **e5b8b45fa31f8b5c385303a5ac32ddb921b1507d**.
[source-snapshot-final.json](source-snapshot-final.json) freezes that checkpoint.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| [wheel](../../docs/PUBLIC_EVIDENCE.md#historical-local-packages) |292847|4ea9adec9098c6f62315279b4189c3755de83e48fed02a0fb6259b544148c278|
| [sdist](../../docs/PUBLIC_EVIDENCE.md#historical-local-packages) |221578|8f317668585f99d59cd9e6b263180b5947d9404bf58b0357f47cb764858782f7|

[Copy proof](artifact-copy-02.json) confirms retained artifacts match actual build
outputs. Candidate01 and every earlier preview are preserved separately, with
original hashes and commands. They are not relabeled as these final artifacts.

## Failure and change boundary

[ATTEMPTS](ATTEMPTS.md) retains every failed/rejected attempt.
full-01 had877 pass/1 fail: the legacy experiment BLE settle gate finished after
110ms for a120ms requirement. Deterministic [RED](settle-red-01.json) reproduced
an early timer wake; an experiment-only monotonic deadline recheck corrected it.
All19 timing contracts [passed](settle-green-01.json), followed by full879 PASS.
No tolerance was relaxed. Numerical/production source, protocols/dependency lock,
firmware, physical raw evidence and original synthetic inputs remain unchanged.
Hardware remains frozen; no physical reacquisition ran.

The final repository-only correction to docs/M6_DEMO states current CC0 sample
permission instead of an obsolete unqualified pending statement. This document
is outside the wheel/sdist; built archive bytes are unaffected. Closing state,
checklist and plan entries describe current progress. Original candidate maps
and source proofs remain historical byte records. The delivery snapshot binds
current original source/docs plus retained records/artifacts; it excludes its
own map, dynamic state/checklist and subsequent proof records to avoid recursion.
summary.py retains the existing explicit runtime-CRLF/Git-LF mapping and archived
runtime copy; no original source or evidence was normalized.

## Remaining gates

**CP5 OPEN**: fresh clone/fresh environment, README demo twice, deterministic
products, required checks and final M6 coverage. **Linux NOT RUN**.
Public destination approval is metadata; public repository creation, push/tag,
GitHub Release/PyPI and large-evidence migration have not been executed.
Current origin remains the management repository. Wheel/sdist library APIs are
independently verified; complete repository demo requires its Git/protocols/
fixtures/sample assets. Full evidence and firmware binary distribution require
their recorded distribution-specific review before actual publication.
