from __future__ import annotations

import random
from importlib import import_module
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def formal_module() -> ModuleType:
    try:
        return import_module("experiments.m1_ble_link_count_formal")
    except ImportError:
        pytest.fail("V7 formal runner behavior is not implemented yet", pytrace=False)


def test_v7_schedule_is_balanced_and_contains_both_orders_and_single_controls(
    formal_module: ModuleType,
) -> None:
    expected = (
        ("a_only", "b_only", "dual_b_to_a", "dual_a_to_b"),
        ("dual_b_to_a", "a_only", "dual_a_to_b", "b_only"),
        ("dual_a_to_b", "dual_b_to_a", "b_only", "a_only"),
        ("b_only", "dual_a_to_b", "a_only", "dual_b_to_a"),
    )
    canonical_williams = (
        ("a_only", "b_only", "dual_b_to_a", "dual_a_to_b"),
        ("b_only", "dual_a_to_b", "a_only", "dual_b_to_a"),
        ("dual_b_to_a", "a_only", "dual_a_to_b", "b_only"),
        ("dual_a_to_b", "dual_b_to_a", "b_only", "a_only"),
    )

    assert formal_module.FORMAL_BLOCK_SCHEDULE == expected
    assert tuple(random.Random(20260924).sample(list(canonical_williams), 4)) == expected
    assert formal_module.formal_order(4) == tuple(
        condition for block in expected for condition in block
    )
    assert all(set(block) == {"a_only", "b_only", "dual_a_to_b", "dual_b_to_a"} for block in expected)
    assert {
        condition: sum(block[position] == condition for block in expected for position in range(4))
        for condition in expected[0]
    } == {"a_only": 4, "b_only": 4, "dual_a_to_b": 4, "dual_b_to_a": 4}


def test_v7_schedule_rejects_any_block_count_other_than_four(
    formal_module: ModuleType,
) -> None:
    with pytest.raises(ValueError, match="exactly four blocks"):
        formal_module.formal_order(3)


def test_each_v7_condition_requires_its_own_operator_confirmed_cold_reset(
    formal_module: ModuleType,
) -> None:
    token = formal_module.reset_confirmation_token(7)

    assert token == "COLD_RESET_07"
    assert formal_module.validate_reset_confirmation(7, token) is True
    assert formal_module.validate_reset_confirmation(7, "COLD_RESET_06") is False
    assert formal_module.validate_reset_confirmation(7, " yes ") is False


def test_v7_forbidden_boot_ids_include_the_prior_v5_a_only_and_dual_runs(
    formal_module: ModuleType,
) -> None:
    # These IDs are the immutable V5 pre-notify values recorded in CURRENT_TASK.md's V5 pair record.
    assert 2701971511492984250 in formal_module.FORMAL_FORBIDDEN_BOOT_IDS[
        formal_module.NodeId.A
    ]
    assert 9353023436044725051 in formal_module.FORMAL_FORBIDDEN_BOOT_IDS[
        formal_module.NodeId.A
    ]
    assert 13643691926106628137 in formal_module.FORMAL_FORBIDDEN_BOOT_IDS[
        formal_module.NodeId.B
    ]


def test_pre_notify_boot_id_gate_requires_one_fresh_pristine_status_per_active_node(
    formal_module: ModuleType,
) -> None:
    events = [
        {
            "event": "pre_notify_status_gate",
            "node": "A",
            "passed": True,
            "status": {"boot_id": 101, "acquisition_state": "armed"},
        },
        {
            "event": "pre_notify_status_gate",
            "node": "B",
            "passed": True,
            "status": {"boot_id": 202, "acquisition_state": "armed"},
        },
    ]

    boot_ids, errors = formal_module.pre_notify_boot_ids(events, ("A", "B"))

    # The expected IDs are copied unchanged from the successful status fixtures above.
    assert boot_ids == {"A": 101, "B": 202}
    assert errors == []


def test_pre_notify_boot_id_gate_rejects_duplicate_or_failed_status_records(
    formal_module: ModuleType,
) -> None:
    events = [
        {
            "event": "pre_notify_status_gate",
            "node": "A",
            "passed": True,
            "status": {"boot_id": 101, "acquisition_state": "armed"},
        },
        {
            "event": "pre_notify_status_gate",
            "node": "A",
            "passed": True,
            "status": {"boot_id": 102, "acquisition_state": "armed"},
        },
        {
            "event": "pre_notify_status_gate",
            "node": "B",
            "passed": False,
            "status": {"boot_id": 202, "acquisition_state": "armed"},
        },
    ]

    boot_ids, errors = formal_module.pre_notify_boot_ids(events, ("A", "B"))

    assert boot_ids == {}
    assert any("Node A" in error and "exactly once" in error for error in errors)
    assert any("Node B" in error and "did not pass" in error for error in errors)


