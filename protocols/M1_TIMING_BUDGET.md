# M1 Timing and Loss Budget v0.1

Status: PREDECLARED FOR IMPLEMENTATION AND BENCH CHARACTERIZATION. These are engineering
limits, not clinical performance claims. ADR-008 separates the 30-minute acquisition
stability gate from the independent clock-mapping study: rate/loss/overlap/reset rows
govern M1 hardware freeze; pairwise residual rows are evaluated only when suitable
independent events exist and otherwise remain explicitly not measured/inconclusive.

## Design basis

- Characterization duration: at least 30 minutes of simultaneous Node A/Node B data.
- Public nominal rate: 100 Hz per node.
- Initial LSM6DS3TR-C configured ODR: 104 Hz for accelerometer and gyroscope; actual
  rate is measured from device timestamps and recorded.
- Assumed relative angular-speed envelope for the timing allocation: 5 rad/s
  (about 286.5°/s). This is an engineering test assumption to be challenged by pilot
  shoulder recordings, not a patient-motion or clinical limit.
- Planned initial gyroscope range: ±500°/s (about ±8.73 rad/s). It leaves margin over
  the timing design envelope; a clipping/noise pilot must confirm or revise it.
- Maximum angular discrepancy allocated to pairwise timing error: 0.5°
  (8.73 mrad).

Using the first-order bound

``` text
absolute timing-induced angular error ≈ absolute relative angular speed × absolute pairwise time error
```

the allocation permits 1.745 ms at 5 rad/s. M1 therefore uses tighter held-out
pairwise limits of 1.0 ms at p95 and 1.5 ms maximum, corresponding to about 0.286°
and 0.430° at the assumed envelope.

This term covers synchronization only. It excludes gyro bias/noise, scale/range,
filter delay, heading observability, sensor-to-segment alignment, mounting motion and
anatomical-model uncertainty. Those terms must be reported separately at their
applicable milestones; they must not be folded into this timing number.

## Thirty-minute dual-node characterization limits

All interval statistics are computed per node and per uninterrupted clock epoch from
raw device timestamps. Accounted gaps are reported separately rather than removed
without trace.

| Measure | Pass limit |
|---|---|
| Mean measured output rate | 98.8–109.2 Hz (±5% of configured 104 Hz engineering target) |
| p99 absolute interval deviation from epoch median | ≤1.0 ms, excluding explicitly accounted gaps |
| Maximum interval deviation | ≤2.0 ms, excluding explicitly accounted gaps |
| Gap detection threshold | interval ≥1.5 × epoch median |
| Duplicate/out-of-order sample timestamps | 0 accepted as valid; every occurrence accounted |
| Unaccounted sample loss | 0 |
| Sensor FIFO overruns | 0 |
| Firmware queue overruns | 0 |
| Accounted transport sample loss | ≤0.1% per node |
| Maximum consecutive missing samples | ≤4 (one maximum-size packet) |
| Unaccounted packet loss | 0 |
| Usable dual-node overlap | ≥99.5% of scheduled recording interval |
| Unexplained resets/epoch changes | 0 |
| Held-out pairwise sync residual p95 | ≤1.0 ms when independently measurable; otherwise `not measured`/`inconclusive` |
| Held-out pairwise sync residual maximum | ≤1.5 ms when independently measurable; otherwise `not measured`/`inconclusive` |

The ±5% rate band is a project engineering gate, not a claim of manufacturer ODR
tolerance. The measured mean, median interval and full interval distribution remain
report outputs even when the gate passes.

## Clock mapping and validation

For each node and uninterrupted epoch, fit

``` text
t_common = a_i * t_device_i + b_i
```

and preserve the fit method/version, fit window, coefficients, source-event IDs and
raw hashes. Report relative drift from the fitted slopes. Do not fit across reset or
unproven discontinuity boundaries.

