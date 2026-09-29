> Historical firmware/build evidence. Unfinished checks below describe that
> source and date, not current V1 status. The later dual-USB acquisition gate
> passed; dual-BLE throughput remains limited and hardware is frozen. See
> [hardware status](../../../HARDWARE_PROFILE.md) and
> [formal M1 result](../../../docs/validation/acquisition.md).

# Node B physical compatibility — 2026-09-13

## Scope and result

This record is the Node B board-level compatibility check for the shared XIAO
nRF52840 Sense bring-up application. It covers the flashed Node-B-configured
image, nRF52840 identity, onboard LSM6DS3TR-C response, configured register
snapshot and short raw packet delivery. It does not claim BLE, long-duration
timing/loss, FIFO-pressure behavior, calibration or clinical validity.

Result: **raw-axis behavior PASS; board-level compatibility remains incomplete**.

The electronic/IMU/packet-delivery subset passed. The supplied front/rear
photographs record the visible board marking; no explicit PCB revision is
visible. The separately prompted raw-axis behavior check is now recorded
below. BLE and the remaining M1 gates are not claimed by this record.

## Build and flash provenance

- Date/time and timezone: 2026-09-13, Asia/Shanghai
- Intended logical node: B (upper-arm role); no anatomical axis labels are inferred
- Board target: `xiao_ble/nrf52840/sense`
- Build directory: `.cache/node_b_bringup_build_20260913`
- Build selection: `-DKINEIMU_NODE_ID=2`
- CMake cache confirmation: `KINEIMU_NODE_ID:STRING=2`
- FLASH: 66,100 B / 788 KiB (8.19%)
- RAM: 14,648 B / 256 KiB (5.59%)
- UF2 size: 132,608 bytes
- UF2 SHA-256: `c782627573c07e099c092fc5b526181c22c8f7f35a8ca6c3c66dedd12360c9e7`

Immediately before flashing, the mounted volume was `E:` / `XIAO-SENSE`,
`INFO_UF2.TXT` reported Board-ID `Seeed_XIAO_nRF52840_Sense`, and the
bootloader USB serial was `0000000000000002`. The pre-flash
`CURRENT.UF2` SHA-256 was
`56288702e5d2922ac2e4b788ce7f5115f9e5290132df495c1c0073de60ff6e89`.
The UF2 was copied only after all three target checks matched; the previous
`CURRENT.UF2` was not modified in place.

After flashing, the board re-enumerated as application USB `VID:PID
2FE3:0004`, composite serial `0000000000000002`, and CDC `COM8`; Windows
reported the device status as `OK`.

## DTR-gated diagnostic and IMU register audit

The diagnostic preamble was preserved in
`node_b_20260913_compat.usb.bin` before the first binary packet:

```text
Node B: nRF52840 FICR DEVICEID[0]=0x00000002 DEVICEID[1]=0x00000000 hardware_device_id=0x0000000059e4a5f0
KineIMU Shoulder Node B: IMU init rc=0 ready=1
Node B: IMU registers WHO_AM_I=0x6a INT1_CTRL=0x03 CTRL1_XL=0x48 CTRL2_G=0x44 match=1
Node B: data-ready acquisition armed at 104 Hz, +/-4 g, +/-500 dps
Node B: v1 USB packet stream node_id=2 batch_max=4
```

| Check | Observation | Result |
|---|---|---|
| nRF52840 FICR | `DEVICEID[0]=0x00000002`, `DEVICEID[1]=0x00000000`, assembled as `0x0000000059e4a5f0` | PASS |
| IMU initialization | `rc=0`, `ready=1` | PASS |
| LSM6DS3TR-C identity/I2C read | `WHO_AM_I=0x6a`; register reads completed through the configured `0x6a` device | PASS |
| INT1 data-ready route | `INT1_CTRL=0x03` | PASS |
| Accelerometer configuration | `CTRL1_XL=0x48`, diagnostic target 104 Hz / ±4 g | PASS |
| Gyroscope configuration | `CTRL2_G=0x44`, diagnostic target 104 Hz / ±500 °/s | PASS |
| Register snapshot | `match=1` | PASS |
| Packet identity | diagnostic `node_id=2`; decoded packet node ID was B | PASS |

The FICR value equals the bootloader-side identifier observed during the
pre-flash inventory, but the two observations remain recorded by their source
interfaces rather than being silently substituted for one another.

## Physical photo inventory

The maintainer supplied two original, double-sided Node B photographs. They are
referenced by filename and SHA-256 only; the image files, which include the
operator's fingers, were not copied into the repository.

- Front photo `1-照片-1.jpg`, 1,341,311 bytes, SHA-256
  `9ba0acfb062ca98c635c45fafa678f963a9b1f927876b19e76cca640518abfb0`
- Rear photo `2-照片-2.jpg`, 1,311,333 bytes, SHA-256
  `a8e56517bb2c34563e4f62fd4fa9f8e79a284ab1a962d05f87b5bcf78933730d`

