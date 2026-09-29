# M1 BLE Dual-Link Root-Cause Decision — Analysis Checkpoint

Date: 2026-09-23 (Asia/Shanghai)

Status: **15 ms request factor is not identifiable on the current host/device
combination; V3 and V4 are consumed and blocked; V5 A-only passes but its dual
A→B pair is consumed and BLOCKED by sequence gaps and incomplete physical-link
TX attribution.** This is not a final M1 root-cause decision and does not
authorize the 30-minute bench.

## Scope and preserved evidence

The work starts from `codex/m1-cdc-control-unblock`, source HEAD
`4ebf43d8dd1b443e7873f5d0f40b3926e6e6512c`, which is 45 commits ahead of local
`main`. This decision is made on `codex/m1-root-cause-decision`. The old
eight-context transport rejection, old connection-parameter result, Stage 10A
inconclusive result, and formal v2 raw directory are retained unchanged.

The formal v2 root is
`<external-data>\kineimu_m1_ble_connparam_rootcause_v2_20260923_01`. Its locked plan
SHA-256 is
`D2FA561B8E699BB61855188931C0C40812600CD7D30117A79D88CFB92D52B9FB`. Its
198-entry manifest SHA-256 is
`EDEA8A0ED47376D5FD6F2EFC236B740A0FBE249079653A8CB43FDD1C5C55B55A`. A direct
read-only recalculation from raw CDC bytes, KIMU files, and per-run event
sidecars verified the manifest, the locked schedule, and unchanged raw hashes;
it did not use `matrix_audit.json` as input. The corrected recalculation is
`<external-data>\kineimu_m1_cdc_unblock_20260923_05\independent_analysis_v4_clock_domains.json`,
SHA-256
`7D3D2829AB0A7AE5DD319DF5720B4DA8ED88F7ADB338C97EA068C500B18B4A98`.

## Findings from the old and v2 matrices

The September 20 focused eight-context retest rejected that firmware candidate
at its predeclared gates. In the seven successfully established runs, the
first-connected link stayed at roughly 120–125 packets while the
second-connected link stayed at 355–394; the pattern followed connection order
in both directions. The captured enqueue-drop total was 1,015. The failed
setup run and every original artifact remain preserved. No queue or ATT-context
increase is proposed.

In v2, all 12 ON links logged one local request with API return code 0; all 12
OFF links logged no local request. Nevertheless, ON and OFF links both
observed the same last tuple, 15 ms / latency 0 / 420 ms. In the event-relative
parameter windows, callbacks commonly reported a move from that tuple to
13.75 ms / 0 / 9.6 s and back. The callback reports actual parameters but has
no requester identity. An accepted `bt_conn_le_param_update()` API call does
not establish that a later `param_updated` callback was caused by that call;
the identical OFF observations show the local request was not necessary for
the observed tuple. Therefore the local 15 ms request versus OFF causal
contrast was not realized and is **not identifiable on this Windows host,
adapter, firmware, and board combination with the available callback
instrumentation**. This hypothesis is closed for this configuration; do not
repeat v2 or infer the update initiator from callback order.

Every one of the 24 v2 node links had a complete 10-second
peripheral-connected-event-relative parameter window and the expected identity
and MTU 127. However, all 24 streams lack an explicit 15-second capture marker
and callback admission evidence. Only 22 of 24 have exact per-generation TX
diagnostic segments; Run 4 Node B and Run 5 Node B are incomplete. The v4
recalculation found 7,105 valid decoded packets, zero CRC-false events, zero
decode errors, and zero framing errors, but those counts cannot replace the
missing boundaries. The v2 disposition remains **INCONCLUSIVE**. The former
315-callback estimate in the report was a stale v3 value; v4 corrected it to
zero. The corrected config hash is
`A077A6962116BDC2729CA4C9BF92B8D023C7BEA5A546BA82A08079592EE93DFF`.

Within the eight v2 dual runs, the first-connected link delivered 88–96
packets and the second delivered 394–402. In both orders this tracked
connection position, not node identity; same-block single links delivered
about 378–400 packets. Complete first-link diagnostic segments show 972–1,209
`bt_gatt_notify_cb()` `-ENOMEM` returns, 972–1,209 retries, 68–78 full-context
wait episodes, and about 13.4–14.2 s accumulated wait in a nominal 15 s
capture. Second links and singles show no such pressure. This is strong
mechanism evidence for submission-resource backpressure at the GATT/ATT notify
boundary. Because exact v2 capture boundaries are absent and two TX segments
are incomplete, it is not yet a complete causal attribution of the throughput
loss, nor does it identify which Windows/controller/stack resource is
exhausted.

