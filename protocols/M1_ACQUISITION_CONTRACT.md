# M1 Acquisition Contract v0.1

Status: FROZEN FOR M1 IMPLEMENTATION. Breaking changes require a new protocol
version and migration note.

This contract defines the boundary between XIAO nRF52840 Sense firmware and the
PC recorder. It does not change the canonical normalized IMU table in
`DATA_FORMAT.md`.

## Invariants

- Node identity is explicit in every sample packet: `A` = 1, `B` = 2.
- Node A is the thorax node and Node B is the upper-arm node for M1.
- Raw signed sensor counts and per-sample device timestamps are immutable.
- SI conversion and sensor-axis conversion happen explicitly in the host adapter.
- Each uninterrupted device clock uses one `clock_epoch`; no clock fit crosses an epoch.
- Sample and packet sequence counters are independent unsigned 32-bit counters with
  modulo wrap handling.
- Host receipt time is transport evidence, not sample time.
- Raw streams remain separate. Synchronization and resampling produce new processed
  artifacts and never overwrite raw data.
- The current hand-motion axis check for Node A is qualitative sign/channel evidence,
  not a calibration or a sensor-to-segment rotation matrix.

## BLE service

M1 uses one project-specific 128-bit GATT service per node:

| Item | UUID | Operation | Purpose |
|---|---|---|---|
| Service | `f7d20001-4b49-4e45-494d-552d53484c44` | discovery | KineIMU Shoulder M1 |
| Identity/config | `f7d20002-4b49-4e45-494d-552d53484c44` | read, indicate | node identity and active sensor configuration |
| Telemetry | `f7d20003-4b49-4e45-494d-552d53484c44` | notify | binary sample packets below |
| Clock exchange | `f7d20004-4b49-4e45-494d-552d53484c44` | write with response, indicate | timestamp-exchange messages |
| Status | `f7d20005-4b49-4e45-494d-552d53484c44` | read, indicate | counters, overflow and acquisition state |

The recorder must read and persist identity/config before enabling telemetry. A
configuration mismatch is a hard start failure, not an implicit conversion.
Discovery order, advertising name and host adapter enumeration never establish node
identity; the recorder accepts a connection only after the identity/config value agrees
with the expected A/B assignment and stable hardware device ID.

## Control-plane values

Identity/config, clock exchange and status use the fixed binary values below. All
integers are little-endian. Every value begins with `uint16 magic = 0x494b`,
`uint8 protocol_version = 1` and a `uint8 message_type`; its final four bytes are
CRC-32C over all preceding bytes. Reserved values are rejected. The executable
reference codec and literal golden vectors are in `kineimu_shoulder.io.m1_control`
and `tests/contracts/test_m1_control.py`.

### Identity/config: 97 bytes, message type 2

| Offset | Type | Field | v1 rule |
|---:|---|---|---|
| 0 | `uint16` | magic | `0x494b` |
| 2 | `uint8` | protocol version | `1` |
| 3 | `uint8` | message type | `2` |
| 4 | `uint8` | node ID | `1` = A, `2` = B |
| 5 | `uint8` | timestamp source | `1` = `mcu_drdy_isr`, `2` = `sensor_internal`, `3` = `reconstructed` |
| 6 | `uint8[3]` | firmware version | major, minor, patch |
| 9 | `uint8` | telemetry batch size | 1–4 samples |
| 10 | `uint32` | configuration generation | increments on every accepted configuration change |
| 14 | `uint32` | clock epoch | active telemetry epoch |
| 18 | `uint64` | boot ID | new nonzero nonce on every MCU boot |
| 26 | `uint64` | hardware device ID | nRF52840 FICR device identity, stable for the board |
| 34 | `uint8[20]` | firmware Git commit | raw 20-byte SHA-1 object ID; all-zero is forbidden in evidence runs |
| 54 | `uint32` | timer frequency, Hz | frequency underlying device timestamps |
| 58 | `uint32` | accelerometer ODR, mHz | 104 Hz is encoded as 104000 |
| 62 | `uint32` | gyroscope ODR, mHz | 104 Hz is encoded as 104000 |
| 66 | `uint32` | accelerometer range, mg | ±4 g is encoded as 4000 |
| 70 | `uint32` | gyroscope range, mdps | ±500°/s is encoded as 500000 |
| 74 | `uint8[19]` | sensor register snapshot | ordered list below |
| 93 | `uint32` | CRC-32C | covers bytes 0–92 |

