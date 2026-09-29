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
[historical exploration — historical availability](docs/PUBLIC_EVIDENCE.md#not-distributed-in-this-source-snapshot); none are active extras.

Public-export note: unavailable internal navigation is redirected to the evidence-availability index; scientific claims and original target names are retained by the export record.
