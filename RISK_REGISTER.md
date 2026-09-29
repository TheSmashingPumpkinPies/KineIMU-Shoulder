# Risk Register — KineIMU Shoulder

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
