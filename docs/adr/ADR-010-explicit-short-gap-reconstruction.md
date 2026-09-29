# ADR-010 — Explicit gravity-supported short-gap reconstruction

Status: Accepted by explicit maintainer instruction on 2026-09-27.

## Context

M5.3 formal4 failed 46 cases: 39 numerical loss/jitter gates, one roundoff
endpoint exclusion and six unresolved evidence references. A missing sharp
rate transition defeats the frozen 10 ms SLERP speed target even with perfect
retained orientations. The maintainer explicitly authorized a new processing
contract, correction of missing-sample integration/velocity support and M2–M5
reacceptance, preserving all raw data, seeds and numerical thresholds.

## Decision

Adopt [M5 processing/1.1](../../protocols/M5_PROCESSING_V1_1.md). Add an explicit
processed reconstruction stage between calibrated node-frame observations and
the unchanged pinned imufusion AHRS. The local model uses one collinear rate
transition supported by observed gravity displacement and neighboring rate
branches; it never accesses labels, nominal knots or deleted samples.
SciPy Rotation performs all rotations. Estimated rows retain original brackets,
times, fit residuals and model assumptions; all original rows/counters survive.
Yaw-only or unsupported dynamics are not reconstructed.

Resolve map/heading reference hashes against independently retained sources
and remove only machine-precision clock roundoff at integer endpoints.
No acquisition schema, frame convention, metric definition, hardware or
dependency version changes. No speed support is removed or relabelled; all
original 10 ms comparison gates and loss/coverage/count denominators remain.

## Consequences and acceptance

This is a declared offline model with synthetic numerical validation, not a
claim of arbitrary real-sensor missing-motion recovery or anatomical heading.
New pipeline provenance invalidates pooling with old processing. Preserve old
CP0/CP1/CP2/formal4 and partial artifacts; two fresh committed-lock 1142-case
runs, byte equality, independent reconstruction/support/error audit and full
M2–M5 regressions are required before accepting CP3. CP4/CP5 remain separate.