def test_matched_ratio_calculation_uses_same_block_node_specific_controls(
    formal_module: ModuleType,
) -> None:
    block_packets = [
        {
            "a_only": {"A": 400},
            "b_only": {"B": 380},
            "dual_a_to_b": {"A": 300, "B": 320},
            "dual_b_to_a": {"A": 310, "B": 330},
        }
        for _ in range(4)
    ]

    derive_ratios = getattr(formal_module, "derive_matched_ratios", None)
    assert callable(derive_ratios), "matched ratio derivation is not implemented yet"
    ratios = derive_ratios(block_packets)

    # These expected ratios apply the V7 plan's formulas directly to the fixture counts.
    assert ratios["per_node_dual_to_single"]["A"]["dual_a_to_b"] == [0.75] * 4
    assert ratios["per_node_dual_to_single"]["B"]["dual_b_to_a"] == [330 / 380] * 4
    assert ratios["first_to_second"]["dual_a_to_b"] == [300 / 320] * 4
    assert ratios["first_to_second"]["dual_b_to_a"] == [330 / 310] * 4


def test_matched_ratio_calculation_rejects_missing_blocks(
    formal_module: ModuleType,
) -> None:
    derive_ratios = getattr(formal_module, "derive_matched_ratios", None)
    assert callable(derive_ratios), "matched ratio derivation is not implemented yet"
    with pytest.raises(ValueError, match="exactly four complete blocks"):
        derive_ratios([])


def test_factor_effect_is_supported_only_when_same_node_falls_below_gate_in_both_orders(
    formal_module: ModuleType,
) -> None:
    result = formal_module.classify_factor_effect(
        {
            "A": {
                "dual_a_to_b": [0.50, 0.60, 0.55, 0.95],
                "dual_b_to_a": [0.60, 0.55, 0.65, 0.95],
            },
            "B": {
                "dual_a_to_b": [0.96, 0.95, 0.94, 0.98],
                "dual_b_to_a": [0.97, 0.96, 0.95, 0.97],
            },
        },
        {"dual_a_to_b": [0.95, 0.96, 0.97, 0.98], "dual_b_to_a": [0.95, 0.96, 0.97, 0.98]},
        integrity_valid=True,
        transport_clean=False,
    )

    # The expected class follows the V7 plan's repeated <0.90 dual/single rule in both orders.
    assert result["disposition"] == "Supported"
    assert "Node A" in str(result["reason"])


def test_factor_effect_is_not_supported_only_when_all_ratios_pass_and_transport_is_clean(
    formal_module: ModuleType,
) -> None:
    ratios = {
        node: {
            "dual_a_to_b": [0.95, 0.96, 0.97, 0.98],
            "dual_b_to_a": [0.95, 0.96, 0.97, 0.98],
        }
        for node in ("A", "B")
    }
    order_ratios = {
        "dual_a_to_b": [0.95, 0.96, 0.97, 0.98],
        "dual_b_to_a": [0.95, 0.96, 0.97, 0.98],
    }

    result = formal_module.classify_factor_effect(
        ratios, order_ratios, integrity_valid=True, transport_clean=True
    )

    # The expected class follows the V7 plan's all-ratios >=0.90 and clean-transport rule.
    assert result["disposition"] == "Not supported"


def test_factor_effect_is_inconclusive_for_incomplete_or_mixed_evidence(
    formal_module: ModuleType,
) -> None:
    complete_ratios = {
        node: {
            "dual_a_to_b": [0.70, 0.95, 0.70, 0.95],
            "dual_b_to_a": [0.70, 0.95, 0.70, 0.95],
        }
        for node in ("A", "B")
    }
    order_ratios = {
        "dual_a_to_b": [0.95, 0.95, 0.95, 0.95],
        "dual_b_to_a": [0.95, 0.95, 0.95, 0.95],
    }

    mixed = formal_module.classify_factor_effect(
        complete_ratios, order_ratios, integrity_valid=True, transport_clean=False
    )
    incomplete = formal_module.classify_factor_effect(
        complete_ratios, order_ratios, integrity_valid=False, transport_clean=True
    )

    assert mixed["disposition"] == "Inconclusive"
    assert incomplete["disposition"] == "Inconclusive"


