"""CP3 closed-interval ROM and elapsed time against frozen R0–R7 fixtures."""

from dataclasses import replace
from math import cos, pi, sin

import numpy as np
import pytest

from kineimu_shoulder.relative_orientation import ClockMap, HeadingRelation, RelativeOrientationResult
from kineimu_shoulder.shoulder import AlignmentRecord, interval_rom_duration

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


THORAX_ALIGNMENT = _alignment("A", "T", SHA_A)


def _m2(times: list[int], angles: list[float], *, valid: list[bool] | None = None,
        reasons: tuple[str, ...] | None = None) -> RelativeOrientationResult:
    def clock(node: str, source: str) -> ClockMap:
        return ClockMap(node, f"clock-{node}", 0, 1.0, 0.0, 0, 2_000_000, 0, 2_000_000,
                        1.0, 1.0, "synthetic anchors", source, "supported")

    n = len(times)
    return RelativeOrientationResult(
        np.array(times, dtype=np.int64), np.array([_qy(a) for a in angles], dtype=np.float64),
        np.array(valid if valid is not None else [True] * n, dtype=np.bool_),
        reasons if reasons is not None else ("valid",) * n, "Derived", "slerp", 500_000, 10.0,
        SHA_A, SHA_B, clock("A", SHA_A), clock("B", SHA_B),
        HeadingRelation("world-A", "world-B", IDENTITY, "synthetic shared heading", SHA_A, "supported"),
    )


def _rom(m2: RelativeOrientationResult, start: int, end: int, *, gap: int = 500_000,
         thorax: AlignmentRecord | None = THORAX_ALIGNMENT):
    return interval_rom_duration(
        m2, thorax_alignment=thorax, humerus_alignment=_alignment("B", "H", SHA_B),
        side="right", source_type="synthetic", max_sample_gap_us=gap,
        start_time_us=start, end_time_us=end,
    )


R0_TIMES = [0, 200_000, 700_000, 1_200_000]
R0_ANGLES = [0, 20, 70, 30]


@pytest.mark.parametrize(("times", "angles", "start", "end", "rom", "duration"), [
    (R0_TIMES, R0_ANGLES, 0, 1_200_000, 7 * pi / 18, 1.2),
    ([0, 100_000, 400_000, 900_000], [10, 65, 35, 50], 0, 900_000, 11 * pi / 36, 0.9),
    (R0_TIMES, R0_ANGLES, 200_000, 700_000, 5 * pi / 18, 0.5),
])
def test_r0_to_r2_known_range_and_observed_duration(times, angles, start, end, rom, duration) -> None:
    result = _rom(_m2(times, angles), start, end)
    assert result.valid and result.reason == "valid"
    # Frozen R0–R2: Qy rotates H +Z by the listed angles; ROM is max−min.
    assert result.rom_rad == pytest.approx(rom, abs=1e-10)
    # Frozen R0–R2: elapsed duration uses the exact requested endpoints in microseconds.
    assert result.elapsed_duration_s == pytest.approx(duration, abs=1e-12)
    assert result.start_time_us == start and result.end_time_us == end
    assert result.first_invalid_row_index is None and result.invalid_row_reasons == ()
    assert result.evidence_label == "Derived" and not result.anatomical_eligible
    assert result.max_sample_gap_us == 500_000
    assert result.side == "right" and result.source_type == "synthetic"
    assert result.thorax_source_sha256 == SHA_A and result.humerus_source_sha256 == SHA_B
    assert result.definition_version == "m3-interval-rom-duration/1.0"


@pytest.mark.parametrize(("start", "end", "reason"), [
    (200_001, 700_000, "interval_endpoint_missing"),
    (700_000, 200_000, "interval_order"),
    (700_000, 700_000, "interval_too_short"),
    (0, 1_200_001, "interval_endpoint_missing"),
])
def test_r3_to_r5_and_out_of_range_boundaries_are_excluded(start, end, reason) -> None:
    result = _rom(_m2(R0_TIMES, R0_ANGLES), start, end)
    assert not result.valid and result.reason == reason
    assert np.isnan(result.rom_rad) and np.isnan(result.elapsed_duration_s)


