# M6.1 / CP1 — synthetic sample input acceptance

Date: 2026-09-28. Project: KineIMU Shoulder. Entry `main` /
`7b3be2b7a1eb44f60bd1a845f0386ca75ab3adac`.
Scope: sample packaging and input acceptance, following the frozen
[Demo contract](../../docs/M6_DEMO_CONTRACT.md) §1 and
[release checklist](../../docs/M6_RELEASE_CHECKLIST.md) CP1.
CP2 demo, benchmark, licensing approval and full clean-clone acceptance remain separate.

Delivery: [sample README](../../datasets/samples/m6_synthetic/README.md) and
[provenance](../../datasets/samples/m6_synthetic/provenance.json); four trajectories
F90 / AL90 / AR90 / T-MIX, 25 exact original-byte input files, 4,539,058 bytes.
Eight captures contain 17,208 node-samples / 4,304 packets, 585,136 bytes.
Three packaging files (README, provenance and local Git attributes) are additional.
The original 36-member map is preserved; 24 of its members are shipped,
12 unshipped members are listed by path/hash. No original source, raw, map,
formal result or failed evidence is overwritten or relabelled.

| CP1 obligation | Evidence / observable result |
|---|---|
| Four Q trajectories and all necessary files | 25-member inventory and eight decoder checks in `tests/integration/test_m6_sample.py`; no generation or AHRS in focused checks |
| Independent annotations and source/config provenance | Original annotations / observation labels / manifests preserved; provenance records generation source lock, original delivery lock, source hashes, runtime, configuration references, units and frames |
| Original bytes / fixed map / Git identity | [input-audit.json](input-audit.json), [original-before.json](original-before.json), exact original CP1 delivery Git blobs and frozen CP0 inventory |
| Raw unchanged before/after | All 37 original run1 files and all 28 sample files checked before/after; eight captures included; final audit repeated after tests |
| Missing input refusal | Each of 25 required files removed only in independent pytest copies; FileNotFoundError |
| Changed input refusal | Each of 25 files changed only in independent copies; ValueError before output creation |
| Recomputed map refusal | A changed capture plus forged matching member hash rejected by independently anchored original map hash |
| Unsupported input refusal | UNKNOWN, F90-30 and ../F90 rejected before processing; all three existing refusal tests also passed before packaging |
| No human data / release scope | Synthetic generator lineage and input types; `anatomical_eligible=false`; INTERNAL ONLY / public redistribution pending |
| Checkout byte preservation | Sample `.gitattributes` sets JSON and capture `-text`; committed-byte audit uses a fresh sparse local clone with core.autocrlf=true, verifies all 28 sample files against delivery Git blobs and all 25 input hashes |

Test-first evidence: initial sandbox [red.log](red.log) encountered the known
Windows pytest temporary-directory access error; retained as an environment failure.
The fresh normal-access [red-normal.log](red-normal.log) returned exit1,
61 expected missing-package failures / 3 existing refusal passes, no setup errors.
[package-tool.txt](package-tool.txt) then copied selected inputs with exclusive writes,
source hashes and original Git checks; [package.log](package.log) records its result.
No production algorithm/API/schema/dependency/firmware changes.
An independent repeat in a fresh temporary root produced all 27 tool-output
files byte-identically (25 inputs plus provenance and Git attributes):
[package-repeat.json](package-repeat.json), [package-repeat.log](package-repeat.log).
README is separately reviewed documentation, outside the tool-output repeat.

The initial full regression retained 825 passes / one documentation failure:
the scanner found a README link to the deliberately removed SHA256SUMS.json in
an untracked negative-control fixture copy. [docs-diagnosis.log](docs-diagnosis.log)
confirmed both affected temporary copies. Their bytes and roots are preserved;
only these owned temporary roots were added to local `.git/info/exclude`.
The repeated tests use the existing local `/.pytest-*/` exclusion convention;
ordinary pytest defaults place fixtures outside the repository. No public ignore
policy or formal-evidence exclusion was changed. One Ruff E501 line-wrap failure
was also retained and corrected without changing test semantics.
See [failure-resolution.json](failure-resolution.json) and
[fresh focused/lint/docs checks](checks-focused2-ruff2-docs2-whitespace2.json).
Full-regression retry is recorded separately, never replacing the failed log.

Final required checks: focused64 pass; full826 pass/no skips with actual external
M1 root; Ruff pass; strict mypy32 pass; docs1243 Markdown/39 archive hashes/0 errors;
whitespace pass. See [full retry checks](checks-full2.json),
[full2.log](full2.log), the focused/lint/docs checks above, and
[initial batch checks](checks-focused-full-ruff-mypy-docs-whitespace.json) for
the unchanged successful mypy result and separately retained initial failures.
The staged whitespace check initially classified original native CRLF process
logs as trailing whitespace. Logs and exit-output captures are now declared
binary evidence in local Git attributes; their original bytes are not rewritten.
`staged-whitespace-pre.log` / `staged-whitespace-pre-exit.txt` retain that failure.
`snapshot-pre-whitespace.json` is a superseded uncommitted preparation map;
the final delivery snapshot is SHA256SUMS.json.
The final CP1 disposition additionally requires the committed snapshot and
fresh sparse-checkout audit; their post-commit records are `committed-evidence.json`
and `checkout-audit.json`, with final disposition in dynamic state.

Reproduce from the repository root with frozen dependencies:

```powershell
uv run --frozen pytest tests/integration/test_m6_sample.py
uv run --frozen python experiments/M6_CP1_20260928/audit-tool.txt .tmp-m6-cp1-new-audit.json
```

The audit output must not already exist. It compares current sample, original run1,
frozen CP0 inventory, original CP1 map and exact original Git blobs, then repeats hashes.
For a new independent sample copy, run `package-tool.txt` with an absent destination;
the tool does not create README (the README is separately reviewed documentation).
It never writes to original inputs or existing output roots.

After delivery, optional committed-byte reproduction:

```powershell
$delivery = git log -1 --format=%H -- datasets/samples/m6_synthetic/provenance.json
uv run --frozen python experiments/M6_CP1_20260928/audit-tool.txt .tmp-m6-cp1-new-git-audit.json $delivery
```

This creates a fresh sparse local Git clone under `.tmp-m6-cp1-checkout-*`,
checks out the exact delivery ref with core.autocrlf=true, and audits the sample.
The clone shares the local Git object store; no file is copied from original run1.
The audit uses the existing verification environment, not the CP5 fresh environment
or complete Demo acceptance.
No external M1 root is needed for focused tests or input audits. Full maintainer
regression separately uses the retained external M1 root, as recorded in checks.

Public license, authors, final release metadata and redistribution remain CP4 gates.
No performance, Linux execution, anatomical/human/clinical accuracy, CP2 or M6 DONE claim.
Remote synchronization and large-evidence distribution remain deferred to final closeout.
