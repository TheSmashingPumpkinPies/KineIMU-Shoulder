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
The wheel installs 57 third-party notice texts under
`share/kineimu-shoulder/third-party/` and includes `py.typed`.
Validate wheel and sdist in separate fresh environments using `python -I` from
outside the checkout. Build success alone does not establish numerical correctness.
