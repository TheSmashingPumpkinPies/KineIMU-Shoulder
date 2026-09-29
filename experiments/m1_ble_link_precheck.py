"""Acquire and independently audit the bounded M1 BLE link-count precheck."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from experiments import m1_ble_link_matrix as matrix_runner
from experiments.m1_ble_connparam_independent_analysis import (
    audit_run_timing_events,
    capture_quality,
    count_invalid_event_lines,
    decode_raw_capture,
    diagnostic_summary,
    parse_cdc,
    raw_input_hashes,
    read_events,
    sha256,
    verify_manifest,
)
from experiments.m1_transport_experiment import EventLog
from kineimu_shoulder.io.m1_packet import NodeId

JSON = dict[str, Any]

PRECHECK_PLAN_PATH = Path(__file__).with_name("M1_BLE_LINK_COUNT_PRECHECK_PLAN_V3_20260923.md")
PRECHECK_PLAN_SHA256 = "964BDDD488915250411A621CF557F56F4CFC6A8848C115FE80ADDDD290D6F7B0"
PRECHECK_OUTPUT_ROOT = Path("<external-data>/kineimu_m1_root_cause_precheck_20260923_03")
PRECHECK_PLAN_V4_PATH = Path(__file__).with_name(
    "M1_BLE_LINK_COUNT_COLD_START_PRECHECK_PLAN_V4_20260924.md"
)
PRECHECK_PLAN_V4_SHA256 = "E277E7AAF46F310F094A297E94CE0ED7F4861E12BCA05A2C8D540A7D8612F7AE"
PRECHECK_V4_OUTPUT_ROOTS = {
    "a_only": Path("<external-data>/kineimu_m1_root_cause_precheck_20260924_01_a_only"),
    "dual_a_to_b": Path(
        "<external-data>/kineimu_m1_root_cause_precheck_20260924_02_dual_a_to_b"
    ),
}
PRECHECK_PLAN_V5_PATH = Path(__file__).with_name(
    "M1_BLE_LINK_COUNT_COLD_START_PRECHECK_PLAN_V5_20260924.md"
)
PRECHECK_PLAN_V5_SHA256 = "2A18B7EA52C1F414695B7C4C1C99E15365C0C1BD9E8756B12042495232E426B2"
PRECHECK_V5_OUTPUT_ROOTS = {
    "a_only": Path(
        "<external-data>/kineimu_m1_root_cause_precheck_20260924_v5_01_a_only"
    ),
    "dual_a_to_b": Path(
        "<external-data>/kineimu_m1_root_cause_precheck_20260924_v5_02_dual_a_to_b"
    ),
}
PRECHECK_PLAN_V6_PATH = Path(__file__).with_name(
    "M1_BLE_LINK_COUNT_COLD_START_PRECHECK_PLAN_V6_20260924.md"
)
PRECHECK_PLAN_V6_SHA256 = "87BCEDC63917FD6F250A85E70883370013CA72D01A14F80ECA9EFA593E834BB8"
PRECHECK_V6_OUTPUT_ROOTS = {
    "a_only": Path(
        "<external-data>/kineimu_m1_root_cause_precheck_20260924_v6_01_a_only"
    ),
    "dual_a_to_b": Path(
        "<external-data>/kineimu_m1_root_cause_precheck_20260924_v6_02_dual_a_to_b"
    ),
}
PRECHECK_V3_BOOT_IDS = {
    "A": 4610435006230911040,
    "B": 9200877888179811312,
}
PRECHECK_SCHEDULE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("OFF", ("a_only", "dual_a_to_b", "b_only", "dual_b_to_a")),
)
PRECHECK_CAPTURE_SECONDS = 15.0
PRECHECK_REST_SECONDS = 2.0
PRECHECK_SETTLE_SECONDS = 10.0
PRECHECK_CONNECT_TIMEOUT_SECONDS = 15.0
PRECHECK_V5_CONNECT_TIMEOUT_SECONDS = 30.0
PRECHECK_PLAN_SOURCE_V2_SHA256 = matrix_runner.ROOT_CAUSE_PLAN_V2_SHA256
PRECHECK_SOURCE_ROOT = Path(
    "<external-data>/kineimu_m1_ble_connparam_rootcause_v2_20260923_01"
)
PRECHECK_SOURCE_PREFLASH = PRECHECK_SOURCE_ROOT / "preflash_firmware_and_hardware_check.json"
PRECHECK_SOURCE_PREFLASH_SHA256 = (
    "DC9E947D82C5E11E95B6289F19A670D7E05B054A1F90E0EFD0708C7F0A8A7881"
)
PRECHECK_FIRMWARE_SOURCE_COMMIT = "270911756c227a20feb18df71edad7ad4544aedb"
PRECHECK_IMAGE_SHA256 = {
    NodeId.A: "226B77FCEA1054022DA9F0E9884D3297245050A88156CE2EAD7A9177B4177380",
    NodeId.B: "6B38472B703D9B102767A1823BC34876EE24B0AA67AA328E346F1312B8525B32",
}
PRECHECK_CONFIG_SHA256 = "0B166B62708A98477DA77E0DFC65B58A0E72B0A3EC85FF47CF7D3A99BA581E69"
PRECHECK_BLE_ADDRESSES = {
    NodeId.A: "02:00:00:00:00:01",
    NodeId.B: "02:00:00:00:00:02",
}
PRECHECK_HARDWARE_DEVICE_IDS = {
    NodeId.A: 1,
    NodeId.B: 2,
}
PRECHECK_BOARD_ID = "Seeed_XIAO_nRF52840_Sense"
PRECHECK_ADAPTER_INSTANCE_PREFIX = r"USB\VID_13D3&PID_3563&MI_00"
PRECHECK_ADAPTER_DRIVER_INF = "oem134.inf"
PRECHECK_ADAPTER_DRIVER_VERSION = "1.3.17.169"
PRECHECK_RUNTIME_CDC_VID = 0x2FE3
PRECHECK_RUNTIME_CDC_PID = 0x0004
PRECHECK_MTU = 127


def precheck_connect_timeout_seconds(plan_version: str) -> float:
    """Return the locked host connect/GATT allowance for a precheck plan."""

    if plan_version in {"v3", "v4"}:
        return PRECHECK_CONNECT_TIMEOUT_SECONDS
    if plan_version == "v5":
        return PRECHECK_V5_CONNECT_TIMEOUT_SECONDS
    if plan_version == "v6":
        return PRECHECK_V5_CONNECT_TIMEOUT_SECONDS
    raise ValueError(f"unsupported precheck plan version: {plan_version}")


def audit_connect_timeout_config(run_config: JSON, expected_plan_sha256: str) -> list[str]:
    """Require a cold-start run's recorded setup deadline to match its plan."""

    if expected_plan_sha256 == PRECHECK_PLAN_V5_SHA256:
        plan_version = "v5"
    elif expected_plan_sha256 == PRECHECK_PLAN_V6_SHA256:
        plan_version = "v6"
    else:
        return []
    expected_timeout = precheck_connect_timeout_seconds(plan_version)
    if run_config.get("windows_connect_gatt_setup_timeout_seconds") == expected_timeout:
        return []
    return [
        "run config connect/GATT setup timeout differs from the locked "
        f"{plan_version.upper()} allowance ({expected_timeout:.1f}s)"
    ]


def precheck_order(
    plan_version: str = "v3", condition: str | None = None
) -> tuple[str, ...]:
    """Return the once-only condition order for a locked precheck plan."""

    if plan_version == "v3":
        if condition is not None:
            raise ValueError("V3 precheck order does not accept a single condition")
        return tuple(
            condition
            for _mode, conditions in PRECHECK_SCHEDULE
            for condition in conditions
        )
    if plan_version == "v4":
        if condition not in PRECHECK_V4_OUTPUT_ROOTS:
            raise ValueError(
                "V4 precheck requires one of "
                + ", ".join(sorted(PRECHECK_V4_OUTPUT_ROOTS))
            )
        return (condition,)
    if plan_version == "v5":
        if condition not in PRECHECK_V5_OUTPUT_ROOTS:
            raise ValueError(
                "V5 precheck requires one of "
                + ", ".join(sorted(PRECHECK_V5_OUTPUT_ROOTS))
            )
        return (condition,)
    if plan_version == "v6":
        if condition not in PRECHECK_V6_OUTPUT_ROOTS:
            raise ValueError(
                "V6 precheck requires one of "
                + ", ".join(sorted(PRECHECK_V6_OUTPUT_ROOTS))
            )
        return (condition,)
    raise ValueError(f"unsupported precheck plan version: {plan_version}")


def _cold_start_roots_for_version(plan_version: str) -> dict[str, Path]:
    if plan_version == "v4":
        return PRECHECK_V4_OUTPUT_ROOTS
    if plan_version == "v5":
        return PRECHECK_V5_OUTPUT_ROOTS
    if plan_version == "v6":
        return PRECHECK_V6_OUTPUT_ROOTS
    raise ValueError(f"unsupported cold-start precheck plan version: {plan_version}")


def _precheck_profile(
    plan_version: str,
    condition: str | None,
) -> tuple[Path, str, Path, tuple[tuple[str, tuple[str, ...]], ...], tuple[str, ...]]:
    if plan_version == "v3":
        if condition is not None:
            raise ValueError("V3 precheck does not accept a condition argument")
        return (
            PRECHECK_PLAN_PATH,
            PRECHECK_PLAN_SHA256,
            PRECHECK_OUTPUT_ROOT,
            PRECHECK_SCHEDULE,
            precheck_order(),
        )
    if plan_version == "v4":
        order = precheck_order(plan_version, condition)
        assert condition is not None
        return (
            PRECHECK_PLAN_V4_PATH,
            PRECHECK_PLAN_V4_SHA256,
            PRECHECK_V4_OUTPUT_ROOTS[condition],
            (("OFF", (condition,)),),
            order,
        )
    if plan_version == "v5":
        order = precheck_order(plan_version, condition)
        assert condition is not None
        return (
            PRECHECK_PLAN_V5_PATH,
            PRECHECK_PLAN_V5_SHA256,
            PRECHECK_V5_OUTPUT_ROOTS[condition],
            (("OFF", (condition,)),),
            order,
        )
    if plan_version == "v6":
        order = precheck_order(plan_version, condition)
        assert condition is not None
        return (
            PRECHECK_PLAN_V6_PATH,
            PRECHECK_PLAN_V6_SHA256,
            PRECHECK_V6_OUTPUT_ROOTS[condition],
            (("OFF", (condition,)),),
            order,
        )
    raise ValueError(f"unsupported precheck plan version: {plan_version}")


def active_nodes_for_condition(condition: str) -> tuple[str, ...]:
    """Return the expected logical node order for a precheck condition."""

    if condition == "a_only":
        return ("A",)
    if condition == "b_only":
        return ("B",)
    if condition == "dual_a_to_b":
        return ("A", "B")
    if condition == "dual_b_to_a":
        return ("B", "A")
    raise ValueError(f"unsupported link-count precheck condition: {condition}")


def validate_runtime_cdc_port(node: NodeId, port_info: dict[str, object]) -> None:
    """Require the application CDC interface, never a same-serial UF2 port."""

    expected_serial = matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node]
    observed_serial = str(port_info.get("serial_number", ""))
    if observed_serial != expected_serial:
        raise RuntimeError(
            f"Node {node.name} CDC USB serial differs: observed {observed_serial!r}, "
            f"expected {expected_serial}"
        )
    vid_value = port_info.get("vid")
    pid_value = port_info.get("pid")
    if not isinstance(vid_value, int) or not isinstance(pid_value, int):
        raise RuntimeError(f"Node {node.name} CDC VID/PID is unavailable")
    vid = vid_value
    pid = pid_value
    if (vid, pid) != (PRECHECK_RUNTIME_CDC_VID, PRECHECK_RUNTIME_CDC_PID):
        raise RuntimeError(
            f"Node {node.name} CDC interface is {vid:04X}:{pid:04X}; "
            "expected application CDC 2FE3:0004"
        )


