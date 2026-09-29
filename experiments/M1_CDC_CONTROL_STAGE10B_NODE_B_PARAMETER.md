# M1 CDC Control Stage 10B Node B Parameter Smoke

Date: 2026-09-21 (Asia/Shanghai)
Status: the requested tuple was observed twice within the peripheral-relative 10-second window, with an intervening renegotiation and a host connection timeout.

## Node B result

The test resolved CDC serial `0000000000000002` to COM8 and used the recorded
Node B BLE address `02:00:00:00:00:02`, previously tied to hardware ID
`0x0000000059E4A5F0` in the M1 device identity records. The CDC ON transaction
was acknowledged as `node_id=2 tx=1 requested=ON selected=ON rc=0`.

The host began its Bleak connection attempt at 15:13:53.174230 UTC. That call
timed out at the existing five-second limit at 15:13:58.406286 UTC. The
peripheral's CDC log then recorded the actual connection and the firmware ON
request at 15:13:59.599940 UTC, with `call=1 api_rc=0`. The peripheral event is
the start of the 10-second parameter inspection window.

The parameter callbacks in the raw CDC capture were:

| Callback UTC | Time from peripheral connection log | Actual interval | Latency | Supervision timeout |
|---|---:|---:|---:|---:|
| 15:14:05.071961 | 5.469 s | 15.00 ms | 0 | 420 ms |
| 15:14:07.573031 | 7.969 s | 11.25 ms | 0 | 420 ms |
| 15:14:09.526515 | 9.922 s | 15.00 ms | 0 | 420 ms |

The target 15 ms / 0 / 420 ms tuple was observed twice within ten seconds of
the peripheral connection event. The connection also renegotiated to 11.25 ms
inside the same window. This is evidence that the target tuple was reached, but
not that it remained stable through the window. The host Bleak connect call
timed out before the peripheral connection log and returned
`is_connected=false`; an unconditional `disconnect()` call returned, but an
immediate CDC OFF request still received `rc=-16` while the link was active.
The original local runner result marks its tuple gate false because its timer
started at the earlier connection attempt. This report reconstructs the
peripheral-relative window from the timestamped CDC event sidecar and does not
overwrite that result.

A later OFF command returned `node_id=2 tx=1 requested=OFF selected=OFF
rc=0` at 15:16:10.356755 UTC, confirming Node B is now disconnected and OFF.
No telemetry subscription or acquisition capture was started.

## Evidence and disposition

The raw CDC and event evidence is in
`.cache/m1_cdc_stage10b_node_b_parameter_smoke_20260921_run01`; the later OFF
cleanup is in `.cache/m1_cdc_stage10_node_b_cleanup_20260921_run01`. The local
manifest is
`.cache/m1_cdc_stage10b_node_b_parameter_manifest_20260921.json`, SHA-256
`2A7CE9872752FCD00EE869FF29E72683234E7984C04D7C0D149441D79F0C873C`.

Node B reached the target tuple, with repeated parameter updates during the
window. Node A did not reach its target tuple, and both Bleak connect calls
timed out, so the formal v2 matrix remains blocked. The two nodes are OFF and
disconnected. The next independent gate is separate short A-only and B-only
acquisition captures, with no telemetry data changed or collected by this
parameter test.
