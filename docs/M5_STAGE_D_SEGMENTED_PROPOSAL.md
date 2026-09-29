# M5.4 D clipped-observation handling proposal

Status: ACCEPTED by explicit maintainer selection on 2026-09-27, after review
of M2 rejection and discontinuous-world consequences. Normative implementation
contract: [m5-recorded-segments/1.0](../protocols/M5_RECORDED_SEGMENTS_V1.md),
[ADR-011](adr/ADR-011-recorded-quality-segments.md). Baseline HEAD:
554d9f6a (resolve full hash with `git rev-parse 554d9f6a`).

## Reproduced blocker

The original B stream has 191,424 observations. Original index 23,297,
sequence 1,604,645, device time 15,120,024,658 us has GYRO_CLIPPED and
X rate -509.04 deg/s. Existing calibration rejects the clipping flag and
also rejects this value against 500 deg/s times its existing 1.001 factor.
The original failed D output and source lock remain immutable.

## Proposed validation-only processed contract

Preserve every original observation, timestamp, flag, counter, packet arrival
and sensor-frame SI value. Classify calibration-ineligible rows using the
existing clipping bits and configured range checks. Export every applicable
reason, the full original denominator and explicit original indices.
Do not alter the calibration API, ranges, tolerances or original flags.

Apply the original calibration function to each contiguous eligible interval,
passing the original flags. Run a fresh pinned AHRS per interval, with identity
initial q_WN and the existing 0.05 s gap limit. A rejected row has null processed
vectors and quaternion, valid=false, and no segment/world ID. A new interval
has its own world ID and an explicit reset record. Do not bridge a rejected row,
carry state across it, interpolate, reconstruct or compare different worlds.
Other input/QC/calibration/AHRS failures still fail the attempt.

For this retained B stream the independent expected partition is [0,23297),
rejected index 23297, [23298,191424). A retains [0,187772). This gives
379,196 original observations, 379,195 eligible node-orientation rows and
one explicitly unavailable row, with three independent AHRS initializations.
Eligibility is not measured orientation accuracy; all q_WN remain
Assumed/Experimental with unobservable heading.

Actual M2/M3/M4 missing-evidence calls must use one contiguous processing
world per node, labelled rejection-only, while requesting original A support.
Missing clock, heading, anatomical alignment and drift evidence still prohibit
shoulder metrics. Do not represent B's two worlds as one continuous stream.

## Acceptance and reacceptance scope

On approval, record a separate versioned contract/ADR and explicit CLI opt-in.
The strict original recorded path, C, synthetic B, CP0-CP3 and production
interfaces remain unchanged. Reaccept D only through targeted red/green tests,
all Python required checks, and a new clean-lock complete A/B replay plus
independent raw/partition/reset/quaternion/null/downstream audit in a fresh root.
Retain source bytes, commands, exits and pre/post hashes of all eleven external
members. Tests must include flagged-only, range-only, consecutive/endpoint/all
bad rows, reset identity, unbridged gaps and semantic product corruption.
Stage E must use this declared policy when it is separately authorized;
CP4/CP5/overall M5 remain OPEN. Stop after D, without acquisition or hardware work.

The maintainer selected the segmented scheme. Original whole-stream rejection
remains available as the strict default, and the original D failure is preserved.
