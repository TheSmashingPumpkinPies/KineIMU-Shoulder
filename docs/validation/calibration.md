# M2.5 offline replay and M2 acceptance evidence

Date: 2026-09-25 (Asia/Shanghai). Baseline code: `main` at
`7d014566b1f3e03ced31f57c9e1fa019b9a38429` before M2.5 edits.
This run uses the repository-retained M1 Node B capture. It does not use
the external 30-minute dual USB bench to infer pairwise orientation.

## Repeatable command and inputs

From the repository root, install the pinned environment with
`uv sync --all-extras --frozen`, then run:

```powershell
.venv/Scripts/python.exe examples/m2_offline_replay.py --output-dir experiments/M2_REPLAY_20260925/artifacts
.venv/Scripts/python.exe examples/m2_offline_replay.py --output-dir experiments/M2_REPLAY_20260925/_repeat
```

The two invocations above ran in Python 3.12.14 with NumPy 2.5.2, SciPy
1.18.1, imucal 2.6.0 and imufusion 1.3.3. `uv.lock` SHA-256 is
`ff2893aaa21f7ec97dfe487ca4c0e80af18d45e1293e47e28cd696feaf8d7c3e`.
The script refuses nonempty output directories and any path containing a
`raw` component; it never writes to the M1 source.

| Input | SHA-256 | Selection |
|---|---|---|
| Canonical generated synthetic fixture | `89d15f3bedcd69bdb9b36f0db5c145f875d1462cbb369678cf5d4ecdc89c9e11` | 101 samples at 10 ms intervals, +π/2 rad/s about Z for 1 s, +Z specific force |
| `firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary.kimu` | `1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201` | Full 208-packet/832-sample file is hash/CRC/QC checked; first 128 samples of its only epoch are processed |

The retained M1 file hash was checked before and after both runs and was
unchanged. Its QC has zero issues; first/last selected sample sequences are
23468/23595 and device times are 257030578/258224914 µs. The processing
configuration uses sensor-frame SI, an explicitly illustrative identity
calibration artifact and declared identity `R_NS`, followed by fresh six-axis
AHRS with observed device time and `max_gap_s=0.05`. The identity artifact's
`fit_window_us=(0,1)` is a required artifact-schema placeholder, **not a
measured fit**. Each output carries the complete calibration artifact,
source hash, original sample sequences and times, and `q_WN` in scalar-first
active convention. The synthetic final quaternion is approximately
`[0.70711825, 0, 0, 0.70709531]`, matching the analytical +90° Z rotation
within the declared 3×10⁻⁵ component tolerance.

## Output equality

Canonical UTF-8 JSON uses sorted keys, compact separators, finite numbers
and one trailing newline. A byte comparison of each file from the two
separate runs returned true. The retained first-run artifacts are:

| Artifact | SHA-256 on each run |
|---|---|
| `artifacts/synthetic.json` | `e775a4d826b28f8d57293b0f359822b7066ca6a9c4b30200a84a3eb3ac5c29ae` |
| `artifacts/m1_node_b.json` | `125cc2b401654a705b0805d0937feea6f8a484399cd7345dc40873058d8c1e1c` |
| `artifacts/report.json` | `1b68c15052af24226c9510f1066bf5955e1f87ccaee5b384c0a9e7d2ed137e19` |

`report.json` records full-source M1 QC, dependency versions, lock hash,
input hashes, both processed-artifact hashes and scientific limitations.
The repeat directory was used only for byte comparison and is not part of
the retained deliverable.

Final required checks: full pytest with
`KINEIMU_M1_RAW_ROOT=<external-data>\kineimu_m1_usb_30min_20260925_01` passed
**326/326**, including external A/B immutable replay; `ruff check .` passed;
strict mypy passed for 15 files (package plus example); docs consistency
reported 154 Markdown files, 39 archive hashes and 0 errors; `git diff
--check` passed. An initial full-suite run was 325/326 because an existing
BLE simulator test exceeded its 0.25 s wall-clock connect limit under suite
load. Both parametrizations passed alone, and the full rerun passed without
BLE source changes. Generated `.tmp-*` pytest trees are excluded from Ruff
discovery so the required full-tree lint command checks project sources.

## M2 acceptance disposition

| Gate | Evidence | Result |
|---|---|---|
| M2.0 conventions | `protocols/M2_PROCESSING_CONTRACT.md`; independent signed quarter-turn and noncommuting frame tests | Passed |
| M2.1 immutable replay | `tests/unit/test_m2_replay.py`, retained Node B and optional external M1 A/B read-only tests | Passed |
| M2.2 sensor calibration | injected affine/bias/axis fixtures and rejection tests; versioned SI artifact | Passed numerically; no M1 physical fit |
| M2.3 six-axis orientation | independent known turn/tilt/time/reset and yaw-bias tests | Passed numerically; heading unobservable |
| M2.4 relative timing | analytical two-body and offset/drift tests; missing or uncertain evidence rejected | Passed numerically; M1 pair lacks required clock and heading evidence |
| M2.5 replay | twice-run canonical artifacts, source/lock/output digests and end-to-end test | Passed |
| `ACCEPTANCE_CRITERIA.md` M2 clause | known-input, convention, normalized quaternion, deterministic replay and explicit drift/heading bounds | Passed within the stated numerical and evidence scope |

## M3 input boundary

M3 may consume `q_TH` only from `relative_orientation` with two identified
per-epoch segment streams, valid per-node device-to-common clock maps,
declared interpolation gap/grid, a supported world/heading relation, and
measured sensor-to-segment alignment for the claimed anatomical task. It must
preserve the validity mask, invalidity reasons, status labels, source hashes,
frame convention and timing/heading uncertainty. Assumed maps or heading
remain `Assumed/Experimental`; invalid rows are excluded from metric
calculation. These single-node `q_WN` artifacts are orientation-stage inputs,
not humerothoracic M3 angles. The M1 USB pair supplies neither independent
pairwise clock mapping, common heading nor measured anatomical alignment.
Six-axis gyro bias can produce yaw drift; the 10 s, +1°/s synthetic test
demonstrates 10° apparent yaw, not a measured hardware drift rate.

M3 may implement only humerothoracic movement approximations with explicit
Observed/Derived/Assumed labels. No glenohumeral, scapular, diagnostic or
clinical score is supported by this evidence.
