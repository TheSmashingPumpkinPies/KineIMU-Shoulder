# Data Format — KineIMU Shoulder

## Canonical Units

- acceleration: m/s²
- angular velocity: rad/s
- time: integer microseconds or nanoseconds
- orientation: normalized quaternion
- angles shown to users: degrees unless explicitly stated

## Canonical Anatomical Reference Frame

``` text
+X = anterior
+Y = left
+Z = superior
```

This is the thorax anatomical reference, not an assertion that raw sensor axes are anatomical.
Humerus long-axis, side and sensor-to-segment conventions require M2 definition.

Any backend using another convention must convert explicitly inside its adapter.

## Normalized IMU Table

Required columns:

``` text
timestamp_us
acc_x_mps2
acc_y_mps2
acc_z_mps2
gyro_x_rads
gyro_y_rads
gyro_z_rads
```

Optional raw columns:

``` text
acc_x_raw
acc_y_raw
acc_z_raw
gyro_x_raw
gyro_y_raw
gyro_z_raw
```

## Per-node Metadata (existing schema 0.1 example)

Minimum:

``` json
{
  "schema_version": "0.1",
  "device": "Seeed Studio XIAO nRF52840 Sense",
  "imu": "LSM6DS3TR-C",
  "firmware_version": "0.1.0",
  "sampling_rate_hz_nominal": 100,
  "accel_range_g": null,
  "gyro_range_dps": null,
  "accel_odr_hz": null,
  "gyro_odr_hz": null,
  "filter_config": null,
  "placement": "thorax",
  "protocol": "unknown",
  "calibration_id": null,
  "firmware_git_commit": null,
  "device_id": null,
  "acquisition_start_utc": null,
  "transport": "usb"
}
```

## Raw / Processed Policy

``` text
raw/         immutable acquisition output
processed/   calibrated/resampled data
derived/     metrics
annotations/ ground truth
```

Never overwrite raw data.

## Timestamp Rules

- per-sample timestamp must be monotonic
- do not infer time only from sample index
- wall-clock time may be stored at session level
- gaps must be detectable

## Schema Versioning

Any breaking column/unit/semantic change requires schema version increment and migration note.

## Quality Flags

Processed sessions should carry explicit QC information for:

- timestamp gaps
- duplicate timestamps
- missing samples
- clipping/saturation
- NaN/Inf
- effective sample rate
- calibration mismatch
- recording interruption

Downstream analysis must not silently treat failed QC as valid.

## Scientific Export

The internal table is not intended to replace community standards.

Provide a Motion-BIDS-compatible export path for research sharing where practical.

## Resampling Policy

Raw timestamps are authoritative.

If an algorithm requires equally spaced samples:

- create a processed/resampled representation;
- record target rate and interpolation method;
- preserve source session ID;
- record gap thresholds;
- do not interpolate across long gaps without explicit justification.

Nominal sampling rate is metadata, not a replacement for per-sample timing QC.

## Dual-IMU M1 session contract

The seven canonical normalized table columns, units and schema 0.1 semantics are retained.
The thorax placement above replaces an illustrative old placement value, not a column/schema change.
Use separate immutable streams for Node A thorax and Node B upper arm; do not concatenate them
without explicit association. Preserve raw sensor-frame channels and device-local timestamps.
M1 container/version, field types/nullability, packet framing and examples are frozen in
`protocols/M1_ACQUISITION_CONTRACT.md` and its versioned JSON schema/example.

The session envelope associates session ID, device IDs, A/B role, test side, board/IMU revision,
stream paths/hashes, clock IDs/epochs, sensor/sample and packet counters, host receive times,
firmware/driver/configuration, per-node calibration/alignment and mounting protocol. Counter/reception
fields remain transport sidecars; they are not silently added to the canonical table.
Record dropped packets versus dropped samples separately, reset/wrap/overflow and disconnect boundaries.
Clock mappings, uncertainty, resampling grids/methods and QC belong to processed artifacts with raw hashes.
Nominally simultaneous rows need not represent simultaneous samples. See SYNC_PROTOCOL.

Derived per-repetition/session outputs require metric definition/version, units, evidence labels
(Observed, Derived, Assumed, Validated, Experimental), validity/exclusion reason, exercise/side,
phase boundaries and processing provenance. Output schema is deferred until the relevant milestone.

## Public data boundary

Distribute only synthetic, non-identifying or explicitly approved de-identified
records. Do not commit identifiable human video, personal information, credentials,
machine home paths or unique physical-device identifiers. Use consistent anonymous
IDs without encoding names/contact details. Preserve untouched originals privately,
with original/public correspondence and SHA-256 records. Raw data and failed records
are immutable; redaction applies to reviewed public copies and provenance metadata.
The [sample annex](datasets/samples/m6_synthetic/LICENSE.md) and
[additional-data grant](docs/PUBLIC_DATA_LICENSE.md) define separate bounded rights.
Code and third-party material retain their own licenses. Human/clinical validation
is outside V1; engineering self-tests do not establish population-level validity.
