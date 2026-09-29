"""Capture both identified XIAO USB packet streams for the M1 bench.

This uses the existing byte-preserving single-port recorder twice, concurrently.
Each acquisition has its own append-only raw stream and event sidecar. A new
output directory is required for every attempt, including an interrupted one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
APPLICATION_VID_PID = (0x2FE3, 0x0004)
HARDWARE_ID_RE = re.compile(rb"hardware_device_id=0x([0-9a-fA-F]{16})")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_ports(
    ports: Iterable[object], *, serial_a: str, serial_b: str
) -> dict[str, str]:
    """Bind current COM names to immutable bootloader USB serial numbers."""
    if not serial_a or not serial_b or serial_a == serial_b:
        raise ValueError("Node A and B require distinct nonempty USB serials")
    candidates = list(ports)
    result: dict[str, str] = {}
    for label, serial_number in (("A", serial_a), ("B", serial_b)):
        matches = [
            port for port in candidates
            if getattr(port, "serial_number", None) == serial_number
            and (getattr(port, "vid", None), getattr(port, "pid", None)) == APPLICATION_VID_PID
        ]
        if len(matches) != 1:
            raise ValueError(
                f"expected exactly one application CDC port for Node {label} "
                f"USB serial {serial_number}; found {len(matches)}"
            )
        result[label] = str(cast(Any, matches[0]).device)
    if result["A"] == result["B"]:
        raise ValueError("Node A and B resolved to the same CDC port")
    return result


def _capture_window(events_path: Path) -> tuple[int, int, int, int, bool]:
    start: dict[str, Any] | None = None
    stop: dict[str, Any] | None = None
    with events_path.open(encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("event") == "capture_start":
                start = event
            elif event.get("event") == "capture_stop":
                stop = event
    if start is None or stop is None:
        raise ValueError(f"missing capture start/stop in {events_path}")
    return (
        int(start["host_monotonic_ns"]),
        int(stop["host_monotonic_ns"]),
        int(stop["packet_count"]),
        int(stop["sample_count"]),
        bool(stop["qc_pass"]),
    )


def verify_identity_pilot(
    *, pilot_dir: Path, serials: dict[str, str], ports: dict[str, str],
    hardware_ids: dict[str, str], image_hashes: dict[str, str], source_commit: str,
) -> dict[str, str]:
    """Bind an already-running stream to an immutable, banner-verified pilot."""
    config_path = pilot_dir / "run_config.json"
    result_path = pilot_dir / "dual_usb_bench_result.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        assessment = result["assessment"]
        if result["provenance"] != config or not assessment["ready"]:
            raise ValueError("pilot result/config mismatch or failed assessment")
        if float(config["scheduled_seconds"]) < 15.0:
            raise ValueError("pilot was shorter than 15 seconds")
        if (config["serials"] != serials or config["ports"] != ports
                or config["hardware_ids"] != hardware_ids
                or config["firmware_source_commit"] != source_commit):
            raise ValueError("pilot identity or firmware source differs from current setup")
        for label in ("A", "B"):
            if config["firmware_images"][label]["sha256"] != image_hashes[label]:
                raise ValueError(f"pilot Node {label} image hash differs")
            node = assessment[f"node_{label.lower()}"]
            for kind in ("usb", "kimu", "events"):
                if not Path(node[f"{kind}_path"]).resolve().is_relative_to(
                    pilot_dir.resolve()
                ):
                    raise ValueError("pilot raw path escapes the pilot directory")
        checked = assess_pair(
            assessment["node_a"], assessment["node_b"],
            expected_a=hardware_ids["A"], expected_b=hardware_ids["B"],
            scheduled_seconds=float(config["scheduled_seconds"]),
        )
        if not checked["ready"]:
            raise ValueError(f"pilot raw verification failed: {checked['reasons']}")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"identity pilot invalid: {error}") from error
    return {
        "pilot_dir": str(pilot_dir.resolve()),
        "pilot_config_sha256": _sha256(config_path),
        "pilot_result_sha256": _sha256(result_path),
    }


def assess_pair(
    a: dict[str, object], b: dict[str, object], *,
    expected_a: str, expected_b: str, scheduled_seconds: float,
    prior_identity_verified: bool = False,
) -> dict[str, object]:
    """Read only the two capture results and reject identity/integrity gaps."""
    reasons: list[str] = []
    windows: dict[str, tuple[int, int]] = {}
    for label, summary, expected in (("A", a, expected_a), ("B", b, expected_b)):
        required_kinds = ("usb", "kimu", "events", "preroll") if prior_identity_verified else (
            "usb", "kimu", "events"
        )
        for kind in required_kinds:
            if f"{kind}_path" not in summary or f"{kind}_sha256" not in summary:
                reasons.append(f"Node {label} {kind} evidence missing")
                continue
            path = Path(str(summary[f"{kind}_path"]))
            if not path.is_file() or _sha256(path) != summary[f"{kind}_sha256"]:
                reasons.append(f"Node {label} {kind} hash mismatch or missing file")
        usb_path = Path(str(summary["usb_path"]))
        if usb_path.is_file() and not prior_identity_verified:
            with usb_path.open("rb") as stream:
                banner = stream.read(2048)
            match = HARDWARE_ID_RE.search(banner)
            if match is None or match.group(1).decode("ascii").lower() != expected.lower():
                reasons.append(f"Node {label} hardware ID banner mismatch or missing")
        if not summary.get("qc_pass") or not summary.get("stream_complete"):
            reasons.append(f"Node {label} capture QC or stream completeness failed")
        if int(str(summary.get("packets", 0))) == 0 or int(str(summary.get("samples", 0))) == 0:
            reasons.append(f"Node {label} has no packet/sample evidence")
        events_path = Path(str(summary["events_path"]))
        if events_path.is_file():
            try:
                start, stop, packets, samples, qc_pass = _capture_window(events_path)
                windows[label] = (start, stop)
                if (packets, samples, qc_pass) != (
                    int(str(summary["packets"])), int(str(summary["samples"])), True
                ):
                    reasons.append(f"Node {label} event summary disagrees with capture result")
                if stop - start < int((scheduled_seconds - 0.1) * 1e9):
                    reasons.append(f"Node {label} capture duration is short")
            except (ValueError, KeyError, json.JSONDecodeError) as error:
                reasons.append(f"Node {label} event window invalid: {error}")
    overlap_fraction = 0.0
    if len(windows) == 2:
        overlap_ns = max(
            0, min(windows["A"][1], windows["B"][1])
            - max(windows["A"][0], windows["B"][0])
        )
        overlap_fraction = min(1.0, overlap_ns / (scheduled_seconds * 1e9))
        if overlap_fraction < 0.995:
            reasons.append("usable dual-node capture overlap below 99.5%")
    else:
        reasons.append("both capture windows are required")
    return {
        "ready": not reasons,
        "reasons": reasons,
        "identity_mode": "verified_prior_pilot" if prior_identity_verified else "live_banner",
        "overlap_fraction": overlap_fraction,
        "windows_monotonic_ns": windows,
        "node_a": a,
        "node_b": b,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--seconds", required=True, type=float)
    parser.add_argument("--serial-a", default="0000000000000001")
    parser.add_argument("--serial-b", default="0000000000000002")
    parser.add_argument("--hardware-id-a", default="0000000000000001")
    parser.add_argument("--hardware-id-b", default="0000000000000002")
    parser.add_argument("--firmware-a", required=True, type=Path)
    parser.add_argument("--firmware-b", required=True, type=Path)
    parser.add_argument("--firmware-source-commit", required=True)
    parser.add_argument(
        "--identity-pilot-dir", type=Path,
        help="use a verified same-board pilot when firmware is already streaming",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.seconds <= 0:
        raise ValueError("capture duration must be positive")
    for image in (args.firmware_a, args.firmware_b):
        if not image.is_file():
            raise FileNotFoundError(image)
    from serial.tools import list_ports  # type: ignore[import-untyped]

    ports = resolve_ports(list_ports.comports(), serial_a=args.serial_a, serial_b=args.serial_b)
    output = args.output_dir.resolve()
    image_hashes = {"A": _sha256(args.firmware_a), "B": _sha256(args.firmware_b)}
    serials = {"A": args.serial_a, "B": args.serial_b}
    hardware_ids = {"A": args.hardware_id_a, "B": args.hardware_id_b}
    pilot_evidence = (
        verify_identity_pilot(
            pilot_dir=args.identity_pilot_dir, serials=serials, ports=ports,
            hardware_ids=hardware_ids, image_hashes=image_hashes,
            source_commit=args.firmware_source_commit,
        )
        if args.identity_pilot_dir is not None else None
    )
    output.mkdir(parents=True, exist_ok=False)
    raw_dir = output / "raw"
    raw_dir.mkdir()
    provenance = {
        "schema": "kineimu.m1.usb-dual-bench/1",
        "session_id": args.session_id,
        "scheduled_seconds": args.seconds,
        "started_utc": datetime.now(UTC).isoformat(),
        "firmware_source_commit": args.firmware_source_commit,
        "firmware_images": {
            "A": {"path": str(args.firmware_a.resolve()), "sha256": image_hashes["A"]},
            "B": {"path": str(args.firmware_b.resolve()), "sha256": image_hashes["B"]},
        },
        "serials": serials,
        "ports": ports,
        "hardware_ids": hardware_ids,
        "identity_mode": "verified_prior_pilot" if pilot_evidence else "live_banner",
        "identity_pilot": pilot_evidence,
        "host_source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
    }
    (output / "run_config.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    processes: dict[str, subprocess.Popen[str]] = {}
    for label, node_id in (("A", 1), ("B", 2)):
        command = [
            sys.executable, str(REPO_ROOT / "scripts" / "capture_m1_usb.py"),
            "--port", ports[label], "--output-prefix", str(raw_dir / f"node-{label.lower()}"),
            "--seconds", str(args.seconds), "--node-id", str(node_id),
            "--finish-complete-packet",
        ]
        if pilot_evidence is not None:
            command.append("--synchronize-running-stream")
        processes[label] = subprocess.Popen(
            command, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
    interrupted = False
    while any(process.poll() is None for process in processes.values()):
        if any(process.poll() not in (None, 0) for process in processes.values()):
            interrupted = True
            for process in processes.values():
                if process.poll() is None:
                    process.terminate()
            break
        time.sleep(0.1)
    outputs: dict[str, dict[str, object]] = {}
    summaries: dict[str, dict[str, object]] = {}
    for label, process in processes.items():
        stdout, stderr = process.communicate()
        outputs[label] = {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr}
        try:
            summaries[label] = json.loads(stdout.strip().splitlines()[-1])
        except (IndexError, ValueError, TypeError):
            pass
    result: dict[str, object] = {"provenance": provenance, "processes": outputs}
    assessment: dict[str, object]
    if not interrupted and all(item["exit_code"] == 0 for item in outputs.values()) and len(summaries) == 2:
        assessment = assess_pair(
            summaries["A"], summaries["B"], expected_a=args.hardware_id_a,
            expected_b=args.hardware_id_b, scheduled_seconds=args.seconds,
            prior_identity_verified=pilot_evidence is not None,
        )
    else:
        assessment = {"ready": False, "reasons": ["capture process failed or produced no summary"]}
    result["assessment"] = assessment
    result["ended_utc"] = datetime.now(UTC).isoformat()
    (output / "dual_usb_bench_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(assessment, sort_keys=True))
    return 0 if assessment["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
