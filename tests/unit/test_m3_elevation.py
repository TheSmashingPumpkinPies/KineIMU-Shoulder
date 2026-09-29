"""CP1 analytical long-axis elevation and evidence exclusions."""

from dataclasses import replace
from math import acos, cos, pi, sin, sqrt

import numpy as np
import pytest

from kineimu_shoulder.relative_orientation import ClockMap, HeadingRelation, RelativeOrientationResult
from kineimu_shoulder.shoulder import AlignmentRecord, long_axis_elevation

SHA_A = "a" * 64
SHA_B = "b" * 64
IDENTITY = (1.0, 0.0, 0.0, 0.0)


def _q(axis: str, degrees: float) -> tuple[float, float, float, float]:
    half = degrees * pi / 360
    components = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[axis]
    return (cos(half), *(sin(half) * value for value in components))


def _clock(node: str, source: str, status: str = "supported") -> ClockMap:
    return ClockMap(node, f"clock-{node}", 0, 1.0, 0.0, 0, 2_000_000, 0, 2_000_000,
                    1.0, 1.0, "synthetic anchors", source, status)


def _m2(quaternions: list[tuple[float, float, float, float]], *, valid: list[bool] | None = None,
        reason: tuple[str, ...] | None = None) -> RelativeOrientationResult:
    n = len(quaternions)
    return RelativeOrientationResult(
        np.arange(n, dtype=np.int64) * 250_000, np.array(quaternions, dtype=np.float64),
        np.array(valid if valid is not None else [True] * n, dtype=np.bool_),
        reason if reason is not None else ("valid",) * n, "Derived", "slerp", 500_000, 10.0,
        SHA_A, SHA_B, _clock("A", SHA_A), _clock("B", SHA_B),
        HeadingRelation("world-A", "world-B", IDENTITY, "synthetic shared heading", SHA_A, "supported"),
    )


def _alignment(node: str, segment: str, source: str, side: str = "right") -> AlignmentRecord:
    return AlignmentRecord(
        node_id=node, epoch=0, segment=segment, side=side, quaternion_nsegment=IDENTITY,
        alignment_id=f"synthetic-{node}", method="known synthetic axes", source_sha256=source,
        neutral_pose="arms down; H +Z proximal", validity="current",
        mounting_validity_statement="same unchanged synthetic mount and source epoch",
        remounted=False, uncertainty="exact synthetic ground truth", status="supported",
        axes_basis="synthetic_ground_truth",
    )


def _compute(m2: RelativeOrientationResult, *, side: str = "right",
             thorax: AlignmentRecord | None = None, humerus: AlignmentRecord | None = None):
    return long_axis_elevation(
        m2, thorax_alignment=_alignment("A", "T", SHA_A, side) if thorax is None else thorax,
        humerus_alignment=_alignment("B", "H", SHA_B, side) if humerus is None else humerus,
        side=side, source_type="synthetic", max_sample_gap_us=500_000,
    )


@pytest.mark.parametrize(("quaternion", "side", "expected"), [
    (IDENTITY, "right", 0.0),
    (_q("y", 90), "right", pi / 2),
    (_q("x", 90), "right", pi / 2),
    (_q("x", -90), "left", pi / 2),
    (_q("y", 180), "right", pi),
])
def test_analytical_e0_to_e4(quaternion, side, expected) -> None:
    result = _compute(_m2([quaternion]), side=side)
    assert result.valid.tolist() == [True]
    assert result.reason == ("valid",)
    assert result.elevation_rad[0] == pytest.approx(expected, abs=1e-10)
    assert result.side == side
    assert result.common_time_us.tolist() == [0]
    assert (result.thorax_source_sha256, result.humerus_source_sha256) == (SHA_A, SHA_B)
    assert result.evidence_label == "Derived"


def test_noncommuting_e5_and_sign_invariance_e6() -> None:
    # q_TH = inverse(Rx(60)) * Ry(45); independent dot of world long axes = sqrt(2)/4.
    a = _q("x", -60)
    b = _q("y", 45)
    q = (a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
         a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
         a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
         a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0])
    result = _compute(_m2([q, tuple(-v for v in q)]))
    np.testing.assert_allclose(result.elevation_rad, acos(sqrt(2) / 4), atol=1e-10, rtol=0)


