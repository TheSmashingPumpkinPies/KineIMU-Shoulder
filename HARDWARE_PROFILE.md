# Hardware Profile — KineIMU Shoulder

## Current decision

[ADR-006](docs/adr/ADR-006-select-xiao-nrf52840-sense.md) selects **two Seeed Studio
XIAO nRF52840 Sense boards** (not the non-Sense or Plus variant) for M1. Each node
uses the onboard LSM6DS3TR-C 6-axis IMU and Nordic nRF52840 BLE-capable MCU.
The hardware choice is closed. The 1,800 s identified dual USB M1 acquisition
bench passed on 2026-09-25; the selected boards, onboard IMU, pinned Zephyr
platform and USB acquisition path are **frozen**. Reopen only for a documented
firmware/acquisition defect or a new maintainer decision. Dual BLE throughput
remains limited and is not covered by the USB pass. Wearable-product feasibility
is outside the current V1 mainline under ADR-008. See
`docs/validation/acquisition.md`.

Earlier StickS3/ESP-IDF compiler evidence remains in the private historical archive;
the published reference firmware targets the selected XIAO boards.

[ADR-007](docs/adr/ADR-007-select-upstream-zephyr.md) selects upstream Zephyr v4.4.0
with Zephyr SDK 1.0.1 and board target `xiao_ble/nrf52840/sense`. nRF Connect SDK is
not an active dependency.

## V1 development stages

1. Single-node USB-C power/debug: no battery, enclosure or soldering. Establish board
   and IMU identity, configured raw sampling, device timestamps, counters and PC capture.
   Exercise calibration and attitude-estimation paths only as integration smoke tests;
   M2 retains formal algorithm/frame validation.
2. Dual-node BLE: retain the physical dual-order transport evidence and its current
   first-connection starvation limitation. Do not claim the BLE path passed.
3. Under ADR-009, the uninterrupted 30-minute dual-node USB bench
   characterization passed with the same identified boards, packet bytes,
   device timestamps and loss detection. Hardware is frozen after M1 unless
   a documented firmware/acquisition defect appears.

## Pre-connection compile evidence

The 2026-09-09 [reproducible XIAO compile spike](firmware/xiao_nrf52840_sense/README.md)
pins Zephyr commit and all west revisions, the firmware Python environment, SDK distribution
and installed-tree hashes, exact build environment and UF2 hashes. Fresh pristine builds passed
for upstream `hello_world` and `sensor/lsm6dsl` on `xiao_ble/nrf52840/sense`.

The generated board definition resolves LSM6DS3TR-C through I2C address `0x6a`,
`st,lsm6dsl`, interrupt GPIO P0.11 and boot-on power-enable GPIO P1.8. These are compile-time
facts. On 2026-09-11 Node A was identified through its UF2 bootloader, flashed, enumerated over
USB CDC and returned continuous onboard LSM6DS3TR-C data through the in-tree driver after a
documented 50 ms deferred-init probe. Front/rear photographs show the model/regulatory and rear
board markings but no explicit PCB revision; `board_revision` is therefore recorded as `null`, not
inferred from those identifiers. These are the limits of the early Node A bring-up record. Later Node B
compatibility and the formal dual-node acquisition gate are documented in
[the M1 result](docs/validation/acquisition.md); unsupported internal FIFO
characteristics remain unmeasured rather than inferred from the USB pass.

## Physical board and driver evidence requirements

Manufacturer and upstream references checked 2026-09-07:
[Seeed product documentation](https://wiki.seeedstudio.com/XIAO_BLE/),
[Seeed Zephyr guide](https://wiki.seeedstudio.com/XIAO-nRF52840-Zephyr-RTOS/) and
[ST LSM6DS3TR-C driver](https://github.com/STMicroelectronics/lsm6ds3tr-c-pid).

During physical bring-up, record both board identifiers/revisions, actual MCU and
IMU identity, bootloader, verified physical routing, interrupt/data-ready behavior,
ODR, ranges, filters, FIFO behavior and timestamp source. The current Seeed Zephyr
definition is useful evidence, but the project must verify it on both physical boards.

Initial per-node target remains nominal 100 Hz accel + gyro, using the sensor's 104 Hz ODR.
ODR need not equal emitted sample rate. The v0.1 engineering target starts at ±4 g and
±500°/s; pilot shoulder motions must check clipping, noise, FIFO overflow and timing before
those values become validated configuration evidence.

## Future hardware integration

Battery selection, power switch/wiring, retention, enclosure, 3D printing, mounted mass,
comfort and runtime are future work. They are not M1 or V1 acceptance gates. If this work
is later authorized, it requires a new plan and measured requirements; no current battery
model or runtime is implied.

## Completed M1 hardware gate

The completion-window BLE retests and the 30-minute dual-node USB bench raw
evidence are preserved. Unsupported cumulative counters and pairwise timing/
synchronization metrics are recorded as not measured. Revisit the selected
boards only for a documented firmware/acquisition blocker or new maintainer
decision; battery, mounting and comfort do not block the hardware freeze.

## Current transport and freeze policy

The formal M1 long bench uses simultaneous dual USB packet capture with the same
frozen packet/device-time/sequence semantics. Preserve the failed/inconclusive
completion-window dual-BLE evidence; USB success does not validate BLE throughput.
The earlier V9 result follows the first-connected link and remains inconclusive
under its predeclared classification, without an established peripheral repair.
[The original 30-minute result](docs/validation/acquisition.md)
records acquisition gates and unmeasured timing fields. Hardware remains frozen;
battery/enclosure/wearability and human/clinical studies are outside V1.
