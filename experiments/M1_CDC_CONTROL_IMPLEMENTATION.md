# M1 Experiment CDC Control Implementation

Date: 2026-09-21 (Asia/Shanghai)
Scope: experiment-only USB CDC control for the locked M1 connection-parameter matrix.

## Wire contract

The host accepts a readiness line only when its node ID matches the open CDC
port:

```text
conn_param_control_ready node_id=<1|2>
```

Each mode write is one ASCII line with a positive, per-node, monotonically
increasing 32-bit transaction ID:

```text
conn_param_request tx=<id> mode=OFF|ON
```

Firmware replies with the same transaction ID and reports both the requested
and selected mode:

```text
conn_param_request_ack node_id=<1|2> tx=<id> requested=OFF|ON selected=OFF|ON rc=<int>
```

The host treats a request as applied only when the node and transaction match,
the ACK's requested mode matches, `rc` is zero, and the selected mode equals
the requested mode. Wrong-node, wrong-transaction, and late ACKs are logged as
stale and do not complete another request. Partial writes, write errors, and
ACK timeouts fail the control gate and clear the pending transaction.

The ACK budget remains five seconds total, measured before dispatch and covering
the serial write and ACK wait. The serial port's existing one-second
`write_timeout` is unchanged; serial-thread dispatch is bounded at two seconds
inside the total request budget. The transaction ID adds correlation to the
plan's OFF/ON mode factor; it does not change that factor or the predeclared
OFF–ON–ON–OFF schedule.

## Startup and block gates

Before any BLE run, the runner opens both serial captures, waits for both
matching readiness lines, then exercises OFF→ON→OFF on each node. It does not
send any handshake command until both nodes are ready. The first run of each
predeclared block sets that block's mode on both nodes, including the node not
selected by a single-node condition. Both ACKs must confirm the requested mode
before the recorder can start BLE. CDC capture boundaries are taken before the
block writes so the command, write timing, and ACK remain in the associated
capture segment for runs that reach the condition runner. A pre-BLE gate failure
remains in the matrix-level CDC capture and control event log.

Any readiness, CDC capture, write, ACK, or run failure stops the schedule at
that point. The runner does not retry or replace a failed condition. It records
the failed control result and stop reason in `matrix_result.json` and returns a
nonzero exit status. A failed initial handshake starts no BLE run.

## Implementation boundary

The experiment firmware enables the CDC UART RX interrupt and copies FIFO bytes
into a bounded application ring from the IRQ callback. Framing, parsing, mode
changes, and ACK formatting run from the main loop. The host keeps one serial
capture thread per node; that thread owns the serial handle, writes commands,
and retains the raw CDC byte stream. The firmware continues to reject mode
changes while connected.

This path does not change the public acquisition schema, BLE queue capacity,
ATT completion context, data format, raw-data handling, or the locked run
schedule. The audit accepts both the current runner's `A` / `B` CDC result keys
and the older `node-a` / `node-b` keys.

The root-cause report and prior inconclusive matrix remain unchanged. No
reference-board image, flash, control smoke, acquisition smoke, or new data
capture has been performed at this software checkpoint.
