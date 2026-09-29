# Validation Plan — KineIMU Shoulder

Validation code remains separate from production code. Important outputs are labeled
Observed, Derived, Assumed, Validated or Experimental. No shoulder algorithm is currently Validated.

## Layer 0 — Physical acquisition evidence

M1 records real dual-device behavior: configured/effective rate, packet/sample counts,
loss and attribution, malformed/framing errors, gaps, disconnect/reconnect events,
timestamp monotonicity, device error counters, provenance and recording integrity.
The 30-minute run is physical engineering evidence, not shoulder-motion accuracy evidence.
Pairwise drift or synchronization residuals are reported only when the required mapping
and independent events exist; otherwise the field is explicitly not measured or inconclusive.

## Layer 1 — Unit and known-input tests

Test quaternion/rotation math, coordinate transforms, filtering, segmentation, metrics,
gap/invalid handling and deterministic replay boundaries. Every numerical expected value
must come from an analytical construction, independent reference or documented invariant.

## Layer 2 — Deterministic synthetic validation

Generate labeled motions such as flexion `0° → 90° → 0°` for a known repetition count,
tempo and hold duration. Validate ROM error, repetition accuracy, tempo/hold error and
angular-velocity error against that ground truth. Add controlled sensor noise, gyro bias,
timing jitter, packet loss and drift. Monte Carlo robustness is optional only after the
deterministic cases and acceptance thresholds are defined.

Synthetic inputs and results must be marked synthetic and record configuration, seed and
generator version. Synthetic biomechanical realism is limited; it verifies algorithm behavior,
not performance on people.

## Layer 3 — Recorded replay validation

Use immutable M1 recordings and traceable repository demo data through:

```text
recording → replay → preprocessing → orientation → relative kinematics
          → exercise analytics → report
```

Replay must preserve source hashes and must not silently repair, filter, interpolate or
resample raw inputs. Tests compare deterministic replays and explicitly exercise QC failures.

## Planned algorithm endpoints

| Endpoint | V1 evidence |
|---|---|
| Orientation/frame math | Analytical rotations and convention tests; drift/heading limitations |
| Humerothoracic ROM / peak | Known synthetic trajectories and replay consistency |
| Repetition count | Labeled synthetic sequences, partial/invalid cases and traceable replay examples |
| Phase / movement / hold timing | Known synthetic boundaries, timing jitter and missing-data cases |
| Angular velocity | Analytical quaternion increments or independently generated known-rate motion |
| Thorax-compensation proxy | Known torso perturbations with explicit axes/baseline; no diagnostic score |
| Variability / longitudinal summaries | Repeated deterministic trajectories and comparability/QC rules |

## Explicitly outside current V1 validation

Human-subject accuracy, volunteer/patient testing, motion-capture comparison, clinical
validation and clinical outcome claims. Digital goniometer, synchronized video,
motion-capture and don/doff studies are possible future validation layers; their absence
is not a V1 failure and their accuracy must not be implied.

## Provenance and reporting

Reports retain dataset/source hashes, software/firmware commits, configuration, units,
frames, filters, resampling policy, exclusions and reproducible commands. Claims identify
the validation layer and tested conditions. Never report precision beyond the ground-truth
resolution or describe synthetic/replay evidence as human or clinical validation.

## Measurement and interpretation risks

| Risk | Impact | Mitigation / gate |
|---|---|---|
| Independent clock drift/transport delay | High | Device clocks, loss counters, repeated independent events, held-out residuals and sync budget |
| 6DoF relative yaw drift / axial rotation | High | M2 duration-dependent heading/functional-calibration tests; defer external-rotation claims |
| Surface IMUs mistaken for isolated joint measurements | High | Humerothoracic terminology; no glenohumeral/scapular claims |
| Upper-arm slippage / soft-tissue artifact | High | State as an unvalidated human-use limitation; future mounting/don/doff study is outside V1 |
| Gravity mistaken for full anatomical alignment | High | Explicit axes/heading assumptions and functional alignment |
| Reference lacks 3D or timing resolution | High | Metric-specific reference, FPS/offset/uncertainty; limit precision |
| Predeclared timing/loss limits fail measured feasibility | High | v0.1 budget is frozen before collection; run 30-minute dual-node characterization and revise only prospectively |
| BLE control/telemetry state cannot be reconciled | High | Versioned CRC-protected identity/config, clock, telemetry and cumulative status values; immutable event sidecars and sequence audit |
| Selected XIAO path fails measured M1 gate | Medium | Revisit only for a documented timing/BLE/power/mounting blocker |
| Wearable bulk / battery / cable pull | Future | Outside current V1; require a new hardware-integration plan before work resumes |
| Raw corruption / loss hidden | High | Immutable streams, counters, QC and explicit processed mapping |
| Backend units/frames/filter phase mismatch | High | Adapter contracts and known-input tests |
| Undefined rep/hold thresholds | Medium | Versioned config, hysteresis/partial rules and separate validation sessions |
| CV near zero / trajectory normalization bias | Medium | Undefined-value policy, documented normalization and sensitivity checks |
| Longitudinal sessions incomparable | High | Side/protocol/calibration provenance and comparability flags |
| Clinical overinterpretation | High | Evidence labels; no diagnostic/compensation/fatigue/outcome scores |
| Personal data disclosure | High | DATA_GOVERNANCE; no identifiable videos in Git |
| Dependency/license conflict | Medium | Locked small stack, notices and release review |
| Premature universal abstractions | Medium | Shoulder-only implementation, ADR scope control |
| Historical documents mistaken for current | Medium | Archive manifest and active-document map |
| Synthetic motion is mistaken for human validity | High | Label synthetic/replay evidence, document generator limits and prohibit clinical accuracy claims |
| Algorithms depend accidentally on live BLE | High | Replay/synthetic input paths and hardware-free end-to-end tests |

## Runner commands and provenance

Use clean committed source, the locked Python environment and a new output root.

```powershell
uv run --frozen python examples/m5_baseline.py --output <new-baseline-root>
uv run --frozen python examples/m5_perturbation.py --output <new-perturbation-root> --workers 4
```

The baseline runs 30 frozen CLEAN-E/S/Q cases and two comparisons. E uses exact
segment orientation; S uses SI/calibration/AHRS/alignment; Q reads frozen packets.
The perturbation runner executes the full predeclared 1,142-case design with
unchanged labels, seeds, denominators, QC, exclusions and numerical budgets.
Recipes and supported domains are in
[the validation contract](protocols/M5_VALIDATION_CONTRACT.md).
Exit 0 requires all required gates; exit 1 preserves failures; exit 2 is blocked.
A stress case's completed execution is a limitation record, not an accuracy PASS.
Existing/raw/output roots are rejected; failed/partial roots are not resumed.
Use --development only for explicitly nonformal diagnostic baseline runs.

Preserve exact source/configuration/firmware/calibration/annotation identities,
input/output hashes, reference method, source/runtime versions and uv.lock.
Record seeds and source labels. Independent expectation/oracle values cannot come
from the implementation under test. Keep error supports and unavailable values;
all-invalid arrays do not imply zero error. Two processes at the same lock must
produce equal canonical products; operational times/PIDs are recorded separately.
Statistics in documentation must trace to generated artifacts. Historical failed
perturbation results are preserved in [the audit record](docs/PUBLIC_AUDIT.md).
