# M5.4 stage D — complete M1 dual USB recorded replay

The maintainer-approved [segmented contract](../protocols/M5_RECORDED_SEGMENTS_V1.md)
adds an explicit `--segmented` option for the retained B clipped/range-exceeding
observation. All original observations survive; rejected processed values are
null and eligible contiguous intervals initialize separate independent worlds.
Only first contiguous worlds enter the missing-evidence downstream probe,
with exact segment provenance and full original A diagnostic support. No
cross-world join/interpolation is performed. The strict default path described
below remains available and preserves its original whole-stream rejection.
Independent segmented auditor: `experiments/M5_CP4_STAGE_D2_20260927/audit.py`.

Development-only runner: `python -m kineimu_shoulder.validation.recorded_dual --output <new-root>`.
Set `KINEIMU_M1_RAW_ROOT` to the immutable M1 acquisition root. Production CLI
uses the frozen manifest hash and A/B anchors from the M1 bench and M2 tests.
Library anchor overrides support constructed tests only; they are not formal evidence.

All eleven SHA256SUMS members, plus the manifest itself, are checked before and
after execution. A mismatch fails; missing files or access block execution.
Outputs cannot be placed anywhere within the acquisition root or old evidence.
Failed/blocked products remain partial; retry requires a new output root.

Read every original packet/sample, counter, flag, host arrival and device timestamp.
Convert raw sensor axes to SI with the pinned M1 sensitivities; no interpolation,
resampling or short-gap reconstruction is applied. Reuse the stage C independent
node routine and its illustrative identity calibration (zero bias, no fitted
uncertainty; fit window `(0,1)` is only a schema placeholder). Apply explicit
identity R_NS, then the pinned imufusion AHRS on each original device timeline.
Initial q_WN `(1,0,0,0)` defines a separate arbitrary world per node.
Node orientations are Assumed/Experimental, never anatomical Validated.

The actual A and B outputs feed an explicit downstream rejection probe. Neither
q_WN has an anatomical R_NK transform. No segment-frame orientation, common yaw,
clock map, heading relation, alignment or bounded thorax drift is established.
The gate interface receives A's complete original timestamp vector only as
requested diagnostic support. This vector is **not** an established common grid.
Missing clock evidence rejects before interpolation or quaternion composition.
Host arrival is preserved as an observation and never used to synchronize.

M2 reports `clock_map_missing`; M3 and M4 retain `clock_or_heading_missing`.
Relative quaternions, elevation and speed are null with valid=false; repetition
counts and shoulder summary statistics remain unavailable. The missing evidence
list also records heading/alignment/drift absence; combined rejection does not
prove their individual gates (those are already tested separately).
Diagnostic `left/flexion` parameters are interface choices, not observed side
or exercise metadata. Requested A time span is Observed support, not a movement
duration. Actual independent-node AHRS execution proves processing completeness,
not motion accuracy, humerothoracic accuracy or clinical validation.

Canonical manifest, both complete node results, downstream and report have a
separate SHA256SUMS inventory. Launch binds exact HEAD/dirty status, full source
map, dependencies, contracts, anchors, adapter configuration and thread settings.
The independent [D auditor](../experiments/M5_CP4_STAGE_D_20260927/audit.py)
decodes raw packets, checks original/SI rows, directly recomputes pinned AHRS and
checks every unavailable output without calling the validation runner.

Exit 0 delivers development stage D only. CP4 remains OPEN until stage E runs
the entire B/C/D collection in two independent processes under a clean source
lock and audits all canonical bytes. Stop after D; CP5/M6 are separate.
