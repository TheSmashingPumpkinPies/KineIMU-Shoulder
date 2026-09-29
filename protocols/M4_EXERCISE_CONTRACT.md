# M4 Exercise Contract — KineIMU Shoulder

Definition freeze: `m4-exercise/1.0`, 2026-09-26 (Asia/Shanghai).
This governs the implemented M4 processed/derived output. The original CP0
review remains in the private historical archive; independent truths are in
`tests/fixtures/M4_KNOWN_EXERCISES.md`. Implementation and exact-input acceptance
are delivered. Definition changes require a reviewed revision and new fixtures.
M1 packets, normalized schema 0.1, raw files and M2/M3 definitions are unchanged.

## Inputs and evidence

Require M3 `ElevationResult` and its corresponding `AngularSpeedResult`.
The latter must bind the same elevation result/content, exact grid, side,
source type, source hashes and positive `max_sample_gap_us`. Its N-1 intervals
must be exactly adjacent grid pairs. Require the nested M2.4
`RelativeOrientationResult` with `quaternion_th`, clock maps, heading relation,
interpolation limits and reasons, and both M3 alignment records. Validate
the M2/M3 contracts; a claimed valid row must have finite unit quaternion
(norm absolute tolerance 1e-12), finite elevation consistent with the M3
definition (1e-10 rad), and corresponding valid speed must match the M3
definition (1e-10 rad/s). Do not recompute a missing speed stream as a fallback.
M4 does not alter the input grid, repair NaNs or interpolate endpoints.

Caller supplies exercise (`flexion` or `abduction`), side, protocol ID/version,
session ID, declared analysis window with exact ordered grid endpoints, the
complete configuration below, calibration IDs/hashes and processing/source
hashes. Window includes both endpoints; N >= 2. A malformed shape, duplicate,
reversed/non-int64 time, inconsistent association or invalid configuration
raises an input error before outputs. A missing global M2/M3 evidence record
produces an invalid analysis with reason, unavailable counts and no candidates;
it must not look like a valid zero-repetition session.

Numeric eligibility and anatomical evidence eligibility are distinct.
Supported synthetic axes/clocks yield Derived synthetic results only.
Assumed clock, heading or alignment allows illustrative arithmetic where
M3 allows it, with Assumed/Experimental and anatomical_eligible=false.
Missing/incompatible/expired alignment and missing clock/heading block
numerical relative metrics under M3. Never strengthen input evidence.
The retained M1 USB pair still lacks independently supported pairwise clock,
common heading and measured alignment. No physical or clinical accuracy is
established by CP0 or subsequent synthetic tests.

## Frozen configuration and rationale

The following is the complete baseline processing profile
`m4-thresholds/1.0`. Values are engineering choices for transparent synthetic
segmentation, not population norms, prescribed exercises or injury thresholds.
All must appear in output; overrides require their own configuration hash.
Degrees in this table are explanatory; stored values use exact multiples of pi.

| Parameter | SI value | Boundary and purpose |
|---|---|---|
| rest_level_rad | pi/18 (10 degrees) | e <= rest level; low return boundary |
| start_level_rad | pi/9 (20 degrees) | e >= start level; 10-degree hysteresis |
| rest_confirm_us | 200000 | elapsed contiguous low-row run >= value |
| start_confirm_us | 200000 | elapsed contiguous high-row run >= value |
| min_peak_rad | pi/3 (60 degrees) | peak >= value |
| min_rom_rad | 2*pi/9 (40 degrees) | M3 closed-interval ROM >= value |
| min_phase_us | 200000 | rise and return chronological spans >= value |
| min_rep_us | 800000 | closed candidate duration >= value |
| plane_min_elevation_rad | pi/6 (30 degrees) | direction gate identifiable at equality |
| plane_tolerance_rad | pi/9 (20 degrees) | direction deviation <= value |
| plane_min_fraction | 0.90 | time-weighted qualifying fraction >= value |
| hold_band_rad | pi/36 (5 degrees) | both interval endpoints >= peak-band |
| hold_speed_limit_rads | pi/36 (5 degrees/s) | M3 3-D speed <= value |
| min_hold_us | 500000 | maximal contiguous qualifying interval run >= value |
| cv_mean_floor_rad | pi/180 (1 degree) | CV only if mean ROM > value |
| decomposition_cos_floor | 1e-8 | abs(cos(beta)) <= value is singular |
| max_sample_gap_us | required, no session default | identical to M3; equality passes |
| max_thorax_drift_rad | required if thorax trace supplied | positive, protocol-specific; no physical default |

