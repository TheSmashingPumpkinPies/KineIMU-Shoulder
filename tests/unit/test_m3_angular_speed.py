"""CP2 interval angular speed against frozen S0–S6 analytical fixtures."""

from dataclasses import replace
from math import cos, pi, sin

import numpy as np
import pytest

from kineimu_shoulder.relative_orientation import ClockMap, HeadingRelation, RelativeOrientationResult
from kineimu_shoulder.shoulder import AlignmentRecord, relative_angular_speed

SHA_A = "a" * 64
SHA_B = "b" * 64
IDENTITY = (1.0, 0.0, 0.0, 0.0)


def _qy(degrees: float) -> tuple[float, float, float, float]:
    half = degrees * pi / 360
    return (cos(half), 0.0, sin(half), 0.0)


def _alignment(node: str, segment: str, source: str) -> AlignmentRecord:
    return AlignmentRecord(
        node_id=node, epoch=0, segment=segment, side="right", quaternion_nsegment=IDENTITY,
        alignment_id=f"synthetic-{node}", method="known synthetic axes", source_sha256=source,
        neutral_pose="arms down; H +Z proximal", validity="current",
        mounting_validity_statement="same synthetic mount", remounted=False,
        uncertainty="exact synthetic ground truth", status="supported", axes_basis="synthetic_ground_truth",
    )


def _m2(times: list[int], quaternions: list[tuple[float, float, float, float]], *,
        valid: list[bool] | None = None, reason: tuple[str, ...] | None = None) -> RelativeOrientationResult:
    def clock(node: str, source: str) -> ClockMap:
        return ClockMap(node, f"clock-{node}", 0, 1.0, 0.0, 0, 2_000_000, 0, 2_000_000,
                        1.0, 1.0, "synthetic anchors", source, "supported")

    n = len(times)
    return RelativeOrientationResult(
        np.array(times, dtype=np.int64), np.array(quaternions, dtype=np.float64),
        np.array(valid if valid is not None else [True] * n, dtype=np.bool_),
        reason if reason is not None else ("valid",) * n, "Derived", "slerp", 500_000, 10.0,
        SHA_A, SHA_B, clock("A", SHA_A), clock("B", SHA_B),
        HeadingRelation("world-A", "world-B", IDENTITY, "synthetic shared heading", SHA_A, "supported"),
    )


def _speed(m2: RelativeOrientationResult, *, gap: int = 500_000):
    return relative_angular_speed(
        m2, thorax_alignment=_alignment("A", "T", SHA_A),
        humerus_alignment=_alignment("B", "H", SHA_B), side="right",
        source_type="synthetic", max_sample_gap_us=gap,
    )


@pytest.mark.parametrize(("times", "quaternions", "expected"), [
    ([0, 250_000], [IDENTITY, IDENTITY], [0.0]),
    ([0, 250_000], [IDENTITY, _qy(30)], [2 * pi / 3]),
    ([0, 200_000, 700_000], [_qy(0), _qy(20), _qy(70)], [5 * pi / 9, 5 * pi / 9]),
    ([0, 250_000], [IDENTITY, tuple(-v for v in _qy(30))], [2 * pi / 3]),
])
def test_s0_to_s3_observed_delta_and_sign(times, quaternions, expected) -> None:
    result = _speed(_m2(times, quaternions))
    assert result.start_time_us.tolist() == times[:-1]
    assert result.end_time_us.tolist() == times[1:]
    assert result.valid.tolist() == [True] * len(expected)
    assert result.reason == ("valid",) * len(expected)
    # Frozen S0–S3: principal Y increments 0°, 30°, or 20°/50° divided by 0.25/0.2/0.5 s.
    np.testing.assert_allclose(result.relative_angular_speed_rads, expected, atol=1e-10, rtol=0)
    assert result.evidence_label == "Derived"
    assert result.side == "right"
    assert result.source_type == "synthetic"
    assert result.thorax_source_sha256 == SHA_A
    assert result.humerus_source_sha256 == SHA_B
    assert result.max_sample_gap_us == 500_000
    assert result.definition_version == "m3-relative-angular-speed/1.0"
    assert result.anatomical_eligible is False


