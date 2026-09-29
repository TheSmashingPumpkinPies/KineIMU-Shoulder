# M1 BLE Connection-Parameter Root-Cause Matrix — Plan v2

Plan date: 2026-09-23 (Asia/Shanghai)
Version: **v2, locked before acquisition**
Status: **PREDECLARED PLAN. Do not begin the formal matrix until this file is
committed, its SHA-256 is pinned in the runner, and a new empty output root and
matching preflight record are verified.**

This plan supersedes the host-connection setup procedure for a new execution
only. The 2026-09-21 plan, its formal matrix, report, raw evidence and
inconclusive disposition remain immutable.

## Objective and immutable experiment design

Measure whether the XIAO peripheral's one-time request for a 15 ms / latency 0 /
420 ms BLE connection tuple changes the negotiated parameters and dual-link TX
completion behavior on the same Windows central, two boards and firmware build.
This is a short root-cause diagnostic, not an M1 acceptance run and not a
clinical or shoulder-metric validation.

The only treatment remains whether the peripheral application issues one
connection-parameter request per connected node after the link is established:

| Mode | Peripheral action |
|---|---|
| OFF | No local `bt_conn_le_param_update()` call. The matched build disables Zephyr's automatic peripheral update. The Windows central may still negotiate or initiate a tuple change; record the observed values. |
| ON | Issue one request for 15 ms minimum and maximum interval, latency 0, and 420 ms supervision timeout. Record its firmware API return and all actual parameter callbacks. No application retry loop. |

Do not change public schemas, BLE queue or ATT completion resources, firmware
retry delay, sensor rate, packetization, connection parameters beyond the
predeclared ON request, host disk, or capture code between modes. Do not change
the target tuple, run order, 10-second observation, 15-second capture, or
2-second inter-run rest. Do not replace or repeat any scheduled condition.

## Why v2 changes connection setup

The old matrix used a five-second total connect gate. In Stage 12, Windows
address-string and exact-`BLEDevice` paths both timed out with A/B at zero
packets. The five-second limit included Windows connection and GATT setup, so
neither attempt entered the planned observation/capture path.

Stage 10A Node A acknowledged ON (`api_rc=0`) but has only 6.608944 seconds of
events after the actual firmware peripheral-connected callback. Its one
non-target callback therefore does not establish failure of the full planned
10-second target gate. Stage 10A is **inconclusive**. Stage 10B Node B observed
the target tuple at 5.469 s, then a different tuple at 7.969 s, then the target
again at 9.922 s after the real connected event. These records require a full
10-second event-relative window that preserves every callback; the first
non-target callback cannot decide the gate.

The following setup-policy changes apply only to this experiment runner. They
do not change the production recorder's global connection defaults:

1. Measure M1-service-filtered scan separately from Windows connection/GATT.
2. Before each connection, perform a bounded 5.0-second M1-service-filtered
   scan for the explicit expected address. Require a fresh matching
   `BLEDevice` result.
3. Construct BleakClient from that `BLEDevice` and pass the M1 service filter;
   do not trigger implicit address-string discovery from `connect()`.
4. Allow an independent 15.0-second upper bound for Windows OS connect and GATT
   service setup. Record scan, OS connect, GATT service discovery, identity,
   MTU, CDC control, parameter-window and capture times separately. The scan
   duration is not charged against this 15.0-second limit.
5. Keep a separate 1.0-second scan-context cleanup grace after the 5.0-second
   scan, with a 6.0-second scan watchdog. This grace does not extend the scan
   search interval or the 15.0-second connect/GATT limit.
6. Start each selected node's 10.0-second parameter deadline at its actual
   firmware CDC `connected` event and `k_uptime_get_32()` value. If the host
   connect coroutine returns later, do not shorten the window. For dual runs,
   preserve that node's callbacks while its deadline runs; the telemetry-enable
   gate waits until every selected node has completed its own full window.
