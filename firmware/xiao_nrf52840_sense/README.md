# XIAO nRF52840 Sense Zephyr compile spike

This directory records the reproducible platform and Node A hardware-gate evidence for
the active KineIMU Shoulder M1 firmware target. The Zephyr workspace, SDK, build
directories and generated binaries stay outside this repository. The checked-in
`node_a_bringup` application remains a USB-C physical-compatibility/staging probe;
the separate [`m1_ble`](m1_ble/README.md) application is the first buildable BLE
acquisition slice, not a completed M1 validation artifact.

## Frozen platform

- Board: Seeed Studio XIAO nRF52840 Sense, target `xiao_ble/nrf52840/sense`.
- MCU: Nordic nRF52840.
- IMU: onboard ST LSM6DS3TR-C through Zephyr's in-tree `st,lsm6dsl` path.
- Zephyr: signed release tag `v4.4.0`, commit
  `684c9e8f32e4373a21098559f748f06915f950c9`.
- Zephyr SDK: 1.0.1 Windows x86-64 GNU distribution.
- Python: 3.12.14; west 1.5.0; CMake 3.31.10; Ninja 1.13.0.
- Cross compiler: `arm-zephyr-eabi-gcc` 14.3.0; GNU ld 2.43.1.
- Python packages: [requirements-zephyr-v4.4.0.freeze.txt](requirements-zephyr-v4.4.0.freeze.txt).
- West revisions: [west-zephyr-v4.4.0.freeze.txt](west-zephyr-v4.4.0.freeze.txt).

