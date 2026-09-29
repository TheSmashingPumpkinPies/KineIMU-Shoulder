# Dependency Matrix — KineIMU Shoulder

Retained M0 API baseline, CPython 3.12.14; versions remain pinned.

The table's core-license shorthand is not a complete distribution license inventory.
Current exact installed declarations, additional/native notices and version-tag
texts are retained in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md) and its snapshot.
API calls establish compatibility, not physical or clinical accuracy.

| Package | Version | License | Role | API evidence |
|---|---|---|---|---|
| numpy | 2.5.2 | BSD-3-Clause | core | arrays/shapes |
| scipy | 1.18.1 | BSD-3-Clause | core | identity quaternion rotation |
| pandas | 3.0.5 | BSD-3-Clause | core | table |
| imufusion | 1.3.3 | MIT | orientation / analysis extra | stationary update, normalized wxyz |
| imucal | 2.6.0 | MIT | calibration / analysis extra | SI identity calibration, JSON round trip |

Run tests/integration/test_dependency_smoke.py for callable-contract evidence, not scientific validity.
imufusion requires set_sample_period before two-vector update; consumes g and deg/s.
imucal units are explicit SI in the tested contract.
Retain toolchain decision ADR-004 as amended by ADR-005.
Historical retired candidates: [archive — historical availability](docs/PUBLIC_EVIDENCE.md#not-distributed-in-this-source-snapshot).

Public-export note: unavailable internal navigation is redirected to the evidence-availability index; scientific claims and original target names are retained by the export record.
