"""CP3 independent T0–T15 truths in fixtures/M4_KNOWN_EXERCISES.md."""

import warnings
from dataclasses import replace
from importlib.util import find_spec
from math import cos, pi, sin

import numpy as np
import pytest
from test_m4_segmentation import ANGLES, IDENTITY, SHA_A, TIMES, analyze, inputs

from kineimu_shoulder import exercise
from kineimu_shoulder.frames import compose_quaternions
from kineimu_shoulder.relative_orientation import SegmentOrientationStream


def api():
    assert find_spec("kineimu_shoulder.thorax") is not None, "CP3 thorax API is missing"
    from kineimu_shoulder import thorax
    return thorax


def axis(index, degrees):
    q = [cos(degrees*pi/360), 0., 0., 0.]
    q[index] = sin(degrees*pi/360)
    return q


def setup(components=(0, 0, 0), baseline=IDENTITY, *, times=TIMES, angles=ANGLES,
          side="left", sign=1):
    module = api()
    e, speed = inputs(times, angles, side=side)
    config = replace(exercise.ExerciseConfig(500000), max_thorax_drift_rad=pi/180)
    metrics = exercise.compute_repetition_metrics(analyze(e, speed, config=config, side=side))
    quaternions = []
    for t in times:
        local = t if t < 2600000 else t-3000000
        f = max(0, min(1, (local-200000)/600000, (2200000-local)/800000))
        extension, lateral, axial = (v*f for v in components)
        # CP0 T4: Hamilton qZ(gamma) qY(beta) qX(alpha), independently constructed.
        d = compose_quaternions(axis(3, axial), compose_quaternions(axis(2, -extension), axis(1, -lateral)))
        q0 = baseline if t < 2600000 else compose_quaternions(axis(3, 40), axis(1, 25))
        quaternions.append(sign*compose_quaternions(q0, d))
    stream = SegmentOrientationStream("A", "A", 0, "Wa", SHA_A,
                                      np.array(times, dtype=np.int64), np.array(quaternions))
    relative = e.relative_orientation
    heading = module.ThoraxHeadingEvidence("Wa", "synthetic heading", SHA_A,
                                           (times[0], times[-1]), "supported")
    drift = module.ThoraxDriftEvidence("Wa", "synthetic zero drift", SHA_A,
                                       (times[0], times[-1]), 0., "supported")
    kwargs = dict(common_time_us=e.common_time_us, clock_map=relative.thorax_clock_map,
                  alignment=e.thorax_alignment, calibration_sha256=SHA_A,
                  configuration=config, max_timing_uncertainty_us=relative.max_timing_uncertainty_us,
                  heading_evidence=heading, drift_evidence=drift)
    trace = module.prepare_thorax_common_grid(stream, **kwargs)
    return module, metrics, trace, stream, kwargs


def proxy(module, metrics, trace):
    result = module.compute_thorax_excursion(metrics, trace=trace)
    assert result.metrics is metrics and result.trace is trace
    return result.repetitions[0]


@pytest.mark.parametrize("components", [(0, 0, 0), (10, 0, 0), (0, 15, 0), (0, 0, 20),
                                        (20, 10, 30), (-10, 0, 0), (0, -15, 0), (0, 0, -20)])
@pytest.mark.parametrize("baseline,side,sign", [(IDENTITY, "left", 1),
    (compose_quaternions(axis(3, 40), axis(1, 25)), "right", -1)])
def test_t0_to_t6_axes_order_baseline_sign(components, baseline, side, sign):
    module, metrics, trace, _, _ = setup(components, baseline, side=side, sign=sign)
    rep = proxy(module, metrics, trace)
    for name, expected in zip(("extension", "lateral_flexion", "axial_rotation"), components, strict=True):
        value = getattr(rep, name)
        assert value.valid and value.reason == "ok" and value.unit == "rad"
        assert value.evidence_label == "Derived" and not value.anatomical_eligible
        # CP0 T0–T6: signed extrema include baseline zero; magnitude is max absolute, not range.
        np.testing.assert_allclose([value.min_rad, value.max_rad, value.magnitude_rad],
            np.array([min(0, expected), max(0, expected), abs(expected)])*pi/180, atol=1e-10, rtol=0)


