from __future__ import annotations

from importlib import import_module
from pathlib import Path


def test_v8_plan_and_runner_use_a_new_versioned_root() -> None:
    formal = import_module("experiments.m1_ble_link_count_formal_v8")

    assert formal.FORMAL_PLAN_PATH.name == "M1_BLE_LINK_COUNT_ROOT_CAUSE_PLAN_V8_20260924.md"
    assert formal.FORMAL_PLAN_PATH.is_file()
    assert formal.FORMAL_OUTPUT_ROOT == Path(
        "<external-data>/kineimu_m1_root_cause_formal_v8_20260924_01"
    )
    assert formal.FORMAL_PLAN_SHA256 == formal.precheck.sha256(formal.FORMAL_PLAN_PATH).upper()


def test_v8_plan_preserves_the_interrupted_v7_root_and_requires_live_prompt() -> None:
    formal = import_module("experiments.m1_ble_link_count_formal_v8")
    plan = formal.FORMAL_PLAN_PATH.read_text(encoding="utf-8")

    assert "kineimu_m1_root_cause_formal_v7_20260924_01" in plan
    assert "PowerShell command prompt" in plan
    assert "live acquisition prompt" in plan


def test_v8_run_profile_uses_its_own_versioned_schemas() -> None:
    matrix = import_module("experiments.m1_ble_link_matrix")

    assert matrix._run_config_schema("link_count_formal_v8") == (
        "kineimu.m1.ble-link-count-formal-v8-run/1.0",
        "kineimu.m1.ble-link-count-formal-v8-run-result/1.0",
        "m1-link-count-formal-v8",
    )


def test_v8_independent_auditor_is_bound_to_v8_runner_and_root() -> None:
    formal = import_module("experiments.m1_ble_link_count_formal_v8")
    audit = import_module("experiments.m1_ble_link_count_formal_audit_v8")

    assert audit.formal is formal
    assert audit.FORMAL_PLAN_PATH == formal.FORMAL_PLAN_PATH
    assert audit.FORMAL_PLAN_SHA256 == formal.FORMAL_PLAN_SHA256
    assert audit.FORMAL_OUTPUT_ROOT == formal.FORMAL_OUTPUT_ROOT


def test_v8_excludes_boot_ids_from_both_manifest_verified_v6_prechecks() -> None:
    formal = import_module("experiments.m1_ble_link_count_formal_v8")

    assert {
        12288373895513561913,
        7701146763957617505,
    } <= formal.FORMAL_FORBIDDEN_BOOT_IDS[formal.NodeId.A]
    assert 4936689328756888443 in formal.FORMAL_FORBIDDEN_BOOT_IDS[formal.NodeId.B]
