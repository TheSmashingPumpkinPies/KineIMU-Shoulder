"""CP1 oracles from tests/fixtures/M4_KNOWN_EXERCISES.md (C0–C21)."""

from dataclasses import replace
from math import cos, pi, sin

import numpy as np
import pytest

from kineimu_shoulder.exercise import ExerciseConfig, segment_shoulder_repetitions
from kineimu_shoulder.relative_orientation import ClockMap, HeadingRelation, RelativeOrientationResult
from kineimu_shoulder.shoulder import AlignmentRecord, long_axis_elevation, relative_angular_speed

TIMES = [-400000, -200000, 0, 200000, 400000, 600000, 800000,
         1000000, 1200000, 1400000, 1600000, 1800000, 2000000, 2200000, 2400000]
ANGLES = [0, 0, 0, 20, 40, 60, 80, 80, 80, 80, 60, 40, 20, 0, 0]
SHA_A, SHA_B = "a" * 64, "b" * 64
IDENTITY = (1., 0., 0., 0.)


def inputs(times=TIMES, angles=ANGLES, *, side="left", exercise="flexion", direction=0,
           invalid=None, sign=1, gap=500000, assumed=False):
    quaternions = []
    for index, degrees in enumerate(angles):
        half = degrees * pi / 360
        deviation = (direction.get(index, 0) if isinstance(direction, dict) else direction) * pi / 180
        # Independent axis-angle carrying +Z to CP0's stated long-axis vector.
        if exercise == "flexion":
            axis = (sin(deviation), -cos(deviation), 0)
        else:
            axis = ((1 if side == "left" else -1) * cos(deviation), sin(deviation), 0)
        quaternions.append([sign * cos(half), *(sign * sin(half) * v for v in axis)])
    valid = np.ones(len(times), dtype=np.bool_)
    reasons = ["valid"] * len(times)
    if invalid is not None:
        valid[invalid] = False
        reasons[invalid] = "clock_validity"
        quaternions[invalid] = [np.nan] * 4
    def clock(node, sha):
        return ClockMap(node, node, 0, 1., 0., -2000000, 20000000, -2000000, 20000000,
                        1., 1., "synthetic anchors", sha, "assumed" if assumed else "supported")
    relative = RelativeOrientationResult(
        np.array(times, dtype=np.int64), np.array(quaternions), valid, tuple(reasons),
        "Assumed/Experimental" if assumed else "Derived", "slerp", gap, 10., SHA_A, SHA_B,
        clock("A", SHA_A), clock("B", SHA_B),
        HeadingRelation("Wa", "Wb", IDENTITY, "synthetic heading", SHA_A, "supported"),
    )
    def alignment(node, segment, sha):
        return AlignmentRecord(node, 0, segment, side, IDENTITY, node, "synthetic axes", sha,
                               "arms down; H +Z proximal", "current", "unchanged mount", False,
                               "exact synthetic", "supported", "synthetic_ground_truth")
    kwargs = dict(thorax_alignment=alignment("A", "T", SHA_A), humerus_alignment=alignment("B", "H", SHA_B),
                  side=side, source_type="synthetic", max_sample_gap_us=gap)
    return long_axis_elevation(relative, **kwargs), relative_angular_speed(relative, **kwargs)


def analyze(elevation, speed, *, config=None, window=None, exercise="flexion", side="left"):
    return segment_shoulder_repetitions(
        elevation, speed, exercise=exercise, side=side, configuration=config or ExerciseConfig(500000),
        analysis_window_us=window or (int(elevation.common_time_us[0]), int(elevation.common_time_us[-1])),
        session_id="synthetic-cp1", protocol_id="known-exercises", protocol_version="1.0",
        calibration_sha256=(SHA_A, SHA_B), processing_sha256=SHA_A,
    )


@pytest.mark.parametrize("side,exercise,sign", [
    ("left", "flexion", 1), ("right", "flexion", 1),
    ("left", "abduction", 1), ("right", "abduction", 1), ("left", "flexion", -1),
])
def test_c0_c1_c2_c20_clean_boundaries(side, exercise, sign):
    result = analyze(*inputs(side=side, exercise=exercise, sign=sign), side=side, exercise=exercise)
    # CP0 A: retrospective start/end and earliest maximum, C0/C1/C2/C20.
    assert (result.detected_count, result.valid_count, result.excluded_count) == (1, 1, 0)
    candidate = result.candidates[0]
    assert (candidate.start_us, candidate.end_us, candidate.peak_us) == (200000, 2200000, 800000)
    assert candidate.start_confirmation_us == (200000, 400000)
    assert candidate.end_confirmation_us == (2200000, 2400000)
    assert candidate.rise_support_us == (200000, 800000)
    assert candidate.return_support_us == (800000, 2200000)
    assert candidate.plane_fraction == pytest.approx(1, abs=1e-12)
    assert candidate.plane_eligible_duration_s == pytest.approx(1.4, abs=1e-12)
    assert result.elevation_result is not None and not result.anatomical_eligible