Visible front marking: `Seeed Studio`, `Model: XIAO-nRF52840`, `FCC ID:
Z4T-XIAONRF52840` and the regulatory marking `R 211-220207`. The rear image
shows the XIAO/nRF52840 board silkscreen and pin labels. No literal `Rev`,
`Revision` or `Vx.x` PCB revision marking is visible in either photograph;
`board_revision` therefore remains `null` by observation, not inference.

## Complete raw packet capture

The first 10-second capture established the preamble and valid packet path. Its
wall-time stop left one explicit packet tail; the parser did not repair it:

- `node_b_20260913_compat.usb.bin`: 32,742 bytes,
  SHA-256 `c38c6820a32eb8a3aee2dba060ff948041a671f2113c01e34059ac82bd0a06b3`
- `node_b_20260913_compat.kimu`: 35,496 bytes,
  SHA-256 `d75411259bf50dbb6c06bc454a6e13e5f235a4d9b2e879f5d6f3846f7f7609b1`
- `node_b_20260913_compat.events.ndjson`: 64,856 bytes,
  SHA-256 `4603b4a3b02e3f0bc6f32d187f3141780342e7e2e2be75d11ae78485510d918a`
- 261 valid packets / 1,044 decoded samples
- all valid packets had node ID B, clock epoch 0 and four samples
- sequence QC: zero decode, framing, missing, duplicate, reorder, timestamp or
  node-mismatch errors
- parser sidecar: 362 diagnostic/noise bytes and one expected 16-byte
  `truncated_packet` at the wall-time stop; `qc_pass=true`,
  `stream_complete=false`

A second capture used a packet-count stop and completed without a parser tail:

- `node_b_20260913_stationary.usb.bin`: 25,792 bytes,
  SHA-256 `d374f6350bcefe0829c66b61232cb07025ec3c8b57ecef75ec4941cce9b0926a`
- `node_b_20260913_stationary.kimu`: 28,288 bytes,
  SHA-256 `1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201`
- `node_b_20260913_stationary.events.ndjson`: 53,730 bytes,
  SHA-256 `ba3589ee342ce5b8fb02c8b64911592fca4ad739eee78d63f9ad89fbd599cf0b`
- 208 valid packets / 832 decoded samples
- packet sequence `5867`–`6074`; sample sequence `23468`–`24299`; clock epoch 0
- all packet/sample flags were zero
- sequence QC: zero decode, framing, missing, duplicate, reorder, timestamp or
  node-mismatch errors; `qc_pass=true`, `stream_complete=true`

The exact recorder commands were:

```text
python scripts/capture_m1_usb.py --port COM8 --seconds 10 --node-id 2 --output-prefix firmware/xiao_nrf52840_sense/evidence/node_b_20260913_compat
python scripts/capture_m1_usb.py --port COM8 --seconds 8 --packets 208 --read-size 64 --node-id 2 --output-prefix firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary
```

The `.usb.bin` files are the immutable received byte streams. The `.kimu`
files contain only validated packet payloads in the existing outer framing;
the events files retain parser/QC provenance.

## Stationary raw-count sanity check

The second capture was analyzed as raw signed counts; no unit or axis
conversion was applied. Across all 832 samples:

- mean accelerometer counts: `(-628.845, 5047.352, 6657.972)`
- accelerometer norm: min `8288.640`, median `8379.889`, max `8478.219`
- mean gyroscope counts: `(78.971, -116.870, 120.036)`
- gyroscope norm: min `172.267`, median `185.401`, max `200.027`
- device timestamp span: `257030578` to `264845581` µs
- adjacent timestamp delta: min `9399`, median `9400`, max `9430` µs

The stable nonzero accelerometer vector and low, bounded gyroscope vector are
plausible stationary readout behavior for the configured ±4 g / ±500 °/s
raw-count path. This is wiring/readout sanity evidence only, not calibration,
accuracy, rate, jitter or loss validation. The short timestamp observation is
retained for later timing analysis; it does not close the M1 sustained-rate
gate.

## Node B raw-axis mapping — 2026-09-13

The same physical reference pose was used for all three actions: component
side up, USB connector toward the operator, and the right edge defined from
that view. “Viewed from above” means looking down at the component side; the
last action was a horizontal-plane rotation, not an edge-lift action.

The mapping is based on signed `gyro_raw` counts from validated Node B packet
samples. The sample ranges below are zero-based indices in the concatenated
decoded samples of each capture. No raw bytes were edited, and no filtering,
resampling, interpolation, unit conversion or coordinate transformation was
applied.

| Physical action | Raise/forward direction | Return direction | Selected decoded window evidence |
|---|---|---|---|
| USB connector edge raised, then returned | `gyro_raw Y > 0`; mean `(43, 704, 57)` | `gyro_raw Y < 0`; mean `(61, -812, 56)` | `node_b_20260913_axis_usb_controlled_retry`, samples `728–935` / `1144–1403` |
| Right edge raised, then returned | `gyro_raw X < 0`; mean `(-803, -114, 82)` | `gyro_raw X > 0`; mean `(1656, -73, 40)` | `node_b_20260913_axis_right_controlled`, samples `884–1247` / `1560–1715` |
| Clockwise in the horizontal plane, viewed from above, then counterclockwise return | `gyro_raw Z < 0`; mean `(29, -142, -679)` | `gyro_raw Z > 0`; mean `(26, -129, 1202)` | `node_b_20260913_axis_yaw_controlled`, samples `1144–1715` / `1976–2123` |

