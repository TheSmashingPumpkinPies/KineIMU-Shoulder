# M5 Validation Contract — KineIMU Shoulder

Version: `m5-validation/1.0`. Frozen at CP0 on 2026-09-26 (Asia/Shanghai),
before M5 generators, oracles or acceptance runs. Governing scope:
M5 plan (complete record retained in the local evidence archive), [acceptance](../ACCEPTANCE_CRITERIA.md),
[M2](M2_PROCESSING_CONTRACT.md), [M3](M3_KINEMATICS_CONTRACT.md) and
[M4](M4_EXERCISE_CONTRACT.md). Independent constructions and case IDs:
[M5 known sensor motions](../tests/fixtures/M5_KNOWN_SENSOR_MOTIONS.md).
This is a validation-only contract; public acquisition schema 0.1 is unchanged.
CP0 passes specification review only. CP1–CP5 require future executable evidence.

## Independent truth and execution boundary

Validation code belongs in `kineimu_shoulder/validation/`, tests and experiments.
Reuse existing replay/calibration/AHRS/relative/M3/M4 interfaces. No new rotation,
filter, segmentation or calibration algorithm is authorized by this contract.
The generator may use NumPy/SciPy to construct inputs. The oracle must obtain
expected vectors, rates, boundaries and summaries from the scalar trigonometric,
matrix and integer-time equations in the fixture, without importing production
frames, orientation, relative orientation, shoulder, exercise or thorax routines.
Do not share generator rotation/derivative helpers with the oracle. SciPy may
cross-check truth, but cannot be its sole source when it is also the input source.
Production outputs never populate expected values or labels.

Two paths run separately with explicit source type `synthetic`:

- E: exact post-alignment dual orientations, isolating downstream M2.4/M3/M4.
  Retain all existing M3/M4 tolerances and fixtures without modification.
- S: sensor-frame SI observations → declared calibration → R_NS → fresh AHRS
  → fixed post-AHRS alignment once → explicit clock/heading/grid → M3/M4.
  Q: the same source quantized and framed as M1 demo recordings, then replayed
  through S. Q has its own input/count provenance, and uses the S clean budgets.

Expected continuous truth, nominal-grid labels and observation-grid labels are
separate artifacts. Jitter/loss never edits the continuous trajectory or its
nominal-grid rep denominator. The observation-grid oracle explains sampling
effects; acceptance timing errors are against frozen nominal-grid labels.
Orientation/elevation/speed row errors use truth at that row's true common time.
Timestamp-error cases retain true times separately from the claimed timestamps.

## Observation model, frames and clocks

Use right-handed column vectors, active scalar-first Hamilton quaternions.
Let K=T for A and K=H for B; R_AB maps B into A. World gravity acceleration
is g_W=(0,0,-9.80665) m/s². Sensor origin has zero linear acceleration and
zero lever arm in this ideal observation model (not a human-mounted sensor).
There is no centripetal/tangential term, magnetometer or anatomical accuracy claim.

```text
R_WN = R_WK R_NK^T;  R_WS = R_WN R_NS
f_S = R_WS^T (0,0,+9.80665)          [specific force, m/s²]
[omega_S]_cross = R_WS^T dR_WS/dt   [body rate, rad/s, true common seconds]
f_raw,S = M^-1 f_S + b_a + n_a
omega_raw,S = omega_S + b_g(t) + n_g
f_cal,S = M(f_raw,S - declared_b_a); omega_cal,S = omega_raw,S - declared_b_g
f_N = R_NS f_cal,S; omega_N = R_NS omega_cal,S
R_WK,estimated = R_WN,AHRS R_NK     [fixed alignment applied exactly once]
```

At rest with identity axes f_S=(0,0,+g). Axis permutations/alignment are
nontrivial proper rotations fixed in the fixture. Initial q_WN is derived from
the known initial pose, explicitly synthetic, never inferred from gravity.
Default M is identity, biases zero. Known-parameter and independent stationary
calibration controls below override only the declared fields.

Nominal true sample times are integer microseconds, t_i=10000*i (100 Hz),
including both session endpoints. SI S uses continuous rates evaluated at the
sample time, with the LEFT derivative at piecewise-linear knots: sample i>0
represents the interval ending there. Sample 0 has no invented integration dt.
For mixed-axis curves use the analytic body rate at the right endpoint; their
discretization error is tested at 100/200 Hz in CP1, not hidden as exact integration.
No ideal sample is called a measured 104 Hz hardware observation.