@pytest.mark.parametrize("times", [[0, 200000, 400000], [0, 200000]])
def test_c3_c21_quiet(times):
    result = analyze(*inputs(times, [0] * len(times)))
    assert result.analysis_valid
    assert (result.detected_count, result.valid_count, result.excluded_count) == (0, 0, 0)


@pytest.mark.parametrize("direction,expected", [(45, False), (20, True), (21, False), (180, False)])
def test_c5_to_c8_direction(direction, expected):
    candidate = analyze(*inputs(direction=direction)).candidates[0]
    assert candidate.valid is expected
    assert candidate.plane_fraction == (1 if expected else 0)
    if not expected:
        assert "plane_mismatch" in candidate.reasons


def test_c5_opposite_abduction():
    elevation, speed = inputs(exercise="abduction", direction=180)
    assert "plane_mismatch" in analyze(elevation, speed, exercise="abduction").candidates[0].reasons


def test_c9_unobservable():
    config = replace(ExerciseConfig(500000), plane_min_elevation_rad=pi/3, min_peak_rad=pi/3)
    result = analyze(*inputs(angles=[0, 0, 0, 180, 180, 180, 180, 180, 180, 180, 0, 0, 0, 0, 0]), config=config)
    assert "plane_unobservable" in result.candidates[0].reasons
    assert result.candidates[0].plane_fraction is None


def test_c10_elapsed_debounce_and_hysteresis():
    times = TIMES[:3] + [100000, 200000, 300000] + [v + 200000 for v in TIMES[3:]]
    result = analyze(*inputs(times, ANGLES[:3] + [20, 19, 20] + ANGLES[3:]))
    assert (result.detected_count, result.valid_count) == (1, 1)
    assert result.candidates[0].start_us == 300000
    assert any(d.reason == "start_debounce_failed" and d.bounds_us == (100000, 100000)
               for d in result.segmentation_diagnostics)


@pytest.mark.parametrize("window,bounds,reason", [
    ((400000, 2400000), (400000, 2200000), "partial_start"),
    ((-400000, 1800000), (200000, 1800000), "partial_end"),
    ((-400000, 2200000), (200000, 2200000), "partial_end"),
])
def test_c11_to_c13_censoring(window, bounds, reason):
    candidate = analyze(*inputs(), window=window).candidates[0]
    assert (candidate.start_us, candidate.end_us) == bounds
    assert not candidate.valid and reason in candidate.reasons


def test_c14_failed_return_does_not_split():
    angles = ANGLES.copy()
    angles[10] = 0
    result = analyze(*inputs(angles=angles))
    assert (result.detected_count, result.valid_count) == (1, 1)
    assert result.candidates[0].end_us == 2200000


@pytest.mark.parametrize("mode", ["row", "speed", "gap", "tail"])
def test_c15_to_c19_interruptions(mode):
    times = [v + (400000 if v >= 1000000 and mode == "gap" else 0) for v in TIMES]
    elevation, speed = inputs(times, invalid=7 if mode == "row" else 14 if mode == "tail" else None)
    if mode == "speed":
        mask, values, reasons = speed.valid.copy(), speed.relative_angular_speed_rads.copy(), list(speed.reason)
        mask[6], values[6], reasons[6] = False, np.nan, "speed_test_failure"
        speed = replace(speed, valid=mask, relative_angular_speed_rads=values, reason=tuple(reasons))
    result = analyze(elevation, speed)
    assert result.valid_count == 0
    assert result.candidates[0].interrupted
    if mode == "tail":
        assert result.detected_count == 1
        assert result.candidates[0].end_us == 2200000
    else:
        assert result.detected_count == 2
        assert result.candidates[0].end_us == 800000
        assert result.candidates[1].partial_start
    if mode == "row":
        assert (7, "m2_invalid:clock_validity") in result.candidates[0].offending_rows
    if mode == "speed":
        assert (6, "speed_test_failure") in result.candidates[0].offending_intervals
    if mode == "gap":
        assert "sample_gap" in result.candidates[0].reasons
    assert result.observed_valid_duration_s + result.observed_invalid_duration_s == pytest.approx(
        (times[-1] - times[0]) / 1e6, abs=1e-12)


