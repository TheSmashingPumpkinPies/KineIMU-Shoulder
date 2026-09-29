# M1 active BLE link-count root-cause experiment — V9

Status: predeclared V9 plan; lock it with its matching runner,
independent auditor, tests, and hardware identity pins in one commit before any
acquisition starts. The commit does not make this an M1 acceptance, a 30-minute
bench, a hardware freeze, or an M2 start.

## Predecessor attempts and operator interaction

V7's separate root <external-data>/kineimu_m1_root_cause_formal_v7_20260924_01
was consumed by a terminal-launch interruption. Its control log contains one
scheduled start for run 1 (a_only), but there is no cold-reset confirmation,
BLE/CDC/KIMU/TX capture, matrix_result.json, or hash manifest. This provides
no throughput outcome and is not a completed condition or usable replication.
Keep that root unchanged.

V8's separate root
`<external-data>/kineimu_m1_root_cause_formal_v8_20260924_01` was also consumed and
must remain unchanged. Its first scheduled condition received the required
physical reset and USB identities, then stopped before BLE when the runner sent
fixed OFF before either CDC control client had completed HELLO/READY. Both full
CDC captures contain only 238 bytes; there are no KIMU streams, event sidecars,
15-second capture markers, or TX diagnostics. V8's independent audit is
INCONCLUSIVE (`integrity_valid=false`); its manifest SHA-256 is
`2C88F9ED42450AE0ED0718E4368233EC2C264F7B5D0A6B1BAC7D680984722319` and its
independent report SHA-256 is
`78F3B2AECAA349B998D5EE334AC23E5BA0F9DC24ACC9B3DC2E388381FA52DB0A`. No V8
throughput result is retained or inferred. V9 uses a new root and corrects the
runner order by requiring READY from both boards before taking CDC boundaries
and before sending fixed OFF. V9 also stores `require_pristine_start` as the
boolean the independent auditor requires.

For every reset gate, the runner must remain open at its dedicated persistent
live acquisition prompt. The operator physically removes power/USB from both
boards for at least five seconds, reconnects them, then confirms the reset in
the Codex chat. The agent enters the exact run token into the still-live
acquisition session. Never type the token at a PowerShell command prompt. If
that session is lost, or the prompt/condition no longer matches, stop and leave
the V9 root consumed; do not restart or substitute a condition.

The V9 gate regression is covered by focused tests: both nodes must complete
HELLO/READY before the runner cuts the run-local CDC streams or sends OFF, and
the independent auditor rejects missing, duplicate, failed, or out-of-order
READY/boundary/OFF records. The V8 scripts, raw directory, manifest, and
INCONCLUSIVE report are not edited.

## Question and scope

Test whether assigning two simultaneous BLE links, rather than one link, causes
a repeatable telemetry-throughput deficit on the current two-node/current-Windows
combination. The V6 cold-start precheck passed the one-link versus two-link
manipulation and evidence-integrity gates. V6 is screening evidence only; its
one dual run does not establish a causal effect.

V2's local 15 ms connection-parameter request remains unidentifiable in the
current combination because its ON and OFF windows converged to the same
`15 ms / 0 / 420 ms` tuple. V9 does not retry that intervention. Every V9
capture keeps the firmware's local connection-parameter request mode OFF. The
Windows central may still negotiate or update parameters; every complete
connection and parameter callback is recorded, and callback presence alone is
not treated as evidence of who initiated an update.

The treatment is **active BLE link count**. No other factor is changed. Results
apply only to the locked boards, firmware images, Windows host, and adapter.
This design can identify an active-link-count effect in that combination. It
cannot by itself separate Windows central/controller scheduling from peripheral
Zephyr/Bluetooth resource behavior.

## Locked hardware and software inputs

| Item | Locked value |
| --- | --- |
| Node A | Seeed XIAO nRF52840 Sense; application node 1; hardware ID `1`; bootloader USB serial `0000000000000001`; BLE address `02:00:00:00:00:01` |
| Node B | Seeed XIAO nRF52840 Sense; application node 2; hardware ID `2`; bootloader USB serial `0000000000000002`; BLE address `02:00:00:00:00:02` |
| Firmware source | `270911756c227a20feb18df71edad7ad4544aedb` |
| Node A UF2 SHA-256 | `226B77FCEA1054022DA9F0E9884D3297245050A88156CE2EAD7A9177B4177380` |
| Node B UF2 SHA-256 | `6B38472B703D9B102767A1823BC34876EE24B0AA67AA328E346F1312B8525B32` |
| Generated A/B `.config` SHA-256 | `0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69` (byte-identical) |
| Build | `xiao_ble/nrf52840/sense`, Zephyr v4.4.0, SDK 1.0.1; 4 acquisition queue slots; 8 ATT TX contexts; completion-driven notification TX |
| Acquisition | M1 104 Hz; four raw samples per notification; public KIMU format unchanged |
| BLE link | MTU 127 required and recorded for every connected node/run |
| Host | Windows 11 build `10.0.26200`; MediaTek Bluetooth Adapter, USB instance prefix `USB\VID_13D3&PID_3563&MI_00`, driver `oem134.inf` version `1.3.17.169`; no host/adapter substitution |
| Local parameter mode | OFF before every condition and retained OFF through every capture |
| Per-run timing | 10 s settle from firmware connected events; explicit 15.000 s capture; 2 s minimum rest after disconnect |
| Connection/GATT setup bound | 30 s |

