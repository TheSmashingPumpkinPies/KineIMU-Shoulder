# M2 Processing Contract — KineIMU Shoulder

Status: M2.0 convention lock, 2026-09-25. This contract governs processed
artifacts and numerical interfaces. It does not change the immutable M1 packet
format, the seven-column normalized table or public schema 0.1. A change to a
frame or multiplication convention requires a reviewed contract version.

Recorded D validation may explicitly partition clipping/range-ineligible rows
before applying the unchanged calibration API, under approved
[m5-recorded-segments/1.0](M5_RECORDED_SEGMENTS_V1.md) / ADR-011. Each eligible
contiguous interval initializes a separate AHRS world; ineligible rows retain
raw observations and null processed values. This is not calibration bypass or
a continuous orientation recovery. Strict M2 application remains as specified below.

## Units, arrays and source order

- One stream is one identified node and uninterrupted device-clock epoch.
  Sample arrays have shape `(N, 3)`, axis order X/Y/Z, float64, with finite
  acceleration in m/s² and angular velocity in rad/s. Quaternions have shape
  `(N, 4)` or `(4,)`, scalar-first `[w, x, y, z]`, finite, unit norm.
- Device timestamps are the authoritative integer `timestamp_us` values.
  Preserve original sample sequence, packet sequence, clock ID and epoch; do
  not synthesize time from nominal ODR or pair samples by row index.
- M1 signed counts first receive the declared count-to-SI scale **in sensor
  register X/Y/Z order**. Apply per-sensor acceleration calibration and gyro
  bias in that sensor frame. Then apply the explicit `R_NS` axis transform to
  both vectors and run AHRS on node-frame SI. The existing M1 raw adapter
  already produces node-frame SI for its original smoke-test contract; M2
  replay must expose sensor-frame SI before calibration and retain that adapter
  behavior for existing callers. Calibration is never fitted to unlabelled
  node-frame values and never silently inserted in the raw adapter.
- Raw bytes and timestamps remain immutable. Processed products carry source
  paths/SHA-256, node and epoch identity, firmware/configuration, calibration
  ID, axis and alignment IDs, backend/version and processing configuration.

## Frames and rotation convention

All frames use right-handed orthonormal axes and column vectors. `R_AB` maps
coordinates of a vector in B into A: `v_A = R_AB v_B`. `q_AB` denotes the same
**active** rotation in Hamilton convention. The implementation uses SciPy
`Rotation` for numerical rotation operations; the project boundary always uses
scalar-first `[w, x, y, z]`. `q` and `-q` represent the same orientation;
normalization does not silently repair zero, nonfinite or nonunit input.

```text
R_AC = R_AB R_BC       q_AC = q_AB ⊗ q_BC
v_A  = R_AB v_B        (rightmost rotation acts first)
R_BA = R_ABᵀ           q_BA = inverse(q_AB)
```

- `S_A`/`S_B`: each IMU's sensor register axes, with positive directions
  determined by its declared board configuration, not inferred from gravity.
- `N_A`/`N_B`: each node's declared board axes. `R_NS` is the M1 sensor-to-node
  transform and must be a proper rotation (`RᵀR=I`, determinant `+1`) for
  quaternion composition. A reflected axis map may be useful for raw data
  rearrangement but cannot be passed to AHRS as a 3-D rotation.
- `T`: thorax segment, +X anterior, +Y left, +Z superior (DATA_FORMAT.md).
  `H`: upper-arm segment, +Z proximal along the humeral long axis, +X
  anterior and +Y left in a declared arms-down neutral pose. This is a
  mathematical reference for synthetic fixtures, not measured anatomical
  alignment. Record test side and neutral-pose/alignment method before any
  anatomical interpretation; remounting invalidates the old alignment.
- `W`: the AHRS world/reference frame. Each node has an independently
  initialized world until a common frame and heading relationship is
  established. A common gravity direction alone cannot align AP/ML heading.

AHRS consumes node-frame signals and its adapter must emit `R_WN`. Fixed
segment-to-node alignments are applied **once after AHRS**:

```text
R_WT = R_WN(A) R_NT
R_WH = R_WN(B) R_NH
R_TH = R_WTᵀ R_WH = inverse(q_WT) ⊗ q_WH
```

`R_TH` expresses humerus vectors in thorax coordinates only when A and B share
a supported world/heading reference and a common timeline. M2 does not output
a validated humerothoracic angle from the M1 dual USB bench, which lacks
physical anatomical alignment and independently established pairwise timing.

## Time, gaps and clock mapping

- Within an epoch, times must increase strictly. Duplicate/reordered times,
  invalid sample values, counter gaps and resets are visible QC events; no
  adapter repairs them. A new epoch resets orientation/filter state. AHRS
  receives each positive observed `dt_s = (t_i-t_(i-1))/1e6` and an explicit
  initialization rule for the first sample. The caller declares `max_gap_s`
  in processed configuration; a longer gap invalidates or resets state, never
  becomes one giant hidden integration step. No numerical default gap is
  asserted before M2.3 validation.
- A dual-stream common time needs a per-node, per-epoch artifact specifying
  `t_common = a_i t_device_i + b_i`, its source/method, fit and validity
  interval, residual/uncertainty, clock IDs and held-out evidence. Host packet
  arrival or simultaneous capture start alone does not establish this map.
  An assumed mapping is labelled **Assumed/Experimental** through every
  derived result; missing or unsupported mapping blocks validated pairing.
- Resampling is a separate processed operation. Record grid, interpolation,
  gap limit, source hashes and validity mask. Do not interpolate across a
  declared long gap; no calibration or AHRS backend may hide resampling.

## Third-party backend boundary

These are required **adapter** contracts, not claims that the backend has
already passed M2 numerical validation. Pinned versions are in `uv.lock` and
`DEPENDENCIES.md`; current API smoke evidence is in `BACKEND_CONTRACTS.md`.

| Backend | Adapter input | Adapter output and checks | Exclusions |
|---|---|---|---|
| `imucal==2.6.0` | Finite sensor-frame `(N,3)` float64 accel m/s² and gyro rad/s; explicit sensor ID, axes, range/config, calibration ID and source hashes | Same sample count/order and units in `(N,3)` float64, with a versioned parameter artifact recording fit source/window, method, units, axes, validity domain and input hashes. Reject wrong sensor/config, nonfinite values and unsupported fit data. Verify actual application and JSON round-trip with injected known parameters in M2.2. | No segment alignment, timestamp changes, clock mapping or interpolation. API smoke alone does not prove estimated calibration accuracy. |
| `imufusion==1.3.3` | Finite calibrated node-frame accel `(3,)` m/s² and gyro `(3,)` rad/s per sample, with positive observed `dt_s`, declared initialization/reset and gap limit | Convert gyro rad/s → deg/s and accel m/s² → g only at this boundary. Call `Ahrs.set_sample_period(dt_s)` before each update; call `update_no_magnetometer(gyro_dps, accel_g)`. Convert returned quaternion to project `[w,x,y,z]`, normalize/check and independently verify its rotation direction and axes against known rotations before accepting `R_WN`. Reject invalid time, sample or state. | No inferred timing, resampling, anatomical alignment or absolute heading claim. Six-axis yaw is unobservable from static gravity and can drift. |

The backend frame direction was checked in M2.3 as described below. M2.2
confirmed that `imucal` applies the declared affine acceleration and gyro-bias
artifact in sensor axes. No backend convention leaks into core functions.

## M2.3 per-epoch orientation and fixed alignment

`kineimu_shoulder.orientation.estimate_orientation` accepts one calibrated
node-frame epoch: strictly increasing int64 device microseconds, finite `(N,3)`
acceleration in m/s² and gyro in rad/s, and a caller-declared positive
`max_gap_s`. The first output is the caller-declared unit `q_WN` (identity by
default); it receives **no invented integration period**. Each subsequent
update uses its observed device-time difference. A duplicate/reversal or gap
above the declared limit rejects the whole epoch; the caller must split and
restart explicitly. Every call creates a fresh AHRS. The adapter divides
acceleration by standard gravity `9.80665 m/s²` and converts gyro with
`180/π`, only at the imufusion boundary. It skips the backend startup mode so
initial motion is not silently suppressed, checks the backend quaternion norm,
then normalizes float32 backend output into project float64 `[w,x,y,z]`.

