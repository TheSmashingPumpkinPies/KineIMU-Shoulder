"""M2.4 analytical two-body, clock, and evidence-gate fixtures."""

from dataclasses import replace
from math import sqrt

import numpy as np
import pytest

from kineimu_shoulder.frames import rotate_vector
from kineimu_shoulder.relative_orientation import (
    ClockMap,
    HeadingRelation,
    SegmentOrientationStream,
    relative_orientation,
)

ROOT_HALF = sqrt(0.5)
SOURCE = "a" * 64


def _stream(
    times: list[int], quaternions: list[tuple[float, float, float, float]], *, node: str
) -> SegmentOrientationStream:
    return SegmentOrientationStream(
        node_id=node,
        clock_id=f"clock-{node}",
        epoch=0,
        world_id=f"world-{node}",
        source_sha256=SOURCE,
        timestamp_us=np.array(times, dtype=np.int64),
        quaternion_wsegment=np.array(quaternions, dtype=np.float64),
    )


def _map(node: str, *, slope: float = 1.0, offset: float = 100_000.0, uncertainty: float = 1.0,
         valid_end: int = 2_000, status: str = "supported") -> ClockMap:
    return ClockMap(
        node_id=node,
        clock_id=f"clock-{node}",
        epoch=0,
        slope=slope,
        intercept_us=offset,
        fit_device_start_us=0,
        fit_device_end_us=valid_end,
        valid_device_start_us=0,
        valid_device_end_us=valid_end,
        uncertainty_us=uncertainty,
        heldout_residual_us=1.0 if status == "supported" else None,
        method="synthetic event anchors" if status == "supported" else "declared assumption",
        source_sha256=SOURCE,
        status=status,
    )


def _heading(*, status: str = "supported", target: str = "world-B") -> HeadingRelation:
    return HeadingRelation(
        thorax_world_id="world-A",
        humerus_world_id=target,
        quaternion_thorax_world_humerus_world=(1.0, 0.0, 0.0, 0.0),
        method="known synthetic shared heading",
        source_sha256=SOURCE,
        status=status,
    )


def _compute(thorax: SegmentOrientationStream, humerus: SegmentOrientationStream, grid: list[int],
             *, thorax_map: ClockMap | None = None, humerus_map: ClockMap | None = None,
             heading: HeadingRelation | None = None, max_gap: int = 1_500,
             max_uncertainty: float = 10.0):
    return relative_orientation(
        thorax, humerus, common_time_us=np.array(grid, dtype=np.int64),
        thorax_clock_map=_map("A") if thorax_map is None else thorax_map,
        humerus_clock_map=_map("B") if humerus_map is None else humerus_map,
        heading_relation=_heading() if heading is None else heading,
        max_interpolation_gap_us=max_gap, max_timing_uncertainty_us=max_uncertainty,
    )


def test_noncommuting_two_body_rotation_expresses_humerus_in_thorax() -> None:
    thorax = _stream([0, 1000], [(ROOT_HALF, 0, 0, ROOT_HALF)] * 2, node="A")
    humerus = _stream([0, 1000], [(0.5, 0.5, 0.5, 0.5)] * 2, node="B")
    result = _compute(thorax, humerus, [100_000, 100_500])

    assert result.valid.tolist() == [True, True]
    assert result.evidence_label == "Derived"
    # Analytical source: R_WT=Rz(90), R_WH=Rz(90)Rx(90), hence R_TH=Rx(90).
    np.testing.assert_allclose(rotate_vector(result.quaternion_th[1], (0, 1, 0)), (0, 0, 1), atol=1e-12)


def test_offset_drift_and_slerp_use_declared_common_time_not_row_index() -> None:
    thorax = _stream([0, 1000, 2000], [(1, 0, 0, 0)] * 3, node="A")
    humerus = _stream([0, 1000, 2000], [
        (1, 0, 0, 0), (ROOT_HALF, 0, 0, ROOT_HALF), (0, 0, 0, 1),
    ], node="B")
    result = _compute(thorax, humerus, [100_600, 101_150],
                      humerus_map=_map("B", slope=1.1, offset=100_050))

    assert result.valid.tolist() == [True, True]
    # Analytical source: B times map to 100050, 101150, 102250 us; 100600 is
    # halfway through its first 90° turn, and 101150 is the second exact sample.
    np.testing.assert_allclose(rotate_vector(result.quaternion_th[0], (1, 0, 0)),
                               (ROOT_HALF, ROOT_HALF, 0), atol=1e-12)
    np.testing.assert_allclose(rotate_vector(result.quaternion_th[1], (1, 0, 0)),
                               (0, 1, 0), atol=1e-12)


def test_heading_relation_rotates_humerus_world_into_thorax_world() -> None:
    thorax = _stream([0, 1000], [(1, 0, 0, 0)] * 2, node="A")
    humerus = _stream([0, 1000], [(1, 0, 0, 0)] * 2, node="B")
    heading = HeadingRelation("world-A", "world-B", (ROOT_HALF, 0, 0, ROOT_HALF),
                              "known synthetic frame rotation", SOURCE, "supported")
    result = _compute(thorax, humerus, [100_500], heading=heading)

    # Analytical source: R_WA_WB=Rz(90) and both segment orientations are identity.
    np.testing.assert_allclose(rotate_vector(result.quaternion_th[0], (1, 0, 0)), (0, 1, 0), atol=1e-12)