def test_independent_audit_ignores_prior_audit_json_and_requires_complete_raw_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        formal_audit_module = import_module("experiments.m1_ble_link_count_formal_audit")
    except ImportError:
        formal_audit_module = None
    assert formal_audit_module is not None, "V7 independent raw audit is not implemented yet"
    root = Path("synthetic-formal-root")
    plan_hash = "a" * 64
    monkeypatch.setattr(formal_audit_module, "FORMAL_PLAN_PATH", Path("locked-plan.md"))
    monkeypatch.setattr(formal_audit_module, "FORMAL_PLAN_SHA256", plan_hash)
    monkeypatch.setattr(formal_audit_module, "FORMAL_OUTPUT_ROOT", root)
    monkeypatch.setattr(formal_audit_module, "verify_manifest", lambda _root: {"valid": True, "sha256": "b" * 64})
    monkeypatch.setattr(formal_audit_module, "raw_input_hashes", lambda _root: {})
    monkeypatch.setattr(formal_audit_module, "sha256", lambda _path: plan_hash)

    def read_index(path: Path) -> dict[str, object]:
        assert path.name != "matrix_audit.json", "prior audit output must not be read"
        if path.name == "matrix_config.json":
            return {
                "schema": "kineimu.m1.ble-link-count-formal/1.0",
                "predeclared_plan_sha256": plan_hash,
                "run_order": [],
            }
        if path.name == "matrix_result.json":
            return {
                "schema": "kineimu.m1.ble-link-count-formal-result/2.0",
                "run_order": [],
                "run_results": [],
            }
        return {}

    monkeypatch.setattr(formal_audit_module, "_read_json", read_index)

    report = formal_audit_module.audit_formal_root(root)

    assert report["disposition"] == "Inconclusive"
    assert report["matrix_audit_json_used"] is False
    assert report["integrity_valid"] is False


def test_active_tx_segment_requires_one_exact_unsaturated_generation() -> None:
    try:
        audit_module = import_module("experiments.m1_ble_link_count_formal_audit")
    except ImportError:
        audit_module = None
    assert audit_module is not None, "V7 independent raw audit is not implemented yet"
    active = {
        "segment_index": 2,
        "delta_quality": "exact",
        "saturated": False,
        "counter_deltas": {
            name: 0
            for name in (
                "calls", "accepted", "final_fail", "packet_drops", "enomem", "eagain",
                "retries", "window_full", "wait_us", "completed", "cancelled",
                "callbacks_stale", "callbacks_cancelled", "callbacks_unexpected",
                "age_count", "schedule_fail_initial", "schedule_fail_retry",
            )
        },
    }
    active["counter_deltas"]["calls"] = 10
    summary = {
        "snapshot_count": 4,
        "segments": [
            {"segment_index": 1, "counter_deltas": {"calls": 0}},
            active,
        ],
    }

    active_tx_segment = getattr(audit_module, "_active_tx_segment", None)
    assert callable(active_tx_segment), "active TX-generation audit is not implemented yet"
    observed, errors = active_tx_segment(summary)

    assert observed == active
    assert errors == []


def test_active_tx_segment_rejects_ambiguous_or_incomplete_generations() -> None:
    audit_module = import_module("experiments.m1_ble_link_count_formal_audit")
    active_tx_segment = getattr(audit_module, "_active_tx_segment", None)
    assert callable(active_tx_segment), "active TX-generation audit is not implemented yet"
    summary = {
        "snapshot_count": 1,
        "segments": [
            {
                "segment_index": 1,
                "delta_quality": "incomplete_or_lower_bound",
                "saturated": True,
                "counter_deltas": {"calls": 1},
            },
            {
                "segment_index": 2,
                "delta_quality": "exact",
                "saturated": False,
                "counter_deltas": {"calls": 1},
            },
        ],
    }

    segment, errors = active_tx_segment(summary)

    assert segment is None
    assert "fewer than two snapshots" in errors[0]
    assert "found 2" in errors[1]


def test_independent_audit_rejects_reused_boot_ids_across_conditions() -> None:
    audit_module = import_module("experiments.m1_ble_link_count_formal_audit")
    check_unique = getattr(audit_module, "_unique_boot_id_errors", None)
    assert callable(check_unique), "cross-condition fresh-boot audit is not implemented yet"
    audits = [
        {
            "run_index": 1,
            "condition": "a_only",
            "nodes": {"A": {"acquisition_start": {"boot_id": 101}}},
        },
        {
            "run_index": 2,
            "condition": "b_only",
            "nodes": {"B": {"acquisition_start": {"boot_id": 202}}},
        },
        {
            "run_index": 3,
            "condition": "dual_a_to_b",
            "nodes": {
                "A": {"acquisition_start": {"boot_id": 101}},
                "B": {"acquisition_start": {"boot_id": 203}},
            },
        },
    ]

    errors, repeated_runs = check_unique(audits)

    # The reused ID is explicitly injected in runs 1 and 3; run 2 has a distinct Node B ID.
    assert repeated_runs == {1, 3}
    assert len(errors) == 1
    assert "Node A" in errors[0] and "boot ID 101" in errors[0]


