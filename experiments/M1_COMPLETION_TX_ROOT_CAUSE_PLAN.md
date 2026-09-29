# M1 completion-TX root-cause experiment plan

Plan date: 2026-09-21 (Asia/Shanghai)

Status: **LOCKED PRE-ACQUISITION PLAN.** This task only records the design. It does
not implement the request path or runner, build or flash firmware, connect to BLE,
create the data output directory, or collect data. This is a diagnostic experiment,
not an M1 acceptance run.

## Objective and selected branch

Test whether a peripheral-initiated BLE connection-parameter request changes the
negotiated link settings and reduces the dual-link TX completion bottleneck on the
current Windows central system.

The read-only Windows PnP enumeration found one physical Bluetooth controller:
MediaTek Bluetooth Adapter, USB hardware ID
`USB\VID_13D3&PID_3563&MI_00\7&1d754fa2&0&0000`. Its driver is
`oem134.inf`, MediaTek version `1.3.17.169` (2026-03-25). Other Bluetooth-class
entries were Windows enumerators, GATT services, or paired devices. There is no
second available USB BLE adapter to swap on this host, so the selected factor is
the connection-parameter request. This experiment will not change the PC, Windows
installation, controller, or driver.

The built diagnostic images' generated `.config` files also reveal
`CONFIG_BT_GAP_AUTO_UPDATE_CONN_PARAMS=y`. Zephyr enables this by default and
automatically sends its preferred-parameter update after 5 s when acting as a
peripheral. The same config advertises 30–50 ms, latency 0, and 420 ms as the
preferred tuple. Therefore those images do not provide a true
no-active-request OFF condition and are ineligible unchanged. The matched
experiment images must set
`CONFIG_BT_GAP_AUTO_UPDATE_CONN_PARAMS=n` in both modes. Keep
`CONFIG_BT_GAP_PERIPHERAL_PREF_PARAMS=y` and its existing advertised preference
identical in both modes; the Windows central may still initiate an update, which
will be measured from the actual negotiated tuple.

## One changed factor

The only treatment factor is whether the XIAO peripheral application actively
requests updated LE connection parameters after a BLE connection is established.
The setting is applied to both nodes at the start of each block; only connected
nodes issue a request.

| Setting | Per-connection behavior |
|---|---|
| OFF | Do not call `bt_conn_le_param_update()`. The common experiment build has Zephyr's automatic peripheral update disabled; the Windows central may still initiate or negotiate parameter changes. |
| ON | Call `bt_conn_le_param_update()` once for each connected node, requesting 15 ms minimum and maximum interval, latency 0, and 420 ms supervision timeout. Do not add an application retry loop. |

No connection-parameter, PHY, DLE, TX queue, completion-context, retry-delay,
sensor, packetization, host-disk, capture, or public-schema setting may change
between settings. Both modes use the same build configuration, including
`CONFIG_BT_GAP_AUTO_UPDATE_CONN_PARAMS=n`; this common control makes OFF mean no
peripheral-initiated request. The only OFF/ON difference is whether the
application calls the request API.

## Zephyr 4.4.0 API and value check

The frozen project platform is upstream Zephyr v4.4.0, commit
`684c9e8f32e4373a21098559f748f06915f950c9`, with Zephyr SDK 1.0.1.
Zephyr v4.4.0 declares `bt_conn_le_param_update()` and defines connection interval
fields in 1.25 ms units and supervision timeout in 10 ms units. Its GAP conversion
macros accept 7.5–4000 ms intervals and 100–32000 ms timeouts. The requested
values are exact multiples of both units:

- `BT_GAP_MS_TO_CONN_INTERVAL(15)` = 12 units = **15 ms**; use min = max = 12.
- latency = **0**.
- `BT_GAP_MS_TO_CONN_TIMEOUT(420)` = 42 units = **420 ms**.
- The Bluetooth Core timeout constraint is
  `timeout > 2 × (1 + latency) × interval`; here 420 ms > 30 ms. No subrating
  is requested or enabled by this experiment.