For drift cases d_A=round_even(t), d_B=round_even((1+rho)*t+250000) us;
exact reference maps are a_A=1,b_A=0; a_B=1/(1+rho), b_B=-250000/(1+rho).
Retain sub-microsecond rounding residuals. Map uncertainties are 1 us per node,
held-out residual <=1 us, combined limit 2000 us. Supported status identifies
synthetic construction, not physical measurement. Identity common-world heading
relation is a known synthetic input. Device dt still drives the unchanged AHRS;
a correct downstream clock map does not silently correct its integration skew.
Default rho=0 and both device offsets zero outside clock cases.

Use an explicit common grid at 10000 us, no extrapolation, SLERP bracket gap
limit 50000 us; M3/M4 max_sample_gap_us=50000; AHRS max_gap_s=0.05.
Equality passes each existing gap rule. AHRS rejects the whole unsplit epoch
for bad time or over-limit gaps; no automatic slicing/reset to salvage a rep.
Post-AHRS grid interpolation is a named processed stage with original brackets,
indices, masks and maps retained. Relative source and thorax trace bindings match.

## Frozen processing and calibration controls

Use CPython 3.12.14, pinned `uv.lock`, imufusion 1.3.3 and imucal 2.6.0.
Call the existing `estimate_orientation` unchanged: fresh Ahrs per node/epoch,
explicit initial quaternion, skip_startup, no magnetometer, no set_settings
override, no additional filtering or gyro-offset estimator. Thus configuration
is the pinned backend's default plus exactly these existing adapter calls.
Retain package/adapter/lock hashes; CP1 must record the installed backend's
effective defaults if its API exposes them, otherwise mark them not exposed.
Do not guess gain/rejection settings. A backend/configuration change invalidates
comparison and requires a versioned rerun.

Every session has a separate stationary source/calibration window [0,5] s,
evaluation begins at 5 s and includes remaining quiet rest/confirmation tails.
These 5 s are excluded from metric-error/coverage denominators and never hide
later failure. Reset only at actual epoch boundaries. Report first-row and
end-of-warmup orientation errors separately. Known initial pose controls do
not claim convergence from an unknown tilt; existing M2 stationary-tilt tests
remain the separate convergence evidence.

C-APPLY injects M=diag(1.02,0.98,1.01), b_a=(0.02,-0.01,0.03) m/s² and
b_g=(0.001,-0.002,0.003) rad/s into both sensors, supplies exact parameters,
and checks recovered SI within 1e-12 absolute per component (unquantized).
C-FIT estimates only gyro bias from the independent [0,5] window: minimum
500 samples, minimum 4 s, |norm(f)-g|<=0.1 m/s², each-axis SD<=0.05 m/s²,
gyro norm<=0.05 rad/s. Noise-high plus constant bias-low/high are the fit cases.
Bias residual norm <=0.001 rad/s is the predeclared estimation gate; then W
metric gates apply. No acceleration affine fit from one static pose, no fit on
evaluation motion, no recalibration of ramps or heading drift during evaluation.
The existing six-labelled-pose M2 test supplies affine-estimation coverage.

Use complete `m4-thresholds/1.0` from the M4 contract, with only the declared
50000 us gap and max_thorax_drift_rad=pi/180 (1 degree) limits supplied here.
No adaptive thresholds, smoothing, interpolation of crossings or clinical norms.

## Predeclared numerical gates

All comparisons use absolute error, zero relative tolerance unless a formula
below explicitly defines a bound. Counts/reasons/keys are exact, never fuzzy.
The clean and working budgets are engineering acceptance targets set before
running M5; they are not measured backend, hardware or clinical accuracy.

| Quantity | E exact | S/Q clean C | Working perturbation W |
|---|---|---|---|
| Elevation/peak; proxy extrema/magnitude | 1e-10 rad | pi/180 rad | pi/60 rad |
| Per-node orientation geodesic error | 1e-12 rad cross-check | pi/450 rad | pi/180 rad |
| ROM | 1e-10 rad | pi/90 rad | pi/30 rad |
| Each interval speed and per-phase/rep max and time-weighted mean | 1e-10 rad/s | pi/90 rad/s | pi/30 rad/s |
| Start/end/confirmation boundary absolute offset; peak-support distance | Exact integer us / earliest peak | 50000 us | 100000 us |
| Rep/phase/hold/rest duration absolute error | 1e-12 s | 0.10 s | 0.20 s |
| ROM range and sample SD | 1e-10 rad | 2*pi/90 rad | 2*pi/30 rad |
| Plane fraction | 1e-12 | 0.02 | 0.05 |
| Relative valid-duration coverage and valid-rep recall | Exact fixture | 1.00 / 1.00 | >=0.98 / 1.00 |
| Thorax-proxy coverage among eligible relative reps, for supported drift cases | Exact fixture | 1.00 | 1.00 |
| False valid reps; missed truth complete reps, ordinary in-plane cases | 0 / 0 | 0 / 0 | 0 / 0 |

