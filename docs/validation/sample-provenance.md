> Historical sample construction record. Listed source-tool audit commands require the archived development checkout. Current release commands are in [VALIDATION.md](../../VALIDATION.md).

# M5.1 / CP1 — dual sensor source and independent truth

Date: 2026-09-26. Branch `main`. **M5.1 / CP1 PASS at source-tool scope.**
Source base: `044c61d`. Exact source/tool lock:
`ee0741334e430c7cf8b5b9845d0a9b48426fecad`.
Two independent processes ran from that clean tracked lock, with no source
changes between launches. CP2–CP5 and overall M5 remain open.

The generator uses SciPy rotations and analytical body rates. The independent
oracle imports only immutable motion parameters, uses explicit scalar matrix
entries, matrix derivatives and rational integer-time crossings, and never calls
the generator or production M2/M3/M4 geometry/metrics for expected values.
Shared parameter records are the specification, not shared numerical helpers.
These validation tools introduce no production algorithm or dependency.

| CP0 obligation | Executable CP1 evidence |
|---|---|
| O0–O4 gravity, nontrivial axes, flexion and both abduction sides | `tests/unit/test_m5_source.py` identity/neutral/sign tests and independent matrix references |
| O5/T1 mixed body rate and composition | Independent matrix derivative at 1e-5 s; measured max component error 7.981904026621578e-11 rad/s, gate 1e-6 |
| T1 timestep convergence | Mixed gyro-only orientation integration max error at 100/200 Hz: 0.003162356052136164 / 0.0015811597581567888 rad; ratio 0.49999422332242416 <=0.75; 100 Hz <=pi/450 |
| O6 calibration and zero invariants | Exact M/bias inversion to 1e-12; zero perturbation byte/array invariants; knot derivative ownership |
| O7/P9 Q quantization | Ties-to-even/int16 rejection, half-LSB force bound, unchanged original counters, final partial packet |
| F1/F4/T0 and independent labels | Rational ceil crossings, 80.1-degree F90 closed ROM, n-1 VAR SD, 54 complete F90L reps, PARTIAL eligibility, movement-start thorax excursion |
| P0–P8 perturbation construction | PCG64 full original arrays, separate true/claimed/device time, exact clock inverse, original sample/packet masks, bias/ramp/world-vertical injection and common-yaw invariance |
| Complete finite expansion | [case-manifest.json](../../datasets/samples/m6_synthetic/case-manifest.json): 1,142 unique IDs with unchanged controls; all five stochastic seeds retained |
| Mutations catch wrong truth tools | tool-audit.json (complete record retained in the local evidence archive): gyro sign, noncommuting order, claimed-time misuse and loss renumbering all caught; original source bytes restored |
| Q is replayable and canonical | `tests/integration/test_m5_source_export.py`: two processes, bytes/hashes, USB codec and existing `replay_capture` with QC/count/timestamp assertions; existing output rejected |

The matrix contains C33/W589/stress297/evidence122/boundary67/rejection34.
Path, clock sign/map, heading mechanism and fit level are explicit condition-ID
suffixes, preserving unique trajectory/condition/target/seed IDs. `F90-30` is the
contract's I-HD 30-second cropped/repeated control, not an additional exercise.
Sensor-source recipes resolve all perturbations before launch. Evidence/input/
irregular-grid/M4-fixture recipes remain explicit obligations for the CP2/CP3
runner; listing them does not claim they were executed or passed in CP1.

Physical cycle support, nominal M4 threshold labels and observation-grid labels
are distinct. The observation oracle reports sampled analytical envelopes, not
a prediction of the production state machine or QC. It never fills lost rows.
E quaternion isolation arrays are generated inputs, cross-checked against the
independent matrix oracle; they must not replace independent expected values.
World-yaw isolation changes q_WK/q_WN only, while sensor injection changes gyro
only. Neither mechanism edits the physical trajectory reference. The explicit
world formula h=rate*(t-5) includes negative warmup yaw, as frozen in CP0.

Each Q demo has A/B sensor-SI JSON, raw USB `.bin`, outer-framed M1 `.kimu`,
exact quaternion isolation arrays, calibration/axis/clock/initial-pose metadata,
and independent annotations. Synthetic host times are last-sample device times
times 1000 ns, not measured arrival times or evidence supporting clock maps.
The demos are F90, AL90, AR90 and T-MIX: 2,151 samples and 538 packets per node,
including the final three-sample packet. No human or physical sensor input.

