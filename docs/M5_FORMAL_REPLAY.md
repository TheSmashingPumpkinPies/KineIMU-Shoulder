# M5.4 E — formal immutable replay collection and CP4 audit

Maintainer authorized the last E segment on 2026-09-27 (message names M4.5;
repository milestone is M5.4). Governing requirements: [replay plan](../M5_4_REPLAY_PLAN.md),
[frozen validation contract](../protocols/M5_VALIDATION_CONTRACT.md), and
[approved D quality segmentation](../protocols/M5_RECORDED_SEGMENTS_V1.md).

The validation-only `formal_replay` entry runs unchanged complete B/C/D
processors in each fresh independent Python process. B reads all four frozen
CP1 stored Q trajectories; C reads all 832 retained Node B observations;
D reads all 379196 original M1 observations with the approved explicit
null-row/independent-world policy. No new data is acquired.

Formal roots are frozen before launch:
`experiments/M5_CP4_FORMAL_20260927/run1` and `run2`. They must both be absent.
The external acquisition root and its eleven-member manifest remain read-only.
Any partial attempt remains immutable; a later retry requires a new root.

The E envelope has `formal=true`. Its unchanged B/C/D subreports retain
`formal=false` and CP4 OPEN because they describe individual processor
delivery. This intentional distinction preserves the original audited
semantics; a complete collection alone does not accept CP4.

Canonical envelope and all stage files carry identical source lock, source
map, runtime, configurations, original input hashes and complete product
support. Root paths, PIDs, commands, durations and logs are separate operational
evidence. Each process must start from a clean committed tracked tree.

The [independent E auditor](../experiments/M5_CP4_STAGE_E_20260927/audit.py)
does not import the new collection runner. It independently checks all 35
canonical products plus the outer digest file, both actual process identities,
complete source ZIP, required checks, unchanged original snapshots, and invokes
the existing complete B/C/D numerical auditors in six separate processes.
Their complete original-SI, quaternion, error-support and downstream-null
checks remain unchanged. Only that pair audit can emit CP4 PASS.

| CP4 requirement | Retained evidence and independent check |
|---|---|
| Original data immutable | Envelope input_before/input_after; launch snapshots; B/C source hashes and D eleven-member before/after audits |
| Every required input actually replayed | Each collection's B four-case, C one-case, D two-case reports; captured process commands, PIDs and exits |
| Missing evidence propagated | C/D numerical auditors check every downstream null, invalid flag, unavailable count/statistic and existing reason |
| Assumptions and evidence labels explicit | C/D calibration, world, heading and anatomical eligibility checks; D independent reset/partition audit |
| Synthetic truth, quantization and support | Each B audit checks frozen labels, sensor half-LSB bounds, counts, coverage and independently recomputed error scalars |
| Repeatability and complete outputs | E compares all 35 required products plus outer SHA256SUMS.txt; rejects missing, modified, duplicate or unlisted files |
| Source/runtime/configuration provenance | E checks clean source lock, submanifest bindings, complete source map/ZIP, runtime, pinned contracts/configuration and check logs |

Launch tools and retained checks are in
[E evidence](../experiments/M5_CP4_STAGE_E_20260927/README.md).
Use `.venv/Scripts/python.exe experiments/M5_CP4_STAGE_E_20260927/launch.py checks`,
commit valid source/check evidence, confirm clean lock and absent roots, then
use the same tool with `launch`. The launcher preserves actual command/exit
records and failure products. It never resumes or patches a consumed root.

Recorded calibration remains illustrative identity, node orientation remains
Assumed/Experimental, and no static-gravity/common-heading/anatomical accuracy
claim is made. Real-record shoulder metrics remain null and invalid under
missing evidence. CP4 replay acceptance leaves CP5 and overall M5 OPEN.
Hardware remains frozen; no physical action, firmware work or push applies.
