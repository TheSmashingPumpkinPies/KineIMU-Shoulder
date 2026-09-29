# m5-recorded-segments/1.0 — explicit recorded quality segments

Accepted by the maintainer on 2026-09-27 after reviewing the D handling proposal
and consequences of independent AHRS restart. See [ADR-011](../docs/adr/ADR-011-recorded-quality-segments.md).
This is a validation-only recorded-replay contract, selected explicitly with
`recorded_dual --segmented`. It does not modify public schema 0.1, calibration
or AHRS APIs, imufusion settings, synthetic processing/1.1 or frozen CP0–CP3.

## Conservation and partition

Decode and export all original packets, sample counts, device times, flags,
counters, host arrival times, sensor-frame SI and QC, in original order.
The eligibility denominator is the complete original sample count.
No observation is edited, deleted, replaced or reconstructed.

An observation is ineligible if it has ACCEL_CLIPPED or GYRO_CLIPPED, or any
sensor SI component exceeds the configured per-axis range multiplied by the
existing calibration tolerance 1.001. Use the exact M2 calibration predicates:
`abs(a)>accel_range_g*9.80665*1.001` and
`abs(w)>deg2rad(gyro_range_dps)*1.001`. Equality remains eligible.
Retain every applicable reason: accel_clipped, gyro_clipped,
accel_range_exceeded, gyro_range_exceeded. These are validation artifact
reasons, not new production M2/M3 reason codes.

Partition eligible observations into maximal contiguous original-index
intervals, retaining start/stop-exclusive indices and device endpoints.
Ineligible rows have null node-frame vectors/quaternion, valid=false,
all reasons and null segment index. Original sensor-frame values remain
present even there. A processing segment is not a device-clock epoch.

Each segment passes original flags, node/config identity and vectors through
unchanged `apply_calibration`. Then call a fresh `estimate_orientation` with
original times, identity initial q_WN and max_gap_s=0.05. Export a distinct
world ID, reset reason, initial quaternion and null initial integration dt.
No state or integration interval crosses an ineligible observation.
There is no interpolation, inferred motion or cross-segment comparison.

Shape, nonfinite, bad time, source/count/QC mismatch, zero acceleration,
unapproved gaps and backend failures still fail the attempt. No eligible
sample means node failure and downstream NOT RUN. A single-row segment has
only its explicitly assumed identity initialization, with no invented dt.

`orientation.valid` means a processed value exists under these assumptions;
it does not mean physical accuracy, shared heading or anatomical validity.
All q_WN remain Assumed/Experimental, heading_observable=false,
anatomical_eligible=false; calibration is illustrative identity/zero bias.

## Downstream and acceptance

Use the first eligible contiguous processing world from each actual node for
the existing missing-evidence M2/M3/M4 rejection probe. Bind exact segment
indices/world IDs in `probe_segments`. Request full original A timestamps as
diagnostic support only; they are not a synchronized common grid. Do not join
B's processing worlds into a single stream. No maps, common heading, segment
alignments or bounded drift are fabricated. Shoulder outputs stay unavailable.

Independent retained-source expectations for this D attempt:
A 46,943 packets / 187,772 rows, one eligible segment;
B 47,856 packets / 191,424 rows, intervals [0,23297) and [23298,191424),
ineligible index23297 / sequence1604645 / time15120024658 us with both
gyro_clipped and gyro_range_exceeded. Total379196 original rows,
379195 eligible q_WN rows, one null row and three initializations.
This is a complete quality-aware replay, not an all-observations AHRS pass.

Reacceptance scope is D: red/green partition/reset/null tests, unchanged strict
C/D regression paths, required full Python checks and one new clean-lock
development A/B execution plus independent raw/partition/SI/backend/null/
downstream audit. All eleven external manifest entries and manifest hash must
match before/after; retain source ZIP, commands, exits and product hashes.
Original failed D root and original auditor remain immutable.
This originally defined the D reacceptance segment, before the subsequent
two-process B/C/D acceptance. Current V1 validation coverage is recorded in
[the coverage report](../docs/validation/coverage.md). Original failed D evidence
remains historical; hardware remains frozen.
