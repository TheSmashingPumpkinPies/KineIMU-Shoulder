# M1 BLE Connection-Parameter Root-Cause Matrix — Evidence Report

Date: 2026-09-21 (Asia/Shanghai)
Disposition: **inconclusive**
Experiment root: `<external-data>/kineimu_m1_ble_connparam_rootcause_20260921_01`

## Decision

The locked parameter manipulation was not realized. All eight USB CDC mode-control
writes timed out; none was acknowledged or applied. In all 12 planned ON node-run
links, the raw firmware log records `mode=OFF`, `call=0`, `api_rc=NA`; zero of
those links reports the requested `15,000 us / 0 / 420,000 us` tuple. The locked
plan therefore requires **inconclusive**. Throughput or diagnostic differences
between planned blocks cannot establish or reject the connection-parameter
hypothesis, and no root cause is assigned.

The full 16-run schedule was attempted once, in order, without replacement runs
or mid-run parameter edits. Node A produced zero valid packets in all 12 active
node captures; Node B produced 3,416 valid packets across its 12 active captures.
That incomplete data is a second reason the result cannot be elevated beyond
inconclusive.

## Locked plan and execution

The plan was committed before acquisition as
`d7337ab0b12740943847728451a3a1acf8619031` and remained unchanged. Its SHA-256 is
`6B295C3C5CC5B2B9E06623D9E28B9A7DD70F342085DA66D29D3ABBF847B9D2D4`. The
predeclared four-block order, 10 s settle, 15 s capture, 2 s inter-run rest, and
5 s connection-attempt timeout are recorded in the copied plan and
`matrix_config.json`. The result records 16/16 attempts and an exact match to
the locked schedule. Every run connected without a run-level error; the eight
mode-control write timeouts are separately preserved in `matrix_result.json`.

The output root was absent before the runner created it. The runner resolved
application CDC ports from USB serial after re-enumeration: Node A
`0000000000000001` → COM5; Node B `0000000000000002` → COM8 (both VID:PID
`2FE3:0004`).

| Run | Block / requested mode | Condition / connection order | A packets | B packets | B dual / same-block single | First / second |
|---:|---|---|---:|---:|---:|---:|
| 1 | 1 / OFF | `a_only` | 0 | — | — | — |
| 2 | 1 / OFF | `b_only` | — | 397 | — | — |
| 3 | 1 / OFF | `dual_b_to_a` (B → A) | 0 | 51 | 0.1285 | n/a (A = 0) |
| 4 | 1 / OFF | `dual_a_to_b` (A → B) | 0 | 405 | 1.0202 | 0.0000 |
| 5 | 2 / ON | `b_only` | — | 402 | — | — |
| 6 | 2 / ON | `dual_a_to_b` (A → B) | 0 | 406 | 1.0100 | 0.0000 |
| 7 | 2 / ON | `a_only` | 0 | — | — | — |
| 8 | 2 / ON | `dual_b_to_a` (B → A) | 0 | 51 | 0.1269 | n/a (A = 0) |
| 9 | 3 / ON | `dual_b_to_a` (B → A) | 0 | 46 | 0.1144 | n/a (A = 0) |
| 10 | 3 / ON | `a_only` | 0 | — | — | — |
| 11 | 3 / ON | `dual_a_to_b` (A → B) | 0 | 403 | 1.0025 | 0.0000 |
| 12 | 3 / ON | `b_only` | — | 402 | — | — |
| 13 | 4 / OFF | `dual_a_to_b` (A → B) | 0 | 402 | 0.9975 | 0.0000 |
| 14 | 4 / OFF | `dual_b_to_a` (B → A) | 0 | 48 | 0.1191 | n/a (A = 0) |
| 15 | 4 / OFF | `b_only` | — | 403 | — | — |
| 16 | 4 / OFF | `a_only` | 0 | — | — | — |

`B dual / same-block single` is B's valid packet count in the dual run divided
by B's `b_only` count in the same block. A's same-block single control was zero
in every block, so A dual/single ratios are undefined. First/second is undefined
for B → A because A, the second node, had zero packets. These are descriptive
observations under an unrealized manipulation, not treatment-effect evidence.

## Manipulation check

| Check | Observed |
|---|---:|
| Planned block mode-control operations acknowledged and applied | 0 / 8 |
| Mode-control errors | 8 × `SerialTimeoutException: Write timeout` |
| Planned ON node-run links | 12 |
| ON links logging a successful local ON request (`call=1`, `api_rc=0`) | 0 / 12 |
| ON links observing 15 ms / 0 / 420 ms | 0 / 12 |
| Planned OFF links logging no local request | 12 / 12 |
| OFF links with a final tuple different from the target | 12 / 12 |

