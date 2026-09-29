# KineIMU Shoulder — metric definitions and implementation

The eight V1 core families are implemented in the [M3 kinematics](../protocols/M3_KINEMATICS_CONTRACT.md)
and [M4 exercise](../protocols/M4_EXERCISE_CONTRACT.md) interfaces. Their numerical
and evidence gates are tested against known inputs and deterministic synthetic
references; see [validation coverage](validation/coverage.md). This establishes
engineering behavior within the tested conditions, not human or clinical accuracy.

Flexion and abduction are the supported V1 exercises. A is the thorax reference;
B is the upper arm. Internal rotations use quaternions, angles use rad, speed
uses rad/s and durations use s. Displays explicitly convert angles to degrees.
Thresholds belong to the versioned `m4-thresholds/1.0` profile and are configurable
engineering parameters. They are not clinical normal standards.

## Eight V1 core metric families

| ID | Core family | Implemented definition and output |
|---|---|---|
| 1 | Humerothoracic ROM | Maximum minus minimum upper-arm-relative-to-thorax elevation over an eligible interval/repetition; session aggregation over valid reps. ROM differs from absolute peak. |
| 2 | Peak Elevation Angle | Maximum unsigned humerothoracic long-axis elevation over the repetition; valid-rep session aggregation. |
| 3 | Repetition Count | Deterministic elevation/hold/return segmentation; detected, valid and excluded counts with partial, interrupted and invalid reasons. |
| 4 | Movement / Phase Duration | Repetition, elevation, return, preceding rest and cadence. Hold intervals have separate ownership; rise + return + hold equals repetition duration. |
| 5 | Hold Duration | Sum of qualifying contiguous intervals near the repetition peak, satisfying the configured angular band, speed limit and minimum hold duration. Zero means no qualifying observed hold. |
| 6 | Angular Velocity | Principal 3-D relative quaternion increment divided by the observed interval duration; phase/rep maximum and duration-weighted mean magnitude. This is interval angular speed, not signed elevation derivative or instantaneous gyro rate. |
| 7 | Rep-to-Rep Variability | Valid-rep ROM range, sample SD and CV, with minimum-count and near-zero-mean guards. Trajectory-deviation metrics are not delivered by the V1 summary interface. |
| 8 | Thorax Compensation Excursion | Movement-start-relative thorax extension, lateral-flexion and axial-rotation proxy; signed extrema and maximum absolute excursion. Requires compatible thorax trace, heading and bounded drift evidence. No compensation score. |

Invalid or unsupported values remain unavailable with reasons; JSON uses `null`,
never an invented zero. Original timestamps and QC breaks are retained. Resampling
is explicit processed data and never bridges unsupported gaps. Repetition variability
describes consistency; thorax excursion describes movement. Neither implies pathology.
Exact endpoint, denominator, filtering, interpolation, branch and exclusion rules
are specified in the linked contracts and their known-input tests.

## Extensions

| ID | Extension | Current boundary |
|---|---|---|
| 9 | Target Attainment Rate | An extension, not a V1 core accuracy claim; any target and denominator require an explicit protocol. No project-defined normal ROM. |
| 10 | Movement Smoothness | SPARC/LDLJ candidates remain outside the V1 core; no validated default or rehabilitation-quality claim. |
| 11 | Within-Set ROM Trend | An extension requiring group/slope and missing-rep policy; never a fatigue index. |
| 12 | Longitudinal Trend | Comparable-session summaries support descriptive core-metric comparison with side, protocol, calibration and configuration identity. No clinical outcome score. |

## Evidence labels and interpretation

- Observed: sensor channels, timestamps, counters and recorded annotations.
- Derived: orientation, relative orientation, segmentation and computed metrics.
- Assumed: constructed clocks, alignment, heading, mounting rigidity and thresholds.
- Validated: only within the explicitly linked reference, protocol and tested conditions.
- Experimental: unvalidated assumptions, extensions and methods.

Labels can coexist. Synthetic numerical validation does not make an output
anatomically eligible. The bundled demo has `anatomical_eligible=false`. Physical
replay without supported pairwise timing, heading or anatomical alignment returns
unavailable shoulder metrics. Static gravity alone does not establish AP/ML heading.

Outputs describe humerothoracic movement. Two surface IMUs do not isolate
glenohumeral or scapular motion. Injury risk, diagnosis, pain prediction, fatigue,
instability and clinical outcome scores are excluded. Human-subject and
motion-capture validation remain outside V1; see [scope](../PROJECT_SCOPE.md)
and [validation](../VALIDATION.md).
