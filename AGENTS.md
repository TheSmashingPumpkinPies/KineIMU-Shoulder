# KineIMU Shoulder contributor instructions

Read PROJECT_SCOPE.md, ARCHITECTURE.md, DATA_FORMAT.md, DEPENDENCIES.md and
ACCEPTANCE_CRITERIA.md before editing; hardware work also requires HARDWARE_PROFILE.md,
MOUNTING_PROTOCOL.md and THIRD_PARTY_COMPATIBILITY.md. Explicit maintainer decisions,
these contracts and accepted ADRs govern changes; historical evidence is informative.

Shoulder-only V1. Raw data and frozen benchmark evidence are immutable. Use SI units,
normalized quaternions and explicit frames/timing internally. Keep validation separate
from production and backend conversions in adapters. New algorithms need written
rationale and known-input tests. Do not infer anatomical heading from gravity or claim
glenohumeral/scapular/clinical measurements. Public schema changes need maintainer approval.
Hardware remains frozen unless an acquisition defect justifies reopening it.

Run pytest, ruff check ., mypy and scripts/check_docs_consistency.py for Python work.
Firmware changes require reference-board compilation and relevant timing evidence.
Before handoff record the commit, verification and exact next action in the PR; private
source-development handoff files are intentionally absent from this public repository.
Use small reviewable commits. Never add credentials, identifiable human data, local
SDKs or generated environments. Follow PUBLIC_EXPORT.json for immutable members and
LICENSE/THIRD_PARTY_NOTICES.md for the applicable per-file license boundaries.
