# M1 single-node numerical integration smoke

This validation uses the retained physical Node B stationary record to check
that immutable raw counts and device timestamps can cross the host adapter and
reach the existing `imucal` and `imufusion` APIs. It is validation/report code
under `validation/`; the production count conversion is under
`kineimu_shoulder/io/m1_raw.py`.

## Reproduce

From the repository root, with the pinned environment synchronized:

```text
uv sync --all-extras --frozen
python -m validation.m1_single_node_smoke --config experiments/m1_single_node_smoke_20260915/config.json --output experiments/m1_single_node_smoke_20260915/result.json
```

The committed configuration pins the input path and expected SHA-256. The
runner also records the configuration hash, software commit, Python/backend
versions and exact command in `result.json`. It reads the `.kimu` file only;
the raw file is not rewritten.

## Selected evidence

- Record: `firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary.kimu`
- Record SHA-256:
  `1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201`
- Firmware evidence: `firmware/xiao_nrf52840_sense/evidence/node_b_20260913_compatibility.md`
- Firmware source commit: `87131b2d3b6931b3d8fd47b25740bf833f0af23b`
- Flashed UF2 SHA-256:
  `c782627573c07e099c092fc5b526181c22c8f7f35a8ca6c3c66dedd12360c9e7`
- Configuration: 104 Hz sensor ODR, ±4 g acceleration, ±500 °/s angular rate;
  raw register order X/Y/Z; timestamp source `mcu_drdy_isr`.

The result is recorded in [result.json](result.json). The current run is an
M1 input/interface compatibility result only. It does not claim M2 calibration
quality, heading/yaw validity, sensor-to-segment or anatomical alignment,
shoulder-joint angles, or clinical validity.
