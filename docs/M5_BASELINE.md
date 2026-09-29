# M5.2 clean baseline runner

`examples/m5_baseline.py` executes the 30 `CLEAN-E/S/Q` cases already frozen
in the CP1 manifest. E runs all thirteen trajectories from exact segment
orientations. S runs those trajectories from sensor SI through the existing
imucal calibration, R_NS, fresh pinned imufusion AHRS, and one fixed R_NK
alignment. Q additionally encodes and reads the four frozen M1-framed demos
through the existing immutable replay adapter. Hardware remains frozen.

The separate common-grid stage supplies explicit synthetic clock/heading and
alignment evidence to M3 and all M4 stages. The independent oracle uses scalar,
matrix and rational-time equations; generator quaternions and downstream
metrics never supply expected values. Each result retains errors with support,
signed/absolute values, maxima/RMSE, matches, missed/false candidates, evaluation
coverage, original QC, SI/null validity and all source/calibration/frame records.
Summary gates cover phases, speeds, proxy extrema, variability and cadence;
the F90/F90-NEXT pair also checks descriptive longitudinal comparison.
The identical declared calibration artifacts cite the frozen parameter contract
as their source; they are not fitted from evaluation motion. Per-session raw
hashes remain stream lineage. Changing raw input alone therefore does not
pretend to be a different calibration for the comparison gate.

The [frozen M5 contract](../protocols/M5_VALIDATION_CONTRACT.md) remains
unchanged. All ordinary sessions pass their full stationary warmup to the M4
state machine as arming context. Row/interval errors and duration coverage
still use only the evaluation window beginning at 5 seconds. PARTIAL retains
its explicit [5.8,20] second analysis crop. Both context and evaluation windows
are recorded; M4's reported analysis-window duration describes its context
window, not the error/coverage denominator. First-row and end-of-warmup
orientation errors are separately reported.

E constructs its elementary axis-angle input from integer microseconds and
rational degree ratios. This follows M4's symbolic equality-fixture rule and
avoids losing a mathematically exact threshold through floating-time
subtraction. No threshold slack, snapping of measured angles, changed
production algorithm, modified source observations or widened budget is used.
S/Q retain CP1's continuous sensor generator and original input timestamps.
For an empty eligible set, the existing M4 active-time sum is valid zero;
ROM/SD/CV and cadence retain their existing availability reasons. The CP1
oracle's `active_s=None` summary placeholder is not used as the M4 empty-sum
expectation; no frozen source/oracle file is changed.

Run from a clean committed checkout with the pinned environment:

```powershell
.venv/Scripts/python.exe examples/m5_baseline.py --output <previously-absent-root>
```

`--development` permits an explicitly nonformal diagnostic run. Formal launch
records exact HEAD, tracked cleanliness, all package/processing/contract/truth/
manifest/lock hashes and runtime versions. Existing output roots are rejected;
partial and failed outputs are preserved. Exit 0 means all 30 cases and both
comparisons passed; exit 1 retains acceptance failures, exit 2 means blocked
launch. The separate SHA256SUMS manifest excludes its own digest. Two separate
processes from the same lock must produce identical bytes before CP2 passes.
Earlier stopped attempts are linked through an immutable partial-file inventory
in each later launch manifest. They are never resumed or completed in place.

CP2 is a clean synthetic numerical/evidence checkpoint. CP3 perturbation scans,
CP4 actual external M1 replay and CP5 overall M5 closeout remain separate.
Synthetic supported evidence never makes anatomy physically validated.

Retained formal CP2 evidence: [baseline report](../experiments/M5_CP2_20260926/README.md),
[independent audit](../experiments/M5_CP2_20260926/reproducibility.json) and
[source interpretation notes](../experiments/M5_CP2_20260926/SPEC_NOTES.md).
All30 frozen clean cases and both comparisons passed; two independent processes
produced identical bytes for all131 files. This does not pass CP3–CP5.
