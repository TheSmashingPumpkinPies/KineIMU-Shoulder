# Node B physical identity — 2026-09-13

## Scope and result

This record captures the connected board's read-only Windows USB enumeration and
serial-reset transition. No UF2 was flashed and no raw sensor data was modified.

Result: **Electronic identity PASS; compatibility INCOMPLETE**. The application,
bootloader and UF2 metadata are now recorded. Physical board marking/revision and
sensor compatibility bring-up remain unverified.

## Observation context

- Date/time and timezone: 2026-09-13 16:45–16:51 +08:00
- Operator: maintainer-assisted, Codex-driven read-only enumeration
- Intended logical node: B (upper-arm role); final assignment remains pending the
  compatibility gate
- USB location: `Port_#0001.Hub_#0004`
- Repository HEAD before this evidence commit: `2e88f2ed0ab261fa4f554f27c3603a29436f8812`

## Application USB state

- PnP bus-reported description: `Seeed XIAO nRF52840 Sense`
- Composite device: `USB\\VID_2886&PID_8045\\0000000000000003`
- Application USB VID/PID: `2886:8045`
- Application USB serial/device identifier: `0000000000000003`
- Application hardware-ID USB revision: `REV_0101`
- CDC port: `COM6`
- CDC child hardware ID: `USB\\VID_2886&PID_8045&MI_00`
- Windows device status: `OK`, `CM_PROB_NONE`
- A five-second read of COM6 at 115200 baud produced zero bytes; no firmware
  identity or sensor diagnostic text was inferred from this absence.

## Bootloader USB state

A standard 1200-baud touch was opened and closed on COM6. The board then
re-enumerated as:

- PnP bus-reported description: `XIAO nRF52840 Sense`
- Composite device: `USB\\VID_2886&PID_0045\\0000000000000002`
- Bootloader USB VID/PID: `2886:0045`
- Bootloader USB serial/device identifier: `0000000000000002`
- Bootloader hardware-ID USB revision: `REV_0100`
- CDC port: `COM7`, child description `nRF Serial`
- CDC child hardware ID: `USB\\VID_2886&PID_0045&MI_00`
- Windows device status: `OK`, `CM_PROB_NONE`
- Additional 1200-baud touches left the same bootloader USB state active.
- UF2 mass-storage disk: `Adafruit nRF UF2`, USB disk serial
  `0000000000000002`, MBR, Windows disk number `1`

The mounted volume was `E:` with label `XIAO-SENSE`, FAT filesystem and capacity
33,423,360 bytes. The exact `INFO_UF2.TXT` content was:

```text
UF2 Bootloader 0.6.1 lib/nrfx (v2.0.0) lib/tinyusb (0.10.1-293-gaf8e5a90) lib/uf2 (remotes/origin/configupdate-9-gadbb8c7)
Model: Seeed XIAO nRF52840
Board-ID: Seeed_XIAO_nRF52840_Sense
SoftDevice: S140 version 7.3.0
Date: Nov 12 2021
```

The bootloader volume files were read without modification:

- `INFO_UF2.TXT`: 240 bytes, SHA-256
  `78d580460bbea1a33ac78ba3ff0858cf57eb01e858db490b44bec3127e4bd191`
- `INDEX.HTM`: 111 bytes, SHA-256
  `f27081d93ede33b1aa7a1a6c5f02c4f7952bb8e3f45c8649d1fbae8b677c5479`
- `CURRENT.UF2`: 1,908,736 bytes, SHA-256
  `56288702e5d2922ac2e4b788ce7f5115f9e5290132df495c1c0073de60ff6e89`

`CURRENT.UF2` is the bootloader's current-image file and was not interpreted as
a KineIMU build or flashed back to the board.

The application and bootloader serial/device identifiers are preserved as two
separate observations. They are not assumed to be interchangeable or to be the
nRF52840 FICR device ID required by the M1 identity/config characteristic.

## Non-inferences and open compatibility fields

- `REV_0101` and `REV_0100` are USB hardware-ID descriptor revisions, not PCB
  revision evidence.
- The USB product description identifies the Seeed XIAO nRF52840 Sense family;
  it does not by itself prove the physical IMU response or GPIO/I2C routing.
- Physical front/rear markings and PCB revision: not inspected/recorded; PCB
  revision remains `null` pending physical inspection.
- nRF52840 FICR hardware device ID: not yet read.
- LSM6DS3TR-C `WHO_AM_I=0x6a`, I2C address `0x6a`, INT1/data-ready route,
  104 Hz configuration, ±4 g/±500 °/s ranges, stationary sanity sample and
  separate raw-axis mapping: not yet verified on Node B.

## Next physical action

The electronic identity gate is complete. Before BLE, build or select a
Node-B-configurable bring-up image (the current Node A v1 image is hard-coded to
Node A), flash it only after matching this Board-ID/serial, and verify the
LSM6DS3TR-C identity, I2C/INT1 routing, configured acquisition and raw-axis
behavior. Preserve this current `CURRENT.UF2` hash as pre-flash provenance.