The register snapshot order is fixed so filter, FIFO and interrupt configuration is
auditable rather than summarized ambiguously: `FIFO_CTRL1` (`0x06`), `FIFO_CTRL2`
(`0x07`), `FIFO_CTRL3` (`0x08`), `FIFO_CTRL4` (`0x09`), `FIFO_CTRL5` (`0x0a`),
`INT1_CTRL` (`0x0d`), `INT2_CTRL` (`0x0e`), `CTRL1_XL`–`CTRL10_C`
(`0x10`–`0x19`), `MD1_CFG` (`0x5e`) and `MD2_CFG` (`0x5f`). These are raw
register bytes. Persist their decoded meaning in the manifest's `filter_config` object
and preserve the raw identity/config value in the transport sidecar.

The hardware device ID integer is assembled as `(DEVICEID[1] << 32) | DEVICEID[0]`
before little-endian encoding. ODR/range fields deliberately use integer hardware-
configuration units at this firmware/adapter boundary; conversion to the canonical SI
sample table remains explicit on the host.

M1 does not change configuration while telemetry is active. A requested change stops
telemetry, increments `configuration_generation`, updates this characteristic by
indication and requires the recorder to re-read and accept it before a new capture.
The 97-byte value fits one ATT value at the required MTU 127.

### Clock exchange: message types 3 and 4

The host writes a 20-byte request with response:

| Offset | Type | Field | v1 rule |
|---:|---|---|---|
| 0 | `uint16` | magic | `0x494b` |
| 2 | `uint8` | protocol version | `1` |
| 3 | `uint8` | message type | `3` |
| 4 | `uint32` | transaction ID | unique among outstanding exchanges on this connection |
| 8 | `uint64` | host send time, ns | host monotonic time captured immediately before the write |
| 16 | `uint32` | CRC-32C | covers bytes 0–15 |

The device returns a 48-byte indication:

| Offset | Type | Field | v1 rule |
|---:|---|---|---|
| 0 | `uint16` | magic | `0x494b` |
| 2 | `uint8` | protocol version | `1` |
| 3 | `uint8` | message type | `4` |
| 4 | `uint32` | transaction ID | echoes the request |
| 8 | `uint64` | host send time, ns | echoes the request exactly |
| 16 | `uint64` | boot ID | must match identity/config |
| 24 | `uint32` | clock epoch | epoch containing both device timestamps |
| 28 | `uint64` | device receive time, µs | captured at entry to the GATT write callback |
| 36 | `uint64` | indication queued time, µs | captured immediately before indication submission |
| 44 | `uint32` | CRC-32C | covers bytes 0–43 |

The host records its receive time immediately when the matching indication callback
starts. It persists all four times, transaction/connection IDs and acceptance result in
the transport sidecar. Device callback/queue timestamps are not radio-air timestamps;
link scheduling and path asymmetry remain uncertainty terms. Two-way exchanges may
support a candidate clock map, but they do not replace the rigid-fixture held-out common
events required by `SYNC_PROTOCOL.md` and `M1_TIMING_BUDGET.md`.

### Status: 80 bytes, message type 5

