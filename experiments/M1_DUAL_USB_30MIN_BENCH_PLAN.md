# M1 Dual USB 30-Minute Bench Plan

Status: **ready for the formal 30-minute run; it has not yet started**. The corrected 15-second pilot and direct-continuation smoke test passed on the two live boards. Decision basis: [ADR-009](../docs/adr/ADR-009-dual-usb-m1-bench-fallback.md). The prior BLE bench plan and all BLE raw evidence remain unchanged.

## Fixed setup

- Node A/thorax: USB serial `0000000000000001`, FICR hardware ID `0000000000000001`, image SHA-256 `C184CB89CB364C8908FB12AC3672F5C16BC1716E8020A72B976BE33FBBABBFA0`.
- Node B/upper arm: USB serial `0000000000000002`, FICR hardware ID `0000000000000002`, image SHA-256 `BE4A8829D0647388D9DB67E784CBB9558C64CFB967E03434DC281E3BE53A7401`.
- Both images: source commit `5f81e2e14a15cb1f379f3c2d16598c9c246b1904`, Zephyr v4.4.0, SDK 1.0.1, board `xiao_ble/nrf52840/sense`; byte-identical generated `.config` SHA-256 `E33B9EF61626DD7623C8A080C4682003E3E595B6D5ED260C06222A227D015A2D`. Node ID is the sole build selection.
- Both boards remain stationary and USB powered. Keep the current flashed application running. The runner resolves live COM ports by immutable USB serial, never by port order, and verifies the corrected pilot at `.cache/m1_usb_dual_pilot_20260925_02` (result SHA-256 `4F2955F8DE5DC14879F956461D40EB412586513F52A972068A70E130148D010F`) as the prior hardware-ID banner evidence. If either board is reset, reflashed or disconnected, create a fresh banner-verified pilot before this command.
- Use a new, absent external output directory. Preserve every failed attempt and never overwrite raw files.

## Fixed acquisition

- Scheduled simultaneous capture: **1,800 s**.
- IMU configuration: 104 Hz accelerometer and gyroscope, ±4 g, ±500°/s, four raw samples per v1 packet.
- The firmware reads and deliberately discards the first valid post-arm DRDY frame before issuing sample sequence zero, so a partial startup ODR interval cannot appear inside the recorded epoch. The USB identity preamble states this policy; all subsequent raw frames are preserved.
- Scheduled expectations: 187,200 samples and 46,800 packets per node; these are planning values, not measured counts or an automatic loss calculation.
- Before timed capture, the runner saves USB startup backlog in separate `*.preroll.usb.bin` files and starts both raw captures at complete packet boundaries. Pre-roll byte counts/hashes are recorded in each event sidecar. All bytes after `capture_start` are preserved unchanged. A bounded one-second end grace completes a partial USB packet; actual start/stop times and any grace remain in each event sidecar.
- No deliberate disconnect, callback delay, resampling, interpolation, raw repair, body mounting or motion stimulus.

## One command on the current live boards

```powershell
.\.venv\Scripts\python.exe experiments/m1_usb_dual_bench.py `
  --output-dir <external-data>\kineimu_m1_usb_30min_20260925_01 `
  --session-id m1-usb-30min-20260925-01 `
  --seconds 1800 `
  --firmware-a .cache\m1_usb_bench_build_a\zephyr\zephyr.uf2 `
  --firmware-b .cache\m1_usb_bench_build_b\zephyr\zephyr.uf2 `
  --firmware-source-commit 5f81e2e14a15cb1f379f3c2d16598c9c246b1904 `
  --identity-pilot-dir .cache\m1_usb_dual_pilot_20260925_02
```

The runner re-verifies the immutable pilot's live hardware-ID banners, A/B serial/port/image/source bindings and every pilot raw hash before creating the formal output directory. It preserves and hashes pre-roll USB bytes, then rejects missing or changed capture hashes, failed per-node parser/sequence QC, empty streams, short captures and overlap below 99.5%. It writes a run configuration and result in the new directory. A nonzero exit retains all partial artifacts.

## Read-only audit after capture

```powershell
.\.venv\Scripts\python.exe experiments/m1_bench_summary.py `
  --run-dir <external-data>\kineimu_m1_usb_30min_20260925_01 `
  --scheduled-seconds 1800 --configured-rate-hz 104 --samples-per-packet 4
```

Report exact run duration and overlap, image/source hashes, configured and device-time effective rates, expected/received counts, packet/sample sequence loss, malformed/framing errors, maximum device-sample and host-packet gaps, timestamp monotonicity, reset/epoch changes, USB byte-stream and sidecar hashes, and manifest integrity. Apply the acquisition stability limits in `protocols/M1_TIMING_BUDGET.md`. USB disconnect/reconnect and cumulative device status counters are not exposed by this staging app; report them as `not measured` rather than zero. Report pairwise clock offset/drift/residual as `not measured` or `inconclusive` unless independent common-event evidence exists. The BLE limitation remains separate.

The formal test is **not passed** until the 1,800-second physical capture and read-only audit exist.