## Competing bottleneck locations and discriminating observations

These are operational alternatives for the dominant loss point in one capture;
they are not claims that other stages cannot contribute.

| Candidate dominant choke point | Evidence that would distinguish it |
| --- | --- |
| Acquisition/packet queue before GATT submission | Exact capture-window deltas for sensor samples, queue enqueue/dequeue/high-water, and sample/packet drops; loss here without matching GATT `-ENOMEM`/retry growth. |
| GATT/ATT submission or completion resource pressure | Per-connection-generation `bt_gatt_notify_cb()` return codes, accepted/completed counts, retries, in-flight count, full-window wait and age; pressure must line up with the exact accepted callback window. |
| Host callback or raw sink after notification delivery | Device accepted/completed counts versus host notify callbacks, `.kimu` packet counts and raw bytes over the same explicit boundaries, with callback and write durations. |

The observed first-link `-ENOMEM`/retry/wait pattern supports the second path
most strongly. Short host callback durations and normal second-link/single
counts weaken a host raw-sink explanation, but the formal run cannot pass its
evidence gate without exact boundaries. The producer/queue path is not
excluded by these data.

## Versioned link-count precheck V3

The selected single factor is **one versus two simultaneously active BLE
links**. Hold firmware, nodes, host/adapter, connection-parameter request mode
OFF, sensor configuration, MTU requirement, 10-second setup/parameter window,
15-second capture, and post-disconnect OFF cleanup fixed. The precheck must
cover both `dual_a_to_b` and `dual_b_to_a`, with same-block `a_only` and
`b_only` controls, to show that the first-link behavior is still observable
and belongs to link count/order rather than a fixed node identity.

The precheck must fail closed unless it demonstrates all of the following for
each scheduled node/run: firmware connection event and full 10-second
parameter window; 15-second strict capture start/deadline and per-callback
admission; device identity and MTU 127; exact TX counters for the complete
connection generation; nonempty immutable KIMU and event/CDC evidence with
matching hashes; confirmed host and peripheral disconnect; and final OFF
control ACKs for both nodes. The raw directory must be new and empty before
execution. Any failed or partial run stays in the evidence directory and
stops the precheck; no replacement is allowed.

This precheck is an instrumentation/usability gate, not the formal causal
experiment. Following the V2 host-runner failure, versioned plan
`M1_BLE_LINK_COUNT_PRECHECK_PLAN_V3_20260923.md` was prepared with SHA-256
`964BDDD488915250411A621CF557F56F4CFC6A8848C115FE80ADDDD290D6F7B0`. The
strict capture marker now passes the typed `NodeId`; the precheck config records
the expected application CDC interface; and the independent auditor expects the
writer's result schema and reads KIMU/event sidecars from `raw/`. Four targeted
regressions, full pytest (214), Ruff, configured mypy (13 source files), and
`git diff --check` pass. The runner is bound to the distinct root
`<external-data>\kineimu_m1_root_cause_precheck_20260923_03`, confirmed absent. Plan,
runner, tests, and initial task state are locked in commit
`46be3648d8fddcb5e113c0efb28397aa06a2a7f1`. V3 subsequently ran once and is
consumed; its acquisition and audit outcome are recorded below. The plan itself
is unchanged. No firmware change is selected here.

## V3 acquisition and independent raw audit — blocked

All four planned V3 conditions ran once, in order, with no stop reason. The
immutable raw root is
`<external-data>\kineimu_m1_root_cause_precheck_20260923_03`; its 60-entry
`SHA256SUMS.txt` manifest has SHA-256
`B7AD4BD7BDE80A7899870D0A408778FA404580E6D07CDAAFA2DD04910E46791D` and
verifies without missing, mismatched, duplicate or unlisted entries. The
corrected independent audit is
`<external-data>\kineimu_m1_root_cause_precheck_20260923_03_independent_freshness_corrected.json`,
SHA-256
`4BE3520A018F4C695CFE1CE1CF8390A96F75F9D9FAE02795E12C21E64456FC88`;
`raw_inputs_unchanged=true`. It read raw CDC/KIMU and event sidecars directly,
not an earlier audit.

