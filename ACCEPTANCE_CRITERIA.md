# Acceptance Criteria — KineIMU Shoulder

These criteria implement [ADR-008](docs/adr/ADR-008-hardware-tested-software-complete-v1.md).

## M0 — Engineering Foundation: DONE

Preserve the repository/CI, source-of-truth, ADR, reproducibility, data-governance,
dependency, schema, test and handoff foundation. Do not reopen M0 for this direction change.

## M1 — Physical Acquisition Validation

- Two identified XIAO nRF52840 Sense nodes record simultaneously to PC as A/thorax
  reference and B/upper arm.
- Preserve separate immutable raw streams, event sidecars, device timestamps, host
  arrival observations, sample/packet sequences, reset/epoch boundaries and provenance.
- Preserve the completed physical completion-window BLE TX retests in both link
  establishment orders and report their failed dual-link gate. Under ADR-009,
  the formal long run uses the identified dual USB acquisition path; it does not
  claim that dual BLE throughput passed.
- Run at least 30 uninterrupted minutes at the configured 104 Hz ODR with no planned
  disconnect stimulus or artificial callback delay.
- Report scheduled duration, firmware/software identity, configured and effective rate,
  expected/received packet and sample counts, sequence loss, malformed/framing errors,
  maximum gaps, disconnect/reconnect events, timestamp monotonicity, error counters and
  recording hashes/integrity.
- Report clock offset/drift/inter-device timing evidence if available. If the frozen
  protocol or collected reference cannot support a metric, mark it `not measured` or
  `inconclusive`; do not invent it and do not force a public-schema rewrite.
- Preserve the separate deliberate recovery evidence and reference-board build evidence.
- Do not mark the 30-minute bench test passed before physical execution.

After M1, freeze hardware unless a later firmware/acquisition defect blocks the software pipeline.

## M2 — Calibration, Orientation and Replay

Accelerometer calibration, gyroscope bias handling, coordinate/frame conventions,
normalized quaternion orientation, relative orientation and deterministic replay.
Known-input and convention tests; explicit heading/drift limits. Static gravity alone
does not determine full anatomical heading.

## M3 — Shoulder Kinematics

Torso/reference and upper-arm relative orientation, humerothoracic movement
approximation, ROM, angular velocity and movement duration. Tests distinguish measured,
derived and assumed quantities and reject unsupported glenohumeral/scapular claims.

## M4 — Exercise Analytics

Focused flexion and abduction analytics: repetition count, per-repetition ROM, tempo,
hold duration, angular velocity, consistency/variability, thorax-compensation proxy and
longitudinal session summaries. Versioned thresholds, partial/invalid handling and QC-aware outputs.

## M5 — Synthetic and Replay Validation

- Unit tests for rotations, transforms, filters, segmentation, metrics and edge cases.
- Deterministic synthetic ground truth for known ROM, repetitions, tempo, holds and
  velocity; then controlled noise, bias, jitter, packet loss and drift perturbations.
- Replay validation from M1/demo recordings through preprocessing, orientation,
  kinematics, exercise analytics and report generation.
- Report algorithm errors and robustness with source/configuration provenance. Synthetic
  evidence is always labeled synthetic.

## M6 — Hardware-free Demo and Release

A clean clone can run at least one complete replay or synthetic demo without XIAO
hardware. README, architecture, hardware/protocol/algorithm/validation documentation,
limitations, reproducible examples, sample dataset, benchmark results, technical report,
LICENSE and CITATION.cff are present and consistent.

## Outside Current V1 Acceptance

Battery integration, enclosure, straps/retention engineering, human wear tests,
volunteer/patient studies, motion-capture comparison and clinical validation. These are
future work, not V1 defects. No diagnostic, clinical outcome or clinically validated ROM claim.
