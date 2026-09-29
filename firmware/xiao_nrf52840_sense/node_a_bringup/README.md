# Node A IMU bring-up

This is a minimal hardware-gate application for the XIAO nRF52840 Sense. It is
not the complete M1 production acquisition firmware; the v1 USB-C packet path
below is a single-node staging slice. The separate
[`m1_ble`](../m1_ble/README.md) application contains the BLE acquisition slice.

## Explicit logical-node selection

The source tree is shared by the two physical bring-up nodes. An unqualified
build defaults to Node A (`KINEIMU_NODE_ID=1`). Build Node B only with an
explicit CMake selection:

```powershell
& (Join-Path $venvScripts 'python.exe') -m west build -p always `
    -b 'xiao_ble/nrf52840/sense' `
    -d '.cache\node_b_bringup_build' `
    'firmware\xiao_nrf52840_sense\node_a_bringup' `
    -- -DKINEIMU_NODE_ID=2
```

The CMake gate accepts only `1` or `2`; the selected value controls the
diagnostic label and v1 packet node ID. Startup also prints both nRF52840 FICR
`DEVICEID` words and the M1 contract-order 64-bit hardware ID. The word
assembly is kept in a small platform-independent helper and is covered by the
QEMU acquisition test; the physical FICR values must still be recorded from
the connected nRF52840 board.

The XIAO board definition enables the LSM6DS3TR-C power rail during fixed
regulator initialization. In Zephyr 4.4.0, the fixed-regulator already-enabled
path does not apply the devicetree `startup-delay-us` value. The application
therefore marks only the IMU for deferred initialization, waits 50 ms from
entry to `main`, and calls `device_init()` before configuring 104 Hz sampling.
The 50 ms interval exceeds the sensor datasheet's typical 35 ms turn-on time;
it is a bring-up margin, not a measured production timing requirement.

Build from Windows PowerShell with the pinned workspace described in the
parent README:

```powershell
$workspaceRoot = '<firmware-workspace>\Toolchains\KineIMU-Zephyr-4.4.0'
$sdkRoot = '<firmware-workspace>\Toolchains\Zephyr-SDK-1.0.1'
$venvScripts = Join-Path $workspaceRoot '.venv\Scripts'
$env:PATH = "$venvScripts;$env:PATH"
$env:ZEPHYR_BASE = Join-Path $workspaceRoot 'zephyr'
$env:ZEPHYR_SDK_INSTALL_DIR = $sdkRoot
$env:ZEPHYR_TOOLCHAIN_VARIANT = 'zephyr'

& (Join-Path $venvScripts 'python.exe') -m west build -p always `
    -b 'xiao_ble/nrf52840/sense' `
    -d '.cache\node_a_bringup_build' `
    'firmware\xiao_nrf52840_sense\node_a_bringup'
