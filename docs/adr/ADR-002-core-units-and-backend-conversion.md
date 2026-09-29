# ADR-002: Core Units and Backend Conversion

- Status: Accepted
- Date: 2026-09-05

## Decision

Core units:

- acceleration: m/s²
- angular velocity: rad/s

Third-party adapters explicitly convert to backend-required units such as deg/s.

## Consequence

Backend conventions never redefine core semantics.
