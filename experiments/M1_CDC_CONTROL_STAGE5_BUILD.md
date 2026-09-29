# M1 CDC Control Stage 5 and Stage 6 Build Audit

Date: 2026-09-21 (Asia/Shanghai)
Status: software and image gates passed; UF2 bootloader identity check pending.

## Build provenance

Both experiment images were built from repository source HEAD
`545e38d6b86c9a773a609a93526405493861976b`, for
`xiao_ble/nrf52840/sense`, with upstream Zephyr 4.4.0
(source commit `684c9e8f32e4373a21098559f748f06915f950c9`) and Zephyr SDK 1.0.1.
The experiment option was enabled in both images. Their only node-specific build
definition is Node A `KINEIMU_NODE_ID=1` and Node B
`KINEIMU_NODE_ID=2`.

The common overlay is
`experiments/M1_CONN_PARAM_ROOTCAUSE.overlay.conf`, SHA-256
`1B2BB4FAFA44259BAB33829EEE932EFA993F6AEBE6F82D7367DAA791AF78C9EB`.
The generated `.config` files are byte-identical: 57,969 bytes with SHA-256
`0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69`.
Both disable automatic peripheral connection updates and retain preferred
interval settings 24–40 (30–50 ms), latency 0 and timeout 42 (420 ms); the
Zephyr connection update timeout remains 5,000 ms.

## Image identity

| Node | Node ID | UF2 bytes | UF2 SHA-256 | ELF SHA-256 |
|---|---:|---:|---|---|
| A | 1 | 312,320 | `010FA6CCAD28845F431C087B51071A717657BFA12BAFE9B78E65899E0CD46CFA` | `B436F1D98110D119D0323CF856ED8ADC82F555D9A2BDC10D63FC3B30FA3FB94D` |
| B | 2 | 312,320 | `2796B5E38F123E191BC1F82314917CA6B024A73D3BAA0C19EA244AABEA014627` | `DC822EC3093A61BA9EFD6D7CA829E970B11683A97B4D30E78874BA3459C7806C` |

Both UF2 files contain 610 valid, contiguous 512-byte blocks with 256-byte
payloads, nRF52840 family ID `0xADA52840`, and flash address range beginning
at `0x00027000`. Their embedded build definitions were checked against the
source commit and node IDs above. The files are in isolated build directories:

- A: `<external-root>/zbuild/kineimu_m1_cdc_control_stage5_node_a_20260921/zephyr/zephyr.uf2`
- B: `<external-root>/zbuild/kineimu_m1_cdc_control_stage5_node_b_20260921/zephyr/zephyr.uf2`

## Resource and stack audit

The pinned SDK size utility reported:

| Node | text (bytes) | data (bytes) | bss (bytes) | total |
|---|---:|---:|---:|---:|
| A | 153,076 | 2,936 | 45,224 | 201,236 |
| B | 153,080 | 2,936 | 45,224 | 201,240 |

For compiler stack estimates, every generated C compile command was repeated
with GCC `-fstack-usage`. This produced 243 `.su` files per node, with zero
compiler warnings. Diagnostic objects and reports are under ignored
`.cache/m1-cdc-stage5-stackusage-{a,b}-20260921/`; the flashable build
directories and UF2 files were not modified by the scan.

| Function frame | Node A | Node B |
|---|---:|---:|
| `publish_status_if_due` | 1,096 B | 1,096 B |
| `publish_status` | 600 B | 600 B |
| `main` | 488 B | 496 B |
| `tx_worker` | 160 B | 160 B |
| `write_clock_request` | 160 B | 160 B |

Configured stack allocations include main 4,096 B, system workqueue 2,048 B,
Bluetooth RX 1,200 B, Bluetooth TX processor 1,024 B, USB device 1,024 B, and
the application TX worker 1,536 B. The `.su` results are per-function static
frames; they do not measure the full call-chain peak or runtime high-water.
Runtime thread analysis is not enabled in the flash images.

Both firmware builds completed and emitted device-tree and UF2 outputs. The
host build reported a nonfatal DTC-not-found message; the separate compiler
stack scan emitted no compiler warnings.

## Device and preservation gates

At the last application-mode USB enumeration, pyserial resolved Node A serial
`0000000000000001` to COM4 and Node B serial
`0000000000000002` to COM7 (VID:PID `2886:0045`). COM numbers must be
rediscovered by USB serial after bootloader entry and after flashing. The
required bootloader board ID `Seeed_XIAO_nRF52840_Sense` has not yet been
observed in this checkpoint.

The new machine-local manifest is
`.cache/m1_cdc_stage5_build_manifest_20260921.json`, SHA-256
`3CA8D277EF1B4FDC35C25B8BCAC02BC49226572779AB287B3D12DE7F5BFA53B0`.
The previous preflash record remains unchanged at SHA-256
`C4EF413589C0FA0B9326A1FFC8AEE167C0AADF55F7CF7BABA26D5383A3EC3CE5`.
The prior plan remains at SHA-256
`6B295C3C5CC5B2B9E06623D9E28B9A7DD70F342085DA66D29D3ABBF847B9D2D4`; it is
not the plan for a future v2 matrix.

No board has been flashed in this checkpoint, and no BLE smoke or new data
capture has started. After the maintainer puts both boards into UF2 bootloader
mode, verify each `INFO_UF2.TXT` board ID and the USB-serial-to-volume mapping.
Only then copy each matching image once. M1 remains open; M2 has not started.
