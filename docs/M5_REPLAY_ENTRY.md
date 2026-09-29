# M5.4 stage A — entry, report and evidence gates

Stage A implements development entry/QC and gate-report tests only. CP4/CP5
remain OPEN. No complete retained Node B or external M1 orientation replay,
formal launch or two-process CP4 acceptance occurred in this segment.
The governing sequence remains [M5.4 replay plan](../M5_4_REPLAY_PLAN.md).

## Reusable interfaces and limits

| Interface | Reuse in CP4 | Remaining integration |
|---|---|---|
| `io.m2_replay.replay_capture` | Complete file SHA-256, framing/CRC/node/epoch/QC, sensor SI and original counters/time | Independent anchors and before/after checks are now in validation entry |
| CP1 `run1/{F90,AL90,AR90,T-MIX}/{A,B}.kimu` | Eight immutable synthetic recordings; source map in retained `SHA256SUMS.json`, metadata and independent annotations | Stage B must read these files; generator memory or newly generated Q files cannot substitute |
| `validation.baseline.run_case`, `validation.perturbation` | Known calibration, explicit transforms, pinned AHRS, common grid, independent oracle/errors and full M3/M4 chain | Existing Q mode generates a new file; it is an integration reference, not the CP4 stored-file runner |
| `calibration.apply_calibration`, `orientation.estimate_orientation` | Recorded identity example and independent per-node world | C/D must run all samples, not M2 example's 128-row excerpt; declare assumptions and no common yaw |
| `relative_orientation`, `shoulder`, `exercise`, `thorax`, `summary` | Actual missing-evidence rejection and descriptive summaries | `validation.replay.gate_report` exercises these interfaces and keeps all stage reasons/null values |
| `validation.replay.export_entry` | Safe fresh output, before/after hash, full decode/QC, pinned counts/endpoints, source/runtime map and artifact hashes | Intentionally entry-only; calibration/AHRS/full replay NOT RUN, no exit-0 or formal mode |

No production, algorithm/backend, acquisition schema, frozen truth/seed/gate or
hardware change. Stage A's gate fixture uses F90 **E** exact synthetic inputs;
it is neither a Q accuracy run nor evidence that recorded inputs have alignment.
The entry adapter declares illustrative sensor-to-node identity, suitable for
recorded entry/QC and the small identity-axis test packets. Stage B must use
the frozen Q metadata's actual R_NS and R_NK, each applied at its declared stage.

## Required input-to-acceptance mapping

These are the fixed required CP4 session IDs. Entry files have per-node IDs
(`Q-F90-A`, etc.); they do not replace complete session results. All are required
in each future formal run. The four Q sessions preserve their corresponding
frozen `*/CLEAN-Q/SAME/0` truth/case IDs and independent label denominators.

| Session ID | Required files and independent anchors | Acceptance/report obligation | Stage |
|---|---|---|---|
| Q-F90 | CP1 run1 F90 A/B KIMU, metadata, labels, retained digest map | Full synthetic chain; independent F1/Q errors, three cycles, counts/coverage/quantization/warmup, no anatomical upgrade | B |
| Q-AL90 | CP1 run1 AL90 A/B and matching retained references | Full left-abduction synthetic chain, independent labels and frozen Q budgets | B |
| Q-AR90 | CP1 run1 AR90 A/B and matching retained references | Full right-abduction chain and correct side/axis/sign | B |
| Q-T-MIX | CP1 run1 T-MIX A/B and matching retained references | Full mixed thorax chain, independent noncommuting geometry/proxy labels | B |
| REC-NODE-B | `firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary.kimu`; hash in plan; 208 packets/832 samples; endpoints 257030578–264845581 us | Complete QC/counts/time and node AHRS; identity calibration Assumed/Experimental; single-node shoulder unavailable | C |
| REC-M1-USB | External root selected by `KINEIMU_M1_RAW_ROOT`; A/B hashes, counts/endpoints in plan and `test_m2_replay_m1_bench.py`; full 11-file manifest plus manifest digest | Full independent node AHRS; no invented clock/common-heading/alignment/drift; shoulder unavailable with stage reasons; before/after complete source inventory | D |

Q counts are 538 packets/2,151 samples per node including the final partial
packet, from [CP1 retained evidence](../experiments/M5_CP1_20260926/README.md).
Node B endpoints come from the committed
[compatibility record](../firmware/xiao_nrf52840_sense/evidence/node_b_20260913_compatibility.md).
M1 anchors come from the committed
[bench report](../experiments/M1_DUAL_USB_30MIN_RESULT_20260925.md) and M2 test,
never from a new CP4 result. Q digest/metadata/annotation maps must be verified
before processing. The external full-manifest checker remains a D/E obligation.

## Development entry and report

