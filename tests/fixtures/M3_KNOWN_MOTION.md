# M3 Known-Motion Fixtures — independent CP0 expected values

Frozen 2026-09-25 before M3 numerical implementation. These are analytical
vector/rotation constructions, not outputs copied from production code. All
quaternions below are active Hamilton scalar-first; `Q_axis(θ)` means the
right-hand rotation about the named **positive** axis by θ degrees. Unless
stated, both nodes have exact synthetic identity alignments, supported known
clock/heading relations, valid M2 rows, and `max_sample_gap_us=500000`.
Fixture source type is `synthetic`; output is `Derived`, never human-validated.

| ID | Side; thorax/world and humerus/world construction | Independent analytical expectation |
|---|---|---|
| E0 | right; `R_WT=I`, `R_WH=I` | H +Z remains T +Z; elevation `0 rad`. |
| E1 | right flexion; `R_WT=I`, `R_WH=Q_Y(+90°)` | Right-hand Y rotation sends +Z to +X anterior; dot with T +Z is 0; elevation `π/2 rad`. |
| E2 | right abduction; `R_WT=I`, `R_WH=Q_X(+90°)` | +Z becomes −Y (rightward); elevation `π/2 rad`. |
| E3 | left abduction; `R_WT=I`, `R_WH=Q_X(−90°)` | +Z becomes +Y (leftward); elevation `π/2 rad`. |
| E4 | right; `R_WT=I`, `R_WH=Q_Y(+180°)` | +Z becomes −Z; elevation `π rad`. |
| E5 | right; `R_WT=Q_X(+60°)`, `R_WH=Q_Y(+45°)` | World axes are T +Z=`(0,−√3/2,1/2)` and H +Z=`(√2/2,0,√2/2)`; their dot is `√2/4`; relative elevation `acos(√2/4) ≈ 1.2094292028881888 rad` (not 45°). |
| E6 | right; replace any row's `q_TH` with `−q_TH` | The rotation matrix and elevation are identical to the original row. |

For speed fixtures, both endpoints are exact `q_TH`; time is common `µs`.
The known path between samples is supplied only to establish an expected
principal increment. The algorithm observes endpoints, not the path.

| ID | Common times and relative quaternions | Independent analytical expectation |
|---|---|---|
| S0 | `0,250000`; `I,I` | Principal increment 0; speed `0 rad/s`. |
| S1 | `0,250000`; `I,Q_Y(+30°)` | `(π/6 rad)/(1/4 s) = 2π/3 rad/s`. |
| S2 | `0,200000,700000`; `Q_Y(0°),Q_Y(20°),Q_Y(70°)` with declared gap 500000 µs | Increments 20°/0.2 s and 50°/0.5 s, each `5π/9 rad/s`; irregular time is essential. |
| S3 | same as S1, but second quaternion negated | Same `2π/3 rad/s`; quaternion sign has no motion content. |
| S4 | `0,500001`; `I,Q_Y(+30°)` | Invalid `sample_gap` under the 500000 µs limit; no numeric speed. |
| S5 | `0,250000`; first row valid, second M2-invalid `interpolation_gap` | Invalid `m2_invalid:interpolation_gap`; no numeric speed. |
| S6 | `0,250000`; known physical path `Q_Y(0°)→Q_Y(360°)` but endpoints `I,I` | Principal endpoint increment 0, computed speed 0; full revolution is aliased and cannot be inferred or called measured zero motion. |

For interval fixtures, elevations are supplied by the exact corresponding
`Q_Y(angle)` sequence; each listed time is a real grid member. The interval
is closed and includes both endpoints.

| ID | Common times µs; elevation angles; request | Independent analytical expectation |
|---|---|---|
| R0 | `0,200000,700000,1200000`; `0°,20°,70°,30°`; request `[0,1200000]` | max−min=`70°=7π/18 rad`; elapsed `1.2 s`; last angle is not the peak. |
| R1 | `0,100000,400000,900000`; `10°,65°,35°,50°`; request `[0,900000]` | max−min=`55°=11π/36 rad`; elapsed `0.9 s`, not 65° or a sample-count duration. |
| R2 | R0, request `[200000,700000]` | max−min=`50°=5π/18 rad`; elapsed `0.5 s`; excludes the neutral row. |
| R3 | R0, request `[200001,700000]` | Invalid `interval_endpoint_missing`; do not interpolate 200001 µs. |
| R4 | R0, request `[700000,200000]` | Invalid `interval_order`. |
| R5 | R0, request `[700000,700000]` | Invalid `interval_too_short`. |
| R6 | R0 with row at 700000 M2-invalid `interpolation_gap` | Entire `[0,1200000]` excluded as `interval_invalid_row`, retaining row/M2 reason. |
| R7 | `0,500001`; `0°,30°`; request `[0,500001]` | Entire interval excluded as `sample_gap`. |

Evidence fixtures apply to E/S/R alike: an absent/mismatched/expired alignment
blocks all numeric outputs; an absent clock map or heading relation blocks all
numeric outputs; an assumed alignment, clock map or heading produces
`Assumed/Experimental` while preserving source type and hashes. A physical M1
USB pair with no supported pairwise clock, common heading or measured
alignment is not a fixture for anatomical metric accuracy.
