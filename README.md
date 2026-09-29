# KineIMU Shoulder

A dual-IMU research framework for shoulder rehabilitation movement analysis,
providing acquisition, calibration, orientation estimation, humerothoracic
movement metrics and reproducible validation. It supports hardware-free replay
and synthetic demonstrations. Acquisition has been tested on the reference
hardware; human movement accuracy and clinical validation remain unestablished.
It is not a medical diagnosis system.

KineIMU Shoulder 面向肩部康复运动分析研究：以胸廓为参考，分析上臂相对运动，
并提供可追溯的采集、处理、指标和验证结果。

The public source candidate is version `0.1.0`. Original Python code/documentation
use MIT; existing reference-firmware SPDX notices retain Apache-2.0. The selected
synthetic sample has its own CC0 annex. M0–M6 are DONE within the documented local
V1 boundaries. Historical Windows acceptance and this audited public copy's checks
are distinct; see [public provenance](docs/PUBLIC_EXPORT.md) and
[evidence availability](docs/PUBLIC_EVIDENCE.md). No DOI or release tag is declared.
Machine paths and device identities in historical evidence are anonymized;
[the public audit](docs/PUBLIC_AUDIT.md) describes preserved results and copy integrity.

## What it does

- Records two identified IMUs as separate, immutable streams with timestamps,
  sequence counters, quality checks and provenance.
- Replays recorded or synthetic sensor data through calibration, quaternion
  orientation, explicit alignment and synchronization, and humerothoracic kinematics.
- Analyzes shoulder flexion and left/right abduction: ROM, peak elevation,
  repetition count, movement and phase duration, holds, angular speed,
  repetition variability and a thorax excursion proxy.
- Exports machine-readable results and a readable summary, preserving units,
  evidence labels, valid denominators and reasons for unavailable values.

The reference hardware is two Seeed Studio XIAO nRF52840 Sense boards with
LSM6DS3TR-C IMUs. **Physical acquisition validation passed for dual USB** in M1;
dual BLE remains limited. The analysis stack runs independently of live hardware.

## Quick start

Use **CPython 3.12.14** and **uv 0.12.5**:

```powershell
git clone https://github.com/TheSmashingPumpkinPies/KineIMU-Shoulder.git
cd KineIMU-Shoulder
uv sync --extra analysis --frozen
uv run --frozen python examples/m6_demo.py --output demo-output-01
```

The demo requires no XIAO devices, external M1 recordings or `PYTHONPATH` changes.
Dependency installation requires network access or a populated cache. Windows is
the measured platform; Linux acceptance has not been executed.

The [bundled sample](datasets/samples/m6_synthetic/README.md) contains four
synthetic trajectories: flexion, left abduction, right abduction and flexion with
a moving thorax. All eight sensor streams pass through the full processing chain.
The selected original sample files are approved for public reuse under
[CC0-1.0](datasets/samples/m6_synthetic/LICENSE.md). Their original provenance
and historical INTERNAL ONLY labels are preserved; the dated license annex
records the current permission without rewriting original evidence.

Open `demo-output-01/summary.md` after a successful run:

```text
demo-output-01/
  summary.md          readable metrics, QC and evidence boundaries
  run.json            runtime, source, input and output provenance
  SHA256SUMS.txt       output integrity index
  replay/             processed, derived, annotations and error artifacts
```

Successful runs exit with code 0 and produce 26 files. Use a new output directory
for each run: existing paths are rejected, and partial failed runs are retained.
Inside the checkout, use a new top-level `demo-output-*` directory.
See [demo usage and output semantics](docs/M6_DEMO.md) for failure codes,
determinism and the distinction between the M6 run and historical M5 report status.

The demo runs from a **repository clone** with its Git metadata, protocols,
fixtures and sample. The library wheel and sdist do not contain the complete demo
or acceptance evidence. No `kineimu-shoulder` console command is implemented;
the supported demo entry is the Python script above.

## Evidence and limits

| Evidence layer | Established scope | Evidence |
|---|---|---|
| Hardware acquisition | A 30-minute physical dual-USB bench passed its acquisition gates; hardware is frozen | [M1 result](experiments/M1_DUAL_USB_30MIN_RESULT_20260925.md) |
| Calibration and orientation | Known-input numerical and replay checks; physical calibration accuracy is unestablished | [M2 acceptance](experiments/M2_REPLAY_20260925/README.md) |
| Kinematics and exercise analytics | Synthetic numerical and evidence-interface checks | [M3](experiments/M3_CP4_20260925/README.md), [M4](experiments/M4_CP5_20260926/README.md) |
| Robustness and recorded replay | Finite synthetic perturbation design and complete recorded replay; missing evidence remains unavailable | [M5 coverage and acceptance](experiments/M5_CP5_20260928/README.md) |
| Complete hardware-free demo | Four stored synthetic trajectories, independent numerical audit and two-process determinism | [M6 CP2](experiments/M6_CP2_20260928/README.md) |
| End-to-end benchmark | One warmup and five timed Windows runs; includes startup, validation and I/O | [Protocol, results and reproduction](benchmarks/demo/REPORT.md) |