Use repeated rigid-fixture common events near the beginning, middle and end of the
recording. Events used to fit the mapping and held-out events used to evaluate it must
be disjoint. Report held-out residual p50, p95, p99 and maximum for each node and for
the A/B pair. Host BLE arrival times may assist transport diagnosis but may not serve
as the only synchronization evidence.

The final report must identify the event localization method and its resolution. If
reference/event uncertainty is too large to distinguish the 1.0/1.5 ms limits, the
result is inconclusive rather than passed.

## Disconnect/recovery test

Run a separate deliberate disconnect test after the uninterrupted characterization:

- record the disconnect and reconnect host-monotonic times;
- resume telemetry and re-verify identity/configuration within 10 seconds;
- preserve all counters and the clock epoch if continuity is proven;
- otherwise start a new epoch and a new mapping, without bridging the gap;
- account for every missing packet/sample and report the unavailable interval.

The host recorder uses a 5-second timeout for each individual connection
establishment and a separate 10-second recovery deadline starting when the
disconnect is observed. An in-progress attempt is capped at the remaining
recovery time. The 10-second target measures recorder recovery, not raw-data
continuity during the intentional outage.

## Required report inputs

- firmware commit/build identity and sensor driver/configuration;
- BLE connection parameters, negotiated ATT MTU and batch size;
- both immutable raw-stream and sidecar hashes;
- sample/packet sequence audits and all overflow/status counters;
- actual rates and interval/jitter distributions;
- loss, gaps, overlap, resets, disconnect/recovery and buffer high-water marks;
- clock coefficients, relative drift and held-out residuals;
- scripts/commands, environment and exact acceptance result.

Any limit revision after observing the characterization data is a new budget version
and cannot be used retrospectively to pass the same run.

## Clock event annotation and reproduction

Concurrent USB arrival, a common start command and BLE callback timing do not
establish sample synchronization. Use a rigid co-mounted bench pair and a repeated
common event with an independent reference clock; movement of separately worn
segments is not a shared-event reference. Record fixture/mounting/configuration,
reference/localization methods, resolution/standard uncertainty, raw hashes,
node IDs, device time, sample sequence and uninterrupted clock epochs.
The annotation format remains
[m1-sync-event-plan-0.1](schemas/m1-sync-event-plan-0.1.schema.json).

Predeclare E01/E02 at the beginning, E03/E04 in the middle and E05/E06 at the end:
odd IDs are fit events, even IDs held-out. They must be disjoint, cover both nodes
and all phases. Every evaluated epoch needs at least two fit events and one held-out
event; reset/discontinuity starts a new epoch rather than bridging it.
Fit centered t_common_us = a_i * t_device_us + b_i; report uncentered coefficients,
covariance, source-event IDs/windows and (a_i - 1) * 1e6 drift ppm. Pairwise
B-minus-A offset and (a_B / a_A - 1) * 1e6 drift stay scoped to each epoch pair.

For uniform resolution bins, standard uncertainty is resolution_us / sqrt(12);
other distributions require a recorded method. Expanded uncertainty uses k = 2.
The guard is the larger of maximum expanded uncertainty and conservative combined
reference/localization resolution. At >=500 µs it cannot distinguish the frozen
1.0 ms p95 / 1.5 ms maximum limits, so the result is inconclusive. With sufficient
resolution, exceedance fails. Roughly 100 Hz nearest-sample annotation is normally
insufficient; sub-sample localization requires independent resolution justification.
Interpolation for event localization is explicit processed work, never a raw rewrite.

```text
python -m validation.m1_clock_mapping --event-plan path/to/sync-events.json --output path/to/clock-mapping-report.json --verify-raw
```

Raw streams are read only for hash verification. Reports retain per-node/epoch and
pairwise held-out p50/p95/p99/max, per-event uncertainty, resolution and guard.
The implementation records fit_time_source=device_time_us,
host_arrival_used_for_fit=false, resampling=none and raw_data_modified=false.
A physical pilot does not replace the uninterrupted 30-minute bench; this optional
reference study is not a reason to reopen frozen hardware.
