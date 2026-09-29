# Synchronization Protocol — KineIMU Shoulder

M1 maps thorax and upper-arm sample clocks to one timeline.
Future physical-reference studies may map that timeline to video or motion capture.
Concurrent USB arrival or a common start command does not establish sample synchronization.

Preserve device timestamps, sample/packet counters, reset/wrap markers, host monotonic reception times
and clock domains. The packet/session fields are frozen for M1 in
`protocols/M1_ACQUISITION_CONTRACT.md`; numerical gates are predeclared in
`protocols/M1_TIMING_BUDGET.md`.

## M1 candidates

Start with one XIAO nRF52840 Sense over USB-C for sample-clock and raw-capture bring-up.
The two-node M1 transport is BLE-to-PC; USB debug output may remain available during
development but is not the claimed wireless synchronization mechanism.
Repeated common events while both nodes are rigidly co-mounted on a bench fixture can estimate
offset/rate mismatch. Motion of separately worn segments is not a common-motion clock reference.
The concrete event layout, localization/provenance fields and physical pilot procedure are in
[`protocols/M1_CLOCK_MAPPING_FIXTURE.md`](protocols/M1_CLOCK_MAPPING_FIXTURE.md); its event-plan
annotations are validation artifacts and do not change the frozen acquisition packet/schema.
Compare verified shared electrical trigger only after board routing/voltage review, or two-way
timestamp exchange with measured asymmetry. BLE is the current acquisition transport; connection timing
alone does not demonstrate synchronized sampling.

Use t_common = a_i * t_device_i + b_i per node and uninterrupted clock epoch.
Record method, fit interval, residuals, uncertainty and drift; evaluate held-out events.
Include beginning/intermediate/end events over intended duration; detect nonlinear drift, resets,
wraparound, out-of-order packets and missing intervals. Do not fit across resets.
Apply clock mappings in processed data; preserve raw clocks/bytes.

The M1 BLE clock characteristic records host send/receive callback times and device receive/indication-
queue times in a CRC-protected transaction. These timestamps expose round-trip behavior and may support
a candidate clock map, but callback/queue time is not radio-air time and path asymmetry remains an
uncertainty term. Rigid-fixture held-out common events remain the independent way to
establish sub-millisecond pairwise residuals, but ADR-008 permits M1 to report them as
not measured/inconclusive rather than treating a new fixture study as a hardware-freeze blocker.

## Reference/video

Record FPS (actual frame times for variable-rate video), event description, reference frame,
matched IMU event, offset/rate mapping, localization uncertainty, annotation version and resolution.
Include late events. Tapping one worn segment does not necessarily excite both IMUs simultaneously;
record independent establishment of the common timeline.
No timing/angle claim beyond reference resolution or annotation uncertainty.

## Report

Per node: actual rate, interval distribution, jitter, sample/packet loss and QC.
Pair: usable overlap, offset, relative drift, residual quantiles/max, held-out errors,
uncertainty, duration and transport configuration.
Pass thresholds are engineering budgets, not clinical standards. The 30-minute M1 stability
result uses the acquisition rate/loss/overlap/reset limits. Pairwise residual thresholds apply
only when an independently supported mapping artifact exists; otherwise report `not measured`
or `inconclusive` and carry the limitation into downstream analysis.