Angle gate rationale: allocate the clean 1-degree downstream budget to two
node orientation errors (0.4 degree each) plus 0.2 degree grid/quantization
reserve. W allocates 1 degree/node plus 1 degree timing/noise reserve.
Each node must fit its allocated 0.4 degree C / 1 degree W sub-budget.
ROM involves two extrema, so it receives the conservative 2*angle bound;
peak/elevation retain the single-angle bound. Signed proxy extrema use it too;
proxy magnitude max(abs(extrema)) has the same bound. These are targets,
not a proof that every arbitrary 3-D decomposition meets that sensitivity.
Only the fixture's nonsingular small-angle thorax trajectories use these gates.

At 100 Hz, crossing discretization <=0.01 s per boundary. The slowest
ordinary baseline slope is 35 degrees/s (70 degrees in 2 s), so 1 degree
adds <=0.0286 s crossing uncertainty and 3 degrees <=0.0858 s. Rounded
0.05/0.10 s boundary targets and two-boundary 0.10/0.20 s duration targets
cover these sources. M4 hold ownership can move at both ends; test it separately,
do not infer hold accuracy from rep duration. The physical maximum plateau
is a set: S/Q peak-time error is distance to [plateau_start,plateau_end], with
the table's boundary budget. Also report earliest-peak offset diagnostically;
a tiny numerical drift can choose a later plateau row. M4 still returns its
earliest *estimated* maximum unchanged. E asserts the earliest exact row.
S/Q phase durations are compared to the analytic ownership evaluated using
the estimated peak row within that plateau (hold removes plateau intervals),
and retain separate nominal earliest-peak phase errors as diagnostics.
2/6 degrees/s speed budgets
are separately frozen because differentiation amplifies time/noise errors;
angle accuracy alone cannot prove them.

Q uses ±4 g (0.122 mg/LSB) and ±500 degrees/s (17.5 mdps/LSB). Half-LSB
component bounds are 0.00059820565 m/s² and 0.00015271631 rad/s;
three-axis norm bounds are sqrt(3) times these. Deterministic ties-to-even
quantization, no clipping saturation to hide an error. Generate via the existing
M1 codec, 4 samples/packet except a final 1–4-sample packet. All original
sample/packet counters start at 0 and remain unchanged after deletion masks.
Store q-truth separately; it is never packed as a measured IMU channel.

Summary mean/max inherits per-rep error epsilon; ROM range <=2*epsilon;
sample SD <=2*epsilon conservatively (n>=2). Use ROM epsilon=2*angle bound
for those formulas and the table's range/SD bounds.
CV is checked against its analytic truth with bound
`delta_sd/(mu-epsilon) + sd_truth*epsilon/(mu*(mu-epsilon))`, where
delta_sd=2*epsilon and mu is the positive truth mean ROM. If mu<=epsilon,
only existing availability/reason gates are asserted. Cadence n/T error bound
is `n*delta_T/(T*(T-delta_T))`, delta_T=n*duration_budget and T>delta_T.
Longitudinal difference error <=sum of the two mean budgets; denominators,
sample SD n-1, phase time conservation and comparability keys match exactly.
Zero/one-rep and near-zero-CV controls retain M4's exact unavailability rules.

No-match errors are null, never zero. W must satisfy every error, evidence,
coverage and count gate for EVERY seed. Averaging away a failed seed is forbidden.
Quiet/wrong-plane/partial/evidence-negative cases use their explicit fixture
expectations instead of requiring valid-rep recall from a zero denominator.

## Finite perturbation matrix and repeat unit

