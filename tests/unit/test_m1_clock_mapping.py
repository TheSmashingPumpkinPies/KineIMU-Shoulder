"""TDD tests for independent M1 clock mappings and held-out validation."""

import hashlib
import json
from dataclasses import replace

import numpy as np
import pytest

from validation.m1_clock_mapping import (
    CLOCK_MAPPING_METHOD_VERSION,
    CommonEvent,
    EventObservation,
    EventPhase,
    EventPlan,
    EventRole,
    RawStreamInput,
    analyze_clock_mapping,
    event_plan_from_dict,
    event_plan_to_dict,
    load_event_plan,
    validate_event_plan,
    write_clock_mapping_report,
)

RAW_A = "a" * 64
RAW_B = "b" * 64


def _synthetic_plan(
    *,
    a_a: float = 1.000020,
    b_a: float = 1_250.0,
    a_b: float = 0.999970,
    b_b: float = -750.0,
    localization_resolution_us: float = 1.0,
) -> EventPlan:
    # Synthetic construction: t_device = (t_common - b) / a, then integer
    # device timestamps are rounded.  This is the analytical inverse of the
    # specified t_common = a * t_device + b model, not a recorded output.
    event_spec = (
        ("E01", EventPhase.BEGINNING, EventRole.FIT, 10_000_000.0),
        ("E02", EventPhase.BEGINNING, EventRole.HELD_OUT, 300_000_000.0),
        ("E03", EventPhase.MIDDLE, EventRole.FIT, 900_000_000.0),
        ("E04", EventPhase.MIDDLE, EventRole.HELD_OUT, 1_200_000_000.0),
        ("E05", EventPhase.END, EventRole.FIT, 1_790_000_000.0),
        ("E06", EventPhase.END, EventRole.HELD_OUT, 1_800_000_000.0),
    )

    events: list[CommonEvent] = []
    for event_id, phase, role, common_time_us in event_spec:
        events.append(
            CommonEvent(
                event_id=event_id,
                phase=phase,
                role=role,
                common_time_us=common_time_us,
                reference_method="synthetic_exact_common_clock",
                reference_resolution_us=localization_resolution_us,
                reference_uncertainty_us=localization_resolution_us / np.sqrt(12.0),
                observations=(
                    EventObservation(
                        node_id="A",
                        clock_epoch=0,
                        device_time_us=round((common_time_us - b_a) / a_a),
                        localization_method="synthetic_exact_event_sample",
                        localization_resolution_us=localization_resolution_us,
                        localization_uncertainty_us=localization_resolution_us / np.sqrt(12.0),
                        raw_sha256=RAW_A,
                    ),
                    EventObservation(
                        node_id="B",
                        clock_epoch=0,
                        device_time_us=round((common_time_us - b_b) / a_b),
                        localization_method="synthetic_exact_event_sample",
                        localization_resolution_us=localization_resolution_us,
                        localization_uncertainty_us=localization_resolution_us / np.sqrt(12.0),
                        raw_sha256=RAW_B,
                    ),
                ),
            )
        )
    return EventPlan(
        schema_version="kineimu.m1.sync-event-plan/0.1",
        session_id="synthetic-known-offset-drift",
        method_version=CLOCK_MAPPING_METHOD_VERSION,
        raw_streams=(
            RawStreamInput(node_id="A", path="raw/node-a.kimu", sha256=RAW_A),
            RawStreamInput(node_id="B", path="raw/node-b.kimu", sha256=RAW_B),
        ),
        events=tuple(events),
        fixture_id="synthetic-rigid-fixture",
        fixture_description="deterministic common events for TDD only",
    )


