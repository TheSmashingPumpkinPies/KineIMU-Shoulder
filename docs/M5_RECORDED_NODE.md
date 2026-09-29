# M5.4 stage C — complete retained Node B

The validation-only `kineimu_shoulder.validation.recorded_node` entry reads all
208 packets / 832 samples of the retained stationary Node B KIMU stream.
Independent anchors come from the [compatibility record](../firmware/xiao_nrf52840_sense/evidence/node_b_20260913_compatibility.md)
and [replay plan](../M5_4_REPLAY_PLAN.md): SHA-256
`1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201`,
timestamps 257030578–264845581 us, packet counters 5867–6074,
sample counters 23468–24299, epoch 0. Counts, endpoints and QC are checked
before calibration or AHRS. All original flags, device times, counters and
host receive observations are retained. Host arrival is never used as a clock map.

```powershell
.venv/Scripts/python.exe -m kineimu_shoulder.validation.recorded_node --output <absent-development-root>
```

The existing raw-count adapter produces sensor SI, with 0.122 mg/LSB and
17.5 mdps/LSB. The existing imucal adapter applies an illustrative identity
calibration and identity R_NS. Zero biases are assumptions, not estimates
from this stationary record. Its `(0,1)` fit window is a schema placeholder,
as in M2.5; no fit or measured calibration uncertainty is claimed.
Pinned imufusion uses every observed device interval (maximum 0.05 s),
initial q_WN=(1,0,0,0), and an independent arbitrary world. Quaternions are
active node-to-world wxyz, unit norm. No R_NK, resampling, interpolation,
reconstruction, bias fitting or inferred shared heading is applied.
Node orientation remains Assumed/Experimental, heading_observable=false,
anatomical_eligible=false. Static gravity cannot supply complete yaw/AP-ML.
The capture has no motion ground truth or shoulder accuracy budget.

## Single-node downstream rejection

The production M2 relative API requires two nonempty, finite streams and has
no absent-node input signature. Stage C therefore names an explicit **single-node
self-input rejection probe**: the same B node/time/q_WN is supplied to both
gate slots, with original B identity intact and all clocks, shared heading,
anatomical alignments, heading/drift evidence absent. No A stream is generated,
and this diagnostic container is never called an aligned or paired observation.
Original B times serve only as the probe's requested rows; no common time grid
is established. The illustrative left/flexion arguments are interface parameters,
not an observed task or test-side claim. Missing-artifact context hashes are
explicit absence sentinels, not hashes of measured alignment/calibration evidence.

The actual `validation.replay.gate_report` calls M2 relative orientation,
M3 elevation/speed and M4 segmentation/metrics/thorax/summary. M2 returns
`clock_map_missing`; M3 returns `clock_or_heading_missing`; the actual downstream
records preserve invalid/null values through the final summary. The separate
missing-evidence inventory records absent thorax, both maps, common heading,
both alignments, thorax trace, heading and drift. These inventory facts are not
misrepresented as isolated stage rejection reasons: earlier clock gates mask
later gates in this real input. Stage A's independent supported fixtures cover
isolated missing-evidence precedence. No valid repetition count, ROM, shoulder
angle, angular speed or thorax excursion is inferred from this single node.

Fresh output protection reuses stage A's raw/source/acquisition/evidence rules.
Strict canonical JSON retains a manifest with exact HEAD, dirty flag,
source/contract/truth/manifest/lock hashes, runtime/backend/thread settings,
input anchors and configuration; result and report bind every product through
SHA256SUMS.txt. No output root or operational timing enters canonical bytes.
Source bytes are hashed before and after the entire calibration/AHRS/gate path.
Failures retain partials; missing data/access is BLOCKED. Exit 0 means only
stage C development gates passed, 1 means failure, 2 means blocked. CP4 stays
OPEN; stages D and E remain required. No hardware action or acquisition occurs.
