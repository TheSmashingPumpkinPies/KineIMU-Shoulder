# Reproducibility and Provenance

Every formal experiment must be reproducible from a manifest.

## Experiment Manifest

Record at least:

``` json
{
  "dataset_id": "",
  "dataset_hash": "",
  "firmware_commit": "",
  "software_commit": "",
  "device_id": "",
  "calibration_id": "",
  "config_file": "",
  "annotation_version": "",
  "reference_method": ""
}
```

## Derived Results

Never manually edit benchmark numbers in README without a generated source artifact.

Preferred flow:

``` text
raw data
→ script
→ machine-readable result
→ figure/table
→ README/report
```

## Randomness

For ML/statistical workflows:

- record random seeds;
- record split IDs;
- never split adjacent windows from one session across train/test unless explicitly justified.

## Environment

Keep:

- `uv.lock`
- firmware toolchain version
- CI versions
- dependency matrix

Firmware platform spikes additionally keep source/module revisions, an environment freeze,
SDK distribution and installed-tree hashes, exact build commands, resource usage and generated
artifact hashes. The current M1 record is
[firmware/xiao_nrf52840_sense/README.md](firmware/xiao_nrf52840_sense/README.md).
