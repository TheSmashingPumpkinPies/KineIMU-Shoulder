# ADR-006: Reference hardware

Status: Accepted. Selected 2026-09-07; current V1 boundary follows ADR-008.

Use two **Seeed Studio XIAO nRF52840 Sense** boards with nRF52840 and
LSM6DS3TR-C, rather than non-Sense or Plus variants. USB-C supports power,
debugging and the validated dual-USB acquisition path. The two-node BLE path
remains implemented with its measured throughput limitation explicitly reported.

The board choice does not establish measurement accuracy, timing, loss,
synchronization, power or comfort. Reference-board build and physical acquisition
evidence remain required. Battery, soldering, enclosure, wearability and human
studies are outside current V1. Hardware is frozen after M1 unless a documented
firmware/acquisition defect requires reopening it.

See [hardware profile](../../HARDWARE_PROFILE.md), [firmware](../../firmware/xiao_nrf52840_sense/README.md)
and [M1 result](../validation/acquisition.md).
