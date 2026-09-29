"""CP2 analytical truths P0–P10 in fixtures/M4_KNOWN_EXERCISES.md.

Catch hold/elevation-rate confusion, sample weighting, double ownership and
numeric leakage from excluded candidates. Construction uses CP1 test utilities.
"""

from dataclasses import fields, replace
from math import cos, isnan, pi, sin

import numpy as np
import pytest
from test_m4_segmentation import ANGLES, TIMES, analyze, inputs

from kineimu_shoulder import exercise as module
from kineimu_shoulder.exercise import ExerciseConfig
from kineimu_shoulder.shoulder import long_axis_elevation, relative_angular_speed


def metrics(segmentation):
    function = getattr(module, "compute_repetition_metrics", None)
    assert callable(function), "CP2 per-repetition metrics API is missing"
    return function(segmentation)


def check(metric, value, unit):
    assert metric.valid and metric.reason == "ok"
    assert metric.unit == unit
    assert metric.evidence_label == "Derived" and not metric.anatomical_eligible
    assert metric.value == pytest.approx(value, rel=0, abs=1e-10 if unit != "s" else 1e-12)


@pytest.mark.parametrize("times,angles,duration,rise,returned,hold,mean,max_speed,return_mean", [
    (TIMES, ANGLES, 2., .6, .8, .6, 70., 100., 100.),  # P0
    (TIMES[:7] + [1000000, 1200000, 1400000, 1600000, 1800000],
     ANGLES[:7] + [60, 40, 20, 0, 0], 1.4, .6, .8, 0., 100., 100., 100.),  # P1
    (TIMES[:7] + [1000000, 1300000, 1500000, 1700000, 1900000, 2100000, 2300000],
     ANGLES[:7] + [80, 80, 60, 40, 20, 0, 0], 1.9, .6, .8, .5, 140/1.9, 100., 100.),  # P2
    (TIMES[:7] + [1000000, 1200000, 1400000, 1600000, 1800000, 2000000, 2200000],
     ANGLES[:7] + [80, 80, 60, 40, 20, 0, 0], 1.8, .6, 1.2, 0., 140/1.8, 100., 80/1.2),  # P3
    ([-400000, -200000, 0, 200000, 500000, 800000, 1000000, 1200000, 1400000],
     [0, 0, 20, 40, 80, 80, 40, 0, 0], 1.2, .5, .7, 0., 140/1.2, 200., 80/.7),  # P10
])
def test_p0_p1_p2_p3_p10_analytical_metrics(times, angles, duration, rise, returned, hold,
                                        mean, max_speed, return_mean):
    result = metrics(analyze(*inputs(times, angles)))
    rep = result.repetitions[0]
    # CP0 P0/P1/P2/P3/P10: exact closed supports and integrated axis motion.
    for name, value, unit in [
        ("rom_rad", 80*pi/180, "rad"), ("peak_elevation_rad", 80*pi/180, "rad"),
        ("rep_duration_s", duration, "s"), ("elevation_duration_s", rise, "s"),
        ("return_duration_s", returned, "s"), ("hold_duration_s", hold, "s"),
        ("rep_speed_mean_rads", mean*pi/180, "rad/s"),
        ("rep_speed_max_rads", max_speed*pi/180, "rad/s"),
        ("return_speed_mean_rads", return_mean*pi/180, "rad/s"),
    ]:
        check(getattr(rep.metrics, name), value, unit)
    assert rep.candidate is result.segmentation.candidates[0]
    assert rep.metrics.preceding_rest_duration_s.reason == "rest_interrupted"
    if hold:
        check(rep.metrics.hold_speed_mean_rads, 0., "rad/s")
        check(rep.metrics.hold_speed_max_rads, 0., "rad/s")
    else:
        assert rep.metrics.hold_speed_mean_rads.reason == "empty_phase"
        assert isnan(rep.metrics.hold_speed_max_rads.value)
    # Contract conservation and single interval ownership; confirmation tail excluded.
    owned = rep.elevation_intervals + rep.return_intervals + rep.hold_intervals
    assert len(set(owned)) == len(owned)
    start = times.index(rep.candidate.start_us)
    end = times.index(rep.candidate.end_us)
    assert sorted(owned) == list(range(start, end))
    assert rise + returned + hold == pytest.approx(duration, abs=1e-12)