The module accepts an explicit validation-local JSON list, not a new public
acquisition schema. Each row provides `case_id`, `path`, `sha256`, `node_id`,
`expected_packets`, `expected_samples`, `expected_endpoints_us` and `source_type`
(`synthetic` or `recorded`). Paths select existing immutable inputs. Independent
anchors must come from the table's committed references. The CLI test constructs
only a two-sample test copy; no real long input is selected by default.

```powershell
.venv/Scripts/python.exe -m kineimu_shoulder.validation.replay --input-spec <explicit-inputs.json> --output <new-development-root>
```

The output root must be absent, including rejection of an empty existing root.
Resolve paths before rejecting raw components, input trees and their ancestors,
the entire acquisition root containing a raw directory (including its processed
siblings), repository source/data trees, and existing experimental evidence directories.
Claim the new root with exclusive mkdir and files with exclusive creation;
never append to an old root. Duplicate/traversal case IDs fail before claiming.

Products are strict canonical UTF-8/LF/sorted/indented JSON: `manifest.json`,
`cases/<id>/entry.json`, `report.json`, plus a separate `SHA256SUMS.txt` excluding
itself. Manifest binds exact current HEAD, tracked-dirty flag, source/contract/
truth/processing/lock map, runtime, adapter configuration and selected input
anchors. It is always `formal=false`; source cleanliness and a committed source
map are not granted by this development manifest. Entry retains original
counters/time/QC and hashes; report binds case artifacts to requirement IDs.
No absolute output path, wall clock or duration enters canonical products.

Successful decoding produces `entry_disposition=PASSED` but full stage
`NOT RUN`, `passed=false`, checkpoint OPEN and partial artifact disposition.
Exit 2 means full replay is pending or required data/access is BLOCKED.
Hash/node/CRC/count/endpoint/QC/mutation failures produce FAILED and exit 1.
Every selected case remains in the report; failures do not erase partial output.
There is deliberately no stage A exit 0 or CP4 PASS path.

The gate reporter takes explicit already-aligned streams, maps, heading,
alignments and thorax evidence; it calls the production M2/M3/M4 stages and
serializes their records without filling unavailable numbers. Isolated tests
remove one item from supported synthetic input. Both clock maps and both
alignments are covered; heading relation, thorax heading and drift are covered.
Expected upstream reasons are literal existing contracts: `clock_map_missing`,
`heading_missing`, `alignment_missing`, `thorax_heading_missing`,
`thorax_drift_unbounded`. Summary keeps invalid analysis/counts/null metrics,
or unavailable thorax proxy while supported shoulder quantities remain separate.

## Red/green and remaining verification

Implementation-first baseline was prevented with an import-presence assertion:
21 tests failed because the runner was missing (`.tmp-m54-a-red2`, exit 1),
then the same 21 passed (54.72 s). Source-type/CLI additions were separately
red (`.tmp-m54-a-red3`, two failures, exit 1) before implementation. Expanded
25-test set passed (57.48 s); additional path/read-order and canonical-root
controls receive final verification in the stage delivery record. Review found
that protecting only the raw parent would permit output in the acquisition
root's processed sibling, contaminating a complete M1 manifest. A test-copy
regression failed before the minimal ancestor protection, then passed. The
superseded full-suite attempt was stopped and retained; the final complete
suite after the fix passed 659 tests with two external-M1-data skips (396.38 s).
Initial sandbox run hit the already documented Windows pytest temp-directory
WinError 5; normal-permission fresh basetemp was used, without a code workaround.

Stage B next: add tests for reading the complete frozen CP1 Q files, verified
metadata/labels and independent error support, then connect the existing
processing/1.1 chain. C/D actual node AHRS and recorded downstream gate reports,
full external manifest pre/post audit, and E clean-lock/two-process independent
audit all remain unexecuted. Stage A tests cannot accept those obligations.

Final verification and the local source anchor are recorded in
[stage A delivery](../experiments/M5_CP4_STAGE_A_20260927/README.md).

## Stage B continuation

Complete stored Q replay is now implemented and tested; see [the stored demo entry](M5_STORED_DEMO.md). Its separate development report keeps CP4 OPEN. Retained B execution/audit is delivered; see [stage B evidence](../experiments/M5_CP4_STAGE_B_20260927/README.md). C/D/E acceptance remains separate and NOT RUN.

## Stage C continuation

The complete retained Node B runner and independent audit are implemented;
see [recorded node interface and explicit rejection probe](M5_RECORDED_NODE.md).
Its 21 focused tests and full694 passed/2 external-M1-data skips pass.
Complete standalone C execution and independent audit are delivered at source
lock84cbeed4; see [stage C evidence](../experiments/M5_CP4_STAGE_C_20260927/README.md).
CP4 stays OPEN; D/E have not run. The old M2 128-row excerpt is not used.