The first V3 audit report remains preserved with SHA-256
`314F110F0F894D22C17F7D7D8E7382DF9F1BDF749A627752FFFFFDCEF7913842`. Its
only reported gate was an unplanned minimum callback span of 14.9 seconds,
although the raw control markers prove exact 15.000-second windows and strict
per-callback admission. The initial freshness-report attempt
(SHA-256 `E360DF555F6EF309841BEECF10F480F1091811345DFAA81B7626BD82D6245FA1`)
is preserved but superseded because that audit code searched the node sidecar
for a telemetry-enable event that is recorded in the shared control log. The
corrected audit correlates the two logs; no original raw or prior report was
changed.

Corrected results: active-link states `[1, 2, 1, 2]`, both dual orders,
firmware connection/parameter windows, explicit capture boundaries, callback
admission, device identity/MTU, exact per-generation TX snapshots, host and
firmware disconnects, final OFF ACKs and manifest integrity all pass. The
precheck still **BLOCKS** on acquisition freshness. Firmware code explicitly
keeps sampling while disconnected. The per-node pre-notify status and raw
sample sequence prove that later scheduled conditions reused a running boot:

| Condition/node | Pre-notify state and counters | Raw sample sequence gaps |
|---|---|---:|
| A-only / A | `armed`; sample/drop counters zero | 0 |
| Dual A→B / A | `streaming`; 1,097 queue drops before notify | 2,737 |
| Dual A→B / B | `armed`; sample/drop counters zero | 0 |
| B-only / B | `streaming`; 1,087 queue drops before notify | 2,192 |
| Dual B→A / A | `streaming`; 8,171 queue drops before notify | 6,464 |
| Dual B→A / B | `streaming`; 3,355 queue drops before notify | 2,803 |

These are proven carryover and sample-loss observations for this V3 schedule,
not proof that the firmware sample queue caused the historical dual-link
throughput deficit. V3 does not identify an end-to-end BLE bottleneck and does
not authorize a formal matrix. A later clean-start precheck must use a fresh
boot for each condition and demonstrate distinct boot IDs, armed/zero pre-notify
status, gap-free raw samples, and all existing evidence gates. The minimal
precheck should compare A-only with dual A→B so Node A is common to both
conditions. If these gates pass, only then draft a balanced formal plan with
both dual orders and same-block single-node controls.

## V4 cold-start precheck — A-only acquisition consumed and BLOCKED

The V4 plan is
`experiments/M1_BLE_LINK_COUNT_COLD_START_PRECHECK_PLAN_V4_20260924.md`,
SHA-256 `E277E7AAF46F310F094A297E94CE0ED7F4861E12BCA05A2C8D540A7D8612F7AE`;
the plan, experiment-only runner gate, audit, and regression tests are locked
at commit `1030cea6cc8c179de6b5c03b14570221e311c28f`. It compares Node A with
one versus two active links, request mode OFF in both, using independent
processes and raw roots. It is only an instrumentation/manipulability gate,
not a throughput experiment or cause test.

Before telemetry CCC enable, the V4-only client requires pristine `armed`
status, zero acquisition/drop/TX/high-water counters, never-produced sample
and packet sequence sentinels, valid node/boot identity, and a boot ID not used
in V3 or the earlier V4 A-only condition. The dual acquisition recomputes and
requires a passing independent raw audit of the A-only root. The paired audit
recomputes both manifests/raw hashes and checks condition labels, same Node A,
distinct boots, link state, identity/config/host, strict timing, full TX
snapshots, and cleanup. V3/default recorder behavior is unchanged.

The A-only condition consumed
`<external-data>\kineimu_m1_root_cause_precheck_20260924_01_a_only`; its 24-entry
manifest SHA-256 is
`5C845BF6C3F77CAAD0BF7CCF9C8FF4C4132D71099C482959E9C6B8FAA6867887` and
verifies with no missing, mismatched or unlisted files. The independent raw
audit `<external-data>\kineimu_m1_root_cause_precheck_20260924_01_a_only_independent.json`
has SHA-256 `F9F1D82FE83DD6A6FBE4C92C07192A57C17DAE6773FE66AFC7F8240D8CB27A17`,
`raw_inputs_unchanged=true`, and disposition **BLOCKED**. It recomputed the
raw inputs and did not read a previous audit.