Pinned imufusion 1.3.3 direction was tested with independent physical-axis
fixtures: +Z angular rate for 1 s maps node +X to world +Y; stationary
specific force along node +Y converges to a +X quarter-turn mapping node +Y
to world +Z. Thus the output is accepted as active `q_WN` under this adapter
configuration. Known positive and negative yaw quarter-turns, variable observed
intervals, stationary tilt, reset and input rejection are automated tests.
These are synthetic numerical checks, not measured shoulder accuracy.
In the locked deterministic heading check, a stationary 10 s synthetic stream
with +1°/s uncorrected Z-gyro bias ends at +10° apparent yaw (within
`3e-5` Cartesian component tolerance). The zero-bias, +90°/s for 1 s
synthetic case ends at +90° within the same tolerance. These examples expose
the six-axis observability limit; they are not hardware drift estimates.

For a measured sensor-to-segment map `q_TS` (sensor vectors expressed in the
thorax segment) or `q_HS` (humerus segment), combine the declared proper
sensor-to-node rotation once as `q_NT = q_NS ⊗ inverse(q_TS)` or
`q_NH = q_NS ⊗ inverse(q_HS)`. `segment_to_node_alignment` performs this
conversion; `align_segment` then applies `q_WT = q_WN ⊗ q_NT` or
`q_WH = q_WN ⊗ q_NH` after AHRS. Alignment input must have documented segment,
test side, mounting/neutral method, ID and uncertainty in the processed
artifact; remounting invalidates it. The M1 bench has no measured anatomical
alignment, common heading or pairwise clock map, so its A/B outputs remain
independent node orientations. Six-axis yaw is unobservable from gravity and
may drift; `heading_observable=false` records this limitation on every result.

## M2.4 relative orientation on a declared common timeline

`kineimu_shoulder.relative_orientation.relative_orientation` is a processed
operation after per-node AHRS and fixed segment alignment. It accepts one
`SegmentOrientationStream` per node/epoch with original int64 device microseconds,
scalar-first unit `q_WT` or `q_WH`, node/clock/epoch/world identity and source
SHA-256. Callers supply a strictly increasing int64 common-time grid; the
function never pairs rows or host packet arrival times.

Each stream needs its own `ClockMap` with matching node, clock and epoch,
positive finite slope and finite intercept in `t_common_us = slope *
t_device_us + intercept_us`, a fit interval and an inclusive device-time
validity interval,
method/source SHA-256, uncertainty in microseconds, status (`supported` or
`assumed`), and a held-out residual for a supported map. A supported status is
an evidence claim by the supplied artifact; this numerical function cannot
establish it from two streams. The caller declares the maximum combined clock
uncertainty and interpolation gap. The two map uncertainties add as a
conservative bound. A separate `HeadingRelation` records `q_WaWb`, the
rotation from humerus world B into thorax world A, with both world IDs,
method/source SHA-256 and supported or assumed status. Identity quaternions in
independent worlds do not establish common heading.

For each grid time within both clock validity intervals and stream spans, the
operation applies spherical linear interpolation to each segment quaternion
using neighboring mapped sample times, then computes `q_TH = inverse(q_WaT) ⊗
q_WaWb ⊗ q_WbH`. Exact sample times use the recorded quaternion. No
extrapolation or interpolation over a declared long gap is allowed. Invalid
rows contain NaN quaternion components, a false validity mask and a reason
such as missing/incompatible map or heading, excessive timing uncertainty,
clock validity, stream span or interpolation gap. The result retains the grid,
both source hashes, maps, heading relation, interpolation method and limits.
Any assumed map or heading marks valid output `Assumed/Experimental`; supported
inputs yield `Derived`. Six-axis drift remains a limit even for supported
initial heading alignment. The M1 USB pair lacks the required pairwise clock,
heading and anatomical evidence, so it cannot be promoted to a synchronized
humerothoracic result by this operation.

## M2.5 offline replay example and M3 handoff

