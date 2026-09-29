# M1 BLE Link-Count Cold-Start Precheck V4

Date: 2026-09-24 (Asia/Shanghai)

Status: **PRECHECK PLAN ONLY — NOT A CAUSAL THROUGHPUT EXPERIMENT**

## Purpose and interpretation

This bounded precheck repairs the V3 setup defect before any formal experiment.
V3 reused one firmware boot across four conditions. The firmware intentionally
keeps acquiring after BLE disconnect, so later conditions began in `streaming`
state with nonzero acquisition/drop counters and raw sample gaps. V3 remains
consumed and blocked; do not modify or rerun its root.

The single factor remains the number of active BLE links: one versus two. Use
the same Node A and compare a fresh-boot `a_only` capture with a fresh-boot
`dual_a_to_b` capture. The extra B link is the only condition change. The two
conditions use separate acquisition processes and separate empty output roots;
both boards must be reset to a new firmware boot before each process. Boot IDs,
status counters, and sample sequences prove the reset and clean acquisition
state. This is an instrumentation/manipulability gate only. Packet counts and
TX metrics from this two-condition precheck do not support or refute a
throughput cause.

The formal v2 parameter-request factor remains **INCONCLUSIVE and unidentifiable
on this Windows/adapter/firmware/board combination**: ON and OFF both ended at
15 ms / latency 0 / 420 ms, and parameter callbacks do not identify who
initiated an update. Do not repeat v2 or infer the initiator from callbacks.

## Locked source, hardware, and output roots

- Run this plan on branch `codex/m1-root-cause-decision` from its committed,
  clean tracked tree. The pre-acquisition config must bind the exact Git HEAD
  and hashes of this plan, both Python runners, firmware identity files, and
  all copied raw files.
- The V4-only experiment runner enables an experiment-side gate in
  `MatrixBleClient`: it decodes the pre-notify status read and blocks telemetry
  CCC enable unless the state is pristine `armed`, all locked counters are
  zero, both sequence fields are the never-produced sentinel, and the boot ID
  is outside the predeclared forbidden set. V3 and production recorder defaults
  do not enable this gate.
- Firmware source commit:
  `270911756c227a20feb18df71edad7ad4544aedb`.
- Seeed XIAO nRF52840 Sense (`xiao_ble/nrf52840/sense`), Zephyr v4.4.0,
  SDK 1.0.1, LSM6DS3TR-C at 104 Hz.
- Node A bootloader USB serial `0000000000000001`, hardware device ID
  `1`, BLE address `02:00:00:00:00:01`, image SHA-256
  `226B77FCEA1054022DA9F0E9884D3297245050A88156CE2EAD7A9177B4177380`.
- Node B bootloader USB serial `0000000000000002`, hardware device ID
  `2`, BLE address `02:00:00:00:00:02`, image SHA-256
  `6B38472B703D9B102767A1823BC34876EE24B0AA67AA328E346F1312B8525B32`.
- Both byte-identical generated build configs have SHA-256
  `0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69`.
- Keep the same Windows host and MediaTek Bluetooth adapter, instance
  `USB\VID_13D3&PID_3563&MI_00`, driver `oem134.inf` version `1.3.17.169`.
  Resolve application CDC `2FE3:0004` by board USB serial; COM numbers are not
  identities. Do not change host, adapter, firmware, public data format, the
  four-slot sample queue, eight ATT TX contexts, retry delay, or sensor setup.
- Condition roots, each of which must be absent before its one acquisition:
  - `<external-data>\kineimu_m1_root_cause_precheck_20260924_01_a_only`
  - `<external-data>\kineimu_m1_root_cause_precheck_20260924_02_dual_a_to_b`
- Store each independent report outside its corresponding raw root. A paired
  report must also be outside both roots. A root is consumed as soon as it is
  created, including a failed or partial run. Never replace or supplement a
  condition.

## Fixed conditions and execution

| Order | Condition | Active BLE links | Connection order | Output root |
|---:|---|---:|---|---|
| 1 | `a_only` | 1 | A | `..._01_a_only` |
| 2 | `dual_a_to_b` | 2 | A then B | `..._02_dual_a_to_b` |

For both acquisitions, keep peripheral parameter requests OFF, the complete
10-second firmware-connected-event-relative parameter observation, MTU 127,
and the exact 15.000-second recorder-ready capture. Complete both host and
firmware disconnect evidence and acknowledged OFF cleanup. No second BLE
condition may run in the same firmware boot.

