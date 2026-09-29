# Distribution

Version 0.1.0 uses MIT for original Python code/documentation. Firmware and
third-party components retain their own licenses; see [notices](../../THIRD_PARTY_NOTICES.md).

| Artifact | Contents |
|---|---|
| Git repository | Library, examples, samples, protocols, tests, firmware and reference evidence |
| Wheel | Python library, typing marker, MIT metadata and complete third-party notice texts |
| Source distribution | Rebuildable package sources, README, citation, notices and report |

The wheel and sdist omit complete demo data, tests, acquisition firmware and Git
metadata. Repository validation entry points require their repository fixtures.
Native dependencies are installed separately using the locked environment.

```powershell
uv sync --all-extras --frozen
uv build
```

Expected artifacts: `kineimu_shoulder-0.1.0-py3-none-any.whl` and
`kineimu_shoulder-0.1.0.tar.gz`. Preserve source/lock and artifact SHA-256 values.
The wheel installs the complete 57-member [third-party snapshot](licenses/README.md)
under `share/kineimu-shoulder/third-party/`: 54 notice texts plus the inventory,
upstream-reference metadata and README. It also includes `py.typed`.
Validate wheel and sdist in separate fresh environments using `python -I` from
outside the checkout. Build success alone does not establish numerical correctness.

## Maintaining the current public index

After ordinary documentation edits, run from the clone root:

```powershell
uv run --frozen python scripts/check_docs_consistency.py --refresh-index
uv run --frozen python scripts/check_docs_consistency.py
git diff --check
```

The refresh verifies the complete Git-visible inventory and all immutable bytes before
atomically updating only indexed mutable members' actual sizes/SHA-256. It refuses
missing, new, duplicate or unsafe members; membership changes need separate review.
It preserves each license, `source_head`, publication identity and all other fields.
[PUBLIC_VERIFICATION.json](../PUBLIC_VERIFICATION.json) remains the historical record;
fresh checks belong to the new run's logs, not that record. Review the index diff with
the documentation diff before committing.
