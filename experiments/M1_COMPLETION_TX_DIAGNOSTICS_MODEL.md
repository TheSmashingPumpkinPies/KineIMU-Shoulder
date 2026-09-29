# M1 Completion TX Diagnostics Model

Date: 2026-09-20 (Asia/Shanghai)
Status: **runtime diagnostics implemented; focused QEMU 15/15 and full firmware 91/91 GREEN; Node A/B reference builds and host checks passed; committed-source image rebuild remains**

This note records the bounded firmware change from
`M1_COMPLETION_TX_ROOT_CAUSE_PLAN.md`. It does not change queue size, ATT
completion contexts, retry delay, BLE policy, or any public packet/GATT/session
schema.

## Existing ownership and trace behavior

- `node_a_ble_tx_queue` owns packet copies and tags each queued packet with its
  stream generation. Disconnect closes and flushes the queue and advances that
  generation. A dequeued packet is checked again before submission.
- `m1_ble_service.c` owns the fixed `CONFIG_BT_ATT_TX_COUNT` array of submission
  contexts. Each context owns its packet bytes, notify parameters, and delayed
  retry work. The `user_data` pointer refers to the containing context until
  the ATT callback owner is drained.
- A context enters the existing completion state before its initial work is
  scheduled. `-ENOMEM` and `-EAGAIN` cause a 5 ms delayed retry. The service
  retains that context while retries are pending.
- On disconnect, the service cancels active contexts, then schedules reclaim
  work. Reclaim synchronously cancels delayed submit work and only then returns
  the context slot. Queue generation checks prevent queued old stream packets
  from crossing a reconnect boundary.
- The queue generation starts at 1 and saturates at `UINT32_MAX`; reaching that
  value stops the queue rather than reusing a generation. It denotes a stream
  invalidation epoch, not necessarily one physical BLE connection: closing the
  telemetry CCC also calls the queue disconnect path.

The active CDC fields `notify_calls`, `notify_last_duration`,
`notify_max_duration`, and `notify_total_duration` are terminal context
statistics. `tx_note_notify()` increments `notify_calls` when a context
completes, fails, or is canceled. It is not called for each actual
`bt_gatt_notify_cb()` invocation. A transient return can therefore produce
multiple GATT calls but one `notify_calls` increment; cancellation and work
scheduling failures can increment it without any GATT call.

The legacy active duration starts when the worker claims a completion context, before
the first work schedule. It ends at completion or terminal cleanup, so it
includes scheduling, retry delay, and any retry attempts. It is not the duration
of the `bt_gatt_notify_cb()` call and is not the accepted submission to
completion age. The older acquisition trace helper is separate: its
`notify_calls` counts calls to `node_a_acquisition_trace_note_notify_duration()`
and its `notify_max_duration` stores the maximum supplied value. That helper
currently has no production call site.

In the active path, `tx_submit_notify()` performs connection, CCC, MTU, and
payload checks before calling `bt_gatt_notify_cb()`. Those early errors are not
returns from the Zephyr API and do not enter its return-code table. If retry
scheduling fails, the legacy terminal result remains `-EIO`, while the
diagnostic snapshot preserves the exact work scheduler result separately.

The implementation in `m1_ble_tx_diagnostics.c` protects every counter and
per-context diagnostic state transition with one spinlock. Completion ownership
still uses the existing per-context completion lock. The service captures the
accepted/completion generation before changing ownership, and only returns a
context to the worker after diagnostic ownership has also been updated.
Diagnostics are copied into the existing CDC trace once per status interval;
there is no per-packet output.

