# M1 Dual USB 30-Minute Physical Bench Result — 2026-09-25

Disposition: **PASS for the predeclared M1 dual-node acquisition-stability gate**. This is a USB result only. The BLE dual-link limitation and formal V9 inconclusive result remain in force. Pairwise clock synchronization and cumulative device status counters were not measured by this run.

## Execution and immutable evidence

- Followed `M1_DUAL_USB_30MIN_BENCH_PLAN.md` once, without a planned disconnect or stimulus. Raw root: `<external-data>\kineimu_m1_usb_30min_20260925_01`; session `m1-usb-30min-20260925-01`. No replacement run was made.
- Host source HEAD at acquisition: `7de9397a299d9cfc9bbca8f64531edc885d26d31`. Corrected firmware source: `5f81e2e14a15cb1f379f3c2d16598c9c246b1904`, Zephyr v4.4.0 / SDK 1.0.1, XIAO nRF52840 Sense. A/B UF2 SHA-256: `C184CB89CB364C8908FB12AC3672F5C16BC1716E8020A72B976BE33FBBABBFA0` / `BE4A8829D0647388D9DB67E784CBB9558C64CFB967E03434DC281E3BE53A7401`. The generated `.config` SHA-256 was `E33B9EF61626DD7623C8A080C4682003E3E595B6D5ED260C06222A227D015A2D` for both.
- A (`0000000000000001`) resolved to COM5; B (`0000000000000002`) to COM8. The runner verified the prior banner-identified corrected pilot, its raw hashes, board serials, port mapping, images and source before creating the formal root. The 2 s continuation smoke and the formal stream have monotonically advancing device times across the 14,185 s gap, consistent with the same running applications; no reset is evidenced.
- The runner exited 0 with `ready=true`, `reasons=[]`, and two complete streams. Separate `*.kimu`, exact `*.usb.bin`, `*.events.ndjson`, and pre-capture `*.preroll.usb.bin` files were retained for each node. Each pre-roll held 4,684 bytes. No raw stream was repaired, filtered, interpolated, resampled, or overwritten.
- The subsequent `m1_bench_summary.py` read the completed raw capture and events. Its only write was a new `summary.json`. Its raw/event SHA-256 values matched the capture result, including the pre-roll hashes recorded in the event sidecars. An 11-entry `SHA256SUMS.txt` covers the result, configuration, summary, and eight per-node evidence files. Independent rehash found **11/11 matching, 0 missing, 0 unlisted**. Manifest SHA-256: `219A7A2CF07EB962EE3BF4755DC0A49D4CCF48447BB27BE1EDC08D55F5529EA7`.

| Evidence | Node A SHA-256 | Node B SHA-256 |
|---|---|---|
| Raw KIMU | `9e929d0ac025ea3b7322c3a48668e5f21c83fd7372ba920709c18f124f328db5` | `0ae3f1aa712b915bf5b0f4381cb2391b3619d41bbbc2fe81152f5d32c0e5bc68` |
| Exact USB bytes | `20969212d934605914ec6486805b235fb082567c827dca3e7027fb3eb81a47a2` | `53c5e17fa75fc2554983bc67c1d1f990d6250c68bed7e826f2c0d736a7456f08` |
| Events | `dfcce4bea7173d774068df3d6317e43a5ce6fc2b9475ff5ffc18b20d039af4aa` | `bfc04c59d8b4bf942a6890e661919d4a65596ebe2ef4d61e048b5bb05e6e0227` |
| Pre-roll USB bytes | `598720ce7527150197d4807a313f154af77ad82082fdb5308f005f1ab4a739c9` | `272035a7a4a0b9e9a15b517bc3f7d2497d9aa5d19f91ca97b0278aa25d98e378` |

## Read-only measurements and locked limits

The scheduled simultaneous capture was 1,800 s. First-to-last host packet spans were 1,799.875 s (A) and 1,799.812 s (B). Their directly observed common packet span was **1,799.781 s, or 99.9878%** of schedule; the minimum is 99.5%. The event `capture_stop` markers were written after post-capture QC and therefore include about 10 s of audit overhead; they are not treated as extra acquired data. First-to-last device sample spans were 1,800.106629 s / 1,800.054749 s. No second clock epoch occurred.

