# M1 BLE acquisition application

This is the first buildable BLE acquisition slice for the XIAO nRF52840 Sense
M1 node. It is a separate application from
[`node_a_bringup`](../node_a_bringup/README.md), which remains the USB-C staging
path. Both applications reuse the same explicit raw acquisition, timestamp,
queue, packet and sensor-register adapters.

## Build

Use the pinned Zephyr v4.4.0 workspace and SDK described in the parent
[firmware README](../README.md). Keep the build directory outside the Git
worktree to avoid generated files in the repository:

```powershell
$repoRoot = '.'
$zephyrRoot = '<firmware-workspace>\Toolchains\KineIMU-Zephyr-4.4.0'
$sdkRoot = '<firmware-workspace>\Toolchains\Zephyr-SDK-1.0.1'
$venvScripts = Join-Path $zephyrRoot '.venv\Scripts'
$env:PATH = "$venvScripts;$env:PATH"
$env:ZEPHYR_BASE = Join-Path $zephyrRoot 'zephyr'
$env:ZEPHYR_SDK_INSTALL_DIR = $sdkRoot
$env:ZEPHYR_TOOLCHAIN_VARIANT = 'zephyr'

& (Join-Path $venvScripts 'python.exe') -m west build -p always `
    -b 'xiao_ble/nrf52840/sense' `
    -d '<external-root>\zbuild\kineimu_m1_ble_node_a' `
    (Join-Path $repoRoot 'firmware\xiao_nrf52840_sense\m1_ble')
```

Build the Node-B logical image only with an explicit selection:

```powershell
& (Join-Path $venvScripts 'python.exe') -m west build -p always `
    -b 'xiao_ble/nrf52840/sense' `
    -d '<external-root>\zbuild\kineimu_m1_ble_node_b' `
    (Join-Path $repoRoot 'firmware\xiao_nrf52840_sense\m1_ble') `
    -- -DKINEIMU_NODE_ID=2
