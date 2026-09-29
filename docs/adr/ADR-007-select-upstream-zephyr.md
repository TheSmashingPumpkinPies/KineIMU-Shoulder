# Reference firmware platform

Status: Accepted. Upstream Zephyr v4.4.0 with Zephyr SDK 1.0.1 is the pinned
reference baseline; board target xiao_ble/nrf52840/sense and in-tree st,lsm6dsl
sensor compatibility path. nRF Connect SDK is not an active dependency.

Pin the upstream release tag, west module revisions, SDK distribution/checksum,
Python environment and build commands under [firmware](../../firmware/xiao_nrf52840_sense/README.md).
Do not vendor downloaded SDK/workspace or silently update versions. Nordic-only
APIs need a demonstrated requirement. Build examples do not establish physical
sampling, timing, throughput, loss, power or measurement validity; retain tests on
both reference boards and the documented dual-BLE limitation.