```

## Configured data-ready acquisition slice

The first production-path slice replaces the 500 ms polling probe with explicit
accelerometer and gyroscope configuration at the frozen M1 values: 104 Hz,
plus or minus 4 g and plus or minus 500 degrees/s. It then registers Zephyr's
`SENSOR_TRIG_DATA_READY` callback. Configuration uses the Zephyr sensor API, but
each delivered event reads one contiguous 12-byte I2C burst beginning at
`OUTX_L_G` (`0x22`) and decodes the six little-endian signed 16-bit registers
into gyro counts (`0x22`–`0x27`) and accelerometer counts (`0x28`–`0x2d`).
Configuration failures stop setup before the trigger is armed.

The in-tree LSM6DSL driver invokes the application sensor callback from Zephyr's
global work queue after its GPIO ISR. The timestamp slice adds a second callback to
the same physical INT1 GPIO callback list. At that callback's entry it captures the
64-bit Zephyr monotonic uptime tick, then uses a spinlock to hand the value to the
deferred sensor callback. Tick-to-microsecond conversion and all I2C work stay outside
the ISR. The driver continues to own GPIO configuration and interrupt enable/disable.

The target build uses 32768 uptime ticks/s, giving an approximately 30.5 us timestamp
quantum by configuration. The callback now publishes complete timestamp/epoch/sequence-bearing
raw-count samples to a fixed 16-entry Zephyr message queue. Full queues reject the newest sample,
preserve accepted FIFO order and saturating-increment explicit firmware-overrun and
pre-packetization-drop counters. Capacity 16 is an unvalidated engineering parameter; sensor FIFO
policy and v1 binary packet emission remain separate steps.

The QEMU unit test under `tests/firmware/node_a_acquisition` exercises the real Zephyr
configuration API against a fake sensor driver and injects the raw I2C burst through a
test callback. It covers exact configured ranges, 104 Hz ODR, configuration ordering,
data-ready registration, driver-error propagation, little-endian signed register decoding,
gyro/accelerometer register order, atomic preservation on a bus error and the requested
register bit fields. The raw-boundary RED run passed 15 cases and failed the new mapping case
at the incorrect accelerometer offset; GREEN passed 16/16.

The timestamp extension added a Zephyr GPIO-emulator test. RED passed the five existing
cases and failed the new case at the `-ENOSYS` weak fallback; GREEN passed 6/6. A
temporary zero-timestamp mutation failed the strict-monotonic assertion before
restoration. The detailed software and build record is
[node_a_20260912_isr_timestamp.md](../evidence/node_a_20260912_isr_timestamp.md).

The independent-counter extension assigns a sample sequence only after a coherent
sensor read and exposes a separate packet-sequence allocator for the later packetizer.
Both are uint32 modulo counters. Start/reboot initialization installs a caller-provided
clock epoch and resets both counters; an in-boot clock reset advances the epoch and
atomically resets both sequence frontiers while acquisition is stopped. RED retained
the six prior passes and failed all four new cases; GREEN passed 10/10. A mutation that
made packet allocation advance the sample counter failed the four counter cases. See
[node_a_20260912_counters.md](../evidence/node_a_20260912_counters.md). The acquisition queue,
sensor FIFO/overflow policy and v1 binary packet emission remain separate steps at that point.

The bounded-queue extension preserves the complete timestamp/epoch/sequence-bearing raw-count sample
in FIFO order, supports blocking consumption, records occupancy high-water, and rejects the newest
sample at capacity with saturating loss counters. RED passed the 10 prior cases and failed all 4 initial
queue cases; GREEN passed 14/14. A deliberate drop-oldest mutation motivated and failed a fifth policy
test, and restoration passed 15/15. See
[node_a_20260912_sample_queue.md](../evidence/node_a_20260912_sample_queue.md). Sensor FIFO policy,
and v1 binary packet emission remain separate steps.

The raw boundary deliberately does not call `sensor_sample_fetch()` or `sensor_channel_get()` for
the sample payload, because those APIs expose converted `sensor_value` results. The staged burst
decode commits both raw axes only after a successful I2C transaction, so a bus error cannot publish
a partially updated sample. The resulting in-memory record is the packetizer's raw acquisition
input; it preserves the frozen raw signed-count, timestamp, epoch and sample-sequence boundary
without unit or axis conversion.

### Sample-level clipping flags

After the six signed counts are decoded, the same raw boundary sets the sample-level
`ACCEL_CLIPPED` and `GYRO_CLIPPED` bits. The criterion is deliberately a raw-code
full-scale-equivalent check, not an arbitrary percentage of full scale and not a claim that the
analog sensing element saturated. The [LSM6DS3TR-C datasheet](https://www.st.com/resource/en/datasheet/lsm6ds3tr-c.pdf)
specifies two's-complement 16-bit
outputs and nominal sensitivities of 0.122 mg/LSB at the configured +/-4 g and 17.50 mdps/LSB at
the configured +/-500 dps:

```text
accel: ceil(4,000 mg / 0.122 mg/LSB) = 32,787 counts > signed int16 range
       -> flag only +32,767 or -32,768, the two raw int16 endpoints
