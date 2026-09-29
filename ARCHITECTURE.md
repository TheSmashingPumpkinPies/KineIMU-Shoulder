# Architecture — KineIMU Shoulder

## Pipeline

```text
Live dual IMU | Recorded Replay | Synthetic Ground Truth
→ normalized, provenance-bearing dual-node streams
→ QC → Sensor Calibration
→ Sensor-to-Segment Alignment → Orientation Estimation
→ Thorax–Humerus Relative Orientation → Exercise Segmentation
→ shoulder kinematics → exercise metrics → Validation → Session Summary
```

Hardware is an input backend, not a dependency of the analysis stack. The current
BLE/USB recorders remain transport adapters. M2 must add or confirm the smallest
equivalent interfaces needed for deterministic replay and synthetic sources; do not
rename working code merely to match a `DataSource` diagram.

Alignment supplies explicit sensor-to-segment transforms. The implementation must declare
whether calibrated signals are rotated before AHRS or sensor-frame orientation is rotated afterward.
Never apply alignment twice.

## Code boundaries

Retain kineimu_shoulder/io/ and validation/; add calibration/, orientation/, frames/
or shoulder/ only when the corresponding milestone implements them;
retain firmware/sticks3/ as historical M0 evidence and create the active upstream-Zephyr
XIAO firmware application only for the concrete M1 implementation; retain datasets,
protocols, integrations and benchmarks.
Create sync/, alignment/ or source abstractions only for a concrete implementation requirement.
No new empty application modules are necessary for this pivot. Validation stays separate from production.

Natural functions: estimate_orientation, calibrate_imu, synchronize_streams,
compute_humerothoracic_rom, segment_shoulder_repetitions, compute_thorax_compensation.
These are design examples, not existing APIs.
No UniversalMotionAnalyzer, GenericJoint, GenericBodyModel, BodySegmentGraph or ArbitrarySensorNetwork.

## Frames and timing

SI and normalized quaternions internally. M2 must freeze component order, handedness,
active/passive and sensor→segment→world conventions with tests.
For active R_WT mapping thorax vectors to a common world and R_WH mapping humerus to that same world,
R_TH = transpose(R_WT) R_WH maps humerus to thorax. Quaternion composition follows the declared convention.
Independent AHRS startup frames are not automatically the same world.

Define humeral long axis, test side, thorax axes and neutral baseline. Elevation is derived from the
aligned long-axis relationship, not quaternion norm or arbitrary Euler component.
Thorax excursion requires its own documented decomposition.
Static gravity alone cannot determine heading; relative yaw requires drift characterization.

Synchronize before comparing orientations; retain device times and mappings.
Host arrival times are transport observations, not sample times.

## Rules

Raw immutable; QC failures explicit; coordinate/unit conversions traceable.
Resampling creates processed data with source hashes, grid and gap policy; never hide it in adapters.
Enforce [BACKEND_CONTRACTS.md](BACKEND_CONTRACTS.md).
Prefer mature algorithms; new algorithms require justification and known-input tests.
Formal results carry provenance/evidence labels. Embedded results require Python-reference comparison.
Synthetic generators and replay readers must identify their source type and preserve
configuration/source hashes. No clinical interpretation is implied.

## Explicit short-gap reconstruction (ADR-010)

An optional offline processed stage may estimate a single gravity-supported
collinear rate transition between retained calibrated node samples before
orientation estimation. Original observations remain unchanged; inferred rows
retain bracket/time/fit/model provenance. Unobservable or incompatible gaps
remain unreconstructed. This stage is separate from transport and AHRS
adapters; the pinned AHRS itself is unchanged. See
[ADR-010](docs/adr/ADR-010-explicit-short-gap-reconstruction.md).
