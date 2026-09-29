# M6 CP2 requirement coverage

Scope: CP2 complete sensor replay Demo; no M6/CP3–CP5 release acceptance.
Frozen specification: [Demo contract](../../docs/M6_DEMO_CONTRACT.md),
[release requirements](../../docs/M6_RELEASE_CHECKLIST.md).

| Obligation | Implementation / observable evidence |
|---|---|
| One command; hardware-free sample | `examples/m6_demo.py`; `validation/demo.py`; default packaged sample, all four trajectories; no external M1 root in formal process environment |
| Actual packet→QC→SI→calibration→AHRS→alignment→clock/heading/grid→M3→M4→proxy/summary | Existing `export_stored` / `run_stored` / `_session` unchanged; `processed.json.gz`, `derived.json.gz` per trajectory; generator/packet writer blocked in real pipeline integration test |
| Complete input counts and QC | Each of eight streams 538 packets / 2,151 samples, full sequence and 0–21,500,000 us endpoints; independent node/frame/calibration checks in `audit.py` |
| Numeric gates and independent labels | Original clean S/Q individual/aggregate/support budgets remain gates; independent CP3 O/F/T arithmetic auditor invoked for every trajectory; 27,160 recomputed error scalars per full four-Q run |
| Repetition/support/coverage | Each truth=valid=3, missed=false=0; relative/recall/proxy coverage=1; elevation support=1,651, interval-speed support=1,650; independent labels and input audits compared |
| Eight metric families / readability | `summary.md`: core family tables first, full strata/phases/proxy extrema/gate errors retained in collapsible details; scalar unit/valid/reason/evidence/anatomical flag and context definition versions preserved |
| ROM semantics / units / null | Display reads actual exported means, rad→deg explicit; rad/s and s/us retained; sample SD ddof=1; invalid/null remains unavailable with its original reason; tested by altering a test-only derived artifact |
| Evidence domain | synthetic, anatomical_eligible=false; construction assumptions remain Assumed; no clinical/GL/scapular or longitudinal rehabilitation score |
| Original M5 status | report `passed=false`, CP4 OPEN, formal=false retained; M6 demo_passed checks own four-case/input/inventory/hash gates |
| 26-file product inventory | 22 canonical replay products + inner index + run + summary + top index; exact inventories checked independently; no capture generated |
| Provenance / runtime | run HEAD/dirty/source and lock hashes, actual Python command, 25 before/after input hashes, runtime/thread configuration, timestamps/PID, product hashes and failed gates |
| Two-process equality | Formal pair at same clean source lock; all22 canonical products, inner index and summary equal; top24 hashes equal; run comparison uses only six declared process-field exceptions |
| Strict failures | Missing/tampered input, unavailable dependencies, usage, unsafe/existing output, junction/raw/source ancestors, interrupted/blocked/mixed failures; meaningful NOT RUN reasons and retained partial roots |
| Integrity-negative controls | Incomplete success claim rejected; modified machine product rejected; undeclared run field rejected even with independently repaired checksum index |
| Raw / historical evidence preservation | `inputs-before.json` and `inputs-after.json` bind all37 original files / all28 packaged sample files; tracked status and scoped diff protect existing production/firmware/schema/threshold/dependency sources |
| Required checks | Check records/logs for full pytest with existing external M1 root, focused Demo without it, full Ruff, strict mypy, docs/archive hashes, whitespace and pinned build |
| Platform and remaining release gates | Actual Windows pair; Linux NOT RUN, CI command is configuration only; CP3 benchmark, CP4 license/citation/packaging, CP5 clean clone/fresh environment and remote distribution remain independent |

Formal execution results, source lock, retained roots and exact command/exit records
are finalized in README and machine evidence after the pair passes. Coverage rows
name checks; they do not substitute for their execution or committed-byte proof.