def rolling_inputs(rate):
    e, _ = inputs()
    qs = []
    for time, degrees in zip(TIMES, ANGLES, strict=True):
        a = -degrees*pi/360
        b = rate*min(max(time/1e6-.8, 0), .6)*pi/360
        # Hamilton qY(a) qZ(b), independent of production rotation operations.
        qs.append([cos(a)*cos(b), sin(a)*sin(b), sin(a)*cos(b), cos(a)*sin(b)])
    relative = replace(e.relative_orientation, quaternion_th=np.array(qs))
    kwargs = dict(thorax_alignment=e.thorax_alignment, humerus_alignment=e.humerus_alignment,
                  side=e.side, source_type=e.source_type, max_sample_gap_us=e.max_sample_gap_us)
    return long_axis_elevation(relative, **kwargs), relative_angular_speed(relative, **kwargs)


@pytest.mark.parametrize("rate,hold,mean", [(10, 0., 73.), (5, .6, 71.5)])
def test_p4_p5_hold_uses_three_dimensional_speed(rate, hold, mean):
    rep = metrics(analyze(*rolling_inputs(rate))).repetitions[0]
    # CP0 P4/P5: (140 + rate*.6)/2, while elevation is constant on plateau.
    check(rep.metrics.hold_duration_s, hold, "s")
    check(rep.metrics.rep_speed_mean_rads, mean*pi/180, "rad/s")
    if hold:
        check(rep.metrics.hold_speed_mean_rads, 5*pi/180, "rad/s")
        assert rep.hold_runs_us == ((800000, 1400000),)


@pytest.mark.parametrize("scale,phase,valid", [(1, 200000, True), (.8, 200000, True),
                                            (1, 400000, True), (1, 400001, False)])
def test_p6_p7_p8_timing_and_peak_equalities(scale, phase, valid):
    times = [round(t*scale) for t in [-400000, -200000, 0, 200000, 400000, 600000,
                                     800000, 1000000, 1200000]]
    config = replace(ExerciseConfig(500000), min_phase_us=phase,
                     rest_confirm_us=round(200000*scale), start_confirm_us=round(200000*scale))
    rep = metrics(analyze(*inputs(times, [0, 0, 20, 40, 60, 40, 20, 0, 0]),
                          config=config)).repetitions[0]
    assert rep.candidate.valid == valid
    # CP0 P6–P8: earliest peak .4*scale, ROM60, duration1*scale.
    if valid:
        check(rep.metrics.rom_rad, pi/3, "rad")
        check(rep.metrics.peak_elevation_rad, pi/3, "rad")
        check(rep.metrics.rep_duration_s, scale, "s")
    else:
        assert rep.metrics.rep_duration_s.reason == "phase_too_short"
        assert isnan(rep.metrics.rep_duration_s.value)


@pytest.mark.parametrize("minimum,valid", [(80, True), (81, False)])
def test_p9_rom_gate(minimum, valid):
    rep = metrics(analyze(*inputs(), config=replace(ExerciseConfig(500000),
                                                  min_rom_rad=minimum*pi/180))).repetitions[0]
    assert rep.metrics.rom_rad.valid == valid
    if not valid:
        assert rep.metrics.rom_rad.reason == "rom_below_minimum"


@pytest.mark.parametrize("case", ["row", "speed", "gap", "start", "end", "plane", "tail"])
def test_excluded_candidates_never_leak_partial_metrics(case):
    e, s = inputs(invalid=7 if case == "row" else 14 if case == "tail" else None,
                  direction=45 if case == "plane" else 0)
    window = None
    if case == "speed":
        mask, reasons = s.valid.copy(), list(s.reason)
        mask[6], reasons[6] = False, "synthetic_speed_qc"
        s = replace(s, valid=mask, reason=tuple(reasons))
    if case == "gap":
        e, s = inputs([t+400000 if t >= 1000000 else t for t in TIMES])
    if case == "start":
        window = (400000, 2400000)
    if case == "end":
        window = (-400000, 1800000)
    segmentation = analyze(e, s, window=window)
    result = metrics(segmentation)
    # CP0 C11–C19 and P exclusions: retain all reasons/QC, zero numeric contribution.
    assert result.segmentation is segmentation
    assert result.repetitions and not any(rep.candidate.valid for rep in result.repetitions)
    for rep in result.repetitions:
        assert not rep.hold_runs_us and not rep.hold_intervals
        for field in fields(rep.metrics):
            metric = getattr(rep.metrics, field.name)
            assert not metric.valid and isnan(metric.value)
            assert metric.reason == rep.candidate.reasons[0]