The V6 precheck roots were independently re-audited from raw streams and
sidecars before this plan was locked. The fresh read-only pair audit passed with
no prior audit report used; its output SHA-256 is
`0FB442DC725F05210B6B73CA89FF56061CC9995D02FB07EC9E3375E324C0C35A`. The
A-only and dual A-to-B manifests each cover every file and pass verification:
A-only has 24 entries and manifest
SHA-256 624253D0386CB41F09BD86BB23A092178BD5FB8711A992FD7E48E3AC2436FD75;
dual A-to-B has 27 entries and manifest SHA-256
3E69E3EC628822A2C0539940DFB5B65689F5549A3B857D24C72EF5A25B41B7F2. Direct
pre-notify status events identify distinct V6 boot IDs A-only/A=12288373895513561913,
dual/A=7701146763957617505, and dual/B=4936689328756888443. The two raw
conditions independently realize one and two simultaneous links, respectively;
both have exact 15-second capture boundaries, complete connection/parameter
event timing, required board identity and MTU, TX diagnostics, successful OFF
cleanup, and raw hashes unchanged during audit. V9 explicitly forbids these
prior IDs, in addition to retained V3/V5 IDs.

Before collection, the runner also records the live board CDC ports resolved by
USB serial, source/build/image hashes, adapter identity, Python/OS/package
versions, plan SHA-256, runner/auditor hashes, and the exact clean lock commit.
Because V3–V5 showed that sampling can continue after BLE disconnect, **each of
the 16 scheduled conditions gets its own physical cold boot of both boards**.
Before each condition the operator
removes power/USB from both boards for at least five seconds, reconnects them,
and enters that run's unique confirmation token. The runner then resolves both
CDC ports again by locked USB serial, starts new per-run CDC capture threads,
and requires both CDC control sessions to complete nonce-bound HELLO/READY.
Only then does V9 record the two CDC byte boundaries, request OFF on both boards,
and start BLE. The independent auditor verifies this order from the root
`matrix_control.ndjson` and compares each READY session with the run result.
Each active node's pristine pre-notify status gate must also pass. Each
node's observed boot ID must be absent from V3/V5/V6 and from every earlier V9
condition in which that node was observed. The forbidden-ID list also includes
the retained V5 A-only/dual boot IDs. No firmware reflash is planned.

## Conditions and balanced schedule

Each of four blocks contains the same-block single-node controls and both dual
connection orders. Every condition is a separate cold-boot acquisition; no
sampling or boot state is carried from a preceding condition:

1. `a_only`: Node A only.
2. `b_only`: Node B only.
3. `dual_a_to_b`: establish A, then B.
4. `dual_b_to_a`: establish B, then A.

The following four Williams sequences were drawn without replacement from the
four balanced sequences using `random.Random(20260924).sample(...)`; the resulting
order is embedded in code and is not randomized at runtime. Each condition
occupies each within-block position once.

| Block | Run 1 | Run 2 | Run 3 | Run 4 |
| --- | --- | --- | --- | --- |
| 1 | `a_only` | `b_only` | `dual_b_to_a` | `dual_a_to_b` |
| 2 | `dual_b_to_a` | `a_only` | `dual_a_to_b` | `b_only` |
| 3 | `dual_a_to_b` | `dual_b_to_a` | `b_only` | `a_only` |
| 4 | `b_only` | `dual_a_to_b` | `a_only` | `dual_b_to_a` |

The four blocks are repeated measurements on the same hardware and host. They
are not independent subjects; packets and notifications are not statistical
replicates. This is a predeclared engineering discrimination rule for one locked
hardware/host pair, not a population-level significance test; no p-value or
generalized equivalence claim will be made. “Not supported” means these four
observed block pairs meet the operational 0.90 gates with clean transport, not
that smaller effects or effects on other host/board combinations are absent.
For each dual run, compare each node's valid raw packet count with that node's
single-link count from the same block. Also report the first-node / second-node
packet ratio for each dual run.

## Acquisition and immutable evidence

The one-time V9 root is
`<external-data>/kineimu_m1_root_cause_formal_v9_20260924_01` and must not exist before
the locked acquisition. The independent report is outside that root at
`<external-data>/kineimu_m1_root_cause_formal_v9_20260924_01_independent.json`.

