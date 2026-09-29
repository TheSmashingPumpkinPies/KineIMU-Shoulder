# Third-Party Compatibility — KineIMU Shoulder

| Component | Role | License / state | Strategy |
|---|---|---|---|
| Upstream Zephyr v4.4.0 + Zephyr SDK 1.0.1 | nRF52840 firmware, USB and BLE | Apache-2.0 core with per-module licenses; selected by ADR-007 | Record west revisions, SDK checksum/notices and reproducible XIAO build |
| Zephyr `st,lsm6dsl`-compatible driver | onboard LSM6DS3TR-C acquisition | In-tree path passed Node A deferred-init readout; Node B/timing/FIFO open | Verify ODR/range, data-ready timestamp capture, FIFO/overflow and Node B; ST BSD-3-Clause PID remains reference |
| Fusion / imufusion 1.3.3 | AHRS | MIT; M0 API smoke-tested | Adapter converts SI, declares axes/quaternion/timing |
| imucal 2.6.0 | calibration | MIT; M0 SI API smoke-tested | Artifact-specific input/output unit contract |
| pyserial 3.5 | USB-C CDC host capture | BSD-3-Clause; optional capture extra | Reads bytes only; parser preserves complete `.usb.bin`, accepted payloads use frozen `.kimu` framing, and issues remain in NDJSON |
| Bleak 3.0.2 | Host BLE central/recorder | MIT; optional `ble` extra | Production recorder retains explicit address targets, identity/config validation, MTU gate, notification callbacks and disconnect callback; the M1 root-cause runner separately does an M1-service-filtered scan, passes the fresh matching `BLEDevice` and M1 service filter to Bleak, and records the 5 s scan separately from its 15 s Windows connect/GATT budget. Its timing adapter wraps the pinned Bleak 3.0.2 WinRT backend `_get_services` coroutine only during `connect()` and fails closed if that hook is absent; timed cancellation runs bounded disconnect cleanup. It performs no unit/axis conversion and does not change the production recorder's timeout. |

Python baseline remains 3.12.14 with uv 0.12.5.
Compatibility includes installation and actual API calls, not import alone.
Internal acceleration m/s² and gyro rad/s; imufusion requires g and deg/s.
No adapter may hide resampling or assume arbitrary anatomical alignment.
See BACKEND_CONTRACTS and DEPENDENCY_MATRIX.
Retired backend evidence is [historical — historical availability](docs/PUBLIC_EVIDENCE.md#not-distributed-in-this-source-snapshot).

M6.4 records the maintainer-approved MIT license for original code and documents,
Copyright (c) 2026 Hongbo Liao. [CITATION.cff](CITATION.cff) identifies Hongbo Liao
as project author, version 0.1.0 and the selected public repository destination.
The selected original synthetic sample has a separate CC0-1.0 grant.
[Third-party statements](THIRD_PARTY_NOTICES.md) and installed license texts
preserve upstream licensing independently of the project license.
See the [release-review sheet](docs/release/REVIEW.md) and
[current CP4 verification](experiments/M6_CP4_FINAL_20260928/README.md).
Technical acceptance and actual public publication are recorded separately.

Public-export note: unavailable internal navigation is redirected to the evidence-availability index; scientific claims and original target names are retained by the export record.