The signed-direction result is therefore:

```text
USB edge upward                       -> gyro +Y
right edge upward                     -> gyro -X
clockwise viewed from above (flat)   -> gyro -Z
```

The detailed raw excerpts are in
`node_b_20260913_axis_mapping.txt` (complete record retained in the local evidence archive).
The selected immutable capture triplets are:

| Capture | Valid packets / samples | Parser/QC observation | `.usb.bin` SHA-256 | `.kimu` SHA-256 | `.events.ndjson` SHA-256 |
|---|---:|---|---|---|---|
| `axis_right_controlled` (complete record retained in the local evidence archive) | 540 / 2,160 | 95 noise bytes, one CRC issue and one timed-stop tail; valid-record QC has 2,538 missing packets / 10,152 samples | `59cd08d4161c7a1f1e55c1d45de6e400ae0759ee3693a34dfa5b6cd0ac683704` | `dd2f0cf0c44052c76541957711e8d8d0c809e62eee568d7451c9e7e257e00c3f` | `bcc8188dac91e7be017ab6dae1558947fb3f71f179539e5053495f8323e4d32f` |
| `axis_usb_controlled_retry` (complete record retained in the local evidence archive) | 540 / 2,160 | 95 noise bytes, one CRC issue and one timed-stop tail; valid-record QC has 1,327 missing packets / 5,308 samples | `2474fc9b4f6ebae2a2b08077e3f9cbf354c9fbe1615359db6d52ec0bf5d943c3` | `bd8a1b1d7c15f24b02fec61c3016b54295bf271aba94064d84a9984e1e0e4c1f` | `e1bc6bd37e6a4e461736e6b0af4c7e410a3322596cc9d527ced7892ee73f674b` |
| `axis_yaw_controlled` (complete record retained in the local evidence archive) | 531 / 2,124 | zero valid-record sequence/QC errors; one expected timed-stop tail | `c899edf53cdd49111fdbad6111fc669fd0a60f689afaf2c9abe5c8afcf7e49ed` | `d82e455ea7ccf35f42b6237ff696073d52defbd2555111fad062ae005187fb9b` | `00456d01027166de84f9427923f11cc065357a83e44448385170d525b1df0020` |

The right and USB retry mappings use only the valid decoded records in the
selected motion windows; the retained CRC, tail and sequence-gap diagnostics
are not hidden or repaired. The result is a physical raw-board/sensor
behavior observation. It is not a claim about anatomical axes, sensor-to-
segment calibration, shoulder angles, timing/loss performance or clinical
validity.

## Exploratory capture provenance

Earlier and unsynchronized attempts were retained unchanged as an audit trail,
but were not used to select the final channel/sign result because their action
onset was not isolated or their stream continuity was not suitable for that
purpose. Their parser and QC sidecars remain available; no sample was deleted
or repaired.

| Capture prefix | Valid packets / samples | Reason not selected as the primary mapping excerpt |
|---|---:|---|
| `node_b_20260913_axis_mapping` | 930 / 3,720 | Combined multi-action capture; action boundaries were not separately controlled |
| `node_b_20260913_axis_right` | 407 / 1,628 | Fixed window ended before the prompted action; parser CRC/tail and sequence gaps |
| `node_b_20260913_axis_right_manual` | 1,072 / 4,288 | Manual timing; parser CRC/tail and sequence gaps |
| `node_b_20260913_axis_usb_controlled` | 531 / 2,124 | Controlled window showed no clear deliberate USB-edge pulse |
| `node_b_20260913_axis_usb_manual` | 1,063 / 4,252 | Manual timing; no isolated action boundary |
| `node_b_20260913_axis_yaw_manual` | 1,072 / 4,288 | Manual timing; parser CRC/tail and sequence gaps |

The selected controlled triplets and their hashes are listed above. Keeping
these exploratory files does not turn them into timing/loss evidence; it only
preserves the received streams and the reasons for excluding them from the
primary mapping selection.

## Open physical checks

- Board front/rear marking: recorded from the supplied photographs as `Seeed
  Studio`, `Model: XIAO-nRF52840`, `FCC ID: Z4T-XIAONRF52840` and `R 211-220207`;
  no explicit PCB revision is visible, so `board_revision=null`. USB
  `REV_0100`/`REV_0101` descriptors are not used as revision evidence.
- Separate raw-axis mapping: recorded above from three prompted Node B
  captures. The observations remain sensor-axis observations, not anatomical
  labels. The capture sidecars retain the USB stream issues and no raw data
  was repaired.
- FIFO pressure/overrun, sustained timing/loss, dual-node BLE,
  synchronization, power and the 30-minute M1 measurement remain open.

No raw capture data was modified.