Across the 24 active node-run CDC captures, the last observed tuple was
`40,000 us / 0 / 420,000 us`. The logged link-event tuple sequence was
`48,750 / 0 / 420,000`, `48,750 / 0 / 420,000`, `13,750 / 0 / 9,600,000`,
then `40,000 / 0 / 420,000 us`. All planned ON captures retained an OFF / no-call
request log. The plan's manipulation-validity gate is false.

## Independent throughput and diagnostic recomputation

`independent_recalculation.json` was computed directly from `matrix_result.json`,
each run's raw `.cdc.bin`, raw `.kimu`, and event sidecar; it did not use
`matrix_audit.json` as an input. The parser independently decoded the
length-prefixed KIMU records, checked node identity and packet integrity, counted
valid packets, and then calculated same-block and first/second ratios. For
diagnostics, it parsed `tx_diag` snapshots and calculated first-to-last counter
deltas within each boot / connection-generation segment.

### Node B TX diagnostic deltas

Counter columns below are first-to-last deltas from the raw CDC trace. `accepted`
is the successful notification-submission count; rates per notification
submission in the JSON use this denominator. Active-second rates use the planned
15 s window. `ILB` means the total is incomplete or a lower bound because at
least one observed segment has only one snapshot or otherwise lacks a complete
delta. The single `exact` row had complete deltas across its observed segments.

| Run | Planned mode / condition | B packets | Quality | Accepted | -ENOMEM | -EAGAIN | Retry calls | Full-window events | Wait (us) | Completed | Age p50 / p95 |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2 | OFF / `b_only` | 397 | ILB | 351 | 0 | 0 | 0 | 0 | 0 | 351 | <1 ms / <1 ms |
| 3 | OFF / `dual_b_to_a` | 51 | ILB | 49 | 1,356 | 0 | 1,356 | 33 | 13,184,099 | 48 | ≥100 ms / ≥100 ms |
| 4 | OFF / `dual_a_to_b` | 405 | ILB | 403 | 0 | 0 | 0 | 0 | 0 | 403 | <1 ms / <1 ms |
| 5 | ON / `b_only` | 402 | ILB | 389 | 0 | 0 | 0 | 0 | 0 | 389 | <1 ms / <1 ms |
| 6 | ON / `dual_a_to_b` | 406 | ILB | 400 | 0 | 0 | 0 | 0 | 0 | 400 | <1 ms / <1 ms |
| 8 | ON / `dual_b_to_a` | 51 | exact | 51 | 1,210 | 0 | 1,210 | 35 | 14,246,018 | 49 | ≥100 ms / ≥100 ms |
| 9 | ON / `dual_b_to_a` | 46 | ILB | 45 | 1,103 | 0 | 1,102 | 31 | 13,617,873 | 44 | ≥100 ms / ≥100 ms |
| 11 | ON / `dual_a_to_b` | 403 | ILB | 389 | 0 | 0 | 0 | 0 | 0 | 389 | <1 ms / <1 ms |
| 12 | ON / `b_only` | 402 | ILB | 376 | 0 | 0 | 0 | 0 | 0 | 376 | <1 ms / <1 ms |
| 13 | OFF / `dual_a_to_b` | 402 | ILB | 395 | 0 | 0 | 0 | 0 | 0 | 395 | <1 ms / <1 ms |
| 14 | OFF / `dual_b_to_a` | 48 | ILB | 47 | 1,440 | 0 | 1,440 | 31 | 13,830,278 | 44 | ≥100 ms / ≥100 ms |
| 15 | OFF / `b_only` | 403 | ILB | 395 | 0 | 0 | 0 | 0 | 0 | 395 | <1 ms / <1 ms |

The JSON also retains each segment's `calls`, all scalar deltas, parsed return
codes, completion-age histogram, mean age, per-second rates, per-submission
rates, snapshot count, and quality flag. In the 12 Node A active captures, valid
packet counts and observed TX submission/retry/drop deltas were zero.

### Integrity and loss observations

- Independently decoded raw valid-packet counts match both the runner counts and
  `notify` event-sidecar counts for all 24 active node-run streams.
- Total valid packets: A = 0; B = 3,416. B-only controls were 397, 402, 402,
  and 403 packets. B in B → A dual runs was 51, 51, 46, and 48; B in A → B dual
  runs was 405, 406, 403, and 402. This order difference is recorded only as
  observation; the requested parameter contrast was absent.
- Across the captured streams: 1,206 packet-sequence gaps and 31,491
  sample-sequence gaps; zero CRC errors, decode errors, and framing errors in
  both raw and event checks. The independent JSON has the per-run values.
