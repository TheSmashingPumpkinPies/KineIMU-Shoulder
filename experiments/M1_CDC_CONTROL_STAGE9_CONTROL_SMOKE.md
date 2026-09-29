# M1 CDC Control Stage 9 Physical Smoke

Date: 2026-09-21 (Asia/Shanghai)
Status: PASS — BLE-disconnected OFF→ON→OFF control completed on both nodes.

## Procedure and identities

Used the matrix's existing `_MatrixCdcCapture`, control client, and initial
handshake routine. USB CDC ports were re-resolved by USB serial immediately
before opening. Only CDC serial interfaces were opened; no BLE client or
acquisition session was started. The sequence ran from 2026-09-21
14:44:46.926371 UTC to 14:44:49.058840 UTC.

| Node | USB serial | Port observed | Ready marker |
|---|---|---|---|
| A | `0000000000000001` | COM5 | `conn_param_control_ready node_id=1` |
| B | `0000000000000002` | COM8 | `conn_param_control_ready node_id=2` |

COM values are recorded for this run only; future runs resolve by USB serial.
Each node completed OFF→ON→OFF with per-node transaction IDs 1, 2, and 3.
Every write returned its full expected byte count. Every ACK matched node,
transaction, requested mode, selected mode, and `rc=0`:

| Node | tx | Mode | Write bytes | `write()` ms | Command-to-ACK ms | Exact ACK |
|---|---:|---|---:|---:|---:|---|
| A | 1 | OFF | 33/33 | 23.0 | 101.0 | `node_id=1 tx=1 requested=OFF selected=OFF rc=0` |
| A | 2 | ON | 32/32 | 103.7 | 213.7 | `node_id=1 tx=2 requested=ON selected=ON rc=0` |
| A | 3 | OFF | 33/33 | 105.2 | 215.2 | `node_id=1 tx=3 requested=OFF selected=OFF rc=0` |
| B | 1 | OFF | 33/33 | 42.9 | 104.9 | `node_id=2 tx=1 requested=OFF selected=OFF rc=0` |
| B | 2 | ON | 32/32 | 104.8 | 198.8 | `node_id=2 tx=2 requested=ON selected=ON rc=0` |
| B | 3 | OFF | 33/33 | 104.3 | 198.3 | `node_id=2 tx=3 requested=OFF selected=OFF rc=0` |

Command-to-ACK time includes the measured synchronous `write()` duration plus
the host monotonic interval from completed write to matching ACK. The maximum
was 215.2 ms, within the requested 500 ms target. The client's existing
20 ms slow-write diagnostic marked all six writes delayed; the writes were
complete and the ACKs remained within the target. No serial write timeout or
five-second control budget was changed. Both nodes were left in OFF mode.

## Evidence and disposition

The machine-local capture is
`.cache/m1_cdc_stage8_control_smoke_20260921_run01`. It contains the structured
result, event sidecar, and exact CDC byte streams. Result SHA-256 is
`57D9B0053556D53424548BB78E9B674BA1CCD1C5D5F6A7D433AF8FE319E0B613`; event
sidecar SHA-256 is
`F1EC568CC3372C84953BAA2DBB6B0F58A0BDCB8B892078402308EA58843BC7BB`. Node A
and B CDC byte-stream hashes are respectively
`98FC2AF4A131CE9D5957A831C7AF2DA3ADB74C7412AC1298D636D8334F4610E6` and
`54F0CA9506DAEE8BB7084399C7B4846C00E91BF529E886D34AEC72959148462C`.
Manifest:
`.cache/m1_cdc_stage9_control_smoke_manifest_20260921.json`, SHA-256
`8D96F0ED98F8275ED2D26D9A248BCB870697EA318A289569C8723685FBF82D21`.

The control smoke passed. No BLE connection, negotiated-parameter test,
acquisition capture, formal v2 matrix, or raw acquisition data collection has
started. Next, set ON and connect Node A alone, then Node B alone. For each,
require the firmware ON request log and the actual negotiated 15 ms / 0 / 420 ms
tuple within the fixed 10-second inspection window; stop if either check fails.