def test_assumed_evidence_and_quiet_global_failure():
    result = metrics(analyze(*inputs(assumed=True)))
    assert result.repetitions[0].metrics.rom_rad.evidence_label == "Assumed/Experimental"
    assert not result.repetitions[0].metrics.rom_rad.anatomical_eligible
    assert not metrics(analyze(*inputs([0, 200000], [0, 0]))).repetitions
    e, s = inputs()
    e = replace(e, thorax_alignment=None)
    s = replace(s, elevation_result=e)
    result = metrics(analyze(e, s))
    assert not result.segmentation.analysis_valid and not result.repetitions


def test_forged_segmentation_rejected_before_metrics():
    segmentation = analyze(*inputs())
    forged = replace(segmentation, candidates=(replace(segmentation.candidates[0], end_us=2400000),))
    with pytest.raises(ValueError, match="segmentation"):
        metrics(forged)


def two_reps(*, invalid=None, exclude_middle=False):
    times = TIMES + [2600000, 2800000, 3000000, 3200000, 3400000, 3600000, 3800000,
                     4000000, 4200000, 4400000, 4600000, 4800000, 5000000]
    angles = ANGLES + [0, 0, 0, 20, 40, 60, 60, 60, 60, 40, 20, 0, 0]
    if exclude_middle:
        # Third A, with a plane-excluded B between the two eligible repetitions.
        times += [t+5600000 for t in TIMES]
        angles += ANGLES
    direction = {i: 45 for i in range(18, 27)} if exclude_middle else 0
    return analyze(*inputs(times, angles, invalid=invalid, direction=direction))


@pytest.mark.parametrize("invalid", [None, 15])
def test_adjacent_rest_requires_continuity(invalid):
    result = metrics(two_reps(invalid=invalid))
    rest = result.repetitions[1].metrics.preceding_rest_duration_s
    # CP0 A+B: next3.2 - previous2.2 = 1 s; QC at2.6 cannot be bridged.
    if invalid is None:
        check(rest, 1., "s")
    else:
        assert not rest.valid and rest.reason == "rest_interrupted" and isnan(rest.value)


def test_rest_cannot_span_excluded_candidate():
    result = metrics(two_reps(exclude_middle=True))
    assert [rep.candidate.valid for rep in result.repetitions] == [True, False, True]
    rest = result.repetitions[2].metrics.preceding_rest_duration_s
    assert not rest.valid and rest.reason == "rest_interrupted"


def test_hold_runs_split_on_motion_and_do_not_merge_short_runs():
    times = [-400000, -200000, 0, 200000, 400000, 600000, 800000,
             1100000, 1400000, 1600000, 1900000, 2200000, 2400000, 2600000, 2800000, 3000000]
    angles = [0, 0, 0, 20, 40, 60, 80, 80, 80, 78, 78, 78, 60, 40, 0, 0]
    rep = metrics(analyze(*inputs(times, angles))).repetitions[0]
    # Extension of P0: two static .6 s runs separated by 10deg/s motion.
    assert rep.hold_runs_us == ((800000, 1400000), (1600000, 2200000))
    check(rep.metrics.hold_duration_s, 1.2, "s")
    check(rep.metrics.return_duration_s, .8, "s")
    shortened = replace(ExerciseConfig(500000), min_hold_us=600001)
    rep = metrics(analyze(*inputs(times, angles), config=shortened)).repetitions[0]
    # Each run misses independently; their sum cannot qualify a hold.
    assert not rep.hold_runs_us
    check(rep.metrics.hold_duration_s, 0., "s")


def test_pause_below_peak_band_is_not_hold():
    times = [-400000, -200000, 0, 200000, 400000, 600000, 900000, 1200000,
             1400000, 1600000, 1800000, 2000000, 2200000, 2400000]
    angles = [0, 0, 0, 20, 40, 60, 60, 60, 80, 60, 40, 20, 0, 0]
    rep = metrics(analyze(*inputs(times, angles))).repetitions[0]
    # P0 band rule extension: .6 s static pause at60 < peak80-band5.
    check(rep.metrics.hold_duration_s, 0., "s")
    check(rep.metrics.elevation_duration_s, 1.2, "s")


