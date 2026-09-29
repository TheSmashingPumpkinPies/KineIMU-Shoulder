# KineIMU Shoulder — Project Specification

Active specification, 2026-09-07. Authority: [PROJECT_SCOPE.md](../PROJECT_SCOPE.md).
Original v0.2 materials remain [historical — historical availability](PUBLIC_AUDIT.md#not-distributed-in-this-source-snapshot).

## System

A: thorax/reference node. B: upper-arm/humerus node. The future human placement concept
is retained in MOUNTING_PROTOCOL, but wear and don/doff validation are outside current V1.
Initial V1 exercises: flexion and abduction. Scaption is future work. Measure
humerothoracic relative movement approximations.

## Eight V1 core metric families

All are planned Derived engineering quantities, NOT yet implemented or Validated.
A repetition is elevation → optional hold → return; rest lies between repetitions.
Only QC-eligible repetitions enter valid summaries; retain total, valid and excluded counts/reasons.
Before implementation freeze thresholds, interval endpoints, filters, missing-data and partial-rep policies.
Parameters are configurable and documented, never clinical normal standards.

| ID | Core family | Definition and planned outputs |
|---|---|---|
| 1 | Humerothoracic ROM | Per-rep maximum minus minimum upper-arm-relative-to-thorax elevation; session mean and maximum per-rep ROM. Record start angle and exercise plane. ROM differs from absolute peak. |
| 2 | Peak Elevation Angle | Per-rep maximum humerothoracic elevation; session mean peak, maximum and distribution. |
| 3 | Repetition Count | Total detected and valid repetitions; deterministic signal-processing segmentation first; explicit partial/invalid handling. |
| 4 | Movement / Phase Duration | Total repetition, elevation phase, return phase, rest interval and cadence/tempo. Document denominator, e.g. valid reps per active minute. Hold separately represented. |
| 5 | Hold Duration | Time near configured target with configured angular-velocity/staticity criteria; per-rep and mean duration. Define hysteresis and minimum duration before M3. |
| 6 | Angular Velocity | Peak and mean, elevation-phase and return-phase speed. Specify source: relative quaternion increments, transformed gyro difference, or elevation derivative; these differ. Document axis, signed versus magnitude, filtering and conversion. Internal rad/s; display rad/s or deg/s explicitly. |
| 7 | Rep-to-Rep Variability | ROM SD, CV and range; sample SD for at least two valid reps, CV = SD / absolute mean with configured near-zero guard and undefined flag. Explicit time normalization for trajectory RMSE to mean or normalized deviation; document grid, phases and normalization. |
| 8 | Thorax Compensation Excursion | Per-rep maximum extension, lateral-flexion and rotation excursion relative to thorax orientation at movement start. Document decomposition, direction, signed extrema and excursion magnitude. No compensation score. |

Trajectory resampling preserves original times and excludes unbridgeable gaps.
Movement variability describes consistency, not neurological impairment, abnormal motor control or pathology.
Thorax excursion describes objective movement only.

## Extensions

| ID | Extension | Boundary |
|---|---|---|
| 9 | Target Attainment Rate | Valid reps reaching target / all valid reps; undefined at zero denominator. Target from user, research protocol or therapist prescription; no project-defined normal ROM. |
| 10 | Movement Smoothness | SPARC or LDLJ candidates; no default before validation of signal choice/sensitivity. Raw jerk is not a rehabilitation-quality claim. |
| 11 | Within-Set ROM Trend | First/last group comparison or ROM slope; specify group size and missing-rep policy. May call within-set ROM decline; never fatigue index. |
| 12 | Longitudinal Trend | Comparable-session ROM, thorax compensation, variability, validated smoothness and completion; record side/protocol/calibration changes. Rehabilitation progress tracking, not clinical outcome score. |

## Excluded measurements

Glenohumeral ROM; scapular upward rotation, posterior tilt and internal/external rotation;
scapulohumeral rhythm; shoulder instability score; rotator cuff diagnosis; pain prediction;
injury-risk prediction; fatigue score; clinical rehabilitation outcome score.
Two surface IMUs do not isolate scapular/glenohumeral contributions.
External rotation needs dedicated heading evidence before accuracy claims.

## Evidence labels

- Observed: raw sensor channels, timestamps, counters and recorded reference annotations.
- Derived: orientation, relative orientation, segmentation and all eight core metrics.
- Assumed: mounting rigidity, anatomical axes, heading initialization and thresholds.
- Validated: only outputs with linked dataset, reference, uncertainty, protocol/population and report.
- Experimental: unvalidated methods, extensions and protocols.

Labels can coexist: Derived becomes Validated only within tested conditions.
No shoulder metric is currently Validated. See [VALIDATION.md](../VALIDATION.md).

Public-export note: unavailable internal navigation is redirected to the evidence-availability index; scientific claims and original target names are retained by the export record.
