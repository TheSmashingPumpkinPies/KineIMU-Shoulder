# M1 CDC Control Stage 7 Preflash Identity Check

Date: 2026-09-21 (Asia/Shanghai)
Status: board and volume identities verified; matched flash pending.

## Bootloader identity

After the maintainer entered both boards into UF2 bootloader mode, Windows
reported two removable `XIAO-SENSE` volumes. Both `INFO_UF2.TXT` files report
model `Seeed XIAO nRF52840`, board ID
`Seeed_XIAO_nRF52840_Sense`, SoftDevice S140 v7.3.0, and UF2 Bootloader 0.6.1.
The drive letters were mapped to USB disk serials through the Windows
partition-to-disk association:

| Node | Drive | Physical disk | USB serial | Board ID | UF2 to copy |
|---|---|---|---|---|---|
| A | E: | PhysicalDrive1 | `0000000000000001` | `Seeed_XIAO_nRF52840_Sense` | `m1_cdc_node_a.uf2` |
| B | F: | PhysicalDrive2 | `0000000000000002` | `Seeed_XIAO_nRF52840_Sense` | `m1_cdc_node_b.uf2` |

Both volumes currently contain `CURRENT.UF2`, `INDEX.HTM`, and
`INFO_UF2.TXT`; the new copy names do not collide with those files.

## Immediate preflash recheck

The flashable UF2 hashes still match the Stage 5 record:

- A: `010FA6CCAD28845F431C087B51071A717657BFA12BAFE9B78E65899E0CD46CFA`
- B: `2796B5E38F123E191BC1F82314917CA6B024A73D3BAA0C19EA244AABEA014627`

The generated A/B configurations remain byte-identical at
`0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69`.
Firmware and the experiment overlay have no changes since the image source
HEAD `545e38d6b86c9a773a609a93526405493861976b`. The old preflash record
remains at SHA-256
`C4EF413589C0FA0B9326A1FFC8AEE167C0AADF55F7CF7BABA26D5383A3EC3CE5`, and
the old plan remains at SHA-256
`6B295C3C5CC5B2B9E06623D9E28B9A7DD70F342085DA66D29D3ABBF847B9D2D4`.

The machine-local identity record is
`.cache/m1_cdc_stage7_preflash_manifest_20260921.json`, SHA-256
`54BB3F0F9F723B12930BF2D6CD6414674B6CE8709B1F7DA188BA9EF496EFBFD3`.
It records the repository HEAD at the check
`f33e407eba04b6fc0eeff9925350bb613aa72768`, build/config/image identities,
board IDs, serial-to-volume mapping, and intended filenames.

No UF2 has been copied in this checkpoint. The next action is to copy A's
verified UF2 once to E: and B's verified UF2 once to F:, then re-resolve both
application CDC ports by USB serial. Stop if either copy or re-enumeration
does not match the recorded identity.
