# ADR-012 — Release documentation and license selection

Status: Accepted by explicit maintainer instruction on 2026-09-28.

## Decision

The maintainer approved an English README with Chinese technical report, the
research-framework introduction presented for review, MIT for original project
code and documentation, and CC0-1.0 for the selected original synthetic sample.
The maintainer explicitly confirmed the right to publish that sample.
The copyright holder is **Hongbo Liao**. The first public package version is
**0.1.0**. Affiliation and ORCID are omitted at the maintainer's request.

The introduction describes tested dual-IMU acquisition, hardware-free replay
and synthetic validation, and humerothoracic shoulder movement analysis.
Human movement accuracy and clinical validation are not claimed.

## Final identity confirmation

After explanations and concrete proposals in chat, the maintainer explicitly
replied “三项同意” on 2026-09-28. This approves copyright year **2026**, project
citation author **Hongbo Liao** (given-names Hongbo; family-names Liao), and
public repository owner **TheSmashingPumpkinPies**. The approved publication
destination is **https://github.com/TheSmashingPumpkinPies/kineimu-shoulder**.
The current origin remains the management repository. Selecting a destination
does not establish that it exists publicly or authorize repository creation.

The root LICENSE contains the full MIT notice, including
`Copyright (c) 2026 Hongbo Liao`. CITATION.cff and package metadata contain the
approved author, MIT license, repository destination and version. The actual
publication date and DOI are omitted; no affiliation or ORCID is invented.
The exact sample permission is recorded in
[its current license annex](../../datasets/samples/m6_synthetic/LICENSE.md).
Original sample bytes, digest map and historical permission statements remain
unchanged; the dated annex supplies the current authorization.

## Boundaries and next checks

Third-party material and historical reference sources retain their own terms.
This decision does not license all historical experiments, hardware recordings
or dependency distributions under CC0, and does not change scientific claims,
schemas, dependencies, firmware or algorithms.

Prior internal preview artifacts are immutable records of the earlier draft.
Build and inspect new artifacts and independently install them using the
approved metadata. CP4 remains OPEN until verification; CP5 and actual
public publishing are separate steps. No push, tag, Release, PyPI upload,
repository creation, history rewrite or evidence migration is authorized here.