The scan found Node A at its locked BLE address. Firmware logged a connection
event 14.84 seconds after host connect start, but Windows/Bleak did not return
from connect/GATT setup within the 15-second timeout; the connect/GATT timing
was 14.948 seconds. The host never obtained GATT identity/MTU, notify enable,
capture boundaries, KIMU packets or an active TX generation. Host disconnect,
firmware disconnect and acknowledged OFF cleanup completed. Raw KIMU and event
sidecar are empty. For comparison, 24 V2 raw connect-total durations were
0.544–0.953 seconds (median 0.628 seconds). This setup delay is an outlier
observation, not evidence of a dual-link throughput cause.

The initial independent audit crashed on missing MTU and null recorder fields.
Targeted RED/GREEN tests now make both cases explicit audit failures. The fix
is commit `33b2631dd80d51f352d10a7ae5af635b45b61b07`; the V4 acquisition
predates it and the raw root remains unchanged. The dual root was not run under
V4 because its A-only audit failed. Preserve this root and plan; prepare a
separately versioned precheck with a longer fixed connect/GATT setup allowance
and fresh output roots before any new physical capture.

At the V4 lock, full pytest passed **222/222**, Ruff passed (with warnings for
inaccessible ignored scratch roots), configured mypy passed for 13 source
files, and `git diff --check` passed. No firmware changed. Formal experiment,
repair, 30-minute bench, hardware freeze, and M2 remain unstarted.

## Current disposition

- **Confirmed:** local 15 ms request versus OFF did not create distinct actual
  tuples in v2; the v2 result remains inconclusive for its throughput rules.
- **Strong but not final causal evidence:** order-associated throughput loss
  co-occurs with per-generation GATT `-ENOMEM`, retry, and full-context wait.
- **Not established:** who initiated the observed connection-parameter
  updates; the precise shared resource behind `-ENOMEM`; or the final dominant
  source of all missing packets.
- **Proven precheck defect:** reusing a boot across disconnected conditions
  carries active acquisition state into the next run; later V3 status snapshots
  and raw sequence gaps fail the new freshness gate.
- **Next action:** V5 A-only has passed its independent raw audit. Reset both
  boards again and run only dual A→B from the exact same locked Git HEAD; run
  the paired raw audit if dual completes. Do not rerun V3/V4 or start a formal
  matrix until both V5 single-root audits and the paired raw audit pass.
- **M1/bench gate:** M1 remains open. No 30-minute bench, hardware freeze, or
  M2 work is started.

## V5 cold-start precheck — plan/code locked; A-only passes; dual pending

Plan `experiments/M1_BLE_LINK_COUNT_COLD_START_PRECHECK_PLAN_V5_20260924.md`
has SHA-256
`2A18B7EA52C1F414695B7C4C1C99E15365C0C1BD9E8756B12042495232E426B2` and is
locked with its experiment-only runner, audit and tests at commit
`2912990a334f8230c4645be03623f307ddc74b52`. It keeps active-link count
(one versus two) as the only precheck factor; both conditions use request mode
OFF and a fixed 30-second Windows connect/GATT setup allowance. The exact
15-second capture, firmware, board pair, host/adapter, sampling setup and
protocol remain fixed. This is only an instrumentation/evidence-integrity
precheck and cannot establish throughput causality.

Fresh V5 roots and report outputs were verified absent. The locked runner
records and audits the exact Git HEAD, code and plan hashes, firmware/build and
board identities, CDC USB serials, BLE addresses, host/adapter driver, full
connect and parameter-window events, strict capture marker, per-generation TX
diagnostics, identity/MTU, disconnect/OFF cleanup, and raw manifest/hashes.
V4 raw-audit compatibility is preserved. No firmware, public format, queue,
ATT context, host or adapter changed.

Verification before acquisition: targeted V5 contract tests **25 passed**;
full pytest **227 passed**; Ruff **all checks passed** (warnings only for
inaccessible ignored scratch paths); configured mypy **13 source files
passed**; docs consistency **143 Markdown / 39 archive hashes / 0 errors**;
`git diff --check` passed. The V5 A-only attempt and independent audit now pass
as recorded below. The dual acquisition and pair audit remain pending. No
formal matrix, firmware repair, 30-minute bench, hardware freeze, M2, push,
merge or PR has started.

