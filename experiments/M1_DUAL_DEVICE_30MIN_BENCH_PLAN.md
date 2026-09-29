# M1 Dual-Device 30-Minute Bench Plan

Status: predeclared and ready; **not yet executed**.

Purpose: characterize uninterrupted physical acquisition stability for the two identified
XIAO nRF52840 Sense nodes after the completion-window dual-order retest passes. This is not
a human, wearable, shoulder-angle or clinical validation experiment.

## Preconditions

1. The multi-context completion-window images have passed the separate two-block,
   both-link-order retest.
2. Node A/B Board-ID, bootloader serial, BLE address, hardware device ID, firmware commit
   and image SHA-256 are recorded immediately before the run.
3. Both boards are externally powered and stationary on the bench. No battery, enclosure,
   body mounting or deliberate motion is required.
4. The output directory is new, external to Git and empty. Existing raw artifacts remain immutable.
5. CDC ports and explicit BLE addresses are verified; scan order is not used for identity.

## Fixed run profile

- Mode: `bench`
- Scheduled duration: `1800 s`
- Configured sensor ODR: `104 Hz` accelerometer and gyroscope
- Packet batch size: `4` samples
- Expected scheduled samples per node: `187200`
- Expected scheduled packets per node: `46800`
- Artificial host callback delay: `0 ms`
- Planned disconnect stimulus: none
- Recovery delay setting: recorder default `0.25 s` (unused unless an unplanned disconnect occurs)
- Raw policy: append-only; no repair, filtering, interpolation or resampling

The expected counts are design expectations (`104 s⁻¹ × 1800 s`, divided by four samples
per packet), not observed results. Startup/teardown and device timestamp span are reported
separately; a count difference is investigated rather than silently labeled loss.

## Capture command

```powershell
uv run --frozen python experiments/m1_transport_experiment.py `
  --mode bench `
  --output-dir <NEW_EXTERNAL_RUN_DIR> `
  --session-id <SESSION_ID> `
  --node-a-address <BLE_ADDRESS_A> `
  --node-b-address <BLE_ADDRESS_B> `
  --expected-node-a-device-id <DEVICE_ID_A> `
  --expected-node-b-device-id <DEVICE_ID_B> `
  --cdc-port-a COM5 `
  --cdc-port-b COM8 `
  --predeclared-plan experiments/M1_DUAL_DEVICE_30MIN_BENCH_PLAN.md `
  --seconds 1800 `
  --callback-delay-ms 0 `
  --notes "uninterrupted dual-device M1 bench characterization"
```

Do not reuse an output directory after a failed attempt. Retain failed attempts as evidence
and create a new directory for any retry.

## Read-only audit commands

```powershell
uv run --frozen python experiments/m1_transport_audit.py --run-dir <RUN_DIR>
uv run --frozen python experiments/m1_bench_summary.py --run-dir <RUN_DIR>
```

The first audit reconciles raw sequences, packet flags, status counters, CDC diagnostics,
connections and hashes. The second writes the compact `summary.json` with scheduled/configured
values, effective device-time rate, expected/received counts, sequence loss rate, malformed
and framing counts, maximum device-sample and host-inter-packet gaps, disconnect/reconnect
counts, monotonicity and integrity hashes.

## Required report fields

- duration, device count, firmware/software commit and image hashes;
- configured ODR/ranges/filter snapshot and negotiated transport configuration;
- expected and received packet/sample counts;
- effective per-epoch sample rate and device timestamp interval statistics;
- packet/sample gaps, loss attribution, malformed/framing errors and maximum gaps;
- disconnect count, reconnect events, resets/clock epochs and all host/device errors;
- raw/event/CDC/config/report hashes and manifest verification;
- pairwise offset/drift/synchronization result linked from a separate clock-mapping
  artifact, or the explicit status `not measured`/`inconclusive` with reason.

Apply the acquisition stability limits in `protocols/M1_TIMING_BUDGET.md`. Pairwise
residual limits apply only when independently measurable. Do not mark this plan passed
until the physical run and audits exist.
