# M1 CDC Control Stage 10A Node A Parameter Smoke

Date: 2026-09-21 (Asia/Shanghai)

Corrected disposition: **INCONCLUSIVE** — the raw capture ends 6.609 seconds after the actual peripheral-connected event, before the required 10.0-second observation window is complete.

## Node A observation

The test resolved CDC serial `0000000000000001` to COM5 and used BLE address
`02:00:00:00:00:01`, previously tied to hardware ID `0x000000005EF610E5`.
The ON command was acknowledged as `node_id=1 tx=1 requested=ON selected=ON
rc=0`. The firmware logged the parameter API call with `call=1` and
`api_rc=0`.

The host connection attempt started at 15:03:29.861278 UTC. The actual firmware
connected event was received at 15:03:31.266228 UTC. A parameter callback was
received at 15:03:32.147343 UTC and reported:

```text
Node A: BLE link parameter callback interval_units=11 latency=0 supervision_timeout_units=960
Node A: BLE link event=param_updated info_rc=0 interval_us=13750 latency=0 supervision_timeout_us=9600000 ...
```

This callback records 13.75 ms / latency 0 / 9,600 ms supervision timeout,
which is a non-target tuple. The host connection attempt later timed out; the
CDC observation ended at 15:03:37.875172 UTC. From the actual connected event
to that end, the available observation was 6.608944 seconds, or **6.609
seconds**. The predeclared 10.0-second event-relative window was not completed.
Therefore this callback cannot establish a completed target-tuple failure;
Node A's Stage 10A parameter disposition is **inconclusive**.

The earlier run result's `tuple_gate_pass=false` used the host connection-attempt
timer and is preserved as recorded. This corrected report interprets the same
raw CDC timeline from the real peripheral-connected event. It does not change
the raw events, the local result JSON, or the historical formal matrix.

The host `connect()` call reached its previous five-second timeout while the
peripheral remained connected. An OFF request made immediately afterward
returned `rc=-16`. A later cleanup OFF command returned `rc=0`; Node A was then
disconnected and OFF. No telemetry subscription or acquisition capture started.

## Preserved evidence

Original Stage 10A files remain unchanged under
`.cache/m1_cdc_stage10_parameter_smoke_20260921_run02/node-a`:

- CDC byte stream SHA-256: `1060BAC39B5CC86DC28A77D0C46F5A7282345F551936E2F63531F35BDBFEE04A`
- CDC event sidecar SHA-256: `4F61E758A6B8DE9C4CCDFBE7EDAA91B4CF17496EE37110B04A731B094D1CE7DF`
- Original run result SHA-256: `2FA48310BDD2089949E78EC90349FF6426FF1580674A8118535552DAAE311AC1`
- Original local manifest SHA-256: `4CACAA617ED3E75323B4821F5DF22D84CD3108A00705C17BCD9345C7CEC5576A`

The five-second address-string and BLEDevice attempts in Stages 11–13 also did
not pass acquisition setup. Under the new maintainer-authorized v2 policy, the
parameter smoke must use a fresh session handshake, a fresh M1-service-filtered
scan, a separate 15.0-second Windows connect/GATT setup limit, and the complete
10.0-second window from the firmware connected event. Both nodes must pass
before the formal matrix may run.
