# M1 completion-driven TX dual-link retest

Status: predeclared focused retest with quantitative gates locked on 2026-09-20;
not a formal M1 acceptance run.

## Objective

Check whether the order-linked starvation observed in the closed-loop baseline
is removed when the selected completion-driven BLE TX implementation is flashed
to both nodes. Preserve the same short conditions, host recorder and raw packet
format so the result remains comparable with the retained baseline.

## Fixed conditions

- Firmware: both XIAO nRF52840 Sense nodes built from the recorded completion-
  driven TX implementation commit. The acquisition/TX queue remains four
  slots; no queue-capacity change is enabled.
- Transport: `bt_gatt_notify_cb()` is submitted from the Zephyr system
  workqueue and packet progress is completion-driven. No connection-parameter
  request or host disk-write decoupling is enabled.
- Host: the existing Bleak 3.0.2 adapter and recorder. Raw notification bytes
  are appended to the existing `.kimu` stream without resampling,
  interpolation, filtering or packet repair.
- Sensor and packetization: the existing M1 104 Hz configuration and four raw
  samples per notification.
- Each run has a fresh output directory, exact CDC byte capture, event sidecar,
  run configuration, and source/plan hashes.
- Use a new, empty persistent output root at
  `<external-data>/kineimu_m1_ble_completion_retest_20260920_clean_01`. Do not append to,
  overwrite, or reuse either September 20 artifact root.
- Host HEAD must contain the repaired matrix connection-order gate from
  `572f640e9c31bbc0caf7f66036485f921cd94c56`; the exact HEAD is captured in the
  matrix configuration.
- Flash only the recorded Node A image to the volume whose bootloader serial is
  `0000000000000001` (expected `E:`), and only the recorded Node B image to the
  volume whose bootloader serial is `0000000000000002` (expected `F:`). Verify
  the Board-ID, volume-to-serial mapping, and image SHA-256 before copying.
  After application re-enumeration, resolve each CDC port from its USB serial;
  never reuse a remembered COM number as identity.

| Node | Firmware source commit | UF2 image | SHA-256 |
|---|---|---|---|
| A | `893e9d3894f11c30862d6e34f569da3519ef2e83` | `<external-root>/zbuild/kineimu_m1_ble_completion_window_node_a_20260916_final/zephyr/zephyr.uf2` | `A85F129B6E706633C7DEBB00F8B213B0879A90597768A0CA099AC77272A6D0BF` |
| B | `893e9d3894f11c30862d6e34f569da3519ef2e83` | `<external-root>/zbuild/kineimu_m1_ble_completion_window_node_b_20260916_final/zephyr/zephyr.uf2` | `6EF7D171F9A662035E54D6F5265F74FCEB90FC628CFAFD1DFF0DAB10228FD964` |

## Conditions

1. `a_only`: connect and record Node A only.
2. `b_only`: connect and record Node B only.
3. `dual_a_to_b`: connect Node A first, then establish Node B.
4. `dual_b_to_a`: connect Node B first, then establish Node A.

The two dual conditions retain the baseline's explicit BLE establishment order.
The shared-ready barrier starts the timed acquisition window only after all
selected nodes complete control-plane setup.

## Counterbalanced execution order

Use two blocks with no manual reordering:

| Block | Run 1 | Run 2 | Run 3 | Run 4 |
| --- | --- | --- | --- | --- |
| 1 | `a_only` | `dual_b_to_a` | `b_only` | `dual_a_to_b` |
| 2 | `dual_a_to_b` | `b_only` | `dual_b_to_a` | `a_only` |

Keep the per-run duration and inter-run rest fixed and record both in
`matrix_config.json`.

The two blocks are repeated measurements on the same two boards and host. Report
each run under its block and exact connection order. Do not treat the two blocks
as independent statistical samples or use them for an inferential test.

## Required observations

Retain the same firmware CDC fields as the baseline: actual connection
interval, latency, supervision timeout, PHY, DLE, notify completion count,
failure count, maximum/total completion duration, queue high-water and loss
counters. Retain one host callback timing event per telemetry notification,
plus immutable raw bytes and packet sidecars.

## Locked quantitative pass/fail rule

The following thresholds are fixed before the new capture. Run exactly the two
blocks above, with 15.0 seconds of active capture per condition and 2.0 seconds
between runs. Do not replace a failed run or change the order, duration, firmware,
adapter, or connection settings during this matrix.

1. **Setup and connection:** all 8/8 runs complete with no runner error, BLE
   setup/connection error, rejected configuration, or identity mismatch. The
   recorded Node A/B hardware IDs and firmware source commit must match the
   identities and candidate above.
2. **Same-block single-node throughput:** let `P(node, run)` be the number of
   decoded telemetry packets in that run's immutable raw stream, corroborated by
   the recorder result. Throughput is `P / 15.0 packets/s`. For every dual run,
   each connected node must deliver at least 90% of its own same-block single-node
   control throughput: `P(node, dual) / P(node, same-block single) >= 0.90`.
   This gives a separate A and B comparison for each of the four dual runs.
3. **Connection-order balance:** for every dual run,
   `P(first-connected node) / P(second-connected node) >= 0.90`.
4. **Loss and parse quality:** firmware `tx_enqueue_drops` must remain zero
   through the matrix. Evaluate its cumulative trace from the freshly flashed
   zero baseline and also report each run's first-to-last trace delta. In every
   node/run raw-stream QC summary, `decode_errors == 0` and
   `framing_errors == 0`; no notification event may report `crc_ok == false`.
   Missing evidence for one of these required checks cannot count as a pass.

Every gate must pass; otherwise the focused retest fails and the eight-context
candidate is formally rejected for this transport acceptance gate. Report all
8 runs in block/order sequence with packet counts, packet rates, same-block
single-node ratios, first/second ratio, enqueue-drop delta, CRC/decode/framing
counts, and setup result. Retain all other QC and transport counters as observed
diagnostics. This result does not close the separate sustained-duration,
synchronization, power or shoulder-validity gates.

## Predeclared action after a failed gate

Stop completion-window tuning: do not enlarge the queue or add completion
contexts. The next task is a separate, bounded root-cause investigation. Add
diagnostics for `bt_gatt_notify_cb()` return codes, `-ENOMEM`/`-EAGAIN` retry
counts, live and peak in-flight notifications, and completion age. First test
the Windows BLE central/controller connection-event scheduling hypothesis, with
a different BLE central or USB adapter as the highest-information comparison.
If no substitute central is available, predeclare a connection-parameter or
connection-event scheduling experiment. Change one factor per experiment and
revisit the previous conclusion that no connection-parameter request is needed.
