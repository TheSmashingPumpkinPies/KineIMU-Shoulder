# KineIMU Shoulder packaging boundaries

M6.4 licensed candidate: `0.1.0`; original code/docs MIT, author and copyright
holder Hongbo Liao, copyright year 2026. Decisions are in [REVIEW.md](REVIEW.md).
Actual candidate checks are in
[CP4 candidate evidence](../../experiments/M6_CP4_FINAL_20260928/README.md).
The [earlier draft evidence](../../experiments/M6_CP4_20260928/README.md) remains
unchanged. Successful packaging does not replace CP5 or establish publication.

## Artifact contracts

| Artifact | Contents / use | Boundary |
|---|---|---|
| Wheel | Python package, typing marker, full MIT license and third-party notices/texts | Library APIs; no complete clone demo or validation-fixture promise |
| sdist | Package sources, metadata, README, MIT/CITATION, report and release review/notices | Rebuilds the wheel; excludes full samples, tests, protocols, experiments, Git and firmware |
| Git repository | Demo script, protocols, fixtures, sample and source | Required for examples/m6_demo.py; public destination approved, actual hosting/evidence distribution pending |
| Technical report | Markdown with repository evidence links | Repository report; isolated sdist copy is informative, not a complete evidence archive |
| Third-party snapshot | Byte-preserved installed license files and source/hash inventory | Terms reference; dependencies installed separately, not bundled |

No self-contained demo ZIP or firmware binary is published by this step.
Some validation modules read repository fixtures/contracts. Installing the
wheel does not establish that every repository validation entry point works
standalone. Native dependencies retain their upstream distributions/notices.
The CC0 sample annex is part of the repository sample, excluded from Python
wheel/sdist because neither distributes the sample data.

## Build and inspect

From the checkout using the pinned toolchain:

```powershell
uv sync --all-extras --frozen
uv build --out-dir dist/m6-candidate-01
```

Use a new destination per recorded build. Expected artifacts are
`kineimu_shoulder-0.1.0-py3-none-any.whl` and `kineimu_shoulder-0.1.0.tar.gz`.
Inspect exact sources, README/notices, Requires-Python, dependencies/extras,
License-Expression MIT, Author Hongbo Liao and the approved repository URL.
The wheel preserves py.typed. License-File entries cover root LICENSE and
THIRD_PARTY_NOTICES.md; the complete snapshot is installed under
`share/kineimu-shoulder/third-party/`. Hatchling 1.27.0 does not recursively
expand the old license glob; explicit shared-data inclusion preserves nested
notices. The original failed preview archive check remains retained.

Install wheel and sdist into separate fresh venvs. Run API checks using
`python -I` from an external directory and prove imports come from the new
environment. Check pinned dependencies and execute real SI calibration,
observed-dt AHRS, known-rotation/M3 assertions, invalid evidence handling and
installed metadata/notices. Record commands, exits and artifact SHA-256.

CP4 installs dependency wheels using frozen analysis requirements exported
from uv.lock with hashes, followed by no-deps project installation. Unrestricted
pip resolution is not a reproduction of the locked transitive environment.
Independent package installation is separate from CP5 fresh-clone demo acceptance.

## Candidate and publication

Build new artifacts from the approved metadata instead of relabeling previews.
Recheck sources, notices, sample rights and CFF on the candidate source ref,
then complete CP5. Preserve all prior artifacts, failed attempts and hashes.
The approved public destination is
https://github.com/TheSmashingPumpkinPies/kineimu-shoulder; repository creation,
public publishing and large evidence distribution remain separate actions.
