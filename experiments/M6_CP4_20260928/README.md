> Public distribution note: the historical local package files are excluded; their audit results and failed attempts below remain the original historical records. Rebuild final packages from the reviewed public source.

# M6.4 / CP4 internal release-review preview

Maintainer requested a first version of public README and release documents for
final review. **CP4 OPEN: final content, project/sample licensing, citation authors
and public candidate identity remain pending.** This directory records technical
verification of the internal preview, not a public release or CP5 clean clone.

Entry HEAD: `acab57accbeee2d1fdb3cab0b6ab09c511dda0ec`, branch `main`.
M0–M5 DONE and M6 CP0–CP3 PASS remain within their existing scopes; hardware frozen.
Numerical code, dependencies/lock, public schema, firmware, raw sample and old
evidence are unchanged. Package metadata description and document/notice inclusion
are updated for the preview; the version remains `0.1.0`.

Review entry: [README](../../README.md), [technical report](../../docs/M6_TECHNICAL_REPORT.md),
[review sheet](../../docs/release/REVIEW.md), [notices](../../THIRD_PARTY_NOTICES.md),
[packaging boundaries](../../docs/release/PACKAGING.md).

## Verification

| Check | Observed result / record |
|---|---|
| Full pytest | **878 passed, 0 skipped**, actual external M1 root and fresh external pytest temp; [command](full-01.json), [log](full-01.log) |
| Ruff | PASS, including the CP4 evidence scripts; [record](ruff-final-02.json) |
| Strict mypy | PASS, 33 package source files; [record](mypy-02.json) |
| Documentation / immutable archive | Initial full check PASS, 39 archive hashes; final delivery/state checks separately recorded; [initial record](docs-01.json) |
| Pinned build | sdist then wheel-from-sdist PASS for final preview; [command](build-03.json), [log](build-03.log) |
| Archive contracts | PASS: 34 package source/typing files, 57 snapshot files, exact README/root notices, metadata/extras, exclusions; [full members/hashes](archive-green-03.json) |
| Independent installs | PASS: two absent-root venvs, eight actual commands, frozen hash-enforced analysis dependencies, isolated cwd/import, calibration/AHRS/rotation/M3/unavailable checks and original installed notices; [complete command/exit/hash audit](installation-audit-attempt03.json) |
| CFF | YAML parse PASS; official 1.2.0 schema has exactly the missing required `authors` error; **schema_valid=false**, [audit](citation-draft-audit.json) |
| Integrity and boundaries | PASS: 25 original inputs; 52 installed + 2 version-tag notice texts; all 556 CP3 frozen records (old README at its accepted Git anchor); six retained original artifacts; [audit](preview-audit.json) |

The generic wrapper for the first install run collided with the child JSON name;
all original logs and corrected new-root runs remain. `attempt03` is the complete
authoritative audit for final preview03. Failure details and the red/green wheel
notice-inclusion check remain in [ATTEMPTS.md](ATTEMPTS.md).
Pure production code, fixtures/thresholds, uv.lock, firmware and all sample bytes
remain unchanged. Linux NOT RUN. CP5 clone acceptance has not been attempted.

## Final internal preview artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| [Wheel](../../docs/PUBLIC_EVIDENCE.md#historical-local-packages) | 292281 | `b6cbf5447c933bda4f766274c36423016f419916916b4344ae109f595c862747` |
| [sdist](../../docs/PUBLIC_EVIDENCE.md#historical-local-packages) | 220828 | `39d13ddc160b483b15a380c047fd887009f451b6026ed155957545e9b834e630` |

Built at the entry HEAD plus scoped working-tree document/package metadata
changes; never described as clean-source release candidates. The exact current
source/document/evidence hashes are frozen in `source-snapshot.json` before the
delivery commit and verified against its Git blobs in the later committed proof.
The snapshot excludes dynamic state, itself and later proof/check records.
The unchanged `summary.py` has a declared existing runtime-CRLF/Git-LF identity
mapping; its runtime bytes are retained in `runtime-summary.log`. Only that
named file uses exact CRLF→LF correspondence in the proof; all other frozen
members require identical Git/disk bytes. See [precommit notes](PRECOMMIT_NOTES.md).
Rebuilding after final editorial/license/citation approval must create new
artifacts, not relabel these internal previews. Superseded attempt01/02 artifacts
are retained byte-for-byte alongside their logs and archive maps.

LICENSE remains an unapproved status file; CITATION is intentionally incomplete.
They do not satisfy final CP4 licensing/CFF gates. The CFF schema is retained
unmodified from its official 1.2.0 source under CC-BY-4.0, with its
[license](cff-upstream-LICENSE.txt), [original citation/authors](cff-upstream-CITATION-cff.txt),
[schema URL/hash](cff-schema-source.json) and [notice source/hash](cff-upstream-notice-sources.json).

## Reproduce the technical checks

From a new checkout with the same pinned toolchain, use NEW command record names,
artifact directories, audit files and external environments. The helper scripts
refuse to overwrite their records. For installs, export analysis requirements
with `uv export --frozen --no-dev --no-emit-project --extra analysis --format
requirements-txt`; install with `--require-hashes` and `--only-binary :all:`.
Then install the project wheel or sdist with `--no-deps` into separate new venvs;
run `python -I` on [installed_api_check.py](installed_api_check.py) from an external cwd.
Use [check_archives.py](check_archives.py) with new `--artifacts` and `--output`.
Actual commands/paths/runtime identities are in the records above. Snapshot
generation and retention helpers are one-shot custody operations, not commands
to rerun into this completed evidence directory.

## Next action

Maintainer reviews [the concrete content and decision sheet](../../docs/release/REVIEW.md).
Record approved license/authorship/sample/URL/version choices, complete and validate
LICENSE/CITATION, rebuild/verify on a new final candidate, then accept CP4 before
CP5. No further hardware or benchmark run is required by this draft. No
push/tag/Release/PyPI or history/storage migration has occurred.
