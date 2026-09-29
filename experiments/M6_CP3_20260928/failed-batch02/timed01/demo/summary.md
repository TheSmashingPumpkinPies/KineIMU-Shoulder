# KineIMU Shoulder — complete sensor replay Demo

M6 demo_passed=true. Four stored-Q trajectories completed under the frozen clean S/Q gates.

Source type: synthetic; anatomical_eligible=false. Machine angles remain rad; display angles use deg = rad × 180/pi. Speed remains rad/s; durations s, boundaries us.

Processing: m5-processing/1.1; source HEAD: `addcdd7fb0ce2e187ebf32daa6af6051241113cd`; tracked_dirty=false.

Runtime: `{"packages": {"imucal": "2.6.0", "imufusion": "1.3.3", "numpy": "2.5.2", "scipy": "1.18.1"}, "platform": "Windows-11-10.0.26200-SP0", "python": "3.12.14", "thread_environment": {"MKL_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}}`.

Input map SHA-256: `2aa180e32003f91e57accf1d53c5b4b914e0c9e9c0ab4cdb22db02a3ab0964f9`.

Observed: decoded sensor/QC/time. Derived: calculated metrics. Assumed: known synthetic calibration/initialization/alignment/heading/clock. Validated: only the existing tested synthetic gate domain. Experimental: retained where emitted; labels are never promoted.

The original [M5 report](replay/report.json) retains passed=false, CP4 OPEN and formal=false; its stage_passed=true describes this completed stored-Q stage.

ROM uses the detected repetition boundaries; nominal full-motion 90 deg is not substituted. ROM sample SD uses ddof=1; CV is dimensionless; n<2 remains unavailable with a reason.

## F90 — flexion / left

[Machine result](replay/cases/Q-F90/result.json); [derived](replay/cases/Q-F90/derived.json.gz); [processed](replay/cases/Q-F90/processed.json.gz).

Counts (repetitions, Derived; definition=m4-exercise-summary/1.0; valid=true; reason=['ok']; anatomical_eligible=false): detected_count=3; valid_count=3; excluded_count=0; partial_start_count=0; partial_end_count=0; interrupted_count=0; proxy_valid_count=3; proxy_unavailable_count=0

Truth/count comparison: `{"false": 0, "missed": 0, "truth": 3, "valid": 3}`. Coverage: `{"denominator_s": 16.5, "invalid_duration_s": 0.0, "proxy": 1.0, "recall": 1.0, "relative": 1.0, "valid_duration_s": 16.5}`.

Exclusion reasons: `{}`.

| Node | Packets / samples | QC issues | Calibration / AHRS | Source SHA-256 |
|---|---|---|---|---|
| A | 538 / 2151 | [] | True / True | `e5bf18d8ffd43257c0e745223da5c5506205c5658763f324bccae9241371d487` |
| B | 538 / 2151 | [] | True / True | `d07f099f4171a6a4c316e37c30c63731da98ac5733e59a172f16b471a6b1977b` |

Eight core families: humerothoracic ROM; peak elevation; repetition count; movement/phase duration; hold duration; angular velocity; rep-to-rep variability; thorax compensation excursion proxy.

Aggregate definition: `m4-exercise-summary/1.0`. Each stratum retains its own denominator.

| Core family | Result |
|---|---|
| Humerothoracic ROM, mean | n=3: 80.570417 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Peak elevation, mean | n=3: 90.284607 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Repetition count | 3 valid / 3 detected; 0 excluded; Derived; valid=True; reason=['ok']; anatomical_eligible=false |
| Movement / elevation / return duration | n=3: 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Hold duration | n=3: 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Angular velocity, mean / peak | n=3: 0.666371 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.052321 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Rep-to-rep variability, range / SD / CV (n=3) | 0.046369 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.026007 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000323 dimensionless; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Thorax proxy magnitude, extension / lateral flexion / axial rotation | n=3: 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

<details>
<summary>All metric strata, repetition phases, proxy extrema and gate errors</summary>

| Metric | n | Mean | Maximum |
|---|---:|---|---|
| elevation_duration_s | 3 | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 3 | 1.052321 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.052656 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 3 | 1.051107 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.051365 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 3 | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 3 | 0.002484 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.002832 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 3 | 0.001958 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.002233 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 3 | 90.284607 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 90.324495 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 2 | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3 | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 3 | 1.052321 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.052656 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 3 | 0.666371 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.666375 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 3 | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 3 | 0.790683 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.790893 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 3 | 0.788911 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.789050 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 3 | 80.570417 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 80.600405 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_magnitude_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_max_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_min_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_magnitude_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_max_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_min_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_magnitude_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_max_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_min_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

| Variability | Value |
|---|---|
| rom_range (n=3) | 0.046369 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_sd (n=3) | 0.026007 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_cv (n=3) | 0.000323 dimensionless; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Per-repetition phase support and validity (definition=['m4-exercise/1.0', 'm3-long-axis-elevation/1.0', 'm3-relative-angular-speed/1.0']); all original boundaries and hold runs remain in machine data.

