# M1 BLE Link-Count Precheck V3

Status: **precheck plan only; not a formal causal matrix**
Date: 2026-09-23 (Asia/Shanghai)

## Purpose and bounded factor

The formal v2 peripheral-request factor remains **INCONCLUSIVE** and is not
identifiable on this Windows/adapter/firmware/board combination: ON and OFF
connections converged to the same actual `15 ms / 0 / 420 ms` tuple, and
`param_updated` callbacks do not identify the requester. First-link throughput
loss with GATT `-ENOMEM`, retries, and full-context waits remains a mechanism
observation, not an established end-to-end cause or resource-owner attribution.

This V3 precheck evaluates one alternate, directly observable factor: **one vs.
two simultaneously active BLE links**. The precheck only verifies state
realization and the evidence path; one block cannot support a transport-effect
claim. Local peripheral parameter requests stay **OFF** in every condition.
Firmware, board, host/controller, sensor setup, connection behavior, capture
duration, queue capacity, ATT completion contexts, and public data format remain
fixed. V3 exists because the consumed V2 precheck stopped in the host capture
marker before any 15-second measurement.

## Preserved earlier attempts and V2 instrumentation correction

Precheck V1 stopped before a scheduled condition because the serial-matched
ports were UF2 bootloader interfaces `2886:0045`. Its consumed raw root is
`<external-data>\kineimu_m1_root_cause_precheck_20260923_01`; the 14-entry manifest
SHA-256 is
`D62DD9749EC6961BEC58BA51911C6E393E66ED26BDAC2D233A9E9E0C3364EDA4`. Its
independent report is
`<external-data>\kineimu_m1_root_cause_precheck_20260923_01_independent.json`,
SHA-256 `296CC2BC489DDD76D606626B1D16DBBB2AA932BFDFD210C9B200F7076378789F`,
disposition BLOCKED. No BLE condition or KIMU capture occurred.

Precheck V2 required matching USB serials and application CDC `2FE3:0004` and
passed this gate after the user reset both boards. It executed only `a_only`;
the BLE link established and was disconnected cleanly. The acquisition then
stopped before the capture-window marker with
`AttributeError: 'str' object has no attribute 'name'`. Its KIMU file is empty,
there is no measured link-count factor, and no dual-link condition ran. Do not
interpret this as a BLE throughput result.

The V2 callback passed `node_id.name` to `EventLog.write`, whose contract takes a
`NodeId`; this raised while writing the shared capture marker. The working-tree
runner correction now passes the enum. The preserved V2 audit additionally
exposed three evidence-path mismatches, corrected for V3: it expected matrix
result schema `/2.0` while the writer emits `/1.0`; root config did not persist
the expected application CDC VID/PID; and the analyzer searched the run root
instead of the recorder `raw/` directory for KIMU/event sidecars.

V2 root
`<external-data>\kineimu_m1_root_cause_precheck_20260923_02` is consumed and immutable.
Its 24-entry manifest SHA-256 is
`5D635868F1B651CE0363AFC198C13B6571752FF5610EAAF1B8838E7CDC3C013C` and
verified. Preserved independent report
`<external-data>\kineimu_m1_root_cause_precheck_20260923_02_independent.json`,
SHA-256 `BE7E1C0AEB448FB9B9831898BA7EBC00C8515195C34E7D58F76CB319CDA14B51`,
is BLOCKED; raw-input hashes were unchanged. Never resume, append to, or
overwrite the V1/V2 roots or replace a planned condition inside this V3 root.

## Locked hardware, host, and source provenance

- Firmware source: `270911756c227a20feb18df71edad7ad4544aedb`.
- Board: Seeed XIAO nRF52840 Sense (`xiao_ble/nrf52840/sense`), Zephyr v4.4.0,
  SDK 1.0.1; existing LSM6DS3TR-C 104 Hz configuration.
- Node A bootloader USB serial `0000000000000001`; application hardware ID
  `1`; expected node ID 1.
- Node B bootloader USB serial `0000000000000002`; application hardware ID
  `2`; expected node ID 2.
- Require serial-matched application CDC VID/PID `2FE3:0004` for both nodes
  before output-root creation and before sending HELLO. The UF2 interface
  `2886:0045` is forbidden. Resolve devices by USB serial at runtime; COM names
  are informational only.
- BLE addresses: A=`02:00:00:00:00:01`, B=`02:00:00:00:00:02`. Read runtime
  identity/config and prove its node ID, hardware ID, and firmware commit.
- Node A image SHA-256:
  `226B77FCEA1054022DA9F0E9884D3297245050A88156CE2EAD7A9177B4177380`.
- Node B image SHA-256:
  `6B38472B703D9B102767A1823BC34876EE24B0AA67AA328E346F1312B8525B32`.
- Byte-identical Node A/B build `.config` SHA-256:
  `0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69`.
- Source preflash/hardware record:
  `<external-data>\kineimu_m1_ble_connparam_rootcause_v2_20260923_01\preflash_firmware_and_hardware_check.json`,
  SHA-256
  `DC9E947D82C5E11E95B6289F19A670D7E05B054A1F90E0EFD0708C7F0A8A7881`.
  No reflashing or firmware change is part of this precheck.
- Keep the same Windows host and MediaTek Bluetooth adapter as the source v2
  run: instance `USB\VID_13D3&PID_3563&MI_00`, driver `oem134.inf`
  `1.3.17.169`. Record runtime OS/controller/driver and both resolved CDC
  interface records in `matrix_config.json`.
- Keep the existing four-slot acquisition queue, eight ATT TX contexts, 5 ms
  retry, GATT/data contract, and public data format unchanged.