def test_r6_invalid_interior_row_excludes_whole_interval_with_original_reason() -> None:
    m2 = _m2(R0_TIMES, R0_ANGLES, valid=[True, True, False, True],
             reasons=("valid", "valid", "interpolation_gap", "valid"))
    result = _rom(m2, 0, 1_200_000)
    assert not result.valid and result.reason == "interval_invalid_row"
    assert result.first_invalid_row_index == 2
    assert result.invalid_row_reasons == ((2, "m2_invalid:interpolation_gap"),)
    assert np.isnan(result.rom_rad) and np.isnan(result.elapsed_duration_s)


def test_all_invalid_rows_are_preserved_in_provenance() -> None:
    m2 = _m2(R0_TIMES, R0_ANGLES, valid=[True, False, False, True],
             reasons=("valid", "clock_extrapolation", "interpolation_gap", "valid"))
    result = _rom(m2, 0, 1_200_000)
    assert result.first_invalid_row_index == 1
    assert result.invalid_row_reasons == (
        (1, "m2_invalid:clock_extrapolation"), (2, "m2_invalid:interpolation_gap"),
    )


def test_invalid_rows_outside_requested_interval_do_not_exclude_it() -> None:
    m2 = _m2(R0_TIMES, R0_ANGLES, valid=[False, True, True, False],
             reasons=("clock_extrapolation", "valid", "valid", "interpolation_gap"))
    result = _rom(m2, 200_000, 700_000)
    # Frozen R2: only the closed [200000, 700000] rows contribute, giving 70°−20°.
    assert result.valid and result.rom_rad == pytest.approx(5 * pi / 18, abs=1e-10)
    assert result.invalid_row_reasons == ()


def test_invalid_row_reason_takes_precedence_over_gap() -> None:
    m2 = _m2([0, 600_000, 1_200_000], [0, 30, 60],
             valid=[True, False, True], reasons=("valid", "interpolation_gap", "valid"))
    result = _rom(m2, 0, 1_200_000)
    assert result.reason == "interval_invalid_row"
    assert result.invalid_row_reasons == ((1, "m2_invalid:interpolation_gap"),)


def test_r7_gap_excludes_whole_interval_and_equality_passes() -> None:
    m2 = _m2([0, 500_001], [0, 30])
    excluded = _rom(m2, 0, 500_001)
    assert excluded.reason == "sample_gap" and not excluded.valid
    assert np.isnan(excluded.rom_rad) and np.isnan(excluded.elapsed_duration_s)
    included = _rom(m2, 0, 500_001, gap=500_001)
    # Frozen R7 at the gap equality boundary: range is 30°, elapsed is 0.500001 s.
    assert included.rom_rad == pytest.approx(pi / 6, abs=1e-10)
    assert included.elapsed_duration_s == pytest.approx(0.500001, abs=1e-12)


def test_single_sample_cannot_define_a_nonzero_interval() -> None:
    result = _rom(_m2([0], [0]), 0, 0)
    assert not result.valid and result.reason == "interval_too_short"


def test_missing_evidence_blocks_interval_and_assumptions_propagate() -> None:
    m2 = _m2([0, 250_000], [0, 30])
    missing = _rom(m2, 0, 250_000, thorax=None)
    assert missing.reason == "interval_invalid_row" and missing.first_invalid_row_index == 0
    assert missing.invalid_row_reasons == ((0, "alignment_missing"), (1, "alignment_missing"))
    assert missing.evidence_label == "Invalid" and np.isnan(missing.rom_rad)
    assumed = _rom(replace(m2, evidence_label="Assumed/Experimental"), 0, 250_000)
    assert assumed.valid and assumed.evidence_label == "Assumed/Experimental"
    assert not assumed.anatomical_eligible
