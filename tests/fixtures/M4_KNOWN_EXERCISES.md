# M4 Independent Known Exercises — CP0 Truth Freeze

Frozen 2026-09-26 before M4 numerical code. Governing definition:
`protocols/M4_EXERCISE_CONTRACT.md`, `m4-exercise/1.0`.
These are analytical fixtures, not outputs copied from a production routine.
Future tests cite case IDs and the derivations here. Synthetic only;
no physical anatomical accuracy, clinical threshold or human study is claimed.
All tabulated degrees convert to rad by pi/180; seconds to exact integer
microseconds by 1000000. No random noise or interpolation is needed for CP1–CP4.

## Source construction and primary oracle A

Use exact common-grid times, supported synthetic identity clock maps/world
relation, synthetic known alignment records for both nodes, stable source
IDs/hashes, side and the frozen baseline profile (gap 500000 us).
For a signed axis rotation q_X(b)=[cos(b/2),sin(b/2),0,0], and similarly Y/Z.
Set q_TH=q_Y(-e) for flexion, q_X(+e) for left abduction, q_X(-e) for right
abduction. Rotated +Z is respectively (-sin e,0,cos e),
(0,-sin e,cos e), (0,+sin e,cos e). Thus elevation is e for 0<=e<=pi,
the declared direction deviation is zero, and axis interval speed is
abs(e_next-e)/observed_dt (principal differences below pi).
This vector/right-hand-rule derivation is independent of SciPy and M4.
Set q_WT=identity, q_WH=q_TH unless a thorax case changes both consistently.
Use all table rows; do not interpolate additional rows in boundary assertions.

| Time s | Elevation degrees | Role |
|---|---|---|
| -0.4, -0.2, 0 | 0, 0, 0 | confirmed rest |
| 0.2, 0.4, 0.6, 0.8 | 20, 40, 60, 80 | start confirms at 0.4, retrospective start 0.2 |
| 1.0, 1.2, 1.4 | 80, 80, 80 | plateau |
| 1.6, 1.8, 2.0, 2.2 | 60, 40, 20, 0 | end row 2.2 |
| 2.4 | 0 | end confirms at 2.4 |

A expected: one detected/valid, zero excluded. [start,end]=[0.2,2.2],
earliest peak=0.8; start confirmation [0.2,0.4], end confirmation [2.2,2.4].
ROM=80 degrees (minimum zero at end), peak=80 degrees; duration=2 s.
Rise support 0.2..0.8, return support 0.8..2.2. Hold 0.8..1.4=0.6 s;
elevation duration=0.6 s, return duration=0.8 s. All moving intervals have
100 degrees/s, plateau 0; rep mean=(60+80)/2=70 degrees/s and max=100.
Elevation/return means and maxima=100; hold mean/max=0.
Plane eligible duration=1.8-0.4=1.4 s, passing duration=1.4, fraction=1.
One-rep summary mean/max ROM=80, ROM range=0, SD/CV unavailable
`insufficient_repetitions`, active time=2 and cadence=0.5 s^-1;
preceding rest unavailable (no preceding rep). Thorax proxy=0 on all axes
with synthetic drift bound 0, if the matching optional trace is supplied.

## Segmentation, direction and QC truth cases (CP1)