These values are representable and valid; **no substitute values are needed**.
Use the peripheral API after connection. A zero return from the API is only the
local call result; it does not prove that the central negotiated the requested
tuple. Record the API return and the actual parameters from the existing
`le_param_updated` callback / `bt_conn_get_info()` trace.

The current application already logs actual `interval_us`, `latency`, and
`supervision_timeout_us` from its `le_param_updated` callback. The current
diagnostic images do not call the request API, but their Zephyr auto-update
setting sends the GAP preferred parameters after the default **5000 ms** delay.
For both matched experiment images, disable only
`CONFIG_BT_GAP_AUTO_UPDATE_CONN_PARAMS`; retain
`CONFIG_BT_GAP_PERIPHERAL_PREF_PARAMS=y` and the current preferred values as a
common build setting. Keep `CONFIG_BT_CONN_PARAM_UPDATE_TIMEOUT=5000` unchanged.
Zephyr's peripheral API stores an application-selected tuple and sends it when
the 5 s peripheral update timer expires. ON calls the API once after each
selected link connects; OFF makes no call. The timer is permitted to expire in
both conditions, so each run has the same **10.0 s setup/settling interval after
the last selected link connects**, with notifications disabled. Then enable
notifications and start the shared 15.0 s capture window. If the requested tuple
is not observed by the end of the 10 s interval, record that fact and still
perform the scheduled capture; do not retry the condition.

Primary references:

