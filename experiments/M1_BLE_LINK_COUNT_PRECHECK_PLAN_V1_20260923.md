# M1 BLE Link-Count Precheck v1

Status: **precheck plan only; not a formal causal matrix**
Date: 2026-09-23 (Asia/Shanghai)

## Purpose and bounded factor

The v2 peripheral-request factor is not identifiable on the current
Windows/adapter/firmware/board combination because the ON and OFF streams
converged on the same actual tuple. This precheck evaluates whether the
existing capture system can distinguish **one versus two simultaneously active
BLE links** while recording both connection orders and same-block single-node
controls. It is an instrumentation and state-realization gate, not a formal
causal result or M1 acceptance run.

The sole manipulated factor is active BLE link count: one in `a_only` and
`b_only`, two in `dual_a_to_b` and `dual_b_to_a`. Local peripheral parameter
requests remain **OFF** for every condition. Firmware, board, host/controller,
sensor setup, connection behavior, capture duration, and recorder remain fixed.

## Locked setup and provenance

- Firmware source: `270911756c227a20feb18df71edad7ad4544aedb`.
- Board: Seeed XIAO nRF52840 Sense (`xiao_ble/nrf52840/sense`), Zephyr v4.4.0,
  SDK 1.0.1; LSM6DS3TR-C at the existing 104 Hz configuration.
- Node A bootloader USB serial: `0000000000000001`; application hardware ID
  `1`; expected node ID 1.
- Node B bootloader USB serial: `0000000000000002`; application hardware ID
  `2`; expected node ID 2.
- Resolve CDC ports by those USB serials at execution time. Current observed
  mapping is A=COM4 and B=COM7; COM names are not fixed identifiers.
- BLE addresses from the v2 verified device map: A=`02:00:00:00:00:01`,
  B=`02:00:00:00:00:02`. Runtime identity reads must match the hardware IDs
  above; address alone is not device identity.
- Node A image SHA-256:
  `226B77FCEA1054022DA9F0E9884D3297245050A88156CE2EAD7A9177B4177380`.
- Node B image SHA-256:
  `6B38472B703D9B102767A1823BC34876EE24B0AA67AA328E346F1312B8525B32`.
- Both byte-identical build configurations SHA-256:
  `0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69`.
- The source board/image verification record is the v2
  `preflash_firmware_and_hardware_check.json`, SHA-256
  `DC9E947D82C5E11E95B6289F19A670D7E05B054A1F90E0EFD0708C7F0A8A7881`.
  No new flash or firmware change is part of this precheck. BLE identity reads
  and the source record must independently agree with these identities.
- Host/controller are held to the same Windows host and single MediaTek USB
  Bluetooth adapter used by v2: instance
  `USB\VID_13D3&PID_3563&MI_00`, driver `oem134.inf` 1.3.17.169. Record the
  runtime OS, adapter/controller identity, and driver with the run config.
- Existing four-slot acquisition queue, eight ATT TX contexts, 5 ms retry,
  GATT/data contract, and public data schema remain unchanged.
- Output root: `<external-data>\kineimu_m1_root_cause_precheck_20260923_01`.
  It must not exist before execution. The script refuses a nonempty or
  previously used root.
- The committed runner source hash, Git HEAD, locked plan hash, image/config
  hashes, serial map, and device IDs are written to the output root before the
  first BLE connection.

## Conditions and fixed execution order

One block is used only to verify instrumentation and state realization; it is
not enough to support a transport-effect claim.

| Run | Condition | Active links | BLE establishment order | Same-block control |
| --- | --- | ---: | --- | --- |
| 1 | `a_only` | 1 | A | — |
| 2 | `dual_a_to_b` | 2 | A then B | A-only in run 1; B-only in run 3 |
| 3 | `b_only` | 1 | B | — |
| 4 | `dual_b_to_a` | 2 | B then A | A-only in run 1; B-only in run 3 |

All four conditions use local parameter-request mode OFF. Hold 10.0 s from each
firmware peripheral-connected event for parameter/event observation, capture
exactly 15.0 s from the shared recorder-ready boundary, and wait 2.0 s after
confirmed disconnect before the next run. The strict per-callback admission
marker uses the recorder's shared `perf_counter_ns` clock domain.