| ID | Construction | Exact expected behavior |
|---|---|---|
| C0 | A flexion on either side | A boundaries/counts; zero deviation |
| C1 | A left abduction and A right abduction | Same A values; q_X signs above; side preserved |
| C2 | q_TH and every thorax quaternion replaced by their negatives | Identical values, boundaries and reasons |
| C3 | Window [-0.4,0.4], every e=0 | Valid analysis, counts 0/0/0, numeric summaries unavailable, empty_active_time cadence |
| C4 | A, one-row window or duplicate/reversed/non-int64 times | Input error before counts, not zero reps |
| C5 | A with q_X(-e) declared LEFT abduction | All eligible plane intervals deviate pi; one excluded plane_mismatch, no relabel |
| C6 | A with u=(-sin(e)/sqrt(2),-sin(e)/sqrt(2),cos(e)), left flexion | 45-degree deviation, fraction 0; one excluded plane_mismatch |
| C7 | A with u=(-sin(e)*cos(20 deg),-sin(e)*sin(20 deg),cos(e)), left flexion | Exact plane tolerance equality passes, fraction 1 |
| C8 | Repeat C7 with direction 21 degrees | fraction 0, plane_mismatch |
| C9 | Modify profile min_peak=plane_min=pi/3; motion peaks at e=pi with only neutral/180 rows, adequate timing | Transverse norm zero; no eligible direction duration, plane_unobservable; never infer plane from 180 elevation |
| C10 | Before A insert 0.1:20, 0.2:19, 0.3:20; shift A start/high rows to 0.4 onward with consistent times | First high run fails debounce, intermediate value does not disarm confirmed rest; only the sustained high run opens one candidate |
| C11 | A window starts at 0.4 (no leading rest) | One left-censored candidate [0.4,2.2], partial_start, no numeric contribution |
| C12 | A window ends at 1.8 | One [0.2,1.8], partial_end, no invented return |
| C13 | A window ends at 2.2 | Low run has no confirmation duration; partial_end, not accepted complete rep |
| C14 | A e=0 row at 1.6, then e=40 at 1.8 (otherwise A) | Failed low run does not end envelope; only confirmed end at 2.2, one candidate |
| C15 | A row 1.0 invalid with exact m2 reason `clock_validity` | One interrupted [0.2,0.8], offending row retained; subsequent high block produces partial_start [1.2,2.2]. detected=2, valid=0; never bridge |
| C16 | A speed [0.8,1.0] invalid though endpoints valid | One interrupted ending 0.8; next block starts at 1.0 and is partial_start. Original speed reason retained |
| C17 | Shift all A times >=1.0 forward 0.4 (gap 0.6 > 0.5) | Same split logic, sample_gap at [0.8,1.4], no enlarged integration/hold |
| C18 | Shift all A times >=1.0 forward 0.3 (plateau gap exactly0.5), observed speed recomputed | Continuity passes; hold0.9, rep2.3, rise0.6, return0.8 s; no sample_gap |
| C19 | A row 2.4 invalid, otherwise unchanged | Return confirmation breaks; candidate interrupted/excluded, retrospective end cannot be certified |
| C20 | A has e=80 at 1.0 and 1.4 as already tabulated | earliest maximum stays 0.8, one candidate |
| C21 | All rows <=10, but only one low row before window end | No excursion/candidate; zero counts if global inputs valid |

For C9 and direction-only constructions, q_TH may be supplied by the
axis-angle rotation carrying +Z to the stated u with zero arbitrary long-axis
roll; the expected plane result follows u directly. Full quaternion speed
truth must then be derived independently before making a speed assertion.
C10 asserts state/count only; it is not a speed/ROM fixture.

Plane fraction boundary oracle: override gap to 1000000 us; times
[-1,-0.5,0,0.5,1,2,3,4,5,6,7,8,9,10,10.5,11,11.5], elevations
[0,0,20,40,80,80,80,80,80,80,80,80,80,80,40,0,0].
Declare flexion; only row t=0.5 has direction deviation 21 degrees, all
other identifiable rows zero. Eligible support [0.5,10.5] has duration 10 s;
only [0.5,1] fails (0.5 s), fraction=0.95: passes with deviation diagnostic.
Move the sole deviating row to t=2: [1,2] and [2,3] fail (2 s), fraction=0.8:
excluded. For exact 0.90 equality use deviating row at t=0.5 AND t=10.5:
two half-second boundary intervals fail, total=1 s, fraction=9/10 passes.
This locks BOTH-endpoint interval testing and time rather than row weighting.

## Per-rep metric and equality oracles (CP2)

