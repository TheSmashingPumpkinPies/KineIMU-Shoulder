# M1 closed-loop dual-link throughput root-cause matrix

Status: predeclared measurement plan; not a formal M1 acceptance run.

## Objective

Separate the contribution of the BLE link, the firmware notification boundary,
and the host notification callback before changing transport behavior. The
experiment is specifically intended to test the observation that Node B can
remain near two packets per second while the fixed four-slot TX queue is not
necessarily the causal bottleneck.

## Fixed conditions

- Firmware: the diagnostic A/B images built from the recorded source HEAD for
  this run, with the existing four-slot queue and synchronous
  `bt_gatt_notify()` worker unchanged.
- Host: the existing Bleak 3.0.2 adapter and recorder. Raw notification bytes
  are written to the existing append-only `.kimu` stream; no resampling,
  interpolation, filtering, or packet repair is allowed.
- Sensor and packetization: the existing M1 104 Hz configuration and four raw
  samples per notification.
- No connection-parameter request, no completion-driven TX, no host disk-write
  decoupling, and no queue-capacity change is enabled during this matrix.
- Each run has a fresh output directory, exact CDC byte capture, event sidecar,
  run configuration, and source/plan hashes.

## Conditions

Each condition is a short, stationary capture of the same duration:

1. `a_only`: connect and record Node A only.
2. `b_only`: connect and record Node B only.
3. `dual_a_to_b`: connect Node A first, then establish Node B.
4. `dual_b_to_a`: connect Node B first, then establish Node A.

The two dual conditions are deliberately ordered at the BLE connection boundary;
the host recorder's shared-ready barrier still starts the timed acquisition
window only after all selected nodes have completed control-plane setup.

## Counterbalanced execution order

Use two blocks, with no manual reordering:

| Block | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| 1 | `a_only` | `dual_b_to_a` | `b_only` | `dual_a_to_b` |
| 2 | `dual_a_to_b` | `b_only` | `dual_b_to_a` | `a_only` |

This places every condition once in each half of the matrix and balances the
two dual-link establishment orders. Keep the inter-run rest interval fixed and
record it in `matrix_config.json`.

## Required observations

The firmware CDC diagnostics record, per connection snapshot:

- actual connection interval in microseconds, peripheral latency, and
  supervision timeout in microseconds;
- actual PHY TX/RX and Link Layer data-length TX/RX limits and times;
- raw callback values for parameter, PHY, and DLE updates;
- cumulative notify call count, failures, last/max synchronous notify-call
  duration, and total duration.

The host event sidecar records, per telemetry callback:

- callback sequence, entry/exit monotonic timestamps, wall duration, and
  payload length;
- the existing packet event and unchanged raw capture offset.

## Decision rule after capture

- If the actual connection parameters differ materially between conditions and
  the throughput change follows that difference, evaluate a bounded
  connection-parameter request.
- If device notify-call duration stalls in the dual condition while host
  callback durations remain small, evaluate a completion-driven TX design with
  explicit packet lifetime and callback ownership.
- If host callback p95/max is material while device notify-call duration is
  ordinary, evaluate decoupling raw disk writes with an explicit bounded writer
  and loss policy.
- A high queue high-water value alone is not a root-cause decision and is not a
  reason to enlarge the four-slot queue.

No fix is selected or applied before the matrix and offline audit are complete.