`examples/m2_offline_replay.py` writes canonical processed JSON and a QC/
provenance report outside `raw/` for a generated known-turn fixture and the
first 128 samples of a hash-verified retained M1 Node B capture. Both use
sensor-frame SI, an explicitly illustrative identity calibration artifact,
the declared identity `R_NS` and the same fresh six-axis AHRS settings.
`m2-offline-example/1.0` is an example-only processed format, not a revision
of the public M1 raw or normalized schema. Each artifact preserves original
device times, sample sequences, `q_WN`, scalar-first/active frame convention,
calibration parameters, source hash, gap limit and heading limitation. The
report identifies QC scope, dependency lock and output hashes. See
`experiments/M2_REPLAY_20260925/README.md` for exact commands and digests.

M3's anatomical metric input requires valid `q_TH` from the separate M2.4
relative-orientation operation, plus its two source streams, clock maps,
heading relation, alignment evidence, validity mask and reasons. A single
node's `q_WN` cannot be renamed `q_TH`. M1's USB pair lacks independent
pairwise clock, common heading and anatomical alignment evidence, so this
example emits no synchronized humerothoracic result.

## M2.1 immutable replay input

`kineimu_shoulder.io.m2_replay.replay_capture` takes one framed `.kimu` path,
an independently recorded SHA-256 digest, expected on-wire node ID, and an
explicit M1 count-scale/axis configuration. It reads the file without writing
to it, verifies the complete-file digest before decoding, invokes the M1
framing/packet codec and sequence QC, and returns per-epoch sensor-frame SI
with source path/hash, node ID, configuration, packet sequence/flags, host
packet receipt times, original sample sequence/flags/counts/device times and
the full QC report. The host times remain transport evidence only.

The replay boundary rejects malformed framing, invalid packet CRC, wrong node,
and duplicate/reordered device time within an epoch. Packet/sample sequence
gaps and counter anomalies remain in QC alongside unchanged sample order;
epoch changes split the output and reset the time frontier. It does not infer
a clock map, interpolate, calibrate, or apply `R_NS`. The older M1
`convert_raw_samples` still applies `R_NS` for its existing node-frame callers;
both conversions share the same count-to-SI scale.

## M2.2 sensor calibration and applicability

`kineimu_shoulder.calibration` defines `m2-calibration/1.0`, a per-node JSON
artifact. It records node and sensor IDs, both SI units, exact M1 count-scale,
range and axis configuration, accelerometer affine matrix/bias, gyro bias,
fit method/window, source SHA-256 values and a human-readable validity
statement. Its calculation is `a_cal,S = M(a_raw,S - b_a)` and
`omega_cal,S = omega_raw,S - b_g`; `imucal==2.6.0` applies those parameters
in sensor axes, then project code applies the declared proper `R_NS` once.
There is no timestamp, interpolation or segment alignment in this step.

Application rejects wrong node/sensor/configuration, nonfinite values,
explicit accel/gyro clipping, values outside the configured sensor ranges,
bad units and a reflected `R_NS`. Recorded data must supply its original
sample flags. `estimate_gyro_bias` additionally requires strictly increasing
device times, the caller's documented minimum samples/duration and explicit
limits for acceleration norm, per-axis acceleration variability and measured
angular-rate norm. The mean is only a zero-rate bias estimate under the
stationary assumption. The gate cannot distinguish a sufficiently slow
constant rotation from bias; its threshold and window must be reported with
any estimate. It is not a temperature or lifetime drift calibration.