Fixtures use max_sample_gap_us=500000 and, where relevant,
max_thorax_drift_rad=pi/180 with exact synthetic drift bound 0.
Require 0 <= rest < start < plane_min <= min_peak < pi;
0 < min_rom <= pi; 0 < plane_tolerance < pi/2;
0 < plane_min_fraction <= 1; positive integer time/gap limits;
0 <= hold_band < min_peak; nonnegative finite hold speed limit;
positive finite CV floor and 0 < decomposition_cos_floor < 1.
Reject booleans as integer parameters and nonfinite configuration values.
No smoothing, peak-finding library, hidden debounce or adaptive threshold is
introduced. The small state machine is justified because the required exact
QC and boundary semantics are project-specific; use existing M3 calculations
and SciPy rotations rather than a new rotation algorithm.
The min_rom gate is the amplitude/prominence rule; no separate prominence,
maximum rep duration or local-extremum splitting rule exists in 1.0.

## Candidate state machine, time ownership and QC

Process the declared window in observed timestamp order. A run means
consecutive qualifying valid rows with valid connecting speed intervals and
no over-limit gap; its elapsed time is last timestamp minus first timestamp.
There is no sample-count debounce and no interpolation of a crossing.

1. Begin UNARMED. Confirm REST after a low-row run e <= rest lasting
   rest_confirm_us; equality passes. It stays armed through intermediate
   values below start. Leading high rows before a confirmed rest form one
   left-censored candidate starting at the first window/continuity-block row
   with e > rest; it ends at the first subsequently confirmed low run, or at
   window end/QC break. A block that starts low but has an excursion before
   confirmation likewise emits a left-censored candidate. A low-only block
   emits none. Its unknown movement start is never inferred.
2. While armed, start confirmation is a contiguous e >= start run lasting
   start_confirm_us. On confirmation open a candidate at that run's FIRST
   row (not the confirming row). A failed high run is a diagnostic
   `start_debounce_failed` with its bounds, not a detected repetition.
3. An open candidate ends at the FIRST row of the first e <= rest run
   lasting rest_confirm_us. Its confirmation tail is retained separately;
   candidate end is retrospective. A failed return run leaves it open.
   Ignore new high crossings while open: one envelope gives one candidate.
   Once return is confirmed the low run already arms the next start.
4. Peak boundary is the earliest row of the maximum elevation in the closed
   candidate. Equal maxima never create extra reps. Rise support is
   [start,peak], return support [peak,end]. Require both chronological spans
   >= min_phase_us, duration >= min_rep_us, peak and ROM gates. A zero-length
   phase fails. Window end while open emits `partial_end`; left-censored
   candidates emit `partial_start` even if a return is observed. Both reasons
   may coexist. Confirmations must lie within the analysis window.
5. Any invalid elevation/q_TH row, invalid speed interval, or gap > M3 limit
   ends continuity, resets UNARMED and cancels pending confirmation. If open,
   emit one excluded interrupted candidate ending at the last preceding valid
   row, plus offending row/interval indices and exact upstream reasons. If a
   retrospectively chosen end is already awaiting rest confirmation and the
   confirmation tail breaks, that candidate is also interrupted/excluded.
   Invalid rows never serve as boundaries or get bridged. A subsequent high
   block is a separate partial-start candidate. Thus counts are algorithmic
   detected envelopes, not an estimate of true reps during lost data.

Closed row supports can share a boundary row. Adjacent time intervals belong
once: [t_i,t_i+1] is in a candidate iff both endpoints lie within [start,end].
It belongs to rise if end <= peak, otherwise return (peak is an exact row).
No interval crosses the peak. Confirmation tails belong to rest, not the rep.
All candidates are retained with stable ordinal IDs, observed bounds,
confirmation bounds, peak or null, censoring and diagnostic reasons.
Excluded candidates retain observed boundary durations as diagnostics but all
per-rep metric values are unavailable; they never enter numeric summaries.

