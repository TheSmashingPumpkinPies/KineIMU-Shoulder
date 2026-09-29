# M1 BLE Link-Count Cold-Start Precheck V6

Date: 2026-09-24 (Asia/Shanghai)

Status: **PRECHECK PLAN ONLY — NOT A CAUSAL THROUGHPUT EXPERIMENT**

## Purpose and V5 forensic correction

V5 is consumed. Its locked paired audit remains **BLOCKED** because the dual
root has packet/sample sequence gaps and the V5 per-generation TX gate is not
met. Do not change the V5 plan, raw roots, manifest, or independent report.

Raw V5 CDC and event records establish one physical connect and one physical
disconnect for each node. The firmware `generation` field is a telemetry queue
epoch: disabling the telemetry CCC and disconnect cleanup can advance it
without a BLE reconnect. TX counters are cumulative across those queue epochs.
The V5 segment report grouped them by epoch and therefore omitted counter
changes between the last snapshot bearing one epoch label and the first
snapshot bearing the next. The snapshots do not identify which side of that
transition performed those changes. V6 reports the terminal cumulative
counters from one fresh firmware boot as physical-connection-lifetime totals,
retains every between-epoch delta as unattributed, and names queue epochs as
queue epochs. It does not reinterpret V5's BLOCKED decision.

V5 measured real dual-run loss (Node A: 82 packet and 331 sample sequence
gaps; Node B: 7 packet and 28 sample sequence gaps). These are outcomes to
measure and preserve in V6, rather than reasons to discard otherwise intact
raw evidence. CRC, decode, framing and wrong-node errors remain integrity
failures. V6 only checks that packet/sample gap counts are present; it does not
require them to be zero.

V6 has one manipulable factor: **active BLE link count, one versus two**. It
checks that the Windows host can realize the contrast and that every required
evidence stream is auditable. It cannot establish a causal throughput effect
because its fixed A-only then A→B order is a precheck schedule, not the
balanced formal design.

The historical V2 local 15 ms request versus OFF factor remains
**INCONCLUSIVE and unidentifiable** on this Windows/adapter/firmware/board
combination. All ON and OFF links ended at `15 ms / 0 / 420 ms`; firmware
parameter callbacks do not identify who initiated an update. Do not repeat or
reinterpret V2.

## Locked source, hardware and roots

- Acquire only from the clean, committed `codex/m1-root-cause-decision` tree.
  Each root config records the exact acquisition Git HEAD, plan SHA, host and
  runner hashes, firmware source/image/config hashes, board IDs, USB serials,
  BLE identities and adapter/driver identity.
- V6 uses a 30.0-second host connect/GATT setup allowance for both conditions.
  The existing five-second scan bound, ten-second
  firmware-connected-event-relative observation, and exact 15.000-second
  capture remain fixed.
- Before telemetry CCC enable, require the existing pristine-start status
  gate: status `armed`, all acquisition/drop/backpressure/high-water counters
  zero, never-produced sample and packet sequence sentinels, and valid node and
  boot identity. Both boards must be physically reset before each condition;
  the dual run must use a Node A boot ID distinct from the A-only boot ID.
- Keep the same Seeed XIAO nRF52840 Sense boards, firmware, Windows host and
  MediaTek Bluetooth adapter recorded in V5. Resolve application CDC by USB
  serial. Do not flash or replace hardware, change the host/adapter, public
  format, four-slot sample queue, eight ATT TX contexts, retry policy or sensor
  setup.
- Locked firmware source commit:
  `270911756c227a20feb18df71edad7ad4544aedb`.
- Locked image SHA-256: Node A
  `226B77FCEA1054022DA9F0E9884D3297245050A88156CE2EAD7A9177B4177380`; Node B
  `6B38472B703D9B102767A1823BC34876EE24B0AA67AA328E346F1312B8525B32`.
- Locked build-config SHA-256 for both boards:
  `0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69`.
- Locked hardware IDs: A `1`, B
  `2`. Locked USB serials: A `0000000000000001`, B
  `0000000000000002`. Locked BLE addresses: A `02:00:00:00:00:01`, B
  `02:00:00:00:00:02`. Expected MTU is 127.
- Each absent root is consumed at most once:
  - `<external-data>\kineimu_m1_root_cause_precheck_20260924_v6_01_a_only`
  - `<external-data>\kineimu_m1_root_cause_precheck_20260924_v6_02_dual_a_to_b`
