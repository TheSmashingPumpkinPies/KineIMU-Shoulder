# M1 rigid-fixture clock-mapping pilot protocol

Status: implementation protocol for M1 synchronization validation. This is a
bench timing experiment only; it does not estimate orientation, anatomical
alignment, shoulder angles, or rehabilitation metrics.

This protocol implements the requirements in [`SYNC_PROTOCOL.md`](../SYNC_PROTOCOL.md),
[`M1_TIMING_BUDGET.md`](M1_TIMING_BUDGET.md), and [`DATA_FORMAT.md`](../DATA_FORMAT.md).
The event-plan JSON shape is versioned by
[`m1-sync-event-plan-0.1.schema.json`](schemas/m1-sync-event-plan-0.1.schema.json).

## Fixture and repeated common event

Mount Node A and Node B to the same rigid plate or rail with their sensing
faces and axes fixed. The fixture must prevent relative translation, rotation,
strap motion and cable pull during the run. This is a temporary bench fixture,
not the wearable thorax/upper-arm mounting protocol. Record the fixture ID,
mounting orientation, attachment method, node IDs, firmware/configuration and
any visible looseness before collection.

Use one repeatable mechanical stimulus at a fixed point on the rigid fixture:
for example, a calibrated solenoid/pendulum striker or a guided plunger with a
repeatable release. The stimulus must excite both rigidly mounted IMUs. Do not
tap one independently mounted sensor and assume the other sensor saw the same
event.

Use an independent common-time reference for the event onset/peak, such as a
calibrated optical, acoustic or other reference logger with recorded sample
times. A BLE callback or host arrival timestamp is not a common event
reference. A shared electrical trigger requires a separate routing and voltage
review before it is used. The common-time origin may be arbitrary, but it must
be the same reference clock for all event IDs in one uninterrupted experiment.

## Predeclared event split

Create the event plan before reviewing the captured residuals. The minimum
six-event layout is:

| Event ID | Placement | Use | Purpose |
|---|---|---|---|
| E01 | beginning | fit | early offset/rate anchor |
| E02 | beginning | held_out | independent early check |
| E03 | middle | fit | mid-run rate anchor |
| E04 | middle | held_out | independent mid-run check |
| E05 | end | fit | late-run rate anchor |
| E06 | end | held_out | independent late-run check |

“Beginning”, “middle” and “end” refer to the intended recording interval and
must be recorded in the plan. For a reset or unproven discontinuity, do not
bridge the interval: increment the device `clock_epoch`, create a new mapping
and collect a complete fit/held-out event set for that epoch. Every epoch that
is evaluated needs at least two fit events and one held-out event; the standard
pilot layout gives three of each at all three placements.

The validation code rejects duplicate event IDs, missing A/B observations,
missing phase coverage, missing fit support for an epoch, or any overlap
between fit and held-out IDs. Only `fit` events enter a node/epoch fit. Only
`held_out` events enter residual statistics.

## Event annotation and resolution

For every event, store the independent reference time and, separately for each
node, the local device timestamp selected from the immutable raw stream. The
annotation records:

- event ID, beginning/middle/end phase and fit/held-out role;
- common reference method, resolution and standard uncertainty;
- node-local localization method, resolution and standard uncertainty;
- node ID, `clock_epoch`, device timestamp and optional sample sequence;
- the SHA-256 of the raw stream used for that observation.

The initial auditable method may be a documented raw-sample peak/edge
annotation. Its resolution is the smallest time increment that the method can
actually distinguish; it is not the nominal sample rate written in metadata.
At roughly 100 Hz, a nearest-sample annotation is normally several
milliseconds wide and will therefore be `inconclusive` for the 1.0/1.5 ms M1
gate. A template or sub-sample localization method is allowed only when its
resolution and uncertainty are independently justified and recorded. Any
interpolation used to localize an event is a derived/processed calculation; it
must not rewrite or replace the raw `.kimu` stream.

For a declared resolution treated as a uniform bin width, the default standard
uncertainty is `resolution_us / sqrt(12)`. If a different distribution is used,
record that method in the annotation and provide its standard uncertainty.
The report uses coverage factor `k = 2` for the expanded uncertainty. The
decision-resolution guard is the larger of the maximum expanded uncertainty
and the conservative combined reference/localization resolution. If it is greater than or equal
to the 500 µs separation between the predeclared 1.0 ms p95 and 1.5 ms maximum
limits, the result is `inconclusive`, even when the point residuals are small.

## Mapping and report

For every `(node_id, clock_epoch)`, validation fits the centered numerical
equivalent of:

```text
t_common_us = a_i * t_device_us + b_i
```

The centered calculation is only a numerical-conditioning device; the report
stores the uncentered `a_i` and `b_i`. It also stores the fit event IDs, device
and common fit windows, coefficient covariance, reference-time offset and
`(a_i - 1) * 1e6` relative drift in ppm. For a single A/B epoch pair it stores
the B-minus-A device offset at a common reference time and
`(a_B / a_A - 1) * 1e6` relative drift. Multiple epoch pairs are retained
individually rather than collapsed into one unsupported number.

The processed report stores p50, p95, p99 and maximum absolute residuals for
each node/epoch and for the A/B pair, plus per-event standard and expanded
uncertainties, resolution and the decision guard. The pairwise engineering
decision is `pass` only when the resolution guard is sufficient, held-out p95
is at most 1.0 ms and held-out maximum is at most 1.5 ms. It is `fail` when a
limit is exceeded with sufficient resolution, and `inconclusive` when the
event evidence cannot distinguish the two limits.

The host arrival times in BLE transport sidecars remain diagnostic only. They
are not loaded by `validation.m1_clock_mapping` and cannot affect the fit.
The report explicitly records `fit_time_source=device_time_us`,
`host_arrival_used_for_fit=false`, `resampling=none`, and
`raw_data_modified=false`.

## Reproduction

Run the standalone validation command after a capture and an independently
reviewed event annotation plan:

```text
python -m validation.m1_clock_mapping \
  --event-plan path/to/session/sync-events.json \
  --output path/to/session/processed/clock-mapping-report.json \
  --verify-raw
```

The command reads the two raw streams only to verify their declared hashes.
The event plan and report are processed/annotation artifacts; neither command
rewrites raw bytes. The checked-in synthetic known-offset/drift TDD artifact is
in [`experiments/m1_clock_mapping_synthetic_20260915`](../experiments/m1_clock_mapping_synthetic_20260915/).

The physical pilot is not a 30-minute M1 acceptance run. A formal acceptance
run must still satisfy the duration, loss, overlap, reset and timing inputs in
[`M1_TIMING_BUDGET.md`](M1_TIMING_BUDGET.md), with all event and raw hashes
retained.