def test_known_offset_and_drift_are_recovered_per_node() -> None:
    report = analyze_clock_mapping(_synthetic_plan())

    assert report.decision_status == "pass"
    mappings = {mapping.node_id: mapping for mapping in report.mappings}

    # Source: the synthetic fixture inverse above uses these predeclared
    # coefficients; integer device-time rounding contributes less than 1 us.
    np.testing.assert_allclose(mappings["A"].coefficient_a, 1.000020, rtol=0.0, atol=2e-8)
    np.testing.assert_allclose(mappings["A"].coefficient_b_us, 1_250.0, rtol=0.0, atol=5.0)
    np.testing.assert_allclose(mappings["B"].coefficient_a, 0.999970, rtol=0.0, atol=2e-8)
    np.testing.assert_allclose(mappings["B"].coefficient_b_us, -750.0, rtol=0.0, atol=5.0)

    # Source: relative drift is defined by the M1 model as (a - 1) * 1e6 ppm.
    np.testing.assert_allclose(mappings["A"].relative_drift_ppm, 20.0, rtol=0.0, atol=0.02)
    np.testing.assert_allclose(mappings["B"].relative_drift_ppm, -30.0, rtol=0.0, atol=0.02)
    assert mappings["A"].fit_event_ids == ("E01", "E03", "E05")
    assert mappings["A"].fit_window_device_us[0] < mappings["A"].fit_window_device_us[1]

    assert report.pair.held_out.event_ids == ("E02", "E04", "E06")
    assert report.pair.held_out.p95_us <= 1_000.0
    assert report.pair.held_out.max_us <= 1_500.0


def test_fit_and_held_out_event_ids_must_be_disjoint() -> None:
    plan = _synthetic_plan()
    duplicate = replace(plan.events[0], role=EventRole.HELD_OUT)
    invalid = replace(plan, events=plan.events + (duplicate,))

    with pytest.raises(ValueError, match="event IDs.*disjoint|duplicate event ID"):
        validate_event_plan(invalid)


def test_unknown_mapping_method_version_is_rejected() -> None:
    invalid = replace(_synthetic_plan(), method_version="kineimu.m1.clock-mapping.unknown/9")

    with pytest.raises(ValueError, match="method version"):
        validate_event_plan(invalid)


def test_clock_epochs_receive_separate_mappings() -> None:
    base = _synthetic_plan()
    second_epoch_events = tuple(
        replace(
            event,
            event_id=f"R{event.event_id[1:]}",
            common_time_us=event.common_time_us + 2_000_000_000.0,
            observations=tuple(
                replace(
                    observation,
                    clock_epoch=1,
                    device_time_us=observation.device_time_us + 100_000_000,
                )
                for observation in event.observations
            ),
        )
        for event in base.events
    )
    report = analyze_clock_mapping(replace(base, events=base.events + second_epoch_events))

    assert {(mapping.node_id, mapping.clock_epoch) for mapping in report.mappings} == {
        ("A", 0),
        ("A", 1),
        ("B", 0),
        ("B", 1),
    }
    assert all(len(mapping.fit_event_ids) == 3 for mapping in report.mappings)


def test_resolution_that_cannot_separate_budget_thresholds_is_inconclusive() -> None:
    report = analyze_clock_mapping(_synthetic_plan(localization_resolution_us=600.0))

    assert report.pair.held_out.decision_resolution_us >= 500.0
    assert report.decision_status == "inconclusive"
    assert report.decision.reason == "event resolution/uncertainty cannot separate 1.0 ms and 1.5 ms limits"


def test_common_reference_resolution_also_blocks_an_unsupported_decision() -> None:
    plan = _synthetic_plan()
    coarse_reference = replace(
        plan,
        events=tuple(replace(event, reference_resolution_us=600.0) for event in plan.events),
    )

    report = analyze_clock_mapping(coarse_reference)

    assert report.pair.held_out.max_event_resolution_us >= 600.0
    assert report.decision_status == "inconclusive"


def test_host_arrival_is_not_an_input_to_the_fit() -> None:
    report = analyze_clock_mapping(_synthetic_plan())

    # The public event-observation contract contains device time only for the
    # fit.  Host BLE arrival is transport diagnostic metadata and cannot alter
    # the recovered mapping.
    assert report.fit_time_source == "device_time_us"
    assert report.host_arrival_used_for_fit is False


def test_prediction_uncertainty_uses_the_actual_device_time_coordinate() -> None:
    report = analyze_clock_mapping(_synthetic_plan())
    mapping = next(mapping for mapping in report.mappings if mapping.node_id == "A")
    held_out = next(event for event in report.events if event.event_id == "E02")
    observation = next(observation for observation in held_out.observations if observation.node_id == "A")
    covariance = np.asarray(mapping.coefficient_covariance, dtype=np.float64)
    coordinate = np.asarray([observation.device_time_us, 1.0], dtype=np.float64)
    # Source: first-order covariance propagation for y = [x, 1] beta,
    # plus the independently declared local and common-event uncertainties.
    expected_standard_uncertainty = np.sqrt(
        max(
            0.0,
            float(coordinate @ covariance @ coordinate)
            + (mapping.coefficient_a * observation.localization_uncertainty_us) ** 2
            + held_out.reference_uncertainty_us**2,
        )
    )
    node_result = next(result for result in report.node_results if result.node_id == "A")
    np.testing.assert_allclose(
        node_result.held_out.standard_uncertainties_us[0],
        expected_standard_uncertainty,
        rtol=0.0,
        atol=1e-9,
    )