gyro:  ceil(500,000 mdps / 17.50 mdps/LSB) = 28,572 counts
       -> flag any axis >= +28,572 or <= -28,572
```

The integer implementation evaluates these limits without floating point and keeps the original
signed counts unchanged. A value one code inside a limit is not flagged; no `near-full-scale`
margin is implied. The bits describe an observed raw-code boundary for downstream QC. A
clipping/noise pilot on both physical nodes is still required to determine whether +/-4 g and
/-500 dps are suitable for the shoulder acquisition; passing these unit tests does not validate
the selected ranges or sensor noise in hardware.

## v1 USB-C packet staging

After the register audit and data-ready setup, Node A prints a short diagnostic
preamble and then emits consecutive frozen M1 v1 sample packets on the same USB
CDC console. The packetizer gathers up to four queued samples, writes the
16-byte header, 26-byte sample records and CRC-32C in little-endian order, and
does not append text after the first binary packet. Packet flags carry pending
sensor-FIFO and acquisition-queue overrun events once, plus a sequence
discontinuity marker. The direct raw path remains outside the packet encoder.

Use the host recorder from the repository root after installing its optional
capture dependency:

```powershell
uv sync --all-extras --frozen
uv run --all-extras --frozen python scripts/capture_m1_usb.py `
    --port COM5 `
    --seconds 10 `
    --output-prefix firmware/xiao_nrf52840_sense/evidence/node_a_20260913_usb_packet
```

The recorder preserves the complete CDC bytes as `.usb.bin`, writes validated
packet payloads using the frozen `.kimu` outer framing, and records parser/QC
events in `.events.ndjson`. This USB-C slice is for Node A transport bring-up;
it does not claim BLE identity/config, clock exchange, status, two-node
synchronization, sustained timing/loss performance or M1 completion.
The first physical capture used flashed UF2
`0cb593223cea93f22b6dc6b6fc1aa4431656177bab28f10defce55db0e4a7a98d`. The final
clean build after explicit queue-flag initialization hardening is UF2
`3dd80115deaabeb7e61111e29d930c06e9591df93664fe497fe0bc4e61e87b50`; it was
subsequently flashed to the same verified Node A and recaptured. See the final
artifact section in [node_a_20260913_usb_packet_v1.md](../evidence/node_a_20260913_usb_packet_v1.md).

## Sensor FIFO/overflow visibility

The Node A callback now also reads the LSM6DS3TR-C `FIFO_STATUS1`/`FIFO_STATUS2`
pair (`0x3a`/`0x3b`) as one direct two-byte I2C burst. The adapter preserves both
raw bytes and decodes `DIFF_FIFO[10:0]` plus watermark, overrun, full and empty
flags. An overrun assertion edge saturating-increments the separate
`sensor_fifo_overruns` diagnostic counter; repeated reads while the flag remains
asserted are one observed event. A status-read error is reported without dropping
the already coherent direct raw sample.

The in-tree Zephyr `st,lsm6dsl` driver initializes the sensor FIFO in bypass mode.
Because the current packet-ready payload path reads the output registers directly
and does not drain FIFO data, this slice intentionally leaves that mode unchanged.
It establishes an auditable status boundary and console visibility without claiming
that a FIFO is the active sample source. Physical FIFO pressure/overflow behavior,
including a deliberate overflow run, remains open for a later validation slice.
The QEMU tests and build record are in
[node_a_20260913_fifo_visibility.md](../evidence/node_a_20260913_fifo_visibility.md).

At startup the bring-up application reads and prints `WHO_AM_I`, `INT1_CTRL`,
`CTRL1_XL` and `CTRL2_G`, then stops if the requested identity, data-ready route,
ODR or range bits do not match. Because the board console is USB CDC, this
console-oriented probe follows Zephyr's CDC console pattern and waits for host
DTR before initialization so the one-shot audit is not discarded during USB
enumeration. This DTR dependency is specific to the bring-up probe, not a
production acquisition requirement.

