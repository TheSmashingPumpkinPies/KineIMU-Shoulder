# M1 CDC Control Stage 11 Single-node Acquisition Smoke

Date: 2026-09-21 (Asia/Shanghai)
Status: FAIL — both host BLE connection attempts timed out before telemetry capture; no acquisition packets were collected.

## Procedure and outcome

Each node was opened separately by the recorded USB serial, set to connection-parameter mode OFF with an acknowledged CDC transaction, and passed to the existing single-node recorder for a planned 15-second capture. The recorder's existing five-second BLE connection timeout was unchanged. No formal matrix or 30-minute bench was started.

| Node | USB serial / port | BLE address | Initial OFF ACK | BLE result | Raw bytes / valid packets | Cleanup OFF |
|---|---|---|---|---|---:|---|
| A | `0000000000000001` / COM5 | `02:00:00:00:00:01` | tx=1, rc=0 | timed out after 5.0 s; no peripheral link event logged | 0 / 0 | tx=2, rc=0 |
| B | `0000000000000002` / COM8 | `02:00:00:00:00:02` | tx=1, rc=0 | timed out after 5.0 s; peripheral logged a connection and DLE update | 0 / 0 | tx=2–4 returned rc=-16 while linked; tx=5 returned rc=0 after `disconnected reason=0x13` |

The 15-second capture interval did not begin for either node because recorder setup failed at connection establishment. Node B's peripheral link log shows that a radio link existed even though the host recorder's `connect()` did not return successfully. The CDC log contains no telemetry-enable or acquisition-stream-start line.

## Acquisition gates

| Gate | A | B | Evidence |
|---|---|---|---|
| Recorder returned a capture | FAIL | FAIL | `BleTransportError` after the unchanged 5.0-second connection timeout |
| Valid packets greater than zero | FAIL | FAIL | zero-byte raw streams; zero valid packets |
| `callback`, `raw_try`, `raw_ok`, and `notify_calls` increased | INDETERMINATE | INDETERMINATE | zero firmware trace snapshots were logged |
| Zero CRC/decode/framing errors | No errors observed; gate not established | No errors observed; gate not established | no packet records were available to inspect |
| OFF state confirmed | PASS | PASS | final OFF ACK had rc=0 for each node |

The absent firmware trace is expected when acquisition never starts. In
`firmware/xiao_nrf52840_sense/m1_ble/src/main.c`, `acquisition_enabled` becomes
true only after `node_a_ble_service_is_stream_ready()` succeeds following
telemetry notification setup. `publish_status_if_due()` emits the requested
trace fields only while that flag is true. The host timed out before enabling
telemetry on both runs; therefore these counters are unavailable, not proven
zero.

## Evidence and disposition

Fresh local evidence was written only under ignored `.cache` paths:

- A run: `.cache/m1_acquisition_smoke_20260921_node_a_run01`; `run_result.json` SHA-256 `1D0A015DC9A9B295F8303C935FBD780B08EDCAA488860166034C0E21AB2A32B2`; empty raw stream SHA-256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.
- B run: `.cache/m1_acquisition_smoke_20260921_node_b_run01`; `run_result.json` SHA-256 `EF7E314D7273C4860505A8B7401A6D0FA4D6A4BE089A03354CF24F01C70A915F`; empty raw stream SHA-256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.
- Combined local manifest: `.cache/m1_acquisition_smoke_20260921_manifest.json`, SHA-256 `D5FD9602B888A1462B71CD5248371CD550CD7CD386278A43AE334C71ED35AC46`.

Both nodes are confirmed disconnected and OFF. No prior raw data or public schema was changed. The formal v2 matrix remains blocked by Node A's Stage 10A tuple mismatch, and these acquisition gates also did not pass. Do not run the formal matrix, the 30-minute bench, or M2.

Next: inspect the installed Bleak/Windows connection-resolution path and perform a non-connecting scan for the explicitly recorded M1 device addresses. Keep the five-second connection timeout unchanged; do not reflash or change firmware, BLE queue/context limits, or public schemas.