7. Complete MTU, identity/config, status and clock/control-plane validation
   after the host connection is established. Do not let those operations reset
   or shorten an already-running firmware-event-relative parameter deadline.
   Enable telemetry and start the 15.0-second capture only after all selected
   connections, validation checks and complete parameter windows have passed.
8. At teardown, call host disconnect for every created BLE client and require
   the latest successful host attempt's matching firmware connected and
   disconnected events. Anchor the fixed 2.0-second rest after this confirmed
   teardown time. If the control gate fails or teardown is not confirmed, stop
   before another scheduled run and preserve the partial result.

## Prior evidence required by this plan

The matched diagnostic images and all three physical gates have passed. Their
raw evidence and manifests are persistent and independently hash-checked.

| Evidence | Result | Manifest SHA-256 |
|---|---|---|
| Gate 1, CDC session/reopen/control | A/B pass; exact session/tx ACKs, OFF→ON→OFF, same-boot reopen with a new session, stale ACK and old-session rejection | `E0C3D5FF3E411AAC91FBE306A6DD50A5821CA3737CADBCAA06AA84C3BFA1119A` |
| Gate 2 retry 2, parameter smoke | A/B pass; complete event-relative windows 10.016 s / 10.015 s; both observed 15 ms / 0 / 420 ms; confirmed firmware disconnect then OFF `rc=0` | `31D3B97DC2FD267CE599FB4A799AE043C7BBFE908803435BD6A81FF0152463E5` |
| Gate 3, acquisition smoke | A/B 15 s; 389 / 398 valid packets; callback/raw_try/raw_ok/notify_calls deltas 1,404/1,404/1,404/351 on both; zero CRC/decode/framing/node mismatch | `91E05A5AC7BE0CB8600B2DE423A8368EC9EB21334A921936185B6DB5A6A29E7D` |

Evidence root for these gates:
`<external-data>/kineimu_m1_cdc_unblock_20260923_01`. Earlier failed Gate 2 attempts
remain in their separate roots and are not inputs to the formal matrix.

## Hardware and matched firmware lock

Use the same two Seeed XIAO nRF52840 Sense boards, firmware, Windows machine,
MediaTek Bluetooth adapter and driver used for the physical gates. Re-resolve
the board bootloader serials and application CDC ports by USB serial before the
formal run; COM port numbers are not board identities.

| Node | Node ID | Bootloader USB serial | Last application CDC port | BLE address | Expected hardware device ID |
|---|---:|---|---|---|---:|
| A | 1 | `0000000000000001` | COM5 | `02:00:00:00:00:01` | `1` |
| B | 2 | `0000000000000002` | COM8 | `02:00:00:00:00:02` | `2` |

The recorded host is Windows 10 Home China, DisplayVersion 25H2, build
26200.9457, using the MediaTek Bluetooth Adapter
(`USB\VID_13D3&PID_3563&MI_00\7&1d754fa2&0&0000`), driver `oem134.inf`
version 1.3.17.169 (2026-03-25), project Python 3.12.14, and Bleak 3.0.2.
Recheck and record these identities at preflight; use the same host/controller
and driver for this comparison.

Build provenance is recorded in
`<external-data>/kineimu_m1_cdc_unblock_20260923_01/firmware_build_and_board_map.json`:

- Firmware/host source commit embedded in both images:
  `270911756c227a20feb18df71edad7ad4544aedb`.
- Upstream Zephyr v4.4.0 commit
  `684c9e8f32e4373a21098559f748f06915f950c9`, Zephyr SDK 1.0.1, target
  `xiao_ble/nrf52840/sense`.
