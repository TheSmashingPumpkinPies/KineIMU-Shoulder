# Backend Contracts — KineIMU Shoulder

Active M1 contracts and pinned backend candidates.

## M1 raw-count host adapter — Implemented

Implementation: `kineimu_shoulder.io.m1_raw`.

The adapter accepts decoded `m1_packet.Sample` values whose acceleration and
angular-rate fields are immutable LSM6DS3TR-C signed int16 register counts in
sensor register order X, Y, Z. The caller must supply the configured ranges,
nominal sensitivities and a `SensorToNodeTransform`; the adapter does not infer
any of them. For the retained Node B smoke, the transform is explicitly

```text
node = I * sensor
sensor axes = (sensor_x, sensor_y, sensor_z)
node axes   = (node_x, node_y, node_z)
```

The nominal scales are 0.122 mg/LSB at ±4 g and 17.50 mdps/LSB at ±500 °/s,
with explicit conversions to m/s² and rad/s. The output retains raw counts,
sample sequence, device timestamp and sample flags and produces one SI row per
input sample. It never interpolates, resamples, changes timestamps or declares
an anatomical/sensor-to-segment alignment.

## imufusion — M2.3 Adapter Contract

### Intended role

Python orientation reference and possible embedded counterpart.

### Tested API

Baseline: imufusion 1.3.3 on CPython 3.12.14.

- call `Ahrs.set_sample_period(period_s)` before updates;
- `Ahrs.update_no_magnetometer(gyroscope, accelerometer)` takes two sensor vectors;
- the tested stationary update returns a normalized quaternion in `[w, x, y, z]` order;
- public sensor inputs use gyroscope deg/s and acceleration g.

### Adapter responsibilities

- explicit rad/s → deg/s conversion;
- explicit m/s² → g conversion;
- explicit quaternion component-order declaration at the KineIMU Shoulder boundary;
- no hidden resampling or timing inference.

------------------------------------------------------------------------

## imucal — Candidate Contract

### Intended role

Reproducible 6DoF calibration artifacts and calibration application.

### Tested API

Baseline: imucal 2.6.0 on CPython 3.12.14. A `FerrarisCalibrationInfo` configured with m/s² and rad/s input/output
units successfully applied an identity calibration and survived JSON serialization/deserialization.

This confirms API compatibility only. It does not validate a calibration protocol or estimated parameters.

## Contract gate before M2 integration

For each pinned backend declare input/output shapes, units, axes, quaternion order and rotation direction,
sample-period handling, missing/gap rejection, calibration/configuration and validation domain.
The M2.3 `kineimu_shoulder.orientation` adapter tested pinned imufusion 1.3.3
against positive/negative analytical rotations and stationary tilt. Its output
is active sensor/node-to-world `q_WN` for the declared six-axis configuration.
The adapter takes one node-frame epoch and observed device microsecond deltas,
rejects duplicate/reordered/over-limit timing, and resets backend state per
call. The first quaternion is a declared initial assumption, not an inferred
gravity heading. The backend does not supply anatomical alignment; a measured
sensor-to-segment map is composed once after AHRS. See
`protocols/M2_PROCESSING_CONTRACT.md` for equations and heading limits.
imucal outputs calibrated accel/gyro arrays and a versioned calibration artifact; it does not align segments.
Reject incompatible units/configurations; retain input hashes. Resampling is explicit upstream processed data,
never an adapter side effect. Test known rotations and invalid timing before accepting an adapter.

------------------------------------------------------------------------

## Bleak — host BLE central/recorder contract

### Intended role

Optional asynchronous GATT client for the frozen M1 service. The recorder receives
an explicit address-to-`NodeId.A`/`NodeId.B` assignment and never derives node roles
from advertising name, discovery order or host enumeration.

### Input/output boundary

- input: BLE address, explicit expected node ID, optional previously recorded
  nRF52840 hardware device ID and the M1 service characteristic UUIDs;
- output: unchanged notification bytes in one append-only `.kimu` stream per node,
  callback-entry host monotonic timestamps, decoded control/telemetry fields and
  transport events in a separate NDJSON sidecar;
- the adapter does not convert raw counts, axes, timestamps or sampling grids;
  those remain explicit downstream operations;
- identity/config is read and validated before telemetry notification is enabled;
  negotiated ATT MTU below 127 is a hard start failure;
- disconnect/reconnect creates a new connection ID and repeats identity/config,
  status and clock exchange before accepting telemetry again.

The implementation uses the pinned `ble` extra (Bleak 3.0.2). Physical BLE
interoperability and sustained throughput/loss results remain validation evidence,
not dependency compatibility evidence.
