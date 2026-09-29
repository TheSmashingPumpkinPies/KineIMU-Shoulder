# KineIMU Shoulder

A hardware-tested dual-IMU research framework for shoulder rehabilitation movement
analysis. It provides acquisition, calibration, quaternion orientation,
humerothoracic kinematics, exercise metrics and reproducible validation.
The complete hardware-free demo runs without devices.

KineIMU Shoulder 以胸廓为参考分析上臂运动，提供可追溯的采集、处理、指标与验证结果。
本项目用于研究，不是医疗诊断系统，也未建立人体运动精度或临床有效性。

## Quick start

Use CPython **3.12.14** and uv **0.12.5**:

```powershell
git clone https://github.com/TheSmashingPumpkinPies/KineIMU-Shoulder.git
cd KineIMU-Shoulder
uv sync --extra analysis --frozen
uv run --frozen python examples/m6_demo.py --output demo-output-01
```

Open `demo-output-01/summary.md`. The demo replays four stored synthetic trajectories:
flexion, left/right abduction and flexion with a moving thorax. Eight streams pass
through decoding/QC, calibration, orientation, alignment, synchronization and metrics.
A successful run exits 0 and produces 26 files with input/source/output hashes.
Use a new output directory for every run; failed partial outputs are preserved.
See [demo usage](docs/M6_DEMO.md) and [output contract](docs/M6_DEMO_CONTRACT.md).

The demo needs a repository clone, including Git, protocols, fixtures and samples.
Library packages provide analytical APIs rather than the complete repository demo.
Dependency installation needs network access or a populated cache. Windows is the
verified platform; Linux execution remains unverified. CI performs Linux checks when run.

## Capabilities and evidence

- Separate immutable dual-node recordings with timestamps, sequence counters and QC.
- Explicit SI units, frames, quaternion orientation, calibration and synchronization.
- Shoulder flexion and abduction: ROM, peak elevation, repetitions, movement/phase
  duration, holds, angular speed, repetition variability and thorax excursion proxy.
- Machine-readable results and summaries with validity reasons and evidence labels.

Physical acquisition validation passed on two Seeed Studio XIAO nRF52840 Sense
boards with LSM6DS3TR-C IMUs using dual USB. Hardware is frozen within V1 scope;
dual BLE throughput remains a documented limitation. M0–M6 are DONE within the
documented engineering boundary. This does not establish human or clinical accuracy.

| Topic | Documentation |
|---|---|
| Scope and system | [Scope](PROJECT_SCOPE.md), [architecture](ARCHITECTURE.md), [metric definitions](docs/METRICS.md) |
| Hardware and capture | [Hardware](HARDWARE_PROFILE.md), [firmware](firmware/xiao_nrf52840_sense/README.md), [mounting](MOUNTING_PROTOCOL.md), [acquisition contract](protocols/M1_ACQUISITION_CONTRACT.md) |
| Units and processing | [Data format](DATA_FORMAT.md), [backends](DEPENDENCIES.md), [processing contracts](protocols/M2_PROCESSING_CONTRACT.md), [reconstruction](protocols/M5_PROCESSING_V1_1.md) |
| Validation | [Methods and commands](VALIDATION.md), [coverage](docs/validation/coverage.md), [reproduction](docs/validation/reproduce.md), [technical report](docs/M6_TECHNICAL_REPORT.md) |
| Benchmarks | [Protocol](benchmarks/demo/PROTOCOL.md), [historical results](benchmarks/demo/REPORT.md), [reproduction](benchmarks/demo/REPRODUCE.md) |
| Distribution and rights | [Packages](docs/release/PACKAGING.md), [third-party notices](THIRD_PARTY_NOTICES.md), [public audit](docs/PUBLIC_AUDIT.md) |

Outputs describe **humerothoracic movement**, not glenohumeral or scapular angles.
Static gravity does not determine anatomical heading. Recorded shoulder metrics
remain null/invalid when timing, heading or anatomical alignment evidence is missing.
The default demo is synthetic with `anatomical_eligible=false`; its calibration,
alignment and clocks are constructed assumptions. Human-subject, motion-capture
and clinical validation, battery/enclosure and wearability are outside V1 scope.

## Tests and builds

```powershell
uv sync --all-extras --frozen
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen mypy benchmarks/demo/run_benchmark.py
uv run --frozen python scripts/check_docs_consistency.py
uv build
```

Tests use temporary outputs outside the checkout. Two optional physical replay
tests require external M1 recordings; absence is reported as a skip.
Numerical changes require independent known-input tests and explicit units/frames.
Preserve raw records, failed results and upstream notices.

Repository/reserved CLI name: `kineimu-shoulder`; import: `kineimu_shoulder`.
The supported demo entry is the Python script; no console command is implemented.

## License and citation

Original project code and documentation: [MIT](LICENSE), Copyright (c) 2026
Hongbo Liao. Firmware and dependencies retain their respective licenses and
[full notices](THIRD_PARTY_NOTICES.md).
The original 25 demo input files retain their unchanged [CC0 permission](datasets/samples/m6_synthetic/LICENSE.md).
Additional retained original records have a separate [bounded grant](docs/PUBLIC_DATA_LICENSE.md).
No grant extends to software or third-party works.

Use [CITATION.cff](CITATION.cff) and cite Hongbo Liao, *KineIMU Shoulder*,
version 0.1.0 [software], with the exact revision and processing/input identities.
No DOI or release tag is declared.