The official SDK release is
[zephyrproject-rtos/sdk-ng v1.0.1](https://github.com/zephyrproject-rtos/sdk-ng/releases/tag/v1.0.1).
The selected distribution and official GitHub release SHA-256 are:

```text
zephyr-sdk-1.0.1_windows-x86_64_gnu.7z
811cb97797ddf6198eea66b030168d12512f605c7e332ea24d2cbe47b769c472
```

The downloaded archive was not retained. To identify the installed tree independently,
the following local files were hashed on 2026-09-09:

```text
sdk_version
44e161e4495cac2cf7858043e9e6418e9579f0ddcfae826f9a372622968ce066

sdk_gnu_toolchains
88c140b86b86e3b278a0820d51a569b17a39f18bd757cfcac8c78beac2424d99

gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-gcc.exe
859a8542f68802ef311a41bf8b6b2942da58e09fa8f40762a0501036332da7a5
```

The official archive digest identifies the intended distribution; the three installed-file
hashes identify the tree actually used. They do not claim a byte-for-byte verification of
an archive that is no longer present.

## Reproduction on Windows PowerShell

Keep the toolchain outside the repository. The paths below record the verified local
layout; another machine may use different absolute paths.

```powershell
$workspaceRoot = '<firmware-workspace>\Toolchains\KineIMU-Zephyr-4.4.0'
$sdkRoot = '<firmware-workspace>\Toolchains\Zephyr-SDK-1.0.1'
$buildRoot = Join-Path $workspaceRoot 'builds\pre_node_a'
$venvScripts = Join-Path $workspaceRoot '.venv\Scripts'
$env:PATH = "$venvScripts;$env:PATH"
$env:ZEPHYR_SDK_INSTALL_DIR = $sdkRoot

Push-Location $workspaceRoot
try {
    & '.\.venv\Scripts\python.exe' -m west build -p always `
        -b 'xiao_ble/nrf52840/sense' `
        'zephyr\samples\hello_world' `
        -d (Join-Path $buildRoot 'xiao_hello')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & '.\.venv\Scripts\python.exe' -m west build -p always `
        -b 'xiao_ble/nrf52840/sense' `
        'zephyr\samples\sensor\lsm6dsl' `
        -d (Join-Path $buildRoot 'xiao_lsm6dsl')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
```

The virtual-environment `Scripts` directory must be placed on `PATH`. A controlled
reproduction without that line selected system CMake 4.4.3, could not find Ninja and
failed before compilation. With the recorded PATH, the build selected the pinned CMake
3.31.10 and Ninja 1.13.0. Both successful configurations printed a non-fatal early
`Could NOT find Dtc` diagnostic and then generated the board devicetree normally.

## Verified compile evidence

Fresh, separate builds were run on 2026-09-09 under
`builds/pre_node_a_20260909_v2/`. Both commands exited zero.

| Upstream sample | UF2 bytes | UF2 SHA-256 | FLASH used | RAM used |
|---|---:|---|---:|---:|
| `samples/hello_world` | 93,184 | `b6d0e13cba3cb4548e21a67118af7e59691dbfd945c75e58acd1dd104ee09ef6` | 46,552 B / 788 KiB (5.77%) | 13,560 B / 256 KiB (5.17%) |
| `samples/sensor/lsm6dsl` | 133,120 | `3f58f7c1eb160ef9393d24125b9b2c30c32b5ac4a64a17f84a5caeff5ce2ba4c` | 66,384 B / 788 KiB (8.23%) | 14,200 B / 256 KiB (5.42%) |

For the sensor sample, the generated configuration contains `CONFIG_I2C=y`,
`CONFIG_SENSOR=y` and `CONFIG_LSM6DSL=y`. The generated devicetree resolves the onboard
device as I2C address `0x6a`, compatible `st,lsm6dsl`, interrupt GPIO P0.11 and
boot-on sensor power enable GPIO P1.8. This is compile-time board-definition evidence,
not proof that either physical IMU responds or that interrupts work.

## Node inventory prepared before connection

| Logical node | Intended M1 role | Physical identifier | Board revision | Bootloader | Status |
|---|---|---|---|---|---|
| A | thorax | bootloader USB serial `0000000000000001` | `null`; no explicit revision visible in reviewed front/rear photos | UF2 0.6.1 / S140 7.3.0 | inventory, UF2, CDC, onboard IMU readout and raw-axis mapping verified |
| B | upper arm | pre-flash app `0000000000000003`; bootloader `0000000000000002`; Node-B image app `0000000000000002` — keep source interfaces separate | `null`; no explicit PCB revision visible in supplied front/rear photos; USB descriptor revisions `REV_0101`/`REV_0100` are not PCB revision evidence | UF2 0.6.1 / S140 7.3.0; Board-ID `Seeed_XIAO_nRF52840_Sense` | electronic identity, IMU/raw-packet delivery, visible marking and raw-axis behavior verified; see [Node B compatibility evidence](evidence/node_b_20260913_compatibility.md) |

Use removable labels `A` and `B`; do not infer identity from COM-port order. Keep the
same logical identity in firmware metadata, raw stream filenames and session manifests.
The physical identifiers cannot be truthfully populated before the boards are connected.

## Node B identity result — 2026-09-13 (electronic identity verified)

The connected board was observed in application USB state as `Seeed XIAO nRF52840
Sense`, application `VID:PID 2886:8045`, serial/device identifier
`0000000000000003` and `COM6`. A 1200-baud reset transition exposed the
`VID:PID 2886:0045` bootloader USB state with serial/device identifier
`0000000000000002` and `COM7`. The `XIAO-SENSE` volume exposed
`INFO_UF2.TXT` with UF2 Bootloader `0.6.1`, Board-ID
`Seeed_XIAO_nRF52840_Sense` and SoftDevice `S140 7.3.0`. At that initial
identity snapshot, physical markings, PCB revision and sensor compatibility
remained open. The complete observation and
non-inference boundary are recorded in
evidence/node_b_20260913_identity.md (complete record retained in the local evidence archive).

## Node B physical compatibility result — 2026-09-13 (raw-axis behavior recorded)

The Node-B-configured bring-up UF2 was flashed only after matching the recorded
`Seeed_XIAO_nRF52840_Sense` Board-ID, bootloader serial `0000000000000002` and
the `XIAO-SENSE` volume. The board re-enumerated on COM8 and printed the FICR
ID, `IMU init rc=0 ready=1`, `WHO_AM_I=0x6a`, `INT1_CTRL=0x03`, `CTRL1_XL=0x48`,
`CTRL2_G=0x44`, `match=1` and packet `node_id=2`.

The complete raw byte streams, validated `.kimu` records and sequence/QC
sidecars are in [Node B compatibility evidence](evidence/node_b_20260913_compatibility.md).
The electronic/IMU/raw-packet subset passed, including a complete 208-packet /
832-sample short capture and a raw-count stationary sanity check. The supplied
photos record the visible board marking; no explicit PCB revision is visible,
so `board_revision` remains `null`. The separately prompted Node B raw-axis
behavior check is recorded as USB edge `+Y`, right edge `-X` and flat clockwise
rotation `-Z`, using raw signed gyro counts only. BLE physical interoperability,
sustained timing/loss, FIFO-pressure, synchronization, power and measurement gates
remain separate open work.

## Exact Node A bring-up record

Complete the following in order and preserve the console transcript or failure output:

1. Photograph or transcribe the board marking without identifiable human data; assign label A.
2. Record USB VID/PID, serial/device identifier, board revision and bootloader volume/version.
3. Use a known data-capable USB-C cable; no battery, enclosure or soldering.
4. Flash the verified hello UF2 and record boot plus USB CDC output.
5. Flash the verified LSM6DSL UF2 and record device-ready output and continuous samples.
6. Verify stationary acceleration magnitude is plausibly near local gravity and stationary gyro
   is near zero only as a wiring/readout sanity check, not as calibration or accuracy evidence.
7. Rotate each board axis separately and record the observed sign/channel mapping. Do not call
   raw sensor axes anatomical axes.
8. Record any reset, disconnect, driver error or missing sample output verbatim.

Evidence fields:

```text
date/time and timezone:
operator:
logical node: A
board marking/revision:
USB VID/PID:
USB serial/device ID:
bootloader/version:
hello UF2 SHA-256:
LSM6DSL UF2 SHA-256:
console transcript path/hash:
IMU device-ready result:
observed stationary accel/gyro:
axis-motion notes:
errors/resets/disconnects:
result: PASS / FAIL / INCOMPLETE
```

Do not advance this file from compile evidence to physical compatibility evidence until
the record above is populated. ODR, ranges, FIFO, timestamp quality and interrupt behavior
remain M1 measurement gates.

## Node A physical result — 2026-09-11

The maintainer physically labelled the first board as Node A. A rapid double reset exposed
the `XIAO-SENSE` UF2 volume with bootloader VID/PID `2886:0045`, unique USB serial
`0000000000000001`, UF2 0.6.1 and board ID `Seeed_XIAO_nRF52840_Sense`. The upstream hello
and LSM6DSL samples were flashed, and the application CDC interface enumerated as COM5 with
VID/PID `2FE3:0004`.

The pristine LSM6DSL sample failed its early sensor initialization even though the I2C shell
later found address `0x6a` and read WHO_AM_I `0x6a`. The project bring-up application works
around the board-definition power-up ordering by deferring only the IMU, waiting 50 ms and
then invoking the standard Zephyr driver initialization. On hardware it reported
`IMU init rc=0 ready=1` and emitted continuous acceleration in m/s^2 and angular rate in
rad/s. A stationary captured sample had acceleration norm `9.925721 m/s^2` and angular-rate
norm `0.066799 rad/s`; this is wiring/readout sanity evidence only, not calibration or
accuracy validation.

The buildable probe is in [node_a_bringup](node_a_bringup/README.md). The complete record and
console capture are in evidence/node_a_20260911.md (complete record retained in the local evidence archive) and
`evidence/node_a_20260911_serial.txt`. Separate-axis motion mapping also passed: with the
component side up and USB toward the operator, USB-edge-up maps to gyro `+Y`, right-edge-up
maps to gyro `-X`, and clockwise viewed from above maps to gyro `-Z`.

Maintainer-supplied front/rear photographs were reviewed on 2026-09-11. The front label reads
`Seeed Studio`, `Model: XIAO-nRF52840`, `FCC ID: Z4T-XIAONRF52840` and `R 211-220207`;
the rear silkscreen reads `seeed studio`, `XIAO`, `nRF52840` and `NFC`. No explicit `Rev`,
`revision` or `Vx.x` marking is visible, so `board_revision` remains `null` by observation rather
than inference. The photo hashes are recorded in the evidence file; the images were not copied into Git.
The Node A physical inventory/core bring-up checklist, configured data-ready delivery and GPIO ISR
timestamp delivery are `PASS`. The timestamp TDD, reference-board build, flashed artifact identity and
physical CDC observations are recorded in
evidence/node_a_20260912_isr_timestamp.md (complete record retained in the local evidence archive). The physical
capture contained 1,230 strictly increasing timestamps and no `missing ISR timestamp` message. This
does not characterize timing, jitter, latency or loss. Independent sample/packet counter software and
its reference-board build are recorded in
evidence/node_a_20260912_counters.md (complete record retained in the local evidence archive); the counter artifact has
not been flashed. The fixed-capacity FIFO, explicit drop-newest policy and saturating queue-loss
accounting are recorded in
evidence/node_a_20260912_sample_queue.md (complete record retained in the local evidence archive); its reference
artifact has not been flashed, so physical queue-pressure/loss behavior remains open.
The Node A v1 packet USB-C staging slice is now implemented and physically exercised with the final
source-tree artifact. The flashed
reference artifact, complete CDC byte stream, frozen `.kimu` records, parser/QC sidecar and explicit
end-of-window truncation are recorded in
evidence/node_a_20260913_usb_packet_v1.md (complete record retained in the local evidence archive). This is
single-node transport evidence before BLE, not M1 completion. The first capture used UF2
`0cb593223cea93f22b6dc6b6fc1aa4431656177bab28f10defce55db0e4a7a98d`; the final clean build
`3dd80115deaabeb7e61111e29d930c06e9591df93664fe497fe0bc4e61e87b50` was flashed and recaptured.
