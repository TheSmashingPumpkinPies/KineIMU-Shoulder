# M3 Kinematics Contract — KineIMU Shoulder

Status: **implemented V1 contract**, originally frozen 2026-09-25 (Asia/Shanghai).
This defines the processed/derived M3 interface. Implementation and known-input
tests are delivered; see [metric coverage](../docs/METRICS.md). It does not make a
change to the M1 packet, normalized table, or public schema 0.1. Numerical
examples and independent expected values are in
`tests/fixtures/M3_KNOWN_MOTION.md`. A change to these metric definitions or
frame conventions requires a reviewed contract revision before implementation.

## Required input and evidence

One M3 operation consumes one M2.4 `RelativeOrientationResult` and an explicit
alignment record for **each** of its A/thorax and B/humerus source streams.
`q_WN` from one node is never an M3 input. The M2 result supplies a strictly
increasing int64 `common_time_us` grid, scalar-first active Hamilton `q_TH`
array `(N,4)`, `valid` mask, one exact `reason` per row, source SHA-256 values,
both `ClockMap` artifacts, `HeadingRelation`, SLERP method, interpolation gap
and timing-uncertainty limits. Its grid and mask are authoritative; M3 neither
pairs raw rows nor remaps clocks, resamples, interpolates, repairs NaNs or
changes an M2 exclusion reason.

Each alignment record must bind the corresponding node/source hash and epoch,
segment (`T` or `H`), test side (`left` or `right`), proper fixed segment-to-node
rotation `q_NT`/`q_NH`, alignment ID, method, source hash, neutral-pose
definition, mounting/session validity statement, remount status, uncertainty
statement and evidence status (`supported` or `assumed`). The record must say
whether its axes were *measured* or are exact synthetic ground truth. A
synthetic known alignment is eligible for numerical fixtures only. For a
physical anatomical interpretation, the session needs measured, currently
valid anatomical alignment for both segments; a remount invalidates an old
record. Gravity-only alignment cannot establish AP/ML heading. A merely
plausible identity transform is not alignment evidence.

Both clock maps and the heading relation must exist, match the source streams
and have passed M2.4's checks. A valid M2 row with an assumed clock or heading
is eligible for an **illustrative** calculation but retains
`Assumed/Experimental`; it cannot be reported as measured/validated anatomy.
An assumed alignment has the same restriction. Validity of a numerical M3
sample and eligibility for a physical anatomical claim are separate fields.
The retained M1 dual USB pair has no independent pairwise clock, common
heading or measured anatomical alignment and is ineligible for an anatomical
M3 result. M3 synthetic gates do not establish physical or clinical accuracy.

## Frames, neutral and equations

All frames are right-handed. `R_AB` maps B-coordinate column vectors into A;
`q_AB` is its active, scalar-first `[w,x,y,z]` Hamilton quaternion. `T` is
thorax anatomical +X anterior, +Y left, +Z superior. In the declared
arms-down neutral pose, `H` has +Z proximal along the humeral long axis,
+X anterior and +Y left. Test side is mandatory and is preserved even though
the unsigned elevation formula is the same for both sides. In neutral,
`q_TH = identity` and the two +Z axes coincide. These axes are a mathematical
fixture until supported by session-specific alignment evidence.

For a valid sample, set `u_T = R_TH [0,0,1]^T`, with
`R_TH = R_WT^T R_WH`. Define long-axis elevation in radians by

```text
e = atan2( || [0,0,1] × u_T ||, [0,0,1] · u_T ) , 0 ≤ e ≤ π.
```

The `atan2` form avoids an unclipped inverse-cosine argument near the
endpoints. For a unit `u_T`, it equals `acos(u_T,z)`. It is an unsigned
humerothoracic long-axis elevation approximation: it cannot by itself label
flexion versus abduction, infer an exercise plane, or isolate glenohumeral or
scapular motion. Quaternion sign `q`/`-q` must give identical output. A valid
numeric sample is finite; an invalid sample has no usable angle (NaN in an
array representation), `valid=false`, and a reason.

For adjacent grid samples `i,i+1`, with **both** valid, positive observed
`Δt_s = (t[i+1]-t[i])/1e6` and `Δt_us ≤ max_sample_gap_us`, compute

```text
δq = inverse(q_TH[i]) ⊗ q_TH[i+1]
θ = 2 atan2( ||δq_xyz||, |δq_w| ) , 0 ≤ θ ≤ π
relative_angular_speed_rads = θ / Δt_s.
```

