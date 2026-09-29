# M3 Development Plan — Shoulder Kinematics

Status: M3.0/CP0 passed, 2026-09-25 (Asia/Shanghai). Planning baseline: `main`
at `d2a9ef1`. M0, M1 (dual USB) and M2 are accepted; M3 numerical implementation
has not started. This plan implements the M3 clause of `ACCEPTANCE_CRITERIA.md`
without changing the public M1/normalized data schema or reopening hardware.

## Outcome and evidence boundary

M3 consumes the M2.4 `RelativeOrientationResult` (`q_TH`, common-time grid,
validity/reasons, clock maps, heading relation and source hashes), together
with explicit thorax/humerus alignment and source-type evidence. It produces
provenance-bearing humerothoracic movement approximations: long-axis elevation,
relative angular speed, and ROM and elapsed duration for a caller-supplied
movement interval. Internal angles use radians and angular speed uses rad/s;
presentation may convert units explicitly.

The retained M1 dual USB capture has no independently established pairwise
clock map, common heading or measured anatomical alignment. It can exercise
per-node replay and QC, but cannot be used for a measured anatomical M3 result.
M3 known-motion gates therefore use two synthetic segment streams with known
clock, heading, axes and alignment. They establish numerical correctness, not
physical or clinical accuracy. An assumed mapping/heading or illustrative
alignment stays `Assumed/Experimental`; an invalid M2 row never becomes a
plausible M3 number. A `Derived` calculation on synthetic truth remains
explicitly tagged synthetic, never `Validated` against people or motion capture.

## Sequence and checkpoints

| Stage | Deliverable | Checkpoint / exit gate |
|---|---|---|
| M3.0 — Contract and fixtures | `protocols/M3_KINEMATICS_CONTRACT.md` freezes the processed input/output contract, test side and axes, neutral definition, source/evidence labels, interval endpoint/gap policy, metric equations, units, invalidity reasons and numerical tolerances. Record independently constructed known-motion fixture values before implementation. | **CP0:** Review the contract against M2.4, `01_PROJECT_SPEC.md` and `DATA_FORMAT.md`. Explicitly require M2 validity and alignment evidence. No public schema change, inferred anatomical heading, or M1 pairwise anatomical claim. |
| M3.1 — Long-axis elevation | Add the smallest production function under `kineimu_shoulder/shoulder/` to rotate humeral +Z into thorax coordinates with valid `q_TH` and calculate elevation from its angle to thorax +Z. Carry common times, row validity/reasons, evidence and source identities. | **CP1:** Test neutral 0°, known 90° flexion and side-declared abduction, 180° reversal, sign-invariant `q`/`-q`, noncommuting thorax/humerus rotations, and invalid/missing alignment and clock/heading evidence. Expected angles come from independent analytical vector geometry. |
| M3.2 — Relative angular speed | Calculate the shortest relative quaternion rotation between adjacent valid `q_TH` samples divided by the observed positive common-time delta. Output an interval value with its two endpoints, not an invented point-sample timestamp; state that this is the magnitude of three-dimensional relative angular velocity, not the signed derivative of elevation. | **CP2:** Constant-rate and variable-time analytical fixtures recover rad/s; sign-flipped quaternions, zero motion, invalid endpoints and over-limit gaps do not create spikes or bridge missing data. A full turn between only two samples demonstrates the unavoidable aliasing limit and cannot be reported as measured speed. Exact source, units and interval semantics are recorded. |
| M3.3 — Interval ROM and duration | For a caller-supplied closed sample-time interval, compute elevation maximum minus minimum and elapsed time from its actual endpoint timestamps. Require at least two valid samples, valid evidence throughout and no over-limit gap. Return explicit exclusion reasons instead of partial metrics. | **CP3:** Known triangular and asymmetric elevation traces recover ROM and duration; baseline/peak distinction, irregular timing, single sample, invalid rows, gaps and reversed/out-of-range boundaries are tested. No repetition detection or hold/tempo algorithm is introduced. |
| M3.4 — Integration and closeout | Run the complete synthetic two-node M2.4 → M3 path; emit a versioned processed/derived example with source and configuration hashes, alignment/heading/clock status, validity counts, units and exact command. Document numerical error and the M1 evidence limit. | **CP4:** Two locked-environment runs produce identical canonical outputs; M3 acceptance cases and full project checks pass. The report distinguishes Observed source times, Derived computations, Assumed/Experimental inputs and absent physical validation. Handoff to M4 names the interval signal and QC contract. |

## Decisions to lock at CP0

- `T` axes are +X anterior, +Y left, +Z superior; `H` +Z points proximally
  along the humeral long axis in the declared arms-down neutral reference.
  Elevation is the angle between `R_TH [0,0,1]` and `[0,0,1]`, bounded to
  `[0,π]`. It is not an Euler component, glenohumeral angle or scapular angle.
- M3 records exercise side and alignment method/ID/validity. A synthetic known
  alignment is sufficient for synthetic tests. A physical anatomical claim
  requires measured alignment suitable for that session; remounting invalidates
  it. Gravity-only alignment cannot establish anterior/posterior or
  medial/lateral heading.
- The M2.4 grid and mask are authoritative for paired samples. M3 does not
  infer a clock map, resample, patch NaNs, pair device rows, or downgrade an
  invalid reason. It retains source hashes and the M2 clock/heading artifacts.
- Relative angular speed uses the principal rotation angle of
  `inverse(q_TH[i]) ⊗ q_TH[i+1]` divided by `Δt`. This is an interval average;
  it cannot resolve within-interval motion or aliasing. Signed elevation
  derivative and phase-specific speed belong to a later explicit M4 choice.
- A requested interval uses existing sample-time endpoints and is wholly
  eligible or excluded. No interpolation into an endpoint or across a gap is
  implied. The contract will freeze the maximum gap and endpoint rules before
  implementation; these are processing parameters, not clinical thresholds.
- All numeric output is finite for valid rows/intervals. Invalid results carry
  an exclusion reason and no usable numeric metric. Evidence can only stay the
  same or become more restrictive downstream. Output schema is a versioned M3
  derived artifact; the public acquisition schema remains unchanged.

## Verification and handoff discipline

Write analytical tests before numerical implementation. Each expected-value
assertion cites the construction of its truth; include pure known rotations,
noncommuting frames, irregular timing and invalid evidence. Run focused tests
after each stage and, before each checkpoint/handoff, run `pytest`,
`ruff check .`, `mypy --strict kineimu_shoulder`,
`python scripts/check_docs_consistency.py` and `git diff --check`. Keep
validation fixtures and reports outside production code, commit small valid
segments, and refresh `CURRENT_TASK.md`, `PROJECT_STATUS.md` when changed,
`HANDOFF.md` and `CHANGELOG_DEV.md` after each segment.

M3 completion requires CP0–CP4 evidence plus the M3 acceptance criterion.
M4 owns automatic flexion/abduction exercise segmentation, repetition count,
per-repetition/phase summaries, holds, variability and thorax-compensation
proxy. M5 owns broader perturbation robustness and recorded replay validation.

**Disposition:** CP0–CP4 passed at the synthetic numerical and evidence
interface scope. CP4 integration, two-run artifact hashes and M3 acceptance
are in `experiments/M3_CP4_20260925/README.md`. M4 exercise analytics is
next; the M1 USB pair remains ineligible for anatomical M3 claims.