## V5 A-only — precheck evidence passed; dual pending

After the user physically reset both boards, V5 `a_only` was attempted once.
The immutable root is
`<external-data>\kineimu_m1_root_cause_precheck_20260924_v5_01_a_only`; its
24-entry manifest SHA-256 is
`DC61609285105A569CEF7F58C016567B67798E1B9511DD736A2FE109A0567F0F`. The
independent report is
`<external-data>\kineimu_m1_root_cause_precheck_20260924_v5_01_a_only_independent.json`,
SHA-256 `AEC89BB9321CF4339FAA536CE417DCA02F968115D3C8840158F10F8250166599`.
It was recalculated from raw CDC/KIMU/event sidecars; `raw_inputs_unchanged`
is true, all 24 manifest entries verify, and the report has no errors with
disposition **PASS_FOR_PAIR_AUDIT**.

The run config records Git HEAD
`10dae265d0943060881b8124ff414d3dee9b9cd4`, V5 plan SHA above, runner SHA-256
`38F46475C4B5655E8CFEBCF3578DC00125F1D488E3A243987E2E13F5A7BBB22A`, matrix
runner SHA-256
`B2A4D9DD7C8B87141DA729B8B7B1ED106DEA1BCEFA9D74626C0199D784C3FD70`, and
the 30-second connect/GATT limit. Node A boot
`2701971511492984250` started `armed` with zero pre-notify acquisition/drop
counters and never-produced sequence sentinels. One active BLE link was
realized. Firmware connection and both parameter callbacks reconcile across
the full 10.000-second connected-event-relative window. The actual callbacks
were `60 ms / 0 / 9600 ms`, `13.75 ms / 0 / 9600 ms`, and
`40 ms / 0 / 420 ms`. Because request mode was OFF, this says nothing about a
local 15 ms request; callback records still do not identify the initiator.

The explicit shared-recorder capture marker is exactly 15.000 seconds, with
the boundary audit passing. Identity and MTU 127 passed. Raw capture contains
390 valid packets / 1,560 samples; sequence gaps, CRC, decode, framing and
node-ID errors are zero. Both TX connection-generation snapshots have exact
deltas and no drops, retries, `-ENOMEM`, `-EAGAIN`, or full-window waits. Host
and firmware disconnect and OFF cleanup passed. This confirms the A-only
instrumentation and evidence gates, not a throughput effect or cause.

At this A-only checkpoint, the dual root and pair audit were still unused. The
next step then was one dual A→B attempt from a clean worktree at the same
recorded Git HEAD after a fresh reset. That attempt and its paired raw audit
are recorded below; the gate blocked and both output roots are consumed.

## V5 dual A→B precheck — consumed; paired audit BLOCKED

V5 plan SHA-256 is
`2A18B7EA52C1F414695B7C4C1C99E15365C0C1BD9E8756B12042495232E426B2`; its
plan/runner/audit/test lock commit is
`2912990a334f8230c4645be03623f307ddc74b52`. The one dual A→B acquisition ran
once from the same Git HEAD as A-only, `10dae265d0943060881b8124ff414d3dee9b9cd4`.
Dual raw root:
`<external-data>\kineimu_m1_root_cause_precheck_20260924_v5_02_dual_a_to_b`;
manifest has 27 valid entries and SHA-256
`49AFADA6850EC763EC9909E6DFE5F5D4A24F09509938DB656F832163D9F82651`.
Independent paired report:
`<external-data>\kineimu_m1_root_cause_precheck_20260924_v5_pair_audit.json`;
SHA-256 `1077467B04F8A074916297E5FCBEC5E667531DFC0501C32E4F608FD71AAEA21A`;
disposition **BLOCKED**. Direct raw verification confirms the A-only 24-entry
and dual 27-entry manifests, complete explicit timing/identity/MTU 127/cleanup
evidence, one physical connection per node, and zero CRC/decode/framing/
wrong-node errors.

