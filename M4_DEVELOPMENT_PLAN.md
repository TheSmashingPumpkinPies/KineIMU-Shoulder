# M4 Development Plan — Focused Exercise Analytics

Status: M4.0–M4.5 / CP0–CP5 passed on `main` (2026-09-26, Asia/Shanghai).
M0–M4 are accepted at their documented evidence scope. This plan
implements the M4 clauses of `ACCEPTANCE_CRITERIA.md`, `01_PROJECT_SPEC.md`
and `02_DEVELOPMENT_ROADMAP.md`; M5 remains the separate robustness and
recorded-replay validation milestone.

M4.0/CP0 artifacts (2026-09-26): `protocols/M4_EXERCISE_CONTRACT.md`
freezes `m4-exercise/1.0`; `tests/fixtures/M4_KNOWN_EXERCISES.md` records
independent analytical truths; `experiments/M4_CP0_REVIEW_20260926.md`
records the specification cross-review. M4.1/CP1 plane verification and
candidate segmentation passed its direct-input synthetic gate on 2026-09-26;
see [the CP1 report](experiments/M4_CP1_20260926.md). M4.2/CP2 per-repetition
metrics passed its direct-input synthetic gate on 2026-09-26; see
[the CP2 report](experiments/M4_CP2_20260926.md). M4.3/CP3 explicit thorax
preparation and excursion proxy passed its direct-input synthetic gate;
see [the CP3 report](experiments/M4_CP3_20260926.md). M4.4/CP4 explicit
set/session summaries and chronological comparisons passed the synthetic gate; see
[the CP4 report](experiments/M4_CP4_20260926.md) for verification. M4.5/CP5
passed exact-orientation M2.4/M3→M4 integration and two-run canonical byte
equality; see [the CP5 report](experiments/M4_CP5_20260926/README.md).
Overall M4 is accepted at synthetic numerical/evidence scope. No physical
anatomical or clinical accuracy is established. M5 robustness/replay is next.

## Outcome and boundary

M4 produces versioned, QC-aware flexion and abduction exercise results:
detected/valid/excluded repetition counts; per-repetition humerothoracic ROM,
peak elevation, phase/rep/rest/hold durations and angular speed; rep-to-rep
variability; thorax orientation excursion as a compensation **proxy**; and
comparable session summaries. These are derived research quantities, not
diagnoses, clinical outcome scores or isolated glenohumeral/scapular angles.

The primary input is M3's common-time `ElevationResult` and interval
`AngularSpeedResult`, including row/interval `valid` and `reason`, side,
source hashes, `max_sample_gap_us`, and M2 clock/heading and M3 alignment
evidence. An exercise label is caller supplied (`flexion` or `abduction`).
M4 must independently check its geometric consistency using the full
`q_TH` long-axis direction in thorax axes; unsigned elevation alone cannot
identify a plane. Ambiguous/out-of-plane motion is explicitly excluded or
flagged by the versioned rule, never silently relabeled.

Thorax excursion additionally requires an **explicit, aligned thorax
orientation trace** on the same common-time grid, with its own source hash,
clock map, alignment, heading relation, interpolation/gap history and row
mask. M3's `q_TH` is insufficient to recover absolute thorax movement.
Preparing this processed trace is a visible operation outside any backend
adapter; CP0 decides the smallest existing-interface extension needed.
If a valid trace is unavailable, thorax excursion is unavailable with a
reason while otherwise eligible relative-movement metrics may remain usable.
Six-axis yaw drift and assumed anatomical alignment remain evidence limits.

## Stages and checkpoints

