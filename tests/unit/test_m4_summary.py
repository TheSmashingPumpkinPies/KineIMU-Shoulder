"""CP4 U0–U10 independent truths; catch pooled strata and wrong denominators."""

from dataclasses import replace
from importlib.util import find_spec
from math import isnan, pi, sqrt

import pytest
from test_m4_segmentation import ANGLES, SHA_A, SHA_B, TIMES, analyze, inputs
from test_m4_thorax import setup

from kineimu_shoulder.exercise import ExerciseConfig, compute_repetition_metrics
from kineimu_shoulder.shoulder import long_axis_elevation, relative_angular_speed

B_TIMES = [2600000, 2800000, 3000000, 3200000, 3400000, 3600000, 3800000,
           4000000, 4200000, 4400000, 4600000, 4800000, 5000000]
B_ANGLES = [0, 0, 0, 20, 40, 60, 60, 60, 60, 40, 20, 0, 0]


def api():
    assert find_spec("kineimu_shoulder.summary") is not None, "CP4 summary API is missing"
    from kineimu_shoulder import summary
    return summary


def context(**changes):
    return replace(api().SummaryContext(
        session_start_utc="2026-09-26T00:00:00Z", calibration_ids=("cal-A", "cal-B"),
        alignment_sha256=(SHA_A, SHA_B), backend=("known-direct-input", "1.0", SHA_A),
        grid_policy=("explicit caller grid", "1.0"), source_generator=("known-exercises", "1.0"),
    ), **changes)


def summarize(seg=None, *, ctx=None, proxy=None):
    return api().summarize_exercise(proxy or compute_repetition_metrics(seg or analyze(*inputs())),
                                    context=ctx or context())


def stat(result, name):
    return result.statistics[name][0]


def number(metric, value):
    assert metric.valid and metric.reason == "ok"
    tolerance = 1e-12 if metric.unit in ("s", "s^-1", "dimensionless") else 1e-10
    assert metric.value == pytest.approx(value, abs=tolerance, rel=0)


def pair_seg(**kwargs):
    return analyze(*inputs(TIMES+B_TIMES, ANGLES+B_ANGLES, **kwargs))


def test_u0_u1_u10_zero_one_global_missing():
    quiet = summarize(analyze(*inputs([0, 200000, 400000], [0, 0, 0])))
    assert (quiet.detected_count, quiet.valid_count, quiet.excluded_count) == (0, 0, 0)
    assert stat(quiet, "rom_rad").n == 0
    assert stat(quiet, "rom_rad").mean.reason == "no_valid_repetitions"
    assert quiet.active_cadence.reason == "empty_active_time"
    single = summarize()
    # U1 / A: 80 degree ROM, 2 seconds active; n=1 cannot estimate sample SD.
    number(stat(single, "rom_rad").mean, 80*pi/180)
    number(single.active_cadence, .5)
    assert single.rom_sd.reason == "insufficient_repetitions"
    assert single.rom_cv.reason == "insufficient_repetitions"
    assert (single.proxy_valid_count, single.proxy_unavailable_count) == (0, 1)
    e, _ = inputs()
    kwargs = dict(thorax_alignment=None, humerus_alignment=e.humerus_alignment,
                  side=e.side, source_type=e.source_type, max_sample_gap_us=e.max_sample_gap_us)
    e2 = long_axis_elevation(e.relative_orientation, **kwargs)
    s2 = relative_angular_speed(e.relative_orientation, **kwargs)
    invalid = summarize(analyze(e2, s2))
    assert invalid.detected_count is invalid.valid_count is invalid.excluded_count is None
    assert not invalid.analysis_valid


def test_u2_arithmetic_means_sample_sd_and_active_denominator():
    result = summarize(pair_seg())
    assert (result.detected_count, result.valid_count, result.excluded_count) == (2, 2, 0)
    # U2 analytical (80+60)/2; sample SD sqrt(100+100); cadence 2/(2+1.6).
    for name, mean, maximum in [("rom_rad", 70*pi/180, 80*pi/180),
                                ("peak_elevation_rad", 70*pi/180, 80*pi/180),
                                ("rep_duration_s", 1.8, 2), ("hold_duration_s", .6, .6),
                                ("elevation_duration_s", .5, .6), ("return_duration_s", .7, .8),
                                ("rep_speed_mean_rads", 66.25*pi/180, 70*pi/180),
                                ("return_speed_mean_rads", 100*pi/180, 100*pi/180)]:
        item = stat(result, name)
        assert item.n == 2
        number(item.mean, mean)
        number(item.maximum, maximum)
    number(result.rom_range, 20*pi/180)
    number(result.rom_sd, 10*sqrt(2)*pi/180)
    number(result.rom_cv, sqrt(2)/7)
    number(result.active_time_s, 3.6)
    number(result.active_cadence, 5/9)
    number(result.analysis_window_duration_s, 5.4)
    rest = stat(result, "preceding_rest_duration_s")
    assert rest.n == 1
    number(rest.mean, 1)
    assert result.input_result.segmentation.candidates == pair_seg().candidates


