# Stored dual-node sensor replay

This validation entry reads the bundled, immutable stored Q captures for
F90, AL90, AR90 and T-MIX. Each node has 538 packets and 2,151 samples over
0–21.5 s. The frozen evaluation window is 5–21.5 s; initialization at 0 and
5 s is checked separately. This is synthetic evidence with
`anatomical_eligible=false`. The subreport retains its original stage-B semantics:
`formal=false` and `checkpoint_disposition=OPEN`. This describes the scope of this
entry, not the current overall V1 completion status. See [validation](../VALIDATION.md).

```powershell
.venv/Scripts/python.exe -m kineimu_shoulder.validation.stored_demo --output <absent-development-root>
```

Exit 0 means **stage B development replay passed**, not CP4 acceptance.
Failed inputs/numerical gates return 1; unavailable sources return 2/BLOCKED.
All four session IDs remain in the report, including failures. Output uses the
stage A raw/source/acquisition/evidence protections and exclusive fresh creation.
Never reuse an old output root.

The independently pinned CP1 `SHA256SUMS.json` binds KIMU files, metadata,
pre-quantization SI/time references, independent annotations/observation labels,
case expansion and backend/launch provenance. All selected bytes are checked
before and after replay. Editing a digest map to agree with edited inputs fails
the map's independent anchor. Sensor observations are read from actual KIMU;
no generator, packet writer or exact orientation time series supplies them.

The loader checks original node IDs, epochs, counts, endpoints, sequence and
device-time identity, QC and frozen sensor-component half-LSB budgets. Frozen
replay converts counts to sensor SI and preserves sensor axes. Known clean
calibration operates in sensor axes, then its adapter applies R_NS once to
produce node SI before explicit processing/1.1 reconstruction and pinned AHRS;
R_NK is applied once after AHRS. Synthetic metadata supplies known initial pose,
clock maps and common world. These are construction assumptions, never inferred
from gravity or host arrival times. Clean Q observations add no reconstructed rows.

The existing CP3 session pipeline computes M2/M3/M4, independent O/F/T matrix
errors, complete support/coverage denominators, candidate matching/exclusions,
repetition/proxy metrics and session summaries. Recomputed nominal labels and
summary references must also match frozen CP1 annotations. The frozen S/Q clean
budgets apply unchanged; peak plateau and warmup ownership rules are retained.

Canonical products are `manifest.json`, `report.json` and five files per session:
`result.json` plus deterministic gzip (`mtime=0`) of canonical JSON for
`processed`, `derived`, `annotations` and `errors`. `SHA256SUMS.txt` binds all
22 products and excludes itself. Manifest includes exact HEAD, dirty state,
source/contract/truth/lock/auditor hashes, runtime, thread environment and explicit
configuration. This entry always records `formal=false`.

The integration test independently audits all four exported cases with the
retained CP3 auditor, checking scalar arithmetic, geodesics, O/F/T expectations,
reconstruction conservation, retention, coverage and full error support. Its
corruption control changes only a test output and must fail the auditor.
No production algorithm, backend, schema, frozen gate, raw source or hardware
is modified by this entry. Recorded-node and dual-stream audits remain separate
validation layers. See [reproduction](validation/reproduce.md).