The installed imufusion 1.3.3 Ahrs API has no settings getter; manifests record
effective defaults as **not exposed**, plus its public API and the frozen adapter
calls. No guessed defaults or settings overrides. No AHRS is run by CP1 tools.
Synthetic supported construction does not confer anatomical eligibility.

Reproduce in the locked Python 3.12.14 environment, using a fresh absent output:

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_m5_source.py tests/unit/test_m5_manifest.py tests/integration/test_m5_source_export.py --basetemp .tmp-m5-cp1-reproduce
.venv/Scripts/python.exe examples/m5_sensor_source.py --output .tmp-m5-cp1-new-source
.venv/Scripts/python.exe experiments/M5_CP1_20260926/audit_tools.py --mutations --output .tmp-m5-cp1-new-audit.json
```

Run the mutation audit only when no other process is using the generator. It
restores original bytes in `finally`. Reproduction output roots must be new;
raw files and prior evidence must not be overwritten. The export is a source
tool, not the formal CP2/CP3/CP4 acceptance runner. That runner still needs the
contract's committed clean lock, source-raw path guards, partial/failure manifest,
complete case disposition and exit 0/1/2 semantics.

Verification at preparation: full pytest **587 passed / 2 external M1 skips**;
Ruff passed; strict mypy **23 source files** passed. The two skips do not pass
CP4. CP0 contract/truth SHA-256 remain exactly the frozen values in
CP0 review (complete record retained in the local evidence archive). Public schema, production interfaces,
firmware, hardware and dependencies are unchanged; hardware remains frozen.


## Retained locked-generation evidence

[run1](../../datasets/samples/m6_synthetic/manifest.json) and run2 (complete record retained in the local evidence archive) each retain37 files,
9,991,724 bytes, including8 synthetic `.kimu` node recordings. Every file is
byte-identical across the independent processes; every non-self output digest
in SHA256SUMS.json was recomputed and passed. Both manifests bind the exact
source lock above and tracked_dirty=false. The frozen case manifest exactly
matches both copies. Reproducibility record (complete record retained in the local evidence archive):

- case-manifest SHA-256: `5bab237edd4386c630fa25ddae4fa774d41e4d51cf2493f2d3f23b458234edee`
- run manifest SHA-256: `257499bcc53a1fb94f10b956159fd1030f30611272504fb9ed4a2bd97273cbfb`
- SHA256SUMS SHA-256: `2aa180e32003f91e57accf1d53c5b4b914e0c9e9c0ab4cdb22db02a3ab0964f9`

Executed commands (separate processes, both exit0):

```powershell
.venv/Scripts/python.exe examples/m5_sensor_source.py --output experiments/M5_CP1_20260926/run1
.venv/Scripts/python.exe examples/m5_sensor_source.py --output experiments/M5_CP1_20260926/run2
```

Regenerate from the source lock in a separate checkout for identical Git/source
manifest bytes; later commits intentionally change provenance even if numerical
input bytes stay identical. No run root, wall-clock time or run duration enters
canonical source products. Failed development test roots remain untouched and
are described by the red/green/mutation history above; no formal CP2/CP3 run was
started. Initial exporter development caught a Windows path-key mismatch and
missing `.kimu` outer framing; both were fixed with passing regression checks.
The final dynamic-state docs check initially caught a removed M1 milestone
heading, which was restored before the clean lock. No tolerances were changed.

**Exact next action:** M5.2/CP2 runner over the frozen unperturbed E/S/Q controls,
using existing calibration/AHRS and explicit alignment/maps/heading/grid, all
independent row/rep/phase/proxy/summary gates, warmup diagnostics and two clean
locked processes. The boundary/evidence recipes must be implemented explicitly;
CP1 manifest enumeration is not downstream acceptance. CP4 still requires actual
external M1 read-only replay and cannot pass from pytest skips.


Final closeout verification: full587 passed/2 skipped (exit0), Ruff passed,
strict mypy23 files passed; docs893 Markdown/39 immutable archive hashes/0 errors;
whitespace passed. Required test command used a fresh
`.tmp-m5-cp1-closeout-full` root with normal Windows permissions. All retained
bytes/hash checks passed; no implementation or dependency changes after lock.