def test_hold_crosses_peak_and_can_empty_chronological_rise():
    times = [-400000, -200000, 0, 200000, 400000, 700000, 1000000,
             1300000, 1600000, 1800000, 2000000, 2200000, 2400000]
    angles = [0, 0, 0, 77, 78, 80, 80, 79, 78, 60, 40, 0, 0]
    # CP0 ownership rule extension: start .2 to1.6 within5deg, all speeds <10deg/s.
    config = replace(ExerciseConfig(500000), hold_speed_limit_rads=10*pi/180)
    rep = metrics(analyze(*inputs(times, angles), config=config)).repetitions[0]
    assert rep.hold_runs_us == ((200000, 1600000),)
    check(rep.metrics.hold_duration_s, 1.4, "s")
    check(rep.metrics.elevation_duration_s, 0., "s")
    assert rep.elevation_intervals == ()
    assert rep.metrics.elevation_speed_mean_rads.reason == "empty_phase"
    assert rep.metrics.elevation_speed_max_rads.reason == "empty_phase"
    check(rep.metrics.return_duration_s, .6, "s")


def test_gap_equality_integrates_observed_hold_time():
    times = [t+300000 if t >= 1000000 else t for t in TIMES]
    rep = metrics(analyze(*inputs(times))).repetitions[0]
    # CP0 C18: exact .5s gap is valid; observed hold .9, not nominal .6.
    check(rep.metrics.hold_duration_s, .9, "s")
    check(rep.metrics.rep_duration_s, 2.3, "s")
    check(rep.metrics.rep_speed_mean_rads, (140/2.3)*pi/180, "rad/s")


@pytest.mark.parametrize("side,exercise,sign", [("right", "flexion", -1),
                                            ("left", "abduction", 1), ("right", "abduction", 1)])
def test_p0_side_plane_and_quaternion_sign_invariance(side, exercise, sign):
    rep = metrics(analyze(*inputs(side=side, exercise=exercise, sign=sign),
                          side=side, exercise=exercise)).repetitions[0]
    # CP0 A applies to both declared sides/planes and either quaternion sign.
    check(rep.metrics.rom_rad, 80*pi/180, "rad")
    check(rep.metrics.rep_speed_mean_rads, 70*pi/180, "rad/s")
    check(rep.metrics.hold_duration_s, .6, "s")


def test_p0_all_phase_speed_statistics_and_exact_membership():
    rep = metrics(analyze(*inputs())).repetitions[0]
    # CP0 A: rise3 moving intervals, hold3 static, return4 moving.
    assert rep.elevation_intervals == (3, 4, 5)
    assert rep.hold_intervals == (6, 7, 8)
    assert rep.return_intervals == (9, 10, 11, 12)
    for phase in ("elevation", "return"):
        for statistic in ("mean", "max"):
            check(getattr(rep.metrics, f"{phase}_speed_{statistic}_rads"), 100*pi/180, "rad/s")


def test_p10_phase_speed_denominators_and_maxima():
    times = [-400000, -200000, 0, 200000, 500000, 800000, 1000000, 1200000, 1400000]
    angles = [0, 0, 20, 40, 80, 80, 40, 0, 0]
    rep = metrics(analyze(*inputs(times, angles))).repetitions[0]
    # CP0 P10: rise integrates60deg/.5s; return80deg/.7s includes .3s pause.
    check(rep.metrics.elevation_speed_mean_rads, 120*pi/180, "rad/s")
    check(rep.metrics.elevation_speed_max_rads, (400/3)*pi/180, "rad/s")
    check(rep.metrics.return_speed_mean_rads, (800/7)*pi/180, "rad/s")
    check(rep.metrics.return_speed_max_rads, 200*pi/180, "rad/s")


def test_mutated_nested_arrays_cannot_bypass_qc():
    segmentation = analyze(*inputs())
    segmentation.angular_speed_result.relative_angular_speed_rads[6] = np.nan
    with pytest.raises(ValueError, match="claimed valid"):
        metrics(segmentation)
