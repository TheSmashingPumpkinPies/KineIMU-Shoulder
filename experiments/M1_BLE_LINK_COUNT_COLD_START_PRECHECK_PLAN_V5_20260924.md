# M1 BLE Link-Count Cold-Start Precheck V5

Date: 2026-09-24 (Asia/Shanghai)

Status: **PRECHECK PLAN ONLY — NOT A CAUSAL THROUGHPUT EXPERIMENT**

## Purpose

V4 is consumed and blocked. Its A-only run found Node A at the locked BLE
address and firmware observed a connection 14.843 seconds after host connect
start, but Windows/Bleak connect/GATT setup did not return before the locked
15-second timeout. The raw root and independent BLOCKED audit remain immutable.
The 24 V2 raw connect-total durations were 0.544–0.953 seconds (median 0.628
seconds), so the V4 setup duration is an outlier observation.

V5 keeps the single manipulable factor **active BLE link count: one versus
two** and extends only the common host connect/GATT setup allowance from 15 to
30 seconds. Both conditions use the same 30-second deadline. The firmware,
board pair, host/adapter, request mode, BLE settings, ten-second
firmware-connected-event-relative observation, MTU requirement and exact
15-second capture remain fixed. This precheck tests whether the instrument can
realize and audit the link-count contrast; it does not establish a throughput
effect or causal root cause.

The historical V2 local 15 ms request versus OFF factor remains
**INCONCLUSIVE and unidentifiable** on this Windows/adapter/firmware/board
combination. All ON and OFF links ended at `15 ms / 0 / 420 ms`, and firmware
parameter callbacks do not identify who initiated an update. Do not repeat or
reinterpret V2.

## Locked source, hardware and roots

- Acquire only from a clean committed tree on branch
  `codex/m1-root-cause-decision`. The root config must bind the exact Git HEAD,
  plan SHA, host runner hashes, firmware source/image/config hashes, board IDs,
  USB serials, adapter identity and driver version.
- Plan V5 uses a 30.0-second host connect/GATT setup timeout for each condition.
  The independent audit must read the per-run timeout and confirm it matches
  this plan. The existing five-second scan bound, ten-second connected-event
  observation and exact 15.000-second capture stay unchanged.
- Before telemetry CCC enable, require the V4 pristine-start gate: status
  `armed`, all acquisition/drop/backpressure/high-water counters zero,
  never-produced sample and packet sequence sentinels, valid node/boot
  identity, and a boot ID outside the V3 set and prior V5 A-only boot ID.
- Keep the same Seeed XIAO nRF52840 Sense boards, firmware, host and MediaTek
  Bluetooth adapter recorded in the V4 plan. Resolve application CDC by USB
  serial. Do not flash, replace hardware, change the host/adapter, public
  format, four-slot sample queue, eight ATT TX contexts, retry policy or sensor
  setup.
- Condition roots, each absent before its single acquisition:
  - `<external-data>\kineimu_m1_root_cause_precheck_20260924_v5_01_a_only`
  - `<external-data>\kineimu_m1_root_cause_precheck_20260924_v5_02_dual_a_to_b`
- Independent outputs, also absent before use and outside both raw roots:
  - `<external-data>\kineimu_m1_root_cause_precheck_20260924_v5_01_a_only_independent.json`
  - `<external-data>\kineimu_m1_root_cause_precheck_20260924_v5_pair_audit.json`

## Fixed schedule and acquisition

| Order | Condition | Active links | Connection order | Request mode |
|---:|---|---:|---|---|
| 1 | `a_only` | 1 | A | OFF |
| 2 | `dual_a_to_b` | 2 | A then B | OFF |

The same Node A is measured in both conditions. Separate processes and fresh
firmware boots prevent V3's disconnected-but-still-sampling carryover. The
precheck order is fixed because the dual runner must independently audit the
A-only root and forbid reuse of its Node A boot ID; this is not the formal
experiment order. No condition may be replaced or rerun.

Before each condition, physically reset both existing boards without flashing
or changing hardware, then resolve CDC identities by USB serial. Run the
one-time command for A-only and independently audit its raw root. Only after
that audit passes, reset both boards again and run dual A→B using the A-only
root as `--prior-root`; the runner recomputes the A-only audit before starting.
Then run the paired independent audit. If acquisition, identity, reset, audit,
integrity or cleanup fails, preserve the consumed output and stop.

The exact acquisition commands are:

```powershell
python -m experiments.m1_ble_link_precheck acquire --plan-version v5 --condition a_only
python -m experiments.m1_ble_link_precheck audit --root-dir <external-data>\kineimu_m1_root_cause_precheck_20260924_v5_01_a_only --output-json <external-data>\kineimu_m1_root_cause_precheck_20260924_v5_01_a_only_independent.json
python -m experiments.m1_ble_link_precheck acquire --plan-version v5 --condition dual_a_to_b --prior-root <external-data>\kineimu_m1_root_cause_precheck_20260924_v5_01_a_only
python -m experiments.m1_ble_link_precheck audit-pair --plan-version v5 --output-json <external-data>\kineimu_m1_root_cause_precheck_20260924_v5_pair_audit.json
```

## Evidence and stop gates

Each root must independently prove: matching plan and exact source hashes;
same adapter/firmware/board identity; correct CDC VID/PID and serial; one
passed pre-notify pristine-status gate for each active node; full firmware
connection and parameter events; 30-second connect/GATT timeout recorded in
config; MTU 127 and correct GATT identity; exact shared 15.000-second
recorder-ready boundary; exact per-generation TX snapshots; nonempty CDC, KIMU
and event raw evidence; matching packet/notify counts; zero sequence gaps, CRC,
decode, framing or node-ID errors; completed host and firmware disconnect;
acknowledged OFF cleanup; and a valid complete SHA-256 manifest.

The paired audit independently recalculates both roots from immutable raw CDC,
KIMU, event sidecars and config/result files; verifies manifests and before/after
raw hashes; checks the two distinct fresh Node A boot IDs; and confirms exactly
one versus two concurrent active links over the full shared capture. It must
not use earlier audit JSON as input.

Both single-root audits and the pair audit must pass before drafting a separate
balanced formal plan with both dual connection orders and same-block single-node
controls. No outcome from V5 is Supported/Not supported for historical root
cause. Any missing contrast, timeout, missing boundary, incomplete TX
generation, integrity discrepancy or cleanup error is **BLOCKED** for the
precheck and **INCONCLUSIVE** for causal throughput attribution.

Do not start a formal matrix unless all V5 precheck gates pass. Do not repair
firmware on this precheck evidence. Do not run the 30-minute M1 bench, freeze
hardware, start M2, push, merge or create a PR.