Unit: one trajectory × condition × target × seed full session. Frames and
within-session reps are not independent replicates; no confidence interval or
population-generalization claim is made from this finite design.
Trajectory IDs and durations are fixed in the fixture. B={F90,AL90,AR90};
long counterpart F90L lasts 300 s after warmup, with the same repeated motion.
Baseline controls include all fixture trajectories, on E and S; Q uses F90,
AL90, AR90 and T-MIX. All deterministic cases use seed=0.
Stochastic cases use the complete seed set {1103,2207,3301,4409,5519}.
NumPy Generator(PCG64(SeedSequence([seed,node_code,factor_code]))) is frozen;
node codes A=1/B=2; factor codes accel=11,gyro=12,sample-jitter=21,
timestamp-jitter=22. Draw full original arrays before masking, independent
per-node/per-axis streams in row-major (N,3) order. Accel/gyro normals are
independent zero-mean, untruncated; stated sigma is per axis. Jitter draws
integer offsets uniformly inclusive [-J,J] us, with endpoints and knots fixed
at 0 offset; never redraw to repair bad ordering.

Targets A, B, SAME (both +), DIFF (A+,B-). Noise uses A/B/SAME only and
SAME still has independent random streams. Bias direction is each sensor's
+Z unless explicitly marked heading-body injection. All other factors zero.
Canonical run order: trajectory ID, condition ID, target in A/B/SAME/DIFF
order, ascending seed; fresh pipeline state per session removes order effects.
CP1 must expand and retain the COMPLETE case manifest before CP2/CP3 execution.
IDs are `trajectory/condition/target/seed`; no adaptive additions to the formal set.

| Condition IDs / levels | Injection and expansion | Class / expected gate |
|---|---|---|
| N-A-L/H/X: sigma=0.005/0.02/0.20 m/s² | Accel SI; B × A/B/SAME × five seeds | L/H W; X stress |
| N-G-L/H/X: sigma=0.001/0.005/0.05 rad/s | Gyro SI; same expansion | L/H W; X stress |
| B-C-L/H/X: 0.002/0.02/1 degree/s = pi/90000,pi/9000,pi/180 rad/s | Constant sensor-Z residual; B and F90L × all four targets; seed0 | Short L/H W; long L W, long H/X stress; short X stress |
| B-R-L/H/X: end bias 0.004/0.04/2 degrees/s | b(t)=end_bias*(t-5)/evaluation_duration, zero during calibration; same expansion | Short L/H W; long L W; long H/X stress |
| J-S-L/H/X: J=100/1000/6000 us | Actual sample time changes; reevaluate force/rate at true times; B × A/B/SAME × five seeds | L/H W; X stress (reject if nonmonotone) |
| J-T-L/H/X: J=100/1000/6000 us | Claimed timestamp changes, observation time unchanged; same expansion | L/H W; X stress; negative dt rejects epoch |
| L-S-ONE/PER/BURST | On B trajectories, each target A/B/SAME; delete B's first-rep peak-start row (same physical row for A), or every 100th original sample i>500, or rows [peak_us-20000,peak_us+40000] inclusive | ONE/PER W; BURST gap>50ms rejects epoch; exact missing counts |
| L-P-ONE/PER/BURST | Q packet loss, B trajectories × A/B/SAME; delete packet containing first peak, every 25th packet p>125, or that peak packet and next packet | ONE/PER W (50ms equality); BURST rejects epoch; sample and packet losses distinct |
| D-C-0/L/H/X: rho=0/±100/±500/±5000 ppm | B and F90L, B target, exact map and wrong identity-scale map controls; seed0 | Exact 0/L/H W; X stress; wrong map diagnostic stress, never invent evidence |
| D-H-L/H/X: yaw-rate=0.002/0.02/0.2 degrees/s | B and F90L × all targets; two separate paths: sensor body-rate drift and post-alignment world-yaw drift; seed0 | L W; short H W; long H and X stress; proxy bound gate below |
| I-NB | N-A-H + N-G-H + B-C-H, B trajectories × DIFF bias/SAME noise × five seeds | Short W; compare all matched single-factor controls |
| I-JL | J-S-H + L-S-PER on S, B trajectories × SAME × five seeds | W; integer nominal indices define masks |
| I-HD | D-H-H at 30 s and 300 s, F90 truncated/repeated, DIFF; seed0 | 30s W; 300s stress + proxy drift exceeded |
| C-APPLY / C-FIT | F90, AL90, AR90; apply seed0; fit N-A-H+N-G-H+B-C-L/H, SAME, all five seeds | SI gate / fit gate plus W metrics |

