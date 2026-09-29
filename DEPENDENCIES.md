# Dependencies — KineIMU Shoulder

| Function | Selection | Boundary |
|---|---|---|
| Numerical | NumPy / SciPy | Core, existing pinned versions |
| Tables | pandas | Core |
| Calibration | imucal | Optional calibration extra; adapter contract |
| Orientation | imufusion | Optional orientation extra; explicit SI conversion |
| Combined analysis dependencies | imucal + imufusion | analysis extra |
| USB-C CDC capture | pyserial 3.5 | Optional capture extra; byte-preserving `scripts/capture_m1_usb.py` adapter |
| Host BLE central/recorder | Bleak 3.0.2 | Optional `ble` extra; async GATT client boundary in `kineimu_shoulder.io.m1_ble` |
| Firmware platform | Upstream Zephyr v4.4.0 + Zephyr SDK 1.0.1 | Selected by ADR-007; pin west revisions and SDK checksum in setup evidence |
| Firmware IMU driver | Zephyr in-tree `st,lsm6dsl` compatibility | First path for XIAO LSM6DS3TR-C; verify identity/ODR/FIFO/interrupt behavior |
| Plotting | Select when validation needs it | No new runtime dependency in pivot |

Keep CPython 3.12.14 / uv 0.12.5 and uv.lock.
Prefer mature implementations, pin versions/licenses and cite source/paper where relevant.
The verified Zephyr source/module revisions, firmware Python freeze, SDK distribution and
installed-tree hashes, exact Windows build commands and UF2 hashes are recorded in
[the XIAO compile-spike evidence](firmware/xiao_nrf52840_sense/README.md).
No vendoring or new dependency without justified review. The official ST
`lsm6ds3tr-c-pid` is BSD-3-Clause reference material, not an active dependency while
the selected Zephyr in-tree driver is being verified against the required contract.
API smoke tests do not validate measurements.
Legacy application dependencies and their compatibility results are archived in
[historical exploration — historical availability](docs/PUBLIC_AUDIT.md#not-distributed-in-this-source-snapshot); none are active extras.

Public-export note: unavailable internal navigation is redirected to the evidence-availability index; scientific claims and original target names are retained by the export record.

## Pinned Python API baseline

| Package | Version | License | Role | API evidence |
|---|---|---|---|---|
| numpy | 2.5.2 | BSD-3-Clause | core | arrays/shapes |
| scipy | 1.18.1 | BSD-3-Clause | core | identity quaternion rotation |
| pandas | 3.0.5 | BSD-3-Clause | core | table |
| imufusion | 1.3.3 | MIT | orientation / analysis extra | stationary update, normalized wxyz |
| imucal | 2.6.0 | MIT | calibration / analysis extra | SI identity calibration, JSON round trip |

Run tests/integration/test_dependency_smoke.py for callable-contract evidence, not scientific validity.
imufusion requires set_sample_period before two-vector update; consumes g and deg/s.
imucal units are explicit SI in the tested contract.

License shorthand is not the complete distribution inventory; retain
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and upstream license texts.
API smoke calls establish compatibility, not measurement or clinical accuracy.

## Backend input/output contracts

| Adapter | Input | Output / limits |
|---|---|---|
| `io.m1_raw` | Signed int16 sensor-register X/Y/Z, configured ranges/sensitivities and explicit SensorToNodeTransform | One SI row per sample with original counts, device time, sequence and flags; no interpolation or anatomical alignment |
| imucal 2.6.0 | Explicit SI accel/gyro and versioned calibration artifact | Calibrated arrays with declared units; calibration does not align segments |
| imufusion 1.3.3 | Adapter converts rad/s to deg/s and m/s² to g; observed device dt | Declared active sensor/node-to-world q_WN, wxyz; fresh backend state; initialization is an assumption, not anatomical heading |
| Bleak 3.0.2 | Explicit address-to-node assignment, expected identity and frozen GATT service | Unchanged notification bytes per node, callback-entry monotonic time and event sidecar; identity/config validation, ATT MTU >=127, new connection identity after reconnect |
| pyserial 3.5 | USB CDC bytes | Byte-preserving capture; separate framing/issues and frozen KIMU parsing |

The retained Node B raw-count example uses node = I * sensor, 0.122 mg/LSB at
±4 g and 17.50 mdps/LSB at ±500 °/s, explicitly converted to m/s² and rad/s.
These are nominal configuration scales, not a calibration-accuracy claim.
Call Ahrs.set_sample_period before its two-vector update. Backend shape, axes,
rotation direction, missing/gap rejection and timing are explicit under
[the processing contract](protocols/M2_PROCESSING_CONTRACT.md). Reject incompatible
configuration and duplicate/reordered/over-limit timing; apply alignment once.
Adapters never hide resampling. Physical BLE interoperability and throughput
require physical evidence; API compatibility alone does not establish them.
