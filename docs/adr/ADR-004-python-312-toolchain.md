# ADR-004: Python 3.12 Toolchain Baseline

> Partially superseded by ADR-005: application dependencies retired; Python/uv baseline retained. Original rationale below is historical.

- Status: Accepted
- Date: 2026-09-05

## Context

KineIMU needs one reproducible Python baseline that supports the scientific core and the primary V1 dependency
candidates. The machine has uv-managed CPython 3.11.15, 3.12.14, and 3.13.5. KielMAT 0.0.5 declares Python
`>=3.10,<3.13`, while mobgap, imucal, and imufusion support Python 3.12.

An API-level compatibility spike on Windows x86-64 successfully installed and called NumPy, SciPy, pandas,
imufusion, imucal, and mobgap under CPython 3.12.14. Python 3.13 was not selected because it excludes the current
KielMAT release. Python 3.11 remains supported upstream but provides no project-specific advantage over 3.12. An
isolated KielMAT install resolved but failed because its `qmt` dependency required Microsoft Visual C++ 14+ to build.

## Decision

- Use uv 0.12.5 as the environment and lock-file tool.
- Use CPython 3.12.14 as the M0 reproducible baseline.
- Constrain the initial package metadata to Python `>=3.12,<3.13`.
- Keep the scientific core small and expose orientation, calibration, and gait dependencies as optional extras.
- Keep KielMAT in a separate environment because KielMAT 0.0.5 requires `tpcp>=0.27,<0.28`, while mobgap 1.2.0
  requires `tpcp>=2.1.1` (resolved as 2.3.0 during the spike).

## Alternatives Considered

1. Python 3.11: compatible with the candidates, but older than the selected baseline and unnecessary here.
2. Python 3.13: compatible with the primary stack, but incompatible with KielMAT 0.0.5 metadata.
3. Install mobgap and KielMAT together: rejected because their `tpcp` constraints are unsatisfiable.

## Consequences

### Positive

- One exact interpreter version and a lock file can reproduce the tested environment.
- Backend dependency weight and conflicts do not leak into the minimal core installation.
- The primary V1 gait backend remains installable with the orientation and calibration candidates.

### Negative

- Python 3.13 users need a later compatibility decision.
- KielMAT integration requires its own environment/process boundary unless upstream constraints change.
- KielMAT 0.0.5 is not currently installable on the tested Windows host without adding an MSVC build toolchain or
  obtaining a compatible `qmt` wheel.

## Validation / Revisit Trigger

Revisit when Python 3.12 approaches end of support, a required dependency drops 3.12, KielMAT updates its `tpcp`
constraint, or another platform fails to resolve the lock file.
