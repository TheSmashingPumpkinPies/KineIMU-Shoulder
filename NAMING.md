# Project Naming — Final

Status: RESOLVED; accepted [ADR-005](docs/adr/ADR-005-pivot-to-kineimu-shoulder.md).

| Identifier | Final value |
|---|---|
| Display name | KineIMU Shoulder |
| Repository | kineimu-shoulder |
| Python distribution / package / import | kineimu_shoulder |
| Python usage | import kineimu_shoulder |
| CLI | kineimu-shoulder |
| Firmware display name | KineIMU Shoulder Firmware |

Distribution tooling normalizes underscores to hyphens in metadata/lock resolution.
Rename the small typed M0 skeleton now; no stable application API/CLI exists, so no legacy alias.
CLI is a reserved name; this pivot does not claim a command implementation.

Local checkout remains .. The current origin is the management repository
TheSmashingPumpkinPies/KineIMU_Shoulder_ProjectManagement.
The maintainer-approved public destination is TheSmashingPumpkinPies/kineimu-shoulder,
recorded in [ADR-012](docs/adr/ADR-012-release-documentation-and-license-selection.md).
Public hosting, repository creation, push and release are pending; selecting this
destination does not change origin. Verify hosting before updating the remote.
Historical archives/commits and superseded ADR context retain original names.
Future namespace changes require an ADR and migration review.

Actual GitHub destination: https://github.com/TheSmashingPumpkinPies/KineIMU-Shoulder. The GitHub casing does not change CLI/import names.
