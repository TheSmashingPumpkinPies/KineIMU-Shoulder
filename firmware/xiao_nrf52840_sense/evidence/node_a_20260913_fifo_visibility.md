# Node A sensor FIFO/overflow visibility evidence

Date: 2026-09-13 (Asia/Shanghai)

## Scope and boundary

This slice makes the LSM6DS3TR-C sensor FIFO status observable without changing
the packet-ready raw sample source. The existing data-ready callback still reads
the direct `OUTX_L_G`–`OUTZ_H_XL` register burst and publishes immutable signed
counts with the existing ISR timestamp, clock epoch, independent sample sequence
and fixed 16-entry drop-newest software queue.

The in-tree Zephyr `st,lsm6dsl` driver initializes `FIFO_CTRL5.FIFO_MODE` to
bypass. This slice intentionally does not enable a sensor FIFO that the current
raw-direct path would not drain. Therefore this is software status visibility,
not physical FIFO-pressure or overflow characterization.

## Adapter contract

`lsm6dsl_fifo.c` is the LSM6DS3TR-C-specific direct-I2C adapter:

- Input: one two-byte burst beginning at `FIFO_STATUS1` (`0x3a`).
- Output: both raw status bytes, `DIFF_FIFO[10:0]` as `unread_words`, and the
  watermark, overrun, full and empty flags from `FIFO_STATUS2`.
- Failure: a negative I2C result is returned and the destination snapshot is
  unchanged.
- Overrun accounting: the observer saturating-increments the contract's
  `sensor FIFO overruns` counter on each observed overrun assertion edge. A
  repeated read while the flag remains asserted is not counted again; a clear
  followed by a new assertion is a new observed event.
- Diagnostic policy: a status-read error is printed but does not discard a raw
  sample whose direct register read already succeeded.

The register meanings follow the [LSM6DS3TR-C datasheet](https://www.st.com/resource/en/datasheet/lsm6ds3tr-c.pdf).
The status snapshot is kept separate from the frozen v1 packet and control-value
encoders; packet flags and status transport remain later integration work.

## TDD evidence

The RED run added four tests against the weak missing-implementation fallbacks:
the two-byte register read/parse, atomic preservation on a bus error, assertion-
edge accounting and uint32 saturation. The existing 16 acquisition cases passed
and the four new cases failed, for 16/20 passed.

The GREEN run passed 20/20 cases in one QEMU configuration with no warnings.
The tests hand-check `DIFF_FIFO=0x534` and all four level flags, preserve a prior
snapshot on `-EIO`, reject repeated overrun-level reads as duplicates, count a
clear/reassert transition, and keep the cumulative counter at `UINT32_MAX`.

## Reference build

A clean Zephyr v4.4.0 build for `xiao_ble/nrf52840/sense` completed with the
pinned Zephyr SDK 1.0.1 toolchain:

```text
FLASH: 65,444 B / 788 KiB (8.11%)
RAM:   14,648 B / 256 KiB (5.59%)
UF2:   131,072 bytes
SHA-256: 80ce8231d4876a522dc2af7e8f3b40ae07c1798c02842ec8231268b8600b2752
```

The final build directory was `.cache/m1_fifo_reference_final_20260913`. The
artifact was not flashed, so this record contains no physical sensor-FIFO
overrun result.