def test_s4_gap_excludes_interval_and_equality_passes() -> None:
    m2 = _m2([0, 500_001], [IDENTITY, _qy(30)])
    excluded = _speed(m2)
    assert excluded.reason == ("sample_gap",)
    assert excluded.valid.tolist() == [False]
    assert np.isnan(excluded.relative_angular_speed_rads[0])
    included = _speed(m2, gap=500_001)
    assert included.valid.tolist() == [True]
    # Frozen S4 at the equality boundary: 30° principal increment / 0.500001 s.
    assert included.relative_angular_speed_rads[0] == pytest.approx((pi / 6) / 0.500001, abs=1e-10)


def test_s5_invalid_endpoint_does_not_bridge_missing_data() -> None:
    m2 = _m2([0, 250_000, 500_000], [IDENTITY, (float("nan"),) * 4, _qy(60)],
             valid=[True, False, True], reason=("valid", "interpolation_gap", "valid"))
    result = _speed(m2)
    assert result.reason == ("m2_invalid:interpolation_gap",) * 2
    assert result.valid.tolist() == [False, False]
    assert np.isnan(result.relative_angular_speed_rads).all()
    assert result.start_time_us.tolist() == [0, 250_000]
    assert result.end_time_us.tolist() == [250_000, 500_000]


def test_first_invalid_endpoint_reason_takes_precedence_over_gap() -> None:
    m2 = _m2([0, 600_000, 1_200_000],
             [(float("nan"),) * 4, _qy(30), (float("nan"),) * 4],
             valid=[False, True, False], reason=("clock_extrapolation", "valid", "interpolation_gap"))
    result = _speed(m2)
    assert result.reason == ("m2_invalid:clock_extrapolation", "m2_invalid:interpolation_gap")
    assert np.isnan(result.relative_angular_speed_rads).all()


def test_s6_full_turn_endpoint_alias_is_not_measured_stationarity() -> None:
    # Frozen S6: a known 360° path has identical endpoints, so the endpoint estimator returns zero.
    result = _speed(_m2([0, 250_000], [IDENTITY, IDENTITY]))
    assert result.relative_angular_speed_rads[0] == pytest.approx(0.0, abs=1e-10)
    assert result.quantity_description == "principal endpoint rotation magnitude averaged over interval"


def test_noncommuting_three_dimensional_speed_is_not_elevation_derivative() -> None:
    # Independent Hamilton geometry: inverse(Qx(90)) ⊗ Qy(90) has |scalar|=1/2,
    # hence principal angle 120° while both endpoint long-axis elevations are 90°.
    qx90 = (cos(pi / 4), sin(pi / 4), 0.0, 0.0)
    result = _speed(_m2([0, 250_000], [qx90, _qy(90)]))
    assert result.relative_angular_speed_rads[0] == pytest.approx(8 * pi / 3, abs=1e-10)
    np.testing.assert_allclose(result.elevation_result.elevation_rad, [pi / 2, pi / 2], atol=1e-10, rtol=0)


def test_nonunit_endpoint_excludes_interval() -> None:
    result = _speed(_m2([0, 250_000], [IDENTITY, (2.0, 0.0, 0.0, 0.0)]))
    assert result.reason == ("nonfinite_or_nonunit_quaternion",)
    assert np.isnan(result.relative_angular_speed_rads[0])


def test_global_evidence_blocks_speed_and_assumptions_propagate() -> None:
    m2 = _m2([0, 250_000], [IDENTITY, _qy(30)])
    missing = _speed(replace(m2, heading_relation=None))
    assert missing.reason == ("clock_or_heading_missing",)
    assert missing.evidence_label == "Invalid"
    assert np.isnan(missing.relative_angular_speed_rads).all()
    assumed = _speed(replace(m2, evidence_label="Assumed/Experimental"))
    assert assumed.evidence_label == "Assumed/Experimental"
    assert assumed.anatomical_eligible is False


def test_single_sample_has_no_speed_interval() -> None:
    result = _speed(_m2([0], [IDENTITY]))
    assert result.start_time_us.size == 0
    assert result.end_time_us.size == 0
    assert result.relative_angular_speed_rads.size == 0
    assert result.valid.size == 0
    assert result.reason == ()