For two successive eligible candidates, inter-rep rest is
(next_start - previous_end)/1e6, including confirmation tails and sub-start
motion. It is available only if they are adjacent detected candidates and
every intervening row/interval is valid without a gap. Otherwise report
`rest_interrupted`; do not span an excluded candidate. Leading/trailing time
is separately window context, never fabricated inter-rep rest.

## Side-aware exercise-plane gate

Use proximal long axis u=R_TH*[0,0,1]. In arms-down neutral +Z is proximal,
so anterior movement of the distal arm corresponds to NEGATIVE u_x.
Let s=+1 for left and -1 for right; define a=-u_x, l=-s*u_y.
Flexion tests atan2(abs(l),a); abduction tests atan2(abs(a),l), in [0,pi].
Negative declared-plane direction consequently fails. Left abduction is
R_X(+e), right abduction R_X(-e), flexion R_Y(-e).

Eligible plane intervals require BOTH endpoint elevations >= plane_min and
nonzero transverse axis norm (norm > 1e-12); endpoints at pi are ambiguous.
An interval passes if BOTH endpoint direction deviations <= tolerance.
fraction = sum(passing eligible dt)/sum(all eligible dt). No eligible
duration means `plane_unobservable`, not a passing fraction of 1.
Fraction < min_fraction excludes the entire candidate as `plane_mismatch`.
At equality pass; retain all failing indices and `plane_deviation_present`
even if the fraction passes. Other intervals are explicitly non-identifiable
and reported as such, not silently counted as passing. Caller label is never
changed. Roll about H +Z can leave this gate unchanged while speed changes.

## Repetition metrics and hold semantics

For a fully eligible candidate use M3 closed-interval ROM and elapsed
duration; peak is max elevation, not ROM. Speed always means M3 principal
3-D relative quaternion interval magnitude, rad/s; do not call it signed
elevation rate or instantaneous angular velocity.

Hold-qualified intervals have both endpoints in [peak-hold_band,peak],
valid speed <= hold limit and no QC failure. Keep each maximal contiguous
run only if its total observed duration >= min_hold. Sum all retained runs;
otherwise hold_duration_s=0 is a valid absence of detected hold. The rule
cannot detect unobserved within-interval rotations (M3 aliasing limit).
Hold intervals are removed from rise/return interval ownership and assigned
to hold. Thus elevation_duration_s + return_duration_s + hold_duration_s
= rep_duration_s. min_phase uses the chronological supports BEFORE hold
removal; phase duration may be zero after removal, with phase speed unavailable.
Store support boundaries and every hold interval/run; phases need not be
monotone under small oscillations. A pause below the peak band is not hold.

For rep, elevation, return and hold speed, report maximum interval speed
and time-weighted mean sum(speed_i*dt_i)/sum(dt_i) over the respective
owned intervals. Empty phase: both speed statistics unavailable with
`empty_phase`. Rep mean includes hold. No sample-weighted speed mean.

## Thorax common-grid input and excursion proxy

Freeze an OPTIONAL processed record `m4-thorax-common-grid/1.0`; do not add
fields to M2/M3 dataclasses or change acquisition schema. Preparation is an
explicit processed operation using existing SegmentOrientationStream,
ClockMap and SciPy SLERP, outside backend adapters. It retains original
thorax device timestamps/quaternions and mapped times or a content-addressed
artifact containing them, exact-sample versus bracket indices/weights per
grid row, interpolation/gap history, original source hash/node/epoch/world,
calibration and alignment, map, common grid, q_WaT, row validity/reason,
uncertainty limit, configuration/hash and method/version. No extrapolation.
Fixed q_NT was applied once before resampling; never apply it again.

Grid, thorax identity/hash/map/alignment and world Wa must match the nested
M2/M3 record exactly. Independent thorax row QC is ANDed for proxy metrics
only. Missing trace gives `thorax_trace_missing`; incompatible binding gives
`thorax_trace_incompatible`; any invalid proxy row or gap in the closed rep
gives `thorax_invalid_row`/`thorax_sample_gap`. These make every proxy component
unavailable but do not remove an otherwise valid relative-motion repetition.