The locked zero-sequence-gap gate failed on real data: A has 30 valid packets,
82 packet gaps and 331 sample gaps; B has 374 packets, 7 packet gaps and 28
sample gaps. Final firmware traces record TX enqueue drops 333 on A and 4 on
B. The raw loss is a measured outcome, not file corruption. The active-epoch
first-to-last snapshot deltas in the active queue epoch show a strong mechanism
association (they are not lifetime or capture-boundary totals): A has 1,413 notify calls,
1,387 `-ENOMEM` returns/retries, 26 accepted/completed notifications and
13,489,918 us wait; B has 482 calls, 135 `-ENOMEM` returns/retries, 347
accepted, 339 completed and 1,606,391 us wait. These diagnostic deltas are not
aligned to the exact 15-second capture boundary.

The report's second-active-generation error does not indicate a BLE reconnect.
Firmware increments the TX queue generation when telemetry CCC is disabled
and again on disconnect; global diagnostic counters remain cumulative and
snapshots only relabel the current queue epoch. One firmware connect event was
observed for each node. Direct raw recalculation gives boot-lifetime totals A
1,432 calls / 45 accepted and completed / 1,387 `-ENOMEM`; B 587 calls / 390
accepted and completed / 197 `-ENOMEM`. The generation-2 to generation-3
snapshot transition changes A by +1 call/+1 accepted and B by +79 calls/+17
accepted/+62 `-ENOMEM` and retries; snapshots do not allocate those changes to
either queue epoch. Within-generation-3 tails show +7 A/+2 B completions. These
cumulative totals include work outside the exact 15-second capture and are not
15-second rates. The locked per-generation TX completeness gate still fails.
Preserve the paired **BLOCKED** report unchanged.

The one fixed-order A-only/dual comparison (390 versus 30 A packets) is
correlational, not the formal balanced causal experiment. It does not prove
that link count caused the historical deficit or identify the resource owner.
The 15 ms request contrast remains unidentifiable; the throughput bottleneck
remains **INCONCLUSIVE**. Do not rerun V5, start a balanced link-count matrix, repair
firmware, or enter the 30-minute bench. The V6 precheck-only revision below
distinguishes physical BLE connections from queue epochs, defines TX counter
scope, and treats sample gaps as outcomes while preserving raw integrity
checks. Only a passing revised precheck can unlock a separate balanced plan.

## V6 precheck-only revision — locked, not acquired

Plan `M1_BLE_LINK_COUNT_COLD_START_PRECHECK_PLAN_V6_20260924.md` is locked at
SHA-256 `87BCEDC63917FD6F250A85E70883370013CA72D01A14F80ECA9EFA593E834BB8`.
Locked runner SHA-256 is
`B83745FC71C30CFF47EEBE3ACCBE566C24FACB10A9DAAB7EE54FE8D623B50BF9`; the
contract-test SHA-256 is
`CA49509A9953A90E5C203B409809DE509D2B76FEB99A20C2A42E2D34BD9ECE22`.
The new V6-only host audit reports cumulative TX totals since one pristine
firmware boot, preserves queue-epoch segments and cross-epoch deltas without
attributing transitions to either epoch, and requires complete monotonic,
unsaturated counters with terminal no-in-flight state. V6 records raw packet
and sample sequence gaps, duplicates and reorder counts as outcomes; integrity
gates remain for raw files/hashes, exact capture boundaries, CRC/decode/framing,
node identity, connection/MTU and cleanup. V3–V5 audit behavior remains
versioned and unchanged in meaning.

Focused regression contracts pass 3/3, full pytest passes 230/230, full Ruff
passes, configured mypy passes (13 source files), docs consistency passes (144
tracked Markdown files, 39 archive hashes, 0 errors), and `git diff --check` passes.
An in-memory V5 pair audit recalculated from raw evidence still returns
**BLOCKED** with both raw inputs unchanged and the historical report SHA
unchanged. The plan, runner and tests are locked in local commit
`c8a778a77cfc11e8f28db9915d66027f558c24b6`; it has not been pushed. No V6
output root has been created. A documentation-only state refresh follows the
lock commit at `159683dda4ad5704482cea337649f8dd9a2e97c7`, and the tracked tree
was verified clean after that commit. The next step is to reset both boards,
run only the planned A-only precheck, and independently audit it; the dual
precheck is permitted only if that gate passes.

Do not reinterpret or rerun V5, begin the formal experiment before V6 passes,
or run the 30-minute bench. No firmware change is supported by the precheck.
