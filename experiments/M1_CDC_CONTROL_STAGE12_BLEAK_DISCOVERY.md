# M1 CDC Control Stage 12 Bleak Discovery Diagnostic

Date: 2026-09-21 (Asia/Shanghai)
Status: PASS — a five-second non-connecting M1 service scan found both recorded devices; local Bleak source explains the address-string lookup path.

## Scan result

Bleak 3.0.2 performed one five-second service-filtered scan for M1 service
`f7d20001-4b49-4e45-494d-552d53484c44`. The scan did not connect to either
device. It found both addresses previously assigned by the device identity
record:

| Node | Recorded address | Advertised M1 service | RSSI |
|---|---|---|---:|
| A | `02:00:00:00:00:01` | yes | -44 dBm |
| B | `02:00:00:00:00:02` | yes | -54 dBm |

## Local backend-path finding

The installed Bleak Windows `connect()` implementation calls
`BleakScanner.find_device_by_address()` when the client was constructed from
an address string and has no device details yet. Bleak 3.0.2 uses its
constructor timeout for that scan and GATT service discovery. KineIMU's
`_NodeRecorder` wraps the complete `client.connect()` call in
`asyncio.wait_for()` with the fixed 5.0-second connection limit. That outer
limit can therefore cancel address resolution or service discovery before
the recorder starts GATT reads or telemetry subscription.

Bleak accepts a `BLEDevice` as the client input and supports an M1 service UUID
filter. The next experiment will pass only a scan result whose address exactly
matches the explicit Node A or Node B target, filter discovery to the M1
service, and retain the same five-second recorder timeout and expected hardware
device ID validation. This isolates address lookup/service discovery overhead
without changing a timeout, firmware image, or production adapter.

## Evidence

The machine-local scan result is
`.cache/m1_cdc_stage12_ble_scan_20260921_run01/scan_result.json`, SHA-256
`7B8C4D0B80334519697249FD6705DD08150146FE1B05664829277765F18A322F`. It
records the exact device addresses, advertised service UUIDs, scan duration,
Bleak version, and the installed WinRT `connect()` / service-discovery source.
No connection or acquisition was started; no raw data was read or changed.

Next: run separate short A-only and B-only acquisition smokes with the exact
matching `BLEDevice` inputs, the M1 service filter, and the unchanged five-
second connection timeout. Keep explicit hardware identity validation and
verify OFF after each attempt. Node A's Stage 10A parameter mismatch continues
to block the formal matrix.
