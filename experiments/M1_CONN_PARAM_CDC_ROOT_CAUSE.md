# M1 CDC Control Receive Root Cause

Date: 2026-09-21 (Asia/Shanghai)
Scope: experiment-only USB CDC control path; no public BLE or data schema changes.

## Finding

The host-to-device control failure is caused by the experiment application using
`uart_poll_in()` without ever enabling UART RX interrupts. In Zephyr v4.4.0's
USB device-next CDC ACM driver, `uart_poll_in()` only removes bytes already in
the driver's RX ring. It does not arm the USB bulk-OUT endpoint when that ring
is empty. The first bulk-OUT request is submitted by the RX work item, which is
scheduled by `uart_irq_rx_enable()` (or by a later RX completion after that
first request exists). No component in the application calls
`uart_irq_rx_enable()` or registers an RX IRQ callback, so the host's CDC write
cannot enter the firmware RX ring and the write times out.

The device-to-host CDC log remains functional because it uses the independent
TX path: `printk()` reaches `uart_poll_out()`, which enqueues to the TX ring and
schedules TX work. TX does not depend on the RX interrupt-enabled state.

Increasing the host `write_timeout` only waits longer for the same unarmed OUT
transfer. It cannot submit the firmware-side bulk-OUT request or make
`uart_poll_in()` receive bytes.

## Evidence

- The old matrix report records 8/8 mode-control writes as
  `SerialTimeoutException: Write timeout`, while firmware CDC logs were
  captured in the same run. See
  [the root-cause matrix report](M1_CONN_PARAM_ROOT_CAUSE_RESULT_20260921.md).
- The pre-flash record identifies generated configs at
  `<external-root>\zbuild\kineimu_m1_ble_connparam_rootcause_node_{a,b}\zephyr\.config`.
  Both files are 57,969 bytes and have SHA-256
  `0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69`.
  Each enables `CONFIG_USB_DEVICE_STACK_NEXT=y`,
  `CONFIG_UART_INTERRUPT_DRIVEN=y`, and `CONFIG_UART_CONSOLE=y`.
- Application source at
  `firmware/xiao_nrf52840_sense/m1_ble/src/main.c:105` only polls with
  `uart_poll_in()`. A repository search found no application call to
  `uart_irq_rx_enable()`, `uart_irq_callback_user_data_set()`, or
  `uart_fifo_read()`; the bring-up app's `uart_poll_out()` is TX-only.
- In the pinned Zephyr v4.4.0 source
  `subsys/usb/device_next/class/usbd_cdc_acm.c`, class enable (around line 351)
  starts RX only when the RX-IRQ-enabled bit is set; RX enable (around line
  745) schedules the RX work; that work allocates and enqueues a bulk-OUT
  request (around lines 682–722). A completed OUT request copies bytes into
  the RX ring and re-arms the next request (around lines 307–318).
- The driver's `cdc_acm_poll_in()` (around lines 972–988) returns `-1` for an
  empty RX ring; only after consuming an existing byte does it schedule more
  RX work. Its independent `cdc_acm_poll_out()` path (around lines 991–1014)
  schedules TX work.

The source tree is Zephyr v4.4.0, commit
`684c9e8f32e4373a21098559f748f06915f950c9`, recorded by the pre-flash build
provenance. This confirms the supplied root-cause hypothesis; implementation
can proceed with an interrupt-driven, bounded application RX layer.

## Scope note

Node A's `callback=2`, `raw_try=0` acquisition anomaly is independent of CDC
control and remains a separate hard gate. No formal matrix may run until both
nodes pass their individual acquisition smoke tests.