The unperturbed matched control is mandatory for every trajectory/input path.
Periodic masks mean i%100==0 with i>500, or p%25==0 with p>125,
respectively; indices are zero-based and endpoints are not exempted from loss.
Packet containing a nominal peak at sample i has p=i//4. Burst sample masks
use the nominal first-peak time, independent of actual/claimed jitter.
Clock levels run both signs; the zero level runs once. B-R time is true common
time; calibration never removes future ramp. For D-H sensor injection add
`R_WS(t)^T*(0,0,yaw_rate)` to omega_S, making the disturbance world-vertical.
For the isolation path left-multiply R_WK by R_Z(yaw_rate*(t-5)), never inject
that as an actual sensor observation. Their outputs need not agree under
acceleration feedback; report both mechanisms explicitly.

Proxy evidence uses the *known injected yaw bound*, abs(rate)*covered_duration,
not observed small estimated drift. <=pi/180 passes; above it gives
`thorax_drift_exceeded` for A-affected proxy cases. No A disturbance means its
bound is 0; B-only yaw can still corrupt relative plane/angle and is reported.
Common yaw is a relative-motion invariance on the exact E isolation path,
but may still fail world/proxy evidence. Six-axis AHRS cannot automatically
detect arbitrary hidden gyro bias or a dishonest clock map. Stress cases of
those types require retained errors/coverage and an explicit unobservable
limitation, not a fictional production rejection or a new safety heuristic.

## Deterministic boundaries and evidence-negative matrix

GAP tests remove consecutive rows so retained device gaps are 49999,50000,
50001 us; observations and oracle use the explicitly irregular grid. Test
AHRS rejection separately from E's downstream interpolation-gap masks.
Also test duplicate/reverse time, reset epochs, empty/one-row, nonfinite,
zero acceleration, configured range exceedance and explicit clipping flags.
No error produces valid zeros; exact upstream errors are preserved by the
runner as stage, exception type/message or returned reason. Exception prose
is diagnostic; returned reason codes must match existing M2/M3/M4 exactly.

Evidence cases run F90 E/S: remove each map, heading, each alignment or thorax
trace; wrong node/hash/epoch/world/side; map expired outside covered window;
combined uncertainty 1999/2000/2001 us; alignment expired/remounted/assumed;
heading/map assumed; thorax drift 1 degree ±1e-6 rad and equality; drift window
not covering the rep; thorax singularity/branch crossing; comparison remount,
backend/threshold/source-type/evidence change. Unsupported global evidence
blocks M3/M4; missing proxy evidence blocks proxy only. Assumed valid numbers
retain Assumed/Experimental and anatomical_eligible=false. Synthetic supported
records retain source_type=synthetic and anatomical_eligible=false.
Boundary M4 thresholds use exact E fixtures C/P/T/U from M4, not noisy S
inputs expected to reproduce an equality after floating-point AHRS integration.

Freeze evidence mutation IDs `EV-<mutation>`: map-A/map-B/heading/align-A/
align-B/trace missing each in isolation; each source identity field mutation
uses node role swapped, hash all-zero, epoch+1, world ID with `:wrong` suffix,
or opposite side. Expiry sets the affected map/alignment coverage end to
4999999 us (before evaluation); remount=true; assumed changes only status.
Uncertainty controls set A=1000 us and B=999/1000/1001 us. Drift controls
set bound pi/180-1e-6, pi/180, pi/180+1e-6 rad; uncovered window ends1us
before the first rep end. Singularity/branch and comparison mutations reuse
exact M4 T8/T9/U7 constructions and their existing expected reason codes.
Every field mutation is a distinct case with its matching unchanged control,
on F90 E and S. Malformed field values are input-error controls, not fabricated
supported evidence. Prior contract fixtures remain the source for exact reasons.

## Matching, errors and coverage

Truth reps have immutable physical-support ID and nominal M4 start/end labels.
Match emitted candidates one-to-one in time order to a truth physical support
using intersection-over-union >=0.5; ties choose earlier truth ID. Excluded
candidates can match for diagnostics but never count as valid recall. Retain
unmatched truth IDs (missed), unmatched valid candidates (false), unmatched
excluded fragments and all duplicate overlaps. A censored truth support is
separately marked, not included in complete-rep recall.
Known wrong-plane truth has complete physical cycles but zero eligible truth
reps and requires the explicit plane exclusions. Quiet has zero physical cycles.

