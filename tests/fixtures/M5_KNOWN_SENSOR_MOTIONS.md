# M5 Independent Known Sensor Motions — CP0 Truth Freeze

Frozen 2026-09-26, before M5 numerical implementation. Contract:
[m5-validation/1.0](../../protocols/M5_VALIDATION_CONTRACT.md).
These scalar/matrix derivations are the independent reference, not stored
production outputs. Degrees below are explanatory; multiply by pi/180 to
store radians, by 1000000 to store integer microseconds. All sources synthetic.

## Fixed axes and observation anchors (O0–O7)

Use the usual analytic matrices Rx, Ry, Rz with positive right-hand angles:

```text
Rx(a) = [[1,0,0],[0,cos(a),-sin(a)],[0,sin(a),cos(a)]]
Ry(b) = [[cos(b),0,sin(b)],[0,1,0],[-sin(b),0,cos(b)]]
Rz(c) = [[cos(c),-sin(c),0],[sin(c),cos(c),0],[0,0,1]]
qX(a) = [cos(a/2),sin(a/2),0,0]  (analogously Y,Z)
```

Default nontrivial axes:
R_NS,A=Rz(90°), R_NT=Rx(90°);
R_NS,B=Rx(-90°), R_NH=Ry(90°). Sensor origins and force model follow the
contract. At neutral R_WT=R_WH=I, so R_WS,A=Rx(-90°)Rz(90°),
R_WS,B=Ry(-90°)Rx(-90°). Then f_S,A=(-g,0,0), f_S,B=(+g,0,0).
Initial q_WN,A=qX(-90°), q_WN,B=qY(-90°); align once to return neutral.

| ID | Independent construction | Exact expectation / purpose |
|---|---|---|
| O0 | Identity axes stationary | f=(0,0,+9.80665), omega=0, q=identity; gravity sign |
| O1 | Neutral with default axes above | Force vectors above; both aligned segments identity; nontrivial transformations |
| O2 | Pure flexion R_TH=Ry(-e), thorax fixed | u=(-sin(e),0,cos(e)); omega_H=(0,-de/dt,0); default B sensor omega=(0,0,-de/dt) |
| O3 | Left abduction Rx(+e), thorax fixed | u=(0,-sin(e),cos(e)); omega_H=(+de/dt,0,0); B sensor omega=(0,+de/dt,0) |
| O4 | Right abduction Rx(-e), thorax fixed | u=(0,+sin(e),cos(e)); O3 gyro sign reverses; same unsigned elevation |
| O5 | Body rate versus world rate | R_WS^T*dR_WS/dt skew elements yield sensor omega; cannot substitute world Euler derivatives |
| O6 | Default axes plus C-APPLY parameters | M(f_raw-b_a)=f_S and omega_raw-b_g=omega_S componentwise; then R_NS, then AHRS, then R_NK once |
| O7 | Packet Q | r=round_even(value/LSB), reconstructed error <=half LSB; original times/seq unchanged; no hidden resampling |

O1 anchors derive directly by tracing world +Z backwards: A Rx(+90°) maps
+Z to -Y, Rz(-90°) maps -Y to -X; B Ry(+90°) maps +Z to +X and Rx(+90°)
leaves +X. The full sensor composition R_WS,B^T=Rx(+90°)Ry(+90°)
therefore gives (+g,0,0).
For O2 body H -Y maps via R_NS^T R_NH to sensor -Z;
therefore sensor rate is (0,0,-de/dt). For O3 H +X maps through Ry(90°)
to node -Z, then Rx(+90°) to sensor +Y, so sensor rate is
(0,+de/dt,0). These traces independently verify O2/O3 table signs.

## Continuous elementary trajectory and nominal M4 oracle

Session begins with 5 s independent stationary calibration/warmup. At s>=5,
an elementary cycle with peak P radians, rise Tr, plateau Ht, return Tf and
quiet tail R has physical support [s,s+Tr+Ht+Tf] and ends at
s+Tr+Ht+Tf+R. All times in the baseline are on the 0.01 s grid.

```text
e(t)=0                                      t<=s
e(t)=P*(t-s)/Tr                             s<t<=s+Tr
e(t)=P                                      s+Tr<t<=s+Tr+Ht
e(t)=P*(1-(t-s-Tr-Ht)/Tf)                    s+Tr+Ht<t<=s+Tr+Ht+Tf
e(t)=0                                      afterwards through quiet tail
```

