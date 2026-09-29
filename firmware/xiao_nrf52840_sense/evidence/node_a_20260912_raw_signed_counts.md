# Node A raw signed-count acquisition evidence

Date: 2026-09-12 (Asia/Shanghai)

## Scope

This is a short physical-delivery check for the Node A raw signed-count boundary.
It is not evidence for sensor FIFO behavior, queue-pressure capacity, calibrated
units, timing jitter, loss rate, or the M1 30-minute measurement gate.

The configuration path retains Zephyr's LSM6DS3TR-C sensor API for the frozen
104 Hz, ±4 g and ±500 dps settings. The sample path uses one direct I2C burst from
`0x22` through `0x2d`: gyro registers `0x22`–`0x27` followed by accelerometer
registers `0x28`–`0x2d`. Each pair is decoded as a little-endian signed 16-bit
count. Converted `sensor_value` results are not relabeled as raw data.

## Build and device identity

- Board: Seeed XIAO nRF52840 Sense, UF2 `Board-ID: Seeed_XIAO_nRF52840_Sense`.
- Bootloader volume: `XIAO-SENSE`, verified as drive `E:` immediately before flashing.
- Recorded Node A bootloader serial: `0000000000000001`.
- Build directory: `.cache/node_a_raw_reference_build`.
- FLASH: 64,940 B; RAM: 14,584 B.
- UF2 size: 130,048 bytes.
- UF2 SHA-256: `6e425364c41ecce058ccbf758b68325c34e45f038eae127d3733a855d865c773`.
- Application CDC port after flashing: `COM5`.

## Capture check

The port was opened at 115200 8N1 with DTR asserted. The application printed 824
nonempty raw sample lines during an eight-second read window. Every raw sample line
matched the expected signed-count format.

- `clock_epoch`: 0 for the capture.
- `sample_sequence`: 0 through 823, with zero observed gaps.
- `timestamp_us`: 32,427,154 through 40,312,591, with zero non-increasing adjacent values.
- First sample:

  ```text
  clock_epoch=0 sample_sequence=0 timestamp_us=32427154 accel_raw=433,-5426,6204 gyro_raw=0,0,0
  ```

- Last sample:

  ```text
  clock_epoch=0 sample_sequence=823 timestamp_us=40312591 accel_raw=394,-5407,6296 gyro_raw=48,-176,124
  ```

The sequence and timestamp checks were performed on the captured text in memory.
USB CDC output is a diagnostic stream, not the frozen v1 packet framing, and this
short run does not characterize sustained throughput or loss.