def test_t7_each_rep_resets_baseline():
    times = TIMES + [v+3000000 for v in TIMES]
    module, metrics, trace, _, _ = setup((20, 10, 30), times=times, angles=ANGLES+ANGLES)
    result = module.compute_thorax_excursion(metrics, trace=trace)
    assert len(result.repetitions) == 2
    for rep in result.repetitions:
        # CP0 T7: each new q0 cancels before decomposition.
        assert rep.extension.magnitude_rad == pytest.approx(20*pi/180, abs=1e-10)


def unavailable(rep, reason):
    assert reason in rep.reasons
    for name in ("extension", "lateral_flexion", "axial_rotation"):
        value = getattr(rep, name)
        assert not value.valid and value.reason == rep.reasons[0]
        assert all(np.isnan(v) for v in (value.min_rad, value.max_rad, value.magnitude_rad))


@pytest.mark.parametrize("case,reason", [("singular", "thorax_decomposition_singular"),
                                        ("branch", "thorax_branch_crossing")])
def test_t8_t9_singular_and_branch(case, reason):
    module, metrics, _, stream, kwargs = setup()
    q = stream.quaternion_wsegment.copy()
    if case == "singular":
        q[6] = axis(2, 90)
    else:
        q[6], q[7] = axis(3, 179), axis(3, 181)
    trace = module.prepare_thorax_common_grid(replace(stream, quaternion_wsegment=q), **kwargs)
    unavailable(proxy(module, metrics, trace), reason)
    assert metrics.repetitions[0].candidate.valid and metrics.repetitions[0].metrics.rom_rad.valid


@pytest.mark.parametrize("change", ["missing", "grid", "hash", "alignment", "map", "world", "expired", "remount"])
def test_t10_t15_binding(change):
    module, metrics, trace, stream, kwargs = setup()
    if change == "missing":
        trace = None
    else:
        if change == "grid":
            kwargs["common_time_us"] = kwargs["common_time_us"] + 1
        if change == "hash":
            stream = replace(stream, source_sha256="c"*64)
        if change == "alignment":
            kwargs["alignment"] = replace(kwargs["alignment"], alignment_id="different")
        if change == "expired":
            kwargs["alignment"] = replace(kwargs["alignment"], validity="expired")
        if change == "remount":
            kwargs["alignment"] = replace(kwargs["alignment"], remounted=True)
        if change == "map":
            kwargs["clock_map"] = replace(kwargs["clock_map"], intercept_us=1.)
        if change == "world":
            stream = replace(stream, world_id="other")
        trace = module.prepare_thorax_common_grid(stream, **kwargs)
    unavailable(proxy(module, metrics, trace),
                "thorax_trace_missing" if change == "missing" else "thorax_trace_incompatible")
    assert metrics.segmentation.valid_count == 1


def test_t11_original_qc_kept_and_closed_rep_unavailable():
    module, metrics, _, stream, kwargs = setup()
    valid = np.ones(len(TIMES), dtype=np.bool_)
    valid[7] = False
    reasons = tuple("clipping" if i == 7 else "valid" for i in range(len(TIMES)))
    trace = module.prepare_thorax_common_grid(stream, source_valid=valid, source_reason=reasons, **kwargs)
    rep = proxy(module, metrics, trace)
    unavailable(rep, "thorax_invalid_row")
    assert rep.offending_rows == ((7, "source_qc:clipping"),)
    assert trace.source_reason == reasons and not trace.source_valid[7]