| Offset | Type | Field | v1 rule |
|---:|---|---|---|
| 0 | `uint16` | magic | `0x494b` |
| 2 | `uint8` | protocol version | `1` |
| 3 | `uint8` | message type | `5` |
| 4 | `uint8` | node ID | must match identity/config and telemetry |
| 5 | `uint8` | acquisition state | `0` idle, `1` armed, `2` streaming, `3` error |
| 6 | `uint16` | status flags | defined below |
| 8 | `uint64` | boot ID | must match identity/config |
| 16 | `uint32` | clock epoch | current epoch |
| 20 | `uint32` | status sequence | increments for every generated status value |
| 24 | `uint32` | last sample sequence | `0xffffffff` if no sample has been acquired |
| 28 | `uint32` | last packet sequence | `0xffffffff` if no packet has been generated |
| 32 | `uint64` | samples acquired | cumulative in this boot |
| 40 | `uint64` | packets generated | cumulative in this boot |
| 48 | `uint32` | sensor FIFO overruns | cumulative in this boot |
| 52 | `uint32` | firmware queue overruns | cumulative in this boot |
| 56 | `uint32` | transport backpressure events | cumulative in this boot |
| 60 | `uint32` | samples dropped before packetization | cumulative in this boot |
| 64 | `uint32` | acquisition buffer high-water, samples | maximum occupied acquisition-buffer slots in this boot |
| 68 | `uint32` | transport queue high-water, packets | maximum occupied transport-queue slots in this boot |
| 72 | `uint32` | last error code | `0` when none; firmware error table is versioned with implementation |
| 76 | `uint32` | CRC-32C | covers bytes 0–75 |

Status flag bit 0 means sensor ready, bit 1 sampling active, bit 2 fatal error
latched and bit 3 one or more cumulative counters saturated. Bits 4–15 are reserved
and zero. Counters saturate rather than wrap; saturation prevents an M1 pass. The
recorder reads status before telemetry, records every indication, reads it again after
stopping, and reconciles cumulative counters with the raw packet/sample sequence audit.
An unexplained mismatch is not silently assigned to BLE loss.

## Telemetry packet

All integers are little-endian. The packet is an ATT notification value.

### Header: 16 bytes

| Offset | Type | Field | v1 rule |
|---:|---|---|---|
| 0 | `uint16` | magic | `0x494b` (`KI` bytes on wire) |
| 2 | `uint8` | protocol version | `1` |
| 3 | `uint8` | packet type | `1` = sample batch |
| 4 | `uint8` | node ID | `1` = A, `2` = B |
| 5 | `uint8` | sample count | 1–4 |
| 6 | `uint16` | packet flags | defined below |
| 8 | `uint32` | packet sequence | increments once per generated packet |
| 12 | `uint32` | clock epoch | changes after clock reset/discontinuity |

### Sample record: 26 bytes each

| Relative offset | Type | Field | v1 rule |
|---:|---|---|---|
| 0 | `uint32` | sample sequence | increments once per acquired sample |
| 4 | `uint64` | device time, µs | capture time in the declared clock domain |
| 12 | `uint16` | sample flags | defined below |
| 14 | `int16[3]` | acceleration raw | sensor register order X, Y, Z |
| 20 | `int16[3]` | angular-rate raw | sensor register order X, Y, Z |

The last four packet bytes are CRC-32C/Castagnoli over the header and all sample
records, encoded as little-endian `uint32`. The check value for ASCII
`123456789` is `0xe3069283`.

Packet flags:

- bit 0: sensor FIFO overrun observed since the prior packet;
- bit 1: firmware acquisition/transport queue overrun observed since the prior packet;
- bit 2: transport backpressure observed since the prior packet;
- bit 3: a sample discontinuity precedes the first record in this packet;
- bits 4–15: reserved and zero in v1.

Sample flags:

- bit 0: acceleration clipping detected;
- bit 1: angular-rate clipping detected;
- bit 2: timestamp reconstructed instead of captured at the declared sampling event;
- bits 3–15: reserved and zero in v1.

The executable reference codec is `kineimu_shoulder.io.m1_packet`. Its golden
one-sample packet is protected by contract tests.

## MTU and batching

Packet size is `20 + 26N` bytes for `N` samples. An ATT notification can carry
at most ATT MTU minus three bytes, so one sample requires ATT MTU 49 and four
samples require ATT MTU 127. The complete v1 control plane also includes 48-, 80-
and 97-byte values. M1 therefore requires negotiated ATT MTU at least 127 and uses
four-sample telemetry batches. If negotiation yields less than 127, the recorder
persists the MTU event and fails the start; v1 does not reduce the batch size, split
control values, truncate values or silently change layouts.

