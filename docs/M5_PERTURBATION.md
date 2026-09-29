# M5.3 finite perturbation validation

`examples/m5_perturbation.py` executes the entire frozen 1,142-case CP1 manifest.
It preserves independent nominal labels, full evaluation denominators, each seed,
original sample and packet counters, actual/claimed times, per-row/per-repetition
errors, null metrics, missed/false counts, QC, exclusions and stage exceptions.
The CP2 runner remains unchanged. CP3 orchestration derives from its locked
pipeline, with CP0 working budgets applied explicitly, never estimated from results.

Noise, constant/ramp bias, real-sample/timestamp jitter, sample/packet deletion,
clock scale and both heading mechanisms execute their frozen source recipes.
C-APPLY compares recovered SI against the accepted CP1 undisturbed source;
independent finite-difference oracle rates are a separate diagnostic cross-check.
C-FIT uses only the stationary [0,5] second window and existing M2 estimator.
An exact downstream clock map never rescales device dt inside the AHRS.

Existing exact M4 C/P/T/U boundary constructions execute as their full unchanged
pytest suites. Each reusable case links the normalized collected assertion records
and matched clean full-chain control; this is fixture reuse rather than evidence
that an AHRS reproduces a floating point equality. T8/T9 and comparison controls
retain the original M4 construction. Epoch/CRC/hash/node controls reuse the
unchanged M2 replay tests. Operational pytest logs/times are separate from products.

Session-scoped memoization caches repeated identical pure production calls only.
All input/output arrays become read-only; caches end after each case. No AHRS,
stateful backend or source is shared between cases. A regression checks complete
canonical equality to uncached execution. Production code remains unchanged.

Large artifacts use deterministic gzip (mtime=0), wrapping canonical sorted-key
UTF-8 LF JSON. SHA256SUMS binds the compressed bytes. Case results and normalized
fixture results remain ordinary canonical JSON. Two independent process launches
must produce identical product bytes; operational logs are excluded explicitly.

Formal command from clean committed pinned source:

```powershell
.venv/Scripts/python.exe examples/m5_perturbation.py --output <absent-root> --workers 4
```

Exit 0 requires every required recipe and C/W/rejection/evidence gate to pass.
Exit 1 retains failures; exit 2 means blocked launch. Stress completion is execution
with a documented limitation, never an accuracy PASS. Unexpected exceptions fail.
Existing roots/raw datasets are rejected. Failed/partial roots are never resumed.

Early diagnostics found a valid-format all-zero clock-map evidence hash accepted
by the existing M2 API, and the 50 ms gap equality retained coverage but failed the
frozen speed budget at a motion knot. GAP is a predeclared stage-boundary
control, so accepted input with full coverage passes its QC boundary while its
accuracy failure remains diagnostic; it does not become working-domain accuracy
evidence. Hash controls retain their actual evidence failures. No revised
truth or thresholds. CP3 remains OPEN until the complete matrix is independently
audited and every required acceptance issue resolved. CP4 and CP5 are separate.

Working row/interval errors use only finite valid supports while retaining null
rows, signed errors and full support vectors; maxima cannot be inferred from an
all-invalid result. Coverage separately uses the full physical denominator.
This distinction caught and corrected a validation-runner availability defect
in the first stopped formal pair; immutable file inventory is retained.

Drift evidence binds its known injected rate bound to the evaluation [5,end]
window (full warmup remains separate M4 arming context). The original upstream
reason for a drift record not covering the repetition is thorax_drift_unbounded.
Red/green tests caught a window metadata mismatch and a wrong expected reason;
a second immutable stopped pair is preserved in additional_attempts.

Initialization diagnostics require a true observation at each declared support;
single-row inputs retain null at the missing5s warmup point. Post-alignment
world-yaw isolation has its own explicit recipe label. A third stopped pair is
retained; full direct input/gap preflight19/19 passes and focused16 tests pass.

## Complete M5.3 disposition — 2026-09-26

[The complete perturbation report](../experiments/M5_CP3_20260926/README.md)
retains1,142 cases per formal4 run from source lock6f1dec791aa6e959fd41abbb46c0e7da5053601a.
Both launches exited1 because CP3 FAILED, with0 not-run and0 unexpected exceptions.
Independent audit passes:5,380 files/1,661,983,578 bytes per run, all bytes equal;
13,865,857 error scalars per run independently recomputed.

All589 W cases meet >=98% full time coverage and complete-rep recall1.0,
with0 missed/false reps. However39 loss/jitter W cases fail numerical budgets
(max interval-speed error61.223146deg/s versus6deg/s; packet-one node orientation
up to1.442900deg versus1deg). One300s correct -500ppm map loses the final10ms
support and returns interrupted/upstream_invalid instead of partial_end on the
55th incomplete candidate, though all54 eligible repetitions pass numeric/recall
gates. Six heading/A-map/B-map E/S reference-hash controls fail evidence binding;
raw-file hash/CRC/node controls pass. Stress completion remains a limitation record.

Full612 passed/2 existing external-M1 skips in359.79s; all16 CP3 regression tests
included; Ruff/strict mypy25 files/docs/whitespace passed. The prior OpenBLAS
resource failure and temporary owned-worker scheduling throttle are documented.
No production, raw, public schema, frozen truth/seed/budget or backend change.
CP3/CP4/CP5/overall M5 remain OPEN; no physical hardware action.