Outputs describe **humerothoracic movement**: upper arm relative to thorax.
They do not establish glenohumeral or scapular angles. Static gravity alone does
not identify full anatomical heading; independent AHRS worlds need explicit
common-world and timing evidence before relative orientation is meaningful.

The default demo is synthetic with `anatomical_eligible=false`. Its known
calibration, alignment, heading and clocks are constructed assumptions. Real M1
recordings lack the supporting pairwise timing, heading and anatomical alignment
evidence, so recorded shoulder metrics remain null/invalid. A thorax excursion
proxy is descriptive and is not a clinical compensation score.

This project is not a diagnostic system or a clinically validated device.
Human-subject, motion-capture and clinical validation, battery integration,
enclosures and wearability are outside current V1 scope. No injury-risk, pain,
fatigue or clinical outcome score is provided.

## Documentation

| Topic | Start here |
|---|---|
| System and evidence overview | [Technical report](docs/M6_TECHNICAL_REPORT.md) |
| Scope and architecture | [Project scope](PROJECT_SCOPE.md), [architecture](ARCHITECTURE.md) |
| Hardware and acquisition | [Hardware profile](HARDWARE_PROFILE.md), [firmware](firmware/xiao_nrf52840_sense/README.md), [acquisition contract](protocols/M1_ACQUISITION_CONTRACT.md) |
| Units, frames and time | [Data format](DATA_FORMAT.md), [frame conventions](protocols/M2_PROCESSING_CONTRACT.md), [synchronization](SYNC_PROTOCOL.md) |
| Processing and algorithms | [Backend contracts](BACKEND_CONTRACTS.md), [M2](protocols/M2_PROCESSING_CONTRACT.md), [M3](protocols/M3_KINEMATICS_CONTRACT.md), [M4](protocols/M4_EXERCISE_CONTRACT.md), [processing/1.1](protocols/M5_PROCESSING_V1_1.md) |
| Validation and reproduction | [M5 coverage](experiments/M5_CP5_20260928/COVERAGE.md), [reproduction](experiments/M5_CP5_20260928/REPRODUCE.md), [benchmark reproduction](benchmarks/demo/REPRODUCE.md) |
| Release review and artifacts | [Review sheet](docs/release/REVIEW.md), [packaging guide](docs/release/PACKAGING.md), [release checklist](docs/M6_RELEASE_CHECKLIST.md) |

## Development

Package/import: `kineimu_shoulder`. Repository/reserved CLI name:
`kineimu-shoulder`. Internally, calculations use SI units and normalized
quaternions; displayed angles declare degrees explicitly. Raw bytes remain
immutable, and transforms, resampling and reconstruction are explicit stages.

```powershell
uv sync --all-extras --frozen
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen python scripts/check_docs_consistency.py
uv build
```

Full tests need a fresh temporary directory outside the checkout for demo path
guards. Two physical replay tests require the external M1 raw root; absence is
reported as a skip, not physical replay verification. See the
[packaging verification record](experiments/M6_CP4_FINAL_20260928/README.md).
Read [AGENTS.md](AGENTS.md) and [contribution guidance](CONTRIBUTING.md) before editing.
Selected experiments preserve reproducibility. Full internal history, legacy reference
materials and repeated large runs are omitted; their availability is documented.

## License and citation

Original project code and documentation are licensed under **MIT**:
Copyright (c) 2026 **Hongbo Liao**. See [LICENSE](LICENSE).
Existing Apache-2.0 firmware and third-party material retain their own terms;
firmware license text is in `firmware/xiao_nrf52840_sense/LICENSE.Apache-2.0.txt`.
Selected synthetic sample files have a separate
[CC0-1.0 license annex](datasets/samples/m6_synthetic/LICENSE.md).
Additional reviewed original data have a separate
[701-member CC0 annex](docs/PUBLIC_DATA_LICENSE.md); this does not expand the
original25-member sample grant. Third-party material keeps its own terms
in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

[CITATION.cff](CITATION.cff) provides the approved project author **Hongbo Liao**,
title, version and repository destination. Cite **Hongbo Liao, KineIMU Shoulder,
version 0.1.0 [software]**, with the exact source revision used.
Retain the processing version, input provenance and evidence boundaries.
Publication date and DOI are omitted until an actual publication exists.