At configured 104 Hz and four samples per packet, the application payload is
3,224 bytes/s/node (124 bytes × 26 packets/s), or 6,448 bytes/s for two nodes,
excluding BLE overhead. This is a design calculation, not measured throughput.

## Device timestamp source

The identity/config characteristic declares exactly one source:

- `mcu_drdy_isr`: MCU monotonic timer captured in the sensor data-ready ISR;
- `sensor_internal`: LSM6DS3TR-C timestamp read with a documented latch rule;
- `reconstructed`: timestamp derived after the sampling event.

The initial Zephyr implementation target is `mcu_drdy_isr`. The selected in-tree
Zephyr driver does not currently expose the IMU timestamp or FIFO through its sensor
API, so `sensor_internal` requires an explicit reviewed driver extension. A timestamp
taken later in a deferred work handler is `reconstructed` and sets sample flag bit 2.
Its measured error must still satisfy `M1_TIMING_BUDGET.md` before M1 can pass.

## Raw capture files

Each node has its own append-only `.kimu` stream. Every received notification is
stored as:

``` text
uint32 payload_length
uint64 host_monotonic_ns
uint8[payload_length] payload_as_received
```

This outer capture record is little-endian. It preserves malformed packets for audit;
CRC validity and decode outcome are recorded in the transport-event sidecar. The
recorder must flush bounded buffers without modifying or replacing earlier records.
Valid telemetry values are 46–124 bytes. The outer framing parser uses a project hard
limit of 512 payload bytes and rejects a larger declared length before allocating or
waiting for that payload; short, zero-length and otherwise malformed values at or below
that limit are preserved and reported as decode errors.

Each node also has an append-only NDJSON transport-event sidecar. Every line includes:

- event type (`connect`, `connection_parameters`, `mtu`, `notify`, `decode_error`,
  `disconnect`, `reconnect`, `config`, `clock_request`, `clock_response`, or `status`);
- node ID, connection ID and host monotonic time;
- raw-stream byte offset and payload length for a notification;
- packet sequence/epoch/CRC result when decodable;
- explicit error/status details without silently repairing the raw payload.

`config`, `clock_request`, `clock_response` and `status` events preserve the exact
control value as lowercase hexadecimal plus decoded fields and CRC/decode outcome.
Clock-response events also record the host receive timestamp captured at callback entry.
Connection-parameter and MTU changes are recorded as events rather than overwritten by
one final summary value.

## Reset, wrap and disconnect

- Unsigned counter wrap is continuity when modulo arithmetic confirms it.
- A reboot, timer reset, manual clock reset or acquisition restart increments
  `clock_epoch` before the next sample.
- A BLE disconnect alone does not change the epoch if acquisition and its clock remain
  continuous. If either stops or continuity cannot be proven, the next data use a new epoch.
- The host records disconnect/reconnect boundaries and re-reads identity/config before
  accepting telemetry again.
- Duplicates and out-of-order packets are preserved and flagged. They are not silently
  dropped from the raw capture.

## Session manifest

The session manifest follows
`protocols/schemas/m1-session-manifest-0.1.schema.json`; a synthetic, non-evidence
example is in `protocols/examples/m1-session-manifest-0.1.example.json`.

It binds the two node identities/roles, hardware and firmware provenance, timestamp
source and initial epoch, active ODR/range/filter settings, raw stream and event-sidecar
paths/hashes, mounting protocol, calibration/alignment references and clock-mapping
artifacts. Unknown board revision, calibration or alignment is explicit `null`, never
an inferred value.

## Conversion to the canonical table

The host adapter converts raw counts using the persisted range/sensitivity and emits
the seven canonical columns in SI units. Optional raw columns may be copied verbatim.
Node identity, packet/sample counters, clock mapping and transport evidence remain
metadata/sidecars rather than silently extending the canonical table. Any resampling
creates a processed artifact with source hashes, target grid, interpolation method and
gap policy.