def test_u3_exclusions_and_partial_reason_ids_never_contribute():
    directions = {i: 45 for i in range(len(TIMES)+3, len(TIMES+B_TIMES))}
    result = summarize(pair_seg(direction=directions))
    assert (result.detected_count, result.valid_count, result.excluded_count) == (2, 1, 1)
    number(stat(result, "rom_rad").mean, 80*pi/180)  # U3: only A contributes.
    assert stat(result, "preceding_rest_duration_s").n == 0
    assert result.exclusion_reasons["plane_mismatch"] == (result.input_result.repetitions[1].candidate.id,)
    partial = summarize(analyze(*inputs(), window=(400000, 1800000)))
    assert partial.partial_start_count == partial.partial_end_count == 1
    assert stat(partial, "rom_rad").n == 0
    assert set(partial.exclusion_reasons) >= {"partial_start", "partial_end"}
    assert partial.exclusion_reason_counts["partial_start"] == 1
    assert partial.exclusion_reason_counts["partial_end"] == 1
    assert sum(partial.exclusion_reason_counts.values()) > partial.excluded_count


def test_u4_proxy_denominator_and_evidence_strata():
    module, metrics, trace, _, _ = setup((10, 0, 0), times=TIMES+B_TIMES, angles=ANGLES+B_ANGLES)
    trace = replace(trace, heading_evidence=replace(trace.heading_evidence, covered_window_us=(-400000, 2400000)))
    result = summarize(proxy=module.compute_thorax_excursion(metrics, trace=trace))
    assert (result.proxy_valid_count, result.proxy_unavailable_count) == (1, 1)
    assert stat(result, "thorax_extension_magnitude_rad").n == 1
    number(stat(result, "thorax_extension_magnitude_rad").mean, 10*pi/180)  # U4/T1.
    assumed = replace(trace, heading_evidence=replace(trace.heading_evidence, status="assumed"))
    result = summarize(proxy=module.compute_thorax_excursion(metrics, trace=assumed))
    assert stat(result, "thorax_extension_magnitude_rad").mean.evidence_label == "Assumed/Experimental"
    assert stat(result, "rom_rad").mean.evidence_label == "Derived"


@pytest.mark.parametrize("floor,reason", [(1, "cv_mean_near_zero"), (.9, "ok")])
def test_u5_cv_floor(floor, reason):
    # U5 low-amplitude override: two real complete reps with ROM .5 and 1.5 degrees.
    angles = [a*.5/80 for a in ANGLES]+[a*1.5/60 for a in B_ANGLES]
    config = replace(ExerciseConfig(500000), rest_level_rad=0, start_level_rad=.05*pi/180,
                     plane_min_elevation_rad=.1*pi/180, min_peak_rad=.2*pi/180,
                     min_rom_rad=.1*pi/180, hold_band_rad=.01*pi/180, cv_mean_floor_rad=floor*pi/180)
    result = summarize(analyze(*inputs(TIMES+B_TIMES, angles), config=config))
    number(stat(result, "rom_rad").mean, pi/180)  # U5 mean (0.5+1.5)/2.
    number(result.rom_sd, pi/(180*sqrt(2)))
    assert result.rom_cv.reason == reason


def test_u6_u8_u9_ordering_difference_and_unavailable():
    first = summarize(replace(analyze(*inputs()), session_id="A"))
    last = summarize(replace(analyze(*inputs(B_TIMES, B_ANGLES)), session_id="B"),
                     ctx=context(session_start_utc="2026-09-27T00:00:00+00:00"))
    comparisons = api().compare_summaries([last, first])
    item = comparisons[0]
    assert (item.earlier_id, item.later_id) == ("A", "B") and item.comparable
    difference = item.differences["rom_rad"][0]
    number(difference.difference, -20*pi/180)  # U6 later60-earlier80.
    assert (difference.earlier_n, difference.later_n) == (1, 1)
    quiet = summarize(replace(analyze(*inputs([0, 200000, 400000], [0, 0, 0])), session_id="A"))
    item = api().compare_summaries([quiet, last])[0]
    assert item.differences["rom_rad"][0].difference.reason == "comparison_metric_unavailable"
    equal = replace(last, context=context())
    assert api().compare_summaries([equal, first])[0].earlier_id == "A"
    with pytest.raises(ValueError, match="duplicate"):
        api().compare_summaries([first, first])
    missing = summarize(ctx=context(session_start_utc=None))
    with pytest.raises(ValueError, match="UTC"):
        api().compare_summaries([missing, last])