Every scheduled condition gets a unique numbered run directory and an
independent complete CDC capture for both boards. Keep every
success, error, failed setup, partial file, and unattempted condition in its
original position. A nonfatal run failure may be followed by later locked
conditions only if CDC capture is alive, OFF control is still acknowledged,
and disconnect cleanup completed. Stop on a CDC/control/cleanup failure, a
failed per-condition cold-boot/pristine-status gate, a bad run-specific reset
token, or operator cancellation. The run-specific confirmation JSON files are
stored under `operator_reset_confirmations/`; full CDC byte streams are stored
under `cdc_full_capture/run-NN-condition/`; each run directory also receives
the exact pre/post-run CDC byte slice. Do not replace, repeat, or supplement a
condition. Once the output root is created, it is consumed even if the
acquisition is incomplete.

Each run must retain:

- exact raw per-node `.kimu`, notification event sidecars, and run-local raw CDC
  byte segments;
- complete firmware connected/disconnected event ordering and all connection
  parameter callbacks, reconciled against each CDC segment and the explicit
  parameter window;
- one exact active connection-generation TX diagnostic segment per node, with
  submit/return-code/retry/ENOMEM/EAGAIN/wait/window-full/completion/cancel/
  in-flight/completion-age fields and at least two unsaturated snapshots;
- exact 15.000 s capture markers in both host clock domains; every notification
  callback's inclusion flag must reconcile against the stored capture bounds;
- identity-config reads, node/hardware IDs, firmware commit, USB CDC serial,
  accepted MTU, setup/settle events, and completed host/peripheral disconnects;
- per-run OFF acknowledgment and exactly one firmware OFF/no-local-request
  record per active node; final OFF cleanup for both nodes after every run;
- a run-specific operator cold-reset assertion, fresh COM-port resolution by
  USB serial, full CDC raw hashes for both nodes, and a per-node unique boot ID
  on every condition where that node is active;
- copied plan, source preflash record, firmware images/configurations, run
  results, serial-capture summaries, and a SHA-256 manifest covering every file.

The independent audit reads only `matrix_config.json`, `matrix_result.json`,
the root `matrix_control.ndjson`, the manifest, run-local reset/capture
summaries, raw full CDC streams and segments, raw KIMU streams, and event
sidecars. It verifies the per-run READY → CDC boundary → fixed-OFF order,
every CDC stream
hash and all raw hashes before/after analysis, checks boot-ID uniqueness across
conditions directly from pre-notify sidecars, and does not read any prior
`matrix_audit.json` or other audit output. It writes its report outside the
immutable root.

## Prespecified analysis and decisions

For each block and dual order, calculate
`P(node, dual) / P(node, same-block single)`, where `P` is the independently
decoded packet count from the exact 15 s raw capture. For every dual run also
calculate `P(first-connected) / P(second-connected)`. A missing/zero denominator,
unmatched block, or incomplete run cannot be replaced with a later observation.

- **Supported:** all acquisition-integrity gates pass and the same node has a
  dual/single ratio below 0.90 in at least three of four blocks under **both**
  connection orders. This supports a causal active-link-count throughput effect
  for the locked hardware/host combination. A notification-path mechanism is
  supported separately only if exact per-generation TX deltas show increased
  `-ENOMEM`/`-EAGAIN`, wait, or window-full activity alongside that deficit in
  at least three of four matched blocks for both orders. Even then, the design
  does not identify whether the resource pressure originates in the central
  controller or peripheral BLE stack.
- **Not supported:** every per-node dual/single ratio and every first/second
  ratio is at least 0.90, and TX enqueue drops, CRC errors, decode errors, and
  framing errors are all zero.
- **Inconclusive:** any integrity gate fails, any required paired ratio is
  unavailable, results are mixed without the repeatability rule above, or a
  nonzero transport-quality outcome prevents the `Not supported` decision.

Report packet/sample sequence gaps, duplicates, every TX counter, callback
durations, and observed connection tuples as outcomes even where they do not
invalidate the raw measurement. Never attribute a parameter callback to a
requester based only on `param_updated`.

## Stop, lock, and next-action rules

Before collection, commit this plan, the V9 runner/auditor/tests, and the exact
firmware/board/host identity pins together. The committed HEAD and all file and
image hashes are recorded in the output root. Run the focused test first, then
`pytest`, Ruff, and mypy. No firmware source changes are in this experiment, so
no firmware build or Twister run is planned.

If the pre-run identity or empty-root gate fails, do not open BLE or CDC and do
not create the output root. If a failure occurs after root creation, preserve
all partial output and report the exact failed integrity gate; do not rerun.
No 30-minute bench, hardware freeze, M2, host/adapter replacement, public-format
change, queue/context increase, push, merge, or PR is authorized here.

Passing the V9 causal/quality gates can justify proposing a separate 30-minute
M1 bench. It does not complete or close M1.
