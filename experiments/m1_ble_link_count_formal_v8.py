"""Acquire the locked V8 M1 active-link-count root-cause experiment."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any, cast

from experiments import m1_ble_link_matrix as matrix_runner
from experiments import m1_ble_link_precheck as precheck
from experiments.m1_transport_experiment import EventLog
from kineimu_shoulder.io.m1_packet import NodeId

JSON = dict[str, Any]

FORMAL_PLAN_PATH = Path(__file__).with_name(
    "M1_BLE_LINK_COUNT_ROOT_CAUSE_PLAN_V8_20260924.md"
)
FORMAL_PLAN_SHA256 = "3E790212705C22C7B0A1D550D2AD00BB34ABEE494849DA4ECC55B38095BC5ABF"
FORMAL_OUTPUT_ROOT = Path("<external-data>/kineimu_m1_root_cause_formal_v8_20260924_01")
FORMAL_CAPTURE_SECONDS = 15.0
FORMAL_REST_SECONDS = 2.0
FORMAL_SETTLE_SECONDS = 10.0
FORMAL_CONNECT_TIMEOUT_SECONDS = 30.0
FORMAL_SCHEDULE_SEED = 20260924
FORMAL_BLOCK_SCHEDULE: tuple[tuple[str, ...], ...] = (
    ("a_only", "b_only", "dual_b_to_a", "dual_a_to_b"),
    ("dual_b_to_a", "a_only", "dual_a_to_b", "b_only"),
    ("dual_a_to_b", "dual_b_to_a", "b_only", "a_only"),
    ("b_only", "dual_a_to_b", "a_only", "dual_b_to_a"),
)
FORMAL_CONDITIONS = frozenset(
    {"a_only", "b_only", "dual_a_to_b", "dual_b_to_a"}
)
FORMAL_FORBIDDEN_BOOT_IDS = {
    NodeId.A: frozenset(
        {
            precheck.PRECHECK_V3_BOOT_IDS["A"],
            2701971511492984250,
            9353023436044725051,
            12288373895513561913,
            7701146763957617505,
        }
    ),
    NodeId.B: frozenset(
        {
            precheck.PRECHECK_V3_BOOT_IDS["B"],
            13643691926106628137,
            4936689328756888443,
        }
    ),
}
FORMAL_ORDER_NODES = {
    "dual_a_to_b": ("A", "B"),
    "dual_b_to_a": ("B", "A"),
}


def reset_confirmation_token(run_index: int) -> str:
    """Return the run-specific token required after a physical two-board reset."""

    if not 1 <= run_index <= len(FORMAL_BLOCK_SCHEDULE) * 4:
        raise ValueError("V8 reset confirmation run index must be from 1 through 16")
    return f"COLD_RESET_{run_index:02d}"


def validate_reset_confirmation(run_index: int, response: str) -> bool:
    """Require an exact run-specific operator assertion before opening CDC/BLE."""

    return response.strip().upper() == reset_confirmation_token(run_index)


def pre_notify_boot_ids(
    events: list[JSON], expected_nodes: tuple[str, ...]
) -> tuple[dict[str, int], list[str]]:
    """Require one passed pristine pre-notify status record for every active node."""

    boot_ids: dict[str, int] = {}
    errors: list[str] = []
    for node in expected_nodes:
        gates = [
            event
            for event in events
            if event.get("event") == "pre_notify_status_gate"
            and event.get("node") == node
        ]
        if len(gates) != 1:
            errors.append(f"Node {node} pre-notify status gate must occur exactly once; found {len(gates)}")
            continue
        gate = gates[0]
        if gate.get("passed") is not True:
            errors.append(f"Node {node} pre-notify status gate did not pass")
            continue
        status = gate.get("status")
        if not isinstance(status, dict):
            errors.append(f"Node {node} pre-notify status gate has no decoded status")
            continue
        boot_id = status.get("boot_id")
        if not isinstance(boot_id, int) or isinstance(boot_id, bool):
            errors.append(f"Node {node} pre-notify status has no integer boot ID")
            continue
        if status.get("acquisition_state") != "armed":
            errors.append(f"Node {node} pre-notify acquisition state is not armed")
            continue
        boot_ids[node] = boot_id
    return boot_ids, errors


def formal_order(blocks: int) -> tuple[str, ...]:
    """Return the predeclared four-block, counterbalanced V8 run order."""

    if blocks != len(FORMAL_BLOCK_SCHEDULE):
        raise ValueError("the locked V8 experiment requires exactly four blocks")
    return tuple(condition for block in FORMAL_BLOCK_SCHEDULE for condition in block)


def derive_matched_ratios(
    block_packets: list[dict[str, dict[str, int]]],
) -> dict[str, Any]:
    """Compute dual/same-block-single and first/second packet-count ratios."""

    if len(block_packets) != 4:
        raise ValueError("V8 matched ratios require exactly four complete blocks")
    per_node: dict[str, dict[str, list[float | None]]] = {
        node: {condition: [] for condition in FORMAL_ORDER_NODES}
        for node in ("A", "B")
    }
    first_second: dict[str, list[float | None]] = {
        condition: [] for condition in FORMAL_ORDER_NODES
    }
    for block in block_packets:
        for condition, (first_node, second_node) in FORMAL_ORDER_NODES.items():
            dual = block.get(condition, {})
            first_count = dual.get(first_node)
            second_count = dual.get(second_node)
            first_second[condition].append(
                first_count / second_count
                if isinstance(first_count, int)
                and isinstance(second_count, int)
                and second_count > 0
                else None
            )
            for node, single_condition in (("A", "a_only"), ("B", "b_only")):
                dual_count = dual.get(node)
                single_count = block.get(single_condition, {}).get(node)
                per_node[node][condition].append(
                    dual_count / single_count
                    if isinstance(dual_count, int)
                    and isinstance(single_count, int)
                    and single_count > 0
                    else None
                )
    return {"per_node_dual_to_single": per_node, "first_to_second": first_second}


def _valid_four(values: list[float | None]) -> bool:
    return len(values) == 4 and all(
        isinstance(value, (int, float)) and 0.0 <= value < float("inf")
        for value in values
    )


def classify_factor_effect(
    node_order_ratios: dict[str, dict[str, list[float | None]]],
    first_second_ratios: dict[str, list[float | None]],
    *,
    integrity_valid: bool,
    transport_clean: bool,
) -> JSON:
    """Apply V8's prespecified disposition without treating packets as replicates."""

    expected_orders = set(FORMAL_ORDER_NODES)
    if not integrity_valid:
        return {
            "disposition": "Inconclusive",
            "reason": "one or more acquisition-integrity gates failed",
        }
    for node in ("A", "B"):
        if set(node_order_ratios.get(node, {})) != expected_orders or any(
            not _valid_four(node_order_ratios[node][condition])
            for condition in expected_orders
        ):
            return {
                "disposition": "Inconclusive",
                "reason": f"Node {node} lacks four valid matched ratios in both dual orders",
            }
    if set(first_second_ratios) != expected_orders or any(
        not _valid_four(first_second_ratios[condition]) for condition in expected_orders
    ):
        return {
            "disposition": "Inconclusive",
            "reason": "one or both connection orders lack four valid first/second ratios",
        }

    for node in ("A", "B"):
        impaired_orders = {
            condition: sum(value < 0.90 for value in node_order_ratios[node][condition])
            for condition in expected_orders
        }
        if all(count >= 3 for count in impaired_orders.values()):
            return {
                "disposition": "Supported",
                "reason": (
                    f"Node {node} is below the 0.90 same-block single-link ratio in at least "
                    "three of four blocks under both connection orders"
                ),
                "affected_node": node,
                "below_gate_count_by_order": impaired_orders,
            }

    all_throughput_ratios_pass = all(
        value >= 0.90
        for node in ("A", "B")
        for condition in expected_orders
        for value in node_order_ratios[node][condition]
    )
    all_order_ratios_pass = all(
        value >= 0.90
        for condition in expected_orders
        for value in first_second_ratios[condition]
    )
    if all_throughput_ratios_pass and all_order_ratios_pass and transport_clean:
        return {
            "disposition": "Not supported",
            "reason": (
                "all same-block dual/single and first/second ratios meet 0.90, "
                "with zero TX enqueue drops and zero CRC/decode/framing errors"
            ),
        }
    return {
        "disposition": "Inconclusive",
        "reason": (
            "the prespecified repeatability threshold was not met and/or a throughput, "
            "order-balance, or transport-quality gate failed"
        ),
    }


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _locked_input_config(
    root_dir: Path,
    *,
    preflash: JSON,
    images: dict[NodeId, Path],
    configurations: dict[NodeId, Path],
    port_info: dict[NodeId, dict[str, object]],
    adapter_identity: JSON,
) -> JSON:
    repo_root = Path(__file__).resolve().parents[1]
    predeclared_schedule = tuple(("OFF", block) for block in FORMAL_BLOCK_SCHEDULE)
    base = precheck._live_input_config(
        root_dir,
        plan_path=FORMAL_PLAN_PATH,
        plan_sha256=FORMAL_PLAN_SHA256,
        preflash=preflash,
        images=images,
        configurations=configurations,
        port_info=port_info,
        adapter_identity=adapter_identity,
        plan_version="v6",
        schedule=predeclared_schedule,
        run_order=formal_order(4),
        require_pristine_start=True,
        forbidden_boot_ids=FORMAL_FORBIDDEN_BOOT_IDS,
    )
    head = matrix_runner._git_head(repo_root)
    if head is None:
        raise RuntimeError("could not resolve the lock commit HEAD")
    base.update(
        {
            "schema": "kineimu.m1.ble-link-count-formal-v8/1.0",
            "plan_version": "v8",
            "precheck_plan_version": "v8",
            "objective": "causally test the effect of active BLE link count under the locked host/firmware combination",
            "single_factor": "active_ble_link_count",
            "schedule_seed": FORMAL_SCHEDULE_SEED,
            "blocks": 4,
            "block_schedule": [
                {"block": index, "request_mode": "OFF", "sequence": list(block)}
                for index, block in enumerate(FORMAL_BLOCK_SCHEDULE, start=1)
            ],
            "run_order": list(formal_order(4)),
            "seconds_per_capture": FORMAL_CAPTURE_SECONDS,
            "connection_settle_seconds": FORMAL_SETTLE_SECONDS,
            "windows_connect_gatt_setup_timeout_seconds": FORMAL_CONNECT_TIMEOUT_SECONDS,
            "inter_run_rest_seconds": FORMAL_REST_SECONDS,
            "output_root": str(root_dir.resolve()),
            "predeclared_plan_path": str(FORMAL_PLAN_PATH.resolve()),
            "predeclared_plan_sha256": FORMAL_PLAN_SHA256,
            "require_pristine_start": "every scheduled condition; unique boot ID per node across all V8 runs",
            "cold_reset_policy": (
                "operator power-cycles and USB-reenumerates both boards before every scheduled condition"
            ),
            "cdc_capture_policy": "new per-run CDC capture threads and run-local complete byte streams",
            "git_head": head,
            "runner_path": str(Path(__file__).resolve()),
            "runner_sha256": precheck.sha256(Path(__file__)).upper(),
            "acquisition_code_hashes": {
                "formal_runner": precheck.sha256(Path(__file__)).upper(),
                "independent_auditor": precheck.sha256(
                    Path(__file__).with_name("m1_ble_link_count_formal_audit_v8.py")
                ).upper(),
                "shared_matrix_runner": precheck.sha256(Path(matrix_runner.__file__)).upper(),
                "precheck_helpers": precheck.sha256(Path(precheck.__file__)).upper(),
            },
            "v6_precheck_manifest_sha256": {
                "a_only": "624253D0386CB41F09BD86BB23A092178BD5FB8711A992FD7E48E3AC2436FD75",
                "dual_a_to_b": "3E69E3EC628822A2C0539940DFB5B65689F5549A3B857D24C72EF5A25B41B7F2",
                "pair_audit": "0FB442DC725F05210B6B73CA89FF56061CC9995D02FB07EC9E3375E324C0C35A",
            },
        }
    )
    precheck.validate_committed_precheck_inputs(
        repo_root,
        (
            FORMAL_PLAN_PATH,
            Path(__file__),
            Path(__file__).with_name("m1_ble_link_count_formal_audit_v8.py"),
            Path(matrix_runner.__file__),
            Path(precheck.__file__),
        ),
    )
    return base