- All 16 BLE run setups returned successfully, no run-level errors were
  recorded, and no run was replaced. The raw-input hashes were identical before
  and after independent recalculation.

### Audit-tool limitation

The existing `matrix_audit.json` and `MATRIX_REPORT.md` were preserved unchanged.
Their CDC fields show no snapshots / n/a because
`experiments/m1_ble_link_matrix_audit.py` looks up `node-a` / `node-b` in the
runner's CDC mapping, while `matrix_result.json` stores those keys as `A` / `B`
(`_node_audit`, lines 642–649). The independent calculation therefore reads the
raw per-run CDC files directly. No audit implementation or captured artifact
was edited to conceal this limitation.

## Hardware, firmware, and artifact provenance

Both boards were verified as Seeed XIAO nRF52840 Sense before flashing. Their
bootloader USB serial, COM port, UF2 volume, physical disk serial, and board
identity were cross-checked. Each board received the UF2 with its matching
recorded hash. The board `INFO_UF2.TXT` SHA-256 was
`78D580460BBEA1A33AC78BA3FF0858CF57EB01E858DB490B44BEC3127E4BD191` for both.

| Node | Node ID | USB serial | Before-flash mapping | UF2 SHA-256 | ELF SHA-256 |
|---|---:|---|---|---|---|
| A | 1 | `0000000000000001` | COM4 / E: / PhysicalDrive1 | `AF782EC0B0237D44A164338E58AAEDF2CE445F57BF101E4317D7DFCFEF0FBE64` | `E999E9A7E6FE91A7814252E1C31EDD36DEE6299D9B790B625D1DCF10B84F5EFA` |
| B | 2 | `0000000000000002` | COM7 / F: / PhysicalDrive2 | `3FEBE05637894405784BCE5C61621223F410063B39A19F3C6778B1DDE6F60557` | `3D9B5A7CFA1CD769EA9A674E143C8634EF9BDFE8B2400F0844D7D75A486203CE` |

| Provenance item | Value |
|---|---|
| Firmware source commit embedded in both images | `234131be3d6a26d9c6ca8d9c84e9b7f0974e1187` |
| Zephyr / SDK / target | v4.4.0 / 1.0.1 / `xiao_ble/nrf52840/sense` |
| Shared A/B `.config` SHA-256 (57,969 bytes) | `0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69` |
| Zephyr auto connection-parameter update | disabled in both images |
| Host run-time configuration commit | `a46557694d3382e7b9b5e4d9ed8a62ff9ce83e9e` |
| Runner SHA-256 | `3510F0E83438304703C1297F08E12E65E6CF1C535E4420318607E833A4EA4DA0` |
| Host BLE controller | MediaTek USB adapter; `oem134.inf`, version `1.3.17.169` |
| BLE address / expected hardware ID | A `02:00:00:00:00:01` / `1`; B `02:00:00:00:00:02` / `2` |

Key result and audit hashes:

| Artifact | SHA-256 |
|---|---|
| Locked plan and copied plan | `44E873D1E836522CF0928DFA5DEEC092E8C1A1A75011929B147663DAA6C4B` |
| Pre-flash / flash / enumeration record | `C4EF413589C0FA0B9326A1FFC8AEE167C0AADF55F7CF7BABA26D5383A3EC3CE5` |
| `matrix_config.json` | `A153D76461DB8CED6258109BE4C122943F2F9793F09985D39A68339AE49751AF` |
| `matrix_result.json` | `C98FF25786E151AAB2C8AC2F97D90DCB3657598465B2B15E917C377B75D811D5` |
| Preserved `matrix_audit.json` | `F4F31B59800C1061BCBE9F789EEEE04CD338A7C5F40A8234508598DAE490BA79` |
| Preserved `MATRIX_REPORT.md` | `D7324CE10EF4712B525E01D1EC339B7C4F6BF74391FB755B9412280488BDD25F` |
| Independent analysis script | `1EACF3A99511A6F57C7DD969961C3329D77DEC75F1C4A192EB14C2B73C844168` |
| `independent_recalculation.json` | `74C87C152104B18680E57EC018D9F406AB02EDA31CEDFC963D8F3B5FCB18323B` |

The persistent root contains `SHA256SUMS.txt` with the complete per-file hashes,
including all raw streams and sidecars; it was regenerated after adding this
report and independently rechecked. Its final file hash is recorded in
`CURRENT_TASK.md` and `HANDOFF.md` because a manifest cannot hash itself.

## Scope boundary

This report assigns only the predeclared label **inconclusive**. It does not
interpret the observed node/order throughput pattern as a root cause, does not
change firmware, public schemas, or raw data, and does not close M1 or authorize
the 30-minute bench or M2. No fix was implemented.
