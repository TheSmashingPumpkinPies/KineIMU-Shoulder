# M1 CDC Control Stage 8 Matched Flash

Date: 2026-09-21 (Asia/Shanghai)
Status: both matched images copied once; both application CDC interfaces re-enumerated by USB serial; control smoke pending.

## Matched UF2 copies

The bootloader volume mapping and board IDs were checked in Stage 7. Immediately
before each copy, the live serial-to-volume mapping, corresponding source image
hash, and absence of the destination filename were rechecked. Each
`Copy-Item` operation completed once:

| Node | USB serial | Board ID | Source UF2 SHA-256 | Destination | Copy completed (UTC) |
|---|---|---|---|---|---|
| A | `0000000000000001` | `Seeed_XIAO_nRF52840_Sense` | `010FA6CCAD28845F431C087B51071A717657BFA12BAFE9B78E65899E0CD46CFA` | `<device-volume>\m1_cdc_node_a.uf2` (E: / PhysicalDrive1) | 2026-09-21 14:32:30.3827180 |
| B | `0000000000000002` | `Seeed_XIAO_nRF52840_Sense` | `2796B5E38F123E191BC1F82314917CA6B024A73D3BAA0C19EA244AABEA014627` | `<external-root>\m1_cdc_node_b.uf2` (F: / PhysicalDrive2) | 2026-09-21 14:33:50.9263326 |

Both source UF2 files remain 312,320 bytes and their hashes still match the
Stage 5 build report. After the copies, E: and F: bootloader roots were no
longer present. USB CDC enumeration found both expected application serials:

| Node | Current port | USB serial | VID:PID |
|---|---|---|---|
| A | COM5 | `0000000000000001` | `2FE3:0004` |
| B | COM8 | `0000000000000002` | `2FE3:0004` |

The post-flash inventory was checked at 2026-09-21 14:37:03 UTC. COM numbers
are observations for this enumeration; future opens must resolve by USB serial.
The bootloader volumes disappeared after each copy, so file-level destination
readback was unavailable. The evidence is the successful single copy of each
rechecked source image followed by application-mode re-enumeration with its
matching USB serial.

## Preserved inputs and next gate

The Stage 7 preflash manifest remains unchanged at SHA-256
`54BB3F0F9F723B12930BF2D6CD6414674B6CE8709B1F7DA188BA9EF496EFBFD3`. The old
preflash manifest remains at SHA-256
`C4EF413589C0FA0B9326A1FFC8AEE167C0AADF55F7CF7BABA26D5383A3EC3CE5`; the
locked prior plan remains at SHA-256
`6B295C3C5CC5B2B9E06623D9E28B9A7DD70F342085DA66D29D3ABBF847B9D2D4`.
Stage 8's machine-local flash manifest is
`.cache/m1_cdc_stage8_flash_manifest_20260921.json`, SHA-256
`ABDB437E23B9084A8398C8F74BA839FE2559042E5C1913E1E7D4271A8D88552D`.

No CDC control smoke, BLE connection, parameter observation, acquisition
capture, formal v2 matrix, or new raw data collection has started. The next
gate is BLE-disconnected OFF→ON→OFF on each node, requiring complete serial
writes and matching ACK fields for node, transaction, requested mode, selected
mode, and return code. Stop on the first failed ACK or write.