def test_mapping_remains_stable_for_large_device_clock_origins() -> None:
    shift_us = 1_000_000_000_000
    base = _synthetic_plan()
    shifted = replace(
        base,
        events=tuple(
            replace(
                event,
                common_time_us=event.common_time_us + shift_us,
                observations=tuple(
                    replace(observation, device_time_us=observation.device_time_us + shift_us)
                    for observation in event.observations
                ),
            )
            for event in base.events
        ),
    )
    report = analyze_clock_mapping(shifted)
    mappings = {mapping.node_id: mapping for mapping in report.mappings}

    # Source: shifting both clocks by S preserves a and changes b to
    # b + (1-a)S under the same analytical affine model.
    expected_b_a = 1_250.0 + (1.0 - 1.000020) * shift_us
    expected_b_b = -750.0 + (1.0 - 0.999970) * shift_us
    np.testing.assert_allclose(mappings["A"].coefficient_a, 1.000020, rtol=0.0, atol=2e-8)
    np.testing.assert_allclose(mappings["A"].coefficient_b_us, expected_b_a, rtol=0.0, atol=20_000.0)
    np.testing.assert_allclose(mappings["B"].coefficient_a, 0.999970, rtol=0.0, atol=2e-8)
    np.testing.assert_allclose(mappings["B"].coefficient_b_us, expected_b_b, rtol=0.0, atol=20_000.0)


def test_event_plan_and_report_preserve_hashes_versions_and_raw_bytes(tmp_path) -> None:
    raw_a = tmp_path / "node-a.kimu"
    raw_b = tmp_path / "node-b.kimu"
    raw_a.write_bytes(b"immutable raw A")
    raw_b.write_bytes(b"immutable raw B")
    hash_a = hashlib.sha256(raw_a.read_bytes()).hexdigest()
    hash_b = hashlib.sha256(raw_b.read_bytes()).hexdigest()
    plan = _synthetic_plan()
    plan = replace(
        plan,
        raw_streams=(
            RawStreamInput(node_id="A", path=raw_a.name, sha256=hash_a),
            RawStreamInput(node_id="B", path=raw_b.name, sha256=hash_b),
        ),
        events=tuple(
            replace(
                event,
                observations=tuple(
                    replace(observation, raw_sha256=hash_a if observation.node_id == "A" else hash_b)
                    for observation in event.observations
                ),
            )
            for event in plan.events
        ),
    )
    plan_path = tmp_path / "events.json"
    report_path = tmp_path / "report.json"
    plan_path.write_text(json.dumps(event_plan_to_dict(plan), indent=2), encoding="utf-8")
    before_a = raw_a.read_bytes()
    before_b = raw_b.read_bytes()

    loaded = load_event_plan(plan_path, verify_raw_hashes=True)
    report = write_clock_mapping_report(
        loaded,
        report_path,
        event_plan_path=plan_path,
        verify_raw_hashes=True,
        repository_root=tmp_path,
        command="synthetic-test",
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert loaded == plan
    assert event_plan_from_dict(event_plan_to_dict(plan)) == plan
    assert report.decision_status == "pass"
    assert payload["schema_version"] == "kineimu.m1.clock-mapping-validation/0.1"
    assert payload["method"]["version"] == CLOCK_MAPPING_METHOD_VERSION
    assert payload["event_split"]["disjoint"] is True
    assert payload["input"]["raw_streams"][0]["sha256"] == hash_a
    assert payload["input"]["raw_hashes_verified"] is True
    assert payload["mappings"][0]["fit_event_ids"] == ["E01", "E03", "E05"]
    assert payload["mappings"][0]["fit_window_device_us"][0] < payload["mappings"][0]["fit_window_device_us"][1]
    assert payload["processing"]["resampling"] == "none"
    assert payload["reproducibility"]["raw_data_modified"] is False
    assert raw_a.read_bytes() == before_a
    assert raw_b.read_bytes() == before_b