def audit_active_link_state(condition: str, control_events: list[JSON]) -> JSON:
    """Verify the scheduled link count, connect order, and active window overlap."""

    expected_nodes = active_nodes_for_condition(condition)
    errors: list[str] = []
    connect_events = sorted(
        (
            int(event["host_monotonic_ns"]),
            str(event.get("node")),
        )
        for event in control_events
        if event.get("event") == "peripheral_connected_event"
        and isinstance(event.get("host_monotonic_ns"), int)
    )
    observed_order = tuple(node for _timestamp, node in connect_events)
    if observed_order != expected_nodes:
        errors.append(
            f"observed firmware connection order {observed_order} differs from {expected_nodes}"
        )

    marker_events = [
        event for event in control_events if event.get("event") == "matrix_capture_window"
    ]
    markers_by_node: dict[str, list[JSON]] = {}
    for event in marker_events:
        node = str(event.get("node"))
        markers_by_node.setdefault(node, []).append(event)
    if set(markers_by_node) != set(expected_nodes):
        errors.append(
            f"capture marker node set {sorted(markers_by_node)} differs from {sorted(expected_nodes)}"
        )

    window_starts: list[int] = []
    window_deadlines: list[int] = []
    for node in expected_nodes:
        markers = markers_by_node.get(node, [])
        if len(markers) != 1:
            errors.append(f"Node {node} expected one capture marker, found {len(markers)}")
            continue
        marker = markers[0]
        start_host = marker.get("capture_start_host_monotonic_ns")
        deadline_host = marker.get("capture_deadline_host_monotonic_ns")
        start_perf = marker.get("capture_start_perf_counter_ns")
        deadline_perf = marker.get("capture_deadline_perf_counter_ns")
        if not all(
            isinstance(value, int)
            for value in (start_host, deadline_host, start_perf, deadline_perf)
        ):
            errors.append(f"Node {node} capture marker has incomplete clock bounds")
            continue
        start_host_ns = cast(int, start_host)
        deadline_host_ns = cast(int, deadline_host)
        start_perf_ns = cast(int, start_perf)
        deadline_perf_ns = cast(int, deadline_perf)
        if deadline_perf_ns - start_perf_ns != int(PRECHECK_CAPTURE_SECONDS * 1_000_000_000):
            errors.append(f"Node {node} strict capture boundary is not exactly 15.0 seconds")
        window_starts.append(start_host_ns)
        window_deadlines.append(deadline_host_ns)

    first_window_start = min(window_starts) if window_starts else None
    last_window_deadline = max(window_deadlines) if window_deadlines else None
    if first_window_start is not None:
        for connect_ns, node in connect_events:
            if node in expected_nodes and connect_ns >= first_window_start:
                errors.append(f"Node {node} connected after its capture window began")

    if len(expected_nodes) == 2 and len(window_starts) == 2 and len(window_deadlines) == 2:
        overlap_value_ns = min(window_deadlines) - max(window_starts)
        if overlap_value_ns < int((PRECHECK_CAPTURE_SECONDS - 0.1) * 1_000_000_000):
            errors.append("dual links did not overlap for the full shared capture window")
        overlap_ns: int | None = overlap_value_ns
    else:
        overlap_ns = None

    if first_window_start is not None and last_window_deadline is not None:
        for event in control_events:
            event_ns = event.get("host_monotonic_ns")
            if (
                event.get("event") == "peripheral_disconnected_event"
                and event.get("node") in expected_nodes
                and isinstance(event_ns, int)
                and first_window_start <= event_ns <= last_window_deadline
            ):
                errors.append(
                    f"Node {event.get('node')} disconnected before the shared capture ended"
                )

    return {
        "expected_active_links": len(expected_nodes),
        "observed_connection_order": list(observed_order),
        "connected_nodes": list(observed_order),
        "window_start_host_monotonic_ns": first_window_start,
        "window_deadline_host_monotonic_ns": last_window_deadline,
        "concurrent_capture_overlap_ns": overlap_ns,
        "errors": errors,
        "realized": not errors,
    }


_TX_LIFETIME_COUNTERS = (
    "calls",
    "accepted",
    "final_fail",
    "packet_drops",
    "enomem",
    "eagain",
    "retries",
    "window_full",
    "wait_us",
    "completed",
    "cancelled",
    "callbacks_stale",
    "callbacks_cancelled",
    "callbacks_unexpected",
    "age_count",
)


def summarize_physical_connection_tx(
    tx_summary: JSON,
    snapshots: list[JSON],
    *,
    expected_boot_id: int | None,
) -> JSON:
    """Keep boot-lifetime TX totals whole across telemetry queue epoch changes.

    Firmware ``generation`` identifies a queue lifetime, not a BLE connection.
    Snapshots carry cumulative counters, so physical-connection totals must be
    read from the terminal snapshot after checking one fresh, unsaturated boot.
    """

    errors: list[str] = []
    if len(snapshots) < 2:
        errors.append("physical-connection TX diagnostics contain fewer than two snapshots")
    if tx_summary.get("snapshot_count") != len(snapshots):
        errors.append("TX summary snapshot count differs from the raw CDC snapshots")
    if expected_boot_id is None:
        errors.append("fresh pre-notify boot ID is unavailable for TX diagnostics")

    previous: JSON | None = None
    transition_deltas: list[JSON] = []
    observed_generations: list[int] = []
    for index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, dict):
            errors.append(f"TX snapshot {index + 1} is malformed")
            continue
        if snapshot.get("boot") != expected_boot_id:
            errors.append(f"TX snapshot {index + 1} boot ID differs from the fresh boot gate")
        generation = snapshot.get("generation")
        if not isinstance(generation, int):
            errors.append(f"TX snapshot {index + 1} has no integer queue generation")
        elif not observed_generations or observed_generations[-1] != generation:
            if observed_generations and generation < observed_generations[-1]:
                errors.append("TX queue generation moved backwards within one physical boot")
            observed_generations.append(generation)
        if snapshot.get("saturated") != 0:
            errors.append(f"TX snapshot {index + 1} is saturated or has unknown saturation state")
        if snapshot.get("parse_errors"):
            errors.append(f"TX snapshot {index + 1} has parse errors")
        for name in _TX_LIFETIME_COUNTERS:
            if not isinstance(snapshot.get(name), int):
                errors.append(f"TX snapshot {index + 1} is missing integer counter {name}")
        schedule_fail = snapshot.get("schedule_fail")
        if not (
            isinstance(schedule_fail, list)
            and len(schedule_fail) == 2
            and all(isinstance(value, int) for value in schedule_fail)
        ):
            errors.append(f"TX snapshot {index + 1} has incomplete schedule failure counters")
        inflight = snapshot.get("inflight")
        if not (isinstance(inflight, list) and len(inflight) == 2):
            errors.append(f"TX snapshot {index + 1} has incomplete in-flight counters")
        age_bins = snapshot.get("age_bins")
        if not (isinstance(age_bins, list) and len(age_bins) == 8):
            errors.append(f"TX snapshot {index + 1} has incomplete completion-age bins")
        age_us = snapshot.get("age_us")
        if not (isinstance(age_us, list) and len(age_us) == 4):
            errors.append(f"TX snapshot {index + 1} has incomplete completion-age totals")

        if previous is not None:
            for name in _TX_LIFETIME_COUNTERS:
                before, after = previous.get(name), snapshot.get(name)
                if not isinstance(before, int) or not isinstance(after, int) or after < before:
                    errors.append(f"cumulative TX counter {name} is not monotonic")
            before_schedule, after_schedule = previous.get("schedule_fail"), schedule_fail
            if (
                isinstance(before_schedule, list)
                and isinstance(after_schedule, list)
                and len(before_schedule) == len(after_schedule) == 2
            ):
                if any(after < before for before, after in zip(before_schedule, after_schedule, strict=True)):
                    errors.append("cumulative TX schedule-failure counters are not monotonic")
            before_returns, after_returns = (
                previous.get("return_counts"),
                snapshot.get("return_counts"),
            )
            if isinstance(before_returns, dict) and isinstance(after_returns, dict):
                for code in set(before_returns) | set(after_returns):
                    before, after = before_returns.get(code, 0), after_returns.get(code, 0)
                    if not isinstance(before, int) or not isinstance(after, int) or after < before:
                        errors.append(f"cumulative TX return count {code} is not monotonic")
            before_bins = previous.get("age_bins")
            if isinstance(before_bins, list) and isinstance(age_bins, list) and len(before_bins) == len(age_bins) == 8:
                if any(after < before for before, after in zip(before_bins, age_bins, strict=True)):
                    errors.append("cumulative TX completion-age bins are not monotonic")
            before_age_us = previous.get("age_us")
            if (
                isinstance(before_age_us, list)
                and isinstance(age_us, list)
                and len(before_age_us) == len(age_us) == 4
                and age_us[3] < before_age_us[3]
            ):
                errors.append("cumulative TX completion-age total is not monotonic")
            before_generation = previous.get("generation")
            if generation != before_generation:
                deltas = {
                    name: (
                        snapshot[name] - previous[name]
                        if isinstance(snapshot.get(name), int)
                        and isinstance(previous.get(name), int)
                        and snapshot[name] >= previous[name]
                        else None
                    )
                    for name in _TX_LIFETIME_COUNTERS
                }
                transition_deltas.append(
                    {
                        "from_generation": before_generation,
                        "to_generation": generation,
                        "counter_deltas": deltas,
                        "attribution": "between_queue_epoch_snapshots",
                    }
                )
        previous = snapshot

    if snapshots:
        terminal = snapshots[-1]
        inflight = terminal.get("inflight")
        if terminal.get("window_owned") != 0:
            errors.append("terminal TX snapshot still owns a notification window")
        if not isinstance(inflight, list) or len(inflight) != 2 or inflight[0] != 0:
            errors.append("terminal TX snapshot has an in-flight notification")
        physical_totals = {
            name: terminal.get(name) for name in _TX_LIFETIME_COUNTERS
        }
        schedule_fail = terminal.get("schedule_fail")
        physical_totals["schedule_fail_initial"] = (
            schedule_fail[0] if isinstance(schedule_fail, list) and len(schedule_fail) == 2 else None
        )
        physical_totals["schedule_fail_retry"] = (
            schedule_fail[1] if isinstance(schedule_fail, list) and len(schedule_fail) == 2 else None
        )
        physical_totals["return_counts"] = terminal.get("return_counts")
        physical_totals["age_bins"] = terminal.get("age_bins")
        physical_totals["age_us"] = terminal.get("age_us")
        physical_totals["window_owned"] = terminal.get("window_owned")
        physical_totals["inflight"] = inflight
    else:
        physical_totals = {}

    active_queue_generations: list[int] = []
    for segment in tx_summary.get("segments", []):
        generation = segment.get("connection_generation")
        deltas = segment.get("counter_deltas", {})
        if not isinstance(generation, int) or not isinstance(deltas, dict):
            continue
        if any(
            isinstance(deltas.get(name), int) and deltas[name] > 0
            for name in ("calls", "accepted", "final_fail", "packet_drops", "enomem", "eagain")
        ):
            active_queue_generations.append(generation)

    return {
        "physical_connection_boot_id": expected_boot_id,
        "queue_epoch_generations_observed": observed_generations,
        "active_queue_generations": active_queue_generations,
        "physical_connection_totals": physical_totals,
        "totals_scope": "cumulative counters since the fresh firmware boot gate",
        "transition_deltas": transition_deltas,
        "transition_attribution": (
            "counter changes between generation-labelled snapshots are not assigned "
            "to either queue epoch"
        ),
        "snapshot_count": len(snapshots),
        "errors": errors,
        "valid": not errors,
    }