| ID | Construction | Expected |
|---|---|---|
| P0 | A | Values derived above, additive phase durations 0.6+0.8+0.6=2 |
| P1 | Remove A plateau rows 1.0/1.2/1.4; shift original times >=1.6 earlier by 0.6 | [0.2,1.6], peak 0.8, duration 1.4, rise 0.6, return 0.8, hold 0; rep mean/max=100 degrees/s |
| P2 | A plateau reduced to exactly 0.5 s (rows 0.8,1.0,1.3; shift return and confirmation 0.1 earlier) | hold 0.5 passes; duration 1.9, rise 0.6, return 0.8; rep mean=140/1.9 degrees/s |
| P3 | Same with plateau 0.4 s | no retained hold; duration 1.8, elevation=0.6, return=1.2; return mean=80/1.2, rep mean=140/1.8 degrees/s |
| P4 | A plateau additionally rolls q_TH=q_Y(-80 deg) q_Z(10*(t-0.8) deg) on 0.8..1.4; outside plateau use endpoint roll held fixed | Elevation/plane unchanged; plateau 3-D speed 10 degrees/s exceeds limit, hold=0; rep speed uses roll, not zero elevation rate |
| P5 | Same as P4 with 5 degrees/s roll | Staticity equality passes; hold 0.6; rep mean=(140+3)/2=71.5 degrees/s |
| P6 | Exact boundary trace: times [-0.4,-0.2,0,0.2,0.4,0.6,0.8,1.0,1.2], e=[0,0,20,40,60,40,20,0,0] | start 0/end1, peak0.4, ROM/peak60, duration1, chronological rise0.4/return0.6; peak equality passes |
| P7 | P6 scale its positive times by 0.8 and pre-rest by 0.8, override start/rest confirmations to160000 us | rep duration0.8 passes at equality, rise0.32/return0.48; output records override hash |
| P8 | P6 change min_phase_us to400000 | rise equals floor, passes; change to400001 => phase_too_short |
| P9 | A override min_rom_rad=80*pi/180, then 81*pi/180 | ROM equality passes, then rom_below_minimum |
| P10 | Irregular axis trace times [-0.4,-0.2,0,0.2,0.5,0.8,1.0,1.2,1.4], e=[0,0,20,40,80,80,40,0,0] | start0/end1.2, peak0.5; hold0 (0.3 s); rep duration1.2, rise0.5, return0.7; speed max200, rep mean140/1.2 degrees/s (not arithmetic interval mean) |

P4/P5 compositions during fixed elevation obey
q_i^-1 q_j=q_Z(delta_roll); this independently establishes the 3-D rate.
Before peak use roll0, after plateau use final roll, so ascent/return magnitudes
remain the axis elevation differences. Equality decisions use exact symbolic
values, not acceptance tolerances added to processing thresholds.
Excluded cases have null metric values; boundary durations remain diagnostics.

## Thorax decomposition and evidence oracles (CP3)

For all cases use A boundaries and q_WH(t)=q_WT(t) q_TH(t), so relative arm
motion remains exactly A. Supply original/mapped samples at every grid row
(no SLERP), matching provenance, and supported synthetic drift bound0.
At start q_WT(0.2)=q0. Let f(t) increase from0 at0.2 to1 at0.8,
stay1 through1.4 and decrease to0 at2.2 on A's grid; define each D below
with angles multiplied by f. Thus endpoints include baseline0 and full
excursion extrema. Device/grid timing and evidence validity cover the window.

| ID | Relative thorax D | Signed component min/max and magnitude |
|---|---|---|
| T0 | identity | all 0/0/0 |
| T1 | R_Y(-10*f degrees) | extension0/+10/10; other axes0 |
| T2 | R_X(-15*f degrees) | lateral0/+15/15; other axes0 |
| T3 | R_Z(+20*f degrees) | axial0/+20/20; other axes0 |
| T4 | R_Z(30*f) R_Y(-20*f) R_X(-10*f) degrees | extension0/+20/20, lateral0/+10/10, axial0/+30/30; this noncommuting order is essential |
| T5 | Any T1–T4 with q0=q_Z(40 deg) q_X(25 deg) | Same components: inverse(q0)*(q0*D)=D, not world Euler differences |
| T6 | R_Y(+10*f), R_X(+15*f), R_Z(-20*f) separately | corresponding component -10/0/10, -15/0/15, -20/0/20 |
| T7 | A plus second A with a new nonidentity movement-start q0 | Independent baseline reset yields same excursion, never previous rep baseline |
| T8 | At one interior row D=R_Y(90 degrees) | all proxy components unavailable, thorax_decomposition_singular; relative rep stays valid |
| T9 | Consecutive D=R_Z(179 deg), R_Z(181 deg) with gap<=limit | principal gamma +179 then -179, branch jump358>180; proxy unavailable thorax_branch_crossing |
| T10 | Trace absent / different grid / wrong source hash or alignment | missing / incompatible trace reasons respectively; A relative metrics remain valid |
| T11 | One thorax row invalid or internal trace interpolation gap | all proxy components unavailable with original row/gap evidence |
| T12 | Heading record absent / drift record absent | thorax_heading_missing / thorax_drift_unbounded, no manufactured zero bound |
| T13 | drift bound1 degree with configured limit1 degree / bound1.01 degree | equality passes / thorax_drift_exceeded |
| T14 | explicit assumed heading/drift, otherwise A | illustrative numerical proxy, Assumed/Experimental, anatomical_eligible=false |
| T15 | old/remounted or expired thorax alignment, mismatched map/world | incompatible trace or upstream M3 global exclusion as applicable; never apply alignment twice |