`estimate_accelerometer_affine` requires at least six distinct, labelled,
known gravity directions expressed in the same sensor axes, full affine
design rank, no clipping, plausible reference norm and a maximum fitted
residual of 0.05 m/s². The 0.05 m/s² residual is a declared numerical
acceptance threshold for the current known-input gate, not a measured
hardware accuracy limit. It uses NumPy least squares to identify the affine
map; the pinned imucal application class is used for correction. The upstream
[imucal Ferraris guide](https://imucal.readthedocs.io/en/latest/guides/ferraris_guide.html)
describes a separate full six-position plus rotation protocol. A stationary
window alone cannot identify three-axis accelerometer gain, cross-axis terms
or bias. No such labelled multi-pose series, independent calibration reference
or temperature sweep exists in the immutable M1 dual USB bench. Therefore
M2.2 proves the numerical contract on injected synthetic truth and does not
publish physical accelerometer accuracy or transfer validity for those nodes.

`tests/integration/test_m2_replay_recorded.py` uses the retained 832-sample
Node B fixture. The optional external-bench gate
`tests/integration/test_m2_replay_m1_bench.py` reads the immutable 30-minute
A/B USB streams when `KINEIMU_M1_RAW_ROOT` names that root; it checks the two
manifest digests and independently audited counts/timestamp endpoints.

## Locked known-rotation fixtures and M2.0 gate

`tests/unit/test_m2_frames.py` records the following analytical fixtures before
M2.1 replay implementation. Each equality uses absolute tolerance `1e-12`
and zero relative tolerance in float64; this bounds roundoff for exact axis
quarter-turns and is not a sensor accuracy claim.

| Fixture | Independent expected result | Error caught |
|---|---|---|
| `q_X(+90°)=[√½,√½,0,0]`, `+Y` | `+Z` | handedness/sign |
| `q_Y(+90°)=[√½,0,√½,0]`, `+Z` | `+X` | axis/order |
| `q_Z(+90°)=[√½,0,0,√½]`, `+X` | `+Y` | axis/order |
| `q_X ⊗ q_Y` versus `q_Y ⊗ q_X` | `[½,½,½,½]` versus `[½,½,½,-½]`; mapped `+Z` is `+X` versus `-Y` | reversed composition |
| inverse `q_Z(+90°)` on `+Y` | `+X` | inverse direction |
| zero, nonunit or nonfinite quaternion | explicit `ValueError` | silent normalization |

The expected values follow Hamilton multiplication and the right-hand rule,
independently of the SciPy implementation. M2.0 exits when these tests, full
Python checks and documentation consistency pass and schema 0.1 is unchanged.

## M5.3 reference resolution and numerical clock endpoints — 2026-09-27

M5.3 exposed syntactically valid but unresolved map/heading source hashes.
`relative_orientation` now accepts optional `evidence_source_sha256`, ordered
A-map, B-map, heading. Callers obtain these from independently retained evidence
sources before accepting metadata and before mutations. Mismatch yields existing
clock_map_incompatible/heading_incompatible masks and no downstream values.
The reference source can differ from the motion/raw source; no raw-hash equality
is imposed on a separately measured map or heading artifact. Omission retains
the existing caller-attested M2 API; it does not verify artifact availability.
M5 CP3 supplies all three independent expected references. Acquisition schema
0.1, dataclass fields, frame conventions and existing reason codes are unchanged.

Mapping snaps to integer microseconds only within four float64 machine-epsilon
units of max(abs(mapped time), abs(intercept), 1). This removes arithmetic
roundoff at mathematical integer endpoints; it is unrelated to the caller's
timing uncertainty. Genuine fractional quantization residuals (including a
0.2 us short endpoint) still prohibit extrapolation. Relative and thorax stages
use the same rule, preserving original indices and interpolation provenance.

These fixes change evidence gating/numerical roundoff handling, not the frozen
AHRS, truth, seeds, budgets or raw streams. Test-first failures and reacceptance
are recorded in the CP3 unblock experiment.

## Optional explicit short-gap preprocessing — ADR-010

The authorized [M5 processing/1.1](M5_PROCESSING_V1_1.md) adds a named processed
reconstruction stage after calibration/axis conversion and before AHRS.
Original observed samples and timestamps are conserved; inferred transition
rows retain bracket indices, estimated device time, residual and assumptions.
This stage does not live inside an acquisition or AHRS adapter. The AHRS input
array now explicitly contains both observed and reconstructed processed rows;
its one-output-per-input-row contract, defaults and gap rejection are unchanged.
Original raw-time orientation accuracy is checked separately from inferred
rows. Full reacceptance is required under
[ADR-010](../docs/adr/ADR-010-explicit-short-gap-reconstruction.md).
