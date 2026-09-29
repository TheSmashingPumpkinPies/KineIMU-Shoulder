# ADR-005: Pivot to KineIMU Shoulder

- Status: Accepted
- Date: 2026-09-07
- Authorization: explicit maintainer scope/naming pivot.
- Supersedes ADR-001 naming; retires ADR-003 as historical application context.
- Partially supersedes ADR-004 application dependencies; retains Python 3.12.14 / uv 0.12.5.
- ADR-004 is occupied by the Python toolchain decision.

## Context and reason

Previous direction: general low-cost wearable IMU project with gait/posture emphasis.
New direction: KineIMU Shoulder, quantitative shoulder rehabilitation exercise and movement assessment.
Reasons: clearer biomedical engineering problem, bounded scope, stronger hardware-algorithm-validation
chain, more realistic independent project, and avoidance of premature generic framework design.

## Decision

Shoulder is this repository's sole application scope. Use names in NAMING.
Thorax plus lateral mid-upper-arm surface IMUs yield humerothoracic relative movement.
PROJECT_SCOPE and 01_PROJECT_SPEC freeze core families, extensions and exclusions.
M1–M6 cover acquisition, alignment, core metrics, compensation, validation and session system.
M0 remains DONE; retain its infrastructure.

StickS3 remains a development/reference candidate pending Hardware Decision Gate.
Canonical table schema 0.1 is retained; dual-session envelope/transport need an M1 reviewed contract.

## Consequences

Remove gait/posture from active roadmap, extras, tests and empty module/benchmark placeholders.
Future gait/posture work uses separate projects/repos. No universal biomechanics abstraction.
Preserve M0, scientific dependencies useful to shoulder, data governance, reproducibility and CI.
No large metric implementation or unused legacy alias.
Original source pack and historical evidence remain immutable/auditable.
Authoritative ADR registry is docs/adr; bootstrap/docs/adr has a navigation pointer only.

## Alternatives / revisit

Universal platform rejected for scope/validation burden; rebooting M0 rejected as unnecessary.
Immediate board replacement rejected without acquisition/mounting evidence.
Revisit hardware after measured M1 feasibility; claims require metric-specific validation.
