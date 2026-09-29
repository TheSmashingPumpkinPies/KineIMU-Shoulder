# Project Scope — KineIMU Shoulder

Accepted 2026-09-07 and bounded for V1 on 2026-09-19:
[ADR-005](docs/adr/ADR-005-pivot-to-kineimu-shoulder.md) and
[ADR-008](docs/adr/ADR-008-hardware-tested-software-complete-v1.md).

KineIMU Shoulder is a hardware-tested, open-source dual-IMU research framework for
quantitative shoulder rehabilitation motion analysis.

KineIMU Shoulder 是一个经过真实双 IMU 采集层测试、可脱离硬件运行的开源肩部康复运动分析研究框架。本项目不是医疗诊断系统。

## V1 scope

Shoulder-only. Two IMUs provide upper-arm movement relative to a thorax reference.
V1 exercise analytics focus on shoulder flexion and abduction. Scaption and external
rotation are future candidates, not V1 accuracy claims. Sessions support research-grade
exercise summaries and longitudinal session comparison.

Eight core families are frozen in [01_PROJECT_SPEC.md](01_PROJECT_SPEC.md):
humerothoracic ROM, peak elevation angle, repetition count, movement/phase duration,
hold duration, angular velocity, rep-to-rep variability and thorax compensation excursion.
M3 implements relative kinematics; M4 implements the focused exercise metrics,
including the thorax-compensation proxy, after acquisition/alignment gates.

Extensions: target attainment rate, movement smoothness (SPARC/LDLJ candidates),
within-set ROM trend and longitudinal trend. M6 can track validated core values across sessions;
extended interpretation and smoothness are not initial core deliverables.

## Boundaries

Outputs describe humerothoracic movement/elevation or upper-arm relative to thorax.
Excluded: glenohumeral ROM; scapular upward rotation, posterior tilt, internal/external rotation;
scapulohumeral rhythm; shoulder instability score; rotator cuff diagnosis; pain prediction;
injury-risk prediction; fatigue score; clinical rehabilitation outcome score.
No unvalidated compensation score or pathological interpretation of movement variability.

Static gravity alone cannot determine full anatomical heading. With 6DoF sensing,
absolute yaw drifts and relative heading requires duration-dependent validation.
No diagnostic or clinically validated claim without appropriate evidence.

## Retained engineering foundation

M0 is DONE: preserve Git/CI, handoff, SOURCE_OF_TRUTH, ADRs, reproducibility, governance,
dependency management, tests, canonical IMU concepts, QC, provenance and validation discipline.
V1 is session-based, with synchronized dual-node raw capture to PC and explicit processed data.
No all-day standalone logging promise, custom PCB, cloud/account platform, complex ML or large dashboard.
M6 UI is minimal; selected embedded work follows validated reference code.

Gait/posture and other body/joint applications are excluded from active scope, dependencies and roadmap.
No reserved modules or universal motion/body abstractions. Future KineIMU Gait or KineIMU Posture
must be separate projects; reuse mature technology only when a concrete need exists.

## V1 completion boundary

V1 requires physical two-device acquisition evidence, recorded replay, deterministic
synthetic validation, automated algorithm tests and a complete hardware-free demo.
After the M1 dual USB transport path passes its 30-minute bench run, hardware is
frozen unless a later firmware/acquisition defect is discovered. The dual BLE
throughput limitation remains explicit under ADR-009.

Not required for V1: battery integration, enclosure, retention product design, human
wear testing, volunteer or patient studies, motion-capture comparison, clinical
validation or medical-device claims. These are future work, not failed acceptance gates.

Release requires [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md), synthetic/replay
metric validation and reproducible benchmark evidence.