Do not reorder, replace, repeat, or omit a condition. If a run fails or is
partial, retain every file produced so far, complete final OFF cleanup if the
control path is available, write a manifest for the partial root, and stop.
The nonempty output root permanently consumes this one precheck attempt; do not
resume or append to it.

## Required evidence and precheck pass rule

The precheck passes only if all of these gates pass:

1. **Plan, code, and artifact lock:** the runner confirms this exact plan SHA
   is bound to the fixed output root and the root was absent/empty. Before any
   BLE connection, `matrix_config.json` binds Git HEAD, runner SHA, plan SHA,
   firmware source, both image/config hashes, source preflash-record hash,
   expected hardware IDs, resolved USB serials, BLE addresses, and host adapter
   identity. Every output file, including partial outputs, is included in
   `SHA256SUMS.txt`.
2. **Factor state is realized during the capture:** one connected node and
   two concurrently connected nodes are established as scheduled; both active
   nodes in a dual condition remain connected across the entire shared
   15-second window. The two observed connect events must match the planned
   order. Each active firmware connection event is recorded before the capture
   boundary. The CDC local-request record must show OFF / no app request.
3. **Connection/event window:** every active node has the complete 10.0 s
   window anchored to its firmware connected event, including all parameter
   callback values; do not infer who initiated a callback from this record.
4. **Capture boundary and identity:** each active node has one explicit
   shared-ready capture marker, a 15.0 s interval, and consistent per-callback
   admission evidence. BLE identity/config reads match node ID, expected
   hardware ID, and firmware commit; MTU is 127 for every active connection.
5. **Per-generation TX diagnostics:** each active capture contains an exact,
   unsaturated diagnostic segment for its active connection generation, with
   all return-code, accepted/completed, retry, full-context wait, completion
   age, packet-drop, queue, and lifecycle metrics parseable. Missing snapshots,
   ambiguous generations, or saturated counters fail this gate.
6. **Raw-data integrity:** each active node has nonempty `.kimu`, event
   sidecar, and CDC bytes. Independently parse each `.kimu`; packet and notify
   counts agree; CRC, decode, framing, and node-ID errors are zero. Sidecars
   parse completely. Generate a SHA-256 manifest and have a separate
   read-only analyzer verify every listed file, no missing/unlisted files,
   and unchanged raw hashes during analysis. Write that analysis outside the
   raw root.
7. **Cleanup:** every expected host disconnect and firmware disconnect event
   completes after capture, with no cleanup errors. Both nodes end in explicit
   OFF state with acknowledged `rc=0` control transactions.
8. **Schedule:** all four conditions were attempted once in the locked order,
   all four completed without run/setup errors, and no unplanned capture exists.

Passing these gates means only that a new factor and the required observations
are physically controllable and auditable. It does not itself classify the
throughput mechanism or satisfy any M1 throughput threshold. A failure blocks
formal-plan drafting/acquisition until the specific instrumentation issue is
corrected and a new precheck authorization is recorded.

## Stop conditions

Stop at the first hard-gate failure: unexpected board/image/config/host
identity; unavailable or mismatched CDC serial; control handshake failure;
BLE setup, node identity or MTU failure; missing 10-second window or explicit
15-second boundary; incomplete TX generation diagnostics; raw decode/CRC/
framing/node mismatch; missing/changed raw hash; unconfirmed disconnect; or
failed OFF cleanup. Preserve all partial files and manifest them. Do not flash,
change the Bluetooth adapter, modify firmware, grow a queue/context, or start
the formal matrix to work around a failed precheck.

## After the precheck

If and only if the independent precheck audit passes every gate, prepare a new
versioned formal plan for the one-versus-two link factor. That separate plan
must be committed with its runner and input hashes before acquisition; it must
include both connection orders, same-block single controls, balanced execution
order, Supported / Not supported / Inconclusive criteria, integrity gates, and
stop rules. The formal matrix may then be run at most once in a separate new
empty root. This precheck plan does not itself authorize the formal matrix,
30-minute bench, hardware freeze, M2, push, merge, or PR.
