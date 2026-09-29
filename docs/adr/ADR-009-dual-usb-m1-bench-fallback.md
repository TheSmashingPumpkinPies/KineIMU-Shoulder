# ADR-009: Dual USB acquisition for the M1 long bench

- Status: Accepted
- Date: 2026-09-25
- Authorization: maintainer instruction to remove the M1 gate blockage and make the 30-minute test directly runnable.
- Refines the M1 transport path in ADR-008 and the acceptance criteria. It does not change the public schema, selected boards, sensor configuration, or V1 shoulder scope.

## Context

The completion-window BLE implementation was physically retested in both link orders. The later V9 raw evidence shows a repeatable first-connected-node penalty on the current Windows host and its single MediaTek BLE controller: 27–43 packets per 15 seconds on the first link versus 330–371 on the second and about 390 in single-node controls. The impaired board follows connection order. The first link records extensive `-ENOMEM` retries. The locked V9 formal classification is inconclusive for its predeclared schema and decision gates, and no specific peripheral firmware repair has been established. Repeating that matrix or enlarging the queue is not a justified route to a 30-minute stable capture.

ADR-008 already treats BLE and USB acquisition as peer live backends. Both identified XIAO boards have a tested USB packet path using the same M1 packet bytes, device timestamps, node IDs and sample/packet sequences.

On 2026-09-25, matched Node A/B USB images were compiled from `cbb2a8bbdda6be82ca893781d450c731b680ebae`, flashed to serial-matched boards, and captured concurrently for 15 seconds. A delivered 390 packets / 1,560 samples; B delivered 394 packets / 1,576 samples. Both immutable streams passed parser and sequence QC with zero missing packets or samples, and the observed dual capture overlapped for the scheduled window. The read-only summary measured 104.34 Hz for A and 106.38 Hz for B. The first post-arm interval was partial and exceeded the maximum interval-deviation gate. An explicit startup-boundary firmware correction was then flashed to both serial-matched boards. The corrected 15-second pilot delivered A 389 packets / 1,556 samples and B 398 / 1,592, with zero sequence loss or parser errors and maximum interval deviations of 91/92 µs. A direct-continuation smoke test also passed after preserving the USB pre-capture backlog separately. This is short readiness evidence, not a 30-minute result.

## Decision

Use the dual USB packet path for the formal M1 30-minute acquisition characterization. Preserve the separate failed/inconclusive BLE evidence and state the dual BLE limitation in project results. The current BLE 30-minute plan remains an unexecuted historical plan; the active USB run follows `experiments/M1_DUAL_USB_30MIN_BENCH_PLAN.md` in a new output root.

The M1 long-run acceptance decision is based on two simultaneous identified raw streams scheduled for 1,800 seconds with at least 99.5% usable overlap, immutable byte streams and sidecars, device timestamps, counts, rate, sequence and integrity checks. USB does not silently become evidence of dual BLE performance. Metrics that the USB staging firmware cannot expose as cumulative status values are reported as not measured, while packet flags and sequence evidence are still audited. The run cannot be called passed before physical execution and audit.

## Consequences

- The next acquisition action is the 30-minute dual USB bench on the current running boards using the corrected pilot as verified identity evidence, with no additional BLE root-cause matrix gate.
- M1 can report a hardware-tested dual-IMU acquisition backend if the long run passes; dual BLE remains an explicit transport limitation.
- Raw packet bytes and schema 0.1 remain unchanged. BLE connection-parameter and ATT diagnostics do not apply to the USB run.
- The hardware selection and firmware platform remain unchanged. No battery, enclosure, human, motion-capture or clinical work is added.
