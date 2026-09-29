# CP4 accepted — two complete independent formal replay collections

CP4 PASS on 2026-09-28; M5.4 delivered. Numerical lock `a72bdd18dd3567bb3b043c4cd6c75b16b7311cf9`;
independent tool lock `fbcb118ba5eaf54c739767ac36ac9bdb129ad3e5`. [Accepted audit](audit.json),
[commands/exits and complete output map](verification.json),
[original run commands](../M5_CP4_STAGE_E2_20260928/execution.json).

Both complete B/C/segmented-D collections returned exit0 and every35 canonical
product plus outer checksum is byte-identical. All six separate B/C/D numerical
audits passed. Raw Q/labels/metadata/digest map, original Node B and all11 M1
manifest members+manifest hash are unchanged before/after.

| Stage per run | Independent retained-source support |
|---|---|
| B | 4 complete Q trajectories;8 nodes/17208 rows/4304 packets;27160 error scalars;22 products;3 valid repetitions each,0 missed/false |
| C | 832 rows/208 packets;832 quaternions and downstream rejection rows;3 products |
| D | 379196 original rows/94799 packets;379195 quaternions,1 null row,3 fresh worlds,187772 downstream rows;5 products |

Recorded shoulder values stay null/invalid; calibration and independent node
worlds are Assumed/Experimental, no shared heading/anatomical/clinical accuracy
inferred. D explicitly uses ADR-011; no crossing its rejected row/worlds.

Numerical source checks full762/no skips and focused103 with actual external
M1 tests; E4 guard8 and Ruff/mypy32/docs/whitespace pass. Original63 source
entries are exact runtime ZIP/disk/hash matches. Only two original LF-Git/
CRLF-runtime source representations use documented exact path/hash bindings;
all other source Git bytes match. Exact separate tool ZIP is retained.
See [source identity](../../docs/M5_CP4_GIT_EOL_BINDING.md) and
[worker identity](../../docs/M5_CP4_PID_AUDIT_CORRECTION.md).

Original E1 entry failure, E2 PID-audit failure, E3 source-EOL-audit failure and
original failed D root remain immutable. Their reports are not reclassified;
this separate audit accepts the unchanged complete E2 pair. No raw/canonical/
numerical/backend/threshold/truth/schema/hardware alteration or new acquisition.

CP5 and overall M5 remain OPEN. Next authorized continuation is M5.5 evidence
coverage/limitations/test-gap/M6 input closeout; no physical action needed.
Committed-byte proof: [180 artifacts and exact source/tool archives](committed-evidence.json), retained evidence commit `10a51ae69f6ac258bd9543f4d6551cb623424431`.
