# V1 evidence and hardware boundary

Status: Accepted. KineIMU Shoulder has a hardware-tested, software-complete V1
boundary: physical dual-IMU acquisition, immutable recordings, calibration/frame/
quaternion tests, humerothoracic metrics, deterministic synthetic and recorded
replay validation, a hardware-free demo, reproducible benchmark and license notices.
[Acceptance criteria](../../ACCEPTANCE_CRITERIA.md) define the gates.

Freeze hardware after M1 unless a documented firmware/acquisition defect blocks
the pipeline. Live BLE/USB, replay and synthetic inputs are peer backends; algorithms
operate on normalized data and explicit provenance independently of live hardware.

Battery, enclosure, wearability, human-subject studies, motion capture, patient and
clinical validation are outside V1. Unobservable fields stay not measured/inconclusive;
no fabricated metric or implicit schema rewrite. Always label synthetic evidence.
No validated wearable, anatomical ROM instrument, diagnostic or clinical outcome
claim follows from these engineering tests.
