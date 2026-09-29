# CP4 source identity — explicit original Git EOL mapping

E3 audit-only attempt stopped before numerical audits when comparing original
working bytes directly to Git blobs. Read-only diagnosis of every original
source-map entry found exactly two existing CRLF/LF differences. Both were
already present at clean numerical lock a72bdd18 and are byte-exact in the
original actual-runtime ZIP, formal manifests and unchanged current disk.

| Original source | Git LF SHA-256 | Actual-runtime CRLF SHA-256 |
|---|---|---|
| M5_4_REPLAY_PLAN.md | 49f170126c90df9b19d8a85be26d793c87b2ac0dd3f15958a0baa8578f0e4fdf | 92c01e59d81c7f3eac1433110488e42c8aa2fa7cc9809e55368593f13f1395aa |
| kineimu_shoulder/summary.py | 5f72396acdcd02979deabcf289639dc1cef3efcff316c07d55f49cf70b6ae90a | 5502c4b4f252c23051dafdfb0e23bd8cbe9bec15351efd2400c13032713f5281 |

The repository .gitattributes uses text=auto/eol=lf and core.autocrlf=true.
E4 declares this mapping only for those exact paths and exact two hash pairs.
The actual source bytes must still match the immutable original source map,
ZIP and disk without editing. CRLF→LF is used solely to prove their relation
to Git source identity; neither source file is rewritten. Every other source
requires exact Git bytes. Content changes and undeclared mappings fail.
No mapping is applied to raw acquisition data or canonical numerical products.

This corrects audit identity representation, not a numerical/scientific gate.
Python source, algorithms, thresholds, raw, formal roots and previous failed
audits stay untouched. The [PID correction](M5_CP4_PID_AUDIT_CORRECTION.md)
remains active. E4 records all Git/runtime source hashes and mapping modes,
with its own committed tool lock and ZIP. Both original complete numerical
runs at a72bdd18 must satisfy all six independent B/C/D audits, full canonical
byte equality, immutable raw manifests and the original CP4 requirements.

E4 tests require red/green known-original mappings plus semantic-change and
undeclared-path rejection; required audit-tool checks apply. Full762/no-skip/
focused103 source evidence remains tied to unchanged numerical source bytes.
All prior failed roots, audits and logs remain separately retained. CP4 remains
OPEN until E4 complete audit passes; CP5/overall M5 remain outside this segment.