The LEFT derivative at a knot supplies the interval-ending gyro observation:
rise at s+Tr, zero at plateau end, negative slope at return end. There is
no fictitious sample-0 integration. For the zero-plateau case Ht=0, the peak
sample takes rise rate and the next takes return rate. Half-open interval
ownership makes every scalar observation deterministic.

Thorax-fixed flexion/abduction vectors O2/O3/O4 give e exactly for 0<=e<=pi,
zero plane deviation, principal interval speed abs(delta_e)/observed_dt.
For dt=0.01 s, start/rest thresholds 20°/10° and the fixed M4 profile:

```text
ks=ceil(Tr*(20°/P)/dt);  kr=ceil(Tf*(1-10°/P)/dt)
start=s+ks*dt; peak=s+Tr; end=s+Tr+Ht+kr*dt
confirm_start=start+0.20; confirm_end=end+0.20
start_e=P*ks*dt/Tr; end_e=P*(1-kr*dt/Tf)
ROM=P-min(start_e,end_e); duration=end-start
rise_duration=Tr-ks*dt; return_duration=kr*dt; hold_duration=Ht if Ht>=0.5 else 0
```

The phase formula above assumes all ramps exceed the 5°/s hold limit and
Ht=0 or Ht>=0.5. For a short plateau, M4 retains no hold and that plateau
belongs to chronological return. Peak uses the earliest maximum.
Per-rep angular path L=(P-start_e)+(P-end_e); mean speed=L/duration,
max speed=max(P/Tr,P/Tf), hold mean/max=0 for retained plateau. Rise and
return means/maxima=P/Tr,P/Tf respectively when plateau is assigned to hold.
Closed M4 ROM differs from the full physical 0→P→0 excursion because end_e
is generally nonzero. All ceil operations use exact rational degree/time
values, never floating rounding of a production output.

## Frozen sessions (F0–F9)

Every session includes the initial [0,5] window; evaluation is [5,end] inclusive.
Each listed cycle has its own immutable truth ID in chronological order.
The preceding cycle's quiet tail arms the next cycle. Session IDs bind UTC
synthetic starts 2026-09-26T00:00:00Z, then +1 minute in table order; these
are declared metadata, not operational run timestamps.

| Trajectory / ID | Cycle profile and construction | Expected eligibility |
|---|---|---|
| QUIET / F0 | 30 s evaluation, e=0 throughout | 0 physical/0 detected/0 valid; summaries unavailable, not failed analysis |
| F90 / F1 | left flexion, 3 cycles P=90°,Tr=1.5,Ht=1,Tf=2,R=1; starts 5,10.5,16 s; end21.5 s | 3/3 valid; E/S baseline, primary scan |
| AL90 / F2 | F1 with left abduction Rx(+e) | same boundaries/metrics, positive X rotation |
| AR90 / F3 | F1 with right abduction Rx(-e) | same unsigned metrics, negative X rotation |
| VAR / F4 | left flexion cycles (P,Tr,Ht,Tf,R)=(70°,1,0.5,2,1),(80°,1.5,1,1,1),(90°,2,1.5,1.5,1) | 3 valid; sample SD/CV, unequal tempo/holds |
| NOHOLD / F5 | F1 cycles with Ht=0 | 3 valid, hold=0, no empty-time division |
| WRONG / F6 | F1's e, q_TH=Rx(-e), declared left abduction | 3 detected, 0 valid, 3 plane_mismatch; no relabel |
| PARTIAL / F7 | F1 cropped to [5.8,20] s, original warmup retained but analysis window explicitly cropped | first cycle partial_start, third partial_end, only second valid; physical truth IDs unchanged |
| T-EXT / F8 | F1 relative flexion; R_WT=Ry(-e/9), R_WH=R_WT Ry(-e) | same relative metrics, movement-start thorax extension truth below |
| T-MIX / F9 | F1 relative flexion; R_WT=Rz(e/18) Ry(-e/9) Rx(e/30), R_WH=R_WT Ry(-e) | noncommuting two-body sensor test; proxy matrix oracle below |
| F90L / F1L | F1 cycle repeated until evaluation 300 s, final cropped cycle retained as partial; end305 s | 54 complete cycles, last cycle partial_end (300/5.5=54+3/5.5) |
| F90-NEXT / U1 | F1 with P=100° all three cycles; start metadata later than F1, otherwise same context | comparison later-earlier from analytic means; no clinical interpretation |

