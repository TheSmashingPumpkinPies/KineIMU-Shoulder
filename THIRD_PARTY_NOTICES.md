# Third-party notices — KineIMU Shoulder

M6.4 release-review draft, 2026-09-28. The selected project license does not
relicense third-party code, data, documentation, firmware, tools or notices.
Original active project code and original documentation are licensed under
MIT with Copyright (c) 2026 Hongbo Liao; see [LICENSE](LICENSE). This grant
excludes third-party works and immutable historical reference sources.
Selected original
synthetic sample permission is approved under
[its CC0-1.0 annex](datasets/samples/m6_synthetic/LICENSE.md).
Approved identities and release gates are recorded in [the review sheet](docs/release/REVIEW.md).

The Python wheel/sdist declare dependencies and do not bundle their code or
native libraries. The [license snapshot](docs/release/licenses/README.md) retains
actual installed upstream texts byte-for-byte, with version/source/hash inventory.
These texts accompany the internal preview artifacts. Their inclusion is not a
claim that all possible platform or firmware distributions have been cleared.

## Direct Python dependencies

| Component | Pinned version | Upstream license / qualification | Role / source |
|---|---|---|---|
| NumPy | 2.5.2 | BSD-3-Clause core; installed metadata expression also includes 0BSD, MIT, Zlib, CC0-1.0; bundled native-library terms remain in full license text | Arrays; [NumPy](https://github.com/numpy/numpy) |
| SciPy | 1.18.1 | BSD-3-Clause core, with additional component and native-library notices | Rotation / numerical methods; [SciPy](https://github.com/scipy/scipy) |
| pandas | 3.0.5 | BSD-3-Clause; full distribution notice retained | Tables; [pandas](https://github.com/pandas-dev/pandas) |
| imufusion / Fusion | 1.3.3 | MIT | Optional orientation/analysis; [Fusion](https://github.com/xioTechnologies/Fusion) |
| imucal | 2.6.0 | MIT | Optional calibration/analysis; [imucal](https://github.com/mad-lab-fau/imucal) |
| Bleak | 3.0.2 | MIT | Optional BLE capture; [Bleak](https://github.com/hbldh/bleak) |
| pyserial | 3.5 | BSD-3-Clause; installed wheel lacks a license file, upstream v3.5 text tracked separately | Optional USB capture; [v3.5 license](https://github.com/pyserial/pyserial/blob/v3.5/LICENSE.txt) |

Pinned versions are taken from [pyproject.toml](pyproject.toml) and [uv.lock](uv.lock).
The top-level license shorthand is not a replacement for full notices. In
particular, NumPy/SciPy installed license files contain OpenBLAS/LAPACK and
compiler-runtime terms, including GPL with runtime exception where specified.
Preserve the complete files if redistributing those dependency binaries;
do not describe an entire dependency environment as exclusively MIT/BSD.

## Transitive dependencies and tools

The machine-readable snapshot covers installed Windows/Python 3.12 distributions
with name, version, metadata/license classifiers, direct/transitive/tool role,
upstream declared license files and copied text hashes. Runtime transitives
include python-dateutil (2.9.0.post0, BSD/Apache terms in its notice), six
(1.17.0, MIT), tzdata (2026.3, Apache-2.0 with timezone-data notices), and the
WinRT projection/runtime family (3.2.1, MIT) plus typing_extensions (4.16.0,
PSF-2.0). pyserial and WinRT texts absent from their installed wheels are retained
from the official v3.5 / v3.2.1 upstream tags with URL/hash identity in the
[reference inventory](docs/release/licenses/upstream-references.json).
Linux/macOS optional BLE transitives are locked separately
and are not claimed reviewed by this Windows inventory.

Development tools are pytest 9.1.1, Ruff 0.16.6 and mypy 2.3.1 (MIT), with their
transitives under their own licenses. Build uses Hatchling 1.27.0 (MIT); host tools
are CPython 3.12.14 (PSF and included notices) and uv 0.12.5 (MIT/Apache-2.0).
These tools are not shipped inside the project wheel. Consult the original
distributions for embedded notices. The lockfile is the dependency-version
authority, not this summary alone.

The validation-only CFF 1.2.0 schema retained in the
[CP4 evidence](experiments/M6_CP4_20260928/README.md) is an unmodified copy from
the Citation File Format project under CC-BY-4.0. Its official
[source](https://github.com/citation-file-format/citation-file-format/tree/1.2.0),
[original license](experiments/M6_CP4_20260928/cff-upstream-LICENSE.txt) and
[original author/citation notice](experiments/M6_CP4_20260928/cff-upstream-CITATION-cff.txt)
are preserved. The schema is not included in the Python wheel/sdist.
PyYAML/jsonschema were used from existing external validation tooling, without
adding either to the project dependency lock.

## Firmware and external assets

| Item | Licensing / distribution boundary |
|---|---|
| Zephyr v4.4.0 | Apache-2.0 core; per-file SPDX and module-specific licenses; [upstream LICENSE](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/LICENSE) |
| Zephyr SDK 1.0.1 / west modules | Toolchain/module-specific licenses; revisions/checksums recorded in [firmware evidence](firmware/xiao_nrf52840_sense/README.md) and [west freeze](firmware/xiao_nrf52840_sense/west-zephyr-v4.4.0.freeze.txt) |
| Zephyr st,lsm6dsl driver | In-tree selected driver; its source/license and exact build modules remain upstream responsibilities, not a claim of a BSD-only firmware binary |
| ST lsm6ds3tr-c-pid | BSD-3-Clause reference; [upstream](https://github.com/STMicroelectronics/lsm6ds3tr-c-pid); not the active selected dependency |
| Historical StickS3/ESP-IDF material and reference project pack | Historical provenance, outside current Python runtime; not automatically relicensed by a future root license |
| Synthetic demo sample | Selected original files approved under CC0-1.0 in the dated sample license annex; historical provenance/permission labels unchanged; no human data |

No firmware UF2, SDK, third-party source tree or dependency wheel is added to the
Python package by this step. A later firmware-binary/public-evidence distribution
must audit the actual binary/source members and preserve their original notices.
The firmware freeze records reproducibility; it is not a blanket license review.

## Algorithm and scholarly attribution

1. **Orientation software:** x-io Technologies, Fusion / imufusion 1.3.3.
   [Upstream algorithm description](https://github.com/xioTechnologies/Fusion#ahrs-algorithm)
   identifies the revised AHRS in chapter 7 of
   [Madgwick's thesis](https://x-io.co.uk/downloads/madgwick-phd-thesis.pdf).
   This is distinct from the initial chapter-3 algorithm. Cite the actual backend
   and retain its MIT text; no thesis text or algorithm is vendored here.
2. **Calibration software:** Küderle, A., Roth, N., Richer, R., & Eskofier, B. M.
   (2022). *imucal — A Python library to calibrate 6 DOF IMUs*.
   Journal of Open Source Software, 7(73), 4338.
   [DOI 10.21105/joss.04338](https://doi.org/10.21105/joss.04338).
   This is the software citation recommended by the installed upstream README.
   Its Ferraris-method lineage is documented in the
   [upstream guide](https://imucal.readthedocs.io/en/latest/guides/ferraris_guide.html).
   KineIMU's tested affine estimation and gyro-bias handling must not be described
   as a completed physical Ferraris calibration protocol.
3. **Rotations:** SciPy `Rotation` supplies established numerical operations.
   Project-specific coordinate and quaternion semantics are specified in
   [the M2 contract](protocols/M2_PROCESSING_CONTRACT.md).
4. **Project models and exercise analytics:** attribution and written rationale
   remain in [processing/1.1](protocols/M5_PROCESSING_V1_1.md),
   [ADR-010](docs/adr/ADR-010-explicit-short-gap-reconstruction.md),
   [ADR-011](docs/adr/ADR-011-recorded-quality-segments.md) and
   [the M4 contract](protocols/M4_EXERCISE_CONTRACT.md). These are tested project
   methods within finite synthetic/replay domains, with no clinical validity claim.

Software attribution, algorithm lineage and project authorship are separate.
The project [CITATION.cff](CITATION.cff) names the approved author Hongbo Liao
and repository destination; dependency authors remain separate attributions.