Rep 1: valid=True, reason=['ok']; start/peak/end_us=5340000/6500000/9280000; rise=[5340000, 6500000]; return=[6500000, 9280000]; hold_runs_us=[[6500000, 7500000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.051700 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.050634 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002832 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.002233 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.324495 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | unavailable (rest_interrupted); valid=false; reason=rest_interrupted; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.051700 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666365 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790893 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.789050 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.600405 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Rep 2: valid=True, reason=['ok']; start/peak/end_us=10840000/12000000/14780000; rise=[10840000, 12000000]; return=[12000000, 14780000]; hold_runs_us=[[12000000, 13000000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.052605 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.051322 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002326 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.001834 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.266506 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.052605 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666374 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790588 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.788847 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.556812 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Rep 3: valid=True, reason=['ok']; start/peak/end_us=16340000/17500000/20280000; rise=[16340000, 17500000]; return=[17500000, 20280000]; hold_runs_us=[[17500000, 18500000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.052656 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.051365 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002294 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.001808 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.262819 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.052656 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666375 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790569 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.788834 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.554036 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Thorax proxy definition/policy: `['m4-thorax-excursion/1.0', 'm4-thorax-common-grid/1.0', 'm4-thorax-preparation/1.0', 'slerp', ['known synthetic heading', 'supported'], ['known injected yaw bound over evaluation window', 'supported']]`; independent proxy denominator and heading/drift limits apply.

| Rep / component | Min / max / magnitude (deg) | Validity / evidence |
|---|---|---|
| 1 / extension | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 1 / lateral_flexion | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 1 / axial_rotation | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / extension | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / lateral_flexion | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / axial_rotation | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / extension | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / lateral_flexion | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / axial_rotation | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |

Independent error supports and unchanged gate budgets:

| Gate quantity | n | Maximum absolute error | RMSE | Tolerance | Gate |
|---|---:|---|---|---|---|
| A.initialization | 2 | 2.220446049250313e-16 rad | 1.5700924586837752e-16 rad | 0.006981317007977318 rad | True |
| A.orientation | 1651 | 2.220446049250313e-16 rad | 2.220446049250313e-16 rad | 0.006981317007977318 rad | True |
| B.initialization | 2 | 2.220446049250313e-16 rad | 1.5700924586837752e-16 rad | 0.006981317007977318 rad | True |
| B.orientation | 1651 | 0.005663503117983247 rad | 0.0029010194697843507 rad | 0.006981317007977318 rad | True |
| F90:rep-1.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| F90:rep-1.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-1.elevation_speed_max_rads | 1 | 0.004502804422126694 rad/s | 0.004502804422126694 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-1.elevation_speed_mean_rads | 1 | 0.0034369137813365924 rad/s | 0.0034369137813365924 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-1.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-1.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-1.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-1.hold_speed_max_rads | 1 | 0.0028317343779007613 rad/s | 0.0028317343779007613 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-1.hold_speed_mean_rads | 1 | 0.0022327115402707215 rad/s | 0.0022327115402707215 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-1.peak_elevation_rad | 1 | 0.0056635031179832485 rad | 0.0056635031179832485 rad | 0.017453292519943295 rad | True |
| F90:rep-1.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-1.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| F90:rep-1.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| F90:rep-1.proxy.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy_estimated_support.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy_estimated_support.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy_estimated_support.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy_estimated_support.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-1.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-1.rep_speed_max_rads | 1 | 0.004502804422126694 rad/s | 0.004502804422126694 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-1.rep_speed_mean_rads | 1 | 0.0032285620689570527 rad/s | 0.0032285620689570527 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-1.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-1.return_speed_max_rads | 1 | 0.0054948820449916 rad/s | 0.0054948820449916 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-1.return_speed_mean_rads | 1 | 0.003652248890488874 rad/s | 0.003652248890488874 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-1.rom_rad | 1 | 0.008733714565341222 rad | 0.008733714565341222 rad | 0.03490658503988659 rad | True |
| F90:rep-1.speed_estimated_mean | 1 | 0.0032285620689572747 rad/s | 0.0032285620689572747 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-1.speed_nominal_mean | 1 | 0.0032285620689572747 rad/s | 0.0032285620689572747 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-1.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-1.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-2.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| F90:rep-2.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-2.elevation_speed_max_rads | 1 | 0.005407897648036064 rad/s | 0.005407897648036064 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-2.elevation_speed_mean_rads | 1 | 0.0041243409597535585 rad/s | 0.0041243409597535585 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-2.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-2.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-2.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-2.hold_speed_max_rads | 1 | 0.0023256923160932634 rad/s | 0.0023256923160932634 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-2.hold_speed_mean_rads | 1 | 0.0018337131105486955 rad/s | 0.0018337131105486955 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-2.peak_elevation_rad | 1 | 0.004651401744813377 rad | 0.004651401744813377 rad | 0.017453292519943295 rad | True |
| F90:rep-2.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-2.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| F90:rep-2.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| F90:rep-2.preceding_rest_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-2.proxy.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy_estimated_support.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy_estimated_support.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy_estimated_support.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy_estimated_support.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-2.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-2.rep_speed_max_rads | 1 | 0.005407897648036064 rad/s | 0.005407897648036064 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-2.rep_speed_mean_rads | 1 | 0.003237842773132993 rad/s | 0.003237842773132993 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-2.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-2.return_speed_max_rads | 1 | 0.005189877636113227 rad/s | 0.005189877636113227 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-2.return_speed_mean_rads | 1 | 0.003448961742854806 rad/s | 0.003448961742854806 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-2.rom_rad | 1 | 0.007972865012829455 rad | 0.007972865012829455 rad | 0.03490658503988659 rad | True |
| F90:rep-2.speed_estimated_mean | 1 | 0.003237842773133215 rad/s | 0.003237842773133215 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-2.speed_nominal_mean | 1 | 0.003237842773133215 rad/s | 0.003237842773133215 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-2.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-2.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-3.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| F90:rep-3.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-3.elevation_speed_max_rads | 1 | 0.005458352611105166 rad/s | 0.005458352611105166 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-3.elevation_speed_mean_rads | 1 | 0.004167824549391019 rad/s | 0.004167824549391019 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-3.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-3.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-3.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-3.hold_speed_max_rads | 1 | 0.0022935233916113493 rad/s | 0.0022935233916113493 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-3.hold_speed_mean_rads | 1 | 0.001808348908410854 rad/s | 0.001808348908410854 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-3.peak_elevation_rad | 1 | 0.004587061964884898 rad | 0.004587061964884898 rad | 0.017453292519943295 rad | True |
| F90:rep-3.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-3.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| F90:rep-3.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| F90:rep-3.preceding_rest_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-3.proxy.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy_estimated_support.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy_estimated_support.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy_estimated_support.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy_estimated_support.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| F90:rep-3.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-3.rep_speed_max_rads | 1 | 0.005458352611105166 rad/s | 0.005458352611105166 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-3.rep_speed_mean_rads | 1 | 0.0032383482095086347 rad/s | 0.0032383482095086347 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-3.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| F90:rep-3.return_speed_max_rads | 1 | 0.005170483537445425 rad/s | 0.005170483537445425 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-3.return_speed_mean_rads | 1 | 0.00343599244930326 rad/s | 0.00343599244930326 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-3.rom_rad | 1 | 0.007924415468171686 rad | 0.007924415468171686 rad | 0.03490658503988659 rad | True |
| F90:rep-3.speed_estimated_mean | 1 | 0.0032383482095084126 rad/s | 0.0032383482095084126 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-3.speed_nominal_mean | 1 | 0.0032383482095084126 rad/s | 0.0032383482095084126 rad/s | 0.03490658503988659 rad/s | True |
| F90:rep-3.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| F90:rep-3.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| elevation | 1651 | 0.0056635031179832485 rad | 0.0029010194697843493 rad | 0.017453292519943295 rad | True |
| interval_speed | 1650 | 0.006509773399861807 rad/s | 0.0032931584864349306 rad/s | 0.03490658503988659 rad/s | True |
| summary.active_s | 1 | 0.0 s | 0.0 s | 0.30000000000000004 s | True |
| summary.cadence_per_s | 1 | 0.0 s^-1 | 0.0 s^-1 | 0.006609560067681895 s^-1 | True |
| summary.elevation_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.elevation_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.elevation_speed_max_rads.maximum | 1 | 0.005458352611105166 rad/s | 0.005458352611105166 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_max_rads.mean | 1 | 0.005123018227089382 rad/s | 0.005123018227089382 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_mean_rads.maximum | 1 | 0.004167824549391019 rad/s | 0.004167824549391019 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_mean_rads.mean | 1 | 0.003909693096826983 rad/s | 0.003909693096826983 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.hold_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.hold_speed_max_rads.maximum | 1 | 0.0028317343779007613 rad/s | 0.0028317343779007613 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_max_rads.mean | 1 | 0.002483650028535125 rad/s | 0.002483650028535125 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_mean_rads.maximum | 1 | 0.0022327115402707215 rad/s | 0.0022327115402707215 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_mean_rads.mean | 1 | 0.001958257853076757 rad/s | 0.001958257853076757 rad/s | 0.03490658503988659 rad/s | True |
| summary.peak_elevation_rad.maximum | 1 | 0.0056635031179832485 rad | 0.0056635031179832485 rad | 0.017453292519943295 rad | True |
| summary.peak_elevation_rad.mean | 1 | 0.004967322275893693 rad | 0.004967322275893693 rad | 0.017453292519943295 rad | True |
| summary.preceding_rest_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.preceding_rest_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_speed_max_rads.maximum | 1 | 0.005458352611105166 rad/s | 0.005458352611105166 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_max_rads.mean | 1 | 0.005123018227089382 rad/s | 0.005123018227089382 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_mean_rads.maximum | 1 | 0.0032383482095086347 rad/s | 0.0032383482095086347 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_mean_rads.mean | 1 | 0.0032349176838661897 rad/s | 0.0032349176838661897 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.return_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.return_speed_max_rads.maximum | 1 | 0.0054948820449916 rad/s | 0.0054948820449916 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_max_rads.mean | 1 | 0.005285081072850084 rad/s | 0.005285081072850084 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_mean_rads.maximum | 1 | 0.003652248890488874 rad/s | 0.003652248890488874 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_mean_rads.mean | 1 | 0.003512401027549017 rad/s | 0.003512401027549017 rad/s | 0.03490658503988659 rad/s | True |
| summary.rom_cv | 1 | 0.0003227873760430069 1 | 0.0003227873760430069 1 | 0.051216389244558264 1 | True |
| summary.rom_max_rad | 1 | 0.008733714565341222 rad | 0.008733714565341222 rad | 0.03490658503988659 rad | True |
| summary.rom_mean_rad | 1 | 0.008210331682114269 rad | 0.008210331682114269 rad | 0.03490658503988659 rad | True |
| summary.rom_rad.maximum | 1 | 0.008733714565341222 rad | 0.008733714565341222 rad | 0.03490658503988659 rad | True |
| summary.rom_rad.mean | 1 | 0.008210331682114269 rad | 0.008210331682114269 rad | 0.03490658503988659 rad | True |
| summary.rom_range_rad | 1 | 0.0008092990971695357 rad | 0.0008092990971695357 rad | 0.06981317007977318 rad | True |
| summary.rom_sd_rad | 1 | 0.0004539097613355776 rad | 0.0004539097613355776 rad | 0.06981317007977318 rad | True |
| summary.thorax_axial_rotation_magnitude_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_magnitude_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_max_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_max_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_min_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_min_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_magnitude_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_magnitude_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_max_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_max_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_min_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_min_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_magnitude_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_magnitude_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_max_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_max_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_min_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_min_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |

</details>

## AL90 — abduction / left

[Machine result](replay/cases/Q-AL90/result.json); [derived](replay/cases/Q-AL90/derived.json.gz); [processed](replay/cases/Q-AL90/processed.json.gz).

Counts (repetitions, Derived; definition=m4-exercise-summary/1.0; valid=true; reason=['ok']; anatomical_eligible=false): detected_count=3; valid_count=3; excluded_count=0; partial_start_count=0; partial_end_count=0; interrupted_count=0; proxy_valid_count=3; proxy_unavailable_count=0

Truth/count comparison: `{"false": 0, "missed": 0, "truth": 3, "valid": 3}`. Coverage: `{"denominator_s": 16.5, "invalid_duration_s": 0.0, "proxy": 1.0, "recall": 1.0, "relative": 1.0, "valid_duration_s": 16.5}`.

Exclusion reasons: `{}`.

| Node | Packets / samples | QC issues | Calibration / AHRS | Source SHA-256 |
|---|---|---|---|---|
| A | 538 / 2151 | [] | True / True | `e5bf18d8ffd43257c0e745223da5c5506205c5658763f324bccae9241371d487` |
| B | 538 / 2151 | [] | True / True | `ec5e32d084468464ba74801c7aa63a478ff42176f7b6be2030cc0cb894e2203b` |

Eight core families: humerothoracic ROM; peak elevation; repetition count; movement/phase duration; hold duration; angular velocity; rep-to-rep variability; thorax compensation excursion proxy.

Aggregate definition: `m4-exercise-summary/1.0`. Each stratum retains its own denominator.

| Core family | Result |
|---|---|
| Humerothoracic ROM, mean | n=3: 80.570458 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Peak elevation, mean | n=3: 90.284628 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Repetition count | 3 valid / 3 detected; 0 excluded; Derived; valid=True; reason=['ok']; anatomical_eligible=false |
| Movement / elevation / return duration | n=3: 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Hold duration | n=3: 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Angular velocity, mean / peak | n=3: 0.666372 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.052320 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Rep-to-rep variability, range / SD / CV (n=3) | 0.046315 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.025975 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000322 dimensionless; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Thorax proxy magnitude, extension / lateral flexion / axial rotation | n=3: 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

<details>
<summary>All metric strata, repetition phases, proxy extrema and gate errors</summary>

| Metric | n | Mean | Maximum |
|---|---:|---|---|
| elevation_duration_s | 3 | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 3 | 1.052320 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.052660 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 3 | 1.051107 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.051366 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 3 | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 3 | 0.002482 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.002825 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 3 | 0.001959 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.002233 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 3 | 90.284628 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 90.324472 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 2 | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3 | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 3 | 1.052320 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.052660 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 3 | 0.666372 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.666375 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 3 | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 3 | 0.790686 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.790896 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 3 | 0.788911 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.789050 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 3 | 80.570458 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 80.600409 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_magnitude_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_max_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_min_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_magnitude_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_max_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_min_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_magnitude_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_max_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_min_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

| Variability | Value |
|---|---|
| rom_range (n=3) | 0.046315 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_sd (n=3) | 0.025975 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_cv (n=3) | 0.000322 dimensionless; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Per-repetition phase support and validity (definition=['m4-exercise/1.0', 'm3-long-axis-elevation/1.0', 'm3-relative-angular-speed/1.0']); all original boundaries and hold runs remain in machine data.

Rep 1: valid=True, reason=['ok']; start/peak/end_us=5340000/6500000/9280000; rise=[5340000, 6500000]; return=[6500000, 9280000]; hold_runs_us=[[6500000, 7500000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.051698 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.050633 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002825 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.002233 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.324472 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | unavailable (rest_interrupted); valid=false; reason=rest_interrupted; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.051698 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666365 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790896 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.789050 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.600409 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Rep 2: valid=True, reason=['ok']; start/peak/end_us=10840000/12000000/14780000; rise=[10840000, 12000000]; return=[12000000, 14780000]; hold_runs_us=[[12000000, 13000000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.052603 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.051323 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002325 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.001834 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.266552 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.052603 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666375 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790587 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.788847 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.556871 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Rep 3: valid=True, reason=['ok']; start/peak/end_us=16340000/17500000/20280000; rise=[16340000, 17500000]; return=[17500000, 20280000]; hold_runs_us=[[17500000, 18500000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.052660 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.051366 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002295 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.001809 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.262860 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.052660 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666375 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790575 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.788835 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.554094 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Thorax proxy definition/policy: `['m4-thorax-excursion/1.0', 'm4-thorax-common-grid/1.0', 'm4-thorax-preparation/1.0', 'slerp', ['known synthetic heading', 'supported'], ['known injected yaw bound over evaluation window', 'supported']]`; independent proxy denominator and heading/drift limits apply.

| Rep / component | Min / max / magnitude (deg) | Validity / evidence |
|---|---|---|
| 1 / extension | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 1 / lateral_flexion | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 1 / axial_rotation | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / extension | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / lateral_flexion | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / axial_rotation | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / extension | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / lateral_flexion | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / axial_rotation | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |

Independent error supports and unchanged gate budgets:

| Gate quantity | n | Maximum absolute error | RMSE | Tolerance | Gate |
|---|---:|---|---|---|---|
| A.initialization | 2 | 2.220446049250313e-16 rad | 1.5700924586837752e-16 rad | 0.006981317007977318 rad | True |
| A.orientation | 1651 | 2.220446049250313e-16 rad | 2.220446049250313e-16 rad | 0.006981317007977318 rad | True |
| AL90:rep-1.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| AL90:rep-1.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-1.elevation_speed_max_rads | 1 | 0.004500177833015373 rad/s | 0.004500177833015373 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-1.elevation_speed_mean_rads | 1 | 0.00343593128095554 rad/s | 0.00343593128095554 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-1.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-1.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-1.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-1.hold_speed_max_rads | 1 | 0.002825282407919618 rad/s | 0.002825282407919618 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-1.hold_speed_mean_rads | 1 | 0.002232736028120766 rad/s | 0.002232736028120766 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-1.peak_elevation_rad | 1 | 0.005663104216663051 rad | 0.005663104216663051 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-1.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| AL90:rep-1.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| AL90:rep-1.proxy.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy_estimated_support.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy_estimated_support.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy_estimated_support.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy_estimated_support.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-1.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-1.rep_speed_max_rads | 1 | 0.004500177833015373 rad/s | 0.004500177833015373 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-1.rep_speed_mean_rads | 1 | 0.003228290528211275 rad/s | 0.003228290528211275 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-1.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-1.return_speed_max_rads | 1 | 0.005497382412584906 rad/s | 0.005497382412584906 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-1.return_speed_mean_rads | 1 | 0.0036522743635524213 rad/s | 0.0036522743635524213 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-1.rom_rad | 1 | 0.008733784319692184 rad | 0.008733784319692184 rad | 0.03490658503988659 rad | True |
| AL90:rep-1.speed_estimated_mean | 1 | 0.003228290528211497 rad/s | 0.003228290528211497 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-1.speed_nominal_mean | 1 | 0.003228290528211497 rad/s | 0.003228290528211497 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-1.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-1.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-2.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| AL90:rep-2.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-2.elevation_speed_max_rads | 1 | 0.005405251646352083 rad/s | 0.005405251646352083 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-2.elevation_speed_mean_rads | 1 | 0.004125101093509498 rad/s | 0.004125101093509498 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-2.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-2.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-2.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-2.hold_speed_max_rads | 1 | 0.002324602526301457 rad/s | 0.002324602526301457 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-2.hold_speed_mean_rads | 1 | 0.0018343363464043176 rad/s | 0.0018343363464043176 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-2.peak_elevation_rad | 1 | 0.004652206355561406 rad | 0.004652206355561406 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-2.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| AL90:rep-2.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| AL90:rep-2.preceding_rest_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-2.proxy.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy_estimated_support.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy_estimated_support.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy_estimated_support.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy_estimated_support.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-2.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-2.rep_speed_max_rads | 1 | 0.005405251646352083 rad/s | 0.005405251646352083 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-2.rep_speed_mean_rads | 1 | 0.0032383294086729686 rad/s | 0.0032383294086729686 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-2.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-2.return_speed_max_rads | 1 | 0.005188526448244857 rad/s | 0.005188526448244857 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-2.return_speed_mean_rads | 1 | 0.003449193401851902 rad/s | 0.003449193401851902 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-2.rom_rad | 1 | 0.007973900599577366 rad | 0.007973900599577366 rad | 0.03490658503988659 rad | True |
| AL90:rep-2.speed_estimated_mean | 1 | 0.0032383294086731906 rad/s | 0.0032383294086731906 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-2.speed_nominal_mean | 1 | 0.0032383294086731906 rad/s | 0.0032383294086731906 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-2.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-2.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-3.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| AL90:rep-3.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-3.elevation_speed_max_rads | 1 | 0.0054623901461663404 rad/s | 0.0054623901461663404 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-3.elevation_speed_mean_rads | 1 | 0.004168558075715367 rad/s | 0.004168558075715367 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-3.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-3.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-3.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-3.hold_speed_max_rads | 1 | 0.0022947864317616824 rad/s | 0.0022947864317616824 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-3.hold_speed_mean_rads | 1 | 0.0018086170465440158 rad/s | 0.0018086170465440158 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-3.peak_elevation_rad | 1 | 0.004587773493454295 rad | 0.004587773493454295 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-3.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| AL90:rep-3.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| AL90:rep-3.preceding_rest_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-3.proxy.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy_estimated_support.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy_estimated_support.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy_estimated_support.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy_estimated_support.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AL90:rep-3.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-3.rep_speed_max_rads | 1 | 0.0054623901461663404 rad/s | 0.0054623901461663404 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-3.rep_speed_mean_rads | 1 | 0.003238823103194899 rad/s | 0.003238823103194899 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-3.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AL90:rep-3.return_speed_max_rads | 1 | 0.005176623981399064 rad/s | 0.005176623981399064 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-3.return_speed_mean_rads | 1 | 0.003436414950682254 rad/s | 0.003436414950682254 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-3.rom_rad | 1 | 0.007925435232898126 rad | 0.007925435232898126 rad | 0.03490658503988659 rad | True |
| AL90:rep-3.speed_estimated_mean | 1 | 0.003238823103194677 rad/s | 0.003238823103194677 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-3.speed_nominal_mean | 1 | 0.003238823103194677 rad/s | 0.003238823103194677 rad/s | 0.03490658503988659 rad/s | True |
| AL90:rep-3.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AL90:rep-3.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| B.initialization | 2 | 2.220446049250313e-16 rad | 1.5700924586837752e-16 rad | 0.006981317007977318 rad | True |
| B.orientation | 1651 | 0.005663104217917617 rad | 0.002901195666556593 rad | 0.006981317007977318 rad | True |
| elevation | 1651 | 0.005663104216663051 rad | 0.0029011956625724536 rad | 0.017453292519943295 rad | True |
| interval_speed | 1650 | 0.006508707815952031 rad/s | 0.003293411224473474 rad/s | 0.03490658503988659 rad/s | True |
| summary.active_s | 1 | 0.0 s | 0.0 s | 0.30000000000000004 s | True |
| summary.cadence_per_s | 1 | 0.0 s^-1 | 0.0 s^-1 | 0.006609560067681895 s^-1 | True |
| summary.elevation_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.elevation_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.elevation_speed_max_rads.maximum | 1 | 0.0054623901461663404 rad/s | 0.0054623901461663404 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_max_rads.mean | 1 | 0.005122606541844599 rad/s | 0.005122606541844599 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_mean_rads.maximum | 1 | 0.004168558075715367 rad/s | 0.004168558075715367 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_mean_rads.mean | 1 | 0.003909863483393394 rad/s | 0.003909863483393394 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.hold_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.hold_speed_max_rads.maximum | 1 | 0.002825282407919618 rad/s | 0.002825282407919618 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_max_rads.mean | 1 | 0.0024815571219942525 rad/s | 0.0024815571219942525 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_mean_rads.maximum | 1 | 0.002232736028120766 rad/s | 0.002232736028120766 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_mean_rads.mean | 1 | 0.0019585631403563667 rad/s | 0.0019585631403563667 rad/s | 0.03490658503988659 rad/s | True |
| summary.peak_elevation_rad.maximum | 1 | 0.005663104216663051 rad | 0.005663104216663051 rad | 0.017453292519943295 rad | True |
| summary.peak_elevation_rad.mean | 1 | 0.00496769468855951 rad | 0.00496769468855951 rad | 0.017453292519943295 rad | True |
| summary.preceding_rest_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.preceding_rest_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_speed_max_rads.maximum | 1 | 0.0054623901461663404 rad/s | 0.0054623901461663404 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_max_rads.mean | 1 | 0.005122606541844599 rad/s | 0.005122606541844599 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_mean_rads.maximum | 1 | 0.003238823103194899 rad/s | 0.003238823103194899 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_mean_rads.mean | 1 | 0.003235147680026418 rad/s | 0.003235147680026418 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.return_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.return_speed_max_rads.maximum | 1 | 0.005497382412584906 rad/s | 0.005497382412584906 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_max_rads.mean | 1 | 0.005287510947409646 rad/s | 0.005287510947409646 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_mean_rads.maximum | 1 | 0.0036522743635524213 rad/s | 0.0036522743635524213 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_mean_rads.mean | 1 | 0.003512627572028748 rad/s | 0.003512627572028748 rad/s | 0.03490658503988659 rad/s | True |
| summary.rom_cv | 1 | 0.00032239478243892354 1 | 0.00032239478243892354 1 | 0.051216389244558264 1 | True |
| summary.rom_max_rad | 1 | 0.008733784319692184 rad | 0.008733784319692184 rad | 0.03490658503988659 rad | True |
| summary.rom_mean_rad | 1 | 0.008211040050722485 rad | 0.008211040050722485 rad | 0.03490658503988659 rad | True |
| summary.rom_rad.maximum | 1 | 0.008733784319692184 rad | 0.008733784319692184 rad | 0.03490658503988659 rad | True |
| summary.rom_rad.mean | 1 | 0.008211040050722485 rad | 0.008211040050722485 rad | 0.03490658503988659 rad | True |
| summary.rom_range_rad | 1 | 0.0008083490867940579 rad | 0.0008083490867940579 rad | 0.06981317007977318 rad | True |
| summary.rom_sd_rad | 1 | 0.0004533579171000317 rad | 0.0004533579171000317 rad | 0.06981317007977318 rad | True |
| summary.thorax_axial_rotation_magnitude_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_magnitude_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_max_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_max_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_min_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_min_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_magnitude_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_magnitude_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_max_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_max_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_min_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_min_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_magnitude_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_magnitude_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_max_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_max_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_min_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_min_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |

</details>

## AR90 — abduction / right

[Machine result](replay/cases/Q-AR90/result.json); [derived](replay/cases/Q-AR90/derived.json.gz); [processed](replay/cases/Q-AR90/processed.json.gz).

Counts (repetitions, Derived; definition=m4-exercise-summary/1.0; valid=true; reason=['ok']; anatomical_eligible=false): detected_count=3; valid_count=3; excluded_count=0; partial_start_count=0; partial_end_count=0; interrupted_count=0; proxy_valid_count=3; proxy_unavailable_count=0

Truth/count comparison: `{"false": 0, "missed": 0, "truth": 3, "valid": 3}`. Coverage: `{"denominator_s": 16.5, "invalid_duration_s": 0.0, "proxy": 1.0, "recall": 1.0, "relative": 1.0, "valid_duration_s": 16.5}`.

Exclusion reasons: `{}`.

| Node | Packets / samples | QC issues | Calibration / AHRS | Source SHA-256 |
|---|---|---|---|---|
| A | 538 / 2151 | [] | True / True | `e5bf18d8ffd43257c0e745223da5c5506205c5658763f324bccae9241371d487` |
| B | 538 / 2151 | [] | True / True | `de64431c62f58609ee807e3c655acc57caa957c32e2bb25039c3233483f64f3a` |

Eight core families: humerothoracic ROM; peak elevation; repetition count; movement/phase duration; hold duration; angular velocity; rep-to-rep variability; thorax compensation excursion proxy.

Aggregate definition: `m4-exercise-summary/1.0`. Each stratum retains its own denominator.

| Core family | Result |
|---|---|
| Humerothoracic ROM, mean | n=3: 80.570458 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Peak elevation, mean | n=3: 90.284628 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Repetition count | 3 valid / 3 detected; 0 excluded; Derived; valid=True; reason=['ok']; anatomical_eligible=false |
| Movement / elevation / return duration | n=3: 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Hold duration | n=3: 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Angular velocity, mean / peak | n=3: 0.666372 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.052320 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Rep-to-rep variability, range / SD / CV (n=3) | 0.046315 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.025975 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000322 dimensionless; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Thorax proxy magnitude, extension / lateral flexion / axial rotation | n=3: 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

<details>
<summary>All metric strata, repetition phases, proxy extrema and gate errors</summary>

| Metric | n | Mean | Maximum |
|---|---:|---|---|
| elevation_duration_s | 3 | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 3 | 1.052320 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.052660 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 3 | 1.051107 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.051366 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 3 | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 3 | 0.002482 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.002825 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 3 | 0.001959 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.002233 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 3 | 90.284628 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 90.324472 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 2 | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3 | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 3 | 1.052320 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.052660 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 3 | 0.666372 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.666375 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 3 | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 3 | 0.790686 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.790896 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 3 | 0.788911 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.789050 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 3 | 80.570458 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 80.600409 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_magnitude_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_max_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_min_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_magnitude_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_max_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_min_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_magnitude_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_max_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_min_rad | 3 | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

| Variability | Value |
|---|---|
| rom_range (n=3) | 0.046315 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_sd (n=3) | 0.025975 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_cv (n=3) | 0.000322 dimensionless; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Per-repetition phase support and validity (definition=['m4-exercise/1.0', 'm3-long-axis-elevation/1.0', 'm3-relative-angular-speed/1.0']); all original boundaries and hold runs remain in machine data.

Rep 1: valid=True, reason=['ok']; start/peak/end_us=5340000/6500000/9280000; rise=[5340000, 6500000]; return=[6500000, 9280000]; hold_runs_us=[[6500000, 7500000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.051698 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.050633 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002825 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.002233 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.324472 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | unavailable (rest_interrupted); valid=false; reason=rest_interrupted; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.051698 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666365 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790896 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.789050 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.600409 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Rep 2: valid=True, reason=['ok']; start/peak/end_us=10840000/12000000/14780000; rise=[10840000, 12000000]; return=[12000000, 14780000]; hold_runs_us=[[12000000, 13000000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.052603 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.051323 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002325 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.001834 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.266552 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.052603 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666375 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790587 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.788847 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.556871 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Rep 3: valid=True, reason=['ok']; start/peak/end_us=16340000/17500000/20280000; rise=[16340000, 17500000]; return=[17500000, 20280000]; hold_runs_us=[[17500000, 18500000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.052660 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.051366 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002295 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.001809 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.262860 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.052660 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666375 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790575 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.788835 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.554094 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Thorax proxy definition/policy: `['m4-thorax-excursion/1.0', 'm4-thorax-common-grid/1.0', 'm4-thorax-preparation/1.0', 'slerp', ['known synthetic heading', 'supported'], ['known injected yaw bound over evaluation window', 'supported']]`; independent proxy denominator and heading/drift limits apply.

| Rep / component | Min / max / magnitude (deg) | Validity / evidence |
|---|---|---|
| 1 / extension | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 1 / lateral_flexion | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 1 / axial_rotation | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / extension | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / lateral_flexion | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / axial_rotation | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / extension | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / lateral_flexion | -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / -0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / axial_rotation | 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000000 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |

Independent error supports and unchanged gate budgets:

| Gate quantity | n | Maximum absolute error | RMSE | Tolerance | Gate |
|---|---:|---|---|---|---|
| A.initialization | 2 | 2.220446049250313e-16 rad | 1.5700924586837752e-16 rad | 0.006981317007977318 rad | True |
| A.orientation | 1651 | 2.220446049250313e-16 rad | 2.220446049250313e-16 rad | 0.006981317007977318 rad | True |
| AR90:rep-1.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| AR90:rep-1.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-1.elevation_speed_max_rads | 1 | 0.004500177833020924 rad/s | 0.004500177833020924 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-1.elevation_speed_mean_rads | 1 | 0.003435931280955762 rad/s | 0.003435931280955762 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-1.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-1.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-1.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-1.hold_speed_max_rads | 1 | 0.002825282407919618 rad/s | 0.002825282407919618 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-1.hold_speed_mean_rads | 1 | 0.0022327360281204334 rad/s | 0.0022327360281204334 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-1.peak_elevation_rad | 1 | 0.005663104216662607 rad | 0.005663104216662607 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-1.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| AR90:rep-1.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| AR90:rep-1.proxy.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy_estimated_support.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy_estimated_support.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy_estimated_support.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy_estimated_support.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-1.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-1.rep_speed_max_rads | 1 | 0.004500177833020924 rad/s | 0.004500177833020924 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-1.rep_speed_mean_rads | 1 | 0.003228290528211164 rad/s | 0.003228290528211164 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-1.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-1.return_speed_max_rads | 1 | 0.005497382412584906 rad/s | 0.005497382412584906 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-1.return_speed_mean_rads | 1 | 0.0036522743635521993 rad/s | 0.0036522743635521993 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-1.rom_rad | 1 | 0.008733784319692184 rad | 0.008733784319692184 rad | 0.03490658503988659 rad | True |
| AR90:rep-1.speed_estimated_mean | 1 | 0.003228290528211386 rad/s | 0.003228290528211386 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-1.speed_nominal_mean | 1 | 0.003228290528211386 rad/s | 0.003228290528211386 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-1.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-1.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-2.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| AR90:rep-2.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-2.elevation_speed_max_rads | 1 | 0.005405251646352083 rad/s | 0.005405251646352083 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-2.elevation_speed_mean_rads | 1 | 0.004125101093508832 rad/s | 0.004125101093508832 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-2.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-2.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-2.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-2.hold_speed_max_rads | 1 | 0.002324602526301457 rad/s | 0.002324602526301457 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-2.hold_speed_mean_rads | 1 | 0.0018343363464046506 rad/s | 0.0018343363464046506 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-2.peak_elevation_rad | 1 | 0.00465220635556074 rad | 0.00465220635556074 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-2.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| AR90:rep-2.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| AR90:rep-2.preceding_rest_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-2.proxy.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy_estimated_support.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy_estimated_support.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy_estimated_support.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy_estimated_support.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-2.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-2.rep_speed_max_rads | 1 | 0.005405251646352083 rad/s | 0.005405251646352083 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-2.rep_speed_mean_rads | 1 | 0.0032383294086729686 rad/s | 0.0032383294086729686 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-2.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-2.return_speed_max_rads | 1 | 0.005188526448244857 rad/s | 0.005188526448244857 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-2.return_speed_mean_rads | 1 | 0.003449193401852013 rad/s | 0.003449193401852013 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-2.rom_rad | 1 | 0.007973900599577144 rad | 0.007973900599577144 rad | 0.03490658503988659 rad | True |
| AR90:rep-2.speed_estimated_mean | 1 | 0.0032383294086731906 rad/s | 0.0032383294086731906 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-2.speed_nominal_mean | 1 | 0.0032383294086731906 rad/s | 0.0032383294086731906 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-2.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-2.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-3.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| AR90:rep-3.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-3.elevation_speed_max_rads | 1 | 0.005462390146160789 rad/s | 0.005462390146160789 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-3.elevation_speed_mean_rads | 1 | 0.004168558075714923 rad/s | 0.004168558075714923 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-3.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-3.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-3.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-3.hold_speed_max_rads | 1 | 0.0022947864317616824 rad/s | 0.0022947864317616824 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-3.hold_speed_mean_rads | 1 | 0.0018086170465440158 rad/s | 0.0018086170465440158 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-3.peak_elevation_rad | 1 | 0.0045877734934536285 rad | 0.0045877734934536285 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-3.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| AR90:rep-3.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| AR90:rep-3.preceding_rest_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-3.proxy.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy_estimated_support.axial_rotation.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy_estimated_support.axial_rotation.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy_estimated_support.extension.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy_estimated_support.extension.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| AR90:rep-3.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-3.rep_speed_max_rads | 1 | 0.005462390146160789 rad/s | 0.005462390146160789 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-3.rep_speed_mean_rads | 1 | 0.0032388231031944548 rad/s | 0.0032388231031944548 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-3.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| AR90:rep-3.return_speed_max_rads | 1 | 0.005176623981399064 rad/s | 0.005176623981399064 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-3.return_speed_mean_rads | 1 | 0.0034364149506815878 rad/s | 0.0034364149506815878 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-3.rom_rad | 1 | 0.007925435232897682 rad | 0.007925435232897682 rad | 0.03490658503988659 rad | True |
| AR90:rep-3.speed_estimated_mean | 1 | 0.0032388231031942327 rad/s | 0.0032388231031942327 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-3.speed_nominal_mean | 1 | 0.0032388231031942327 rad/s | 0.0032388231031942327 rad/s | 0.03490658503988659 rad/s | True |
| AR90:rep-3.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| AR90:rep-3.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| B.initialization | 2 | 2.220446049250313e-16 rad | 1.5700924586837752e-16 rad | 0.006981317007977318 rad | True |
| B.orientation | 1651 | 0.005663104217917617 rad | 0.002901195666556593 rad | 0.006981317007977318 rad | True |
| elevation | 1651 | 0.005663104216662607 rad | 0.002901195662572308 rad | 0.017453292519943295 rad | True |
| interval_speed | 1650 | 0.006508707815952031 rad/s | 0.003293411224473317 rad/s | 0.03490658503988659 rad/s | True |
| summary.active_s | 1 | 0.0 s | 0.0 s | 0.30000000000000004 s | True |
| summary.cadence_per_s | 1 | 0.0 s^-1 | 0.0 s^-1 | 0.006609560067681895 s^-1 | True |
| summary.elevation_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.elevation_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.elevation_speed_max_rads.maximum | 1 | 0.005462390146160789 rad/s | 0.005462390146160789 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_max_rads.mean | 1 | 0.005122606541844821 rad/s | 0.005122606541844821 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_mean_rads.maximum | 1 | 0.004168558075714923 rad/s | 0.004168558075714923 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_mean_rads.mean | 1 | 0.003909863483393172 rad/s | 0.003909863483393172 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.hold_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.hold_speed_max_rads.maximum | 1 | 0.002825282407919618 rad/s | 0.002825282407919618 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_max_rads.mean | 1 | 0.0024815571219942525 rad/s | 0.0024815571219942525 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_mean_rads.maximum | 1 | 0.0022327360281204334 rad/s | 0.0022327360281204334 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_mean_rads.mean | 1 | 0.0019585631403563667 rad/s | 0.0019585631403563667 rad/s | 0.03490658503988659 rad/s | True |
| summary.peak_elevation_rad.maximum | 1 | 0.005663104216662607 rad | 0.005663104216662607 rad | 0.017453292519943295 rad | True |
| summary.peak_elevation_rad.mean | 1 | 0.004967694688559066 rad | 0.004967694688559066 rad | 0.017453292519943295 rad | True |
| summary.preceding_rest_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.preceding_rest_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_speed_max_rads.maximum | 1 | 0.005462390146160789 rad/s | 0.005462390146160789 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_max_rads.mean | 1 | 0.005122606541844821 rad/s | 0.005122606541844821 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_mean_rads.maximum | 1 | 0.0032388231031944548 rad/s | 0.0032388231031944548 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_mean_rads.mean | 1 | 0.003235147680026196 rad/s | 0.003235147680026196 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.return_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.return_speed_max_rads.maximum | 1 | 0.005497382412584906 rad/s | 0.005497382412584906 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_max_rads.mean | 1 | 0.005287510947409646 rad/s | 0.005287510947409646 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_mean_rads.maximum | 1 | 0.0036522743635521993 rad/s | 0.0036522743635521993 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_mean_rads.mean | 1 | 0.003512627572028637 rad/s | 0.003512627572028637 rad/s | 0.03490658503988659 rad/s | True |
| summary.rom_cv | 1 | 0.0003223947824390643 1 | 0.0003223947824390643 1 | 0.051216389244558264 1 | True |
| summary.rom_max_rad | 1 | 0.008733784319692184 rad | 0.008733784319692184 rad | 0.03490658503988659 rad | True |
| summary.rom_mean_rad | 1 | 0.008211040050722485 rad | 0.008211040050722485 rad | 0.03490658503988659 rad | True |
| summary.rom_rad.maximum | 1 | 0.008733784319692184 rad | 0.008733784319692184 rad | 0.03490658503988659 rad | True |
| summary.rom_rad.mean | 1 | 0.008211040050722485 rad | 0.008211040050722485 rad | 0.03490658503988659 rad | True |
| summary.rom_range_rad | 1 | 0.000808349086794502 rad | 0.000808349086794502 rad | 0.06981317007977318 rad | True |
| summary.rom_sd_rad | 1 | 0.0004533579171002297 rad | 0.0004533579171002297 rad | 0.06981317007977318 rad | True |
| summary.thorax_axial_rotation_magnitude_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_magnitude_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_max_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_max_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_min_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_min_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_magnitude_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_magnitude_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_max_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_max_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_min_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_min_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_magnitude_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_magnitude_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_max_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_max_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_min_rad.maximum | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_min_rad.mean | 1 | 0.0 rad | 0.0 rad | 0.017453292519943295 rad | True |

</details>

## T-MIX — flexion / left

[Machine result](replay/cases/Q-T-MIX/result.json); [derived](replay/cases/Q-T-MIX/derived.json.gz); [processed](replay/cases/Q-T-MIX/processed.json.gz).

Counts (repetitions, Derived; definition=m4-exercise-summary/1.0; valid=true; reason=['ok']; anatomical_eligible=false): detected_count=3; valid_count=3; excluded_count=0; partial_start_count=0; partial_end_count=0; interrupted_count=0; proxy_valid_count=3; proxy_unavailable_count=0

Truth/count comparison: `{"false": 0, "missed": 0, "truth": 3, "valid": 3}`. Coverage: `{"denominator_s": 16.5, "invalid_duration_s": 0.0, "proxy": 1.0, "recall": 1.0, "relative": 1.0, "valid_duration_s": 16.5}`.

Exclusion reasons: `{}`.

| Node | Packets / samples | QC issues | Calibration / AHRS | Source SHA-256 |
|---|---|---|---|---|
| A | 538 / 2151 | [] | True / True | `848ff4efcc35bfe66a98f09eb0208a49b2eaeb644f9c0a8144c0231ea2aa7ac3` |
| B | 538 / 2151 | [] | True / True | `4f759b2b564cf2930dbee8c636af7937df8377541a4fd7901e7568107af02999` |

Eight core families: humerothoracic ROM; peak elevation; repetition count; movement/phase duration; hold duration; angular velocity; rep-to-rep variability; thorax compensation excursion proxy.

Aggregate definition: `m4-exercise-summary/1.0`. Each stratum retains its own denominator.

| Core family | Result |
|---|---|
| Humerothoracic ROM, mean | n=3: 80.573539 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Peak elevation, mean | n=3: 90.275881 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Repetition count | 3 valid / 3 detected; 0 excluded; Derived; valid=True; reason=['ok']; anatomical_eligible=false |
| Movement / elevation / return duration | n=3: 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Hold duration | n=3: 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Angular velocity, mean / peak | n=3: 0.666376 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 1.052383 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Rep-to-rep variability, range / SD / CV (n=3) | 0.045881 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.026038 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.000323 dimensionless; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| Thorax proxy magnitude, extension / lateral flexion / axial rotation | n=3: 7.720888 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 2.478406 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / n=3: 3.935747 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

<details>
<summary>All metric strata, repetition phases, proxy extrema and gate errors</summary>

| Metric | n | Mean | Maximum |
|---|---:|---|---|
| elevation_duration_s | 3 | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 3 | 1.052383 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.052763 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 3 | 1.051072 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.051366 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 3 | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 3 | 0.002393 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.002756 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 3 | 0.001888 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.002174 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 3 | 90.275881 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 90.316277 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 2 | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3 | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 3 | 1.052383 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.052763 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 3 | 0.666376 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.666393 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 3 | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 3 | 0.790880 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.791083 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 3 | 0.788984 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.789117 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 3 | 80.573539 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 80.603591 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_magnitude_rad | 3 | 3.935747 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 3.935886 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_max_rad | 3 | 3.935747 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 3.935886 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_axial_rotation_min_rad | 3 | -0.594706 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | -0.594682 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_magnitude_rad | 3 | 7.720888 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 7.722996 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_max_rad | 3 | 7.720888 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 7.722996 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_extension_min_rad | 3 | -1.184144 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | -1.180097 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_magnitude_rad | 3 | 2.478406 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 2.478789 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_max_rad | 3 | 0.380696 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | 0.382691 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| thorax_lateral_flexion_min_rad | 3 | -2.478406 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | -2.477689 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

| Variability | Value |
|---|---|
| rom_range (n=3) | 0.045881 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_sd (n=3) | 0.026038 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_cv (n=3) | 0.000323 dimensionless; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Per-repetition phase support and validity (definition=['m4-exercise/1.0', 'm3-long-axis-elevation/1.0', 'm3-relative-angular-speed/1.0']); all original boundaries and hold runs remain in machine data.

Rep 1: valid=True, reason=['ok']; start/peak/end_us=5340000/6500000/9280000; rise=[5340000, 6500000]; return=[6500000, 9280000]; hold_runs_us=[[6500000, 7500000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.051701 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.050548 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002756 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.002174 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.316277 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | unavailable (rest_interrupted); valid=false; reason=rest_interrupted; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.051701 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666355 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.791083 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.789117 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.603591 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Rep 2: valid=True, reason=['ok']; start/peak/end_us=10840000/12000000/14780000; rise=[10840000, 12000000]; return=[12000000, 14780000]; hold_runs_us=[[12000000, 13000000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.052687 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.051303 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002228 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.001758 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.256895 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.052687 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666381 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790783 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.788918 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.559317 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Rep 3: valid=True, reason=['ok']; start/peak/end_us=16340000/17500000/20280000; rise=[16340000, 17500000]; return=[17500000, 20280000]; hold_runs_us=[[17500000, 18500000]]; partial_start=False; partial_end=False; interrupted=False.

| Rep metric | Value |
|---|---|
| elevation_duration_s | 1.160000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_max_rads | 1.052763 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| elevation_speed_mean_rads | 1.051366 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_duration_s | 1.000000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_max_rads | 0.002196 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| hold_speed_mean_rads | 0.001731 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| peak_elevation_rad | 90.254472 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| preceding_rest_duration_s | 1.560000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_duration_s | 3.940000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_max_rads | 1.052763 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rep_speed_mean_rads | 0.666393 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_duration_s | 1.780000 s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_max_rads | 0.790774 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| return_speed_mean_rads | 0.788917 rad/s; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |
| rom_rad | 80.557710 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false |

Thorax proxy definition/policy: `['m4-thorax-excursion/1.0', 'm4-thorax-common-grid/1.0', 'm4-thorax-preparation/1.0', 'slerp', ['known synthetic heading', 'supported'], ['known injected yaw bound over evaluation window', 'supported']]`; independent proxy denominator and heading/drift limits apply.

| Rep / component | Min / max / magnitude (deg) | Validity / evidence |
|---|---|---|
| 1 / extension | -1.191556 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 7.717025 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 7.717025 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 1 / lateral_flexion | -2.477689 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.382691 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 2.477689 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 1 / axial_rotation | -0.594752 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 3.935886 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 3.935886 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / extension | -1.180780 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 7.722643 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 7.722643 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / lateral_flexion | -2.478740 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.379758 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 2.478740 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 2 / axial_rotation | -0.594684 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 3.935681 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 3.935681 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / extension | -1.180097 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 7.722996 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 7.722996 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / lateral_flexion | -2.478789 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 0.379640 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 2.478789 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |
| 3 / axial_rotation | -0.594682 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 3.935676 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false / 3.935676 deg; valid=true; reason=ok; evidence=Derived; anatomical_eligible=false | reasons=[] |

Independent error supports and unchanged gate budgets:

| Gate quantity | n | Maximum absolute error | RMSE | Tolerance | Gate |
|---|---:|---|---|---|---|
| A.initialization | 2 | 2.220446049250313e-16 rad | 1.5700924586837752e-16 rad | 0.006981317007977318 rad | True |
| A.orientation | 1651 | 0.0006462048529307916 rad | 0.00035506171823227486 rad | 0.006981317007977318 rad | True |
| B.initialization | 2 | 2.220446049250313e-16 rad | 1.5700924586837752e-16 rad | 0.006981317007977318 rad | True |
| B.orientation | 1651 | 0.0061434053833784325 rad | 0.003330495950936241 rad | 0.006981317007977318 rad | True |
| T-MIX:rep-1.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| T-MIX:rep-1.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-1.elevation_speed_max_rads | 1 | 0.004502995205457161 rad/s | 0.004502995205457161 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-1.elevation_speed_mean_rads | 1 | 0.003350633405986514 rad/s | 0.003350633405986514 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-1.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-1.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-1.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-1.hold_speed_max_rads | 1 | 0.002756335377933405 rad/s | 0.002756335377933405 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-1.hold_speed_mean_rads | 1 | 0.0021739147451651 rad/s | 0.0021739147451651 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-1.peak_elevation_rad | 1 | 0.005520077999633166 rad | 0.005520077999633166 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-1.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| T-MIX:rep-1.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| T-MIX:rep-1.proxy.axial_rotation.magnitude_rad | 1 | 1.8953589809828086e-05 rad | 1.8953589809828086e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy.axial_rotation.max_rad | 1 | 1.8953589809828086e-05 rad | 1.8953589809828086e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy.axial_rotation.min_rad | 1 | 4.187570335898415e-05 rad | 4.187570335898415e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy.extension.magnitude_rad | 1 | 0.0004308184666012571 rad | 0.0004308184666012571 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy.extension.max_rad | 1 | 0.0004308184666012571 rad | 0.0004308184666012571 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy.extension.min_rad | 1 | 0.0005587126640399752 rad | 0.0005587126640399752 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy.lateral_flexion.magnitude_rad | 1 | 0.00014144528644075005 rad | 0.00014144528644075005 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy.lateral_flexion.max_rad | 1 | 0.00016600329084367604 rad | 0.00016600329084367604 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy.lateral_flexion.min_rad | 1 | 0.00014144528644075005 rad | 0.00014144528644075005 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 1.8953589809828086e-05 rad | 1.8953589809828086e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy_estimated_support.axial_rotation.max_rad | 1 | 1.8953589809828086e-05 rad | 1.8953589809828086e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy_estimated_support.axial_rotation.min_rad | 1 | 4.187570335898415e-05 rad | 4.187570335898415e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0004308184666012571 rad | 0.0004308184666012571 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy_estimated_support.extension.max_rad | 1 | 0.0004308184666012571 rad | 0.0004308184666012571 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy_estimated_support.extension.min_rad | 1 | 0.0005587126640399752 rad | 0.0005587126640399752 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.00014144528644075005 rad | 0.00014144528644075005 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.00016600329084367604 rad | 0.00016600329084367604 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.00014144528644075005 rad | 0.00014144528644075005 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-1.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-1.rep_speed_max_rads | 1 | 0.004502995205457161 rad/s | 0.004502995205457161 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-1.rep_speed_mean_rads | 1 | 0.0032181810824916113 rad/s | 0.0032181810824916113 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-1.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-1.return_speed_max_rads | 1 | 0.005684868227145312 rad/s | 0.005684868227145312 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-1.return_speed_mean_rads | 1 | 0.003718530319610891 rad/s | 0.003718530319610891 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-1.rom_rad | 1 | 0.008789315209804194 rad | 0.008789315209804194 rad | 0.03490658503988659 rad | True |
| T-MIX:rep-1.speed_estimated_mean | 1 | 0.0032181810824917223 rad/s | 0.0032181810824917223 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-1.speed_nominal_mean | 1 | 0.0032181810824917223 rad/s | 0.0032181810824917223 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-1.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-1.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-2.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| T-MIX:rep-2.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-2.elevation_speed_max_rads | 1 | 0.005489676329684334 rad/s | 0.005489676329684334 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-2.elevation_speed_mean_rads | 1 | 0.00410524185137362 rad/s | 0.00410524185137362 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-2.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-2.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-2.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-2.hold_speed_max_rads | 1 | 0.0022282468661298715 rad/s | 0.0022282468661298715 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-2.hold_speed_mean_rads | 1 | 0.001757537625674063 rad/s | 0.001757537625674063 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-2.peak_elevation_rad | 1 | 0.004483659098004633 rad | 0.004483659098004633 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-2.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| T-MIX:rep-2.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| T-MIX:rep-2.preceding_rest_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-2.proxy.axial_rotation.magnitude_rad | 1 | 1.539094408162245e-05 rad | 1.539094408162245e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy.axial_rotation.max_rad | 1 | 1.539094408162245e-05 rad | 1.539094408162245e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy.axial_rotation.min_rad | 1 | 4.30660374493904e-05 rad | 4.30660374493904e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy.extension.magnitude_rad | 1 | 0.0005288603152483196 rad | 0.0005288603152483196 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy.extension.max_rad | 1 | 0.0005288603152483196 rad | 0.0005288603152483196 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy.extension.min_rad | 1 | 0.0003706324642128861 rad | 0.0003706324642128861 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy.lateral_flexion.magnitude_rad | 1 | 0.00015979301769417087 rad | 0.00015979301769417087 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy.lateral_flexion.max_rad | 1 | 0.00011481401776377697 rad | 0.00011481401776377697 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy.lateral_flexion.min_rad | 1 | 0.00015979301769417087 rad | 0.00015979301769417087 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 1.539094408162245e-05 rad | 1.539094408162245e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy_estimated_support.axial_rotation.max_rad | 1 | 1.539094408162245e-05 rad | 1.539094408162245e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy_estimated_support.axial_rotation.min_rad | 1 | 4.30660374493904e-05 rad | 4.30660374493904e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0005288603152483196 rad | 0.0005288603152483196 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy_estimated_support.extension.max_rad | 1 | 0.0005288603152483196 rad | 0.0005288603152483196 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy_estimated_support.extension.min_rad | 1 | 0.0003706324642128861 rad | 0.0003706324642128861 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.00015979301769417087 rad | 0.00015979301769417087 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.00011481401776377697 rad | 0.00011481401776377697 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.00015979301769417087 rad | 0.00015979301769417087 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-2.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-2.rep_speed_max_rads | 1 | 0.005489676329684334 rad/s | 0.005489676329684334 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-2.rep_speed_mean_rads | 1 | 0.0032448036088810195 rad/s | 0.0032448036088810195 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-2.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-2.return_speed_max_rads | 1 | 0.0053845964821807035 rad/s | 0.0053845964821807035 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-2.return_speed_mean_rads | 1 | 0.0035196112616429076 rad/s | 0.0035196112616429076 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-2.rom_rad | 1 | 0.008016590140987656 rad | 0.008016590140987656 rad | 0.03490658503988659 rad | True |
| T-MIX:rep-2.speed_estimated_mean | 1 | 0.0032448036088811305 rad/s | 0.0032448036088811305 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-2.speed_nominal_mean | 1 | 0.0032448036088811305 rad/s | 0.0032448036088811305 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-2.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-2.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-3.earliest_peak | 1 | 0.0 us | 0.0 us | 50000 us | False |
| T-MIX:rep-3.elevation_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-3.elevation_speed_max_rads | 1 | 0.005565020343795579 rad/s | 0.005565020343795579 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-3.elevation_speed_mean_rads | 1 | 0.0041686796629418765 rad/s | 0.0041686796629418765 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-3.end_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-3.end_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-3.hold_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-3.hold_speed_max_rads | 1 | 0.002195712375477121 rad/s | 0.002195712375477121 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-3.hold_speed_mean_rads | 1 | 0.0017311913466931245 rad/s | 0.0017311913466931245 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-3.peak_elevation_rad | 1 | 0.004441366189999574 rad | 0.004441366189999574 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.peak_support | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-3.phase_conservation | 1 | 0.0 s | 0.0 s | 1e-12 s | True |
| T-MIX:rep-3.plane_fraction | 1 | 0.0 1 | 0.0 1 | 0.02 1 | True |
| T-MIX:rep-3.preceding_rest_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-3.proxy.axial_rotation.magnitude_rad | 1 | 1.528826104843506e-05 rad | 1.528826104843506e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy.axial_rotation.max_rad | 1 | 1.528826104843506e-05 rad | 1.528826104843506e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy.axial_rotation.min_rad | 1 | 4.3092150345314106e-05 rad | 4.3092150345314106e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy.extension.magnitude_rad | 1 | 0.0005350209974633591 rad | 0.0005350209974633591 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy.extension.max_rad | 1 | 0.0005350209974633591 rad | 0.0005350209974633591 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy.extension.min_rad | 1 | 0.000358723147025064 rad | 0.000358723147025064 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy.lateral_flexion.magnitude_rad | 1 | 0.00016063871251545403 rad | 0.00016063871251545403 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy.lateral_flexion.max_rad | 1 | 0.00011275480368936035 rad | 0.00011275480368936035 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy.lateral_flexion.min_rad | 1 | 0.00016063871251545403 rad | 0.00016063871251545403 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy_estimated_support.axial_rotation.magnitude_rad | 1 | 1.528826104843506e-05 rad | 1.528826104843506e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy_estimated_support.axial_rotation.max_rad | 1 | 1.528826104843506e-05 rad | 1.528826104843506e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy_estimated_support.axial_rotation.min_rad | 1 | 4.3092150345314106e-05 rad | 4.3092150345314106e-05 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy_estimated_support.extension.magnitude_rad | 1 | 0.0005350209974633591 rad | 0.0005350209974633591 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy_estimated_support.extension.max_rad | 1 | 0.0005350209974633591 rad | 0.0005350209974633591 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy_estimated_support.extension.min_rad | 1 | 0.000358723147025064 rad | 0.000358723147025064 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy_estimated_support.lateral_flexion.magnitude_rad | 1 | 0.00016063871251545403 rad | 0.00016063871251545403 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy_estimated_support.lateral_flexion.max_rad | 1 | 0.00011275480368936035 rad | 0.00011275480368936035 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.proxy_estimated_support.lateral_flexion.min_rad | 1 | 0.00016063871251545403 rad | 0.00016063871251545403 rad | 0.017453292519943295 rad | True |
| T-MIX:rep-3.rep_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-3.rep_speed_max_rads | 1 | 0.005565020343795579 rad/s | 0.005565020343795579 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-3.rep_speed_mean_rads | 1 | 0.0032564283005841466 rad/s | 0.0032564283005841466 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-3.return_duration_s | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| T-MIX:rep-3.return_speed_max_rads | 1 | 0.005376018793626258 rad/s | 0.005376018793626258 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-3.return_speed_mean_rads | 1 | 0.0035188021059526786 rad/s | 0.0035188021059526786 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-3.rom_rad | 1 | 0.007988543307595242 rad | 0.007988543307595242 rad | 0.03490658503988659 rad | True |
| T-MIX:rep-3.speed_estimated_mean | 1 | 0.0032564283005839245 rad/s | 0.0032564283005839245 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-3.speed_nominal_mean | 1 | 0.0032564283005839245 rad/s | 0.0032564283005839245 rad/s | 0.03490658503988659 rad/s | True |
| T-MIX:rep-3.start_confirmation | 1 | 0.0 us | 0.0 us | 50000 us | True |
| T-MIX:rep-3.start_us | 1 | 0.0 us | 0.0 us | 50000 us | True |
| elevation | 1651 | 0.005520077999633166 rad | 0.002912821244607269 rad | 0.017453292519943295 rad | True |
| interval_speed | 1650 | 0.006414761173685557 rad/s | 0.0033105193018093484 rad/s | 0.03490658503988659 rad/s | True |
| summary.active_s | 1 | 0.0 s | 0.0 s | 0.30000000000000004 s | True |
| summary.cadence_per_s | 1 | 0.0 s^-1 | 0.0 s^-1 | 0.006609560067681895 s^-1 | True |
| summary.elevation_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.elevation_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.elevation_speed_max_rads.maximum | 1 | 0.005565020343795579 rad/s | 0.005565020343795579 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_max_rads.mean | 1 | 0.005185897292979025 rad/s | 0.005185897292979025 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_mean_rads.maximum | 1 | 0.0041686796629418765 rad/s | 0.0041686796629418765 rad/s | 0.03490658503988659 rad/s | True |
| summary.elevation_speed_mean_rads.mean | 1 | 0.003874851640100818 rad/s | 0.003874851640100818 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.hold_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.hold_speed_max_rads.maximum | 1 | 0.002756335377933405 rad/s | 0.002756335377933405 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_max_rads.mean | 1 | 0.002393431539846799 rad/s | 0.002393431539846799 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_mean_rads.maximum | 1 | 0.0021739147451651 rad/s | 0.0021739147451651 rad/s | 0.03490658503988659 rad/s | True |
| summary.hold_speed_mean_rads.mean | 1 | 0.001887547905844096 rad/s | 0.001887547905844096 rad/s | 0.03490658503988659 rad/s | True |
| summary.peak_elevation_rad.maximum | 1 | 0.005520077999633166 rad | 0.005520077999633166 rad | 0.017453292519943295 rad | True |
| summary.peak_elevation_rad.mean | 1 | 0.004815034429212384 rad | 0.004815034429212384 rad | 0.017453292519943295 rad | True |
| summary.preceding_rest_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.preceding_rest_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.rep_speed_max_rads.maximum | 1 | 0.005565020343795579 rad/s | 0.005565020343795579 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_max_rads.mean | 1 | 0.005185897292979025 rad/s | 0.005185897292979025 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_mean_rads.maximum | 1 | 0.0032564283005841466 rad/s | 0.0032564283005841466 rad/s | 0.03490658503988659 rad/s | True |
| summary.rep_speed_mean_rads.mean | 1 | 0.003239804330652296 rad/s | 0.003239804330652296 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_duration_s.maximum | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.return_duration_s.mean | 1 | 0.0 s | 0.0 s | 0.1 s | True |
| summary.return_speed_max_rads.maximum | 1 | 0.005684868227145312 rad/s | 0.005684868227145312 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_max_rads.mean | 1 | 0.005481827834317499 rad/s | 0.005481827834317499 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_mean_rads.maximum | 1 | 0.003718530319610891 rad/s | 0.003718530319610891 rad/s | 0.03490658503988659 rad/s | True |
| summary.return_speed_mean_rads.mean | 1 | 0.0035856478957354554 rad/s | 0.0035856478957354554 rad/s | 0.03490658503988659 rad/s | True |
| summary.rom_cv | 1 | 0.00032315609691781856 1 | 0.00032315609691781856 1 | 0.051216389244558264 1 | True |
| summary.rom_max_rad | 1 | 0.008789315209804194 rad | 0.008789315209804194 rad | 0.03490658503988659 rad | True |
| summary.rom_mean_rad | 1 | 0.008264816219462512 rad | 0.008264816219462512 rad | 0.03490658503988659 rad | True |
| summary.rom_rad.maximum | 1 | 0.008789315209804194 rad | 0.008789315209804194 rad | 0.03490658503988659 rad | True |
| summary.rom_rad.mean | 1 | 0.008264816219462512 rad | 0.008264816219462512 rad | 0.03490658503988659 rad | True |
| summary.rom_range_rad | 1 | 0.0008007719022089521 rad | 0.0008007719022089521 rad | 0.06981317007977318 rad | True |
| summary.rom_sd_rad | 1 | 0.00045444587066892215 rad | 0.00045444587066892215 rad | 0.06981317007977318 rad | True |
| summary.thorax_axial_rotation_magnitude_rad.maximum | 1 | 1.8953589809828086e-05 rad | 1.8953589809828086e-05 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_magnitude_rad.mean | 1 | 1.6544264979961865e-05 rad | 1.6544264979961865e-05 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_max_rad.maximum | 1 | 1.8953589809828086e-05 rad | 1.8953589809828086e-05 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_max_rad.mean | 1 | 1.6544264979961865e-05 rad | 1.6544264979961865e-05 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_min_rad.maximum | 1 | 4.3092150345236044e-05 rad | 4.3092150345236044e-05 rad | 0.017453292519943295 rad | True |
| summary.thorax_axial_rotation_min_rad.mean | 1 | 4.267796371789853e-05 rad | 4.267796371789853e-05 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_magnitude_rad.maximum | 1 | 0.0005350209974633591 rad | 0.0005350209974633591 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_magnitude_rad.mean | 1 | 0.0004982332597709971 rad | 0.0004982332597709971 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_max_rad.maximum | 1 | 0.0005350209974633591 rad | 0.0005350209974633591 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_max_rad.mean | 1 | 0.0004982332597709971 rad | 0.0004982332597709971 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_min_rad.maximum | 1 | 0.00035872314702520974 rad | 0.00035872314702520974 rad | 0.017453292519943295 rad | True |
| summary.thorax_extension_min_rad.mean | 1 | 0.00042935609175931075 rad | 0.00042935609175931075 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_magnitude_rad.maximum | 1 | 0.00016063871251545403 rad | 0.00016063871251545403 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_magnitude_rad.mean | 1 | 0.00015395900555012498 rad | 0.00015395900555012498 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_max_rad.maximum | 1 | 0.00016600329084362746 rad | 0.00016600329084362746 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_max_rad.mean | 1 | 0.0001311907040989378 rad | 0.0001311907040989378 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_min_rad.maximum | 1 | 0.00014144528644075005 rad | 0.00014144528644075005 rad | 0.017453292519943295 rad | True |
| summary.thorax_lateral_flexion_min_rad.mean | 1 | 0.00015395900555012498 rad | 0.00015395900555012498 rad | 0.017453292519943295 rad | True |

</details>

## Limits

- Synthetic stored sensor observations; anatomical_eligible=false; INTERNAL ONLY / redistribution pending.
- Known calibration, initialization, alignment, heading and clock are Assumed construction conditions.
- Static gravity does not determine full heading; independent AHRS worlds cannot be composed automatically.
- Humerothoracic metrics and thorax excursion proxy; no clinical, glenohumeral or scapular validation.
- Four different exercise/side trajectories are not longitudinal rehabilitation outcomes.
- Repository clone required; wheel-only demo, Linux execution and performance acceptance are not established.
