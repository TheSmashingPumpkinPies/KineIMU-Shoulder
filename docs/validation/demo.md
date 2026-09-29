> Historical CP2 acceptance record, 2026-09-28. Later V1 checks completed and the
> source is published; current commands are in [VALIDATION.md](../../VALIDATION.md).

# M6.2 / CP2 — complete sensor replay Demo acceptance

Project: KineIMU Shoulder. Entry `main` / `ff0051cd` (full SHA in state and checks).
Contract: [m6-demo-contract/1.0](../M6_DEMO_CONTRACT.md).
Delivery: [one-command guide](../M6_DEMO.md),
`examples/m6_demo.py`, `kineimu_shoulder/validation/demo.py` and
`tests/integration/test_m6_demo.py`. Complete Windows pair and independent audit
PASS at clean source lock `1732b1af274ebf05c241d515ebcc126e65def3cd`.
Committed-byte binding is finalized by the separate delivery proof and dynamic state.

The wrapper calls unchanged `export_stored(output / "replay", input_root=sample)`.
No generator, replacement capture, production algorithm, threshold, dependency,
public schema, firmware, old input or old formal evidence changes.
Success requires four trajectories and original aggregate/support gates, both
input audits, complete replay products, checksum validation, readable summary,
M6 run metadata and top-level checksum index. Original M5 CP4 OPEN remains intact.

Evidence collection retains command arrays, actual exits and original output bytes.
Formal pair uses two new processes, a clean tracked tree at one exact source lock,
same sample/environment and safe external fresh roots. Both 26-file original roots
are retained; repository evidence copies preserve their exact bytes. Pair audit independently invokes
the existing CP3 O/F/T arithmetic auditor for every trajectory, checks frames,
calibration/AHRS/QC/source/support and both checksum inventories, and compares all
22 canonical products, inner checksums, summary and all run fields except the
contract's explicitly permitted process metadata. Input maps are audited before
and after collection. The selected inputs subsequently received the
[25-member CC0 permission](../../datasets/samples/m6_synthetic/LICENSE.md).

Test-first/failed attempts retained:

- `red.log`: 27 expected missing-wrapper/entry failures.
- `green.log`: 23 passes / four failures because test output roots were under
  the repository's protected `.pytest-*` tree. No guard weakened; retry used
  an external temporary root.
- `green2.log`: initial complete 27-test pass, including real four-Q replay.
- `failure-red.log`: required input disappearing during export prevented
  final failure-record writing. Only a test copy was removed. Regression first
  reproduced the defect; post-input audit is now recorded separately, preserving
  failure bookkeeping even when input becomes unavailable.
- `negative-green.log`: 27 negative/CLI checks pass after the correction;
  complete replay was deselected and is verified separately again.
- `audit-red.log`: expected missing-independent-auditor failure.
- `pair-red.log`: a complete real replay passed individual audits but pair
  comparison incorrectly compared the run.json hash despite permitted metadata
  differences. The correction independently verifies both run hashes and compares
  every run field with the exact contract whitelist; all other 24 hashes compare
directly. A new undeclared field must still be rejected.

Final execution evidence:

- collection.json (complete record retained in the local evidence archive): two actual `uv run --frozen python
  examples/m6_demo.py --output <fresh-root>` processes, each exit0; external
  M1 root absent and OPENBLAS/OMP/MKL thread variables each 1. Original process
  output roots and exact command/log/output maps remain in attempt records.
- pair-audit.json (complete record retained in the local evidence archive): all22 canonical products, inner index and
  summary equal; remaining24 top product hashes equal; all run fields except
  the complete contract whitelist equal. Both indexes independently verified.
- [run1 summary](../PUBLIC_AUDIT.md) and [run2 summary](../PUBLIC_AUDIT.md): eight core
  families first, detailed metric strata/phase/proxy/error evidence preserved.
  Each root has exactly26 files; no new capture. retained-products.json (complete record retained in the local evidence archive)
  verifies byte-preserving copies against the original process output maps.
- Every run independently checks 27,160 error scalars through the existing locked
  M5 CP3 O/F/T auditor. Each four-Q run has eight complete streams, 17,208 samples /
  4,304 packets; each trajectory truth=valid=3, missed=false=0, relative/recall/proxy
  coverage=1; elevation/interval-speed supports1651/1650. All original budgets pass.
  Frame checks verify decoded sensor SI, R_NS once after calibration and R_NK once
  after AHRS, known initialization and preserved sample/packet/time/hash anchors.
- inputs-before.json (complete record retained in the local evidence archive) = inputs-after.json (complete record retained in the local evidence archive):
  all37 original inputs and all28 packaged sample files unchanged.
- runtime-source.zip (complete record retained in the local evidence archive) and [source map](../PUBLIC_AUDIT.md):
  all49 executed/contract/audit/entry/test/guide/CI dependencies preserved as actual
  runtime bytes, with ZIP member hashes independently checked. Git EOL conversion
  cannot silently substitute reconstructed source bytes.
- full check (complete record retained in the local evidence archive): 855 pass / no skips using actual external M1
  read-only inputs; final focused check (complete record retained in the local evidence archive): 29 pass
  with no external raw root. Full Ruff, strict mypy33, docs1246/39 archive hashes/0
  errors, whitespace and pinned sdist/wheel build pass in separate check records.
  These are regression/build checks, not performance benchmarks. Final presentation
  and bound-loop rendering were independently rechecked after the readability refinement.

Reproduce numerical/inventory/pair audit, with a fresh audit output:

```powershell
uv run --frozen python validation/auditors/demo.py --run1 experiments/M6_CP2_20260928/run1 --run2 experiments/M6_CP2_20260928/run2 --output .tmp-m6-cp2-new-pair-audit.json
```

This is read-only for retained roots. It audits the current packaged inputs/source
against their recorded hashes; a modified environment/source must not be relabelled
as the retained run. `require_clean=False` is available only to Python integration
tests on their deliberately dirty test outputs; CLI/formal acceptance always checks
the recorded clean source state. Test-only altered roots are distinct from retained roots.

`delivery-tool.txt snapshot` freezes source/entry/test/guide/CI plus this evidence;
`delivery-tool.txt prove <delivery-sha> <new-output>` binds exact committed Git/disk
bytes, including all26 files in both retained roots and the runtime source archive.
Dynamic state, the snapshot itself and later proof files are outside that map.

Linux execution: NOT RUN in this Windows session. CI includes an explicit complete
Demo smoke command; configuration is not execution evidence. At this CP2 checkpoint, performance, packaging and fresh-clone checks were
still outstanding; they subsequently completed within V1 scope. This record
performed no remote publication or hardware/human action. Current publication
status is recorded in [the release page](../release/REVIEW.md).