@pytest.mark.parametrize("field,reason", [("heading_evidence", "thorax_heading_missing"),
                                         ("drift_evidence", "thorax_drift_unbounded")])
def test_t12_missing_evidence(field, reason):
    module, metrics, _, stream, kwargs = setup()
    kwargs[field] = None
    trace = module.prepare_thorax_common_grid(stream, **kwargs)
    unavailable(proxy(module, metrics, trace), reason)


@pytest.mark.parametrize("bound,passed", [(pi/180, True), (1.01*pi/180, False)])
def test_t13_drift_equality(bound, passed):
    module, metrics, _, stream, kwargs = setup((10, 0, 0))
    kwargs["drift_evidence"] = replace(kwargs["drift_evidence"], bound_rad=bound)
    trace = module.prepare_thorax_common_grid(stream, **kwargs)
    rep = proxy(module, metrics, trace)
    if passed:
        assert rep.extension.valid
    else:
        unavailable(rep, "thorax_drift_exceeded")


@pytest.mark.parametrize("field", ["heading_evidence", "drift_evidence"])
def test_t14_assumption_retained(field):
    module, metrics, _, stream, kwargs = setup((10, 0, 0))
    kwargs[field] = replace(kwargs[field], status="assumed", method="explicit illustrative assumption")
    trace = module.prepare_thorax_common_grid(stream, **kwargs)
    rep = proxy(module, metrics, trace)
    assert rep.extension.valid and rep.extension.evidence_label == "Assumed/Experimental"
    assert not rep.extension.anatomical_eligible
    assert getattr(trace, field).method == "explicit illustrative assumption"


@pytest.mark.parametrize("field,reason", [("heading_evidence", "thorax_heading_missing"),
                                         ("drift_evidence", "thorax_drift_unbounded")])
def test_evidence_must_cover_whole_rep(field, reason):
    module, metrics, _, stream, kwargs = setup()
    kwargs[field] = replace(kwargs[field], covered_window_us=(400000, 2200000))
    trace = module.prepare_thorax_common_grid(stream, **kwargs)
    unavailable(proxy(module, metrics, trace), reason)


def test_explicit_slerp_provenance_clock_original_brackets_and_no_extrapolation():
    module, _, _, stream, kwargs = setup()
    # Analytical constant-axis 20 degrees over 0.4s: midpoint is 10 degrees.
    stream = replace(stream, timestamp_us=np.array([0, 400000], dtype=np.int64),
                     quaternion_wsegment=np.array([axis(3, 0), axis(3, 20)]))
    clock = replace(kwargs["clock_map"], slope=2., intercept_us=100000.)
    grid = np.array([0, 100000, 500000, 900000, 1000000], dtype=np.int64)
    kwargs.update(clock_map=clock, common_time_us=grid,
                  configuration=replace(kwargs["configuration"], max_sample_gap_us=800000))
    trace = module.prepare_thorax_common_grid(stream, **kwargs)
    np.testing.assert_array_equal(trace.original_stream.timestamp_us, [0, 400000])
    np.testing.assert_array_equal(trace.mapped_time_us, [100000, 900000])
    assert trace.bracket_indices == (None, (0, 0), (0, 1), (1, 1), None)
    assert trace.interpolation_weights == (None, 0., .5, 0., None)
    assert trace.reason == ("outside_stream", "valid", "valid", "valid", "outside_stream")
    np.testing.assert_allclose(trace.quaternion_wat[2], axis(3, 10), atol=1e-12, rtol=0)
    assert trace.configuration_sha256 == kwargs["configuration"].sha256


def test_t11_interpolation_gap_never_bridged():
    module, metrics, _, stream, kwargs = setup()
    keep = [i for i in range(len(TIMES)) if i not in (7, 8)]
    stream = replace(stream, timestamp_us=stream.timestamp_us[keep],
                     quaternion_wsegment=stream.quaternion_wsegment[keep])
    trace = module.prepare_thorax_common_grid(stream, **kwargs)
    rep = proxy(module, metrics, trace)
    unavailable(rep, "thorax_sample_gap")
    assert rep.offending_rows == ((7, "interpolation_gap"), (8, "interpolation_gap"))


