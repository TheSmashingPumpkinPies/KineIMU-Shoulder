"""Create the final read-only roll-up for the independent transport experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

JSON = dict[str, Any]
DEFAULT_RUNS = ("test_a_pressure", "test_b_recovery", "test_b_recovery_retry1")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> JSON:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return cast(JSON, value)


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _node_row(audit: JSON, node_name: str) -> JSON:
    node = cast(JSON, audit["nodes"][node_name])
    qc = cast(JSON, node["sequence"]["qc"])
    status = cast(JSON, node["status"].get("cumulative_deltas_initial_to_final", {}))
    cdc = cast(JSON, node["cdc"].get("maxima", {}))
    return {
        "node": node_name,
        "packets": qc["packets_decoded"],
        "samples": qc["samples_decoded"],
        "missing_packets": qc["packets_missing"],
        "missing_samples": qc["samples_missing"],
        "unattributed_gaps": node["sequence"]["unattributed_gap_count"],
        "sensor_fifo_overruns": status.get("sensor_fifo_overruns", 0),
        "firmware_queue_overruns": status.get("firmware_queue_overruns", 0),
        "pre_packetization_drops": status.get("samples_dropped_before_packetization", 0),
        "transport_backpressure_events": status.get("transport_backpressure_events", 0),
        "tx_queue_high_water": node["high_water"]["tx_queue_high_water_packets"]["status_max"],
        "cdc_tx_queue_high_water": cdc.get("tx_queue_high_water", 0),
        "cdc_tx_enqueue_drops": cdc.get("tx_enqueue_drops", 0),
        "cdc_tx_disconnect_drops": cdc.get("tx_disconnect_drops", 0),
        "cdc_tx_stop_drops": cdc.get("tx_stop_drops", 0),
        "cdc_notify_failures": cdc.get("notify_failures", 0),
        "continuity": node["continuity"],
        "raw_sha256": node["raw_sha256"],
        "events_sha256": node["events_sha256"],
    }


def _load_attempt(root: Path, name: str) -> JSON:
    run_dir = root / name
    audit = _read_json(run_dir / "offline_audit.json")
    return {
        "name": name,
        "path": str(run_dir),
        "session_present": audit["session_present"],
        "run_error": audit["run_result"].get("error"),
        "plan_parameter_check": audit["plan_parameter_check"],
        "raw_unchanged_during_audit": audit["raw_unchanged_during_audit"],
        "manifest_check": audit["manifest_check"],
        "control_event_type_counts": audit["control_event_type_counts"],
        "nodes": {node: _node_row(audit, node) for node in ("A", "B")},
        "recovery_records": {
            node: audit["nodes"][node]["recovery_records"] for node in ("A", "B")
        },
    }


def _write_report(root: Path, plan_hash: str, attempts: list[JSON]) -> None:
    lines = [
        "# Independent M1 FIFO/Queue Pressure and BLE Recovery Report",
        "",
        "This report covers only the separately scoped transport experiments. It is not the "
        "formal 30-minute acceptance dataset and does not change its thresholds.",
        "",
        f"- External root: `{root}`",
        f"- Predeclared plan SHA-256: `{plan_hash}`",
        "- Raw policy: immutable; no packet/sample was repaired, filtered, interpolated, or resampled.",
        "- Analysis policy: all audits opened raw streams read-only; each run has a local "
        "SHA256SUMS.txt and this root has a complete SHA256SUMS.txt.",
        "",
        "## Test A — FIFO/queue pressure",
        "",
        "Predeclared stimulus: dual-node 104 Hz/four-sample streaming for 90 s with a fixed "
        "8 ms host telemetry callback delay and no disconnect stimulus.",
        "",
        "| Node | raw packets | raw samples | missing packets | missing samples | FIFO overruns | "
        "acquisition queue overruns | pre-packetization drops | transport backpressure | "
        "TX HWM | unattributed gaps |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    pressure = next(attempt for attempt in attempts if attempt["name"] == "test_a_pressure")
    for node in ("A", "B"):
        row = pressure["nodes"][node]
        lines.append(
            "| {node} | {packets} | {samples} | {missing_packets} | {missing_samples} | "
            "{fifo} | {queue} | {pre} | {transport} | {hwm} | {unattributed} |".format(
                node=node,
                packets=row["packets"],
                samples=row["samples"],
                missing_packets=row["missing_packets"],
                missing_samples=row["missing_samples"],
                fifo=row["sensor_fifo_overruns"],
                queue=row["firmware_queue_overruns"],
                pre=row["pre_packetization_drops"],
                transport=row["transport_backpressure_events"],
                hwm=row["cdc_tx_queue_high_water"],
                unattributed=row["unattributed_gaps"],
            )
        )
    lines.extend(
        [
            "",
            "Test A result: all observed sequence gaps were attributed by packet flags plus "
            "status/CDC evidence; no sensor FIFO overrun or host decode/framing error was "
            "observed. Node A had 103 enqueue drops plus 1 teardown disconnect drop (status "
            "transport delta 104). Node B had 2,121 enqueue drops plus 5 disconnect drops "
            "(status transport delta 2,126) and 606 acquisition-queue/pre-packetization "
            "drops. Both TX high-water values were 4 packets. This is loss characterization "
            "evidence, not a pass against the formal 30-minute acceptance budget.",
            "",
            "## Test B — BLE disconnect/recovery",
            "",
            "Predeclared stimulus: 55 s with no callback delay; B disconnect at "
            "streaming-relative +15 s for 3 s, A disconnect at +35 s for 3 s; "
            "identity/config revalidation target 10 s.",
            "",
        ]
    )
    for attempt in attempts:
        if attempt["name"] == "test_a_pressure":
            continue
        lines.extend(
            [
                f"### `{attempt['name']}`",
                "",
                f"- Completed recorder session: **{attempt['session_present']}**",
                f"- Recorder error: `{attempt['run_error']}`",
                f"- Plan parameters unchanged: **{attempt['plan_parameter_check']['pass']}**",
                f"- Raw unchanged during audit: **{attempt['raw_unchanged_during_audit']}**",
                "",
            ]
        )
        for node in ("A", "B"):
            row = attempt["nodes"][node]
            lines.append(
                f"- Node {node}: `{row['packets']}` packets / `{row['samples']}` samples; "
                f"missing `{row['missing_packets']}` packets / `{row['missing_samples']}` samples; "
                f"unattributed gaps `{row['unattributed_gaps']}`; epoch decision "
                f"`{row['continuity']['epoch_decision']}`."
            )
            for index, recovery in enumerate(attempt["recovery_records"][node], start=1):
                lines.append(
                    f"- Node {node} recovery {index}: disconnect `{recovery['disconnect_host_monotonic_ns']}`; "
                    f"reconnect `{recovery['reconnect_host_monotonic_ns']}`; "
                    f"reconnect attempts `{recovery['reconnect_attempt_host_monotonic_ns']}`; "
                    f"identity/config revalidation `{recovery['identity_config_revalidation_host_monotonic_ns']}`; "
                    f"telemetry resume `{recovery['telemetry_resume_host_monotonic_ns']}`; "
                    f"link unavailable `{recovery['link_unavailable_ns'] / 1e9:.6f}` s; "
                    f"10 s target **{recovery['recovery_target_10s']}**."
                )
        lines.append("")
    lines.extend(
        [
            "Test B disposition: the first attempt failed before initial BLE connection because "
            "the advertised device was absent. Retry1 entered stable streaming and both planned "
            "active disconnects occurred, but neither node re-advertised for a successful "
            "reconnect; the recorder reached its reconnect deadline. No identity/config "
            "revalidation occurred after either disconnect, so continuity was not proven and "
            "the processed decision is to start a new epoch/map. The disconnect/reconnect "
            "failure is retained as the minimum reproduction; no firmware fix was made in "
            "this task. The first attempt's CDC trace is cumulative device output from the "
            "preceding run because no BLE session was established; it is retained but not used "
            "as Test B session loss evidence.",
            "",
            "## Attribution and observability limits",
            "",
            "Every sequence issue and missing packet/sample gap is in each run's "
            "`sequence_gaps.json`, with stream offset, previous/current values, connection, "
            "packet flags, and attribution evidence. Status, event sidecar, CDC trace and raw "
            "hashes are in each run's `offline_audit.json`.",
            "",
            "The current firmware reports acquisition-buffer high-water as `0U` while "
            "`sample_queue.c` maintains an unexported statistic; this is explicitly marked "
            "non-observable. Sensor FIFO occupancy high-water is not in the frozen M1 status "
            "contract. These are report-only defects, not repaired here.",
            "",
            "The two failed/incomplete Test B attempts are not silently merged with Test A or "
            "with each other. Root `SHA256SUMS.txt` covers all files below this external root "
            "except itself.",
        ]
    )
    (root / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_hash_manifest(root: Path) -> Path:
    path = root / "SHA256SUMS.txt"
    files = sorted(file for file in root.rglob("*") if file.is_file() and file != path)
    with path.open("x", encoding="utf-8") as stream:
        for file in files:
            stream.write(f"{_sha256(file)}  {file.relative_to(root).as_posix()}\n")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-dir", type=Path, required=True)
    parser.add_argument("--overwrite-derived", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    root: Path = args.root_dir
    plan_path = root / "PREDECLARED_PLAN.md"
    plan_hash = _sha256(plan_path)
    run_names = DEFAULT_RUNS
    attempts = [_load_attempt(root, name) for name in run_names]
    if args.overwrite_derived:
        for path in (root / "attempt_index.json", root / "FINAL_REPORT.md", root / "SHA256SUMS.txt"):
            if path.exists():
                path.unlink()
    _write_json(
        root / "attempt_index.json",
        {
            "schema": "kineimu.m1.transport-experiment-attempt-index/0.1",
            "predeclared_plan_sha256": plan_hash,
            "attempts": attempts,
        },
    )
    _write_report(root, plan_hash, attempts)
    _write_hash_manifest(root)
    print(json.dumps({"root": str(root), "plan_sha256": plan_hash, "runs": run_names}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
