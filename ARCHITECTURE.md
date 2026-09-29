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
BLE/USB recorders remain transport adapters. replay and synthetic inputs use the same explicit normalized-data boundary.

Alignment supplies explicit sensor-to-segment transforms. The implementation must declare
whether calibrated signals are rotated before AHRS or sensor-frame orientation is rotated afterward.
Never apply alignment twice.

## Code boundaries

`io/` holds transport, packet parsing, raw-count conversion and replay. Calibration,
orientation, frames, reconstruction, relative orientation, shoulder, exercise,
thorax and summary modules implement the analysis pipeline. `validation/` holds
synthetic sources, independent oracles and replay/Demo acceptance orchestration;
validation remains separate from production. `firmware/xiao_nrf52840_sense/` is the
reference acquisition application. Backend-specific conversion stays in adapters.

## Frames and timing

SI and normalized quaternions internally. Component order, handedness,
active/passive and sensor→segment→world conventions follow the tested M2 contract.
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
Enforce [BACKEND_CONTRACTS.md](DEPENDENCIES.md).
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