def test_missing_drift_limit_and_forged_records_are_input_errors():
    module, metrics, trace, stream, kwargs = setup()
    kwargs["configuration"] = replace(kwargs["configuration"], max_thorax_drift_rad=None)
    with pytest.raises(ValueError, match="drift"):
        module.prepare_thorax_common_grid(stream, **kwargs)
    q = trace.quaternion_wat.copy()
    q[6] = axis(3, 80)
    with pytest.raises(ValueError, match="trace"):
        module.compute_thorax_excursion(metrics, trace=replace(trace, quaternion_wat=q))
    with pytest.raises(ValueError, match="metrics"):
        module.compute_thorax_excursion(replace(metrics, repetitions=()), trace=trace)


def test_excluded_relative_candidate_has_no_proxy():
    module, metrics, trace, _, _ = setup()
    e, speed = inputs(direction=45)
    excluded = exercise.compute_repetition_metrics(analyze(e, speed, config=metrics.segmentation.configuration))
    unavailable(proxy(module, excluded, trace), "plane_mismatch")


@pytest.mark.parametrize("field,value", [("node_id", "other"), ("clock_id", "other"), ("epoch", 1)])
def test_original_identity_must_bind_to_m2(field, value):
    module, metrics, _, stream, kwargs = setup()
    trace = module.prepare_thorax_common_grid(replace(stream, **{field: value}), **kwargs)
    unavailable(proxy(module, metrics, trace), "thorax_trace_incompatible")


def test_t4_consistent_two_body_m2_to_cp3():
    from kineimu_shoulder.relative_orientation import relative_orientation
    from kineimu_shoulder.shoulder import long_axis_elevation, relative_angular_speed
    module, metrics, trace, stream, _ = setup((20, 10, 30))
    e = metrics.segmentation.elevation_result
    r = e.relative_orientation
    q_wh = np.array([compose_quaternions(t, h) for t, h in
                     zip(stream.quaternion_wsegment, r.quaternion_th, strict=True)])
    humerus = replace(stream, node_id="B", clock_id="B", world_id="Wb",
                      source_sha256=r.humerus_source_sha256, quaternion_wsegment=q_wh)
    actual = relative_orientation(stream, humerus, common_time_us=e.common_time_us,
        thorax_clock_map=r.thorax_clock_map, humerus_clock_map=r.humerus_clock_map,
        heading_relation=r.heading_relation, max_interpolation_gap_us=500000, max_timing_uncertainty_us=10.)
    kwargs = dict(thorax_alignment=e.thorax_alignment, humerus_alignment=e.humerus_alignment,
                  side=e.side, source_type=e.source_type, max_sample_gap_us=500000)
    metrics = exercise.compute_repetition_metrics(analyze(long_axis_elevation(actual, **kwargs),
        relative_angular_speed(actual, **kwargs), config=metrics.segmentation.configuration))
    rep = proxy(module, metrics, trace)
    # T4: moving both bodies by q_WT leaves A's relative arm ROM and proxy axes exact.
    assert metrics.repetitions[0].metrics.rom_rad.value == pytest.approx(80*pi/180, abs=1e-10)
    np.testing.assert_allclose([rep.extension.max_rad, rep.lateral_flexion.max_rad, rep.axial_rotation.max_rad],
                               np.array([20, 10, 30])*pi/180, atol=1e-10, rtol=0)


@pytest.mark.parametrize("changes", [{"bound_rad": -1.}, {"bound_rad": float("nan")}])
def test_malformed_drift_bound(changes):
    module, _, _, stream, kwargs = setup()
    kwargs["drift_evidence"] = replace(kwargs["drift_evidence"], **changes)
    with pytest.raises(ValueError, match="drift"):
        module.prepare_thorax_common_grid(stream, **kwargs)