def test_independent_audit_requires_prior_precheck_boot_ids_in_each_run_lock() -> None:
    audit_module = import_module("experiments.m1_ble_link_count_formal_audit")
    validate_forbidden = getattr(audit_module, "forbidden_boot_id_errors", None)
    assert callable(validate_forbidden), "historical boot-ID lock audit is not implemented yet"

    errors = validate_forbidden({"A": [], "B": []})

    assert len(errors) == 2
    assert any("Node A" in error for error in errors)
    assert any("Node B" in error for error in errors)


def test_precollection_failure_is_explicitly_recorded_as_zero_attempts(
    formal_module: ModuleType,
) -> None:
    build_result = getattr(formal_module, "precollection_failure_result", None)
    assert callable(build_result), "precollection failure sealing is not implemented yet"

    result = build_result({"git_head": "a" * 40}, OSError("copy failed"))

    assert result["schema"] == "kineimu.m1.ble-link-count-formal-result/2.0"
    assert result["scheduled_count"] == 16
    assert result["schedule_attempted_count"] == 0
    assert result["all_scheduled_runs_attempted"] is False
    assert result["run_results"] == []
    assert result["stop_reason"] == "OSError: copy failed"


def test_raw_audit_comparison_rows_pair_dual_runs_to_same_block_controls() -> None:
    audit_module = import_module("experiments.m1_ble_link_count_formal_audit")
    comparison_rows = getattr(audit_module, "_comparison_rows", None)
    assert callable(comparison_rows), "V7 same-block raw comparison is not implemented yet"
    counts = {
        "a_only": {"A": 400},
        "b_only": {"B": 380},
        "dual_a_to_b": {"A": 300, "B": 320},
        "dual_b_to_a": {"A": 310, "B": 330},
    }
    audits = []
    for block_index, block in enumerate(audit_module.formal.FORMAL_BLOCK_SCHEDULE, start=1):
        for condition in block:
            audits.append(
                {
                    "valid": True,
                    "block_index": block_index,
                    "condition": condition,
                    "nodes": {
                        node: {
                            "raw_capture": {"valid_packets": packet_count},
                            "active_tx_segment": {"counter_deltas": {"calls": packet_count}},
                        }
                        for node, packet_count in counts[condition].items()
                    },
                }
            )

    packet_blocks, per_node, ratios = comparison_rows(audits)

    assert len(packet_blocks) == 4
    assert per_node["A"]["dual_a_to_b"] == [0.75] * 4
    assert per_node["B"]["dual_b_to_a"] == [330 / 380] * 4
    assert ratios["first_to_second"]["dual_a_to_b"] == [300 / 320] * 4
    assert ratios["first_to_second"]["dual_b_to_a"] == [330 / 310] * 4
    assert len(ratios["tx_by_block"]) == 4


def test_raw_audit_comparison_rows_withhold_ratios_if_a_block_is_missing() -> None:
    audit_module = import_module("experiments.m1_ble_link_count_formal_audit")
    comparison_rows = getattr(audit_module, "_comparison_rows", None)
    assert callable(comparison_rows), "V7 same-block raw comparison is not implemented yet"

    packet_blocks, per_node, ratios = comparison_rows([])

    assert len(packet_blocks) == 4
    assert per_node == {}
    assert ratios == {}


def test_tx_mechanism_requires_repeated_exact_backpressure_with_throughput_deficit() -> None:
    audit_module = import_module("experiments.m1_ble_link_count_formal_audit")
    mechanism_assessment = getattr(audit_module, "_mechanism_assessment", None)
    assert callable(mechanism_assessment), "V7 TX mechanism assessment is not implemented yet"
    per_node_ratios = {
        "A": {
            "dual_a_to_b": [0.5] * 4,
            "dual_b_to_a": [0.6] * 4,
        },
        "B": {
            "dual_a_to_b": [0.95] * 4,
            "dual_b_to_a": [0.95] * 4,
        },
    }
    tx_blocks = []
    for _ in range(4):
        low = {
            "delta_quality": "exact",
            "counter_deltas": {"enomem": 0, "eagain": 0, "wait_us": 0, "window_full": 0},
        }
        high = {
            "delta_quality": "exact",
            "counter_deltas": {"enomem": 10, "eagain": 0, "wait_us": 100, "window_full": 2},
        }
        tx_blocks.append(
            {
                "a_only": {"A": low},
                "b_only": {"B": low},
                "dual_a_to_b": {"A": high, "B": low},
                "dual_b_to_a": {"A": high, "B": low},
            }
        )

    result = mechanism_assessment(per_node_ratios, tx_blocks)

    assert result["assessment"] == "Supported at peripheral notify submit/retry boundary"
    assert result["supported_node_counts"]["A"] == {"dual_a_to_b": 4, "dual_b_to_a": 4}