- Both generated `.config` files are byte-identical (57,969 bytes), SHA-256
  `0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69`.
  `CONFIG_USB_DEVICE_STACK_NEXT=y`, `CONFIG_UART_INTERRUPT_DRIVEN=y`,
  `CONFIG_UART_CONSOLE=y`, `CONFIG_BT_GAP_AUTO_UPDATE_CONN_PARAMS=n`,
  `CONFIG_BT_GAP_PERIPHERAL_PREF_PARAMS=y`; preserve the existing preferred
  tuple and `CONFIG_BT_CONN_PARAM_UPDATE_TIMEOUT=5000`.
- Shared overlay SHA-256:
  `1B2BB4FAFA44259BAB33829EEE932EFA993F6AEBE6F82D7367DAA791AF78C9EB`.
- Node A: ELF SHA-256
  `0E73F614C8699D041E2FA0D781C057DE4BFF11A613907DF03FA1BC428FAECCEA`,
  UF2 314,368 bytes SHA-256
  `226B77FCEA1054022DA9F0E9884D3297245050A88156CE2EAD7A9177B4177380`,
  FLASH 157,112 B / RAM 48,276 B.
- Node B: ELF SHA-256
  `C0D9C9445664B5D251BC3BFAE2582164BD24F6D5AB455A5D048A854589C9A6ED`,
  UF2 314,368 bytes SHA-256
  `6B38472B703D9B102767A1823BC34876EE24B0AA67AA328E346F1312B8525B32`,
  FLASH 157,144 B / RAM 48,276 B.

The images were built from one source commit and identical generated
configuration; node identity is the expected image difference. Each matching
UF2 was flashed once to its serial-matched board and application identity was
confirmed. No further reflash is planned because firmware is unchanged.
Before acquisition, the preflash record must bind this v2 plan hash to the
image/config hashes, source commit, board IDs and exact USB serials.

## Locked conditions, order and timing

Conditions and connection order:

- `a_only`: connect and record A only.
- `b_only`: connect and record B only.
- `dual_a_to_b`: connect A first, then B.
- `dual_b_to_a`: connect B first, then A.

Run the four fixed Williams-order blocks exactly as follows:

| Block | Request | Sequence | Run 1 | Run 2 | Run 3 | Run 4 |
|---:|---|---|---|---|---|---|
| 1 | OFF | W1 | `a_only` | `b_only` | `dual_b_to_a` | `dual_a_to_b` |
| 2 | ON | W2 | `b_only` | `dual_a_to_b` | `a_only` | `dual_b_to_a` |
| 3 | ON | W4 | `dual_b_to_a` | `a_only` | `dual_a_to_b` | `b_only` |
| 4 | OFF | W3 | `dual_a_to_b` | `dual_b_to_a` | `b_only` | `a_only` |

This is 16 scheduled conditions: four per request setting and two repetitions
of each condition per setting. Use exactly 10.0 seconds for parameter setup/
settling from each actual firmware connected event, exactly 15.0 seconds of
active capture, and exactly 2.0 seconds between runs after confirmed firmware
disconnect. Setup and connection time are outside the capture window. Do not
start telemetry before the full parameter window ends. Preserve every actual
in-window `param_updated` tuple and its firmware uptime. The target gate is
whether 15,000 us / latency 0 / 420,000 us is observed at least once in the
complete ON window; a different callback earlier in the window is not a final
failure. Do not require tuple stability beyond the predeclared criteria below.

Before each block transition, send the block's mode to both nodes while
disconnected and require the exact nonce-bound CDC READY/session/tx ACKs and
firmware API result. Each ON link must log `api_rc=0`; OFF links must show no
local parameter request. The capture and result index must retain control
failures, setup/capture errors, partial files and the exact attempted count.

If an ordinary setup or capture condition fails, keep its scheduled result and
any partial output, then continue in the exact order only if cleanup is
confirmed and CDC control remains healthy. Never replace or repeat that
condition. A CDC control failure or unconfirmed BLE cleanup stops the schedule
to avoid contaminating later runs; the incomplete matrix remains
**inconclusive**, with its stop reason and attempted count preserved.

## Output and immutable evidence