def sample_sequence_gap_errors(
    raw_capture: JSON,
    *,
    expected_plan_sha256: str,
    node: str,
) -> list[str]:
    """Keep sequence loss as an outcome in V6 while requiring it be measurable."""

    gap_fields = ("packet_sequence_gaps", "sample_sequence_gaps")
    if expected_plan_sha256.upper() == PRECHECK_PLAN_V6_SHA256:
        return [
            f"Node {node} raw capture omits measurable {field}"
            for field in gap_fields
            if not isinstance(raw_capture.get(field), int)
        ]
    gaps = raw_capture.get("sample_sequence_gaps")
    if not isinstance(gaps, int):
        return [f"Node {node} raw sample sequence gap count is unavailable"]
    if gaps != 0:
        return [f"Node {node} raw sample sequence has {gaps} gaps"]
    return []


def validate_plan_output_root(
    plan_sha256: str,
    root_dir: Path,
    *,
    condition: str | None = None,
) -> Path:
    """Bind this one precheck plan to its own once-only evidence directory."""

    normalized = plan_sha256.upper()
    if normalized == PRECHECK_PLAN_SHA256:
        if condition is not None:
            raise ValueError("V3 precheck output root does not accept a condition")
        expected_root = PRECHECK_OUTPUT_ROOT.resolve()
    elif normalized == PRECHECK_PLAN_V4_SHA256:
        if condition not in PRECHECK_V4_OUTPUT_ROOTS:
            raise ValueError(
                "V4 precheck output root requires one of "
                + ", ".join(sorted(PRECHECK_V4_OUTPUT_ROOTS))
            )
        expected_root = PRECHECK_V4_OUTPUT_ROOTS[condition].resolve()
    elif normalized == PRECHECK_PLAN_V5_SHA256:
        if condition not in PRECHECK_V5_OUTPUT_ROOTS:
            raise ValueError(
                "V5 precheck output root requires one of "
                + ", ".join(sorted(PRECHECK_V5_OUTPUT_ROOTS))
            )
        expected_root = PRECHECK_V5_OUTPUT_ROOTS[condition].resolve()
    elif normalized == PRECHECK_PLAN_V6_SHA256:
        if condition not in PRECHECK_V6_OUTPUT_ROOTS:
            raise ValueError(
                "V6 precheck output root requires one of "
                + ", ".join(sorted(PRECHECK_V6_OUTPUT_ROOTS))
            )
        expected_root = PRECHECK_V6_OUTPUT_ROOTS[condition].resolve()
    else:
        raise ValueError(f"unknown precheck plan SHA-256: {plan_sha256}")
    if root_dir.resolve() != expected_root:
        raise ValueError(
            f"precheck plan SHA-256 {normalized} requires locked output root {expected_root}"
        )
    return expected_root


def write_sha256_manifest(root_dir: Path) -> Path:
    """Write a once-only SHA-256 listing for every current file under ``root_dir``."""

    root = root_dir.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"precheck evidence root does not exist: {root}")
    manifest = root / "SHA256SUMS.txt"
    if manifest.exists():
        raise FileExistsError(f"refusing to overwrite precheck manifest: {manifest}")
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.resolve() != manifest
    )
    with manifest.open("x", encoding="utf-8", newline="\n") as stream:
        for path in files:
            stream.write(f"{sha256(path)}  {path.relative_to(root).as_posix()}\n")
    return manifest


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _read_json(path: Path) -> JSON:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object at {path}")
    return cast(JSON, value)


def _read_ndjson(path: Path) -> list[JSON]:
    events: list[JSON] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        events.append(cast(JSON, value))
    return events


def _run_git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_committed_precheck_inputs(repo_root: Path, paths: tuple[Path, ...]) -> None:
    """Require a clean tracked tree and tracked plan/source files.

    Existing pytest scratch outputs can be untracked and access-restricted. They
    are preserved and do not alter the committed code that this plan locks.
    """

    dirty_tracked = _run_git(
        repo_root,
        "status",
        "--porcelain",
        "--untracked-files=no",
    )
    if dirty_tracked:
        raise RuntimeError(
            "precheck acquisition requires a clean tracked code tree; "
            f"found tracked changes: {dirty_tracked}"
        )
    root = repo_root.resolve()
    for path in paths:
        try:
            relative_path = path.resolve().relative_to(root).as_posix()
        except ValueError as error:
            raise RuntimeError(f"precheck input must live in the repository: {path}") from error
        tracked_path = _run_git(repo_root, "ls-files", "--error-unmatch", relative_path)
        if not tracked_path:
            raise RuntimeError(f"precheck input is not tracked by the current Git HEAD: {path}")


def _read_live_adapter_identity() -> JSON:
    """Read the sole expected MediaTek controller and its installed driver."""

    if sys.platform != "win32":
        raise RuntimeError("the locked physical precheck requires its Windows host")
    command = (
        "$d = @(Get-PnpDevice -PresentOnly -Class Bluetooth | "
        "Where-Object { $_.InstanceId -like 'USB\\VID_13D3&PID_3563&MI_00*' "
        "-and $_.FriendlyName -match 'MediaTek' }); "
        "if ($d.Count -ne 1) { throw ('expected one MediaTek adapter, found ' + $d.Count) }; "
        "$id = $d[0].InstanceId; "
        "$inf = (Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_DriverInfPath').Data; "
        "$ver = (Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_DriverVersion').Data; "
        "$date = (Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_DriverDate').Data; "
        "[pscustomobject]@{status=$d[0].Status;friendly_name=$d[0].FriendlyName;"
        "instance_id=$id;driver_inf=$inf;driver_version=$ver;driver_date=$date} "
        "| ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
        timeout=15.0,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("Windows adapter query returned no single device object")
    identity = cast(JSON, value)
    instance_id = str(identity.get("instance_id", ""))
    if not instance_id.startswith(PRECHECK_ADAPTER_INSTANCE_PREFIX):
        raise RuntimeError(f"unexpected BLE controller instance ID: {instance_id}")
    if str(identity.get("driver_inf", "")).casefold() != PRECHECK_ADAPTER_DRIVER_INF.casefold():
        raise RuntimeError(f"unexpected BLE controller driver INF: {identity.get('driver_inf')}")
    if str(identity.get("driver_version")) != PRECHECK_ADAPTER_DRIVER_VERSION:
        raise RuntimeError(
            f"unexpected BLE controller driver version: {identity.get('driver_version')}"
        )
    if identity.get("status") != "OK":
        raise RuntimeError(f"BLE controller is not ready: status={identity.get('status')}")
    return identity


def _validate_source_artifacts() -> tuple[JSON, dict[NodeId, Path], dict[NodeId, Path]]:
    if not PRECHECK_SOURCE_PREFLASH.is_file():
        raise FileNotFoundError(f"source preflash record is missing: {PRECHECK_SOURCE_PREFLASH}")
    observed_preflash_hash = sha256(PRECHECK_SOURCE_PREFLASH).upper()
    if observed_preflash_hash != PRECHECK_SOURCE_PREFLASH_SHA256:
        raise ValueError("source v2 preflash-record hash differs from the locked precheck plan")
    preflash = _read_json(PRECHECK_SOURCE_PREFLASH)
    if preflash.get("plan_sha256", "").upper() != PRECHECK_PLAN_SOURCE_V2_SHA256.upper():
        raise ValueError("source preflash record does not identify the verified v2 plan")
    if preflash.get("firmware_source_commit") != PRECHECK_FIRMWARE_SOURCE_COMMIT:
        raise ValueError("source preflash record firmware commit differs from the locked plan")
    if preflash.get("build_configurations_identical") is not True:
        raise ValueError("source preflash record does not prove identical A/B build configs")

    images: dict[NodeId, Path] = {}
    configurations: dict[NodeId, Path] = {}
    preflash_images = preflash.get("firmware_images", {})
    preflash_configs = preflash.get("build_configs", {})
    boards = preflash.get("boards", {})
    if not all(isinstance(value, dict) for value in (preflash_images, preflash_configs, boards)):
        raise ValueError("source preflash identity records are incomplete")
    for node in (NodeId.A, NodeId.B):
        node_name = node.name
        image_info = preflash_images.get(node_name, {})
        config_info = preflash_configs.get(node_name, {})
        board_info = boards.get(node_name, {})
        image_path = PRECHECK_SOURCE_ROOT / "firmware" / f"node-{node_name.lower()}.uf2"
        config_path = Path(str(config_info.get("path", "")))
        if not image_path.is_file() or sha256(image_path).upper() != PRECHECK_IMAGE_SHA256[node]:
            raise ValueError(f"Node {node_name} image is missing or differs from the locked hash")
        if image_info.get("sha256", "").upper() != PRECHECK_IMAGE_SHA256[node]:
            raise ValueError(f"Node {node_name} source record image hash differs")
        if image_info.get("source_commit") != PRECHECK_FIRMWARE_SOURCE_COMMIT:
            raise ValueError(f"Node {node_name} source record commit differs")
        if image_info.get("node_id") != int(node):
            raise ValueError(f"Node {node_name} image has an unexpected node ID")
        if not config_path.is_file() or sha256(config_path).upper() != PRECHECK_CONFIG_SHA256:
            raise ValueError(f"Node {node_name} build config is missing or differs from the locked hash")
        if config_info.get("sha256", "").upper() != PRECHECK_CONFIG_SHA256:
            raise ValueError(f"Node {node_name} source record config hash differs")
        if board_info.get("board_id") != PRECHECK_BOARD_ID:
            raise ValueError(f"Node {node_name} source record board model differs")
        if board_info.get("bootloader_usb_serial") != matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node]:
            raise ValueError(f"Node {node_name} source record USB serial differs")
        if board_info.get("application_node_id_from_gate1") != int(node):
            raise ValueError(f"Node {node_name} source record application node ID differs")
        images[node] = image_path
        configurations[node] = config_path

    if configurations[NodeId.A].read_bytes() != configurations[NodeId.B].read_bytes():
        raise ValueError("A/B generated build configurations are not byte-identical")
    return preflash, images, configurations