@pytest.mark.parametrize("field,changes", [
    ("heading_evidence", {"method": ""}), ("drift_evidence", {"reference_sha256": "bad"}),
    ("heading_evidence", {"status": "unknown"}),
    ("drift_evidence", {"covered_window_us": (2200000, 200000)}),
])
def test_malformed_evidence_is_input_error(field, changes):
    module, _, _, stream, kwargs = setup()
    kwargs[field] = replace(kwargs[field], **changes)
    with pytest.raises(ValueError, match="evidence"):
        module.prepare_thorax_common_grid(stream, **kwargs)


def test_original_indices_survive_clock_validity_filter():
    module, _, _, stream, kwargs = setup()
    kwargs["clock_map"] = replace(kwargs["clock_map"], valid_device_start_us=0)
    trace = module.prepare_thorax_common_grid(stream, **kwargs)
    assert trace.reason[:2] == ("outside_clock_validity",)*2
    assert trace.bracket_indices[3] == (3, 3)
    # Original indices do not restart at zero after clock validity filtering.
    np.testing.assert_array_equal(trace.mapped_time_us, TIMES)


def test_closed_rep_qc_excludes_confirmation_tail():
    module, metrics, _, stream, kwargs = setup()
    valid = np.ones(len(TIMES), dtype=np.bool_)
    valid[-1] = False
    reasons = ("valid",)*(len(TIMES)-1)+("clipping",)
    trace = module.prepare_thorax_common_grid(stream, source_valid=valid, source_reason=reasons, **kwargs)
    assert proxy(module, metrics, trace).extension.valid


def test_all_failure_causes_retained_in_order():
    module, metrics, _, stream, kwargs = setup()
    valid = np.ones(len(TIMES), dtype=np.bool_)
    valid[7] = False
    kwargs.update(heading_evidence=None, drift_evidence=None)
    trace = module.prepare_thorax_common_grid(stream, source_valid=valid,
        source_reason=tuple("clipping" if i == 7 else "valid" for i in range(len(TIMES))), **kwargs)
    assert proxy(module, metrics, trace).reasons == (
        "thorax_invalid_row", "thorax_heading_missing", "thorax_drift_unbounded")


def test_alignment_was_already_applied_never_apply_twice():
    from kineimu_shoulder.shoulder import long_axis_elevation, relative_angular_speed
    module, metrics, _, stream, kwargs = setup((10, 0, 0))
    alignment = replace(kwargs["alignment"], quaternion_nsegment=tuple(axis(1, 30)))
    kwargs["alignment"] = alignment
    trace = module.prepare_thorax_common_grid(stream, **kwargs)
    e = metrics.segmentation.elevation_result
    bindings = dict(thorax_alignment=alignment, humerus_alignment=e.humerus_alignment,
                    side=e.side, source_type=e.source_type, max_sample_gap_us=500000)
    metrics = exercise.compute_repetition_metrics(analyze(long_axis_elevation(e.relative_orientation, **bindings),
        relative_angular_speed(e.relative_orientation, **bindings), config=kwargs["configuration"]))
    rep = proxy(module, metrics, trace)
    # Post-alignment T1 remains pure extension10 despite nonidentity q_NT metadata.
    assert rep.extension.max_rad == pytest.approx(10*pi/180, abs=1e-10)
    assert rep.lateral_flexion.magnitude_rad == pytest.approx(0, abs=1e-10)


def test_near_singularity_uses_configured_floor_not_backend_warning_threshold():
    module, metrics, trace, _, _ = setup((89.999999, 0, 0))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        rep = proxy(module, metrics, trace)
    # T1 generalization: cos(beta)>1e-8 is nonsingular under the frozen profile.
    assert rep.extension.max_rad == pytest.approx(89.999999*pi/180, abs=1e-10)
