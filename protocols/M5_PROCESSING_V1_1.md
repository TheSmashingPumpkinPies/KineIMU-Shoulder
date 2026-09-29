# M5 processing/1.1 — explicit short-gap reconstruction

Maintainer authorization: on 2026-09-27 the maintainer approved a new processing
contract, correction of missing-sample integration/velocity support and M2–M5
reacceptance, preserving raw data, all seeds and every numerical threshold.
This version supersedes only CP0's requirement for an entirely unchanged S/Q
processing path. The frozen m5-validation/1.0 file, independent truth, manifest
and failed formal4 evidence remain immutable. E is unchanged. All original
10 ms speed comparisons remain acceptance gates with the SAME 6 deg/s W limit,
full-window denominator, >=0.98 coverage and 100% eligible-rep recall. No
row/seed removal, coarse-support relabeling or tolerance widening is authorized.

## Why a separate processed stage is necessary

Deleting a 90-degree flexion first-peak row at 6.500 s leaves exact angles
89.4 and 90 degrees at 6.490/6.510 s. Their SLERP produces 89.7 at 6.500 s,
so the preceding 10 ms speed is 30 rather than 60 deg/s. Even a perfect AHRS
at retained observations cannot meet the frozen 6 deg/s interval gate.
The right-endpoint body rate likewise describes only the branch ending at
that observation, rather than the whole missing-sample bracket. Independent
rational proof: experiments/M5_CP3_UNBLOCK_20260927/corner-support-proof.json.

## Explicit calibrated-observation reconstruction

`reconstruct_short_gaps` runs after sensor calibration and R_NS conversion,
before the pinned AHRS. It never reads truth, motion IDs, continuous trajectory
parameters, labels, deleted observations, nominal knots, lost true timestamps or
random seeds. It estimates one interior transition using ONLY adjacent retained
node-frame force/rate and observed device times. Every original timestamp,
force and rate remains exactly unchanged; each inferred row has original
bracket indices, inferred time, endpoint-fit residual and explicit assumptions.

The declared model is one collinear piecewise-constant body-rate transition
in a gravity-dominated short bracket. This is an offline model, not a physical
observability claim for arbitrary acceleration or yaw. The gap must exceed
1.5 times the median observed interval and remain <= the existing 0.05 s limit.
A gap above that limit and invalid input remain untouched and are rejected by
the unchanged AHRS, with the original stage/message.

Branch confirmation requires rate change norm >=0.1 rad/s, cross-product norm
<=1e-4 (rad/s)^2, and each neighboring rate within 0.001 rad/s of its branch.
Both force norms must be within 0.05 m/s^2 of standard gravity. Each gravity
projection perpendicular to the transition axis must have norm >=0.1. Yaw
about gravity is unobservable and is never reconstructed. Integrated rotation
must stay below pi to avoid a wrapped angular-displacement ambiguity.

With n=(w_before-w_after)/norm(w_before-w_after), normalized force g0/g1,
and perpendicular projections p0/p1, the observable signed displacement is
atan2(n dot (p1 cross p0), p1 dot p0). For bracket duration dt, solve
t_before=(displacement-(n dot w_after)*dt)/norm(w_before-w_after).
Round the resulting device time ties-to-even to integer microseconds, require
strictly interior time, and use SciPy Rotation to propagate g0 to the transition
and through the second branch. Endpoint unit-force residual must be <=0.001.
Incompatible/ambiguous brackets remain unchanged and their errors stay in gates.
No new rotation implementation, filter, gain override or offset estimator is used.

The inferred transition receives the preceding branch's LEFT derivative, as
in the frozen observation convention. imufusion integrates each explicit
observed/reconstructed interval with its original adapter/default configuration.
The post-AHRS stream includes these processed transition rows, so normal SLERP
does not bridge a detected rate discontinuity. Observed orientation errors
remain evaluated ONLY at original retained true observation times. Original
loss counters and retention denominators remain unchanged. Inferred timestamps
are model estimates and never called recovered raw observations. Model
assumptions remain exported, source type synthetic and anatomical_eligible=false.

## Evidence and reacceptance

Map/heading source references are resolved against independent expected hashes
before use. Float64 integer-clock endpoint roundoff is removed consistently
by M2, M4 validation and thorax processing; genuine fractional deficits still
prohibit extrapolation. See the M2 processing contract addendum.

Reacceptance requires independent reconstruction fixtures, all prior failed IDs,
all M2/M3/M4 regressions, complete frozen 1142-case matrix in two NEW clean-lock
processes, byte equality and independent scalar/source/support audit. The audit
verifies original-row conservation, inferred bracket support and observation-time
geodesics. All old failed and partial attempts stay retained. CP3 cannot pass
before this complete reacceptance; CP4 and CP5 remain separate.