- Independent outputs must be absent and outside both raw roots:
  - `<external-data>\kineimu_m1_root_cause_precheck_20260924_v6_01_a_only_independent.json`
  - `<external-data>\kineimu_m1_root_cause_precheck_20260924_v6_pair_audit.json`

## Fixed schedule and acquisition

| Order | Condition | Active links | Connection order | Request mode |
|---:|---|---:|---|---|
| 1 | `a_only` | 1 | A | OFF |
| 2 | `dual_a_to_b` | 2 | A then B | OFF |

The same Node A appears in both roots. The roots are separate acquisitions and
both require new firmware boots. The dual run may start only after an
independent A-only raw audit passes; its runner recomputes that audit and
forbids reusing Node A's boot ID. This precheck order is not the later formal
experiment order. No failed or partial condition may be replaced or rerun.

Before each condition, physically reset both existing boards without flashing
or changing hardware, then resolve CDC identities by USB serial. Acquire
A-only, audit its raw root, reset both boards again, then acquire dual A→B
using the A-only root as `--prior-root`. Run the paired audit last. Preserve
every raw file and manifest if any acquisition, identity, freshness, audit,
integrity or cleanup gate fails.

```powershell
python -m experiments.m1_ble_link_precheck acquire --plan-version v6 --condition a_only
python -m experiments.m1_ble_link_precheck audit --root-dir <external-data>\kineimu_m1_root_cause_precheck_20260924_v6_01_a_only --output-json <external-data>\kineimu_m1_root_cause_precheck_20260924_v6_01_a_only_independent.json
python -m experiments.m1_ble_link_precheck acquire --plan-version v6 --condition dual_a_to_b --prior-root <external-data>\kineimu_m1_root_cause_precheck_20260924_v6_01_a_only
python -m experiments.m1_ble_link_precheck audit-pair --plan-version v6 --output-json <external-data>\kineimu_m1_root_cause_precheck_20260924_v6_pair_audit.json
```

## Evidence and stop gates

Each condition must independently prove: this plan SHA and exact clean Git
HEAD; unchanged firmware/image/build hashes and physical identities; expected
application CDC interface; pristine boot before telemetry; exactly one
firmware connect event per active node in the declared order; full parameter
and link event streams; 30-second connect/GATT allowance; MTU 127 and GATT
identity; exact shared 15.000-second capture markers; complete event, CDC and
KIMU streams; exact recorder/raw/notify packet counts; host and firmware
disconnect; acknowledged OFF cleanup; and a valid complete SHA-256 manifest.

TX diagnostics must contain at least two full, parseable, unsaturated snapshots
from the gated firmware boot, with monotonic lifetime counters and a terminal
snapshot proving no owned or in-flight notification. Report physical connection
totals from those cumulative boot-lifetime counters. Preserve queue-epoch
segments and calculate every cross-epoch counter jump between adjacent raw
snapshots, explicitly leaving its queue-epoch attribution unresolved. Do not
call a queue epoch a physical BLE connection and do not treat a CCC disable or
generation change as a reconnect. Record packet/sample sequence gaps,
duplicates and reorder counts as measured outcomes. CRC, decode, framing,
wrong-node, missing-boundary, missing-counter, saturated-counter, raw-hash,
identity, disconnect or cleanup failures block the precheck.

The paired audit independently recomputes both roots from raw CDC, KIMU,
sidecars, config and result files; verifies each manifest and before/after raw
hash; checks distinct fresh Node A boot IDs; and confirms one versus two active
links overlap for the full shared capture. It must not use prior audit JSON as
input. Both single-root audits and the pair audit must pass before drafting a
separate balanced formal plan containing both dual connection orders and
same-block single-node controls. A V6 precheck pass permits formal-plan
drafting only; it is not causal support, a repair, or bench eligibility.

Stop after any failed or incomplete root, any invalid/incomplete raw evidence,
any identity/freshness/cleanup failure, or any failure of the A-only prerequisite
before dual. Keep the consumed root and report its exact BLOCKED reason. If
both conditions pass, stop without beginning the formal experiment until its
own plan and code are reviewed and locked. Do not repair firmware from this
precheck, run the 30-minute M1 bench, freeze hardware, start M2, push, merge or
create a PR.