- New output root:
  `<external-data>\kineimu_m1_root_cause_precheck_20260923_03`. It must not exist
  before acquisition. V1 and V2 roots remain immutable.
- Before acquisition, commit this exact plan together with the corrected
  precheck runner, shared matrix runner, and regression tests. The run config
  must bind the resulting Git HEAD and source hashes, this plan SHA, firmware
  and `.config` identities/hashes, device/USB identities, and host adapter.

## Factor, fixed settings, and one-block schedule

Only the number of active BLE links changes. The execution order is fixed for
this instrumentation gate; it is not used as a formal randomized causal
schedule.

| Run | Condition | Active links | Establishment order | Same-block single controls |
| --- | --- | ---: | --- | --- |
| 1 | `a_only` | 1 | A | — |
| 2 | `dual_a_to_b` | 2 | A then B | A-only run 1; B-only run 3 |
| 3 | `b_only` | 1 | B | — |
| 4 | `dual_b_to_a` | 2 | B then A | A-only run 1; B-only run 3 |

All four conditions keep local parameter requests OFF. For each active node,
record the full 10.0-second observation window from its firmware
`peripheral_connected` event, including every parameter callback. Wait 2.0
seconds after confirmed disconnect before the next condition. Capture exactly
15.0 seconds from the shared recorder-ready boundary using strict callback
admission timestamps. For dual conditions, prove both firmware links overlap
for the full 15.0-second window and the observed connection events match the
planned order.

Do not reorder, omit, replace, repeat, or supplement any of the four V3
conditions. On any failed or partial condition, retain every output, complete
OFF cleanup if CDC control is available, write the raw-file manifest, and stop.
The nonempty V3 root then becomes consumed.

## Required evidence and pass gates

V3 passes only if every gate below passes:

1. **Plan/code/artifact lock.** Before BLE, the output root contains the exact
   plan copy, Git HEAD, plan/runner/matrix-runner hashes, firmware source, A/B
   image and byte-identical `.config` hashes, source preflash record hash,
   hardware IDs, BLE addresses, serial-resolved CDC device records, expected
   application CDC `2FE3:0004` record, and current host/controller/driver
   identity. The root was absent before this run.
2. **Factor realization.** All four scheduled conditions complete. Each single
   condition has exactly its one planned active link; each dual condition has
   both links active concurrently for the full 15.0-second capture in the
   planned order. This gate verifies manipulability; it does not classify a
   transport effect.
3. **Firmware parameter/event window.** Every active link has the complete
   10.0-second connected-event-relative window and all parameter callbacks.
   Record callbacks as observations only; do not attribute their initiator
   based solely on `param_updated`.
4. **Capture window and device identity.** Each active node has exactly one
   shared-ready start/deadline marker, 15.0 seconds of callback admission
   evidence on the declared clock domains, runtime identity/config matching the
   expected node/hardware/firmware, and accepted MTU 127 in the capture sidecar.
5. **Per-generation TX diagnostics.** Each active connection generation has
   exact, unsaturated, start/end diagnostic snapshots with every locked call,
   accepted/final-fail, drop, `-ENOMEM`, `-EAGAIN`, retry, window-full/wait,
   completion, cancellation, stale-callback, age, and scheduling-failure
   counter parseable.
6. **Raw-data integrity.** Each active node has nonempty CDC segment, framed
   KIMU stream, and event sidecar under `raw/`. Independent decoding directly
   from raw captures must match notify counts; CRC, decode, framing, and node-ID
   errors are zero. Sidecars parse completely. `SHA256SUMS.txt` lists every
   output file with no missing, mismatched, duplicate, or unlisted file. A
   separate read-only audit confirms unchanged raw-input hashes; it must not
   read `matrix_audit.json` or a prior audit as an input. `matrix_result.json`
   uses schema `kineimu.m1.ble-link-count-precheck-result/1.0`, which must match
   the acquisition writer; per-run results use `/2.0`.
7. **Cleanup.** Every expected host and firmware disconnect is observed and
   completes after capture, with no cleanup errors. Both nodes end in explicit
   OFF state with acknowledged `rc=0` transactions.
8. **Schedule/analysis.** All four conditions were attempted once in the exact
   order. The independent raw audit has no errors, the manifest verifies, and
   hashes remain unchanged during the audit. No planned capture is missing or
   duplicated.

Passing V3 authorizes drafting a separate formal plan for the same single
factor. It is not a formal causal conclusion and does not satisfy M1 throughput
acceptance.

## Stop conditions and next step

Stop at the first hard-gate failure: unexpected source/board/image/config/host
identity; wrong or unavailable serial/CDC VID/PID; failed HELLO/READY, OFF
control, BLE identity or MTU; incomplete connection-event window; missing
capture boundary or TX snapshot; empty/corrupt raw stream; integrity/hash
failure; unconfirmed disconnect; or incomplete schedule. Preserve and manifest
partial output. Do not flash, change the host or adapter, grow queues/contexts,
or start the formal matrix to work around a failure.

If and only if the independent V3 precheck audit passes, prepare a separately
versioned formal plan with a balanced execution schedule, both connection
orders, same-block single controls, hard stop/integrity gates, and explicit
Supported / Not supported / Inconclusive criteria. Commit that plan, runner,
and firmware/hardware identities before at most one formal acquisition in a
new empty root. The formal experiment must still be followed by independent
raw analysis; a matrix alone is not success.

This plan does not authorize changing public format, expanding BLE queue/ATT
capacity, changing the host/adapter, flashing firmware, running the 30-minute
M1 bench, freezing hardware, starting M2, pushing, merging, or opening a PR.
