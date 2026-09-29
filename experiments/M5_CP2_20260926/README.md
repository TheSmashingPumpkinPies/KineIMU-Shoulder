# M5.2 / CP2 — Clean Full-Chain Baseline

Date: 2026-09-26 (Asia/Shanghai). **CP2 PASSED** at the frozen clean synthetic numerical/evidence scope. M5 CP3–CP5 and overall M5 remain OPEN. Hardware remains frozen.

Exact clean numerical source/tool lock: `92d06d0589689417162eb80d351566045c7c25b7` on `main`. Both independent formal launch manifests have `formal=true` and `tracked_dirty=false`. Subsequent state/document commits do not change any processing/source/contract/truth/lock bytes. No push or PR.

The existing calibration/AHRS → explicit segment alignment/clock mapping/common heading/SLERP grid → M3 elevation and 3-D angular speed → M4 segmentation, metrics, thorax proxy, summaries and comparison → canonical processed/derived/report chain is exercised. All 30 frozen CLEAN cases and both F90/F90-NEXT comparisons passed; both runner processes exited 0. E uses exact segment orientations; S applies real imucal calibration and a fresh imufusion AHRS per node; Q additionally encodes and replays the real M1 framed format. Known synthetic parameters/heading are declared, not physically estimated or validated.

| Path | Cases | Eligible repetitions | Missed / false | Disposition |
|---|---:|---:|---:|---|
| E | 13 | 84 | 0 / 0 | PASS |
| S | 13 | 84 | 0 / 0 | PASS |
| Q | 4 | 12 | 0 / 0 | PASS |

Across all paths: 180 eligible repetitions from 194 detected candidates; 14 correctly excluded. Relative-duration coverage is 1.0 in every case; recall and thorax-proxy coverage are 1.0 where an eligible denominator exists. Empty denominators retain null availability. QUIET has no candidates; WRONG excludes all 3; PARTIAL excludes both boundary actions and retains only the middle action. F90-30 excludes its final censored candidate. F90L has 54 eligible repetitions plus its final censored candidate; both E/S have complete 300-second evaluation coverage.

Selected maximum absolute errors are in SI units. These aggregate maxima summarize retained per-case values; each individual gate uses its own unchanged frozen tolerance. The JSON report retains all maximum errors/RMSE/n/tolerances, while case result files retain actual/expected/signed/absolute arrays.

| Metric | Unit | E max error | S max error | Q max error |
|---|---|---:|---:|---:|
| Node orientation | rad | 2.87528511e-14 | 0.00614593477 | 0.00614340538 |
| Relative elevation | rad | 2.87547763e-14 | 0.00613531399 | 0.00566350312 |
| 3-D interval speed | rad/s | 5.01554354e-12 | 0.00822859692 | 0.0065097734 |
| Repetition ROM | rad | 2.22044605e-16 | 0.00980765516 | 0.00878931521 |
| Repetition peak | rad | 0 | 0.00613531399 | 0.00566350312 |
| Repetition/phase duration | s | 0 | 0.01 | 0 |
| Thorax proxy extrema/magnitude | rad | 1.94289029e-16 | 0.000548975429 | 0.000558712664 |
| ROM SD | rad | 8.96518306e-16 | 0.00447407834 | 0.000454445871 |
| ROM CV | 1 | 6.41282337e-16 | 0.00409905298 | 0.000323156097 |
| Active cadence | 1/s | 0 | 0.00041736227 | 0 |

Largest nonzero normalized gate: `T-MIX/CLEAN-S/SAME/0` / `B.orientation` = 0.0061459347717515616 rad / 0.0069813170079773184 rad = 0.880340309. Exact zero-tolerance gates also passed. Both comparison records remain comparable with no differing keys.

| Comparison | Expected ROM difference (rad) | Observed difference (rad) | Absolute error (rad) | Frozen tolerance (rad) |
|---|---:|---:|---:|---:|
| E | 0.17278759594743875 | 0.17278759594743853 | 2.22044605e-16 | 2e-10 |
| S | 0.17278759594743875 | 0.17374802691663183 | 0.000960430969 | 0.0698131701 |