T4 exact full-angle quaternion is Hamilton q_Z(30) q_Y(-20) q_X(-10).
Independent matrix multiplication gives D31=-sin(-20),
D32=cos(-20)*sin(-10), D33=cos(-20)*cos(-10),
D21=sin(30)*cos(-20), D11=cos(30)*cos(-20). Substitution in the
contract extraction recovers alpha=-10,beta=-20,gamma=30 degrees.
This catches reversed axes/order without using a SciPy-generated truth.

## Session and longitudinal oracles (CP4)

Second oracle B: leading rest times 2.6,2.8,3.0 at0; then
(3.2,20),(3.4,40),(3.6,60),(3.8,60),(4.0,60),(4.2,60),
(4.4,40),(4.6,20),(4.8,0),(5.0,0). Concatenate after A including
valid intervening rest rows. All gaps <=0.5. B boundaries3.2..4.8,
peak3.6; ROM/peak60; duration1.6, rise0.4, hold0.6, return0.6;
rise mean/max100 degrees/s, return mean/max100 degrees/s,
rep mean=(40+60)/1.6=62.5 degrees/s, rep max100. Plane fraction1.

CP4 reviewed erratum (2026-09-26): the original return-speed prose said
200/3 degrees/s, contradicting the unchanged rows: (60-0)/(4.8-4.2)=100
degrees/s. Only that prose is corrected; samples and all U0–U10 truths are
unchanged. See `experiments/M4_CP4_20260926.md` for the audit trail.

| ID | Construction | Expected |
|---|---|---|
| U0 | Quiet C3 | counts0/0/0, no means/max/SD/CV/cadence; unavailable reasons explicit |
| U1 | A only | one-rep values above, no invented SD/CV; proxy_missing does not exclude A |
| U2 | A+B | counts2/2/0; ROM mean70, max80, range20 degrees; sample SD10*sqrt(2) degrees; CV=sqrt(2)/7; active time3.6 s; cadence5/9 s^-1; rest1.0 s, rest n1; mean rep duration1.8, hold0.6, rise0.5, return0.7; mean rep mean-speed66.25 degrees/s |
| U3 | A+B but B fails plane | counts2/1/1; summary equals A, SD/CV unavailable; no rest spanning excluded B |
| U4 | A+B with B proxy absent | relative n2; proxy n1/unavailable1; no proxy fabricated for B |
| U5 | Two eligible ROM values0.5 and1.5 degrees under explicit low-amplitude override | mean1 degree exactly floor, sample SD1/sqrt(2) degree, CV unavailable cv_mean_near_zero |
| U6 | Sessions with equal comparability keys, mean ROM80 then60 degrees | later-earlier=-20 degrees, source hashes differ and retained; both n1 |
| U7 | Change side/exercise/thresholds/gap/calibration/alignment/remount/source type/backend/evidence stratum, each independently | incomparable, report exact differing keys, difference null |
| U8 | Same keys but earlier session has no valid reps | comparison_metric_unavailable, never difference from zero |
| U9 | Sessions provided in reverse temporal order | sort by explicit UTC time; equal timestamps sort session IDs; duplicate ID or missing time raises input error |
| U10 | Global missing M3 alignment/clock evidence | invalid analysis and unavailable counts, not U0 |

U5 lowers rest/start/plane/peak/ROM and phase limits consistently; it is a
summary guard fixture with hand-declared eligible reps, not baseline exercise
acceptance. Sample SD uses denominator n-1=1:
sqrt(((-10)^2+10^2)/1)=10*sqrt(2); mean70 gives CV=sqrt(2)/7.
Cadence counts only eligible rep time:2/(2+1.6)=5/9, independent of rest.
These derivations do not call M4 implementations.

## Required test traceability

CP1 tests reference C cases and plane-fraction oracle; CP2 P cases; CP3 T
cases; CP4 U cases. Add malformed artifact/configuration and exact reason
order assertions. Every test compares to these fixed independent values,
not to a second call of the code under test. Counts/interval ownership/QC
reasons are exact; SI tolerances are those in the contract. CP5 separately
declares upstream AHRS numerical tolerance and preserves these direct-input
oracles. Noise/loss robustness and recorded replay are M5 work. CP0 alone
does not claim any of these executable tests has passed.
