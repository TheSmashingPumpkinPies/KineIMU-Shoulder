# ADR-008: Hardware-tested, software-complete V1 boundary

- Status: Accepted
- Date: 2026-09-19
- Authorization: explicit maintainer direction adjustment.
- Refines ADR-005 and supersedes the wearable/human-validation portions of its M1–M6 plan.
- Does not change ADR-006 hardware selection, ADR-007 firmware platform, or the public data schema.

## Context

The two physical XIAO nRF52840 Sense nodes, firmware, protocol, host recorder,
immutable raw capture, sidecars and QC infrastructure are far enough advanced to
finish the physical acquisition layer. Requiring battery integration, enclosure,
retention engineering, human wear studies, motion-capture comparison or clinical
validation would turn those separate research programs into V1 blockers.

The repository needs a finishable endpoint that preserves real-hardware evidence
without overstating what the shoulder algorithms have been validated against.

## Decision

KineIMU Shoulder V1 is a hardware-tested, open-source dual-IMU research framework
for quantitative shoulder rehabilitation motion analysis.

The mainline is:

1. M0 engineering foundation — retained and complete.
2. M1 physical acquisition validation — finish the current transport fix, then run
   one uninterrupted 30-minute dual-device bench characterization with immutable
   artifacts and an explicit measured/not-measured report.
3. Freeze hardware after M1 unless a later firmware or acquisition defect is found.
4. M2 calibration, coordinate conventions, quaternion orientation and deterministic replay.
5. M3 humerothoracic relative kinematics.
6. M4 focused exercise analytics for flexion and abduction.
7. M5 automated validation with unit, deterministic synthetic and recorded replay layers.
8. M6 hardware-free demo, documentation and release packaging.

Live BLE/USB acquisition, recorded replay and synthetic generation are peer input
backends. Production algorithms operate on normalized data plus explicit provenance;
they do not depend on a live transport. Equivalent existing interfaces are preferred
over a naming-driven architecture rewrite.

Battery integration, enclosure, straps/adhesives as a product design, wearability
engineering, human-subject or volunteer studies, motion-capture ground truth,
patient testing and clinical validation are outside the current V1 mainline. They
may be future work. They are neither failures nor release blockers.

## Consequences

- Existing M0 and M1 implementation/evidence remain valid; no working acquisition feature is removed.
- The 30-minute bench run cannot be marked passed until it is physically executed.
- If a requested bench metric is not observable with the frozen protocol, the report
  records it as not measured or inconclusive instead of inventing a value or forcing a schema-breaking refactor.
- Synthetic data is always labeled synthetic. Replay artifacts retain source hashes.
- Algorithm claims are limited to synthetic and replay-based evidence unless a later,
  separately approved study supplies stronger evidence.
- Project descriptions must not imply a validated wearable, clinical ROM instrument,
  diagnostic system or clinical outcome measure.

## Revisit

Reopen hardware only for a documented firmware/acquisition defect that blocks the
software pipeline. Add human or clinical validation only through a separately scoped,
ethically governed and adequately resourced project decision.
