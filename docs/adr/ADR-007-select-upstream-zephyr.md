# ADR-007: Select Upstream Zephyr for XIAO Firmware

- Status: Accepted
- Date: 2026-09-08
- Authorization: explicit current maintainer toolchain decision.
- Resolves the Zephyr versus nRF Connect SDK choice left open by ADR-006.

## Context

ADR-006 selects two XIAO nRF52840 Sense nodes. The board has an upstream Zephyr
target and an in-tree sensor integration for its onboard LSM6DS3TR-C. M1 needs a
small, reproducible firmware stack for USB-C bring-up, BLE transport, timestamps,
counters and acquisition characterization; it does not currently need Nordic-only
cloud, DFU or proprietary-controller features.

## Decision

Use **upstream Zephyr v4.4.0** with **Zephyr SDK 1.0.1** as the M1 firmware
baseline. Use the official board target `xiao_ble/nrf52840/sense` and the Zephyr
in-tree `st,lsm6dsl`-compatible sensor path first.
The nRF Connect SDK is not an active dependency.

Use the signed upstream `v4.4.0` release tag, its `west.yml` module revisions and
the Windows x86-64 GNU Zephyr SDK distribution. Record source revisions, SDK
checksum, Python environment and exact build commands in the firmware README after
the reproducible setup/build spike. Do not track the downloaded SDK or Zephyr
workspace in this repository.

Initial evidence proceeds in this order:

1. pristine compile for `xiao_ble/nrf52840/sense`;
2. UF2 flash and boot/USB observation on one physical node;
3. board/IMU identity and LSM6DS3TR-C sample read;
4. project single-node raw acquisition;
5. two-node BLE transport and synchronization characterization.

## Consequences

Zephyr's standard kernel, device, USB and Bluetooth APIs are the firmware platform
contract. Avoid Nordic-only APIs unless a measured requirement is documented and a
new ADR revisits this decision.

The upstream board entry is not actively maintained, so successful documentation
examples do not replace verification on both project boards. The selected version
and toolchain are not evidence of sample timing, BLE throughput, loss, power or
measurement validity.

Revisit the Zephyr release deliberately through a new compatibility record; do not
silently follow `main` or automatically adopt Zephyr 4.5 when it is released.