On Windows, Zephyr SDK 1.0.1 QEMU requires MinGW runtime DLLs that are omitted by
the SDK archive ([upstream issue #1161](https://github.com/zephyrproject-rtos/sdk-ng/issues/1161)).
The verified local test run used MSYS2 20260611 with UCRT64 GCC runtime libraries
on `PATH`; these are host test tooling, not a project or firmware dependency.
The fresh full Twister run also used `QEMU_BIN_PATH` and `--timeout-multiplier 2`:
with the default 60-second monitor window, this verbose test's body cases can all
finish while the final `PROJECT EXECUTION SUCCESSFUL` marker is still draining
through the Windows named pipe. The final run reached that marker and reported
1/1 configurations and 16/16 cases passed; the multiplier is a host-harness
setting, not a firmware timing claim.

The current reference-board build completed with the pinned toolchain on 2026-09-12:
64,228 B FLASH, 14,008 B RAM and a 128,512-byte UF2. These numbers come from the
reproduction command above with build directory
`.cache/node_a_configured_acquisition_build`; they are compilation evidence only.
The generated UF2 SHA-256 is
`e8b64199fa248d24b60dd9badf04a19b8ce5567bdef87f7bd9cb4f30152f0b59`.
The DTR-wait build was flashed to the recorded Node A. Hardware readback returned
`WHO_AM_I=0x6a`, `INT1_CTRL=0x03`, `CTRL1_XL=0x48` and `CTRL2_G=0x44`, with the
audit reporting `match=1`. A six-second capture contained 598 complete sample
lines across a 5.719-second sample window (104.389 lines/s by host arrival).
This verifies configuration and physical data-ready delivery; USB-buffered host
arrival times are not ISR timing, jitter or loss evidence.

The ISR timestamp reference build completed with the pinned toolchain on 2026-09-12:
64,656 B FLASH and 14,072 B RAM, with a 129,536-byte UF2. Its SHA-256 is
`a2e244a146aacd4796950adceba1f2d5e67d40f89158b753bc46cd72ffd73ad3`.
The rehashed artifact was flashed to the recorded Node A identity. A 12-second COM5
capture contained 1,230 complete timestamped samples, zero non-increasing adjacent
timestamps and no `missing ISR timestamp` message. This verifies physical timestamp
delivery only; timing, jitter, latency and loss characterization remain open.

The independent-counter reference build completed with the same pinned toolchain on
2026-09-12: 64,740 B FLASH and 14,076 B RAM, with a 129,536-byte UF2. Its SHA-256 is
`14681d4a5bc9295af7d8eb5de717313fce325658015457f3d5b6d4439b9261a0`. This artifact
was not flashed; these are software-test and compilation results, not physical delivery
or loss-accounting evidence.

The bounded-queue reference build completed with the same pinned toolchain on 2026-09-12:
65,072 B FLASH and 15,096 B RAM, with a 130,560-byte UF2. Its SHA-256 is
`3a585a2caad598773d440178e14f017f40f904bd04d967d1371797540a2b91a7`. This artifact
was not flashed; queue-pressure and loss behavior have not been measured on hardware.

The raw signed-count reference build completed with the same pinned toolchain on 2026-09-12:
64,940 B FLASH and 14,584 B RAM, with a 130,048-byte UF2 from
`.cache/node_a_raw_reference_build`. Its SHA-256 is
`6e425364c41ecce058ccbf758b68325c34e45f038eae127d3733a855d865c773`.
The artifact was flashed to the recorded Node A after verifying the XIAO Sense bootloader
identity and re-enumerated on COM5. An eight-second CDC capture contained 824 lines matching
the raw sample format, with `sample_sequence=0` through `823`, zero sequence gaps and zero
non-increasing adjacent `timestamp_us` values. The first and last device timestamps were
32,427,154 and 40,312,591 us. This verifies physical raw-count delivery and short-capture
continuity only; it is not a FIFO-pressure, rate, jitter, loss or long-duration result.
See [node_a_20260912_raw_signed_counts.md](../evidence/node_a_20260912_raw_signed_counts.md).
