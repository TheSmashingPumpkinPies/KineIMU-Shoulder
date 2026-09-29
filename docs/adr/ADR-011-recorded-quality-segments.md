# ADR-011 — Explicit recorded quality partition and AHRS restart

Status: Accepted by explicit maintainer instruction on 2026-09-27.

## Context

The first complete M5.4 D attempt correctly rejected original B observation
23297: GYRO_CLIPPED and -509.04 deg/s X rate outside the configured 500 deg/s
calibration gate. Raw evidence and the failed attempt are immutable. The
maintainer reviewed the proposed null-row/independent-world consequences and
explicitly approved adopting the segmented scheme.

## Decision

Adopt [m5-recorded-segments/1.0](../../protocols/M5_RECORDED_SEGMENTS_V1.md)
as an explicit validation-only recorded D option. Preserve every original row
and reason. Apply unchanged calibration and fresh unchanged pinned AHRS to
each maximal contiguous eligible interval. Export null processed values at
ineligible observations and a different arbitrary world per restart.
Do not bridge, reconstruct or compare across rejected rows/worlds.

## Consequences and reacceptance

Independent orientation reference continuity is lost across the bad point.
Startup identity is assumed, not recovered physical orientation. Source-quality
handling does not establish a firmware/acquisition defect or reopen frozen M1.
Strict existing processing, synthetic truth/seeds/gates and public schemas are
unchanged. Reaccept D with targeted tests, full Python checks, a new clean-lock
complete retained-input replay and independent partition/quaternion/null audit.
Preserve the original failed root/auditor; CP0–CP3 remain accepted. E and CP5
remain separate, and no shoulder-accuracy or clinical acceptance is inferred.
