# Node A independent-counter software evidence — 2026-09-12

- Target: XIAO nRF52840 Sense / upstream Zephyr v4.4.0
- Scope: independent sample and packet sequence allocation, uint32 wrap, boot/reset
  initialization and clock-epoch transition
- Excluded: bounded queues, FIFO/overflow policy, v1 binary packet emission and
  physical-device counter delivery

## Contract behavior

The counter state has one unsigned 32-bit sample counter and one unsigned 32-bit
packet counter. Taking a sequence returns the current value and advances only its
own counter. Unsigned overflow therefore implements the frozen modulo-2^32 wrap.

`node_a_counters_start()` installs the caller-provided boot epoch and clears both
counters. This keeps selection/persistence of a new boot epoch outside the counter
primitive until boot identity and control-plane state are implemented.
`node_a_counters_reset_clock()` is the in-boot clock-reset transition boundary:
it increments the epoch and resets both counters before the next sample. The function
is called only while acquisition and packet generation are stopped.

After a successful coherent sensor read, the bring-up callback now attaches the
active epoch and next sample sequence before publishing the inspection snapshot.
The packet sequence allocator is independent and intentionally has no runtime caller
until the later packetizer slice.

## TDD evidence

The RED build used weak no-op/sentinel counter fallbacks. The six existing acquisition
and timestamp cases passed, while all four new counter cases failed for the expected
missing behavior: 6 passed, 4 failed, `PROJECT EXECUTION FAILED`.

The GREEN QEMU run passed 10/10 cases, including:

- interleaved sample/packet allocation proving independence;
- sample and packet transitions from `0xffffffff` to `0`;
- boot/start initialization with a caller-provided changed epoch;
- in-boot clock reset from epoch 41 to 42 with both next sequences returning zero.

A temporary mutation made packet allocation advance the sample counter. The suite
failed all four counter cases and retained all six earlier passes. The correct
implementation was restored and the final run passed 10/10 with
`PROJECT EXECUTION SUCCESSFUL`.

## Reference-board build

The clean `xiao_ble/nrf52840/sense` build used the pinned workspace and SDK recorded
in the parent README, with single-job compilation to avoid Windows archive-file races.

- FLASH: 64,740 B / 788 KiB (7.99%)
- RAM: 14,076 B / 256 KiB (5.37%)
- UF2: 129,536 bytes
- UF2 SHA-256: `14681d4a5bc9295af7d8eb5de717313fce325658015457f3d5b6d4439b9261a0`

The build proves reference-target compilation only. The artifact was not flashed in
this slice, so physical counter delivery is not claimed.