| Stage | Deliverable | Checkpoint / exit gate |
|---|---|---|
| M4.0 — Metric and evidence contract | `protocols/M4_EXERCISE_CONTRACT.md` and independently derived synthetic fixtures. Freeze exact input/output fields, exercise declaration and plane gate, all threshold values and units, endpoint inclusivity, hysteresis/state machine, hold/staticity rule, gap/partial policies, angular-speed source, thorax decomposition, summary denominators, comparability keys, evidence and error tolerances. | **CP0:** Cross-review with M3/M2 contracts, project specification and acceptance criteria. Fixture truths are fixed before production code. Every output has a validity/exclusion path. No public acquisition-schema change or inferred heading. |
| M4.1 — Plane gate and repetition segmentation | A deterministic, versioned state machine over common-time elevation plus `q_TH` direction: rest → elevation → optional hold → return → rest. Preserve sample/interval boundaries and all detected candidates, including excluded or partial candidates. | **CP1:** Independent traces cover clean flexion/left and right abduction, ambiguous/out-of-plane direction, zero/one rep, threshold equality, jitter/hysteresis, starts/ends mid-rep, irregular timestamps, invalid rows and over-limit gaps. No bridge or count inflation. |
| M4.2 — Per-repetition metrics | Compute M3-compatible closed-interval ROM, peak, total/elevation/return/rest/hold durations and phase speed statistics. State explicitly whether a speed is 3-D relative quaternion magnitude or signed elevation rate; never conflate them. | **CP2:** Analytical asymmetric traces with a timed plateau recover count, ROM, peak, tempo/hold and speed within CP0 tolerances. QC-invalid reps retain reasons and have no valid numeric summary contribution. Boundary intervals, denominator and units are tested. |
| M4.3 — Thorax excursion proxy | Consume the evidenced common-time thorax orientation trace and compute per-rep extension, lateral-flexion and axial-rotation excursion relative to movement-start thorax orientation, with signed extrema and magnitude. | **CP3:** Independent known rotations and noncommuting combinations verify axis/order/sign convention and baseline reset; missing/assumed heading, incompatible provenance, gaps, drift limit and unavailable trace yield explicit evidence/validity labels. No compensation score. |
| M4.4 — Set and session summaries | Valid/total/excluded counts and reasons; mean/max ROM and peak, phase/hold/rep duration and speed summaries; ROM SD/CV/range with minimum-count and near-zero rules; rest/cadence with exact active-time denominator; side/protocol/definition/evidence-aware within-session and longitudinal comparison. | **CP4:** Zero, one and multiple eligible reps; sample SD and CV guard; exclusion propagation; changed side, thresholds, calibration, alignment or source-type comparability; empty denominator and ordering tests. Incomparable sessions are reported as such, not pooled. |
| M4.5 — Integration and closeout | One deterministic synthetic M2/M3 → M4 example and versioned derived/report artifacts with exact command, source/configuration/lock/output hashes, units, validity counts and numerical error table. Refresh user and developer documentation. | **CP5:** Two locked-environment runs produce byte-identical canonical outputs; all M4 contract cases and full project checks pass. Report synthetic truth separately from physical/clinical validation. Hand off perturbation and recorded-replay robustness work to M5. |

## CP0 decisions that must be made before numerical code

1. **Exercise-plane rule.** Use the side-aware anterior/lateral components
   of `R_TH[0,0,1]` in the declared thorax frame. Specify minimum elevation
   before direction is identifiable, signed direction, angular tolerance,
   and what fraction of a candidate must satisfy the declared plane.
   The caller's exercise label is retained even when its plane gate fails.
2. **Segmentation thresholds.** Specify start/return levels, peak/prominence,
   minimum phase and rep durations, hold target band, angular-staticity
   threshold, minimum hold, hysteresis, debouncing, equality behavior and
   deterministic tie-breaking. All values are configurable processing
   parameters with a definition version and provenance; none is a clinical
   normal-ROM standard.
3. **Time and QC.** Use observed `common_time_us`, exact grid boundaries and
   M3's declared maximum gap. State which adjacent intervals belong to each
   phase and how a boundary interval is counted once. A candidate containing
   an invalid row/interval or forbidden gap is excluded under the frozen
   policy; no interpolation, NaN filling or partial-valid summary is hidden.
4. **Thorax reference.** Specify the common-world quaternion convention,
   movement-start reference rotation, decomposition order/axis signs,
   singularity handling and yaw/heading drift eligibility. Preserve original
   thorax samples and mapping provenance when constructing the processed
   common-grid trace.
5. **Summaries.** Define exact rep eligibility, total/valid/excluded counts,
   denominator for cadence, sample SD (`n ≥ 2`), CV near-zero guard, and
   longitudinal comparability keys. A trend is a descriptive difference,
   never a clinical recovery score.
6. **Output contract.** Version the M4 derived artifact and expose source
   type, all source/configuration hashes, side, exercise, definitions, units,
   phase endpoints, thresholds, counts, validity/reasons and evidence labels.
   Numeric units remain SI internally: rad, rad/s, s and int64 µs.

CP0 records the exact numeric choices and their rationale in the M4
contract and fixtures. Use that versioned contract for adopted processing
parameters; this planning outline does not override the frozen definitions.

## Verification and handoff

Write tests with independently established expected values before each
algorithm stage; keep fixtures/validation reports separate from production.
Run focused checks at each checkpoint. Before declaring a checkpoint passed,
run `pytest`, `ruff check .`, `mypy --strict kineimu_shoulder`,
`python scripts/check_docs_consistency.py` and `git diff --check` and record
the actual results. A documentation-only planning checkpoint needs the docs
check and whitespace check; it makes no M4 numerical acceptance claim.
Commit coherent work, refresh `CURRENT_TASK.md`/`HANDOFF.md` and
`PROJECT_STATUS.md` when project status changes, append `CHANGELOG_DEV.md`,
and record the exact HEAD and next action after each segment.
