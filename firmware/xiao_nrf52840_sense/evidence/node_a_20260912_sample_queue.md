# Node A bounded sample queue — 2026-09-12

## Scope and design

This software-only slice replaces the overwriteable latest-sample snapshot with a fixed-capacity
acquisition queue. It stops before sensor FIFO policy, raw-register capture, v1 packet assembly or
transport.

- Capacity: 16 complete `node_a_imu_sample` records. This is an engineering parameter selected as a
  small multiple of the four-sample v1 packet batch; it is not a measured throughput or loss result.
- Queue primitive: Zephyr `k_msgq`; the project does not reimplement FIFO indexing.
- Full policy: reject/drop the newest sample, preserving all already accepted samples.
- Loss visibility: each rejected sample saturating-increments both
  `firmware_queue_overruns` and `samples_dropped_before_packetization` and leaves its already-issued
  sample sequence absent from later output. `high_water_samples` records maximum occupancy and
  `counters_saturated` exposes loss-counter saturation.
- Concurrency: a wrapper mutex makes queue mutation and status accounting one operation. A semaphore
  provides a blocking consumer without performing sensor I/O in the GPIO ISR. The producer remains
  the LSM6DSL driver's deferred work callback.
- Preservation: queue entries contain the entire acquired sample, including ISR timestamp,
  `clock_epoch`, `sample_sequence`, acceleration and gyroscope values.

## TDD evidence

The initial RED executable needed `CONFIG_TEST_EXTRA_STACK_SIZE=2048` because the new test fixture
places the approximately 1 KiB fixed queue on the ztest thread stack. After that test-harness
correction, the six acquisition/timestamp tests and four counter tests passed while all four initial
queue tests failed against weak missing-implementation fallbacks: 10 passed, 4 failed.

The first GREEN implementation passed 14/14. A deliberate drop-oldest mutation then exposed that the
tests did not yet distinguish full-queue policies. An explicit preservation test was added while the
mutation was active; the run passed 14 and failed that one new test. Restoring drop-newest behavior
produced the final 15/15 result with `PROJECT EXECUTION SUCCESSFUL`.

The tests cover FIFO field preservation, ring-slot reuse, nonblocking empty behavior, exact full
boundary, drop-newest preservation, cumulative loss/high-water accounting and uint32 saturation.

## Reference build

A clean Zephyr v4.4.0 build for `xiao_ble/nrf52840/sense` completed with the pinned toolchain:

```text
FLASH: 65,072 B / 788 KiB (8.06%)
RAM:   15,096 B / 256 KiB (5.76%)
UF2:   130,560 bytes
SHA-256: 3a585a2caad598773d440178e14f017f40f904bd04d967d1371797540a2b91a7
```

The ELF section summary was `text=63572`, `data=1488`, `bss=13608`. The build directory was
`<firmware-workspace>\Toolchains\KineIMU-Zephyr-4.4.0\builds\node_a_queue_20260912` and remains outside the
repository.

The artifact was not flashed. Therefore this record makes no physical queue-pressure, loss, timing,
FIFO or transport claim.
