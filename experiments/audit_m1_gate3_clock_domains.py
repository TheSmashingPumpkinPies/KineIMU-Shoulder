"""Independently audit strict Gate 3 evidence with both monotonic clock domains."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from kineimu_shoulder.io.m1_capture import iter_capture_records
from kineimu_shoulder.io.m1_packet import NodeId, decode_sample_packet

EXPECTED_SERIALS = {"A": "0000000000000001", "B": "0000000000000002"}
CAPTURE_NS = 15_000_000_000
MAX_CLOCK_PAIR_UNCERTAINTY_NS = 10_000_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _ndjson(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_sha = _sha256(manifest_path)
    sidecar_sha = (root / "manifest.sha256").read_text(encoding="ascii").split()[0].upper()
    if sidecar_sha != manifest_sha:
        raise ValueError("manifest.sha256 does not match manifest.json")
    if _sha256(root / "physical_gates_result.json") != manifest["result_sha256"]:
        raise ValueError("physical_gates_result.json hash mismatch")

    verified_files: list[dict[str, Any]] = []
    for relative_path, expected in manifest["files"].items():
        path = root / relative_path.replace("\\", "/")
        actual = {"sha256": _sha256(path), "size_bytes": path.stat().st_size}
        if actual["sha256"] != expected["sha256"].upper() or actual["size_bytes"] != expected["size_bytes"]:
            raise ValueError(f"manifest mismatch for {relative_path}")
        verified_files.append({"path": relative_path, **actual})

    gate_events = _ndjson(root / "physical_gates.ndjson")
    markers = [event for event in gate_events if event.get("event") == "matrix_capture_window"]
    if len(markers) != 2:
        raise ValueError(f"expected two capture markers, found {len(markers)}")

    node_reports: dict[str, Any] = {}
    for name in ("A", "B"):
        node_id = NodeId.A if name == "A" else NodeId.B
        matching_markers = [event for event in markers if event.get("node") == name]
        if len(matching_markers) != 1:
            raise ValueError(f"expected one capture marker for node {name}")
        marker = matching_markers[0]
        if marker.get("capture_clock_domain") != "perf_counter_ns":
            raise ValueError(f"node {name} marker has the wrong callback clock domain")
        perf_start = int(marker["capture_start_perf_counter_ns"])
        perf_deadline = int(marker["capture_deadline_perf_counter_ns"])
        host_start = int(marker["capture_start_host_monotonic_ns"])
        host_deadline = int(marker["capture_deadline_host_monotonic_ns"])
        uncertainty = int(marker["capture_clock_pair_uncertainty_ns"])
        if perf_deadline - perf_start != CAPTURE_NS or host_deadline - host_start != CAPTURE_NS:
            raise ValueError(f"node {name} marker does not span exactly 15 seconds in both clock domains")
        if marker.get("duration_ns") != CAPTURE_NS:
            raise ValueError(f"node {name} perf-counter duration field is inconsistent")
        if uncertainty < 0 or uncertainty > MAX_CLOCK_PAIR_UNCERTAINTY_NS:
            raise ValueError(f"node {name} clock-pair uncertainty is invalid or exceeds 10 ms")
        if marker.get("host_monotonic_ns") != host_start:
            raise ValueError(f"node {name} event timestamp is not the host-monotonic capture start")

        node_dir = root / "gate3" / f"node-{name.lower()}"
        node_result = json.loads((node_dir / "node_gate_result.json").read_text(encoding="utf-8"))
        if node_result.get("usb_serial") != EXPECTED_SERIALS[name]:
            raise ValueError(f"node {name} USB serial mismatch")
        if node_result.get("identity", {}).get("passed") is not True:
            raise ValueError(f"node {name} identity did not pass")
        if node_result.get("mtu", {}).get("passed") is not True:
            raise ValueError(f"node {name} MTU check did not pass")
        if node_result.get("control_off", {}).get("rc") != 0:
            raise ValueError(f"node {name} initial OFF did not return rc=0")
        if node_result.get("cleanup_off", {}).get("rc") != 0:
            raise ValueError(f"node {name} cleanup OFF did not return rc=0")
        if node_result.get("peripheral_disconnect", {}).get("completed") is not True:
            raise ValueError(f"node {name} peripheral disconnect event missing")
        if not all(item.get("completed") is True for item in node_result.get("disconnects", [])):
            raise ValueError(f"node {name} host disconnect confirmation failed")
        if node_result.get("capture", {}).get("passed") is not True:
            raise ValueError(f"node {name} capture gate did not pass")

        raw_path = node_dir / "capture" / "raw" / f"node-{name.lower()}.kimu"
        event_path = node_dir / "capture" / "raw" / f"node-{name.lower()}.events.ndjson"
        events = _ndjson(event_path)
        timing = [event for event in events if event.get("event") == "notify_callback_timing"]
        notifications = [event for event in events if event.get("event") == "notify"]
        accepted_perf_times: list[int] = []
        accepted_count = 0
        rejected_count = 0
        for event in timing:
            perf_check = event.get("capture_window_check_perf_counter_ns")
            host_callback = event.get("callback_start_host_monotonic_ns")
            if event.get("capture_clock_domain") != "perf_counter_ns":
                raise ValueError(f"node {name} callback has the wrong capture clock domain")
            if not isinstance(perf_check, int) or perf_check != event.get("callback_start_perf_counter_ns"):
                raise ValueError(f"node {name} admission time differs from its perf-counter callback start")
            if not isinstance(host_callback, int):
                raise ValueError(f"node {name} callback event lacks its host-monotonic start time")
            if event.get("host_monotonic_ns") != event.get("callback_start_perf_counter_ns"):
                raise ValueError(f"node {name} callback event/raw clock aliases are inconsistent")
            expected_accepted = perf_start <= perf_check < perf_deadline
            if event.get("capture_window_accepted") is not expected_accepted:
                raise ValueError(f"node {name} admission flag contradicts the perf-counter bounds")
            if expected_accepted:
                if host_callback < host_start:
                    raise ValueError(f"node {name} accepted callback precedes the host capture marker")
                accepted_count += 1
                accepted_perf_times.append(perf_check)
            else:
                rejected_count += 1

        with raw_path.open("rb") as stream:
            raw_records = list(iter_capture_records(stream))
        raw_times: list[int] = []
        for record in raw_records:
            if not perf_start <= record.host_monotonic_ns < perf_deadline:
                raise ValueError(f"node {name} raw record lies outside the perf-counter bounds")
            packet = decode_sample_packet(record.payload)
            if packet.node_id is not node_id:
                raise ValueError(f"node {name} raw packet has the wrong node ID")
            raw_times.append(record.host_monotonic_ns)
        if accepted_count != len(raw_records) or raw_times != accepted_perf_times:
            raise ValueError(f"node {name} accepted callbacks and raw records do not match")
        if len(notifications) != len(raw_records):
            raise ValueError(f"node {name} notify sidecar and raw record counts differ")
        if any(
            event.get("crc_ok") is not True
            or event.get("decode_ok") is not True
            or event.get("node_mismatch") is not False
            for event in notifications
        ):
            raise ValueError(f"node {name} notify sidecar reports a packet error")
        qc = next((event for event in events if event.get("event") == "qc_summary"), {})
        if any(qc.get(key, 0) != 0 for key in ("decode_errors", "framing_errors", "node_mismatches")):
            raise ValueError(f"node {name} QC sidecar reports errors")

        trace = node_result.get("trace", [])
        if len(trace) < 2:
            raise ValueError(f"node {name} lacks two firmware trace snapshots")
        counter_deltas = {
            key: int(trace[-1][key]) - int(trace[0][key])
            for key in ("callback", "raw_try", "raw_ok", "notify_calls")
        }
        if any(delta <= 0 for delta in counter_deltas.values()):
            raise ValueError(f"node {name} firmware counters did not all increase")

        node_reports[name] = {
            "usb_serial": EXPECTED_SERIALS[name],
            "capture_clock_domain": "perf_counter_ns",
            "capture_start_perf_counter_ns": perf_start,
            "capture_deadline_perf_counter_ns": perf_deadline,
            "capture_start_host_monotonic_ns": host_start,
            "capture_deadline_host_monotonic_ns": host_deadline,
            "clock_pair_uncertainty_ns": uncertainty,
            "capture_duration_ns": perf_deadline - perf_start,
            "callback_count": len(timing),
            "accepted_callbacks": accepted_count,
            "rejected_callbacks": rejected_count,
            "raw_record_count": len(raw_records),
            "valid_packets": len(raw_records),
            "raw_bytes": raw_path.stat().st_size,
            "event_sidecar_bytes": event_path.stat().st_size,
            "raw_sha256": _sha256(raw_path),
            "event_sidecar_sha256": _sha256(event_path),
            "firmware_counter_deltas": counter_deltas,
            "identity_mtu_disconnect_off": True,
        }

    for check in verified_files:
        path = root / check["path"].replace("\\", "/")
        if _sha256(path) != check["sha256"] or path.stat().st_size != check["size_bytes"]:
            raise ValueError(f"input changed during independent audit: {check['path']}")
    return {
        "schema": "kineimu.m1.gate3-independent-clock-domain-audit/1",
        "gate_passed": True,
        "source_root": str(root),
        "source_manifest_sha256": manifest_sha,
        "manifest_file_count_verified": len(verified_files),
        "raw_inputs_unchanged_during_recalculation": True,
        "audit_script_sha256": _sha256(Path(__file__).resolve()),
        "nodes": node_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.root)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
