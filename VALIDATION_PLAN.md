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
