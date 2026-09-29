# M5.4 stage D failed retained replay — 2026-09-27

Branch main; exact source/tool lock 6a305eed744caa89276ea3d0961afc468ab398e4.
Maintainer authorized fourth segment full M1 dual USB, then stop. Actual
complete-input development replay exit1; separate independent audit exit1.
FAILED root experiments/M5_CP4_STAGE_D_DUAL_USB_20260927 is immutable; never
repair/reclassify it. Full products/source ZIP/logs/input/output hashes in
experiments/M5_CP4_STAGE_D_20260927/verification.json. No retry was made.

Both complete original streams decoded: A46943 packets/187772 samples,
B47856/191424, total94799/379196; original endpoints/counts/flags/time/SI/QC
preserved. All eleven external manifest entries and manifest hash match
before/after replay and diagnostic. A identity calibration/node AHRS completed;
failed complete auditor directly recomputed all187772 A quaternions before
rejecting incomplete B. B rejected at calibration; B AHRS and actual dual
M2/M3/M4 are NOT RUN. No stage D or CP4 acceptance is claimed.

Root cause independently reproduced from unchanged B raw: index23297,
sample sequence1604645, packet401161, device_time_us15120024658,
elapsed219.073426s, sample_flags2=GYRO_CLIPPED, raw gyro[-29088,5345,119],
X=-509.04deg/s. One flagged and one existing configured-range exceedance row
(same row). Existing apply_calibration first rejects with
"clipped samples cannot be used for calibration"; configured gyro500deg/s,
existing tolerance1.001. This is source-quality evidence, not a proven
firmware/acquisition defect; M1 acquisition-stability DONE and hardware freeze
remain in force. No flag stripping, filtering, calibration bypass, range/gate
change, raw edit or synthetic replacement. See failure-diagnostic.json/.log
and retained diagnose-failed-attempt.py; every original B observation/SI row
was independently checked against the failed result.

Source verification full718 passed/no skips, captured exit0; focused45 includes
both real external M1 tests. Ruff/strict mypy30/docs pass. Initial whitespace
failure was only HANDOFF trailing blank, fixed and rechecked; original failure
log retained. These checks do not satisfy missing complete D numerical evidence.
No owned process remains; historical scratch and failed products preserved.
Sandbox16 old operational/tmp apparent deletions are permission artifacts;
normal-permission tracked tree was clean at launch. CP0–CP3 accepted;
CP4/CP5/overall M5 OPEN, D FAILED, E NOT RUN.

Next requires maintainer decision on an explicit processed handling contract
for the original clipped/range-exceeding observation before any new D attempt.
Current authorization does not permit relaxing the frozen gate or silently
discarding that sample. Preserve original failure/source lock; if a new
processing contract is authorized, test it first and declare reacceptance
scope, then use a new clean lock and ABSENT output root. Do not enter E or
CP5, acquire new data, reopen hardware or push under this segment.
No physical action required. Retained-evidence commit resolves with
git log -1 --format=%H -- experiments/M5_CP4_STAGE_D_20260927/verification.json.
Current state tip resolves with git log -1 --format=%H -- HANDOFF.md.

Reproduce the read-only failure diagnosis with a previously absent output file:

```powershell
.venv/Scripts/python.exe experiments/M5_CP4_STAGE_D_20260927/diagnose-failed-attempt.py --output .tmp-new-m54-d-diagnostic.json
```

Diagnostic recheck exit0 and byte-identical result confirm the failure evidence; this is not D success. Original failed output/source ZIP/logs remain immutable.

## Original launch instructions and limitations

# M5.4 stage D — complete real M1 dual USB replay

Authorized 2026-09-27 fourth segment; stop after D. CP0–CP3 accepted;
CP4/CP5/overall M5 OPEN. Stage E full two-process B/C/D acceptance is separate.
This directory retains source/tool verification, standalone development execution
and independent audit. Current machine-readable status: `checks.json`, followed
by `execution.json` and `verification.json` once the locked execution is retained.

Input root: `<external-data>/kineimu_m1_usb_30min_20260925_01` via
`KINEIMU_M1_RAW_ROOT`. All eleven original manifest entries and manifest hash
`219a7a2cf07eb962ee3bf4755dc0a49d4ccf48447bb27be1edc08d55f5529ea7`
are mandatory before and after execution. A has 46,943 packets/187,772 samples,
device endpoints 14933068145–16733174774 us; B has 47,856/191,424,
14900951232–16701005981 us. Anchors come from the M1 report and M2 tests.

Fresh development output root: `experiments/M5_CP4_STAGE_D_DUAL_USB_20260927`.
Use native thread settings OPENBLAS_NUM_THREADS/OMP_NUM_THREADS/MKL_NUM_THREADS=1.
Source lock resolves with `git log -1 --format=%H -- kineimu_shoulder/validation/recorded_dual.py`;
actual launch HEAD and source bytes must match retained manifest and snapshot.

```powershell
.venv/Scripts/python.exe -m kineimu_shoulder.validation.recorded_dual --output experiments/M5_CP4_STAGE_D_DUAL_USB_20260927
.venv/Scripts/python.exe experiments/M5_CP4_STAGE_D_20260927/audit.py --run experiments/M5_CP4_STAGE_D_DUAL_USB_20260927 --root <external-data>/kineimu_m1_usb_30min_20260925_01 --output experiments/M5_CP4_STAGE_D_20260927/audit.json
```

Only independent illustrative calibration/node AHRS is computed. A and B keep
their original complete observations, sensor SI, counters/flags/host arrival,
device clocks and separate arbitrary worlds. No resampling/reconstruction is
applied. The complete downstream rejection probe uses actual A/B streams and
requested original A timestamp support; it establishes no shared grid/heading
or anatomical transform. Existing M2/M3/M4 reasons propagate to invalid/null
shoulder values. Diagnostic left/flexion is an interface parameter, not an
observed exercise. No motion/anatomical/clinical accuracy claim is made.
See [interface and limitations](../../docs/M5_RECORDED_DUAL.md).

The independent auditor decodes both raw files directly, checks every original
row and sensor/node SI, directly recomputes every pinned imufusion quaternion,
and checks all downstream unavailable rows and report bindings. Product hashes
alone cannot pass semantic corruption tests. All original sources, prior scratch
and failed/partial test evidence are preserved. New attempts require new roots.

Verification commands are captured with actual exit codes and normalized log
hashes. KINEIMU_M1_RAW_ROOT is set for full/focused tests so both external M1
tests must actually run. Test-first missing-runner red, calibration serialization
and relative-time field audit failures, final green, complete pytest, Ruff,
strict mypy, docs and whitespace logs are retained. No production/backend,
raw/public-schema/truth/seed/gate/hardware changes; no acquisition or push.
