# M5.4 stage C — complete retained Node B

Stage C delivered at development scope. Complete retained Node B replay and
independent audit both exited0 at exact source/tool lock
`84cbeed40bf357ca686316c2195293215335cd6e`, with a clean tracked launch and
formal=false. Full694 passed/2 external-M1-data skips (613.99s), captured exit0;
focused21, Ruff, strict mypy29, docs and whitespace pass.
[Verification and retained logs](verification.json) record actual commands,
exits, source/product hashes, test-first red/green and the initial corrected
test-field typo. No production numerical code changed. CP4 remains OPEN.

The [recorded node contract](../../docs/M5_RECORDED_NODE.md) binds complete
208 packets/832 samples, original times/counters/flags and identity-example
calibration/independent node AHRS. The explicit same-B rejection probe calls
actual M2/M3/M4 without inventing A, clocks, heading or anatomical alignment.
It is a rejection-only diagnostic, not a paired/aligned stream or shoulder
analysis. Node orientation is Assumed/Experimental; yaw is unobserved and
motion accuracy is unavailable. Independent audit redecodes every raw count,
checks SI and recomputes all pinned AHRS quaternions directly, then checks
all downstream null values and stage reasons, inventory and source bindings.
Seven rehashed product-corruption controls fail independently. The actual audit
checks all832 AHRS quaternions and downstream rows, all208 packet/832 sample
original counters/times/flags/arrival observations, sensor and node SI,
and all3 canonical products. Source hash before/after replay and audit is
`1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201`.
QC has zero issues; complete span257030578–264845581us, no cropped excerpt.
M2 returns clock_map_missing; M3 and final summary retain
clock_or_heading_missing. Counts, ROM, speed and thorax metrics remain null
and invalid. The requested original-time probe span remains Observed; it is
not a movement duration or established dual-node common grid.

Retained [report](../M5_CP4_STAGE_C_NODE_B_20260927/report.json),
[launch manifest](../M5_CP4_STAGE_C_NODE_B_20260927/manifest.json),
[complete result](../M5_CP4_STAGE_C_NODE_B_20260927/cases/REC-NODE-B/result.json),
[independent audit](audit.json) and
[exact source-byte snapshot](source-lock-84cbeed4.zip) remain immutable.
The snapshot verifies every launch-hashed byte independently of Git newline
normalization; restore its bytes at the source lock when reproducing the original
audit, including the launch-time plan before subsequent progress updates.
The [committed-byte proof](committed-evidence.json) independently verifies all25
artifact Git blobs against disk at retained-evidence commit
`70d4dda8bcc55242e936242110667db52be93dda` and all40 exact source ZIP entries.
Use all native thread variables1 and previously absent output/audit paths:

```powershell
.venv/Scripts/python.exe -m kineimu_shoulder.validation.recorded_node --output <new-development-root>
.venv/Scripts/python.exe experiments/M5_CP4_STAGE_C_20260927/audit.py --run <new-development-root> --output <new-audit.json>
```

Stage C is not CP4 acceptance; D/E, CP5 and overall M5 remain OPEN. C stop reached;
next authorized continuation is D's complete external11-file M1 dual-USB
manifest and independent node AHRS/downstream-unavailable replay. Hardware
frozen; no acquisition, physical
operator action, raw/schema/production/backend/truth/seed/gate changes or push.
