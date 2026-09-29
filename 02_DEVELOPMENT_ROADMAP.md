# KineIMU Shoulder — Development Roadmap

Direction accepted by [ADR-008](docs/adr/ADR-008-hardware-tested-software-complete-v1.md).
M0–M6 are **DONE** at their recorded local V1 acceptance scope; do not redo them.
[M6.5 / CP5](experiments/M6_CP5_20260928/REPORT.md) independently accepts the
hardware-free fresh-clone candidate on Windows; actual public publication is deferred.
M5.0–M5.2 / CP0–CP2 passed at their specification, source-tool and clean
synthetic numerical/evidence scopes. [CP2 evidence](experiments/M5_CP2_20260926/README.md)
retains 30 passing full-chain cases, two comparisons and byte-identical outputs
from two independent processes. [M5.3/CP3 reacceptance](experiments/M5_CP3_UNBLOCK_20260927/README.md)
passed under the explicitly authorized processing/1.1 contract: all 1,142 frozen
cases passed in two independent runs with identical canonical bytes and an
independent audit. [Prior failed evidence](experiments/M5_CP3_20260926/README.md)
remains retained. CP4 actual recorded replay is accepted: two complete independent B/C/segmented-D collections, identical canonical bytes, immutable originals and all six numerical audits pass.
[M5.5/CP5 closeout](experiments/M5_CP5_20260928/README.md) supplies complete
acceptance coverage, verified retained evidence, required project checks and
[M6 inputs](experiments/M5_CP5_20260928/M6_HANDOFF.md). M6 is locally accepted by CP0–CP5; Linux NOT RUN and publication deferred.
The M3 sequence and gates are in [M3_DEVELOPMENT_PLAN.md](M3_DEVELOPMENT_PLAN.md).
The M4 stages and checkpoints are in [M4_DEVELOPMENT_PLAN.md](M4_DEVELOPMENT_PLAN.md).
The M5 stages and checkpoints are in [M5_DEVELOPMENT_PLAN.md](M5_DEVELOPMENT_PLAN.md).

```text
M0 Engineering foundation
  ↓
M1 Physical acquisition validation
  ↓
30-minute dual-device bench test
  ↓
FREEZE HARDWARE
  ↓
M2 Calibration + orientation + deterministic replay
  ↓
M3 Shoulder kinematics
  ↓
M4 Focused exercise analytics
  ↓
M5 Synthetic + replay validation
  ↓
M6 Hardware-free demo + documentation + release
  ↓
V1.0
```

| Milestone | Goal | Exit evidence |
|---|---|---|
| M0 — Engineering foundation | Git/CI, reproducibility, governance, schemas, handoff and scientific engineering baseline | **DONE**; retained unchanged. |
| M1 — Physical acquisition validation | Reliable two-node firmware, protocol, host recording and physical bench characterization | Completion-window BLE transport physically retested and its limitation reported; under ADR-009, uninterrupted 30-minute dual USB run; immutable raw/event/USB-byte artifacts; rate, counts, loss, gaps, timestamps and recording integrity reported; unsupported metrics explicitly marked not measured. |
| Hardware freeze | Stop routine battery, enclosure, retention, wearability and human-test development | M1 evidence recorded; later hardware work requires a documented firmware/acquisition defect or new maintainer decision. |
| M2 — Calibration and orientation | Calibration, explicit frames, quaternion AHRS, relative orientation and deterministic replay | Known-input tests, convention tests, drift/heading limitations and replay-determinism evidence. |
| M3 — Shoulder kinematics | Torso/reference and upper-arm relative orientation to humerothoracic movement approximations | ROM, angular velocity and movement-duration known-motion tests; Observed/Derived/Assumed labels; no glenohumeral/scapular claim. |
| M4 — Exercise analytics | Flexion and abduction repetition/ROM/tempo/hold/consistency plus thorax-compensation proxy and session trends | Deterministic segmentation/edge tests, limited exercise set, explicit thresholds and provenance. |
| M5 — Algorithmic validation | Unit, deterministic synthetic and recorded replay validation | Ground-truth error reports for ROM/count/tempo/hold/velocity; robustness to noise, bias, jitter, packet loss and drift; end-to-end replay report. |
| M6 — Demo, documentation and release | Repository works without XIAO hardware | One clone-and-run full pipeline demo, traceable sample data, automated checks, limitations, technical report, LICENSE and CITATION.cff. |

Human-subject, motion-capture and clinical validation are outside the current V1
mainline. They remain possible future work and must not be presented as failed gates.
Gait/posture and generic-joint infrastructure remain excluded.

## M5.4 / CP4 accepted — 2026-09-28

Two independent complete B/C/ADR-011 D runs and six independent numeric audits passed. [Accepted CP4 evidence](experiments/M5_CP4_STAGE_E4_20260928/README.md) retains canonical equality, originals, exact numerical/audit-tool locks, explicit source-EOL/worker identity proof and all original failed attempts. M5.4 DONE.

## M5.5 / CP5 closeout — 2026-09-28

[Total report](experiments/M5_CP5_20260928/README.md), requirement/case/evidence
coverage, source/input/output hash index, reproduction commands and limitations
are delivered. Full project checks include actual external M1 replay, not skips.
M5 DONE at the frozen synthetic/replay scope. Next M6.0 demo/release planning;
hardware remains frozen, with no acquisition or physical action required.
