# ADR-006: Select XIAO nRF52840 Sense for M1

- Status: Accepted
- Date: 2026-09-07
- Authorization: explicit current maintainer hardware decision.
- Supersedes the provisional StickS3 hardware choice in ADR-005; the ESP-IDF
  skeleton remains historical engineering evidence only.

## Context

M1 requires two identified 6DoF nodes, reliable sample timing, dual wireless
transport, synchronization characterization and a practical shoulder mounting path.
The hardware choice was intentionally left open during the shoulder scope pivot.

## Decision

Use two **Seeed Studio XIAO nRF52840 Sense** boards (not the non-Sense or Plus
variant) as the M1 nodes. Each node uses the onboard ST LSM6DS3TR-C 6-axis IMU and
the Nordic nRF52840 BLE-capable MCU.

Development is staged:

1. Power and debug one node over USB-C. No battery, enclosure or soldering is
   required for this stage. Establish IMU identity/readout, sample timestamps and
   raw capture first. Calibration and attitude-estimation calls may be exercised as
   integration smoke tests, but M2 retains their formal contracts and validation.
2. Add two-node BLE data transport, explicit node identity, time synchronization
   and packet/sample loss detection.
3. Select the wearable power and mechanical assembly only after measured power,
   runtime, placement and retention evidence exists.

A protected 3.7 V LiPo around 200–300 mAh is a planning range, not a selected part
or runtime claim. The expected later assembly is XIAO + LiPo + power switch +
elastic/Velcro retention + simple enclosure.

The maintainer will learn only the basic soldering needed for wires, headers,
battery connection and a switch. Practice uses perfboard, headers and wire; the
project XIAO boards are not soldering practice boards. SMD rework and microsoldering
are out of scope.

3D printing is not a development prerequisite. Enclosure design starts after the
actual sensor placement, battery dimensions and retention method are known; models
may be developed with agent assistance and fabricated by a third-party service.

## Consequences

The active firmware target changes from ESP32-S3/ESP-IDF/BMI270 to
nRF52840/LSM6DS3TR-C. Select and pin an official-release Zephyr or nRF Connect SDK
toolchain only after a reproducible build/flash/IMU-read spike. Pin the exact sensor
driver source and license before integration.

Choosing the board does not establish its sample rate, timing, BLE throughput,
loss, synchronization, power, comfort or measurement validity. Those remain M1
evidence gates. Revisit the board only if a measured blocker prevents M1 acceptance.
