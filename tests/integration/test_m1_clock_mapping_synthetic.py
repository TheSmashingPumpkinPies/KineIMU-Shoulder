"""Integration test for the checked-in synthetic M1 clock-mapping experiment."""

from pathlib import Path
from typing import Any, cast

import pytest

from validation.m1_clock_mapping import analyze_clock_mapping, load_event_plan

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "experiments" / "m1_clock_mapping_synthetic_20260915" / "event_plan.json"


def test_checked_in_synthetic_known_offset_drift_meets_held_out_gate() -> None:
    plan = load_event_plan(PLAN_PATH)
    report = analyze_clock_mapping(plan)

    assert report.decision_status == "pass"
    mappings = {mapping.node_id: mapping for mapping in report.mappings}
    assert mappings["A"].fit_event_ids == ("E01", "E03", "E05")
    assert mappings["B"].fit_event_ids == ("E01", "E03", "E05")

    # Source: the event plan is generated from the analytical inverse
    # t_device=(t_common-b)/a with predeclared A/B offset and drift.
    assert abs(mappings["A"].coefficient_a - 1.000020) < 2e-8
    assert abs(mappings["B"].coefficient_a - 0.999970) < 2e-8
    assert report.pair.held_out.p95_us <= 1_000.0
    assert report.pair.held_out.max_us <= 1_500.0


def test_checked_in_synthetic_report_records_independent_evidence_fields() -> None:
    import json

    report_path = ROOT / "experiments" / "m1_clock_mapping_synthetic_20260915" / "result.json"
    result = cast(dict[str, Any], json.loads(report_path.read_text(encoding="utf-8")))

    assert result["schema_version"] == "kineimu.m1.clock-mapping-validation/0.1"
    assert result["event_split"]["disjoint"] is True
    assert result["event_split"]["fit_event_ids"] == ["E01", "E03", "E05"]
    assert result["event_split"]["held_out_event_ids"] == ["E02", "E04", "E06"]
    assert result["input"]["host_arrival_used_for_fit"] is False
    assert result["input"]["raw_hashes_verified"] is False
    assert result["processing"]["resampling"] == "none"
    assert "relative_drift_ppm" in result["mappings"][0]
    assert "offset_us_at_common_reference" in result["mappings"][0]
    assert "standard_uncertainties_us" in result["held_out"]["pair"]["held_out"]
