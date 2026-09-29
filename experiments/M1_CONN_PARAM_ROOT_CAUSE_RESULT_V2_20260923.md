# M1 Connection-Parameter Root-Cause Matrix v2 — Result

Date: 2026-09-23 (Asia/Shanghai)

Disposition: **INCONCLUSIVE**

## Locked execution

The only authorized v2 formal matrix ran once against the committed plan
[`M1_CONN_PARAM_ROOT_CAUSE_PLAN_V2_20260923.md`](M1_CONN_PARAM_ROOT_CAUSE_PLAN_V2_20260923.md),
SHA-256
`D2FA561B8E699BB61855188931C0C40812600CD7D30117A79D88CFB92D52B9FB`.
The output root is
`<external-data>\kineimu_m1_ble_connparam_rootcause_v2_20260923_01`.

Independent recalculation verified all 198 entries in the root's
`SHA256SUMS.txt`, with no missing, mismatched, or unlisted files. All 16
scheduled runs were attempted in the exact locked order. The report was
calculated directly from the matrix result, raw CDC bytes, raw KIMU streams,
and event sidecars; it did not read `matrix_audit.json`. Raw input hashes were
unchanged during recalculation.

## Recalculated observations

- All 12 ON node-links recorded a successful local connection-parameter call
  (`call=1`, `api_rc=0`) and the target tuple 15 ms / latency 0 / 420 ms.
- All 12 OFF node-links recorded no local parameter request, but their last
  observed tuples were also 15 ms / latency 0 / 420 ms. The predeclared ON/OFF
  contrast was therefore not realized.
- All 24 node-links have a complete firmware-connected-event-relative
  parameter window of at least 10.0 s. Filtered scans took 4.994–5.129 s, while
  connect plus GATT setup, excluding scan, took 0.544–0.953 s (below the
  separate 15.0 s limit).
- The 24 active node streams contain 7,105 valid packets in total, with no
  zero-packet captures. There were no scheduled run-level errors or cleanup
  failures.
- The formal run predates explicit shared capture-boundary markers and
  per-callback admission evidence. None of the 24 node streams has those
  markers, so exact inclusion within each 15.0 s capture cannot be audited.
  The earlier v3 estimate of 315 callbacks at or after a conservative
  earliest-possible deadline was superseded by the clock-domain-corrected v4
  recalculation: it reports **0** such callbacks. Neither count supplies the
  missing explicit boundaries or proves admission to the planned window.
- TX diagnostic segments are incomplete for Run 4 Node B and Run 5 Node B.

Because the OFF tuple contrast was not realized and required capture-boundary
and two TX-diagnostic records are incomplete, the locked criteria yield
**inconclusive**. The matrix does not establish either support or lack of
support. The matrix was not rerun and no condition was replaced, skipped, or
reordered.

## Independent-analysis evidence

- Matrix root: `<external-data>\kineimu_m1_ble_connparam_rootcause_v2_20260923_01`
- Raw manifest: `SHA256SUMS.txt`, 198 entries, SHA-256
  `EDEA8A0ED47376D5FD6F2EFC236B740A0FBE249079653A8CB43FDD1C5C55B55A`
- Locked plan SHA-256:
  `D2FA561B8E699BB61855188931C0C40812600CD7D30117A79D88CFB92D52B9FB`
- Matrix result SHA-256:
  `24D57E3F9ECAC319F46D19CCB325AFCF8317D2B7FA153BFF04B3642E614309F7`
- Matrix config SHA-256:
  `A077A6962116BDC2729CA4C9BF92B8D023C7BEA5A546BA82A08079592EE93DFF`
- Independent recalculation JSON:
  `<external-data>\kineimu_m1_cdc_unblock_20260923_02\independent_analysis_v3_after_capture_boundary_fix.json`
- Recalculation SHA-256:
  `216C2AEA05B1817659AE2929E3CBF3CEF2BA590A3BF30194EAF011F82CDEE054`
- Recalculation script SHA-256:
  `C0E13187418825F8215253DC39F31B0EB14914786EF4B4FBC05973F2B1D1A93F`

The analysis report preserves every classification reason and the schedule,
control, timing, capture-completeness, cleanup, and source-hash checks. Earlier
inconclusive results and raw files remain unchanged.

## Clock-domain-corrected independent recalculation

After fixing the strict capture clock labels in the experiment runner, the
independent analysis was rerun against the same immutable matrix root. This was
a read-only recalculation; no acquisition was repeated and every raw input
hash remained unchanged. The schedule still matches the locked order and the
classification remains **INCONCLUSIVE** for the same scientific reasons: the
OFF tuple contrast was not realized, the formal run lacks exact capture
boundary evidence, and two Node B TX diagnostic segments are incomplete.

- Updated independent report:
  `<external-data>\kineimu_m1_cdc_unblock_20260923_05\independent_analysis_v4_clock_domains.json`
- Report SHA-256:
  `7D3D2829AB0A7AE5DD319DF5720B4DA8ED88F7ADB338C97EA068C500B18B4A98`
- Updated analysis script SHA-256:
  `45CECAFE81CB188DEDBD9994FB533E73262139A8DED0C7D4868773B719A527A2`
- Recalculation fields: `schedule_matches_locked=true`,
  `raw_inputs_unchanged=true`, classification `inconclusive`.

The earlier v3 report and its hash above are retained as historical evidence.
The formal matrix directory, plan and source hashes were not edited.

## Final physical Gate 3 evidence after clock-domain correction

The final 15-second A-only and B-only acquisition smokes passed after the
strict callback, raw timestamp, and capture-boundary comparisons were aligned
to `perf_counter_ns`. Both boards completed identity and MTU checks, confirmed
disconnect, and OFF cleanup with `rc=0`. A produced 393 valid packets and B
produced 402. Firmware callback/raw_try/raw_ok/notify_calls counter deltas were
3199/3199/3199/393 for A and 3121/3121/3121/384 for B. Raw streams and event
sidecars were nonempty; CRC, decode, framing, and node mismatch counts were
zero. One B callback after the capture deadline was rejected by the strict
admission check.

- Gate 3 root:
  `<external-data>\kineimu_m1_cdc_unblock_20260923_05\physical_gates_gate3_clock_labeled`
- Gate 3 manifest SHA-256:
  `260EC6A8DB0471A6FE180B6D2D45D24965A392B444E697AA04D919AA402981AE`
- Independent audit JSON:
  `<external-data>\kineimu_m1_cdc_unblock_20260923_05\physical_gates_gate3_clock_labeled_independent.json`
- Independent audit SHA-256:
  `8BAEB784F05F6448B5243C4EC2A19C1E60621503C743A0346044FEC2DF595746`
- Audit script SHA-256:
  `045A9848EAE8AF69352B3EA6B7A72C5CB4EE9615B4004CD95392CB698D1A8796`

The audit reverified all 15 manifest files and reported unchanged raw inputs.
This later Gate 3 run supersedes no formal matrix evidence and does not change
the matrix's **INCONCLUSIVE** disposition.
