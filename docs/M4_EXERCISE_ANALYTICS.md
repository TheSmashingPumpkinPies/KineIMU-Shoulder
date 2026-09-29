# M4 exercise analytics — usage and export

KineIMU Shoulder M4 consumes explicit common-time M3 elevation and principal
3-D quaternion interval speed, with their associated M2 orientation and
clock/heading evidence. The exercise declaration is `flexion` or `abduction`;
side is explicit. The side-aware geometric gate checks the declaration.
The governing definitions, SI thresholds, time/QC rules and tolerances are in
[the frozen contract](../protocols/M4_EXERCISE_CONTRACT.md).

## Pipeline

1. Call `segment_shoulder_repetitions` with the two associated M3 results,
   `ExerciseConfig`, exact common-time window, session/protocol identity and
   calibration/processing hashes. Retain every candidate and QC break.
2. Call `compute_repetition_metrics`. Complete eligible candidates contribute
   closed ROM, peak, elapsed durations, holds and interval-speed statistics.
   Excluded candidates retain their reasons and unavailable values.
3. Optionally call `prepare_thorax_common_grid` on the original **already
   aligned** thorax stream. Supply the same grid/configuration, its clock map,
   alignment, calibration hash, original QC and explicit heading/drift evidence.
   This visible SLERP operation retains original indices, brackets and weights.
   Call `compute_thorax_excursion`; missing or ineligible trace excludes the
   proxy independently of relative movement metrics.
4. Call `summarize_exercise` with a `SummaryContext`. Mean/max/n, sample ROM SD,
   CV, range, active-only cadence, window duration and overlapping exclusion
   counts remain explicit. Call `compare_summaries` with UTC starts and unique
   session IDs. Differences are later minus earlier means, with both n and
   matching processing/evidence keys. Incomparable pairs expose differing keys.

The APIs live in `kineimu_shoulder.exercise`, `kineimu_shoulder.thorax` and
`kineimu_shoulder.summary`. Rotation remains quaternion-based internally.
The thorax Z-Y-X decomposition reports excursion relative to each repetition's
movement-start orientation; it is a compensation proxy with no clinical score.
Speed is principal 3-D endpoint rotation magnitude divided by elapsed time,
not a signed elevation derivative. Do not infer heading from static gravity.

## Deterministic example

```powershell
uv sync --all-extras --frozen
uv run --frozen python examples/m4_dual_synthetic.py --output-dir experiments/M4_CP5_20260926/my_run
```

The destination must not exist; the example refuses to overwrite it. It
constructs exact post-alignment dual-node segment quaternion streams from
[A/B and T4 analytical truth](../tests/fixtures/M4_KNOWN_EXERCISES.md), runs
M2.4 and M3 through M4, and emits five sessions: flexion, left/right abduction,
wrong-plane exclusion, and later B-only flexion. The latter compares against
the earlier A+B flexion session. No sensor calibration or AHRS is executed by
this example. The M2 backend tests remain separate; no AHRS accuracy claim or
new AHRS tolerance is implied. No noise is added and no input row is repaired.

## Files and provenance

- `processed.json`, `m4-dual-synthetic-processed/1.0`: a session-ID map of
  generated original streams, full M2/M3 records, calibration declarations and
  prepared thorax records. Original/mapped timestamps, interpolation, QC,
  heading, drift, alignment and numerical validity survive serialization.
- `derived.json`, `m4-exercise/1.0`: a batch envelope with `sessions` and
  `comparisons`. Each session carries the frozen M4 envelope fields, candidate
  boundaries/confirmations/phase ownership, metric/proxy validity and reasons,
  and explicit summary context/statistics/comparability keys. Upstream records
  are content-addressed by `input_artifact_sha256` in the processed session map.
  Comparisons reference session IDs in this envelope; inputs are never pooled.
- `report.json`, `m4-cp5-acceptance-report/1.0`: independent expected/actual
  values and tolerances, validity counts, environment, exact command template,
  processing-file/source/configuration/contract/truth/lock/output hashes and
  evidence limits. Processing identity is a content hash of the file-hash map;
  the evidence README records the corresponding implementation commit.

Canonical encoding is UTF-8, sorted keys, compact separators, one LF, strict
JSON. Unavailable NaNs become `null` while validity and exact reasons survive;
infinity is rejected. Each source and processed session is hashed using this
same encoding. The report hashes processed/derived bytes; its own hash is
recorded externally to avoid a self-reference. The frozen threshold hash
uses `ExerciseConfig.sha256` (canonical configuration without terminal LF).
Alignment context hashes cover the alignment contract excluding raw-source
lineage; original source hashes are separately retained. This permits two
sessions under the same synthetic alignment to compare without treating raw
hash equality as a requirement. Changed calibration/remount/evidence remains
incomparable under the CP4 rules.

All exported angles are rad, speed rad/s, durations s, grid/boundaries integer
microseconds and cadence s^-1. Convert explicitly by 180/pi for degree display.
Synthetic timestamps are Observed within the generated fixture; calculations
are Derived. Supported synthetic clock/heading/alignment is exact construction,
not physical anatomical validation. `anatomical_eligible=false` remains explicit.
The [CP5 evidence report](../experiments/M4_CP5_20260926/README.md) records
two-run byte equality and project checks. M5 owns controlled perturbations and
recorded replay robustness; M6 owns complete release/demo packaging.