@pytest.mark.parametrize(("change", "expected"), [
    ({"source_sha256": SHA_B}, "alignment_incompatible"),
    ({"side": "left"}, "alignment_incompatible"),
    ({"segment": "H"}, "alignment_incompatible"),
    ({"mounting_validity_statement": ""}, "alignment_incompatible"),
    ({"remounted": True}, "alignment_expired"),
    ({"validity": "expired"}, "alignment_expired"),
])
def test_alignment_rejections_block_all_rows(change, expected) -> None:
    thorax = replace(_alignment("A", "T", SHA_A), **change)
    result = _compute(_m2([IDENTITY, _q("y", 90)]), thorax=thorax)
    assert result.valid.tolist() == [False, False]
    assert result.reason == (expected, expected)
    assert np.isnan(result.elevation_rad).all()


def test_missing_alignment_and_clock_heading_rejected() -> None:
    m2 = _m2([IDENTITY])
    kwargs = dict(side="right", source_type="synthetic", max_sample_gap_us=500_000)
    missing = long_axis_elevation(m2, thorax_alignment=None,
                                  humerus_alignment=_alignment("B", "H", SHA_B), **kwargs)
    assert missing.reason == ("alignment_missing",)
    for altered in [replace(m2, thorax_clock_map=None), replace(m2, heading_relation=None)]:
        result = _compute(altered)
        assert result.reason == ("clock_or_heading_missing",)
        assert np.isnan(result.elevation_rad).all()


def test_m2_invalid_row_preserves_reason_and_assumptions() -> None:
    m2 = _m2([IDENTITY, (np.nan,) * 4], valid=[True, False], reason=("valid", "interpolation_gap"))
    result = _compute(m2)
    assert result.valid.tolist() == [True, False]
    assert result.reason == ("valid", "m2_invalid:interpolation_gap")
    assert np.isnan(result.elevation_rad[1])
    assumed = _compute(replace(m2, humerus_clock_map=replace(m2.humerus_clock_map, status="assumed")))
    assert assumed.evidence_label == "Assumed/Experimental"
    assumed_alignment = replace(_alignment("B", "H", SHA_B), status="assumed")
    assert _compute(_m2([IDENTITY]), humerus=assumed_alignment).evidence_label == "Assumed/Experimental"


def test_invalid_numeric_quaternion_is_not_repaired() -> None:
    result = _compute(_m2([(2.0, 0.0, 0.0, 0.0), (float("nan"), 0.0, 0.0, 0.0)]))
    assert result.reason == ("nonfinite_or_nonunit_quaternion",) * 2
    assert np.isnan(result.elevation_rad).all()


def test_synthetic_and_assumed_evidence_never_claims_physical_anatomy() -> None:
    synthetic = _compute(_m2([IDENTITY]))
    assert synthetic.anatomical_eligible is False
    assumed = _compute(_m2([IDENTITY]), humerus=replace(_alignment("B", "H", SHA_B), status="assumed"))
    assert assumed.anatomical_eligible is False
    m2 = _m2([IDENTITY])
    measured = long_axis_elevation(
        m2,
        thorax_alignment=replace(_alignment("A", "T", SHA_A), axes_basis="measured"),
        humerus_alignment=replace(_alignment("B", "H", SHA_B), axes_basis="measured"),
        side="right", source_type="recorded", max_sample_gap_us=500_000,
    )
    assert measured.anatomical_eligible is True


def test_incompatible_clock_and_heading_are_not_usable_evidence() -> None:
    m2 = _m2([IDENTITY])
    cases = [
        replace(m2, thorax_clock_map=replace(m2.thorax_clock_map, status="invalid")),
        replace(m2, thorax_clock_map=replace(m2.thorax_clock_map, heldout_residual_us=None)),
        replace(m2, heading_relation=replace(m2.heading_relation, status="invalid")),
        replace(m2, heading_relation=replace(m2.heading_relation, quaternion_thorax_world_humerus_world=(2, 0, 0, 0))),
    ]
    for altered in cases:
        result = _compute(altered)
        assert result.reason == ("clock_or_heading_missing",)
        assert result.evidence_label == "Invalid"