Coverage duration denominator is full evaluation-window elapsed true common
time, including lost samples/gaps/invalid segments. Numerator is valid M3
adjacent-duration support on the common grid, bounded by that window;
valid+invalid duration must conserve the denominator. PARTIAL explicitly uses
its frozen cropped analysis window as denominator, with warmup still excluded.
Report original sample
retention separately. Rep recall denominator is ALL eligible complete truth
reps; proxy coverage denominator is eligible relative reps. Report both lost
observations and lost numeric outputs; null denominator yields null coverage.
Metric errors on matched valid reps cannot substitute for coverage/count gates.
Retain per-row/per-interval and per-rep signed/absolute errors, maxima and RMSE
with n/support; max gates above govern, not just mean/RMSE.
Compare speed at the estimated endpoints and independently frozen truth endpoints
as separate rows, exposing boundary-shift effects instead of silently relabelling.

## Immutable replay and report/launch protocol

Q demo replays F90/AL90/AR90/T-MIX through the full chain with synthetic
maps/heading/alignment and independent labels. Recorded Node B fixture and
external M1 root `<external-data>/kineimu_m1_usb_30min_20260925_01` (selected through
KINEIMU_M1_RAW_ROOT) run read-only through QC, illustrative identity calibration
and independent node AHRS. Do not fabricate pairwise timing, common heading,
anatomical alignment or drift evidence. Shoulder outputs remain unavailable;
real replay has no motion-error ground truth and no shoulder accuracy budget.
Pinned file digests/counts/endpoints come from the committed M2 replay tests
and M1 manifest/audit, not an earlier derived M5 report. Hash before/after all
reads; no new acquisition. Actual external execution is mandatory for CP4;
missing access/data means BLOCKED/NOT RUN. Pytest skip cannot pass it.

Future CP2/CP3/CP4 launch requires committed contract/truth/case-manifest and
generator/oracle/runner hashes, clean intended tracked work, lock/env identity
and a previously absent output directory outside raw. Atomically claim fresh
root, reject existing roots/overwrite and paths inside source raw trees.
Keep partial outputs on failure; never repair/append a formal run to make PASS.
Reruns have new IDs with links to all previous failed evidence. Each checkpoint
requires two independent processes' canonical numerical bytes to match.

Freeze validation-only `m5-report/1.0` with required records:

- manifest: contract/truth/config/case-manifest/generator/oracle/processing/lock
  SHA-256, exact Git commit and dirty status, platform/runtime/backend versions,
  source file map/hashes, trajectory/condition/target/seed, calibration and frames,
  times/maps/grid/interpolation/gap/evidence and quantization metadata;
- source + annotations: continuous parameters, nominal/actual/claimed times,
  original counters, loss masks, independent physical and nominal M4 labels;
- processed + derived: existing M2/M3/M4 records, SI units, validity/reasons,
  source type, all assumptions and evidence; no new public acquisition fields;
- case results: intended class C/W/rejection/stress, stage disposition, all
  errors/supports/counts/coverage/failed gates, matched/unmatched IDs and reasons;
- summary: requirements→case IDs→artifact hashes, every seed row, worst cases,
  failed/not-run counts, explicit known limitations and checkpoint disposition.

Canonical JSON: UTF-8, LF, sorted keys, indent=2, final newline, allow_nan=false;
unavailable numeric values null+valid=false+reason. No wall clock/run duration/
absolute output root in canonical products; save operational logs separately.
Output digests go in a separate SHA256SUMS manifest excluding itself; a file
cannot include its own hash. Exact commit is the pre-run code lock. Run-root
manifest binds all outputs after completion; partial manifest is labelled partial.
Exit 0 only when every required case ran and all C/W/rejection/evidence gates
passed. Exit 1 for failure; exit 2 for blocked required input/configuration.
Stress counts as executed with documented limitation, never as accuracy PASS.
An expected rejection case passes only when its predeclared rejection occurs
at the required stage with no rescued downstream numeric values. Unexpected
exceptions are failures, even in a stress case, unless the contract explicitly
allows the observed bad-time/gap rejection.
Synthetic labels remain explicit; no automatic `Validated` upgrade of anatomy.

Any specification correction requires a new version/review, preserved prior
hashes/failures and declared rerun scope before execution. Never widen a gate,
alter truth, delete a seed or edit raw to rescue a result. CP5 requires CP0–CP4
and required project checks; this document alone passes none of CP1–CP5.
