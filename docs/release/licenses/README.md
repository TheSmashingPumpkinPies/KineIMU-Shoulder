# Third-party license text snapshot

Internal release review, 2026-09-28. [inventory.json](inventory.json) lists the
installed Windows/Python 3.12 all-extras environment's distributions and each
copied original member, size and SHA-256. Texts have a `.txt` suffix appended to
their original member paths; **their bytes are unchanged**. Extra suffixes keep
upstream license fragments out of the repository Markdown-link checker.

Generated once by [snapshot_notices.py](../../PUBLIC_AUDIT.md).
Recreation requires the matching frozen environment and a new snapshot destination;
the script refuses to overwrite its existing inventory. Before/after checks bind
all copied bytes. Version/classifier metadata is evidence of upstream declarations,
not an exhaustive platform-independent legal clearance.

Missing installed texts (pyserial and WinRT) are recorded explicitly.
The official v3.5 / v3.2.1 tag texts are preserved separately, with their own
[URL/hash record](upstream-references.json). They are upstream version references,
not files supplied inside the installed wheels.
The KineIMU wheel installs this snapshot under the environment's
`share/kineimu-shoulder/third-party/`; the sdist preserves its repository path.
Dependencies and tools are not bundled in the KineIMU wheel. No reviewed firmware
binary/SDK redistribution is implied. See [THIRD_PARTY_NOTICES](../../../THIRD_PARTY_NOTICES.md).
