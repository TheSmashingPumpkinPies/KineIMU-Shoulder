# Node A DRDY TOCTOU re-arm evidence — 2026-09-14

## Scope

Source/test commit: `476bd9cb9276ffbbe115c50d9acb4856323cee13`.

This slice fixes the startup race between the quiet-level check and the
Zephyr v4.4.0 in-tree `lsm6dsl_trigger_set()` arm path. The driver disables
its GPIO interrupt, stores the application handler, enables the GPIO interrupt,
then checks the line level. If INT1 is already high at that point it submits a
deferred callback directly. That path does not run the shared GPIO rising-edge
timestamp callback. The global-workqueue callback later re-enables the GPIO
interrupt.

The fix keeps the existing public BLE, packet and data schemas unchanged. The
acquisition boundary now performs a bounded disarm → drain → wait-low → reset
timestamp → arm → verify-low state machine. It retries a high post-arm level
from a disarmed state, and enters an explicit fatal result after the configured
attempt bound. The M1 main loop does not mark acquisition active until the
state machine succeeds. A missing timestamp remains a hard sample gate; during
active acquisition it requests the same bounded recovery protocol.

## QEMU regression sequence

The test image was built and run with the pinned Zephyr v4.4.0 workspace and
`QEMU_BIN_PATH=<system-root>\Program Files\qemu`:

```powershell
$env:ZEPHYR_BASE = '<firmware-workspace>\Toolchains\KineIMU-Zephyr-4.4.0\zephyr'
$env:ZEPHYR_SDK_INSTALL_DIR = '<firmware-workspace>\Toolchains\Zephyr-SDK-1.0.1'
$env:ZEPHYR_TOOLCHAIN_VARIANT = 'zephyr'
$env:QEMU_BIN_PATH = '<system-root>\Program Files\qemu'
$env:Path = '<firmware-workspace>\Toolchains\KineIMU-Zephyr-4.4.0\.venv\Scripts;' + $env:Path
& '<firmware-workspace>\Toolchains\KineIMU-Zephyr-4.4.0\.venv\Scripts\python.exe' -m west twister `
    -T tests\firmware\node_a_acquisition -p qemu_cortex_m3 `
    --inline-logs --timeout-multiplier 5
```

- RED/mutation: a temporary mutation omitted the post-arm level verification,
  modelling the old one-shot behavior. QEMU executed 54/55 cases; the new
  `test_rearm_retries_arm_toctou_and_next_edge_publishes_timestamped_sample`
  failed deterministically because `result.attempts` was 1 instead of 2.
- GREEN: after restoring post-arm verification, the complete QEMU image passed
  55/55 cases. The race case observed one no-timestamp callback, published no
  sample for it, then accepted one sample after the next emulated GPIO rising
  edge with a non-zero ISR timestamp. The permanently-high case returned
  `-ETIMEDOUT`, exposed `NODE_A_IMU_REARM_FATAL`, stopped after three attempts,
  and performed zero arm calls.

The test uses a fake sensor API that raises INT1 inside
`sensor_trigger_set()` and invokes the callback without invoking the GPIO
timestamp callback. The next drain releases the emulated level. The later
edge is delivered through the GPIO emulator before the deferred handler, so
the test exercises the arm orchestration and timestamp/sample gate rather than
only testing a GPIO helper.

## Reference-board builds

`west build -p always` completed for both logical images on
`xiao_ble/nrf52840/sense` with the pinned SDK. Both images used 145,860 B
FLASH, 42,708 B RAM and produced a 291,840-byte UF2:

- Node A: `.cache/m1_ble_node_a_rearm_clean/zephyr/zephyr.uf2`, SHA-256
  `F0E93E5FF55260E38C5A2F4BF1E8CB5085670DCC74F2214E4938A58DC21E96CC`.
- Node B: `.cache/m1_ble_node_b_rearm_clean/zephyr/zephyr.uf2`, SHA-256
  `995D896C4459F10E3362F6F1A815C5B8F2A795088669D553FE150E1B3876F44A`.

These are build artifacts only. No board was flashed.

## Host checks

- Full Python suite: `64 passed`.
- `ruff check .`: passed.
- strict `mypy --config-file pyproject.toml`: passed for 12 source files.
- `python scripts/check_docs_consistency.py`: 105 Markdown files, 39 archive
  hashes, 0 errors.