def test_c18_gap_equality():
    times = [v + (300000 if v >= 1000000 else 0) for v in TIMES]
    result = analyze(*inputs(times))
    assert result.valid_count == 1
    assert result.candidates[0].end_us - result.candidates[0].start_us == 2300000


@pytest.mark.parametrize("bad_indices,fraction,valid", [([3], .95, True), ([5], .8, False), ([3, 14], .9, True)])
def test_plane_time_weighted_fraction_oracle(bad_indices, fraction, valid):
    times = [int(v * 1e6) for v in [-1, -.5, 0, .5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10.5, 11, 11.5]]
    angles = [0, 0, 20, 40, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 40, 0, 0]
    candidate = analyze(*inputs(times, angles, direction=dict.fromkeys(bad_indices, 21), gap=1000000),
                        config=ExerciseConfig(1000000)).candidates[0]
    # Frozen fraction oracle: eligible 10 s; failing 0.5, 2, or 1 s, both endpoints tested.
    assert candidate.plane_fraction == pytest.approx(fraction, abs=1e-12)
    assert candidate.valid is valid
    assert "plane_deviation_present" in candidate.diagnostics


def test_global_missing_and_assumed_evidence():
    elevation, speed = inputs()
    relative = replace(elevation.relative_orientation, heading_relation=None)
    elevation = replace(elevation, relative_orientation=relative)
    speed = replace(speed, elevation_result=elevation)
    result = analyze(elevation, speed)
    assert not result.analysis_valid and result.detected_count is None and result.candidates == ()
    assert "clock_or_heading_missing" in result.reasons
    assumed = analyze(*inputs(assumed=True))
    assert assumed.evidence_label == "Assumed/Experimental" and not assumed.anatomical_eligible


@pytest.mark.parametrize("mutation", ["window", "dtype", "duplicate", "reverse", "elevation", "speed", "binding"])
def test_c4_malformed_inputs(mutation):
    elevation, speed = inputs()
    if mutation == "window":
        with pytest.raises(ValueError):
            analyze(elevation, speed, window=(0, 0))
        return
    if mutation in ("dtype", "duplicate", "reverse"):
        grid = elevation.common_time_us.copy()
        if mutation == "dtype":
            grid = grid.astype(float)
        elif mutation == "duplicate":
            grid[1] = grid[0]
        else:
            grid = grid[::-1]
        elevation = replace(elevation, common_time_us=grid)
    elif mutation == "elevation":
        elevation = replace(elevation, elevation_rad=elevation.elevation_rad + .01)
    elif mutation == "speed":
        speed = replace(speed, relative_angular_speed_rads=speed.relative_angular_speed_rads + .01)
    else:
        speed = replace(speed, side="right")
    with pytest.raises(ValueError):
        analyze(elevation, speed)


@pytest.mark.parametrize("changes", [{"rest_confirm_us": True}, {"plane_min_fraction": np.nan},
                                    {"rest_level_rad": pi}, {"max_sample_gap_us": 0},
                                    {"plane_min_elevation_rad": pi / 9}])
def test_invalid_configuration(changes):
    with pytest.raises(ValueError):
        analyze(*inputs(), config=replace(ExerciseConfig(500000), **changes))


def test_two_successive_envelopes_and_short_unconfirmed_low():
    result = analyze(*inputs(TIMES + [v + 3000000 for v in TIMES], ANGLES * 2))
    # Repeating independent A with a 0.2 s connected rest gap: exactly two envelopes.
    assert (result.detected_count, result.valid_count) == (2, 2)
    assert [(c.id, c.start_us, c.end_us) for c in result.candidates] == [
        (1, 200000, 2200000), (2, 3200000, 5200000)]
    quiet = analyze(*inputs([0, 100000], [10, 10]))
    assert quiet.detected_count == 0


def test_unconfirmed_leading_rest_and_both_censoring_flags():
    candidate = analyze(*inputs([0, 100000, 300000, 500000], [0, 20, 60, 80])).candidates[0]
    assert (candidate.start_us, candidate.end_us) == (100000, 500000)
    assert candidate.partial_start and candidate.partial_end and not candidate.valid
    assert candidate.start_confirmation_us is None and candidate.end_confirmation_us is None