This is the principal three-dimensional relative rotation magnitude averaged
over the **interval** `[t[i],t[i+1]]`; retain both endpoint timestamps. It is
neither signed elevation derivative nor instantaneous gyro rate. `q` sign
changes do not create spikes. No finite sample pair can reveal unobserved
within-interval revolutions: a 360° turn sampled only at its start/end has
identity endpoints and yields 0 under this formula. Report that as an aliasing
limit, never as evidence of no motion.

For a caller-supplied **closed** interval `[start_us,end_us]`, both bounds must
be exact members of the common-time grid, ordered with `start_us < end_us`.
Use every grid row from start through end inclusive. Require at least two
rows, all rows valid and every consecutive time gap no greater than the same
positive caller-declared `max_sample_gap_us`. Then

```text
rom_rad = max(e[start:end inclusive]) - min(e[start:end inclusive])
elapsed_duration_s = (end_us - start_us) / 1e6.
```

The interval is wholly eligible or wholly excluded: no endpoint interpolation,
partial ROM, missing-row bridge, or automatic movement/repetition detection.
ROM is a range and need not equal absolute peak or peak minus neutral.
Duration is elapsed endpoint time, not sample count divided by nominal rate.
M4 owns exercise classification, segmentation and phase/hold summaries.

## Processing parameters, output and exclusions

`max_sample_gap_us` is a required positive integer recorded with the result.
It limits **M3 output intervals**, independently of M2's input interpolation
gap. Equality passes; a larger gap fails. It is a sampling/QC parameter,
not a clinical threshold. For known-motion CP1–CP3 fixtures use 500,000 µs
unless a case explicitly supplies another value. Never silently choose a
default for a research session.

The versioned M3 derived artifact (`m3-kinematics/1.0`) records metric
definition version; side and neutral; units; every common-time row and
validity/reason; speed endpoint pairs and validity/reason; requested interval
and its validity/reason; the gap parameter; both original source SHA-256
values and M2 clock/heading artifacts; both alignment records and evidence
status; processing configuration/source hashes; and source type (`synthetic`,
`recorded` or other declared type). Internal angle and ROM units are rad,
speed rad/s, duration s, timestamps int64 µs. Degree display requires an
explicit `180/π` conversion and label. This derived artifact is separate from
the public acquisition schema.

Provenance labels may coexist: original times and raw channels are `Observed`,
M2 orientation and M3 metrics are `Derived`, synthetic source is explicitly
`synthetic`, and assumed clock/heading/alignment is `Assumed/Experimental`.
`Validated` requires linked external reference, uncertainty, population and
protocol evidence; none is supplied by these fixtures. Downstream labels
cannot be stronger than their input evidence. A result with no eligible row
is `Invalid`; invalid interval/speed items retain their own reason even if
other items in the stream are valid.

The implementation must use stable reason codes, at minimum:

| Reason | Applies when |
|---|---|
| `m2_invalid:<original_reason>` | M2 invalid row/endpoint; preserve its exact reason |
| `alignment_missing`, `alignment_incompatible`, `alignment_expired` | Required record absent, source/side/frame mismatch, or mounting validity lost |
| `clock_or_heading_missing` | M2 artifact absent despite a purported valid result |
| `nonfinite_or_nonunit_quaternion` | A purported valid `q_TH` fails numeric checks |
| `invalid_common_time` | Grid type/order or time delta violates the contract |
| `sample_gap` | Consecutive grid interval exceeds `max_sample_gap_us` |
| `interval_endpoint_missing`, `interval_order`, `interval_too_short` | Requested interval has absent/reversed/equal bounds or fewer than two rows |
| `interval_invalid_row` | Any included sample is invalid; retain row index and underlying reason |

Missing/incompatible global evidence prevents all numeric output. Malformed
array shape, noninteger times, invalid configuration and mismatched reason
length are input errors, not silently excluded samples. Speed intervals use
the first failing endpoint reason or `sample_gap`; an interval ROM result
identifies the first invalid row and all contributing M2 reasons in its
provenance. Do not substitute zero for an invalid metric.

## CP0 numerical review gate

The independent fixture table gives symbolic expected values before M3 code
exists. For exact synthetic quaternion fixtures, CP1 angle and CP3 ROM
comparison tolerance is `1e-10 rad` absolute; CP2 speed is `1e-10 rad/s`
absolute and elapsed duration is `1e-12 s` absolute. These are floating-point
algorithm checks, not physical sensor accuracy. Invalid cases require exact
validity/reason behavior instead of a numeric tolerance. CP0 review checks
this contract against M2.4, `docs/METRICS.md`, `DATA_FORMAT.md` and
`ACCEPTANCE_CRITERIA.md` before any CP1 implementation.