- [Zephyr v4.4.0 `conn.h`: connection-parameter units](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/include/zephyr/bluetooth/conn.h#L42-L80)
- [Zephyr v4.4.0 `conn.h`: `bt_conn_le_param_update()` API](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/include/zephyr/bluetooth/conn.h#L1550-L1564)
- [Zephyr v4.4.0 `gap.h`: interval and timeout conversions/ranges](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/include/zephyr/bluetooth/gap.h#L317-L344)
- [Zephyr v4.4.0 peripheral parameter-update delay](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/subsys/bluetooth/host/Kconfig#L799-L812)
- [Zephyr v4.4.0 automatic peripheral update and preferred-parameter defaults](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/subsys/bluetooth/host/Kconfig.gatt#L212-L257)
- [Bluetooth Core Specification 6.0, LE connection interval and supervision timeout constraints](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-60/out/en/low-energy-controller/link-layer-specification.html)

## Firmware images, devices, and host lock

### Firmware image requirement

The existing completion-TX diagnostic source baseline is
`1f743d22596c53bb3ebda7050ac0d6563e6e5e4c`. Its recorded diagnostic UF2s were
built but not flashed and do not contain the parameter-request control. They are
not eligible for this experiment unchanged.

Before acquisition, implement one test-only runtime mode through the USB CDC
control stream. The host will set `conn_param_request=OFF` or
`conn_param_request=ON` while disconnected and receive an acknowledgment with
the node ID and selected mode. Both nodes receive and acknowledge each block
setting, including the node not used in a single-node condition. This control
path must not use a BLE write or change the public BLE/data schema.

Build one fixed image per node from the same post-change source commit:

| Node | Hardware / build identity | Image use |
|---|---|---|
| A | Seeed XIAO nRF52840 Sense; node ID 1; bootloader serial `0000000000000001`; target `xiao_ble/nrf52840/sense` | Same runtime-selectable image for all 16 runs |
| B | Seeed XIAO nRF52840 Sense; node ID 2; bootloader serial `0000000000000002`; target `xiao_ble/nrf52840/sense` | Same runtime-selectable image for all 16 runs |

Use Zephyr v4.4.0 / SDK 1.0.1 and retain the four-slot TX queue, eight ATT
completion contexts, 5 ms retry interval, completion-TX diagnostics, existing
104 Hz acquisition, and four-sample packetization. Set
`CONFIG_BT_GAP_AUTO_UPDATE_CONN_PARAMS=n` in both images, while keeping
`CONFIG_BT_GAP_PERIPHERAL_PREF_PARAMS=y` and all its values unchanged. The two
images may differ only by their node ID build definition. Keep both images
installed throughout the matrix; switch OFF/ON by the acknowledged USB CDC test
setting, not by reflashing.

The request-capable source commit and both UF2 SHA-256 values do not exist yet
because this is a plan-only task. They are a hard pre-acquisition gate: build and
record them, with the exact source commit, in the experiment's `matrix_config.json`
before any run. Abort before capture if the two images do not use the same source
commit and build settings apart from node ID. The last documented physical
retest used different images (source `893e9d3894f11c30862d6e34f569da3519ef2e83`,
Node A SHA-256 `A85F129B6E706633C7DEBB00F8B213B0879A90597768A0CA099AC77272A6D0BF`,
Node B SHA-256 `6EF7D171F9A662035E54D6F5265F74FCEB90FC628CFAFD1DFF0DAB10228FD964`);
do not use those images for this experiment.

### Devices and Windows central

Use only the same two identified boards and the same Windows host:

- Node A: bootloader serial `0000000000000001`, logical role A.
- Node B: bootloader serial `0000000000000002`, logical role B.
- Re-enumerate both serials and resolve CDC ports by serial before the experiment.
  COM5 for A and COM8 for B are the last recorded mappings, not fixed identities.
- Central system: Windows registry reports ProductName `Windows 10 Home China`,
  DisplayVersion `25H2`, build `26200.9457`; Python reports
  `Windows-10-10.0.26200-SP0`. Preserve the same machine, installation,
  MediaTek controller and driver.
- Host environment: project `.venv` Python 3.12.14, Bleak 3.0.2, existing
  Windows BLE backend. Current host repository HEAD is
  `b05a26d3a60df75498246a7a8548860d2714078f`.

The current `experiments/m1_ble_link_matrix.py` defines only two block orders;
passing four blocks to it would repeat those orders. Before acquisition, update
the host runner to emit this exact four-block schedule and record the new host
HEAD, runner SHA-256, OS/adapter/driver details, device serials, firmware image
hashes, and this plan's SHA-256 in the root configuration.

## Locked run order and timing

Conditions are:

- `a_only`: connect and record A only.
- `b_only`: connect and record B only.
- `dual_a_to_b`: connect A first, then B.
- `dual_b_to_a`: connect B first, then A.

Use the following four-condition Williams order. Each condition appears once in
each within-block position, and each distinct directed first-order transition
appears once across the four sequences.

| Block | Request | Sequence | Run 1 | Run 2 | Run 3 | Run 4 |
|---:|---|---|---|---|---|---|
| 1 | OFF | W1 | `a_only` | `b_only` | `dual_b_to_a` | `dual_a_to_b` |
| 2 | ON | W2 | `b_only` | `dual_a_to_b` | `a_only` | `dual_b_to_a` |
| 3 | ON | W4 | `dual_b_to_a` | `a_only` | `dual_a_to_b` | `b_only` |
| 4 | OFF | W3 | `dual_a_to_b` | `dual_b_to_a` | `b_only` | `a_only` |

This is 16 scheduled conditions, four per request setting and two repetitions
of each condition per setting. Each active window is exactly 15.0 s. Allow a
10.0 s fixed connection-parameter setup/settling interval before every active
window, in both settings. Disconnect after each run, then wait exactly 2.0 s
before beginning the next run's setup. Setup and connection time are outside the
15.0 s capture window. Use the existing 5 s connection-attempt timeout.

If a scheduled setup or capture fails, preserve its error and any partial output,
continue only in the predeclared order, and do not repeat or replace that
condition. Never reorder a later condition to compensate for a failure.

## Output root and immutable evidence

Use the new persistent output root
`<external-data>/kineimu_m1_ble_connparam_rootcause_20260921_01`. It does not exist at
plan time; do not create it until a future authorized acquisition. Require it to
be empty before the first run. Do not append to or overwrite an earlier
`<external-data>` result.

Copy this plan into the root and record its SHA-256. Preserve the existing
byte-exact BLE raw streams, per-run event sidecars, CDC captures, setup errors,
run results, host callback timing, and manifest/hash audit. Open raw streams
read-only during QC. Do not add transport diagnostics to the public data schema.

## Predeclared comparisons

For each block, compare each dual run with that block's same-node single-node
control. Report all 16 runs, not only aggregates.

- **Negotiated parameters:** log the local request call/result and actual
  interval, latency, and supervision timeout for every connected node. ON is
  expected to show 15 ms / 0 / 420 ms; OFF sends no local request and its actual
  tuple is observed, not assumed.
- **Completion age:** compare per-node median and p95 completion age. ON is
  expected to reduce completion age, especially for the node that was previously
  delayed by dual-link scheduling.
- **Retries:** compare exact `-ENOMEM` / `-EAGAIN` retry counts per active
  second and per notification submission. ON is expected to reduce retry rates.
- **Full-window pressure:** compare full-window event counts and wait time per
  active second and per submission. ON is expected to reduce both.
- **Throughput:** report valid packets per 15 s and packets/s per node; compare
  dual/single ratios within each block and first-connected/second-connected
  ratios. ON is expected to improve dual-link throughput and reduce connection-
  order bias. A-only and B-only remain controls under each setting.
- **Loss and quality:** retain enqueue/drop counters, packet/sample gaps,
  CRC-false events, decode/framing errors and setup errors. These are outcomes;
  never repair or discard raw data.

Use the host audit's per-run first/last diagnostic deltas, split by boot and
connection generation. Compare the two OFF blocks with the two ON blocks
descriptively; these are repeated measurements on the same two devices and host,
not independent samples. Do not use inferential tests or claim general support
for other adapters or central systems.

## Locked outcome labels

First report whether the manipulation was realized. It is realized only when
every ON link reports the requested 15 ms / 0 / 420 ms tuple and the corresponding
OFF links show no local request and a different negotiated tuple. If any ON
request is not observed or OFF already has the target tuple, the performance
comparison is **inconclusive**; report which link did not provide a treatment
contrast.

When a valid parameter contrast and complete data exist:

- **Supported:** all four ON dual-link runs meet the existing focused transport
  thresholds (each node's dual/same-block-single ratio at least 0.90 and
  first/second throughput ratio at least 0.90), with zero firmware TX enqueue
  drops and zero CRC/decode/framing errors. In both dual-link orders, both nodes
  must also show no worsening in the three mechanism metrics and at least two
  of completion-age p95, retry rate, and full-window wait rate must improve
  relative to the OFF medians. This supports this parameter change as a
  contributor; it does not close the remaining M1 gates.
- **Not supported:** the parameter contrast was realized and all required data
  are present, but both dual-link orders remain below the focused transport
  thresholds in both ON blocks; for both nodes and both orders the ON median
  throughput ratios do not exceed OFF medians, and at least two of the three
  mechanism metrics do not improve. This does not support the parameter request
  as the cause of the observed bottleneck on this setup.
- **Inconclusive:** any other result, including an unverified/unchanged
  negotiated tuple, missing or failed runs, incomplete diagnostics, or mixed
  outcome directions. Do not re-run failed conditions.

Regardless of label, this short matrix is not the 30-minute M1 bench, does not
validate clinical or shoulder metrics, and does not authorize starting M2.

## Exact next action

Implement and verify the test-only runtime mode control and four-block runner
schedule; build the two matching XIAO images and freeze their hashes. Stop before
physical flashing or data collection unless separately authorized.