async def _initialize_off_control(
    cdc_captures: dict[NodeId, matrix_runner._MatrixCdcCapture],
    events: EventLog,
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for node in (NodeId.A, NodeId.B):
        capture = cdc_captures[node]
        begin = await matrix_runner._run_control_worker(
            capture.begin_fresh_control_session,
            5.0,
        )
        events.write("precheck_control_session", node=node, result=begin)
        if begin.get("ready") is not True:
            raise matrix_runner.CdcControlGateError(
                f"Node {node.name} precheck CDC control session did not become ready"
            )
        ack = await matrix_runner._run_control_worker(capture.set_mode, "OFF", timeout_s=5.0)
        events.write("precheck_off_mode_acknowledgment", node=node, **ack)
        results[node.name] = ack
        if ack.get("applied") is not True or ack.get("rc") != 0:
            raise matrix_runner.CdcControlGateError(
                f"Node {node.name} did not acknowledge local parameter mode OFF"
            )
    return results


def _read_run_events(run_dir: Path, node_names: tuple[str, ...]) -> tuple[list[JSON], dict[str, list[JSON]]]:
    control = _read_ndjson(run_dir / "experiment_control.ndjson")
    by_node = {
        node: read_events(run_dir / "raw" / f"node-{node.lower()}.events.ndjson")
        for node in node_names
    }
    return control, by_node


def audit_fresh_acquisition_start(
    capture_events: list[JSON],
    control_events: list[JSON],
    node: str,
) -> JSON:
    """Require a pristine firmware acquisition state before telemetry starts."""

    errors: list[str] = []
    notify_events = [
        event
        for event in control_events
        if event.get("event") == "telemetry_notify_enabled"
        and event.get("node") == node
    ]
    if len(notify_events) != 1:
        return {
            "valid": False,
            "errors": [
                "expected one telemetry-notify enable event to anchor the acquisition start, "
                f"found {len(notify_events)}"
            ],
            "boot_id": None,
            "status": None,
        }

    notify = notify_events[0]
    notify_ns = notify.get("host_monotonic_ns")
    statuses = [
        event
        for event in capture_events
        if event.get("event") == "status"
        and event.get("source") == "read"
        and isinstance(event.get("connection_id"), str)
        and isinstance(event.get("host_monotonic_ns"), int)
        and isinstance(notify_ns, int)
        and event["host_monotonic_ns"] <= notify_ns
    ]
    if len(statuses) != 1:
        return {
            "valid": False,
            "errors": [
                "expected one pre-notify BLE status read for the active connection, "
                f"found {len(statuses)}"
            ],
            "boot_id": None,
            "status": None,
        }

    status = statuses[0]
    connection_id = status.get("connection_id")
    if not isinstance(connection_id, str) or not connection_id:
        errors.append("pre-notify BLE status has no connection generation ID")
    boot_id = status.get("boot_id")
    if not isinstance(boot_id, int) or boot_id <= 0:
        errors.append("pre-notify BLE status has no valid firmware boot ID")
    if status.get("acquisition_state") != "armed":
        errors.append(
            "pre-notify acquisition was not pristine armed state "
            f"(state={status.get('acquisition_state')!r})"
        )
    zero_fields = (
        "samples_acquired",
        "packets_generated",
        "sensor_fifo_overruns",
        "firmware_queue_overruns",
        "samples_dropped_before_packetization",
        "transport_backpressure_events",
        "transport_queue_high_water_packets",
        "acquisition_buffer_high_water_samples",
    )
    for field in zero_fields:
        value = status.get(field)
        if not isinstance(value, int):
            errors.append(f"pre-notify BLE status omits {field}")
        elif value != 0:
            errors.append(f"pre-notify BLE status {field} is {value}, expected zero")
    for field in ("last_sample_sequence", "last_packet_sequence"):
        if status.get(field) != 0xFFFFFFFF:
            errors.append(
                f"pre-notify BLE status {field} is not the never-produced sentinel"
            )
    return {
        "valid": not errors,
        "errors": errors,
        "boot_id": boot_id,
        "connection_id": connection_id,
        "status_host_monotonic_ns": status.get("host_monotonic_ns"),
        "status": status,
    }


def audit_pre_notify_status_gates(
    control_events: list[JSON],
    expected_nodes: tuple[str, ...],
) -> list[str]:
    """Require one successful experiment-side freshness gate per node."""

    errors: list[str] = []
    for node in expected_nodes:
        gate_events = [
            event
            for event in control_events
            if event.get("event") == "pre_notify_status_gate"
            and event.get("node") == node
        ]
        if len(gate_events) != 1 or gate_events[0].get("passed") is not True:
            errors.append(
                f"Node {node} pre-notify pristine-start gate was not passed exactly once"
            )
    return errors


def _audit_cleanup(
    run_result: JSON,
    control_events: list[JSON],
    node_names: tuple[str, ...],
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    complete_events = [
        event for event in control_events if event.get("event") == "matrix_run_disconnect_complete"
    ]
    if len(complete_events) != 1:
        errors.append(f"expected one completed-disconnect event, found {len(complete_events)}")
    host_disconnects = {
        str(entry.get("node")): entry
        for entry in run_result.get("host_disconnects", [])
        if isinstance(entry, dict)
    }
    peripheral_disconnects = run_result.get("peripheral_disconnects", {})
    if not isinstance(peripheral_disconnects, dict):
        peripheral_disconnects = {}
    for node in node_names:
        host = host_disconnects.get(node, {})
        peripheral = peripheral_disconnects.get(node, {})
        if (
            host.get("completed") is not True
            or host.get("disconnect_called") is not True
            or host.get("is_connected") is not False
        ):
            errors.append(f"Node {node} host disconnect was not confirmed")
        if (
            peripheral.get("required") is not True
            or peripheral.get("observed") is not True
            or peripheral.get("completed") is not True
        ):
            errors.append(f"Node {node} firmware disconnect event was not confirmed")
        disconnected = [
            event
            for event in control_events
            if event.get("event") == "peripheral_disconnected_event"
            and event.get("node") == node
        ]
        if len(disconnected) != 1:
            errors.append(
                f"Node {node} expected one recorded firmware disconnect event, found {len(disconnected)}"
            )
    if run_result.get("disconnect_cleanup_errors"):
        errors.append(f"disconnect cleanup errors: {run_result['disconnect_cleanup_errors']}")
    if complete_events and complete_events[0].get("errors"):
        errors.append(f"disconnect completion reports errors: {complete_events[0]['errors']}")
    return not errors, errors


def _audit_run(
    root: Path,
    run_index: int,
    condition: str,
    *,
    expected_source_commit: str,
    expected_plan_sha256: str = PRECHECK_PLAN_SHA256,
) -> JSON:
    run_dir = root / f"run-{run_index:02d}-{condition}"
    run_config = _read_json(run_dir / "run_config.json")
    run_result = _read_json(run_dir / "run_result.json")
    expected_nodes = active_nodes_for_condition(condition)
    errors: list[str] = []

    if run_config.get("schema") != "kineimu.m1.ble-link-count-precheck-run/2.0":
        errors.append("run config has the wrong precheck schema")
    if run_config.get("experiment_profile") != "link_count_precheck":
        errors.append("run config has the wrong experiment profile")
    if run_result.get("schema") != "kineimu.m1.ble-link-count-precheck-run-result/2.0":
        errors.append("run result has the wrong precheck schema")
    if run_config.get("predeclared_plan_sha256", "").upper() != expected_plan_sha256:
        errors.append("run config plan SHA-256 differs from the locked precheck plan")
    if expected_plan_sha256 in {
        PRECHECK_PLAN_V4_SHA256,
        PRECHECK_PLAN_V5_SHA256,
        PRECHECK_PLAN_V6_SHA256,
    }:
        if run_config.get("require_pristine_start") is not True:
            errors.append("cold-start run did not enable the pre-notify pristine-start gate")
    if expected_plan_sha256 in {PRECHECK_PLAN_V5_SHA256, PRECHECK_PLAN_V6_SHA256}:
        errors.extend(audit_connect_timeout_config(run_config, expected_plan_sha256))
    if run_config.get("condition") != condition:
        errors.append("run config condition differs from the locked schedule")
    if run_config.get("request_mode") != "OFF":
        errors.append("run config did not keep the peripheral request mode OFF")
    if run_config.get("connection_order") != list(expected_nodes):
        errors.append("run config connection order differs from the locked condition")
    if run_config.get("nodes") != sorted(expected_nodes):
        errors.append("run config active node set differs from the locked condition")
    if run_config.get("capture_seconds") != PRECHECK_CAPTURE_SECONDS:
        errors.append("run config capture duration differs from 15.0 seconds")
    change_policy = run_config.get("change_policy", {})
    if (
        change_policy.get("connection_parameter_request") is not False
        or change_policy.get("tx_queue_capacity_change") is not False
        or change_policy.get("host_disk_write_decoupling") is not False
        or change_policy.get("completion_driven_tx") is not True
    ):
        errors.append("run config change policy does not match the locked single-factor profile")
    serial_map = run_config.get("cdc_usb_serials", {})
    for node in expected_nodes:
        expected_serial = matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[NodeId[node]]
        if serial_map.get(node) != expected_serial:
            errors.append(f"Node {node} CDC capture was not resolved by its locked USB serial")

    control_events, events_by_node = _read_run_events(run_dir, expected_nodes)
    if expected_plan_sha256 in {PRECHECK_PLAN_V4_SHA256, PRECHECK_PLAN_V5_SHA256}:
        errors.extend(audit_pre_notify_status_gates(control_events, expected_nodes))
    active_link_state = audit_active_link_state(condition, control_events)
    observed_order = tuple(active_link_state.get("observed_connection_order", []))
    errors.extend(active_link_state.get("errors", []))
    if len(observed_order) != len(expected_nodes):
        errors.append(
            f"expected {len(expected_nodes)} firmware connection events, found {len(observed_order)}"
        )

    timing = audit_run_timing_events(
        control_events,
        events_by_node,
        active_nodes=list(expected_nodes),
        settle_seconds=PRECHECK_SETTLE_SECONDS,
        capture_seconds=PRECHECK_CAPTURE_SECONDS,
        connect_gatt_timeout_seconds=(
            precheck_connect_timeout_seconds(
                "v6"
                if expected_plan_sha256 == PRECHECK_PLAN_V6_SHA256
                else "v5"
                if expected_plan_sha256 == PRECHECK_PLAN_V5_SHA256
                else "v4"
            )
            if expected_plan_sha256
            in {PRECHECK_PLAN_V4_SHA256, PRECHECK_PLAN_V5_SHA256, PRECHECK_PLAN_V6_SHA256}
            else PRECHECK_CONNECT_TIMEOUT_SECONDS
        ),
        require_full_callback_span=False,
    )
    if timing.get("valid") is not True:
        errors.extend(f"capture/setup timing audit: {error}" for error in timing.get("errors", []))

    overlap_ns = active_link_state.get("concurrent_capture_overlap_ns")

    node_rows: JSON = {}
    for node in expected_nodes:
        node_dir = run_dir
        raw_dir = node_dir / "raw"
        raw_path = raw_dir / f"node-{node.lower()}.kimu"
        sidecar_path = raw_dir / f"node-{node.lower()}.events.ndjson"
        cdc_path = node_dir / f"node-{node.lower()}.cdc.bin"
        for path, label in (
            (raw_path, "KIMU raw stream"),
            (sidecar_path, "event sidecar"),
            (cdc_path, "raw CDC segment"),
        ):
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"Node {node} {label} is missing or empty")
        if not raw_path.is_file() or not sidecar_path.is_file() or not cdc_path.is_file():
            continue
        raw = decode_raw_capture(raw_path, node)
        capture_events = events_by_node[node]
        quality = capture_quality(capture_events, raw)
        acquisition_start = audit_fresh_acquisition_start(
            capture_events,
            control_events,
            node,
        )
        if not acquisition_start.get("valid"):
            errors.extend(
                f"Node {node} acquisition freshness: {error}"
                for error in acquisition_start.get("errors", [])
            )
        if expected_plan_sha256 in {PRECHECK_PLAN_V4_SHA256, PRECHECK_PLAN_V5_SHA256}:
            excluded = run_config.get("forbidden_boot_ids_by_node", {}).get(node, [])
            if acquisition_start.get("boot_id") in excluded:
                errors.append(
                    f"Node {node} boot ID was in the predeclared forbidden boot-ID set"
                )
            gate_statuses = [
                event.get("status")
                for event in control_events
                if event.get("event") == "pre_notify_status_gate"
                and event.get("node") == node
            ]
            if len(gate_statuses) == 1:
                gate_status = gate_statuses[0]
                if not isinstance(gate_status, dict) or gate_status.get("boot_id") != (
                    acquisition_start.get("boot_id")
                ):
                    errors.append(
                        f"Node {node} gate status does not match the audited pre-notify status"
                    )
        invalid_sidecar_lines = count_invalid_event_lines(sidecar_path)
        if invalid_sidecar_lines:
            errors.append(f"Node {node} sidecar has {invalid_sidecar_lines} invalid lines")
        if quality.get("event_crc_false") != 0 or raw.get("crc_errors") != 0:
            errors.append(f"Node {node} has CRC errors")
        if quality.get("event_decode_failures") != 0 or raw.get("decode_errors") != 0:
            errors.append(f"Node {node} has decode errors")
        if raw.get("framing_errors") != 0:
            errors.append(f"Node {node} has framing errors")
        errors.extend(
            sample_sequence_gap_errors(
                raw,
                expected_plan_sha256=expected_plan_sha256,
                node=node,
            )
        )
        if raw.get("wrong_node_packets") != 0:
            errors.append(f"Node {node} raw packets contain a node-ID mismatch")
        if raw.get("valid_packets") != quality.get("notify_events"):
            errors.append(
                f"Node {node} valid KIMU packets do not match notify events "
                f"({raw.get('valid_packets')} vs {quality.get('notify_events')})"
            )

        identity = timing.get("nodes", {}).get(node, {}).get("identity_config_read", {})
        if identity.get("hardware_device_id") != PRECHECK_HARDWARE_DEVICE_IDS[NodeId[node]]:
            errors.append(f"Node {node} BLE identity read has a mismatched hardware ID")
        if identity.get("node_id") != int(NodeId[node]):
            errors.append(f"Node {node} BLE identity read has a mismatched node ID")
        if identity.get("firmware_git_commit") != expected_source_commit:
            errors.append(f"Node {node} BLE identity read has a mismatched firmware commit")
        mtu_observation = timing.get("nodes", {}).get(node, {}).get("mtu")
        mtu_event = (
            mtu_observation.get("capture_event")
            if isinstance(mtu_observation, dict)
            else None
        )
        mtu = mtu_event if isinstance(mtu_event, dict) else {}
        if mtu.get("mtu") != PRECHECK_MTU or mtu.get("accepted") is not True:
            errors.append(f"Node {node} BLE connection did not prove MTU 127")

        cdc = parse_cdc(cdc_path, node)
        request_logs = cdc.get("parameter_request_logs", [])
        off_records = [
            record
            for record in request_logs
            if record.get("fields", {}).get("mode") == "OFF"
            and record.get("fields", {}).get("call") == "0"
            and record.get("fields", {}).get("api_rc") == "NA"
        ]
        if len(off_records) != 1:
            errors.append(
                f"Node {node} expected exactly one OFF/no-local-request log, found {len(off_records)}"
            )

        tx = diagnostic_summary(cdc, PRECHECK_CAPTURE_SECONDS)
        tx_segments = tx.get("segments", [])
        active_tx_segments = [
            segment
            for segment in tx_segments
            if any(
                isinstance(segment.get("counter_deltas", {}).get(name), int)
                and segment["counter_deltas"][name] > 0
                for name in ("calls", "accepted", "completed", "retries", "enomem", "eagain")
            )
        ]
        required_tx_fields = {
            "calls",
            "accepted",
            "final_fail",
            "packet_drops",
            "enomem",
            "eagain",
            "retries",
            "window_full",
            "wait_us",
            "completed",
            "cancelled",
            "callbacks_stale",
            "callbacks_cancelled",
            "callbacks_unexpected",
            "age_count",
            "schedule_fail_initial",
            "schedule_fail_retry",
        }
        physical_tx: JSON | None = None
        if expected_plan_sha256 == PRECHECK_PLAN_V6_SHA256:
            physical_tx = summarize_physical_connection_tx(
                tx,
                cdc.get("tx_snapshots", []),
                expected_boot_id=acquisition_start.get("boot_id"),
            )
            errors.extend(
                f"Node {node} physical-connection TX diagnostics: {error}"
                for error in physical_tx.get("errors", [])
            )
            if not physical_tx.get("active_queue_generations"):
                errors.append(f"Node {node} has no active TX queue epoch")
        else:
            if tx.get("delta_quality") != "exact":
                errors.append(f"Node {node} connection-generation TX deltas are not exact")
            if len(active_tx_segments) != 1:
                errors.append(
                    f"Node {node} expected one active TX connection generation, found {len(active_tx_segments)}"
                )
            if tx.get("snapshot_count", 0) < 2 or any(
                segment.get("delta_quality") != "exact" for segment in tx_segments
            ):
                errors.append(f"Node {node} TX diagnostic snapshots are incomplete or saturated")
            if active_tx_segments:
                deltas = active_tx_segments[0].get("counter_deltas", {})
                if required_tx_fields - set(deltas):
                    errors.append(
                        f"Node {node} TX diagnostics omit fields: {sorted(required_tx_fields - set(deltas))}"
                    )
                if any(not isinstance(deltas.get(field), int) for field in required_tx_fields):
                    errors.append(f"Node {node} TX diagnostic generation has unavailable metrics")

        recorder_result = run_result.get("recorder_result")
        recorder_nodes = (
            recorder_result.get("nodes", {})
            if isinstance(recorder_result, dict)
            else {}
        )
        recorder_node = recorder_nodes.get(node, {}) if isinstance(recorder_nodes, dict) else {}
        if recorder_node.get("packets") != raw.get("valid_packets"):
            errors.append(f"Node {node} recorder packet count differs from raw decode")
        node_rows[node] = {
            "hardware_device_id": identity.get("hardware_device_id"),
            "node_id": identity.get("node_id"),
            "firmware_git_commit": identity.get("firmware_git_commit"),
            "mtu": mtu.get("mtu"),
            "capture_boundary_valid": timing.get("nodes", {}).get(node, {}).get("capture_boundary_valid"),
            "parameter_window": timing.get("nodes", {}).get(node, {}).get("parameter_window"),
            "raw_capture": raw,
            "capture_quality": quality,
            "acquisition_start": acquisition_start,
            "event_sidecar_sha256": sha256(sidecar_path),
            "cdc_segment_sha256": sha256(cdc_path),
            "tx_diagnostics": tx,
            "physical_connection_tx": physical_tx,
            "packet_sequence_gaps": raw.get("packet_sequence_gaps"),
            "sample_sequence_gaps": raw.get("sample_sequence_gaps"),
            "packet_duplicates": raw.get("packet_duplicates"),
            "sample_duplicates": raw.get("sample_duplicates"),
            "off_no_local_request_records": len(off_records),
        }

    cleanup_valid, cleanup_errors = _audit_cleanup(run_result, control_events, expected_nodes)
    if not cleanup_valid:
        errors.extend(cleanup_errors)
    return {
        "run_index": run_index,
        "condition": condition,
        "expected_active_links": len(expected_nodes),
        "observed_connection_order": list(observed_order),
        "link_state_realized": active_link_state.get("realized"),
        "concurrent_capture_overlap_ns": overlap_ns,
        "timing_audit": timing,
        "cleanup_valid": cleanup_valid,
        "run_error": run_result.get("error"),
        "nodes": node_rows,
        "errors": errors,
        "valid": not errors and run_result.get("error") is None,
    }


def _cold_start_plan_inputs(
    plan_version: str,
) -> tuple[Path, str, dict[str, Path]]:
    if plan_version == "v4":
        return PRECHECK_PLAN_V4_PATH, PRECHECK_PLAN_V4_SHA256, PRECHECK_V4_OUTPUT_ROOTS
    if plan_version == "v5":
        return PRECHECK_PLAN_V5_PATH, PRECHECK_PLAN_V5_SHA256, PRECHECK_V5_OUTPUT_ROOTS
    if plan_version == "v6":
        return PRECHECK_PLAN_V6_PATH, PRECHECK_PLAN_V6_SHA256, PRECHECK_V6_OUTPUT_ROOTS
    raise ValueError(f"unsupported cold-start precheck plan version: {plan_version}")


def _audit_cold_start_single(root_dir: Path, plan_version: str) -> JSON:
    """Independently audit one cold-start root from raw evidence and sidecars."""

    plan_path, plan_sha256, output_roots = _cold_start_plan_inputs(plan_version)
    root = root_dir.resolve()
    condition = next(
        (
            name
            for name, expected_root in output_roots.items()
            if expected_root.resolve() == root
        ),
        None,
    )
    version_label = plan_version.upper()
    errors: list[str] = []
    if condition is None:
        errors.append(f"{version_label} root is not one of the locked condition roots: {root}")
        expected_order: tuple[str, ...] = ()
    else:
        expected_order = (condition,)
    manifest = verify_manifest(root)
    raw_before = raw_input_hashes(root)
    if manifest.get("valid") is not True:
        errors.append("SHA256SUMS.txt is missing, mismatched, or has unlisted files")
    config = _read_json(root / "matrix_config.json")
    result = _read_json(root / "matrix_result.json")
    if config.get("schema") != "kineimu.m1.ble-link-count-precheck/2.0":
        errors.append("matrix config has the wrong precheck schema")
    if config.get("precheck_plan_version") != plan_version:
        errors.append(f"matrix config does not identify the {version_label} cold-start plan")
    if config.get("predeclared_plan_sha256", "").upper() != plan_sha256:
        errors.append(f"matrix config plan hash differs from the locked {version_label} plan")
    if config.get("run_order") != list(expected_order):
        errors.append("matrix config condition differs from its locked output root")
    if config.get("runtime_cdc_interface_expected") != {
        "vid": PRECHECK_RUNTIME_CDC_VID,
        "pid": PRECHECK_RUNTIME_CDC_PID,
        "usage": "application CDC; UF2 bootloader interface is forbidden",
    }:
        errors.append(f"matrix config runtime CDC interface expectation differs from {version_label}")
    if sha256(root / "PREDECLARED_PRECHECK_PLAN.md").upper() != plan_sha256:
        errors.append(f"copied {version_label} precheck plan hash differs from its locked SHA-256")
    if config.get("firmware_source_commit") != PRECHECK_FIRMWARE_SOURCE_COMMIT:
        errors.append(f"matrix config firmware source differs from the locked {version_label} plan")
    if config.get("require_pristine_start") is not True:
        errors.append("matrix config did not require the pre-notify freshness gate")
    if plan_version in {"v5", "v6"}:
        errors.extend(audit_connect_timeout_config(config, plan_sha256))

    port_records = config.get("cdc_ports_resolved_by_usb_serial", {})
    for node in (NodeId.A, NodeId.B):
        port_record = port_records.get(node.name, {}) if isinstance(port_records, dict) else {}
        if not isinstance(port_record, dict):
            errors.append(f"matrix config Node {node.name} CDC interface record is malformed")
            continue
        try:
            validate_runtime_cdc_port(node, cast(dict[str, object], port_record))
        except RuntimeError as error:
            errors.append(str(error))
        image = config.get("firmware_images", {}).get(node.name, {})
        if image.get("sha256", "").upper() != PRECHECK_IMAGE_SHA256[node]:
            errors.append(f"matrix config Node {node.name} firmware image hash differs")
        build = config.get("build_configs", {}).get(node.name, {})
        if build.get("sha256", "").upper() != PRECHECK_CONFIG_SHA256:
            errors.append(f"matrix config Node {node.name} build config hash differs")

    if result.get("schema") != "kineimu.m1.ble-link-count-precheck-result/1.0":
        errors.append("matrix result has the wrong cold-start precheck schema")
    if tuple(result.get("run_order", [])) != expected_order:
        errors.append("matrix result order differs from its locked single-condition schedule")
    if result.get("schedule_attempted_count") != 1:
        errors.append(f"{version_label} root does not contain exactly one attempted condition")
    if result.get("scheduled_count") != 1 or result.get("all_scheduled_runs_attempted") is not True:
        errors.append(f"{version_label} single-condition acquisition is incomplete")
    if result.get("stop_reason") is not None:
        errors.append(f"{version_label} acquisition stopped: {result.get('stop_reason')}")
    for node in (NodeId.A, NodeId.B):
        for label, records in (
            ("initial", result.get("initial_off_control", {})),
            ("final", result.get("final_control_cleanup", {})),
        ):
            record = records.get(node.name, {}) if isinstance(records, dict) else {}
            if (
                record.get("requested") != "OFF"
                or record.get("applied") is not True
                or record.get("rc") != 0
            ):
                errors.append(f"Node {node.name} {label} OFF control/cleanup ACK failed")

    run_audit: JSON | None = None
    if condition is not None:
        try:
            run_audit = _audit_run(
                root,
                1,
                condition,
                expected_source_commit=PRECHECK_FIRMWARE_SOURCE_COMMIT,
                expected_plan_sha256=plan_sha256,
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            run_audit = {
                "condition": condition,
                "valid": False,
                "errors": [
                    "independent raw audit could not complete: "
                    f"{type(error).__name__}: {error}"
                ],
            }
        if run_audit.get("valid") is not True:
            errors.append(f"{version_label} independent run audit did not mark the condition valid")
        errors.extend(
            f"run {condition}: {error}" for error in run_audit.get("errors", [])
        )
        required_boots = config.get("forbidden_boot_ids_by_node", {})
        for node_name, rows in run_audit.get("nodes", {}).items():
            acquisition = rows.get("acquisition_start", {})
            boot_id = acquisition.get("boot_id")
            forbidden = required_boots.get(node_name, []) if isinstance(required_boots, dict) else []
            if boot_id in forbidden:
                errors.append(f"Node {node_name} started with a predeclared forbidden boot ID")
            if boot_id == PRECHECK_V3_BOOT_IDS.get(node_name):
                errors.append(f"Node {node_name} reused the V3 firmware boot ID")

    raw_after = raw_input_hashes(root)
    if raw_before != raw_after:
        errors.append("raw CDC/KIMU/event inputs changed during the independent analysis")
    return {
        "schema": f"kineimu.m1.ble-link-count-cold-start-precheck-audit/{plan_version[1:]}.0",
        "root_dir": str(root),
        "condition": condition,
        "analysis_source": (
            "matrix config/result + raw per-run CDC segments + raw KIMU + event sidecars; "
            "prior audit reports were not read"
        ),
        "analysis_script_sha256": sha256(Path(__file__).resolve()).upper(),
        "plan_sha256": plan_sha256,
        "manifest_verification": manifest,
        "raw_input_hashes_before": raw_before,
        "raw_input_hashes_after": raw_after,
        "raw_inputs_unchanged": raw_before == raw_after,
        "matrix_config_sha256": sha256(root / "matrix_config.json"),
        "matrix_result_sha256": sha256(root / "matrix_result.json"),
        "matrix_config": config,
        "run": run_audit,
        "errors": errors,
        "precheck_passed": not errors and run_audit is not None,
        "disposition": "PASS_FOR_PAIR_AUDIT" if not errors else "BLOCKED",
    }


def audit_precheck_v4_single(root_dir: Path) -> JSON:
    """Independently audit one V4 cold-start root from its raw evidence."""

    return _audit_cold_start_single(root_dir, "v4")


def audit_precheck_v5_single(root_dir: Path) -> JSON:
    """Independently audit one V5 cold-start root from its raw evidence."""

    return _audit_cold_start_single(root_dir, "v5")


def audit_precheck_v6_single(root_dir: Path) -> JSON:
    """Independently audit one V6 cold-start root from its raw evidence."""

    return _audit_cold_start_single(root_dir, "v6")


def _audit_cold_start_pair(plan_version: str, single_audit: Any) -> JSON:
    """Recompute both locked roots and check their cold-start pair gate."""

    _plan_path, plan_sha256, _roots = _cold_start_plan_inputs(plan_version)
    output_roots = _cold_start_roots_for_version(plan_version)
    version_label = plan_version.upper()
    a_root = output_roots["a_only"].resolve()
    dual_root = output_roots["dual_a_to_b"].resolve()
    a_only = single_audit(a_root)
    dual = single_audit(dual_root)
    errors: list[str] = []
    if a_only.get("precheck_passed") is not True:
        errors.append("a_only independent raw audit did not pass")
    if dual.get("precheck_passed") is not True:
        errors.append("dual_a_to_b independent raw audit did not pass")
    if a_only.get("run", {}).get("valid") is not True:
        errors.append("a_only run audit did not mark the condition valid")
    if dual.get("run", {}).get("valid") is not True:
        errors.append("dual_a_to_b run audit did not mark the condition valid")
    if a_only.get("condition") != "a_only":
        errors.append("a_only root condition label does not match the locked condition")
    if dual.get("condition") != "dual_a_to_b":
        errors.append("dual root condition label does not match the locked condition")

    config_a = a_only.get("matrix_config", {})
    config_dual = dual.get("matrix_config", {})
    shared_config_fields = (
        "git_head",
        "firmware_source_commit",
        "firmware_images",
        "build_configs",
        "build_configurations_identical",
        "host",
        "windows_connect_gatt_setup_timeout_seconds",
        "ble_addresses",
        "expected_hardware_device_ids",
        "usb_serials",
    )
    for field in shared_config_fields:
        if config_a.get(field) != config_dual.get(field):
            errors.append(f"paired roots differ in locked source/hardware field {field}")

    run_a = a_only.get("run", {})
    run_dual = dual.get("run", {})
    nodes_a = run_a.get("nodes", {}) if isinstance(run_a, dict) else {}
    nodes_dual = run_dual.get("nodes", {}) if isinstance(run_dual, dict) else {}
    a_identity = nodes_a.get("A", {})
    dual_a_identity = nodes_dual.get("A", {})
    for field in ("hardware_device_id", "node_id", "firmware_git_commit", "mtu"):
        if a_identity.get(field) != dual_a_identity.get(field):
            errors.append(f"Node A identity differs between paired roots at {field}")
    a_start = a_identity.get("acquisition_start", {})
    dual_a_start = dual_a_identity.get("acquisition_start", {})
    a_boot_id = a_start.get("boot_id")
    dual_a_boot_id = dual_a_start.get("boot_id")
    if not isinstance(a_boot_id, int) or not isinstance(dual_a_boot_id, int):
        errors.append("paired Node A pre-notify boot IDs are unavailable")
    elif a_boot_id == dual_a_boot_id:
        errors.append(
            f"Node A boot ID was reused between the two {version_label} condition roots"
        )
    if a_boot_id == PRECHECK_V3_BOOT_IDS["A"] or dual_a_boot_id == PRECHECK_V3_BOOT_IDS["A"]:
        errors.append("a paired Node A boot ID matches the V3 consumed boot")
    dual_b = nodes_dual.get("B", {})
    dual_b_boot_id = dual_b.get("acquisition_start", {}).get("boot_id")
    if dual_b_boot_id == PRECHECK_V3_BOOT_IDS["B"]:
        errors.append("dual-run Node B boot ID matches the V3 consumed boot")
    if run_a.get("expected_active_links") != 1:
        errors.append("a_only root did not realize exactly one active link")
    if run_dual.get("expected_active_links") != 2:
        errors.append("dual_a_to_b root did not realize exactly two active links")

    return {
        "schema": (
            "kineimu.m1.ble-link-count-cold-start-precheck-pair-audit/"
            f"{plan_version[1:]}.0"
        ),
        "plan_sha256": plan_sha256,
        "analysis_source": "fresh independent analyses of both immutable raw roots",
        "conditions": {"a_only": a_only, "dual_a_to_b": dual},
        "node_a_boot_ids": {"a_only": a_boot_id, "dual_a_to_b": dual_a_boot_id},
        "errors": errors,
        "precheck_passed": not errors,
        "disposition": "PASS_FOR_FORMAL_PLAN_DRAFTING" if not errors else "BLOCKED",
    }


def audit_precheck_v4_pair() -> JSON:
    """Recompute both locked V4 roots and check the cold-start pair gate."""

    return _audit_cold_start_pair("v4", audit_precheck_v4_single)


def audit_precheck_v5_pair() -> JSON:
    """Recompute both locked V5 roots and check the cold-start pair gate."""

    return _audit_cold_start_pair("v5", audit_precheck_v5_single)


def audit_precheck_v6_pair() -> JSON:
    """Recompute both locked V6 roots and check the cold-start pair gate."""

    return _audit_cold_start_pair("v6", audit_precheck_v6_single)


def audit_precheck(root_dir: Path) -> JSON:
    """Recompute precheck completeness from immutable raw streams and sidecars."""

    root = root_dir.resolve()
    config_path = root / "matrix_config.json"
    if config_path.is_file():
        config_probe = _read_json(config_path)
        plan_sha = config_probe.get("predeclared_plan_sha256", "").upper()
        if plan_sha == PRECHECK_PLAN_V4_SHA256:
            return audit_precheck_v4_single(root)
        if plan_sha == PRECHECK_PLAN_V5_SHA256:
            return audit_precheck_v5_single(root)
        if plan_sha == PRECHECK_PLAN_V6_SHA256:
            return audit_precheck_v6_single(root)
    errors: list[str] = []
    manifest = verify_manifest(root)
    raw_before = raw_input_hashes(root)
    if manifest.get("valid") is not True:
        errors.append("SHA256SUMS.txt is missing, mismatched, or has unlisted files")
    config = _read_json(root / "matrix_config.json")
    result = _read_json(root / "matrix_result.json")
    if config.get("schema") != "kineimu.m1.ble-link-count-precheck/2.0":
        errors.append("matrix config has the wrong precheck schema")
    if result.get("schema") != "kineimu.m1.ble-link-count-precheck-result/1.0":
        errors.append("matrix result has the wrong precheck schema")
    if config.get("predeclared_plan_sha256", "").upper() != PRECHECK_PLAN_SHA256:
        errors.append("matrix config plan hash differs from the committed precheck plan")
    if config.get("runtime_cdc_interface_expected") != {
        "vid": PRECHECK_RUNTIME_CDC_VID,
        "pid": PRECHECK_RUNTIME_CDC_PID,
        "usage": "application CDC; UF2 bootloader interface is forbidden",
    }:
        errors.append("matrix config runtime CDC interface expectation differs from the plan")
    if sha256(root / "PREDECLARED_PRECHECK_PLAN.md").upper() != PRECHECK_PLAN_SHA256:
        errors.append("copied precheck plan hash differs from the locked plan")
    if config.get("firmware_source_commit") != PRECHECK_FIRMWARE_SOURCE_COMMIT:
        errors.append("matrix config firmware source differs from the locked plan")
    port_records = config.get("cdc_ports_resolved_by_usb_serial", {})
    for node in (NodeId.A, NodeId.B):
        port_record = port_records.get(node.name, {}) if isinstance(port_records, dict) else {}
        if not isinstance(port_record, dict):
            errors.append(f"matrix config Node {node.name} CDC interface record is malformed")
            continue
        try:
            validate_runtime_cdc_port(node, cast(dict[str, object], port_record))
        except RuntimeError as error:
            errors.append(str(error))
    for node in (NodeId.A, NodeId.B):
        image = config.get("firmware_images", {}).get(node.name, {})
        if image.get("sha256", "").upper() != PRECHECK_IMAGE_SHA256[node]:
            errors.append(f"matrix config Node {node.name} firmware image hash differs")
        build = config.get("build_configs", {}).get(node.name, {})
        if build.get("sha256", "").upper() != PRECHECK_CONFIG_SHA256:
            errors.append(f"matrix config Node {node.name} build config hash differs")

    expected_order = precheck_order()
    observed_order = tuple(result.get("run_order", []))
    if observed_order != expected_order:
        errors.append(f"observed schedule {observed_order} differs from {expected_order}")
    if result.get("schedule_attempted_count") != len(expected_order):
        errors.append("the precheck did not attempt all four planned conditions")
    if result.get("all_scheduled_runs_attempted") is not True:
        errors.append("the locked four-condition precheck schedule is incomplete")

    initial_off = result.get("initial_off_control", {})
    final_off = result.get("final_control_cleanup", {})
    for node in (NodeId.A, NodeId.B):
        for label, records in (("initial", initial_off), ("final", final_off)):
            record = records.get(node.name, {}) if isinstance(records, dict) else {}
            if record.get("requested") != "OFF" or record.get("applied") is not True:
                errors.append(f"Node {node.name} {label} OFF cleanup/control ACK failed")
            if record.get("rc") != 0:
                errors.append(f"Node {node.name} {label} OFF control return code is not zero")

    run_audits: list[JSON] = []
    for run_index, condition in enumerate(expected_order, start=1):
        try:
            run_audit = _audit_run(
                root,
                run_index,
                condition,
                expected_source_commit=PRECHECK_FIRMWARE_SOURCE_COMMIT,
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            run_audit = {
                "run_index": run_index,
                "condition": condition,
                "valid": False,
                "errors": [f"independent raw audit could not complete: {type(error).__name__}: {error}"],
            }
        run_audits.append(run_audit)
        errors.extend(
            f"run {run_index} {condition}: {error}"
            for error in run_audit.get("errors", [])
        )

    raw_after = raw_input_hashes(root)
    if raw_before != raw_after:
        errors.append("raw CDC/KIMU/event inputs changed during the independent analysis")
    return {
        "schema": "kineimu.m1.ble-link-count-precheck-audit/2.0",
        "root_dir": str(root),
        "analysis_source": (
            "matrix config/result + raw per-run CDC segments + raw KIMU + per-run event sidecars; "
            "matrix_audit.json was not read"
        ),
        "analysis_script_path": str(Path(__file__).resolve()),
        "analysis_script_sha256": sha256(Path(__file__).resolve()),
        "plan_sha256": PRECHECK_PLAN_SHA256,
        "runner_sha256": config.get("runner_sha256"),
        "matrix_config_sha256": sha256(root / "matrix_config.json"),
        "matrix_result_sha256": sha256(root / "matrix_result.json"),
        "manifest_verification": manifest,
        "raw_input_hashes_before": raw_before,
        "raw_input_hashes_after": raw_after,
        "raw_inputs_unchanged": raw_before == raw_after,
        "manipulation": {
            "single_factor": "active BLE link count: one versus two",
            "peripheral_parameter_request_mode": "OFF for all conditions",
            "expected_schedule": list(expected_order),
            "observed_active_links_per_run": [
                audit.get("expected_active_links") for audit in run_audits
            ],
            "two_connection_orders_observed": all(
                audit.get("observed_connection_order") == list(
                    active_nodes_for_condition(str(audit.get("condition")))
                )
                for audit in run_audits
            ),
            "factor_realized_in_all_windows": all(
                audit.get("valid") is True for audit in run_audits
            ),
        },
        "runs": run_audits,
        "errors": errors,
        "precheck_passed": not errors and len(run_audits) == len(expected_order),
        "disposition": "PASS_FOR_FORMAL_PLAN_DRAFTING" if not errors else "BLOCKED",
    }


def _live_input_config(
    root_dir: Path,
    *,
    plan_path: Path,
    plan_sha256: str,
    preflash: JSON,
    images: dict[NodeId, Path],
    configurations: dict[NodeId, Path],
    port_info: dict[NodeId, dict[str, object]],
    adapter_identity: JSON,
    plan_version: str = "v3",
    schedule: tuple[tuple[str, tuple[str, ...]], ...] = PRECHECK_SCHEDULE,
    run_order: tuple[str, ...] | None = None,
    require_pristine_start: bool = False,
    forbidden_boot_ids: dict[NodeId, frozenset[int]] | None = None,
    prerequisite_root: Path | None = None,
) -> JSON:
    repo_root = Path(__file__).resolve().parents[1]
    head = matrix_runner._git_head(repo_root)
    if head is None:
        raise RuntimeError("could not resolve the acquisition code HEAD")
    validate_committed_precheck_inputs(
        repo_root,
        (plan_path, Path(__file__), Path(matrix_runner.__file__)),
    )
    ports: JSON = {
        node.name: port_info[node] for node in (NodeId.A, NodeId.B)
    }
    image_records = {
        node.name: {
            "source_path": str(images[node].resolve()),
            "sha256": sha256(images[node]).upper(),
            "size_bytes": images[node].stat().st_size,
            "node_id": int(node),
        }
        for node in (NodeId.A, NodeId.B)
    }
    config_records = {
        node.name: {
            "source_path": str(configurations[node].resolve()),
            "sha256": sha256(configurations[node]).upper(),
            "size_bytes": configurations[node].stat().st_size,
        }
        for node in (NodeId.A, NodeId.B)
    }
    planned_order = run_order if run_order is not None else precheck_order()
    return {
        "schema": "kineimu.m1.ble-link-count-precheck/2.0",
        "precheck_plan_version": plan_version,
        "created_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "project": "KineIMU Shoulder",
        "objective": "verify link-count manipulation and complete capture evidence only",
        "output_root": str(root_dir.resolve()),
        "predeclared_plan_path": str(plan_path.resolve()),
        "predeclared_plan_sha256": plan_sha256.upper(),
        "predeclared_plan_copy": "PREDECLARED_PRECHECK_PLAN.md",
        "schedule": [
            {"block": block_index, "request_mode": mode, "conditions": list(conditions)}
            for block_index, (mode, conditions) in enumerate(schedule, start=1)
        ],
        "run_order": list(planned_order),
        "single_factor": "active_ble_link_count",
        "local_connection_parameter_request": False,
        "seconds_per_capture": PRECHECK_CAPTURE_SECONDS,
        "connection_settle_seconds": PRECHECK_SETTLE_SECONDS,
        "windows_connect_gatt_setup_timeout_seconds": precheck_connect_timeout_seconds(
            plan_version
        ),
        "inter_run_rest_seconds": PRECHECK_REST_SECONDS,
        "ble_mtu_required": PRECHECK_MTU,
        "runtime_cdc_interface_expected": {
            "vid": PRECHECK_RUNTIME_CDC_VID,
            "pid": PRECHECK_RUNTIME_CDC_PID,
            "usage": "application CDC; UF2 bootloader interface is forbidden",
        },
        "ble_addresses": {
            node.name: PRECHECK_BLE_ADDRESSES[node] for node in (NodeId.A, NodeId.B)
        },
        "expected_hardware_device_ids": {
            node.name: PRECHECK_HARDWARE_DEVICE_IDS[node] for node in (NodeId.A, NodeId.B)
        },
        "usb_serials": {
            node.name: matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node]
            for node in (NodeId.A, NodeId.B)
        },
        "cdc_ports_resolved_by_usb_serial": ports,
        "firmware_source_commit": PRECHECK_FIRMWARE_SOURCE_COMMIT,
        "firmware_images": image_records,
        "build_configs": config_records,
        "build_configurations_identical": configurations[NodeId.A].read_bytes()
        == configurations[NodeId.B].read_bytes(),
        "source_preflash_record_path": str(PRECHECK_SOURCE_PREFLASH.resolve()),
        "source_preflash_record_sha256": sha256(PRECHECK_SOURCE_PREFLASH).upper(),
        "source_preflash_plan_sha256": preflash.get("plan_sha256"),
        "boards": {
            node.name: {
                "board_id": PRECHECK_BOARD_ID,
                "node_id": int(node),
                "expected_hardware_device_id": PRECHECK_HARDWARE_DEVICE_IDS[node],
                "bootloader_usb_serial": matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node],
            }
            for node in (NodeId.A, NodeId.B)
        },
        "firmware_build": {
            "board": "xiao_ble/nrf52840/sense",
            "zephyr_version": "v4.4.0",
            "zephyr_sdk": "1.0.1",
            "queue_slots": 4,
            "att_tx_contexts": 8,
            "connection_parameter_mode": "OFF during every capture",
        },
        "host": {
            "python": sys.version,
            "platform": platform.platform(),
            "platform_version": platform.version(),
            "platform_release": platform.release(),
            "machine": platform.machine(),
            "ble_controller_live_inventory": adapter_identity,
            "ble_controller_expected": {
                "instance_id_prefix": PRECHECK_ADAPTER_INSTANCE_PREFIX,
                "driver_inf": PRECHECK_ADAPTER_DRIVER_INF,
                "driver_version": PRECHECK_ADAPTER_DRIVER_VERSION,
            },
        },
        "git_head": head,
        "runner_path": str(Path(__file__).resolve()),
        "runner_sha256": sha256(Path(__file__).resolve()).upper(),
        "matrix_runner_path": str(Path(matrix_runner.__file__).resolve()),
        "matrix_runner_sha256": sha256(Path(matrix_runner.__file__).resolve()).upper(),
        "transport_profile": "completion_driven_tx",
        "require_pristine_start": require_pristine_start,
        "forbidden_boot_ids_by_node": {
            node.name: sorted(ids)
            for node, ids in (forbidden_boot_ids or {}).items()
        },
        "prerequisite_root": str(prerequisite_root.resolve())
        if prerequisite_root is not None
        else None,
        "change_policy": matrix_runner._change_policy(
            True,
            connection_parameter_request=False,
        ),
    }


async def _acquire_precheck(
    root_dir: Path | None,
    *,
    plan_version: str = "v3",
    condition: str | None = None,
    prior_root: Path | None = None,
) -> JSON:
    plan_path, plan_sha256, expected_root, schedule, run_order = _precheck_profile(
        plan_version, condition
    )
    if not plan_path.is_file():
        raise FileNotFoundError(f"locked precheck plan is missing: {plan_path}")
    observed_plan_sha256 = sha256(plan_path).upper()
    if observed_plan_sha256 != plan_sha256:
        raise RuntimeError(
            f"locked {plan_version} plan SHA-256 changed: {observed_plan_sha256}"
        )
    selected_root = root_dir if root_dir is not None else expected_root
    locked_root = validate_plan_output_root(
        plan_sha256,
        selected_root,
        condition=condition if plan_version in {"v4", "v5", "v6"} else None,
    )
    if locked_root.exists():
        raise FileExistsError(f"precheck output root must not already exist: {locked_root}")
    if platform.system() != "Windows":
        raise RuntimeError("the locked physical precheck requires its Windows host")

    forbidden_boot_ids: dict[NodeId, frozenset[int]] = {}
    prerequisite_root: Path | None = None
    if plan_version in {"v4", "v5", "v6"}:
        forbidden: dict[NodeId, set[int]] = {
            NodeId.A: {PRECHECK_V3_BOOT_IDS["A"]},
            NodeId.B: {PRECHECK_V3_BOOT_IDS["B"]},
        }
        if condition == "dual_a_to_b":
            condition_roots = _cold_start_roots_for_version(plan_version)
            expected_prior_root = condition_roots["a_only"].resolve()
            if prior_root is None or prior_root.resolve() != expected_prior_root:
                raise ValueError(
                    "dual_a_to_b requires the locked a_only root as --prior-root"
                )
            prerequisite = _audit_cold_start_single(expected_prior_root, plan_version)
            if prerequisite.get("precheck_passed") is not True:
                raise RuntimeError(
                    "a_only raw precheck audit must pass before dual_a_to_b: "
                    + "; ".join(prerequisite.get("errors", []))
                )
            prerequisite_node_rows = prerequisite.get("run", {}).get("nodes", {})
            prerequisite_a = prerequisite_node_rows.get("A", {})
            prerequisite_boot_id = prerequisite_a.get("acquisition_start", {}).get("boot_id")
            if not isinstance(prerequisite_boot_id, int):
                raise RuntimeError("a_only audit does not contain a valid Node A boot ID")
            forbidden[NodeId.A].add(prerequisite_boot_id)
            prerequisite_root = expected_prior_root
        elif prior_root is not None:
            raise ValueError("a_only acquisition does not accept --prior-root")
        forbidden_boot_ids = {
            node: frozenset(ids) for node, ids in forbidden.items()
        }
    elif prior_root is not None:
        raise ValueError("V3 acquisition does not accept --prior-root")

    preflash, images, configurations = _validate_source_artifacts()
    adapter_identity = _read_live_adapter_identity()
    port_info = {
        node: matrix_runner.resolve_cdc_port_by_serial(
            matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node]
        )
        for node in (NodeId.A, NodeId.B)
    }
    for node, info in port_info.items():
        if info.get("device") is None:
            raise RuntimeError(f"USB serial lookup found no CDC port for Node {node.name}")
        validate_runtime_cdc_port(node, info)

    root_config = _live_input_config(
        locked_root,
        plan_path=plan_path,
        plan_sha256=plan_sha256,
        preflash=preflash,
        images=images,
        configurations=configurations,
        port_info=port_info,
        adapter_identity=adapter_identity,
        plan_version=plan_version,
        schedule=schedule,
        run_order=run_order,
        require_pristine_start=plan_version in {"v4", "v5", "v6"},
        forbidden_boot_ids=forbidden_boot_ids,
        prerequisite_root=prerequisite_root,
    )
    locked_root.mkdir(parents=True, exist_ok=False)
    (locked_root / "firmware").mkdir()
    (locked_root / "PREDECLARED_PRECHECK_PLAN.md").write_bytes(plan_path.read_bytes())
    shutil.copyfile(PRECHECK_SOURCE_PREFLASH, locked_root / "source_preflash_record.json")
    for node in (NodeId.A, NodeId.B):
        firmware_name = f"node-{node.name.lower()}"
        shutil.copyfile(images[node], locked_root / "firmware" / f"{firmware_name}.uf2")
        shutil.copyfile(
            configurations[node],
            locked_root / "firmware" / f"{firmware_name}.config",
        )
    _write_json(locked_root / "matrix_config.json", root_config)

    control_events = EventLog(locked_root / "matrix_control.ndjson")
    cdc_captures = {
        node: matrix_runner._MatrixCdcCapture(
            node=node,
            port_info=port_info[node],
            output_dir=locked_root,
            events=control_events,
        )
        for node in (NodeId.A, NodeId.B)
    }
    started_captures: set[NodeId] = set()
    initial_off_control: dict[str, dict[str, object]] = {}
    final_control_cleanup: dict[str, dict[str, object]] = {}
    run_results: list[dict[str, object]] = []
    stop_reason: str | None = None
    control_gate_error: str | None = None
    capture_metadata: dict[str, JSON] = {}
    try:
        for node, capture in cdc_captures.items():
            capture.start()
            started_captures.add(node)
        for node, capture in cdc_captures.items():
            if not capture.ready.wait(timeout=10.0):
                capture.error = f"timed out opening serial port {capture.port_info.get('device')}"
                control_events.write("cdc_open_timeout", node=node, detail=capture.error)
            elif capture.error is not None:
                control_events.write("cdc_open_error", node=node, detail=capture.error)
        open_errors = [
            f"Node {node.name} CDC capture failed: {capture.error or 'not ready'}"
            for node, capture in cdc_captures.items()
            if capture.error is not None or not capture.ready.is_set() or capture.done.is_set()
        ]
        if open_errors:
            control_gate_error = "; ".join(open_errors)
            stop_reason = control_gate_error
            raise matrix_runner.CdcControlGateError(control_gate_error)

        initial_off_control = await _initialize_off_control(cdc_captures, control_events)
        prior_result: JSON | None = None
        run_index = 0
        for _request_mode, conditions in schedule:
            for condition in conditions:
                run_index += 1
                if prior_result is not None:
                    disconnect_ns = int(prior_result["disconnect_completed_monotonic_ns"])
                    target_ns = disconnect_ns + int(PRECHECK_REST_SECONDS * 1_000_000_000)
                    remaining_ns = target_ns - time.monotonic_ns()
                    if remaining_ns > 0:
                        await asyncio.sleep(remaining_ns / 1_000_000_000)
                setup_started_ns = time.monotonic_ns()
                offsets: dict[NodeId, int] = {}
                try:
                    offsets = await matrix_runner._cut_cdc_captures(cdc_captures)
                    for node, offset in offsets.items():
                        control_events.write(
                            "precheck_run_cdc_boundary",
                            node=node,
                            run_index=run_index,
                            offset=offset,
                        )
                    current = await matrix_runner._run_condition(
                        run_dir=locked_root / f"run-{run_index:02d}-{condition}",
                        condition=condition,
                        run_index=run_index,
                        seconds=PRECHECK_CAPTURE_SECONDS,
                        node_a_address=PRECHECK_BLE_ADDRESSES[NodeId.A],
                        node_b_address=PRECHECK_BLE_ADDRESSES[NodeId.B],
                        expected_node_a_device_id=PRECHECK_HARDWARE_DEVICE_IDS[NodeId.A],
                        expected_node_b_device_id=PRECHECK_HARDWARE_DEVICE_IDS[NodeId.B],
                        request_mode="OFF",
                        set_request_mode_before_run=False,
                        cdc_captures=cdc_captures,
                        plan_path=plan_path,
                        plan_sha256=plan_sha256,
                        completion_driven_tx=True,
                        experiment_profile="link_count_precheck",
                        connection_parameter_request=False,
                        require_pristine_start=plan_version in {"v4", "v5", "v6"},
                        forbidden_boot_ids=forbidden_boot_ids,
                        cdc_start_offsets=offsets,
                        connection_timeout_s=precheck_connect_timeout_seconds(plan_version),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    current = {
                        "run_index": run_index,
                        "block_index": 1,
                        "block_run_index": run_index,
                        "request_mode": "OFF",
                        "condition": condition,
                        "started_monotonic_ns": setup_started_ns,
                        "disconnect_completed_monotonic_ns": time.monotonic_ns(),
                        "cdc_start_offsets": {
                            node.name: offset for node, offset in offsets.items()
                        },
                        "error": f"{type(error).__name__}: {error}",
                    }
                    if isinstance(error, matrix_runner.CdcControlGateError):
                        control_gate_error = str(error)
                if prior_result is not None:
                    prior_disconnect_ns = int(prior_result["disconnect_completed_monotonic_ns"])
                    current_setup_ns = int(current["started_monotonic_ns"])
                    prior_result["inter_run_rest_target_seconds"] = PRECHECK_REST_SECONDS
                    prior_result["inter_run_rest_observed_seconds"] = (
                        current_setup_ns - prior_disconnect_ns
                    ) / 1_000_000_000
                run_results.append(current)
                prior_result = current
                if current.get("error") is not None:
                    stop_reason = str(current["error"])
                    control_events.write(
                        "precheck_stopped_after_failed_run",
                        run_index=run_index,
                        condition=condition,
                        detail=stop_reason,
                    )
                    break
            if stop_reason is not None:
                break
    except asyncio.CancelledError as error:
        stop_reason = f"CancelledError: precheck acquisition cancelled ({error})"
        control_events.write("precheck_cancelled", detail=stop_reason)
    except Exception as error:
        if control_gate_error is None and isinstance(error, matrix_runner.CdcControlGateError):
            control_gate_error = str(error)
        stop_reason = stop_reason or f"{type(error).__name__}: {error}"
        control_events.write("precheck_stopped", detail=stop_reason)
    finally:
        if started_captures:
            try:
                final_control_cleanup = await matrix_runner._rollback_control_nodes(
                    cdc_captures,
                    tuple(node for node in (NodeId.A, NodeId.B) if node in started_captures),
                    control_events.write,
                    timeout_s=5.0,
                    event_name="precheck_final_off_cleanup",
                )
            except Exception as error:
                stop_reason = stop_reason or (
                    f"final OFF cleanup failed: {type(error).__name__}: {error}"
                )
                final_control_cleanup = {
                    node.name: {
                        "node_id": int(node),
                        "requested": "OFF",
                        "applied": False,
                        "rc": None,
                        "error": stop_reason,
                    }
                    for node in (NodeId.A, NodeId.B)
                }
        for node in started_captures:
            cdc_captures[node].stop()
        for node in started_captures:
            capture = cdc_captures[node]
            capture.join()
            capture.finalize_text_log()
        capture_metadata = {
            node.name: capture.metadata() for node, capture in cdc_captures.items()
        }
        control_events.write(
            "precheck_capture_finished",
            run_count=len(run_results),
            cdc=capture_metadata,
        )
        control_events.close()

        _write_json(locked_root / "serial_capture_summary.json", capture_metadata)
        result: JSON = {
            "schema": "kineimu.m1.ble-link-count-precheck-result/1.0",
            "plan_sha256": plan_sha256,
            "plan_version": plan_version,
            "run_order": list(run_order),
            "schedule_attempted_count": len(run_results),
            "scheduled_count": len(run_order),
            "all_scheduled_runs_attempted": len(run_results) == len(run_order),
            "initial_off_control": initial_off_control,
            "final_control_cleanup": final_control_cleanup,
            "control_gate_error": control_gate_error,
            "stop_reason": stop_reason,
            "serial_capture_summary": capture_metadata,
            "run_results": run_results,
        }
        _write_json(locked_root / "matrix_result.json", result)
        manifest = write_sha256_manifest(locked_root)
        result["manifest_sha256"] = sha256(manifest).upper()
        print(
            json.dumps(
                {
                    "root_dir": str(locked_root),
                    "schedule_attempted_count": len(run_results),
                    "manifest_sha256": result["manifest_sha256"],
                    "stop_reason": stop_reason,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    acquire = subparsers.add_parser("acquire", help="run the one-time physical precheck")
    acquire.add_argument("--plan-version", choices=("v3", "v4", "v5", "v6"), default="v3")
    acquire.add_argument(
        "--condition", choices=tuple(PRECHECK_V6_OUTPUT_ROOTS), default=None
    )
    acquire.add_argument("--root-dir", type=Path, default=None)
    acquire.add_argument("--prior-root", type=Path, default=None)
    audit = subparsers.add_parser("audit", help="read-only audit from raw files and sidecars")
    audit.add_argument("--root-dir", type=Path, required=True)
    audit.add_argument("--output-json", type=Path, required=True)
    audit_pair = subparsers.add_parser(
        "audit-pair", help="independently audit both locked cold-start roots"
    )
    audit_pair.add_argument("--plan-version", choices=("v4", "v5", "v6"), default="v4")
    audit_pair.add_argument("--output-json", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "acquire":
        try:
            result = asyncio.run(
                _acquire_precheck(
                    args.root_dir,
                    plan_version=args.plan_version,
                    condition=args.condition,
                    prior_root=args.prior_root,
                )
            )
        except (OSError, RuntimeError, TimeoutError, ValueError) as error:
            print(
                json.dumps({"error": f"{type(error).__name__}: {error}"}, sort_keys=True),
                file=sys.stderr,
            )
            return 2
        return (
            0
            if result["all_scheduled_runs_attempted"]
            and result["stop_reason"] is None
            else 2
        )

    output = args.output_json.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite independent analysis output: {output}")
    if args.command == "audit-pair":
        roots = tuple(
            path.resolve() for path in _cold_start_roots_for_version(args.plan_version).values()
        )
        if any(output == root or root in output.parents for root in roots):
            raise ValueError("paired audit output must be outside both raw condition roots")
        report = (
            audit_precheck_v4_pair()
            if args.plan_version == "v4"
            else audit_precheck_v5_pair()
            if args.plan_version == "v5"
            else audit_precheck_v6_pair()
        )
    else:
        root = args.root_dir.resolve()
        if output == root or root in output.parents:
            raise ValueError("independent audit output must be outside the raw precheck root")
        report = audit_precheck(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output, report)
    print(
        json.dumps(
            {
                "output_json": str(output),
                "output_sha256": sha256(output).upper(),
                "precheck_passed": report["precheck_passed"],
                "disposition": report["disposition"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["precheck_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