F1 single cycle relative to s: start0.34, peak1.50, end4.28 s;
start/end confirmations [0.34,0.54]/[4.28,4.48]. start_e=20.4°,
end_e=9.9°, ROM80.1°, peak90°, duration3.94 s;
rise1.16, hold1.00, return1.78 s; path149.7°;
rep mean149.7/3.94 degrees/s, max60 degrees/s; rise60, return45,
hold0 degrees/s. Plane fraction1. Inter-rep rest1.56 s (10.84-9.28).
Three reps: mean/max ROM80.1°, range/SD/CV0, active time11.82 s,
cadence3/11.82 s^-1. Thorax-fixed proxy signed min/max/magnitude are all0.

F4 cycle starts 5,9.5,15 s, ends21 s. Independent per-cycle values:

| Cycle | Relative start/end/peak s | ROM / peak ° | Rise/hold/return / rep s |
|---|---|---|---|
| 70 | 0.29 / 3.22 / 1.00 | 60.2 / 70 | 0.71 / 0.50 / 1.72 / 2.93 |
| 80 | 0.38 / 3.38 / 1.50 | 70.4 / 80 | 1.12 / 1.00 / 0.88 / 3.00 |
| 90 | 0.45 / 4.84 / 2.00 | 80.4 / 90 | 1.55 / 1.50 / 1.34 / 4.39 |

F4 ROM mean=(60.2+70.4+80.4)/3 degrees; sample SD is
sqrt(sum((ROM_i-mean)^2)/2), CV=SD/mean; not population SD. Each speed
and rest comes from the equations, not a separately guessed fixture constant.
F1L complete physical support ends before305; the final cycle starts302 s
and has no observed confirmed return. Do not call the incomplete 55th cycle
a missed complete repetition. Comparison U1 uses the same ceil equations;
source hashes differ as lineage, all compatibility keys remain identical.

## Moving-thorax independent oracle (T0–T3)

T0 = F8. The commuting Y-axis construction has sensor body angular rates
from the derivative of R_WT and R_WH, not from relative gyro alone.
For a closed rep starting at e0=20.4°, D=Ry(-(e-e0)/9).
Hence extension=(e-e0)/9, lateral=axial=0. Peak extension is
(90-20.4)/9=7.733333333333333°, minimum at end is
(9.9-20.4)/9=-1.166666666666667°; magnitude7.733333333333333°.
This is excursion from M4 movement start, not the 10° world maximum.

T1 = F9. Let a=e/30,b=-e/9,c=e/18. Independent explicit matrix:

```text
R = [[cc*cb, cc*sb*sa-sc*ca, cc*sb*ca+sc*sa],
     [sc*cb, sc*sb*sa+cc*ca, sc*sb*ca-cc*sa],
     [-sb,   cb*sa,          cb*ca]]
sa=sin(a), ca=cos(a), sb=sin(b), cb=cos(b), sc=sin(c), cc=cos(c)
D_ij(t)=sum_k R_ki(start)*R_kj(t)
beta=asin(-D31), alpha=atan2(D32,D33), gamma=atan2(D21,D11)
extension=-beta; lateral=-alpha; axial=gamma
```

Compute these scalar equations at every included truth row; min/max include
baseline0; magnitude=max(abs(min),abs(max)). No shortcut subtracting the
three Euler components: rotations do not commute. Analytic body angular rate
for Rz(c)Ry(b)Rx(a) expressed in K is
(a'-c'*sin(b), b'*cos(a)+c'*sin(a)*cos(b),
-b'*sin(a)+c'*cos(a)*cos(b)). For H with R_WH=R_WT RE, body rate is
RE^T*omega_T+omega_E; then rotate by R_NK and R_NS^T to sensor axes.
Scalar matrix derivative provides an independent check of generator gyro.
All generated quaternions retain Hamilton order; oracle vectors/matrices do
not depend on that generator conversion helper.

