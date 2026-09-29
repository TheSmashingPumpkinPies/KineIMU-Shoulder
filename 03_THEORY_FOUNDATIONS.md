# KineIMU Shoulder — Theory Foundations

Current reading map; no metric implementation or validation result is implied.

## M1

Specific force versus translational acceleration; bias/scale/noise/saturation;
ODR versus output rate, anti-aliasing/filter delay, FIFO, counters and bounded buffering.
Device versus host clocks, offset/rate mismatch, synchronization uncertainty and packet/sample loss.
Preserve raw time; explicit resampling with gap policy.

## M2

SO(3), quaternion conventions and composition; sensor/world/anatomical transforms.
Static gravity constrains tilt, not full heading. AHRS acceleration assumptions fail during dynamics.
Separate IMU calibration from sensor-to-segment alignment and common-heading initialization.
Skin attachment and humeral-axis alignment introduce uncertainty.
Relative orientation cancels a common reference rotation, not arbitrary independent yaw drift.
Characterize yaw, relative heading and recording-duration dependence.

## M3 / M4

Humerothoracic elevation versus per-rep excursion ROM and absolute peak.
Deterministic segmentation, hysteresis, partial reps and optional holds.
Relative angular speed differs from scalar elevation derivative; filtering affects peaks/timing.
ROM variability and time-normalized trajectories need defined denominators and missing-data treatment.
Thorax excursions need a repetition-start reference and anatomical decomposition;
they are not diagnostic compensation scores.

## M5 / M6

Analytical/synthetic ground truth, replay determinism, perturbation robustness, uncertainty
and traceable demo data. Human video, motion capture, repeatability and don/doff effects are future work.
Agreement differs from correlation; repeated reps do not provide independent participant sample size.
Threshold tuning must be separate from formal validation; longitudinal sessions need comparability.
SPARC/LDLJ remain candidates; no raw-jerk quality claim or fatigue interpretation.
Use [VALIDATION_PLAN.md](VALIDATION_PLAN.md) and [metric specification](01_PROJECT_SPEC.md)
for scientific boundaries. Detailed algorithm/literature choices are milestone gates.
