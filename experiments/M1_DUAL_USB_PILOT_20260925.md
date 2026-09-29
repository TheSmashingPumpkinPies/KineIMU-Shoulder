# M1 Dual USB Readiness Pilot — 2026-09-25

The first 15-second simultaneous USB pilot established concurrent capture and integrity, but **did not pass the timing gate**: the first post-arm sample interval was shorter than a full ODR period. The startup-boundary firmware correction was flashed to both identified boards, and the fresh physical pilot **passed the predeclared acquisition-stability limits**. Direct continuation on the same running boards passed a separate smoke test. The formal 30-minute run has not started. Preserve both original result roots: `.cache/m1_usb_dual_pilot_20260925_01` and `.cache/m1_usb_dual_pilot_20260925_02`.

## Board and image identity

The pinned Zephyr v4.4.0 / SDK 1.0.1 builds used source commit `cbb2a8bbdda6be82ca893781d450c731b680ebae` and board `xiao_ble/nrf52840/sense`. A/B generated `.config` files were byte-identical, SHA-256 `E33B9EF61626DD7623C8A080C4682003E3E595B6D5ED260C06222A227D015A2D`. Each image used the intended node ID. Both built at 66,200 B FLASH and 14,648 B RAM, producing 132,608-byte UF2 files.

| Node | Bootloader serial / verified drive | UF2 SHA-256 | Application CDC |
|---|---|---|---|
| A | `0000000000000001` / E: | `C6BC9806BE60BD59857162CEBA270E4DB383546FEB7B7B3EC96DB61FB670D6DD` | COM5 |
| B | `0000000000000002` / F: | `B5ADBBB17F59CF636832B1F8E682CB9DD0F4A3B9928D328E80651A7838F35483` | COM8 |

Both UF2 volumes reported `Seeed_XIAO_nRF52840_Sense`. Live disk serial/drive mapping was checked immediately before each copy. Both app ports re-enumerated with VID:PID `2FE3:0004`. The runner resolved each by serial and verified the matching 64-bit FICR ID in its USB banner.

## Observed short capture

| Measure | A | B |
|---|---:|---:|
| Valid packets / samples | 390 / 1,560 | 394 / 1,576 |
| Device-time effective sample rate | 104.34 Hz | 106.38 Hz |
| Packet / sample sequence gaps | 0 / 0 | 0 / 0 |
| Malformed / framing errors | 0 / 0 | 0 / 0 |
| Maximum sample interval | 9,704 µs | 9,521 µs |
| Maximum absolute interval deviation from epoch median | 4,883 µs | 4,821 µs |
| Timestamp duplicate / reorder | 0 / 0 | 0 / 0 |
| Recorder QC / complete packet stop | pass / pass | pass / pass |

Both host capture-start timestamps were `94622718000000` ns. A stopped at `94637906000000` ns and B at `94637796000000` ns. The measured overlap was 15.078 s, above the 15.000 s scheduled window. The pilot runner initially reported an uncapped overlap/schedule ratio of `1.0052`; a regression test exposed this presentation error, and the runner now caps the reported fraction at 1.0. The original result JSON was not rewritten.

Raw `.kimu` SHA-256: A `719154E49CB9A81F1DC40960511403AA09FFF1174BA88F843565AF894A6CF327`; B `780640B364E75F05FA54B577BEF04F9288892E8F2168ED2DEFC14B43E7EC7CEC`. Exact USB bytes: A `937ADF3E0DC838D9D797769C7FA09A4281BED61D6E3656D9DBB3B6A2B8DB4B9E`; B `A4627782A599DA9E02A520E45EF58C34CFE94FACAFA9647242287F4975BE0D06`.

The event files hash to A `CB7812897F2D3DC8E9C1D6D4FFB0399C25ADB659A5CDD0909ABED36766F8463F` and B `2105C55F67ED7166B5A150ECD8337898B9A7D6AA59A7CFE94AA95F9861562E4C`. The pilot run configuration SHA-256 is `19F9F094FD9EA7EAAB57D0FAF3C03D3CADBA7238651323F5D929DC5A8E73BFF2`; original result SHA-256 is `C7D15C21ADA6468F614202BDF5548923F7BC9A7ACCF055E6854D53A6FCE7BE65`; read-only summary SHA-256 is `69C36B0178CF8A90480AA4C369195019CB53502104BCF89327EC88A64DD3409A`.