def test_missing_clock_or_incompatible_heading_returns_invalid_without_quaternion() -> None:
    thorax = _stream([0, 1000], [(1, 0, 0, 0)] * 2, node="A")
    humerus = _stream([0, 1000], [(1, 0, 0, 0)] * 2, node="B")
    for humerus_map, heading, reason in [
        (None, _heading(), "clock_map_missing"),
        (_map("B"), _heading(target="wrong"), "heading_incompatible"),
    ]:
        result = relative_orientation(
            thorax, humerus, common_time_us=np.array([100_500], dtype=np.int64),
            thorax_clock_map=_map("A"), humerus_clock_map=humerus_map,
            heading_relation=heading, max_interpolation_gap_us=1500,
            max_timing_uncertainty_us=10,
        )
        assert result.valid.tolist() == [False]
        assert result.reason == (reason,)
        assert np.isnan(result.quaternion_th).all()


def test_gap_and_mapping_validity_do_not_interpolate() -> None:
    thorax = _stream([0, 1000, 2000], [(1, 0, 0, 0)] * 3, node="A")
    humerus = _stream([0, 2000], [(1, 0, 0, 0)] * 2, node="B")
    gap_result = _compute(thorax, humerus, [100_500], max_gap=1500)
    interval_result = _compute(thorax, humerus, [101_500],
                               humerus_map=_map("B", valid_end=1000))

    assert gap_result.reason == ("interpolation_gap",)
    assert interval_result.reason == ("outside_clock_validity",)
    assert np.isnan(gap_result.quaternion_th).all()
    assert np.isnan(interval_result.quaternion_th).all()


def test_excessive_clock_uncertainty_blocks_result_and_assumption_is_labeled() -> None:
    thorax = _stream([0, 1000], [(1, 0, 0, 0)] * 2, node="A")
    humerus = _stream([0, 1000], [(1, 0, 0, 0)] * 2, node="B")
    uncertain = _compute(thorax, humerus, [100_500], humerus_map=_map("B", uncertainty=20))
    assumed = _compute(thorax, humerus, [100_500], humerus_map=_map("B", status="assumed"))

    assert uncertain.reason == ("clock_uncertainty",)
    assert np.isnan(uncertain.quaternion_th).all()
    assert assumed.valid.tolist() == [True]
    assert assumed.evidence_label == "Assumed/Experimental"


@pytest.mark.parametrize("change", [
    {"epoch": 1},
    {"clock_id": "other-clock"},
    {"slope": 0.0},
    {"heldout_residual_us": None},
    {"fit_device_start_us": 2_000, "fit_device_end_us": 0},
])
def test_clock_identity_or_evidence_mismatch_blocks_pairing(change: dict[str, object]) -> None:
    thorax = _stream([0, 1000], [(1, 0, 0, 0)] * 2, node="A")
    humerus = _stream([0, 1000], [(1, 0, 0, 0)] * 2, node="B")
    result = _compute(thorax, humerus, [100_500], humerus_map=replace(_map("B"), **change))

    assert result.reason == ("clock_map_incompatible",)
    assert result.evidence_label == "Invalid"
    assert np.isnan(result.quaternion_th).all()


def test_missing_heading_blocks_pairing_even_with_identical_world_quaternions() -> None:
    thorax = _stream([0, 1000], [(1, 0, 0, 0)] * 2, node="A")
    humerus = _stream([0, 1000], [(1, 0, 0, 0)] * 2, node="B")
    result = relative_orientation(
        thorax, humerus, common_time_us=np.array([100_500], dtype=np.int64),
        thorax_clock_map=_map("A"), humerus_clock_map=_map("B"), heading_relation=None,
        max_interpolation_gap_us=1500, max_timing_uncertainty_us=10,
    )

    assert result.reason == ("heading_missing",)
    assert np.isnan(result.quaternion_th).all()


@pytest.mark.parametrize("which", [0, 1, 2])
def test_reference_hash_must_resolve_to_supplied_evidence_source(which):
    q = (1.0, 0.0, 0.0, 0.0)
    a = _stream([0, 1000], [q, q], node="A")
    b = _stream([0, 1000], [q, q], node="B")
    records = [_map("A"), _map("B"), _heading()]
    records[which] = replace(records[which], source_sha256="0" * 64)
    r = relative_orientation(
        a, b, common_time_us=np.array([100000], dtype=np.int64),
        thorax_clock_map=records[0], humerus_clock_map=records[1], heading_relation=records[2],
        max_interpolation_gap_us=1500, max_timing_uncertainty_us=10,
        evidence_source_sha256=(SOURCE, SOURCE, SOURCE),
    )
    assert not r.valid.any()
    assert r.reason == (("clock_map_incompatible" if which < 2 else "heading_incompatible"),)
    assert np.isnan(r.quaternion_th).all()


def test_clock_endpoint_accepts_float_roundoff_but_not_real_submicrosecond_loss():
    from kineimu_shoulder.relative_orientation import _sample_at

    q = np.array([[1., 0., 0., 0.], [1., 0., 0., 0.]])
    c = _map("A", slope=1 / .9995, offset=-250000 / .9995, valid_end=300100000)
    mapped = c.slope * np.array([250000., 300100000.]) + c.intercept_us
    assert 0 < 300000000 - mapped[-1] < 1e-6
    value, reason = _sample_at(mapped, q, c, 300000000, 50000)
    assert reason == "valid" and value is not None
    shifted = mapped.copy()
    shifted[-1] -= .2
    value, reason = _sample_at(shifted, q, c, 300000000, 50000)
    assert value is None and reason == "outside_stream"