def _prepare_locked_root(
    root_dir: Path,
    *,
    config: JSON,
    images: dict[NodeId, Path],
    configurations: dict[NodeId, Path],
) -> None:
    (root_dir / "firmware").mkdir()
    (root_dir / "operator_reset_confirmations").mkdir()
    _write_json(root_dir / "matrix_config.json", config)
    (root_dir / "PREDECLARED_PLAN.md").write_bytes(FORMAL_PLAN_PATH.read_bytes())
    shutil.copyfile(
        precheck.PRECHECK_SOURCE_PREFLASH,
        root_dir / "source_preflash_record.json",
    )
    for node in (NodeId.A, NodeId.B):
        name = node.name.lower()
        shutil.copyfile(images[node], root_dir / "firmware" / f"node-{name}.uf2")
        shutil.copyfile(configurations[node], root_dir / "firmware" / f"node-{name}.config")


def precollection_failure_result(config: JSON, error: Exception) -> JSON:
    """Describe a locked acquisition that failed before any scheduled run began."""

    order = config.get("run_order", list(formal_order(4)))
    if not isinstance(order, list):
        order = list(formal_order(4))
    return {
        "schema": "kineimu.m1.ble-link-count-formal-v8-result/1.0",
        "plan_sha256": FORMAL_PLAN_SHA256,
        "lock_head": config.get("git_head"),
        "run_order": order,
        "scheduled_count": len(order),
        "schedule_attempted_count": 0,
        "all_scheduled_runs_attempted": False,
        "initial_off_control": {},
        "final_control_cleanup": {},
        "per_run_off_control": [],
        "per_run_final_off_cleanup": [],
        "control_gate_error": None,
        "stop_reason": f"{type(error).__name__}: {error}",
        "run_results": [],
    }