For each rep baseline q0=q_WaT[start]. D=R_WaT[start]^T R_WaT[t], expressed
in movement-start thorax axes T0. Decompose using SciPy's existing rotation
operations, with explicit verification of
D=R_Z(gamma) R_Y(beta) R_X(alpha), beta in [-pi/2,pi/2], alpha/gamma in
[-pi,pi). Equivalent extraction away from singularity is
beta=asin(-D31), alpha=atan2(D32,D33), gamma=atan2(D21,D11).
These Euler scalars are output decomposition only; internal rotations remain
quaternions. Define extension=-beta (superior towards posterior),
lateral_flexion=-alpha (superior towards left), axial_rotation=gamma
(anterior towards left). Signs refer to T0, not a changing world or test side.
Use the documented principal branches, no implicit unwrap. If any component
jumps by > pi between adjacent rows, proxy is unavailable with
`thorax_branch_crossing`. abs(cos(beta)) <= decomposition_cos_floor at any
row makes ALL proxy components unavailable: `thorax_decomposition_singular`.
For each component report signed minimum, signed maximum and magnitude
max(abs(min),abs(max)), with baseline zero included. This is excursion from
movement start, not max-min range, sum of angles, displacement or a score.

Require a per-thorax heading/drift evidence record with method/reference
hash, covered time window and conservative angular drift bound in rad over
that window. Bounds must cover the whole rep; bound <= configured max passes.
No record: `thorax_drift_unbounded`; over limit: `thorax_drift_exceeded`;
missing required heading: `thorax_heading_missing`. No inferred zero drift
from static gravity, a short duration or supported initial heading alone.
Explicit assumed heading/drift permits illustrative proxy only with
Assumed/Experimental, anatomical_eligible=false and retained assumption.
Physical anatomical eligibility requires measured valid thorax axes plus
supported clock, heading and duration-specific drift bound. This remains a
thorax orientation compensation proxy, never glenohumeral/scapular motion.

## Summary denominators and comparisons

For a numerically valid analysis, detected_count includes all emitted
candidates; valid_count includes only complete candidates passing QC, timing,
amplitude and plane gates; excluded_count=detected-valid. Group all exclusion
reasons with candidate IDs; reason counts may overlap. Partial counts are
separate. Segmentation has its own validity/evidence label. A valid quiet
window has counts 0,0,0; absent/invalid global input has unavailable counts.

Summarize each eligible relative metric with arithmetic mean and maximum
over eligible reps, explicit n. Report rest separately with its own n.
Thorax summaries use only valid proxy reps, with proxy_valid_count and
proxy_unavailable_count among otherwise eligible relative reps.
Assumed illustrative and supported evidence strata are never pooled.
Zero eligible values => unavailable (`no_valid_repetitions` or
`no_valid_proxy`); one => mean/max valid, variability unavailable.

ROM range=max-min for n>=1; sample SD=sqrt(sum((x-mean)^2)/(n-1)) for n>=2;
CV=SD/abs(mean) only for n>=2 and mean > cv_mean_floor_rad (dimensionless).
Other cases: `insufficient_repetitions` or `cv_mean_near_zero`. No SEM or
clinical consistency score. Active time=sum eligible rep_duration_s; active
cadence=valid_count/active_time, unit s^-1, no rest in denominator. Zero active
time => unavailable `empty_active_time`. Do not label it whole-session cadence.
Report analysis-window elapsed duration independently, without extrapolation
over QC gaps. No summary from a partial-valid piece of an excluded rep.

Within-session sets and longitudinal pairs compare only if keys match:
definition version, complete thresholds/gap policy, side, exercise,
protocol/version, neutral/frame conventions, calibration IDs/hashes,
alignment IDs/transforms/mount validity, clock/heading methods and evidence
stratum, drift policy for proxies, backend/version/configuration, grid policy
and source type. Session/raw source hashes are lineage, not equality keys
(different sessions necessarily have different hashes). Changed calibration
or remount is incomparable under 1.0. Same synthetic generator/version can
compare distinct traces; recorded and synthetic may not be pooled.
Order pairs by explicit UTC session start, then session ID for equal times;
missing start or duplicate ID => comparison input error. Incomparable pairs
retain differing keys and no difference. For comparable available metrics
report later mean minus earlier mean in SI with both n and evidence;
unavailable metric => `comparison_metric_unavailable`. No recovery score.