| Predeclared `M1_TIMING_BUDGET.md` acquisition measure | Limit | A | B | Decision |
|---|---:|---:|---:|---|
| Mean device-time output rate | 98.8–109.2 Hz | 104.311 Hz | 106.343 Hz | PASS |
| p99 absolute contiguous interval deviation | ≤1,000 µs | 30 µs | 31 µs | PASS |
| Maximum absolute contiguous interval deviation | ≤2,000 µs | 31 µs | 31 µs | PASS |
| Gap threshold, 1.5 × epoch median | Report intervals at/above threshold | Median 9,583 µs; max 9,614 µs | Median 9,399 µs; max 9,430 µs | No device-time gaps detected |
| Duplicate/out-of-order sample timestamps | 0 | 0 / 0 | 0 / 0 | PASS |
| Unaccounted sample loss | 0 | 0 sequence gaps | 0 sequence gaps | PASS |
| Sensor FIFO overrun packet flags | 0 | 0 observed | 0 observed | PASS for packet evidence |
| Firmware queue overrun packet flags | 0 | 0 observed | 0 observed | PASS for packet evidence |
| Accounted transport sample loss | ≤0.1% | 0 / 187,772 | 0 / 191,424 | PASS |
| Maximum consecutive missing samples | ≤4 | 0 | 0 | PASS |
| Unaccounted packet loss | 0 | 0 sequence gaps | 0 sequence gaps | PASS |
| Usable dual-node overlap | ≥99.5% | \- | 99.9878% shared | PASS |
| Unexplained reset/epoch change | 0 | 0 | 0 | PASS |

The planning counts were 46,800 packets / 187,200 samples per node at exactly 104 Hz. The received counts were **46,943 / 187,772** for A and **47,856 / 191,424** for B. Counts above plan reflect measured rates and are not negative loss. Both streams had zero malformed packets, framing errors, wrong-node or sequence errors, parser noise, host error events, and packet flag events. Host maximum inter-packet arrival gaps were 204 ms on each node; this transport-arrival statistic has no predeclared pass threshold and did not imply a device-time or sequence gap.

## Limits of the evidence and hardware decision

- This USB staging application exposes no cumulative sensor FIFO, firmware queue, or transport status counters. The zero *observed packet flags* above do not establish zero cumulative counters; those counters are **not measured**.
- USB disconnect/reconnect detection is not instrumented. Event sidecars contain no such event, but physical disconnect/reconnect count is **not measured**, not asserted to be zero. Continuous packets, one clock epoch, and no sequence loss support the uninterrupted acquisition result.
- No independent common events were introduced. Pairwise clock offset, relative drift, and held-out residual p95/maximum are **not measured**. The timing budget explicitly allows that classification for this acquisition-stability gate; it does not imply synchronization performance.
- Dual BLE throughput remains limited on this Windows/MediaTek controller: the V9 formal decision is **INCONCLUSIVE** under its locked gates, with repeated first-connected-link starvation in its raw data. This USB result cannot be transferred to BLE, nor does it establish a BLE root cause or repair.
- The predeclared rate, jitter, loss, overlap, integrity, and reset gates all pass. Under ADR-008/009 and `ACCEPTANCE_CRITERIA.md`, M1 physical acquisition validation is **DONE for the dual USB path**. Freeze the selected XIAO nRF52840 Sense boards, LSM6DS3TR-C configuration, and firmware/acquisition hardware path; reopen only for a documented firmware/acquisition defect or a new maintainer decision. M2 may begin without treating the unmeasured clock and BLE metrics as validated.

## Reproduction

The acquisition command is locked in `M1_DUAL_USB_30MIN_BENCH_PLAN.md` and must not be rerun into this root. The read-only raw audit was:

```powershell
.\.venv\Scripts\python.exe validation/acquisition_summary.py `
  --run-dir <external-data>\kineimu_m1_usb_30min_20260925_01 `
  --scheduled-seconds 1800 --configured-rate-hz 104 --samples-per-packet 4
```

The command generated a new `summary.json` after capture. Subsequent manifest verification only read files. `summary.json` SHA-256: `c202fd83b45d90be9f748692b304e9b86cdff6d237d3e70f0880ebc733ec3d3a`; acquisition result SHA-256: `31d325e6c034705c72e5b1f319b66484a60368c4832f74103045e5d91cd5575e`.