Before each condition, physically reset both existing boards without flashing
or changing hardware. Re-resolve their application CDC identity by USB serial.
For the first condition, run
`python -m experiments.m1_ble_link_precheck acquire --plan-version v4 --condition a_only`
and independently audit its root before proceeding. After its disconnect and
OFF cleanup pass, physically reset both boards, then run
`python -m experiments.m1_ble_link_precheck acquire --plan-version v4 --condition dual_a_to_b --prior-root <external-data>\kineimu_m1_root_cause_precheck_20260924_01_a_only`.
The second command recomputes the first root's audit from its raw inputs and
refuses to begin unless it passes. Then run the paired independent audit with
`python -m experiments.m1_ble_link_precheck audit-pair --output-json <external-data>\kineimu_m1_root_cause_precheck_20260924_pair_audit.json`.
Every audit output must stay outside both condition roots and must not replace
an existing file. If either process, audit, reset, or identity gate fails, stop
and preserve the consumed root(s).

The acquisition must be stopped before streaming if the pre-notify BLE status
does not show a pristine `armed` state, zero sample/packet/FIFO/queue/drop/TX
backpressure/high-water counters, a valid boot ID, and never-produced sample
and packet sequence sentinels. The independent raw audit must prove the status
read precedes telemetry enable in the shared time domain; any stale-start
condition blocks the pair. For the pair, Node A boot IDs must differ from one
another and from V3 Node A boot ID
`4610435006230911040`; dual-run Node B must differ from V3 Node B boot ID
`9200877888179811312`. This demonstrates a fresh firmware boot per condition.

The schedule is fixed and attempted once in the stated order. If the A-only
condition fails, retain and audit it, then stop; do not run dual. If the dual
condition fails, retain its partial output and stop. No condition may be
replaced or rerun. Reset both boards before the second condition only after the
first run's disconnect/OFF cleanup is confirmed and its output manifest is
written.

## Evidence gates

Both condition roots must independently pass every gate:

1. **Lock and identity:** exact plan SHA/copy, code HEAD/source hashes, board
   serial and application CDC VID/PID, firmware source/image/config hashes,
   same host/controller/driver, BLE hardware IDs, runtime identity and MTU 127.
2. **Cold-start freshness:** one pre-notify status read for the active
   connection generation; `armed`; all locked acquisition, sample-loss, TX
   backpressure and high-water counters zero; valid boot ID; never-produced
   sequence sentinels. Node A has a different boot ID in the two roots; V3
   boot IDs are rejected. A mismatch blocks before telemetry capture.
3. **Manipulated link state:** A-only proves exactly one active A link. Dual
   A→B proves both firmware connection events in order and concurrent links
   throughout the full 15.000-second capture. Both use Node A.
4. **Window and per-generation evidence:** complete firmware connection and
   parameter events; exact shared 15.000-second start/deadline; each admitted
   host callback records its timing; exact, unsaturated TX snapshots for every
   active connection generation; status and notifications are tied to those
   generations.
5. **Raw integrity:** nonempty raw CDC, KIMU stream, and sidecar; independently
   decoded packet count matches notifications; sample and packet sequence
   gaps, CRC, decode, framing and node-ID errors are zero; no invalid sidecar
   lines.
6. **Cleanup and hashes:** host and firmware disconnect complete; both nodes
   finish in acknowledged OFF state; a complete per-root SHA-256 manifest has
   no missing, mismatched, duplicate or unlisted files. Independent audit
   hashes raw inputs before/after and confirms they are unchanged without
   reading any prior audit report.
7. **Pair gate:** both independent condition audits pass; Node A boot IDs are
   distinct from each other and V3; source/firmware/config/host/controller and
   Node A identity match across roots; one condition has one active link and
   the other has two.

Passing the pair gate permits drafting a separate balanced formal plan with
both dual connection orders and same-block single-node controls. It does not
establish a transport effect or a causal bottleneck. A failed gate is
**BLOCKED**; a missing contrast, raw integrity issue, or incomplete diagnostic
is **INCONCLUSIVE** for any affected condition. No outcome from this precheck
may be labeled Supported / Not supported for root cause.

## Stop and authorization boundaries

Stop after any source, identity, clean-start, capture, TX, cleanup, or integrity
gate failure. Preserve all partial output and the per-root manifest. Do not
change firmware, add a CDC reset command, flash, change the public format,
expand BLE queue/ATT contexts, or modify the sensor setup to recover. Do not
start a formal matrix unless the pair audit passes. Do not run the 30-minute
bench, freeze hardware, start M2, push, merge, or create a PR.