def _seal_precollection_failure(root_dir: Path, config: JSON, error: Exception) -> JSON:
    """Preserve a zero-run result and hash manifest after this invocation owns the root."""

    result = precollection_failure_result(config, error)
    _write_json(root_dir / "matrix_result.json", result)
    manifest = precheck.write_sha256_manifest(root_dir)
    result["manifest_sha256"] = precheck.sha256(manifest).upper()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


async def acquire_v8(root_dir: Path = FORMAL_OUTPUT_ROOT) -> JSON:
    """Run V8 once with a verified cold boot and isolated CDC capture per condition."""

    if precheck.sha256(FORMAL_PLAN_PATH).upper() != FORMAL_PLAN_SHA256:
        raise RuntimeError("V8 predeclared plan SHA-256 differs from the runner lock")
    if root_dir.resolve() != FORMAL_OUTPUT_ROOT.resolve():
        raise ValueError(f"V8 acquisition is bound to {FORMAL_OUTPUT_ROOT}")
    if root_dir.exists():
        raise FileExistsError(f"V8 evidence root must be new and empty: {root_dir}")
    if platform.system() != "Windows":
        raise RuntimeError("V8 physical acquisition requires the locked Windows host")
    if not sys.stdin.isatty():
        raise RuntimeError(
            "V8 requires interactive run-specific operator confirmation before creating its evidence root"
        )

    preflash, images, configurations = precheck._validate_source_artifacts()
    adapter_identity = precheck._read_live_adapter_identity()
    port_info = {
        node: matrix_runner.resolve_cdc_port_by_serial(
            matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node]
        )
        for node in (NodeId.A, NodeId.B)
    }
    for node, details in port_info.items():
        if details.get("device") is None:
            raise RuntimeError(f"USB serial lookup found no CDC port for Node {node.name}")
        precheck.validate_runtime_cdc_port(node, details)
    config = _locked_input_config(
        root_dir,
        preflash=preflash,
        images=images,
        configurations=configurations,
        port_info=port_info,
        adapter_identity=adapter_identity,
    )
    # Claim the unique evidence root before creating any files. If preparation or
    # control-log creation then fails, seal that owned root as a zero-run result.
    root_dir.mkdir(parents=True, exist_ok=False)
    try:
        _prepare_locked_root(
            root_dir,
            config=config,
            images=images,
            configurations=configurations,
        )
        control_events = EventLog(root_dir / "matrix_control.ndjson")
    except Exception as error:
        return _seal_precollection_failure(root_dir, config, error)

    run_results: list[JSON] = []
    stop_reason: str | None = None
    seen_boot_ids: dict[NodeId, set[int]] = {
        node: set(FORMAL_FORBIDDEN_BOOT_IDS[node]) for node in (NodeId.A, NodeId.B)
    }
    prior_disconnect_ns: int | None = None
    order = formal_order(4)
    try:
        for run_index, condition in enumerate(order, start=1):
            block_index = (run_index - 1) // 4 + 1
            block_run_index = (run_index - 1) % 4 + 1
            started_ns = time.monotonic_ns()
            if prior_disconnect_ns is not None:
                rest_deadline_ns = prior_disconnect_ns + int(FORMAL_REST_SECONDS * 1_000_000_000)
                rest_ns = rest_deadline_ns - time.monotonic_ns()
                if rest_ns > 0:
                    await asyncio.sleep(rest_ns / 1_000_000_000)
            active_nodes = matrix_runner._nodes_for_condition(condition)
            active_names = tuple(node.name for node in active_nodes)
            run_dir = root_dir / f"run-{run_index:02d}-{condition}"
            run_dir.mkdir(parents=True, exist_ok=False)
            token = reset_confirmation_token(run_index)
            control_events.write(
                "formal_scheduled_condition_start",
                run_index=run_index,
                block_index=block_index,
                block_run_index=block_run_index,
                condition=condition,
                request_mode="OFF",
                require_pristine_start=True,
                required_operator_reset_token=token,
            )
            offsets: dict[NodeId, int] = {}
            cdc_captures: dict[NodeId, matrix_runner._MatrixCdcCapture] = {}
            started_captures: set[NodeId] = set()
            run_started = False
            current: JSON = {
                "run_index": run_index,
                "block_index": block_index,
                "block_run_index": block_run_index,
                "condition": condition,
                "request_mode": "OFF",
                "scheduled": True,
                "attempted": True,
                "require_pristine_start": True,
                "started_monotonic_ns": started_ns,
                "operator_reset_confirmation": None,
                "pre_notify_boot_ids": {},
                "fresh_boot_gate_errors": [],
                "final_off_cleanup": {},
                "serial_capture_summary": {},
                "error": None,
            }
            control_gate_error: str | None = None
            try:
                prompt = (
                    f"V8 run {run_index:02d}/16 ({condition}, block {block_index}): "
                    "physically power-cycle BOTH boards (remove USB/power for at least 5 s), "
                    "reconnect them, and confirm the two locked USB serials are enumerated. "
                    "This is the live acquisition prompt in the persistent V8 session; "
                    "confirm in Codex chat and the agent will enter the token here. "
                    "Never type the token at a PowerShell command prompt. "
                    f"Then type {token}: "
                )
                response = input(prompt)
                reset_confirmation = {
                    "run_index": run_index,
                    "condition": condition,
                    "token_expected": token,
                    "operator_asserted_both_boards_power_cycled": validate_reset_confirmation(
                        run_index, response
                    ),
                    "confirmed_monotonic_ns": time.monotonic_ns(),
                    "minimum_power_off_seconds": 5,
                }
                current["operator_reset_confirmation"] = reset_confirmation
                _write_json(
                    root_dir
                    / "operator_reset_confirmations"
                    / f"run-{run_index:02d}-{condition}.json",
                    reset_confirmation,
                )
                control_events.write(
                    "formal_operator_cold_reset_confirmation",
                    run_index=run_index,
                    condition=condition,
                    token_expected=token,
                    confirmed=reset_confirmation["operator_asserted_both_boards_power_cycled"],
                )
                if reset_confirmation["operator_asserted_both_boards_power_cycled"] is not True:
                    raise matrix_runner.CdcControlGateError(
                        f"operator did not enter the required run-specific cold-reset token {token}"
                    )

                # USB COM numbers can change after physical re-enumeration. Resolve each
                # board afresh by its locked USB serial after every operator-confirmed reset.
                port_info = {
                    node: matrix_runner.resolve_cdc_port_by_serial(
                        matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node]
                    )
                    for node in (NodeId.A, NodeId.B)
                }
                for node, details in port_info.items():
                    if details.get("device") is None:
                        raise matrix_runner.CdcControlGateError(
                            f"USB serial lookup found no CDC port for Node {node.name} after reset"
                        )
                    precheck.validate_runtime_cdc_port(node, details)
                current["cdc_ports_after_reset"] = {
                    node.name: port_info[node] for node in (NodeId.A, NodeId.B)
                }
                control_events.write(
                    "formal_run_cdc_ports_resolved_after_reset",
                    run_index=run_index,
                    condition=condition,
                    ports=current["cdc_ports_after_reset"],
                )
                full_capture_dir = root_dir / "cdc_full_capture" / f"run-{run_index:02d}-{condition}"
                full_capture_dir.mkdir(parents=True, exist_ok=False)
                cdc_captures = {
                    node: matrix_runner._MatrixCdcCapture(
                        node=node,
                        port_info=port_info[node],
                        output_dir=full_capture_dir,
                        events=control_events,
                    )
                    for node in (NodeId.A, NodeId.B)
                }
                current["cdc_full_capture_dir"] = str(
                    full_capture_dir.relative_to(root_dir).as_posix()
                )
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
                    raise matrix_runner.CdcControlGateError("; ".join(open_errors))

                offsets = await matrix_runner._cut_cdc_captures(cdc_captures)
                for node, offset in offsets.items():
                    control_events.write(
                        "formal_run_cdc_boundary",
                        node=node,
                        run_index=run_index,
                        offset=offset,
                    )
                run_kwargs: dict[str, object] = {
                    "run_dir": run_dir,
                    "condition": condition,
                    "run_index": run_index,
                    "seconds": FORMAL_CAPTURE_SECONDS,
                    "node_a_address": precheck.PRECHECK_BLE_ADDRESSES[NodeId.A],
                    "node_b_address": precheck.PRECHECK_BLE_ADDRESSES[NodeId.B],
                    "expected_node_a_device_id": precheck.PRECHECK_HARDWARE_DEVICE_IDS[NodeId.A],
                    "expected_node_b_device_id": precheck.PRECHECK_HARDWARE_DEVICE_IDS[NodeId.B],
                    "request_mode": "OFF",
                    "set_request_mode_before_run": True,
                    "cdc_captures": cdc_captures,
                    "plan_path": FORMAL_PLAN_PATH,
                    "plan_sha256": FORMAL_PLAN_SHA256,
                    "completion_driven_tx": True,
                    "experiment_profile": "link_count_formal_v8",
                    "connection_parameter_request": False,
                    "require_pristine_start": True,
                    "forbidden_boot_ids": {
                        node: frozenset(seen_boot_ids[node]) for node in (NodeId.A, NodeId.B)
                    },
                    "pre_run_control_results": None,
                    "cdc_start_offsets": offsets,
                    "connection_timeout_s": FORMAL_CONNECT_TIMEOUT_SECONDS,
                }
                run_started = True
                acquired = await matrix_runner._run_condition_with_control(
                    request_mode="OFF",
                    cdc_captures=cdc_captures,
                    events=control_events.write,
                    run_condition=matrix_runner._run_condition,
                    run_kwargs=run_kwargs,
                    timeout_s=5.0,
                    controlled_nodes=(NodeId.A, NodeId.B),
                )
                current.update(acquired)
                run_events = precheck._read_ndjson(run_dir / "experiment_control.ndjson")
                observed_boot_ids, boot_errors = pre_notify_boot_ids(run_events, active_names)
                for node_name, boot_id in observed_boot_ids.items():
                    node = NodeId[node_name]
                    if boot_id in seen_boot_ids[node]:
                        boot_errors.append(
                            f"Node {node_name} reused boot ID {boot_id} from an earlier/precheck run"
                        )
                    seen_boot_ids[node].add(boot_id)
                current["pre_notify_boot_ids"] = observed_boot_ids
                current["fresh_boot_gate_errors"] = boot_errors
                current["off_control_acknowledgments"] = current.get(
                    "block_mode_control", {}
                )
                if boot_errors:
                    current["error"] = "; ".join(boot_errors)
                off_control_errors = [
                    f"Node {node.name} OFF acknowledgment is missing or unsuccessful"
                    for node in (NodeId.A, NodeId.B)
                    if not isinstance(current["off_control_acknowledgments"].get(node.name), dict)
                    or current["off_control_acknowledgments"][node.name].get("requested") != "OFF"
                    or current["off_control_acknowledgments"][node.name].get("applied") is not True
                    or current["off_control_acknowledgments"][node.name].get("rc") != 0
                ]
                current["off_control_gate_errors"] = off_control_errors
                if off_control_errors:
                    current["error"] = current.get("error") or "; ".join(off_control_errors)
                    control_gate_error = "; ".join(off_control_errors)
                disconnect_valid, disconnect_errors = precheck._audit_cleanup(
                    current, run_events, active_names
                )
                current["runtime_disconnect_cleanup_valid"] = disconnect_valid
                current["runtime_disconnect_cleanup_errors"] = disconnect_errors
                if not disconnect_valid:
                    current["error"] = current.get("error") or "; ".join(disconnect_errors)
                current.update(
                    {
                        "block_index": block_index,
                        "block_run_index": block_run_index,
                        "scheduled": True,
                        "attempted": True,
                        "started_monotonic_ns": started_ns,
                    }
                )
            except asyncio.CancelledError as error:
                current["error"] = f"CancelledError: V8 run cancelled ({error})"
                current["disconnect_completed_monotonic_ns"] = time.monotonic_ns()
                control_events.write(
                    "formal_scheduled_condition_failure",
                    run_index=run_index,
                    block_index=block_index,
                    condition=condition,
                    detail=current["error"],
                )
            except KeyboardInterrupt:
                current["error"] = "KeyboardInterrupt: operator cancelled the V8 condition"
                current["disconnect_completed_monotonic_ns"] = time.monotonic_ns()
                control_events.write(
                    "formal_scheduled_condition_failure",
                    run_index=run_index,
                    block_index=block_index,
                    condition=condition,
                    detail=current["error"],
                )
            except Exception as error:
                current["disconnect_completed_monotonic_ns"] = time.monotonic_ns()
                current["cdc_start_offsets"] = {
                    node.name: offset for node, offset in offsets.items()
                }
                current["error"] = f"{type(error).__name__}: {error}"
                if isinstance(error, matrix_runner.CdcControlGateError):
                    control_gate_error = str(error)
                control_events.write(
                    "formal_scheduled_condition_failure",
                    run_index=run_index,
                    block_index=block_index,
                    condition=condition,
                    detail=current["error"],
                )
            finally:
                if started_captures:
                    try:
                        current["final_off_cleanup"] = await matrix_runner._rollback_control_nodes(
                            cdc_captures,
                            tuple(node for node in (NodeId.A, NodeId.B) if node in started_captures),
                            control_events.write,
                            timeout_s=5.0,
                            event_name="formal_run_final_off_cleanup",
                        )
                    except Exception as error:
                        cleanup_error = f"final run OFF cleanup failed: {type(error).__name__}: {error}"
                        current["final_off_cleanup_error"] = cleanup_error
                    for node in started_captures:
                        cdc_captures[node].stop()
                    for node in started_captures:
                        capture = cdc_captures[node]
                        capture.join()
                        try:
                            capture.finalize_text_log()
                        except Exception as error:
                            current.setdefault("capture_finalization_errors", []).append(
                                f"Node {node.name}: {type(error).__name__}: {error}"
                            )
                    capture_metadata: JSON = {}
                    for node, capture in cdc_captures.items():
                        metadata = capture.metadata()
                        metadata["raw_relative_path"] = (
                            Path(str(current.get("cdc_full_capture_dir", "")))
                            / str(metadata.get("raw_path", ""))
                        ).as_posix()
                        metadata["decoded_log_relative_path"] = (
                            Path(str(current.get("cdc_full_capture_dir", "")))
                            / str(metadata.get("decoded_log_path", ""))
                        ).as_posix()
                        capture_metadata[node.name] = metadata
                    current["serial_capture_summary"] = capture_metadata
                    cdc_capture_errors = [
                        f"Node {node}: {capture.error}"
                        for node, capture in cdc_captures.items()
                        if capture.error is not None
                    ]
                    current["cdc_capture_errors"] = cdc_capture_errors
                    if cdc_capture_errors:
                        current["error"] = current.get("error") or "; ".join(cdc_capture_errors)
                if not (run_dir / "serial_capture_summary.json").exists():
                    _write_json(
                        run_dir / "serial_capture_summary.json",
                        current.get("serial_capture_summary", {}),
                    )
                if not (run_dir / "scheduled_attempt.json").exists():
                    _write_json(run_dir / "scheduled_attempt.json", current)

            for node_name, cleanup in current.get("final_off_cleanup", {}).items():
                if not isinstance(cleanup, dict) or cleanup.get("applied") is not True:
                    current["error"] = current.get("error") or (
                        f"Node {node_name} per-run final OFF cleanup failed"
                    )
            if not run_started and current.get("error") is None:
                current["error"] = "run did not reach the BLE acquisition runner"
            if current.get("final_off_cleanup_error"):
                current["error"] = current.get("error") or str(
                    current["final_off_cleanup_error"]
                )
            attempt_path = run_dir / "scheduled_attempt.json"
            if attempt_path.is_file():
                attempt_path.write_text(
                    json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            run_results.append(current)
            prior_disconnect_ns = cast(
                int,
                current.get("disconnect_completed_monotonic_ns", time.monotonic_ns()),
            )
            cdc_failures = [
                f"Node {node.name}: {capture.error}"
                for node, capture in cdc_captures.items()
                if capture.error is not None
            ]
            cleanup_errors = current.get("disconnect_cleanup_errors", [])
            run_off_cleanup = current.get("final_off_cleanup", {})
            run_off_cleanup_failed = any(
                not isinstance(value, dict) or value.get("applied") is not True
                for value in run_off_cleanup.values()
            )
            unsafe_to_continue = bool(
                cdc_failures
                or cleanup_errors
                or control_gate_error
                or not run_started
                or current.get("runtime_disconnect_cleanup_valid") is False
                or current.get("off_control_gate_errors")
                or current.get("final_off_cleanup_error")
                or current.get("fresh_boot_gate_errors")
                or not isinstance(current.get("operator_reset_confirmation"), dict)
                or current.get("operator_reset_confirmation", {}).get(
                    "operator_asserted_both_boards_power_cycled"
                ) is not True
                or run_off_cleanup_failed
                or current.get("capture_finalization_errors")
            )
            if unsafe_to_continue:
                stop_reason = str(
                    current.get("error")
                    or "; ".join(cdc_failures)
                    or cleanup_errors
                    or "per-run reset, freshness, control, or capture-integrity gate failed"
                )
                control_events.write(
                    "formal_stopped_after_condition_failure",
                    run_index=run_index,
                    condition=condition,
                    detail=stop_reason,
                )
                break

    except asyncio.CancelledError as error:
        stop_reason = f"CancelledError: V8 acquisition cancelled ({error})"
        control_events.write("formal_acquisition_cancelled", detail=stop_reason)
    except Exception as error:
        stop_reason = f"{type(error).__name__}: {error}"
        control_events.write("formal_acquisition_failure", detail=stop_reason)
    finally:
        control_events.write(
            "formal_capture_finished",
            run_count=len(run_results),
            per_run_cdc_capture_count=sum(
                len(run.get("serial_capture_summary", {})) for run in run_results
            ),
        )
        control_events.close()
        first_run_controls = (
            run_results[0].get("off_control_acknowledgments", {}) if run_results else {}
        )
        last_cleanup = (
            run_results[-1].get("final_off_cleanup", {}) if run_results else {}
        )
        result: JSON = {
            "schema": "kineimu.m1.ble-link-count-formal-v8-result/1.0",
            "plan_sha256": FORMAL_PLAN_SHA256,
            "lock_head": config["git_head"],
            "run_order": list(order),
            "scheduled_count": len(order),
            "schedule_attempted_count": len(run_results),
            "all_scheduled_runs_attempted": len(run_results) == len(order),
            "initial_off_control": first_run_controls,
            "final_control_cleanup": last_cleanup,
            "per_run_off_control": [
                {
                    "run_index": run.get("run_index"),
                    "condition": run.get("condition"),
                    "acknowledgments": run.get("off_control_acknowledgments", {}),
                }
                for run in run_results
            ],
            "per_run_final_off_cleanup": [
                {
                    "run_index": run.get("run_index"),
                    "condition": run.get("condition"),
                    "cleanup": run.get("final_off_cleanup", {}),
                }
                for run in run_results
            ],
            "control_gate_error": next(
                (run.get("error") for run in run_results if run.get("error") is not None),
                None,
            ),
            "stop_reason": stop_reason,
            "run_results": run_results,
        }
        _write_json(root_dir / "matrix_result.json", result)
        manifest = precheck.write_sha256_manifest(root_dir)
        result["manifest_sha256"] = precheck.sha256(manifest).upper()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("acquire",))
    parser.add_argument("--root-dir", type=Path, default=FORMAL_OUTPUT_ROOT)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = asyncio.run(acquire_v8(args.root_dir))
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    all_runs_ok = all(run.get("error") is None for run in result["run_results"])
    all_per_run_off = all(
        isinstance(cleanup, dict)
        and cleanup
        and all(
            isinstance(value, dict) and value.get("applied") is True
            for value in cleanup.values()
        )
        for run in result["run_results"]
        for cleanup in [run.get("final_off_cleanup", {})]
    )
    return 0 if result["all_scheduled_runs_attempted"] and all_runs_ok and all_per_run_off else 2


if __name__ == "__main__":
    raise SystemExit(main())