Independent retained-output audit passed: **131 files and 308,650,779 bytes per run**, all bytes identical, all non-self manifest hashes valid, all frozen CP1 nominal labels equal and all 8 Q capture files byte-identical to accepted CP1 demos. Independently recomputed **451,090 error scalar rows per run**, including signed/absolute errors, maxima and RMSE. An intentionally corrupted-byte control was rejected and created no success artifact.

- [Formal report — historical availability](../../docs/PUBLIC_EVIDENCE.md#not-distributed-in-this-source-snapshot), [second report — historical availability](../../docs/PUBLIC_EVIDENCE.md#not-distributed-in-this-source-snapshot), [independent audit](reproducibility.json), [auditor](audit.py).
- [Launch manifest](retry1/run1/manifest.json), [output hash manifest](retry1/run1/SHA256SUMS.json), [runner documentation](../../docs/M5_BASELINE.md).
- [Frozen source interpretation notes](SPEC_NOTES.md), [preserved stopped attempts](partial-attempts.json).

The output hash-manifest SHA-256 (equal for both runs) is `f97c062b5281737c96871584fde66427147e6454297c1275f693f3e4cccdbeb8`. Full relative paths and byte hashes are retained in the independent audit, allowing every report cell to resolve to its processed/derived/annotation/result evidence.

Initialization rows [0,5] seconds arm the unchanged M4 state machine; all error/coverage denominators begin at 5 seconds. PARTIAL preserves its explicit crop. Initialization errors are separately reported. Exact E constructs elementary axis angles from integer-time rational degrees to retain symbolic threshold equality; no tolerance slack or production change. The existing empty active-time sum is valid zero; unavailable ROM/SD/CV/cadence retain null and reasons. See runner documentation for exact contracts.

The frozen VAR prose says the third start is 15s, but its parameter equations and accepted CP1 annotations give 14s. CP2 explicitly follows the retained parameter-defined source and independent annotations; no frozen file/label/budget was edited. Summary UTC dates are declared synthetic ordering labels, not measured UTC. [SPEC_NOTES](SPEC_NOTES.md) records both limitations and future reviewed correction requirements.

Earlier development diagnostic `.tmp-m52-diagnostic1` and original formal `run1`/`run2` were stopped with 13 completed cases/59 files each, retained unchanged, and classified STOPPED_PARTIAL_NOT_PASS. Identical declared calibration parameters had been incorrectly associated with differing evaluation-motion hashes; a red/green regression caught and fixed validation-only provenance before this fresh lock. Raw stream hashes remain separate lineage. The immutable inventory is linked by both successful launch manifests. No stopped root is resumed or repaired.

Reproduction from the exact clean source lock and pinned environment (Python 3.12.14, uv 0.12.5, numpy 2.5.2, scipy 1.18.1, pandas 3.0.5, imufusion 1.3.3, imucal 2.6.0):

```powershell
.venv/Scripts/python.exe examples/m5_baseline.py --output <absent-run1>
.venv/Scripts/python.exe examples/m5_baseline.py --output <absent-run2>
.venv/Scripts/python.exe experiments/M5_CP2_20260926/audit.py --root <parent-containing-run1-run2> --output <absent-audit.json>
```

Delivery verification: pytest **596 passed, 2 external M1-data skips** (all 9 CP2 integration tests included); Ruff and strict mypy (24 source files) pass; documentation and whitespace checks pass. Skips do not count as recorded-replay evidence. Regression controls include missing heading, missing post-AHRS alignment, output-root overwrite protection, exact E threshold equality, excluded actions and consistent calibration provenance/comparison.

Only validation-only code, tests, examples, retained experiments and documentation were added. All production code and frozen CP0/CP1 source/oracle/contract/truth/manifest, raw data, public schema, firmware, hardware and dependency lock remain unchanged. All outputs are `source_type=synthetic`, `anatomical_eligible=false`; this is no physical, anatomical or clinical validation.

**Exact next action: M5.3 / CP3.** Read the frozen finite perturbation/seed manifest and gates, implement validation-only perturbation execution test-first, preserve every outcome, and independently audit the full required matrix. CP4 still requires actual external M1 replay; CP5/overall M5 closeout remain separate.

Public-export note: unavailable internal navigation is redirected to the evidence-availability index; scientific claims and original target names are retained by the export record.