@pytest.mark.parametrize("field,value,key", [
    ("calibration_ids", ("new", "cal-B"), "calibration_ids"),
    ("alignment_sha256", (SHA_B, SHA_B), "alignment_sha256"),
    ("backend", ("other", "1.0", SHA_A), "backend"),
    ("grid_policy", ("different", "1.0"), "grid_policy"),
    ("source_generator", ("other", "1.0"), "source_generator"),
])
def test_u7_explicit_context_keys(field, value, key):
    first = summarize(replace(analyze(*inputs()), session_id="A"))
    last = summarize(replace(analyze(*inputs()), session_id="B"), ctx=context(**{field: value}))
    item = api().compare_summaries([last, first])[0]
    assert not item.comparable and item.differing_keys == (key,)
    assert item.differences is None


def rebuild(e, *, relative=None, **changes):
    kwargs = dict(thorax_alignment=e.thorax_alignment, humerus_alignment=e.humerus_alignment,
                  side=e.side, source_type=e.source_type, max_sample_gap_us=e.max_sample_gap_us)
    kwargs.update(changes)
    r = relative or e.relative_orientation
    return long_axis_elevation(r, **kwargs), relative_angular_speed(r, **kwargs)


@pytest.mark.parametrize("change,keys", [
    ("side", ("alignment", "side")), ("exercise", ("exercise",)),
    ("threshold", ("configuration",)), ("gap", ("configuration", "timing_policy")),
    ("calibration", ("calibration_sha256",)), ("alignment", ("alignment",)),
    ("remount", ("alignment", "evidence_stratum")), ("neutral", ("alignment",)),
    ("clock", ("clock_methods",)), ("heading", ("heading_method",)),
    ("source", ("source_type",)), ("evidence", ("clock_methods", "evidence_stratum")),
    ("protocol", ("protocol",)),
])
def test_u7_upstream_comparability_keys(change, keys):
    first = summarize(replace(analyze(*inputs()), session_id="A"))
    e, speed = inputs()
    config = ExerciseConfig(500000)
    side, exercise = "left", "flexion"
    if change == "side":
        side = "right"
        e, speed = inputs(side=side)
    if change == "exercise":
        exercise = "abduction"
        e, speed = inputs(exercise=exercise)
    if change == "threshold":
        config = replace(config, min_peak_rad=65*pi/180)
    if change == "gap":
        config = ExerciseConfig(600000)
        e, speed = inputs(gap=600000)
    if change in ("alignment", "remount", "neutral"):
        updates = {"alignment_id": "changed"} if change == "alignment" else (
            {"remounted": True} if change == "remount" else {"neutral_pose": "changed neutral"})
        e, speed = rebuild(e, thorax_alignment=replace(e.thorax_alignment, **updates))
    if change in ("clock", "evidence"):
        clock = replace(e.relative_orientation.thorax_clock_map,
                        **({"method": "changed method"} if change == "clock" else {"status": "assumed"}))
        e, speed = rebuild(e, relative=replace(e.relative_orientation, thorax_clock_map=clock))
    if change == "heading":
        heading = replace(e.relative_orientation.heading_relation, method="changed method")
        e, speed = rebuild(e, relative=replace(e.relative_orientation, heading_relation=heading))
    if change == "source":
        e, speed = rebuild(e, source_type="recorded")
    seg = analyze(e, speed, config=config, side=side, exercise=exercise)
    if change == "calibration":
        seg = replace(seg, calibration_sha256=(SHA_B, SHA_B))
    if change == "protocol":
        seg = replace(seg, protocol_version="2.0")
    last = summarize(replace(seg, session_id="B"))
    item = api().compare_summaries([last, first])[0]
    assert not item.comparable and item.differing_keys == keys and item.differences is None


def test_u6_changed_recording_hashes_are_lineage_not_comparison_keys():
    first = summarize(replace(analyze(*inputs()), session_id="A"))
    e, _ = inputs(B_TIMES, B_ANGLES)
    r = e.relative_orientation
    # Different immutable recordings, identical processing methods/artifacts.
    new_a, new_b = "c"*64, "d"*64
    r = replace(r, thorax_source_sha256=new_a, humerus_source_sha256=new_b,
                thorax_clock_map=replace(r.thorax_clock_map, source_sha256=new_a),
                humerus_clock_map=replace(r.humerus_clock_map, source_sha256=new_b),
                heading_relation=replace(r.heading_relation, source_sha256=new_a))
    e, speed = rebuild(e, relative=r,
                       thorax_alignment=replace(e.thorax_alignment, source_sha256=new_a),
                       humerus_alignment=replace(e.humerus_alignment, source_sha256=new_b))
    last = summarize(replace(analyze(e, speed), session_id="B"))
    item = api().compare_summaries([last, first])[0]
    assert item.comparable and item.differing_keys == ()
    number(item.differences["rom_rad"][0].difference, -20*pi/180)  # U6.
    assert item.later.input_result.segmentation.elevation_result.thorax_source_sha256 == new_a