```

The CMake configuration resolves the current worktree `HEAD` and embeds its
40-character Git SHA-1 in identity/config. The application also exposes the
nRF52840 FICR-derived hardware ID and generates a non-zero boot ID on every
boot. The generated `zephyr\zephyr.uf2` remains in the external build
directory.

## Runtime contract

At boot the app waits for the deferred LSM6DS3TR-C power-up, configures the
frozen M1 values (104 Hz, +/-4 g, +/-500 degrees/s), captures the DRDY-based
MCU timestamp and records the contract-order 19-byte register snapshot. It
then advertises as `KineIMU-M1` with the frozen M1 GATT service.

The peripheral registers the Zephyr connection callbacks before enabling the
Bluetooth stack. A failed connection callback or a disconnect callback only
requests a system-workqueue restart; it never calls `bt_le_adv_start()` from
the Bluetooth callback context. The delayable work item starts the same
connectable advertisement asynchronously, treats `-EALREADY` as already
healthy, and retries transient resource errors (`-ENOMEM`, `-ECONNREFUSED`,
`-EAGAIN` and `-EBUSY`) every 100 ms. This covers the short interval in which
Zephyr is still releasing the old connection object after a link loss.

The shared raw acquisition adapter sets `ACCEL_CLIPPED` and `GYRO_CLIPPED`
after decoding each signed-count burst. Its auditable code-domain thresholds
and their LSM6DS3TR-C sensitivity basis are documented in the
[Node A raw-acquisition notes](../node_a_bringup/README.md#sample-level-clipping-flags).
Those flags do not turn a raw-code boundary into a claim of analog hardware
saturation; a physical clipping/noise pilot remains required before the
selected ranges are treated as suitable for shoulder acquisition.

The app does not begin publishing samples until a connected host has a
negotiated ATT MTU of at least 127 bytes and has enabled the telemetry notify
CCC. The host should read identity/config and status before enabling telemetry.
Telemetry uses the existing v1 packet encoder with up to four raw samples per
notification. Clock requests are answered on the clock characteristic with
the boot ID, epoch, callback-entry receive time and indication-queue time.

If the link becomes unavailable after acquisition starts, the app keeps the
bounded acquisition queue active. Queue loss, FIFO overrun, sequence gaps and
transport backpressure remain visible through packet flags and the readable/
indicatable status value; no resampling or silent raw-data repair is performed.

The host recorder gives every individual `connect()` call a 5-second default
timeout (`connection_timeout_s`) and starts a separate 10-second default
recovery deadline (`recovery_timeout_s`) when a disconnect is observed. Each
reconnect attempt is capped by the remaining recovery time, while identity/
configuration validation, clock exchange and telemetry notification setup are
repeated before the stream is accepted. `recovery_start`, `reconnect`,
`telemetry_resume` and `recovery_complete` sidecar events make this boundary
auditable. The CLI exposes these two values as `--connection-timeout` and
`--recovery-timeout`; the public session schema and immutable raw framing are
unchanged. On the Windows/WinRT backend, the host adapter clears the
`GattSession.maintain_connection` flag before closing a client so the
peripheral can observe the link release instead of retaining a stale session.

The transport uses a four-slot, fixed-size TX queue and
`CONFIG_BT_ATT_TX_COUNT` independent completion-owned notification contexts
(eight in the reference configuration). `enqueue()` copies the encoded bytes
into the queue; the TX worker copies each accepted packet into an available
completion context and submits `bt_gatt_notify_cb()` from Zephyr's system
workqueue. The worker can keep multiple ATT-owned packets in flight and does not
block on one slow completion. Each context and its packet bytes remain valid
until the corresponding callback arrives. A full ATT pool retries after 5 ms.
If a disconnect suppresses callbacks, cancellation retains affected contexts
until later system-workqueue reclaim confirms that Zephyr has drained the old
ATT-buffer ownership. Connection generations reject stale queued packets and
stale completions.

The queue still rejects the newest packet when full, preserves accepted FIFO
order, flushes and invalidates packets on disconnect, and stops permanently on
terminal application shutdown. Queue capacity, public status/GATT fields,
packet bytes and raw framing are unchanged. Queue high-water,
enqueue/disconnect/stop losses and queue peak remain available in the existing
CDC trace. The legacy `notify_calls` field counts terminal completion contexts
(completed, failed or canceled), not calls to `bt_gatt_notify_cb()`;
`notify_failures` counts those terminal contexts whose result is negative,
including cancellation. The legacy duration fields start when a completion
context is claimed and include work scheduling and retry delay. They are not
GATT call duration or accepted-to-callback age.

The CDC trace also emits one `tx_diag` summary with actual GATT calls and exact
return-code counts, `-ENOMEM`/`-EAGAIN` resource-pressure returns, retry and
work-scheduling failures, terminal submission failures, definite post-dequeue
packet drops, cancellation/callback counts, completion-window occupancy and
wait time, and accepted-to-callback age statistics. Temporary resource returns
are counted even when a retry later succeeds; they do not become terminal
failures or packet drops by themselves. A canceled context is a definite drop
only when reclaim confirms no GATT call was accepted. Queue loss categories
remain separate. The trace is emitted at the existing status interval, not per
packet. This is an experimental bounded transport change; it does not claim
that a larger queue alone can absorb a blocked BLE path.

At the BLE stream boundary, and after any active callback that has no matching
GPIO ISR timestamp, the app keeps acquisition inactive while it disarms the
LSM6DSL trigger, drains one raw frame, waits for INT1 to be inactive, re-arms
the trigger and verifies the line again. The operation is bounded to three
attempts; a permanently asserted line publishes the existing acquisition
error/fatal status. A callback without an ISR timestamp is discarded and can
request another bounded re-arm, but it is never assigned deferred-handler
time and never becomes a sample. The detailed QEMU RED/GREEN/mutation record
is in
`node_a_20260914_drdy_toctou.md` (complete record retained in the local evidence archive).

## Current validation boundary

The codec, Git identity parser, ATT-MTU policy, register snapshot and FIFO
statistics have QEMU unit coverage. The reference `xiao_ble/nrf52840/sense`
image compiles successfully. Physical BLE central interoperability, sustained
30-minute timing/loss characterization, two-node synchronization, power and
the complete M1 acceptance gate remain open. This slice has not been flashed
or presented as M1 completion.
