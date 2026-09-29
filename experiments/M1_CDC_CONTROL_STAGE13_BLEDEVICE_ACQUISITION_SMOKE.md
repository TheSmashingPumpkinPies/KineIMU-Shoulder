# M1 CDC Control Stage 13 BLEDevice Acquisition Smoke

Date: 2026-09-21 (Asia/Shanghai)
Status: FAIL — the exact-device Bleak path also exceeded the unchanged five-second connection gate on both nodes; no acquisition data was collected.

## Procedure and outcome

A fresh five-second scan found both expected M1 advertisements. Each serial-
resolved node was separately set to connection-parameter mode OFF, then passed
to the existing single-node recorder using the exact matching `BLEDevice`
object and Bleak's M1 service filter. The recorder's five-second connection
timeout and expected hardware device ID checks were unchanged.

| Node | USB serial / port | Matching scan RSSI | Connect result | Raw bytes / valid packets | Cleanup OFF |
|---|---|---:|---|---:|---|
| A | `0000000000000001` / COM5 | -47 dBm | `BleTransportError` after 5.0 s; no peripheral link event logged | 0 / 0 | tx=2, rc=0 |
| B | `0000000000000002` / COM8 | -57 dBm | `BleTransportError` after 5.0 s; no peripheral link event logged | 0 / 0 | tx=2, rc=0 |

Both raw streams and recorder event sidecars are empty. CDC captures contain
only the initial and cleanup OFF ACKs; neither board logged a BLE connection.
Both boards are confirmed disconnected and OFF.

## Acquisition gates

No recorder capture returned and valid packet counts are zero. The firmware
trace counters `callback`, `raw_try`, `raw_ok`, and `notify_calls` have no
snapshots, so their deltas remain unavailable. CRC/decode/framing counts are
zero because the streams contain no records; that does not pass the
acquisition gate.

This attempt used the scan's exact `BLEDevice` object and M1 service filter,
which removed the address-string lookup path. It still failed within the same
five-second connection limit, so that address lookup alone did not explain the
connection timeout. Do not treat this diagnostic as evidence of a BLE link or
successful acquisition.

## Evidence and disposition

Fresh evidence is under ignored `.cache` paths:

- A run: `.cache/m1_acquisition_smoke_stage13_node_a_run01`; `run_result.json` SHA-256 `C15B58D92110C9984B75749E8484EF1849BAC2B598E09BCB8E60457D931A4081`.
- B run: `.cache/m1_acquisition_smoke_stage13_node_b_run01`; `run_result.json` SHA-256 `503EB6A4402CFE982A1D79DF31F7A2865CE20A9EBE3C5B5E17750BEE23AE57A6`.
- Combined local manifest: `.cache/m1_acquisition_smoke_stage13_manifest_20260921.json`, SHA-256 `E147DE1B98BE360B848A3FB0F0CD29D9CE07E81C65297AF457C18E45D8D607D1`.
- Both empty raw streams have SHA-256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.

Node A's Stage 10A parameter mismatch continues to block the formal matrix.
The acquisition smokes also remain failed with the current Windows connection
path and fixed five-second limit. No formal matrix, 30-minute bench, or M2 work
was started. No further physical retries are planned under the same gate; the
next action requires a maintainer-approved host connection policy that can
complete GATT setup within the current limit or a revised timeout constraint.