def test_individual_empty_phase_denominators_and_qc_window_support():
    # P1 no hold then B with a hold: hold duration n2, hold speed n1.
    times = TIMES[:7]+[1000000, 1200000, 1400000, 1600000, 1800000]+B_TIMES
    angles = ANGLES[:7]+[60, 40, 20, 0, 0]+B_ANGLES
    result = summarize(analyze(*inputs(times, angles, gap=1000000), config=ExerciseConfig(1000000)))
    assert stat(result, "hold_duration_s").n == 2
    assert stat(result, "hold_speed_mean_rads").n == 1
    number(stat(result, "hold_duration_s").mean, .3)  # (0+.6)/2 from P1/B.
    number(stat(result, "hold_speed_mean_rads").mean, 0)
    qc = summarize(pair_seg(invalid=7))
    assert qc.valid_count == 1
    number(qc.active_time_s, 1.6)  # U3 counterpart: only B survives QC.
    number(qc.analysis_window_duration_s, 5.4)
    assert qc.input_result.segmentation.observed_invalid_duration_s > 0
    assert stat(qc, "preceding_rest_duration_s").n == 0


def test_proxy_missing_and_invalid_cannot_become_zero_means():
    result = summarize()
    metric = stat(result, "thorax_extension_magnitude_rad")
    assert metric.n == 0 and metric.mean.reason == "no_valid_proxy" and isnan(metric.mean.value)
    assert not result.rom_sd.valid and isnan(result.rom_sd.value)


def test_all_pairs_with_equal_time_use_id_and_keep_each_window():
    seg = analyze(*inputs())
    summaries = [summarize(replace(seg, session_id=name)) for name in ("C", "A", "B")]
    pairs = api().compare_summaries(summaries)
    assert [(p.earlier_id, p.later_id) for p in pairs] == [("A", "B"), ("A", "C"), ("B", "C")]
    assert all(p.comparable for p in pairs)
    assert api().compare_summaries([]) == ()
    for pair in pairs:
        number(pair.differences["rom_rad"][0].difference, 0)  # Identical A truths, no pooling.
        assert pair.earlier.valid_count == pair.later.valid_count == 1


def test_proxy_drift_method_and_assumption_are_comparison_keys():
    module, metrics, trace, _, _ = setup((10, 0, 0))
    first = summarize(proxy=module.compute_thorax_excursion(metrics, trace=trace))
    seg = replace(metrics.segmentation, session_id="B")
    other_metrics = compute_repetition_metrics(seg)
    changed = replace(trace, drift_evidence=replace(trace.drift_evidence, method="other", status="assumed"))
    last = summarize(proxy=module.compute_thorax_excursion(other_metrics, trace=changed))
    pair = api().compare_summaries([last, first])[0]
    assert not pair.comparable and pair.differing_keys == ("proxy_policy",)
    assert pair.differences is None


@pytest.mark.parametrize("changes", [
    {"backend": ("name", "1", "not-a-hash")}, {"source_generator": None},
    {"grid_policy": ("", "1")}, {"calibration_ids": ("", "B")},
    {"alignment_sha256": (SHA_A, "bad")},
])
def test_incomplete_processing_context_rejected(changes):
    with pytest.raises(ValueError):
        summarize(ctx=context(**changes))


def test_forged_metrics_or_summary_rejected():
    metrics = compute_repetition_metrics(analyze(*inputs()))
    rep = metrics.repetitions[0]
    bad = replace(metrics, repetitions=(replace(rep, metrics=replace(
        rep.metrics, rom_rad=replace(rep.metrics.rom_rad, value=0))),))
    with pytest.raises(ValueError, match="metrics"):
        api().summarize_exercise(bad, context=context())
    valid = summarize()
    with pytest.raises(ValueError, match="summary"):
        api().compare_summaries([replace(valid, valid_count=99)])


@pytest.mark.parametrize("start", ["2026-09-26T00:00:00", "garbage", "2026-09-26T08:00:00+08:00"])
def test_non_utc_start_is_input_error(start):
    with pytest.raises(ValueError, match="UTC"):
        summarize(ctx=context(session_start_utc=start))
