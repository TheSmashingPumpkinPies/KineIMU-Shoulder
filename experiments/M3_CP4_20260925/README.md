# M3.4 CP4 — dual synthetic integration and M3 acceptance

Date: 2026-09-25 (Asia/Shanghai). The frozen metric contract is
`protocols/M3_KINEMATICS_CONTRACT.md`; analytical expectations are in
`tests/fixtures/M3_KNOWN_MOTION.md`. This is a hardware-free **synthetic
numerical** acceptance report, not anatomical or clinical validation.

## Reproduce

Use the repository's pinned CPython 3.12 environment after
`uv sync --all-extras --frozen`. The checked environment had NumPy 2.5.2,
SciPy 1.18.1, imufusion 1.3.3, imucal 2.6.0, pytest 9.1.1, Ruff 0.16.6
and mypy 2.3.1. `uv.lock` SHA-256 is
`ff2893aaa21f7ec97dfe487ca4c0e80af18d45e1293e47e28cd696feaf8d7c3e`.
On Windows, from the repository root, two independent outputs were made with:

```powershell
.venv\Scripts\python.exe examples/m3_dual_synthetic.py --output-dir experiments/M3_CP4_20260925/artifacts
.venv\Scripts\python.exe examples/m3_dual_synthetic.py --output-dir experiments/M3_CP4_20260925/repeat
```

Each command requires an absent or empty output directory and refuses a
`raw/` destination. The two directories are retained as reviewable outputs.
The canonical serializer sorts keys, uses compact UTF-8 JSON with a final
newline and disallows NaN. `processed.json` is the versioned M2.4 output
and its source/configuration evidence; `derived.json` is the versioned M3
metric output; `report.json` holds counts, error and artifact digests.

| File | Run 1 SHA-256 | Run 2 SHA-256 |
|---|---|---|
| `processed.json` | `34882b084776c7da26692735deee61cb5edf511323550d155d8eb726412e1ac6` | same |
| `derived.json` | `6e7b912e4103a164e669832e40e9c52502d3f513b9656a593fe609284e4eaaa1` | same |
| `report.json` | `dc7d321ae4ca54354e5cb78677f4869b1a571384dcb0e52d3c5a7fa1` | same |

The independently generated A/thorax and B/humerus source SHA-256 values
are `4277b45b622519c24a83a11f45921ad6e7d002f52e75f060393b366d668ed9d0`
and `59bc1e93b7fe5f7c6828da6d98074263213e5fc8fdebdd72f3bd91bcf6f3638b`.
Configuration SHA-256 is
`1f186da22f65b451bccec846f9fbed5a3e21fac6ac9dff38b2ea0fc6548182c3`.
The complete source samples, clock maps, heading relation, two alignment
records, units, side and gap limits are in the artifacts.

## Known motion and numerical result

A/thorax is fixed at `Qx(+60°)` in world Wa. The declared B-world to
A-world heading relation is also `Qx(+60°)`, and B/humerus follows known
`Qy` angles. The two synthetic device clocks have separately declared
affine offsets of 50,000 and 100,000 µs. The B stream is SLERP-sampled
onto common times `0, 200000, 700000, 1200000` µs; the middle two common
rows lie between B samples. The known noncommuting frame construction gives
`q_TH = Qy(0°,20°,70°,30°)` at those times. Both alignment records are
exact synthetic identity transforms, applied before M2.4 and evidence-checked
in M3 without a second rotation.

| Quantity | Independent expectation | Observed output | Absolute error |
|---|---:|---:|---:|
| Elevation (rad) | `0, π/9, 7π/18, π/6` | `0, 0.3490658503988659, 1.2217304763960306, 0.5235987755982988` | maximum `0` |
| Interval relative speed (rad/s) | `5π/9, 5π/9, 4π/9` | `1.7453292519943293, 1.7453292519943298, 1.3962634015954642` | maximum `6.661338147750939e-16` |
| Closed interval ROM (rad) | `7π/18` | `1.2217304763960306` | `0` |
| Elapsed duration (s) | `1.2` | `1.2` | `0` |

All four M2.4 rows, four M3 elevation rows, three M3 speed intervals and
the requested ROM interval are valid. Their reason is `valid`; the
gap limit is 500,000 µs. CP0 tolerance is `1e-10` rad for elevation/ROM,
`1e-10` rad/s for speed, and `1e-12` s for duration. The CP4 integration
test checks these independent values and byte equality of two command runs.
CP1–CP3 tests cover unsupported evidence, invalid rows, gaps and excluded
intervals separately.

## Evidence and acceptance

The input device times are **Observed within the generated synthetic
sources**. Common-time orientation and M3 numbers are **Derived**. Clock,
heading and alignment status is `supported` because their exact relation
is defined by this synthetic fixture. They are not physically measured.
There is no assumed mapping in this run; if any such input were used, M2/M3
would retain **Assumed/Experimental**. `Validated` against a physical or
clinical reference is absent, and `anatomical_eligible` is false. The
retained M1 USB pair lacks a supported pairwise clock map, common heading
and measured anatomical alignment, so this report makes no M1 anatomical
claim.

M3 acceptance is satisfied at its specified synthetic numerical and
evidence-interface scope: dual-node relative orientation, long-axis
humerothoracic approximation, ROM, interval-average relative angular
speed and elapsed duration, with explicit measurement/evidence labels and
no glenohumeral or scapular claim. CP0–CP3 reviews document their respective
contract and analytical gates. CP4 produced byte-identical outputs and
the full project checks passed: `368 passed, 2 skipped` in pytest;
`ruff check .`, `mypy --strict kineimu_shoulder`, documentation consistency
and `git diff --check` exited 0. The two skipped tests are optional
external M1 raw-root integration tests; their physical evidence is already
reported in M1/M2. Ruff's directory warnings concern inaccessible old
scratch directories, not source findings.

For M4, consume M3's common-time long-axis elevation rows and their
`valid`/`reason` mask, interval endpoint speed values and their mask,
caller-declared `max_sample_gap_us`, side, source hashes and complete
clock/heading/alignment provenance. M4 must choose and version exercise
intervals/thresholds; it must not bridge invalid rows or gaps, interpret
unsigned elevation alone as flexion versus abduction, or treat synthetic
truth as measured anatomical performance.