The Zephyr GATT server API documents `bt_gatt_notify_cb()` as returning zero on
success and a negative error otherwise; success queues the notification and
the callback runs later in thread context. Because this call is made from the
system workqueue, resource exhaustion is returned immediately. Completion
means the stack's send callback ran; it is not an application level receipt or
proof that the host recorder stored the data. See the
[Zephyr 4.4 GATT server API](https://docs.zephyrproject.org/4.4.0/doxygen/html/group__bt__gatt__server.html).

## Diagnostic data contract

`m1_ble_tx_diagnostics.h` contains the bounded snapshot and per-submission
state, and `m1_ble_tx_diagnostics.c` implements its transitions.

| Field or event | Contract |
|---|---|
| `notify_submit_calls` | Count only actual invocations of `bt_gatt_notify_cb()`, once per returned call, including retry invocations. Do not count preflight rejection or `k_work_reschedule()`. |
| `notify_accepted` | Count calls returning exactly zero. The API contract has no positive success return. |
| `notify_final_failures` | Count a terminal pre-accept submission failure: preflight rejection, non-transient GATT error, or initial/retry work-scheduling failure. Temporary `-ENOMEM` / `-EAGAIN` returns alone do not count. |
| `notify_packet_drops` | Count definite losses after queue dequeue. A terminal pre-accept failure increments this separately from its failure cause; worker discard and pre-accept cancellation increment only the drop count. Reclaim counts a canceled context as a drop only after submit work drains and no call returned zero. Queue enqueue/disconnect/stop losses remain in their existing separate counters. Cancellation after acceptance is not a definite drop because delivery outcome is unknown. |
| Exact return code | Count each exact signed return code in a fixed first-seen table of 16 unique codes. Always preserve `notify_last_return_code`. If a new code arrives after the table is full, increment `notify_return_code_overflow`; do not replace an existing bucket. |
| `notify_ret_enomem`, `notify_ret_eagain` | Count actual GATT calls returning each transient error, even if the subsequent retry schedule fails. Scheduler errors are kept separate. |
| `retry_attempts` | Count actual GATT calls after the first call for a context. A scheduled retry that never runs is not an attempt. |
| Schedule failures | Count initial and retry `k_work_reschedule()` failures separately and preserve each last exact work return code. They do not increment GATT call or retry counts. |
| Current and peak in-flight | A notification becomes in-flight only on return code zero. Decrement once on its completion callback or cancellation. A pre-accept context waiting or retrying is not counted in-flight. Peak is retained for the boot. |
| Completion window wait | Count one event when queued work is waiting while every completion context is owned. Repeated enqueue while the same wait episode is active does not create more events. Stop its timer when a context slot becomes available. Keep a boot cumulative wait total in microseconds. |
| Completion age | Start at the cycle timestamp immediately after a zero return from the GATT API. Stop at the matching callback. Store count, last, min, max, saturating total, and eight fixed microsecond histogram bins: `[0,1000)`, `[1000,2500)`, `[2500,5000)`, `[5000,10000)`, `[10000,25000)`, `[25000,50000)`, `[50000,100000)`, and `[100000,∞)`. Cancellation and stale callbacks do not enter this histogram. |
| Generation callback guard | Store the accepted generation with the submission. Compare a callback's captured generation to that accepted generation before changing in-flight state or completion age. A stale generation increments its own counter and cannot complete or decrement a newer submission. A callback after cancellation is counted separately and is idempotent. |
| Counter saturation | All unsigned counters saturate at their integer maximum; 64 bit duration totals saturate at `UINT64_MAX`. The saturation flag is sticky until reboot. No rejected, duplicate, stale, or canceled callback can underflow current in-flight. |

Cycle durations use unsigned 32 bit subtraction to preserve one counter wrap,
then convert with the initialized cycle frequency. Completion and wait totals
are device microseconds, not host arrival time.

The data is per device/node and cumulative for one boot. Initialization starts
the counters at zero and stores the existing identity `boot_id`. Updating the
stream generation changes only its snapshot label; it does not reset totals,
histogram, or peak. A host capture run is a delta between two CDC snapshots with
the same boot ID and connection generation. Split a run if either changes. If
any source counter saturated, report its run delta as a lower bound, not an exact
difference. No capture start or stop command is added to BLE or the public
schema.

## RED and GREEN tests

The QEMU Ztest contract in `tests/firmware/node_a_acquisition/src/test_ble_tx_diagnostics.c`
covers:

- accepted submission and completion age;
- retry success after both `-ENOMEM` and `-EAGAIN`, exact return code counts,
  and actual retry attempts;
- nontransient errors and bounded return code table overflow;
- initial and retry schedule failure without inventing a GATT call;
- cancellation, reclaim, reconnect generation, stale and post-cancel callbacks;
- cycle wrap, histogram boundaries, and eight independent contexts;
- one count per full-window wait episode and cumulative wait duration;
- boot cumulative counters, snapshot run deltas, saturation, and zero lower
  bounds.

The round-two behavioral RED used a temporary isolated Ztest app under ignored
`.cache/tx-diag-red-only` so the shared 88-case app could not time out before
reaching the new suite. With no-op link stubs, QEMU reached
`test_accepted_submission_counts_call_and_completion_age` and failed at
`test_ble_tx_diagnostics.c:53`: `snapshot.notify_submit_calls` was `0` instead
of the expected `1`. The Twister log is in
`.cache/tx-diag-red-only-run/twister.log`. This is a runtime assertion RED,
not only an undefined-symbol link result. An earlier link-failure RED remains
in `.cache/tx-diag-red-final` as the first checkpoint.

Pinned Zephyr 4.4.0 / SDK 1.0.1 focused GREEN run:

```powershell
$toolchainRoot = '<firmware-workspace>\Toolchains\KineIMU-Zephyr-4.4.0'
$sdkRoot = '<firmware-workspace>\Toolchains\Zephyr-SDK-1.0.1'
$venvScripts = Join-Path $toolchainRoot '.venv\Scripts'
$qemuRoot = Join-Path $sdkRoot 'hosttools\qemu'
$env:PATH = "$venvScripts;$qemuRoot;<system-root>\Program Files\qemu;<system-root>\msys64\ucrt64\bin;$env:PATH"
$env:ZEPHYR_BASE = Join-Path $toolchainRoot 'zephyr'
$env:ZEPHYR_SDK_INSTALL_DIR = $sdkRoot
$env:ZEPHYR_TOOLCHAIN_VARIANT = 'zephyr'
$env:QEMU_BIN_PATH = $qemuRoot
Push-Location $env:ZEPHYR_BASE
& (Join-Path $venvScripts 'python.exe') -m west twister `
  -T .\.cache\tx-diag-red-only `
  -p qemu_cortex_m3 `
  --timeout-multiplier 10 `
  -O .\.cache\tx-diag-green-final -v
Pop-Location
```

The first isolated implementation pass passed **13/13 Ztests** on
`qemu_cortex_m3/ti_lm3s6965` (`.cache/tx-diag-green-final`). Review then exposed
a service-level race where the callback could release a slot before the
submitter recorded the GATT return. The implementation now defers slot release
until both events are accounted for, and handles cancellation concurrent with
an accepted return.

Latest isolated diagnostics run passed **15/15 Ztests** on
`qemu_cortex_m3/ti_lm3s6965`; log:
`.cache/tx-diag-callback-race-correct-qemu/twister.log`. It includes dedicated
early-callback and cancel/acceptance-race cases. The final-guard full firmware
run passed **91/91 test cases**, zero failures/errors/warnings in 533.01 s;
log: `.cache/tx-diag-firmware-final-guard/twister.log`.

The full host checks passed against the final guard: pytest 107/107, Ruff all
checks, and mypy with no issues in 13 source files.

Implementation commit `1f743d22596c53bb3ebda7050ac0d6563e6e5e4c` was clean-built
for Node A and Node B using Zephyr 4.4.0 / SDK 1.0.1 on
`xiao_ble/nrf52840/sense`; node IDs are 1 and 2. The generated compiler
definitions contain that full commit hash.

| Image | baseline text/data/bss | final text/data/bss | delta text/data/bss | flash delta | RAM delta | UF2 size | SHA-256 |
|---|---:|---:|---:|---:|---:|---:|---|
| Node A | 147744/2936/44037 | 151360/2936/44989 | +3616/0/+952 | +3616 | +952 | 308736 | `DDB1C0F29B76F790680895EEA4D5D47F2BB689BEF866B5CE10C040FD7931ACA7` |
| Node B | 147752/2936/44037 | 151368/2936/44989 | +3616/0/+952 | +3616 | +952 | 308736 | `C1A41422A86BBBC57CE0C230AD461832030D3DE5F1874BB3F31216CD540040C3` |

The status summary function `publish_status_if_due` has a 1060 B stack frame,
up from 212 B in the preserved baseline (+848 B);
`CONFIG_MAIN_STACK_SIZE` remains 4096 B. The per-image static resource
increase is 3616 B flash and 952 B RAM, with UF2 size +7168 B against baseline.
CMake did not find DTC during optional discovery, but both builds completed
and generated ELF and UF2 images. No device flashing or physical collection
was performed.