The new persistent root is
`<external-data>/kineimu_m1_ble_connparam_rootcause_v2_20260923_01`. It was absent at
plan creation. Verify again that it is absent or empty before the first run;
create it only after the committed plan hash, software preflight, board identity
and preflash record pass. Never write to the old root
`<external-data>/kineimu_m1_ble_connparam_rootcause_20260921_01` or any prior Gate
root.

Copy this exact plan into the new root. Preserve the matrix configuration and
result index, preflight record, raw CDC bytes and event sidecars, all BLE raw
streams and event sidecars, every actual parameter callback, identity/MTU/
control results, timing records, partial output, independent calculations,
manifest and per-file SHA-256 values. Independently recompute raw packet counts,
diagnostic counter deltas, treatment realization and outcome labels from the
saved raw evidence. Do not use the existing audit report as the analysis input.
Keep raw data read-only during analysis and do not add fields to the public
capture schema.

## Predeclared comparisons

Report all 16 scheduled outcomes individually and compare each block's dual run
with that block's same-node single-node control:

- Negotiated interval, latency and supervision timeout; local request call and
  return; and every actual tuple callback.
- Per-node median and p95 notification completion age.
- `-ENOMEM` / `-EAGAIN` retry counts per active second and per notification
  submission.
- Full-window event counts and wait time per active second and per submission.
- Valid packets per 15 seconds and packets per second; dual/single ratios within
  each block; and first-connected/second-connected ratios.
- Firmware enqueue/drop counters, packet/sample gaps, CRC-false events,
  decode/framing errors, node mismatches and setup errors.

Use run-local first/last diagnostic deltas, split by boot and connection
generation. Compare OFF and ON descriptively as repeated measurements on the
same two devices and host. Do not use inferential tests or generalize to other
central adapters or systems.

## Locked outcome labels

First decide whether the treatment contrast was realized. It is realized only
when every ON link observed the requested 15 ms / 0 / 420 ms tuple at least once
inside its complete 10.0-second window, and the corresponding OFF links logged
no local request and ended with a different negotiated tuple. If any ON target
is unobserved, an OFF tuple equals the target, or the required data/diagnostics
are incomplete, label the comparison **inconclusive** and identify the exact
link/run. Do not replace or rerun it.

When the contrast is realized and all required data exist:

- **Supported:** all four ON dual-link runs meet the focused transport
  thresholds (each node's dual/same-block-single ratio is at least 0.90 and the
  first/second throughput ratio is at least 0.90), with zero firmware TX
  enqueue drops and zero CRC/decode/framing errors. For both dual-link orders,
  neither node worsens in the three mechanism metrics and at least two of
  completion-age p95, retry rate and full-window wait rate improve relative to
  the OFF medians. This supports the parameter request as a contributor on this
  setup; it does not close other M1 gates.
- **Not supported:** the contrast is realized and all required data are
  present, but both dual-link orders remain below the focused transport
  thresholds in both ON blocks; for both nodes and both orders, ON median
  throughput ratios do not exceed OFF medians, and at least two of the three
  mechanism metrics do not improve. This does not support this parameter
  request as the cause of the observed bottleneck on this setup.
- **Inconclusive:** every other result, including failed/missing scheduled
  runs, incomplete diagnostics, a mixed direction, an unrealized tuple
  contrast, or a cleanup/control stop before all scheduled runs. Report the
  exact stop reason and number attempted.

Regardless of label, this matrix is not the 30-minute M1 bench, does not
validate clinical or shoulder metrics, and does not authorize M2.

## Exact next action

Commit this v2 plan before changing the runner's v2 SHA/root lock. Then add
explicit old-plan and v2-plan profiles that bind each immutable plan hash to its
own exact output root; add preflight tests for correct and cross-bound plan/root
pairs; run all software gates; verify the new root is still unused and create a
matching preflash record. Execute the fixed schedule exactly once only after
all checks pass.