T2 identity-heading invariance: multiply BOTH segment orientations on the
left by Rz(h(t)). Exact R_TH stays RE since Rz^T Rz=I. Drift/proxy evidence
remains a separate duration-specific gate, not evidence of drift-free worlds.
T3 differential yaw: A fixed, B world yaw h. For flexion,
u=(-sin(e)*cos(h),-sin(e)*sin(h),cos(e)); elevation stays e, declared flexion
plane deviation is abs(h) while abs(h)<pi; 3-D speed need not equal e'.
World-vertical yaw disturbance therefore tests observability/plane/proxy
without falsely assuming every yaw causes an elevation error.

## Perturbation and invalidity anchors (P0–P9, G0–G5)

The complete finite expansion, amplitudes and seeds are frozen in the contract.
The following anchors justify effects independently before running that matrix.

| ID | Reference / expected behavior |
|---|---|
| P0 noise | Clean true force/rate and labels remain unchanged; recorded zero-mean sigma is NOT measured hardware noise or a bound on every draw |
| P1 constant bias | Identity-axis stationary yaw rate b integrates h=b*t; gravity cannot observe h; 10 s at1°/s gives10° apparent yaw (M2 control retained) |
| P2 ramp bias | World-vertical ideal integration over duration T gives h(T)=b_end*T/2; sensor-Z cases depend on pose and are measured against original truth, not this shortcut |
| P3 actual jitter | Force/rate reevaluated at actual times; dt comes from retained times; timing bounds refer to nominal M4 annotations separately |
| P4 timestamp error | Observations stay at true times; claimed dt is wrong. Retain both, so a plausible result cannot erase timing error |
| P5 sample loss | Remove exact original indices, preserve seq gaps; peak-start deletion leaves plateau maxima but hold/boundary support may change |
| P6 packet loss | Delete an entire original four-sample packet; retained gap50ms for one packet,90ms for two; no renumbering; distinguish 1 packet vs4 samples |
| P7 affine clock | Correct inverse scale/offset recovers true times within1us rounding; wrong identity slope error approximately rho*t, separate from gyro/heading drift |
| P8 heading drift | Known bound abs(rate)*duration; 0.002°/s*300=.6° passes1°; .02°/s*300=6° fails proxy drift gate when A affected |
| P9 quantization | Half-LSB and norm bounds from the contract; quantized clean source is not ideal SI or real sensor evidence |
| G0 | 49999/50000 us gap allowed,50001 rejected for unsplit AHRS; E interpolation excludes long bracket instead |
| G1 | duplicate/reverse timestamps and NaN/Inf/zero acceleration: input errors; epoch reset explicit and no cross-epoch state |
| G2 | range/clipping flags: existing calibration rejection; CRC/hash/node failure: replay rejection; no metrics rescued |
| G3 | missing/wrong/expired/assumed clock/heading/alignment: exact M2/M3 reason or Assumed/Experimental, never stronger evidence |
| G4 | missing drift/trace, over-bound proxy, singularity, branch crossing: proxy-only unavailable with exact M4 reasons |
| G5 | zero/one rep, near-zero CV, incompatible comparisons, amplitude/time/plane/hold equality: retained exact M4 C/P/T/U fixtures; no S equality claim |

GAP irregular-grid cases and all evidence mutations must be manifest entries
before runs. Include reference valid matched controls and all seed rows.
M4 retains excluded fragments; valid metric-error denominators never erase
missing truth reps or unobserved duration. Stress cases cannot be relabelled W
after seeing output, and W failures cannot be excused as stress.

## Oracle readiness gate for CP1

Future tests cite these IDs and independently prove: O0/O1 gravity/sign,
O2–O4 handedness, O5/T1 derivative consistency, O6 calibration order,
O7/P9 count conversion; F1/F4 boundaries/interval ownership; T0 movement-start
proxy and T1 noncommutation; P6 loss sequence; P7 clocks; deterministic bytes.
At100/200 Hz compare independent analytic gyro to matrix central differences
away from knots: angular-rate component error <=1e-6 rad/s for a derivative
check step1e-5 s; mixed-axis integrated orientation error must decrease with
half dt (ratio <=0.75 unless both errors<1e-7 rad), and meet C at100Hz.
This is a fixture-tool verification, not a new production integrator.
Deliberate sign/composition/dt/counter mutation must break relevant tests;
zero-noise/bias/mask must reproduce the clean source and labels exactly.
CP0 freezes these expectations. No M5 generator or numerical acceptance
result exists merely because these equations and budgets are written.
