"""Capture two explicitly assigned KineIMU Shoulder nodes over BLE."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from kineimu_shoulder.io.m1_ble import (
    DEFAULT_CONNECTION_TIMEOUT_S,
    DEFAULT_RECOVERY_TIMEOUT_S,
    M1BleError,
    M1BleSessionRecorder,
    NodeTarget,
    discover_m1_devices,
)
from kineimu_shoulder.io.m1_packet import NodeId


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--node-a-address",
        help="BLE address/identifier explicitly assigned to Node A (thorax)",
    )
    parser.add_argument(
        "--node-b-address",
        help="BLE address/identifier explicitly assigned to Node B (upper arm)",
    )
    parser.add_argument(
        "--expected-node-a-device-id",
        type=_parse_uint64,
        help="optional known Node A nRF52840 hardware ID, decimal or 0x-prefixed",
    )
    parser.add_argument(
        "--expected-node-b-device-id",
        type=_parse_uint64,
        help="optional known Node B nRF52840 hardware ID, decimal or 0x-prefixed",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="session output directory; raw/ and session.json are created below it",
    )
    parser.add_argument(
        "--session-id",
        default=_default_session_id(),
        help="session identifier written to session.json",
    )
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--clock-exchanges", type=int, default=3)
    parser.add_argument("--clock-timeout", type=float, default=2.0)
    parser.add_argument(
        "--connection-timeout",
        type=float,
        default=DEFAULT_CONNECTION_TIMEOUT_S,
        help="maximum seconds for each individual BLE connection establishment",
    )
    parser.add_argument(
        "--recovery-timeout",
        type=float,
        default=DEFAULT_RECOVERY_TIMEOUT_S,
        help="independent seconds allowed to recover after a disconnect",
    )
    parser.add_argument("--reconnect-delay", type=float, default=0.25)
    parser.add_argument("--test-side", choices=("left", "right"))
    parser.add_argument("--mounting-protocol-version")
    parser.add_argument("--notes")
    parser.add_argument(
        "--scan",
        action="store_true",
        help="list M1 service candidates and exit; discovery order never assigns A/B",
    )
    parser.add_argument("--discovery-timeout", type=float, default=5.0)
    return parser


def targets_from_args(args: argparse.Namespace) -> tuple[NodeTarget, NodeTarget]:
    """Build explicit A/B assignments; never derive roles from scan order or names."""

    if not args.node_a_address or not args.node_b_address:
        raise ValueError("--node-a-address and --node-b-address are required unless --scan is used")
    return (
        NodeTarget(
            node_id=NodeId.A,
            address=args.node_a_address,
            expected_hardware_device_id=args.expected_node_a_device_id,
        ),
        NodeTarget(
            node_id=NodeId.B,
            address=args.node_b_address,
            expected_hardware_device_id=args.expected_node_b_device_id,
        ),
    )


async def _scan(args: argparse.Namespace) -> int:
    devices = await discover_m1_devices(timeout_s=args.discovery_timeout)
    print(
        json.dumps(
            [
                {"address": device.address, "name": device.name, "rssi": device.rssi}
                for device in devices
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


async def _capture(args: argparse.Namespace) -> int:
    if args.output_dir is None:
        raise ValueError("--output-dir is required for capture")
    recorder = M1BleSessionRecorder(
        targets=targets_from_args(args),
        output_dir=args.output_dir,
        session_id=args.session_id,
        clock_exchange_count=args.clock_exchanges,
        clock_response_timeout_s=args.clock_timeout,
        connection_timeout_s=args.connection_timeout,
        recovery_timeout_s=args.recovery_timeout,
        reconnect_delay_s=args.reconnect_delay,
        test_side=args.test_side,
        mounting_protocol_version=args.mounting_protocol_version,
        notes=args.notes,
    )
    result = await recorder.capture(duration_s=args.seconds)
    print(
        json.dumps(
            {
                "manifest_path": str(result.manifest_path),
                "session_id": result.session_id,
                "nodes": {
                    node_id.name: {
                        "raw_path": str(node_result.raw_path),
                        "events_path": str(node_result.events_path),
                        "packets": node_result.packet_count,
                        "samples": node_result.sample_count,
                        "qc_pass": node_result.qc_pass,
                    }
                    for node_id, node_result in result.node_results.items()
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        return asyncio.run(_scan(args) if args.scan else _capture(args))
    except (M1BleError, OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


def _parse_uint64(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid uint64 value: {value}") from error
    if not 0 < parsed < 1 << 64:
        raise argparse.ArgumentTypeError(f"uint64 value must be positive and fit 64 bits: {value}")
    return parsed


def _default_session_id() -> str:
    return datetime.now(UTC).strftime("m1-ble-%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