## Derived field and reason contract

`m4-exercise/1.0` envelope fields: schema_version, definition_version,
session_id, session_start_utc, protocol_id/version, exercise, side,
source_type, analysis_window_us, units, configuration/hash, processing
commit/hash, dependency_lock_sha256, input_artifact_sha256 (M2/M3 and optional
thorax), original A/B hashes, calibration/alignment and clock/heading evidence,
analysis_valid/reasons/evidence_label/anatomical_eligible, candidates,
segmentation_diagnostics, summary and optional comparisons. Preserve exact
upstream records, not only a free-text conclusion. Frame/neutral and
interpolation history are linked to content-addressed inputs.

Candidate fields: id, start_us/end_us, start_confirmation_us/
end_confirmation_us (two-bound arrays or null), peak_us, partial_start/end,
interrupted, valid, reasons, offending_rows/intervals with original reasons,
plane_eligible_duration_s/passing_duration_s/fraction/failing_intervals,
rise_support_us/return_support_us, hold_runs_us, metrics and thorax_proxy.
Metrics: rom_rad, peak_elevation_rad, rep_duration_s,
elevation_duration_s, return_duration_s, hold_duration_s,
rep/elevation/return/hold_speed_mean_rads and *_speed_max_rads,
preceding_rest_duration_s. Each metric object has value, valid, reason,
unit, evidence_label and anatomical_eligible. Proxy has extension,
lateral_flexion and axial_rotation objects, each with min_rad/max_rad/
magnitude_rad and the same status fields. Diagnostics are explicitly separate
from metric values. Counts and summary objects also carry validity, reason,
evidence and n/denominator where applicable.

Array unavailable values are NaN with valid=false; canonical JSON uses null
with valid=false and exact reason (never nonstandard JSON NaN or zero).
Valid items use reason=`ok`; reason arrays retain ALL causes in order:
upstream/QC by time, censoring, phase/rep duration, peak/ROM, plane.
Reason vocabulary includes `upstream_invalid:<original>`, `sample_gap`,
`partial_start`, `partial_end`, `interrupted`, `phase_too_short`,
`rep_too_short`, `peak_below_minimum`, `rom_below_minimum`,
`plane_unobservable`, `plane_mismatch`, and the metric-specific codes above.
Global failures preserve M3 reason codes. Failures coexist; the first is the
primary reason, subsequent causes are never hidden. Units are rad, rad/s, s,
dimensionless, s^-1 and int64 microseconds; any degree display explicitly
converts by 180/pi. No uncertainty/accuracy number is manufactured: retain
input uncertainty statements, and label numerical tolerance separately.

If no valid connected row pair exists in the window, analysis_valid=false
with `no_usable_continuity`, unavailable counts and no numeric summaries.
Otherwise counts describe only detected envelopes in observed continuity
blocks; output includes every QC break and total observed valid/invalid
duration. An adjacent interval is valid-duration support only when both M3
rows and its speed are valid and its gap passes; all other adjacent elapsed
time belongs to invalid duration, so the two sum to window elapsed time.
A QC-interrupted window is not certified as complete observation
of all true repetitions, even if some eligible candidates remain.

## Acceptance tolerances

Exact fixtures: angle/ROM/proxy/SD absolute tolerance 1e-10 rad,
speed 1e-10 rad/s, dimensionless fraction/CV 1e-12, duration/cadence
1e-12 s / 1e-12 s^-1. Counts, grid boundaries, memberships, reason codes
and comparison keys match exactly, with no fuzzy threshold slack.
Analytical equality fixtures should construct matching symbolic inputs.
End-to-end AHRS tolerances must be separately declared at CP5 from M2's
existing backend error contract, not silently substituted for these direct
exact-input gates. The implemented V1 metrics and subsequent tested coverage
are documented in [metric definitions](../docs/METRICS.md) and
[validation coverage](../docs/validation/coverage.md).
