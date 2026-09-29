"""Contracts for read-only per-run M1 BLE matrix auditing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.m1_ble_link_matrix_audit import _node_audit, _write_report, audit_matrix
from experiments.m1_transport_audit import _parse_cdc
from kineimu_shoulder.io.m1_capture import encode_capture_record
from kineimu_shoulder.io.m1_packet import (
    NodeId,
    PacketFlags,
    Sample,
    SamplePacket,
    encode_sample_packet,
)


def _tx_diag_line(
    *,
    boot_id: int = 55,
    generation: int = 2,
    saturated: int = 0,
    calls: int,
    accepted: int,
    final_fail: int,
    packet_drops: int,
    enomem: int,
    eagain: int,
    retries: int,
    initial_schedule_failures: int,
    retry_schedule_failures: int,
    window_full: int,
    wait_us: int,
    completed: int,
    cancelled: int,
    callbacks_stale: int,
    callbacks_cancelled: int,
    callbacks_unexpected: int,
    age_count: int,
    age_last_us: int,
    age_min_us: int,
    age_max_us: int,
    age_total_us: int,
    age_bins: tuple[int, ...],
    inflight_current: int,
    inflight_peak: int,
) -> str:
    return (
        f"Node A: tx_diag boot={boot_id} generation={generation} "
        f"calls={calls} accepted={accepted} final_fail={final_fail} "
        f"packet_drops={packet_drops} return_last=-12 "
        f"return_counts=0:{accepted},-12:{enomem},-11:{eagain} "
        f"enomem={enomem} eagain={eagain} retries={retries} "
        f"schedule_fail={initial_schedule_failures}/{retry_schedule_failures} "
        "schedule_last=-12/-11 window_owned=4 "
        f"inflight={inflight_current}/{inflight_peak} "
        f"window_full={window_full} wait_us={wait_us} "
        f"completed={completed} cancelled={cancelled} "
        f"callbacks_stale={callbacks_stale} "
        f"callbacks_cancelled={callbacks_cancelled} "
        f"callbacks_unexpected={callbacks_unexpected} "
        f"age_count={age_count} "
        f"age_us={age_last_us}/{age_min_us}/{age_max_us}/{age_total_us} "
        f"age_bins={','.join(str(value) for value in age_bins)} saturated={saturated}"
    )


def _simple_tx_line(*, boot_id: int, generation: int, calls: int, saturated: int = 0) -> str:
    return _tx_diag_line(
        boot_id=boot_id,
        generation=generation,
        saturated=saturated,
        calls=calls,
        accepted=calls,
        final_fail=0,
        packet_drops=0,
        enomem=0,
        eagain=0,
        retries=0,
        initial_schedule_failures=0,
        retry_schedule_failures=0,
        window_full=0,
        wait_us=0,
        completed=0,
        cancelled=0,
        callbacks_stale=0,
        callbacks_cancelled=0,
        callbacks_unexpected=0,
        age_count=0,
        age_last_us=0,
        age_min_us=0,
        age_max_us=0,
        age_total_us=0,
        age_bins=(0, 0, 0, 0, 0, 0, 0, 0),
        inflight_current=0,
        inflight_peak=0,
    )


def _acquisition_trace(*, enqueue_drops: int) -> str:
    return (
        "Node A: acquisition trace callback=100 prestart=0 timestamp_ok=90 "
        "timestamp_miss=0 raw_try=90 raw_ok=90 raw_fail=0 raw_rc=0 "
        "tx_queue_high_water=4 tx_enqueue_drops="
        f"{enqueue_drops} tx_disconnect_drops=10 tx_stop_drops=5 "
        "notify_calls=80 notify_failures=1 notify_last_duration=3 "
        "notify_max_duration=900 notify_total_duration=12000 saturated=0"
    )


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _matrix_run(root: Path, *, node: str, cdc_lines: list[str], events: list[dict[str, Any]]) -> Path:
    run_dir = root / "run-01-a_only"
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    _write_json(root / "matrix_config.json", {"run_order": ["a_only"]})
    _write_json(root / "matrix_result.json", {"run_results": []})
    _write_json(run_dir / "run_config.json", {"nodes": [node]})
    _write_json(
        run_dir / "run_result.json",
        {
            "error": None,
            "recorder_result": {"nodes": {node: {"packets": 1}}},
            "cdc": {f"node-{node.lower()}": {"decoded_log_path": f"node-{node.lower()}.cdc.log"}},
        },
    )
    (run_dir / f"node-{node.lower()}.cdc.log").write_text("\n".join(cdc_lines) + "\n")
    _write_ndjson(raw_dir / f"node-{node.lower()}.events.ndjson", events)
    _write_ndjson(
        run_dir / "experiment_control.ndjson",
        [
            {"event": "ble_connect_call", "node": node},
            {"event": "ble_connect_return", "node": node},
        ],
    )
    return run_dir


def test_audit_resolves_runner_cdc_keys_for_both_nodes(tmp_path: Path) -> None:
    for node_name in ("A", "B"):
        for cdc_key in (node_name, f"node-{node_name.lower()}"):
            root = tmp_path / f"audit-cdc-key-{node_name}-{cdc_key.replace('-', '')}"
            run_dir = _matrix_run(
                root,
                node=node_name,
                cdc_lines=[
                    f"Node {node_name}: BLE link event=connected info_rc=0 "
                    "interval_us=7500 latency=0 supervision_timeout_us=400000"
                ],
                events=[],
            )
            run_config = json.loads((run_dir / "run_config.json").read_text())
            run_result = json.loads((run_dir / "run_result.json").read_text())
            run_result["cdc"] = {
                cdc_key: {"decoded_log_path": f"node-{node_name.lower()}.cdc.log"}
            }

            audited = _node_audit(run_dir, node_name, run_config, run_result)

            assert audited["cdc"]["available"] is True
            assert audited["cdc"]["link_snapshots"]


def _per_run_fixture(root: Path) -> Path:
    start_bins = (10, 20, 10, 10, 10, 5, 3, 2)
    end_bins = (11, 21, 11, 10, 11, 6, 4, 2)
    cdc_lines = [
        "Node A: BLE link event=connected info_rc=0 interval_us=7500 latency=0 "
        "supervision_timeout_us=400000 phy_valid=1 phy_tx=2 phy_rx=2 "
        "dle_valid=1 dle_tx_max_len=251 dle_tx_max_time_us=2120 "
        "dle_rx_max_len=251 dle_rx_max_time_us=2120",
        _acquisition_trace(enqueue_drops=100),
        _tx_diag_line(
            calls=100,
            accepted=90,
            final_fail=2,
            packet_drops=10,
            enomem=5,
            eagain=5,
            retries=10,
            initial_schedule_failures=1,
            retry_schedule_failures=2,
            window_full=40,
            wait_us=90_000,
            completed=80,
            cancelled=10,
            callbacks_stale=20,
            callbacks_cancelled=15,
            callbacks_unexpected=21,
            age_count=70,
            age_last_us=500,
            age_min_us=100,
            age_max_us=5_000,
            age_total_us=250_000,
            age_bins=start_bins,
            inflight_current=1,
            inflight_peak=8,
        ),
        _acquisition_trace(enqueue_drops=102),
        _tx_diag_line(
            calls=104,
            accepted=93,
            final_fail=2,
            packet_drops=11,
            enomem=6,
            eagain=5,
            retries=12,
            initial_schedule_failures=1,
            retry_schedule_failures=2,
            window_full=42,
            wait_us=91_500,
            completed=83,
            cancelled=11,
            callbacks_stale=21,
            callbacks_cancelled=15,
            callbacks_unexpected=21,
            age_count=73,
            age_last_us=1_500,
            age_min_us=100,
            age_max_us=5_000,
            age_total_us=259_000,
            age_bins=(11, 21, 11, 10, 10, 5, 3, 2),
            inflight_current=4,
            inflight_peak=8,
        ),
        _acquisition_trace(enqueue_drops=105),
        _tx_diag_line(
            calls=109,
            accepted=97,
            final_fail=3,
            packet_drops=13,
            enomem=7,
            eagain=5,
            retries=13,
            initial_schedule_failures=2,
            retry_schedule_failures=3,
            window_full=44,
            wait_us=93_000,
            completed=87,
            cancelled=12,
            callbacks_stale=22,
            callbacks_cancelled=16,
            callbacks_unexpected=22,
            age_count=76,
            age_last_us=750,
            age_min_us=100,
            age_max_us=5_000,
            age_total_us=268_000,
            age_bins=end_bins,
            inflight_current=2,
            inflight_peak=8,
        ),
    ]
    valid_payload = encode_sample_packet(
        SamplePacket(
            node_id=NodeId.A,
            packet_sequence=0,
            clock_epoch=0,
            flags=PacketFlags.NONE,
            samples=(Sample(0, 1_000, 0, (1, 2, 3), (4, 5, 6)),),
        )
    )
    invalid_crc_payload = valid_payload[:-1] + bytes([valid_payload[-1] ^ 1])
    valid_record = encode_capture_record(valid_payload, host_monotonic_ns=10)
    invalid_record = encode_capture_record(invalid_crc_payload, host_monotonic_ns=20)
    events = [
        {"event": "notify", "crc_ok": True, "decode_ok": True},
        {
            "event": "decode_error",
            "crc_ok": False,
            "decode_ok": False,
            "detail": "packet CRC-32C mismatch",
        },
        {"event": "notify_callback_timing", "callback_duration_ns": 100},
        {"event": "notify_callback_timing", "callback_duration_ns": 200},
        {"event": "notify_callback_timing", "callback_duration_ns": 300},
    ]
    run_dir = _matrix_run(root, node="A", cdc_lines=cdc_lines, events=events)
    (run_dir / "raw" / "node-a.kimu").write_bytes(valid_record + invalid_record + b"\x01")
    return run_dir


def test_cdc_parser_reads_tx_diag_structured_fields(tmp_path: Path) -> None:
    cdc_path = tmp_path / "node-a.cdc.log"
    cdc_path.write_text(
        _tx_diag_line(
            calls=9,
            accepted=7,
            final_fail=1,
            packet_drops=2,
            enomem=2,
            eagain=1,
            retries=3,
            initial_schedule_failures=1,
            retry_schedule_failures=2,
            window_full=4,
            wait_us=3_000,
            completed=4,
            cancelled=1,
            callbacks_stale=2,
            callbacks_cancelled=1,
            callbacks_unexpected=3,
            age_count=4,
            age_last_us=900,
            age_min_us=600,
            age_max_us=2_500,
            age_total_us=5_000,
            age_bins=(1, 1, 1, 0, 1, 0, 0, 0),
            inflight_current=3,
            inflight_peak=4,
        )
        + "\n"
    )

    parsed = _parse_cdc(cdc_path, "A")

    # These values come directly from the authored CDC line above; parsing must
    # retain the exact signed return-code keys and diagnostic field grouping.
    snapshots = parsed.get("tx_diag_snapshots")
    assert isinstance(snapshots, list) and len(snapshots) == 1
    fields = snapshots[0]["fields"]
    assert fields["boot_id"] == 55
    assert fields["generation"] == 2
    assert fields["calls"] == 9
    assert fields["accepted"] == 7
    assert fields["return_counts"] == {"0": 7, "-12": 2, "-11": 1}
    assert fields["schedule_fail"] == {"initial": 1, "retry": 2}
    assert fields["inflight"] == {"current": 3, "boot_peak": 4}
    assert fields["age_bins"] == [1, 1, 1, 0, 1, 0, 0, 0]


def test_old_cdc_logs_remain_parseable_without_tx_diagnostics(tmp_path: Path) -> None:
    cdc_path = tmp_path / "legacy.cdc.log"
    cdc_path.write_text(
        _acquisition_trace(enqueue_drops=3)
        + "\nNode A: BLE link event=connected info_rc=0 interval_us=7500 latency=0\n"
    )

    parsed = _parse_cdc(cdc_path, "A")

    # The legacy acquisition and link records remain available; the absent new
    # firmware line is represented as an empty optional diagnostic stream.
    assert parsed["trace_snapshot_count"] == 1
    assert parsed["link_snapshot_count"] == 1
    assert parsed.get("tx_diag_snapshots") == []


def test_matrix_audit_uses_run_deltas_and_reports_raw_qc(tmp_path: Path) -> None:
    run_dir = _per_run_fixture(tmp_path)
    raw_path = run_dir / "raw" / "node-a.kimu"
    original_raw = raw_path.read_bytes()

    audit = audit_matrix(tmp_path)
    node = audit["runs"][0]["nodes"]["A"]
    segment = node["tx_diagnostics"]["segments"][0]

    # Expected run counters are final minus initial boot-cumulative snapshots.
    # Percentiles use nearest-rank over the six run-local samples in the
    # firmware's documented eight histogram bins (ceil(0.95 * 6) == rank 6).
    assert segment["submit_attempts"] == 9
    assert segment["accepted"] == 7
    assert segment["return_codes"]["exact_delta_by_code"] == {"0": 7, "-12": 2, "-11": 0}
    assert segment["return_codes"]["count_reconciles_with_submit_attempts"] is True
    assert segment["return_codes"]["categories"] == {
        "accepted": 7,
        "enomem": 2,
        "eagain": 0,
        "other_negative": 0,
        "unexpected_positive": 0,
    }
    assert segment["retries"]["actual_attempts"] == 3
    assert segment["retries"]["schedule_failures"] == {"initial": 1, "retry": 1}
    assert segment["lifecycle"] == {
        "completed": 7,
        "cancelled": 2,
        "stale_callbacks": 2,
        "callbacks_after_cancel": 1,
        "unexpected_callbacks": 1,
    }
    assert segment["in_flight"]["initial_current"] == 1
    assert segment["in_flight"]["final_current"] == 2
    assert segment["in_flight"]["observed_peak_current"] == 4
    assert segment["in_flight"]["run_peak_value"] is None
    assert segment["in_flight"]["boot_peak_start"] == 8
    assert segment["in_flight"]["boot_peak_end"] == 8
    assert segment["completion_window"] == {"full_count": 4, "wait_total_us": 3_000}
    assert segment["completion_age"]["count"] == 6
    assert segment["completion_age"]["total_us"] == 18_000
    assert segment["completion_age"]["mean_us"] == 3_000
    assert segment["completion_age"]["bins"] == [1, 1, 1, 0, 1, 1, 1, 0]
    assert segment["completion_age"]["p50_bucket"]["index"] == 2
    assert segment["completion_age"]["p95_bucket"]["index"] == 6

    # The fixture's queue counter rises 100 -> 105; the legacy boot maximum is
    # not a per-run drop count. Raw bytes must stay byte-for-byte unchanged.
    assert node["queue_drops"]["deltas"] == {"enqueue": 5, "disconnect": 0, "stop": 0}
    assert node["capture_quality"]["crc_errors"] == 1
    assert node["capture_quality"]["decode_errors"] == 1
    assert node["capture_quality"]["framing_errors"] == 1
    assert node["capture_quality"]["raw_unchanged_during_audit"] is True
    assert raw_path.read_bytes() == original_raw
    assert node["callback_durations"]["p95_ns"] == 300
    assert node["actual_connection_parameters"]["interval_us"] == 7_500

    report_path = tmp_path / "MATRIX_REPORT.md"
    _write_report(report_path, audit)
    report = report_path.read_text(encoding="utf-8")
    assert "submit attempts / accepted" in report
    assert "attempt count reconciliation: reconciled" in report
    assert "completion-age distribution" in report
    assert "CRC / decode / framing" in report
    assert "105" not in report


def test_failed_link_setup_is_reported_and_missing_raw_files_are_allowed(tmp_path: Path) -> None:
    run_dir = _matrix_run(tmp_path, node="B", cdc_lines=[], events=[])
    _write_json(run_dir / "run_result.json", {"error": "RuntimeError: Insufficient Resource"})
    _write_ndjson(
        run_dir / "experiment_control.ndjson",
        [{"event": "ble_connect_call", "node": "B"}],
    )

    audit = audit_matrix(tmp_path)

    # The absent return and recorder error describe this failed setup attempt;
    # missing capture sidecars do not make the old/partial run unparsable.
    setup = audit["runs"][0]["setup_errors"]
    assert setup["ble_connect_failures_by_node"] == {"B": 1}
    assert setup["run_error"] == "RuntimeError: Insufficient Resource"
    node = audit["runs"][0]["nodes"]["B"]
    assert node["capture_quality"]["raw_qc_available"] is False
    assert node["tx_diagnostics"]["segments"] == []


def test_tx_diagnostics_split_on_boot_and_generation_and_mark_saturation(tmp_path: Path) -> None:
    cdc_lines = [
        _simple_tx_line(boot_id=55, generation=2, calls=5),
        _simple_tx_line(boot_id=55, generation=2, calls=7, saturated=1),
        _simple_tx_line(boot_id=55, generation=3, calls=8),
        _simple_tx_line(boot_id=55, generation=3, calls=11),
        _simple_tx_line(boot_id=56, generation=1, calls=1),
        _simple_tx_line(boot_id=56, generation=1, calls=4),
    ]
    _matrix_run(
        tmp_path,
        node="A",
        cdc_lines=cdc_lines,
        events=[],
    )

    audit = audit_matrix(tmp_path)
    segments = audit["runs"][0]["nodes"]["A"]["tx_diagnostics"]["segments"]

    # Each segment is differenced only within its own boot/generation. A sticky
    # saturation flag downgrades the first segment's count to a lower bound.
    assert [(segment["boot_id"], segment["generation"]) for segment in segments] == [
        (55, 2),
        (55, 3),
        (56, 1),
    ]
    assert [segment["submit_attempts"] for segment in segments] == [2, 3, 3]
    assert segments[0]["delta_quality"] == "lower_bound"


def test_report_marks_return_code_counts_that_do_not_reconcile(tmp_path: Path) -> None:
    initial = _simple_tx_line(boot_id=55, generation=2, calls=10)
    final = _simple_tx_line(boot_id=55, generation=2, calls=12).replace(
        "return_counts=0:12", "return_counts=0:11"
    )
    _matrix_run(tmp_path, node="A", cdc_lines=[initial, final], events=[])

    audit = audit_matrix(tmp_path)
    segment = audit["runs"][0]["nodes"]["A"]["tx_diagnostics"]["segments"][0]
    assert segment["return_codes"]["count_reconciles_with_submit_attempts"] is False

    report_path = tmp_path / "MATRIX_REPORT.md"
    _write_report(report_path, audit)
    report = report_path.read_text(encoding="utf-8")
    assert "attempt count reconciliation: unreconciled" in report
