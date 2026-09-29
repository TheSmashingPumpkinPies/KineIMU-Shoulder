# M1 CDC Control Stage 10 Parameter Smoke Preflight

Date: 2026-09-21 (Asia/Shanghai)
Status: parameter negotiation was not attempted; no BLE connection was opened.

## Attempt result

At 2026-09-21 14:58:42.140014 UTC, the preflight opened Node A's CDC port
COM5 after resolving serial `0000000000000001`. It then waited five seconds for
a new `conn_param_control_ready node_id=1` marker. The marker did not recur, so
the preflight stopped at 14:58:47.119444 UTC. It sent no ON command, made no BLE
connection attempt, and left the node disconnected and in OFF mode. No
parameter negotiation gate was evaluated.

The local run directory is
`.cache/m1_cdc_stage10_parameter_smoke_20260921_run01`. Its result file SHA-256
is `E407F7FEDDE3E593A7E77736DF81E7F39D844AF84DE9FE4919F0DDC9BA913058`; the
event sidecar SHA-256 is
`BDBE0A22326CBBC025761274EFA2B77F3C515D9961C25CD16BE8E6E28431D86B`. The CDC
binary and text captures are empty. The result's `FAIL` records this harness
preflight timeout; it is not a failed CDC command or BLE parameter result.

## Cause and next action

The firmware prints the ready marker at initialization and repeats it once per
second only while no valid command has been received. In
`firmware/xiao_nrf52840_sense/m1_ble/src/main.c`,
`process_conn_param_experiment_control()` returns after
`conn_param_control_command_received` becomes true. Stage 9 sent the first
valid request on each node, so a later CDC reopen is not expected to produce a
new readiness marker without rebooting the board.

The formal matrix keeps each serial capture open from readiness through its
initial handshake. For this separate smoke, wait for the CDC serial-open event,
then send ON and require its exact transaction ACK using the existing five-
second control budget. Do not wait for a second startup marker. Only after the
ACK passes should the test connect that node and inspect the request log and
actual negotiated tuple within the fixed 10-second window. Repeat for Node B.

The prior Stage 9 BLE-disconnected control smoke remains PASS. This preflight
did not start acquisition or the formal matrix and did not change any timeout.