@pytest.mark.parametrize("gate,threshold,reason", [
    ("min_peak_rad", pi / 3, "peak_below_minimum"),
    ("min_rom_rad", pi / 3, "rom_below_minimum"),
    ("min_phase_us", 400000, "phase_too_short"),
    ("min_rep_us", 1000000, "rep_too_short"),
])
def test_exact_amplitude_and_timing_gates(gate, threshold, reason):
    times = [-400000, -200000, 0, 200000, 400000, 600000, 800000, 1000000, 1200000]
    angles = [0, 0, 20, 40, 60, 40, 20, 0, 0]
    # CP0 P6/P8: closed [0,1], earliest peak0.4, peak/ROM60, rise0.4/return0.6.
    config = replace(ExerciseConfig(500000), **{gate: threshold})
    assert analyze(*inputs(times, angles), config=config).valid_count == 1
    excess = 1 if isinstance(threshold, int) else pi / 180
    excluded = analyze(*inputs(times, angles), config=replace(config, **{gate: threshold + excess}))
    assert reason in excluded.candidates[0].reasons and excluded.valid_count == 0


def test_invalid_speed_everywhere_is_unavailable_analysis():
    elevation, speed = inputs()
    speed = replace(speed, valid=np.zeros(len(TIMES)-1, dtype=np.bool_),
                    relative_angular_speed_rads=np.full(len(TIMES)-1, np.nan),
                    reason=("speed_missing",) * (len(TIMES)-1), evidence_label="Invalid")
    result = analyze(elevation, speed)
    assert not result.analysis_valid and result.reasons == ("no_usable_continuity",)
    assert result.detected_count is None and not result.candidates
    assert len(result.segmentation_diagnostics) == len(TIMES)-1


@pytest.mark.parametrize("mutation", ["nonunit", "nan", "shape", "source", "interval", "missing_row_mask"])
def test_nested_contract_forgery_is_rejected(mutation):
    elevation, speed = inputs()
    if mutation in ("nonunit", "nan", "shape"):
        relative = elevation.relative_orientation
        q = relative.quaternion_th.copy()
        if mutation == "nonunit":
            q[5] *= 2
        elif mutation == "nan":
            q[5] = np.nan
        else:
            q = q[:, :3]
        elevation = replace(elevation, relative_orientation=replace(relative, quaternion_th=q))
        speed = replace(speed, elevation_result=elevation)
    elif mutation == "source":
        speed = replace(speed, humerus_source_sha256=SHA_A)
    elif mutation == "interval":
        speed = replace(speed, end_time_us=speed.end_time_us + 1)
    else:
        elevation = replace(elevation, valid=elevation.valid[:-1])
        speed = replace(speed, elevation_result=elevation)
    with pytest.raises(ValueError):
        analyze(elevation, speed)


@pytest.mark.parametrize("change", [{"slope": -1}, {"uncertainty_us": -1},
                                    {"heldout_residual_us": np.nan}])
def test_malformed_nested_clock_record(change):
    elevation, speed = inputs()
    relative = elevation.relative_orientation
    relative = replace(relative, thorax_clock_map=replace(relative.thorax_clock_map, **change))
    elevation = replace(elevation, relative_orientation=relative)
    speed = replace(speed, elevation_result=elevation)
    with pytest.raises(ValueError):
        analyze(elevation, speed)


@pytest.mark.parametrize("mutation", ["missing_speed", "invalid_label", "valid_reason"])
def test_missing_or_inconsistent_speed_evidence(mutation):
    elevation, speed = inputs()
    if mutation == "missing_speed":
        speed = None
    elif mutation == "invalid_label":
        speed = replace(speed, evidence_label="Invalid")
    else:
        speed = replace(speed, reason=("invalid",) * len(speed.reason))
    with pytest.raises(ValueError):
        analyze(elevation, speed)


def test_irregular_timestamps_p10_boundaries():
    # CP0 P10: elapsed-time confirmations on an irregular grid, [0,1.2], peak0.5.
    times = [-400000, -200000, 0, 200000, 500000, 800000, 1000000, 1200000, 1400000]
    candidate = analyze(*inputs(times, [0, 0, 20, 40, 80, 80, 40, 0, 0])).candidates[0]
    assert candidate.valid
    assert (candidate.start_us, candidate.end_us, candidate.peak_us) == (0, 1200000, 500000)
