# Node A GPIO ISR timestamp software evidence — 2026-09-12

- Date/time and timezone: 2026-09-12 15:57–16:30 +08:00
- Logical node: A; Node B remained disconnected and unassigned
- Firmware baseline: Zephyr v4.4.0 / Zephyr SDK 1.0.1 / `xiao_ble/nrf52840/sense`
- Scope: timestamp capture only; no independent counters, bounded queue or v1 packet emission

## Contract boundary

The initial M1 source is `mcu_drdy_isr`: capture a monotonic MCU time at the
LSM6DS3TR-C INT1 GPIO interrupt and keep host arrival time separate. The project
callback is added to the same Zephyr GPIO callback list already used by the in-tree
LSM6DSL driver. Its first operation reads `k_uptime_ticks()` while still in the GPIO
callback. The driver continues to own pin configuration and interrupt enable/disable,
and continues to defer sensor I/O to the global work queue.

The ISR stores only the 64-bit tick value under a Zephyr spinlock. The deferred sensor
callback consumes it and converts it with `k_ticks_to_us_floor64()` before reading the
sample. This keeps conversion and I2C work outside the ISR. The XIAO build has
`CONFIG_SYS_CLOCK_TICKS_PER_SEC=32768`, so the timestamp quantum is about 30.5 us by
configuration (`1 s / 32768`), not a measured latency or jitter result.

## TDD record

- Baseline: the previous QEMU suite passed 5/5 before edits.
- RED: the new GPIO-emulator test passed the five existing cases and failed only when
  the weak timestamp attachment returned `-ENOSYS` (5 passed, 1 failed).
- GREEN: the test drives two rising edges through Zephyr's GPIO emulator, verifies no
  timestamp exists before an edge, brackets the callback timestamp with the same
  monotonic clock, consumes it once and verifies the second timestamp is strictly
  greater. The suite passed 6/6.
- Test-strength mutation: temporarily publishing zero ticks made only the new test fail
  with `timestamps were not strictly monotonic: 0 then 0 us`; the correct assignment
  was restored.
- A first GREEN attempt using `k_cycle_get_64()` exposed that the QEMU Cortex-M3 timer
  did not enable a 64-bit cycle counter. The implementation was corrected to the
  standard 64-bit Zephyr uptime-tick API; it retains 32768 Hz resolution on the target.

## Reference-board build

Reproduction command (PowerShell environment variables are described in the parent
firmware README):

```powershell
python -m west build -p always -b 'xiao_ble/nrf52840/sense' `
    -d '.cache/node_a_isr_timestamp_build' `
    'firmware/xiao_nrf52840_sense/node_a_bringup'
```

Result: build passed without compiler warnings.

- Flash: 64,656 B / 788 KiB (8.01%)
- RAM: 14,072 B / 256 KiB (5.37%)
- UF2 size: 129,536 bytes
- UF2 SHA-256: `a2e244a146aacd4796950adceba1f2d5e67d40f89158b753bc46cd72ffd73ad3`

These resource values and the hash come from the clean build directory above. They are
compile evidence, not a runtime benchmark.

## Physical delivery — 2026-09-12

Before flashing, the UF2 bootloader enumerated as volume `XIAO-SENSE`, board ID
`Seeed_XIAO_nRF52840_Sense`, VID/PID `2886:0045` and unique USB serial
`0000000000000001`. These values match the recorded Node A identity. The source UF2
was rehashed immediately before copying; its size was 129,536 bytes and SHA-256 was
`a2e244a146aacd4796950adceba1f2d5e67d40f89158b753bc46cd72ffd73ad3`.

After the copy, the bootloader volume disappeared and the same USB serial re-enumerated
with application VID/PID `2FE3:0004` on COM5. A 12-second CDC capture reported:

- `KineIMU Shoulder Node A: IMU init rc=0 ready=1`
- `Node A: IMU registers WHO_AM_I=0x6a INT1_CTRL=0x03 CTRL1_XL=0x48 CTRL2_G=0x44 match=1`
- `Node A: data-ready acquisition armed at 104 Hz, +/-4 g, +/-500 dps`
- 1,230 complete `timestamp_us=...` sample lines
- first/last timestamp: 54,046,417 us / 65,824,615 us
- strictly non-increasing adjacent timestamps: 0
- `missing ISR timestamp` occurrences: 0

Representative endpoints from the same capture were:

```text
timestamp_us=54046417 accel_m_s2=-0.380458,-5.587240,8.086543 gyro_rad_s=0.000000,0.000000,0.000000
timestamp_us=65824615 accel_m_s2=-0.398404,-5.612365,8.160721 gyro_rad_s=0.019242,-0.052839,0.037262
```

This short USB CDC observation proves that the flashed Node A artifact attaches the
timestamp callback and delivers increasing ISR-derived timestamps with the sampled
data. It is not a rate, jitter, latency or loss characterization: the latest-sample
snapshot is still overwriteable and no independent counters or bounded queue exist.

Result: PASS for the Node A GPIO ISR timestamp **software/TDD, reference build and
physical timestamp-delivery** slice. Independent counters, bounded buffering and v1
binary packet emission remain open and separate.