The single short interval on each node exceeded the predeclared 2 ms maximum absolute interval-deviation limit. Later contiguous intervals remained near the configured ODR. This pilot demonstrates short concurrent USB packet delivery and integrity on the selected hardware, while recording the timing-gate failure without rewriting the raw evidence. It does not establish 30-minute stability, BLE dual-link performance, clock alignment, or clinical measurement accuracy.

## Corrected physical pilot and direct continuation

The updated USB firmware source is commit `5f81e2e14a15cb1f379f3c2d16598c9c246b1904`. The A/B reference-board builds used the same pinned Zephyr v4.4.0 / SDK 1.0.1 configuration and byte-identical `.config` SHA-256 `E33B9EF61626DD7623C8A080C4682003E3E595B6D5ED260C06222A227D015A2D`. Both compiled at 66,316 B FLASH and 14,648 B RAM. A UF2 SHA-256 is `C184CB89CB364C8908FB12AC3672F5C16BC1716E8020A72B976BE33FBBABBFA0`; B is `BE4A8829D0647388D9DB67E784CBB9558C64CFB967E03434DC281E3BE53A7401`. Live bootloader serials `0000000000000001` and `0000000000000002` mapped to E: and F: immediately before flashing; both reported `Seeed_XIAO_nRF52840_Sense`. The applications re-enumerated as COM5/COM8.

The fresh 15-second concurrent pilot at `.cache/m1_usb_dual_pilot_20260925_02` passed its runner assessment (`ready=true`, overlap fraction 1.0). The byte-preserving raw and event sidecars passed identity, packet, sequence and framing QC:

| Measure | A | B |
|---|---:|---:|
| Valid packets / samples | 389 / 1,556 | 398 / 1,592 |
| Device-time effective rate | 104.31 Hz | 106.34 Hz |
| Median sample interval | 9,583 µs | 9,399 µs |
| p99 absolute interval deviation | 30 µs | 31 µs |
| Maximum absolute interval deviation | **91 µs** | **92 µs** |
| Packet/sample gaps, malformed/framing errors, timestamp duplicate/reorder, packet flags | 0 | 0 |

The predeclared maximum deviation gate is 2,000 µs; this short run now passes by direct measurement. The capture start timestamps matched at `96332468000000` ns. A/B stops were `96347640000000` / `96347671000000` ns. Raw `.kimu` hashes: A `C7A1458C0E3E50BC5FAC61C94C65ECADFD24CE175900997797BBC37E2DE3E20`, B `6E09A2AF2934967DF5438D1061F3B7F0DC50D8C58EC09A4691E332A0AD1A6F68`. Exact USB byte hashes: A `AECB415F3F7986345EF8A7FA5D903B6CD3B12411C67A110FCF0F5256D23C8F10`, B `3259411EACA8BEFA6930D0CAAF9F9C722FFA779FF83B97B48BCB74FCBC7606A3`. Event hashes: A `5E1FB83A13772D0545DFA4B7C0B31FA9DEFC893C5E1B093A7C7A4361953964D1`, B `31D178CF139EAF87C3BD4EC2ABA9783F3C5F09CE401C1EA33DE5B19AD6817724`. Config/result/summary hashes are `E477421606222E15411146F7D19B44E9B892E26C382660CF1840AF4F180099C9`, `4F2955F8DE5DC14879F956461D40EB412586513F52A972068A70E130148D010F` and `F7CED5AD30BB93622580D1ACC6459E685EFC1BA52D46A268682C90784C493525`.

Opening the already-running USB ports for a 2-second continuation initially exposed a real stale CDC backlog on B: 6,493 missing packet sequences appeared between old buffered packets and current output. That failed attempt remains at `.cache/m1_usb_continuation_smoke_20260925_01`. The runner now saves all pre-capture bytes separately, drains the backlog, and starts timed capture at complete packet boundaries. The repeat at `.cache/m1_usb_continuation_smoke_20260925_02` passed: each board delivered 54 packets / 216 samples, zero packet/sample gaps or parser errors, overlap fraction 1.0, and maximum interval deviations 30/31 µs. Its pre-roll files are separately hashed in the result and sidecars. Result SHA-256 is `112856449F4A6CF72727785ABBD914F563B49EDC20D1359DB6313C46DA36203B`; summary SHA-256 is `829D440C862A7F182CC2084B3639E01EE265A0F79DBFDCBC8FF75FC73AE55FD0`. The formal command can start on the current connected boards without another manual reset. These short runs do not establish 30-minute stability, pairwise clock mapping or dual BLE performance.
