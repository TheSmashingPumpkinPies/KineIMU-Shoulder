"""End-to-end fail-closed checks for the matrix's initial CDC gate."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import pytest

import experiments.m1_ble_link_matrix as matrix_runner
from kineimu_shoulder.io.m1_ble import NodeId


class _Capture:
    def __init__(self, node: NodeId, ready_ok: bool, ack_ok: bool) -> None:
        self.node = node
        self.ready_ok = ready_ok
        self.ack_ok = ack_ok
        self.error: str | None = None
        self.ready = threading.Event()
        self.done = threading.Event()
        self.mode_calls: list[str] = []

    def start(self) -> None:
        self.ready.set()

    def begin_control_session(self, timeout_s: float) -> dict[str, object]:
        return {
            "node_id": int(self.node),
            "session": f"000000000000000{int(self.node)}",
            "ready": self.ready_ok,
            "error": None if self.ready_ok else "READY timeout",
        }

    def set_mode(self, mode: str, *, timeout_s: float = 5.0) -> dict[str, object]:
        self.mode_calls.append(mode)
        return {
            "node_id": int(self.node),
            "requested": mode,
            "selected": mode if self.ack_ok else None,
            "acknowledged": self.ack_ok,
            "applied": self.ack_ok,
            "error": None if self.ack_ok else "ACK timeout",
        }

    def stop(self) -> None:
        self.done.set()

    def join(self) -> None:
        return None

    def finalize_text_log(self) -> None:
        return None

    def metadata(self) -> dict[str, object]:
        return {"node": self.node.name, "error": self.error}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_locked_plan_hashes_are_bound_to_their_exact_output_roots() -> None:
    old_plan_path = Path(matrix_runner.__file__).with_name(
        "M1_COMPLETION_TX_ROOT_CAUSE_PLAN.md"
    )
    v2_plan_path = Path(matrix_runner.__file__).with_name(
        "M1_CONN_PARAM_ROOT_CAUSE_PLAN_V2_20260923.md"
    )

    assert _sha256(old_plan_path) == matrix_runner.ROOT_CAUSE_PLAN_SHA256
    assert _sha256(v2_plan_path) == matrix_runner.ROOT_CAUSE_PLAN_V2_SHA256
    assert matrix_runner._validate_plan_output_root(
        matrix_runner.ROOT_CAUSE_PLAN_SHA256, matrix_runner.ROOT_CAUSE_OUTPUT_ROOT
    ) == matrix_runner.ROOT_CAUSE_OUTPUT_ROOT.resolve()
    assert matrix_runner._validate_plan_output_root(
        matrix_runner.ROOT_CAUSE_PLAN_V2_SHA256,
        matrix_runner.ROOT_CAUSE_OUTPUT_ROOT_V2,
    ) == matrix_runner.ROOT_CAUSE_OUTPUT_ROOT_V2.resolve()

    with pytest.raises(ValueError, match="locked output root"):
        matrix_runner._validate_plan_output_root(
            matrix_runner.ROOT_CAUSE_PLAN_SHA256,
            matrix_runner.ROOT_CAUSE_OUTPUT_ROOT_V2,
        )
    with pytest.raises(ValueError, match="locked output root"):
        matrix_runner._validate_plan_output_root(
            matrix_runner.ROOT_CAUSE_PLAN_V2_SHA256,
            matrix_runner.ROOT_CAUSE_OUTPUT_ROOT,
        )
    with pytest.raises(ValueError, match="unknown locked plan SHA-256"):
        matrix_runner._validate_plan_output_root("0" * 64, Path("<external-data>/unknown"))


@pytest.mark.parametrize(
    ("plan_name", "root_dir"),
    [
        ("M1_COMPLETION_TX_ROOT_CAUSE_PLAN.md", matrix_runner.ROOT_CAUSE_OUTPUT_ROOT_V2),
        ("M1_CONN_PARAM_ROOT_CAUSE_PLAN_V2_20260923.md", matrix_runner.ROOT_CAUSE_OUTPUT_ROOT),
    ],
)
def test_full_matrix_rejects_cross_bound_plan_and_root_before_start(
    plan_name: str, root_dir: Path
) -> None:
    def snapshot(root: Path) -> tuple[bool, dict[str, tuple[int, int]]]:
        if not root.exists():
            return False, {}
        files = {
            path.relative_to(root).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
            for path in root.rglob("*")
            if path.is_file()
        }
        return True, files

    locked_roots = (
        matrix_runner.ROOT_CAUSE_OUTPUT_ROOT,
        matrix_runner.ROOT_CAUSE_OUTPUT_ROOT_V2,
    )
    before = {root: snapshot(root) for root in locked_roots}
    args = argparse.Namespace(
        plan_path=Path(matrix_runner.__file__).with_name(plan_name), root_dir=root_dir
    )

    with pytest.raises(ValueError, match="locked output root"):
        asyncio.run(matrix_runner._run_matrix(args))

    assert {root: snapshot(root) for root in locked_roots} == before


@pytest.mark.parametrize("failure_kind", ["ready", "ack"])
@pytest.mark.parametrize("plan_profile", ["legacy", "v2"])
def test_full_matrix_stops_before_any_run_or_ble_client_on_cdc_gate_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
    plan_profile: str,
) -> None:
    root_dir = tmp_path / "new-matrix-root"
    plan_path = tmp_path / "plan-v2.md"
    plan_path.write_text("immutable v2 test plan\n", encoding="utf-8")
    plan_sha256 = _sha256(plan_path)
    image_a = tmp_path / "node-a.uf2"
    image_b = tmp_path / "node-b.uf2"
    image_a.write_bytes(b"node A test UF2")
    image_b.write_bytes(b"node B test UF2")
    config_a = tmp_path / "node-a.config"
    config_b = tmp_path / "node-b.config"
    config_a.write_bytes(b"matched common configuration\n")
    config_b.write_bytes(config_a.read_bytes())
    source_commit = "f" * 40
    preflash_path = tmp_path / "preflash.json"
    preflash_path.write_text(
        json.dumps(
            {
                "plan_sha256": plan_sha256,
                "firmware_source_commit": source_commit,
                "build_configurations_identical": True,
                "build_configs": {
                    "A": {"path": str(config_a), "sha256": _sha256(config_a)},
                    "B": {"path": str(config_b), "sha256": _sha256(config_b)},
                },
                "firmware_images": {
                    "A": {
                        "sha256": _sha256(image_a),
                        "node_id": 1,
                        "source_commit": source_commit,
                    },
                    "B": {
                        "sha256": _sha256(image_b),
                        "node_id": 2,
                        "source_commit": source_commit,
                    },
                },
                "boards": {
                    "A": {
                        "bootloader_usb_serial": matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[NodeId.A],
                        "board_id": "Seeed_XIAO_nRF52840_Sense",
                    },
                    "B": {
                        "bootloader_usb_serial": matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[NodeId.B],
                        "board_id": "Seeed_XIAO_nRF52840_Sense",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    if plan_profile == "legacy":
        monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_OUTPUT_ROOT", root_dir)
        monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_PLAN_SHA256", plan_sha256)
    else:
        monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_OUTPUT_ROOT_V2", root_dir)
        monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_PLAN_V2_SHA256", plan_sha256)
    monkeypatch.setattr(
        matrix_runner,
        "_validate_firmware_source_commit",
        lambda _repo_root, commit: commit,
    )
    monkeypatch.setattr(
        matrix_runner,
        "resolve_cdc_port_by_serial",
        lambda serial: {"device": f"COM-{serial[-4:]}", "serial_number": serial},
    )

    captures: dict[NodeId, _Capture] = {}

    class FakeCdcCapture(_Capture):
        def __init__(self, **kwargs: Any) -> None:
            node = kwargs["node"]
            ready_ok = failure_kind != "ready"
            ack_ok = failure_kind != "ack"
            super().__init__(node, ready_ok, ack_ok)
            captures[node] = self

    ble_factory_calls: list[object] = []
    monkeypatch.setattr(matrix_runner, "_MatrixCdcCapture", FakeCdcCapture)
    monkeypatch.setattr(
        matrix_runner,
        "create_bleak_client",
        lambda *args, **kwargs: ble_factory_calls.append(args),
    )
    args = argparse.Namespace(
        root_dir=root_dir,
        blocks=len(matrix_runner.ROOT_CAUSE_BLOCK_SCHEDULE),
        seconds=matrix_runner.ROOT_CAUSE_CAPTURE_S,
        inter_run_rest_s=matrix_runner.ROOT_CAUSE_INTER_RUN_REST_S,
        connection_settle_s=matrix_runner.ROOT_CAUSE_SETUP_SETTLE_S,
        completion_driven_tx=True,
        firmware_source_commit=source_commit,
        plan_path=plan_path,
        firmware_node_a_image=image_a,
        firmware_node_b_image=image_b,
        preflash_record_path=preflash_path,
        node_a_address="A-address",
        node_b_address="B-address",
        expected_node_a_device_id=0xA,
        expected_node_b_device_id=0xB,
    )

    result = asyncio.run(matrix_runner._run_matrix(args))

    assert result["schedule_attempted_count"] == 0
    assert result["all_scheduled_runs_attempted"] is False
    assert failure_kind.upper() in str(result["stop_reason"]).upper()
    assert result["control_gate_error"] == result["stop_reason"]
    assert ble_factory_calls == []
    assert not list(root_dir.glob("run-*"))
    assert (root_dir / "matrix_result.json").is_file()
    assert captures[NodeId.A].mode_calls == ([] if failure_kind == "ready" else ["OFF"] * 3)
    assert captures[NodeId.B].mode_calls == ([] if failure_kind == "ready" else ["OFF"] * 2)


@pytest.mark.parametrize(
    ("cleanup_errors", "control_failure", "expected_attempted_count"),
    [
        ([], False, 16),
        (["peripheral disconnect was not confirmed"], False, 1),
        ([], True, 1),
    ],
)
def test_matrix_attempts_later_predeclared_runs_after_capture_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_errors: list[str],
    control_failure: bool,
    expected_attempted_count: int,
) -> None:
    root_dir = tmp_path / "matrix-root"
    plan_path = tmp_path / "plan-v2.md"
    plan_path.write_text("fixed v2 plan\n", encoding="utf-8")
    plan_sha256 = _sha256(plan_path)
    image_a = tmp_path / "node-a.uf2"
    image_b = tmp_path / "node-b.uf2"
    image_a.write_bytes(b"node A image")
    image_b.write_bytes(b"node B image")
    config_a = tmp_path / "node-a.config"
    config_b = tmp_path / "node-b.config"
    config_a.write_bytes(b"matched configuration\n")
    config_b.write_bytes(config_a.read_bytes())
    source_commit = "a" * 40
    preflash_path = tmp_path / "preflash.json"
    preflash_path.write_text(
        json.dumps(
            {
                "plan_sha256": plan_sha256,
                "firmware_source_commit": source_commit,
                "build_configurations_identical": True,
                "build_configs": {
                    "A": {"path": str(config_a), "sha256": _sha256(config_a)},
                    "B": {"path": str(config_b), "sha256": _sha256(config_b)},
                },
                "firmware_images": {
                    "A": {"sha256": _sha256(image_a), "node_id": 1, "source_commit": source_commit},
                    "B": {"sha256": _sha256(image_b), "node_id": 2, "source_commit": source_commit},
                },
                "boards": {
                    node.name: {
                        "bootloader_usb_serial": matrix_runner.ROOT_CAUSE_NODE_USB_SERIALS[node],
                        "board_id": "Seeed_XIAO_nRF52840_Sense",
                    }
                    for node in (NodeId.A, NodeId.B)
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_OUTPUT_ROOT", root_dir)
    monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_PLAN_SHA256", plan_sha256)
    monkeypatch.setattr(matrix_runner, "ROOT_CAUSE_INTER_RUN_REST_S", 0.0)
    monkeypatch.setattr(
        matrix_runner,
        "_validate_firmware_source_commit",
        lambda _repo_root, commit: commit,
    )
    monkeypatch.setattr(
        matrix_runner,
        "resolve_cdc_port_by_serial",
        lambda serial: {"device": f"COM-{serial[-4:]}", "serial_number": serial},
    )

    captures: dict[NodeId, _Capture] = {}

    class FakeCdcCapture(_Capture):
        def __init__(self, **kwargs: Any) -> None:
            node = kwargs["node"]
            super().__init__(node, ready_ok=True, ack_ok=True)
            self.port_info = kwargs["port_info"]
            captures[node] = self

    monkeypatch.setattr(matrix_runner, "_MatrixCdcCapture", FakeCdcCapture)
    monkeypatch.setattr(
        matrix_runner,
        "_cut_cdc_captures",
        lambda _captures: asyncio.sleep(0, result={NodeId.A: 0, NodeId.B: 0}),
    )
    monkeypatch.setattr(
        matrix_runner,
        "_initial_control_handshake",
        lambda *_args, **_kwargs: asyncio.sleep(
            0,
            result={
                "A": {"applied": True, "acknowledged": True},
                "B": {"applied": True, "acknowledged": True},
            },
        ),
    )

    attempted: list[str] = []

    async def fake_run_condition(**kwargs: Any) -> dict[str, object]:
        attempted.append(str(kwargs["condition"]))
        run_index = int(kwargs["run_index"])
        now_ns = matrix_runner.time.monotonic_ns()
        return {
            "run_index": run_index,
            "block_index": (run_index - 1) // 4 + 1,
            "block_run_index": (run_index - 1) % 4 + 1,
            "request_mode": kwargs["request_mode"],
            "condition": kwargs["condition"],
            "started_monotonic_ns": now_ns,
            "disconnect_completed_monotonic_ns": now_ns,
            "disconnect_cleanup_errors": cleanup_errors if run_index == 1 else [],
            "control_gate_failure": control_failure if run_index == 1 else False,
            "error": "synthetic BLE acquisition failure" if run_index == 1 else None,
        }

    async def fake_run_condition_with_control(
        *, run_condition: Any, run_kwargs: dict[str, object], **_kwargs: Any
    ) -> dict[str, object]:
        return await run_condition(**run_kwargs)

    monkeypatch.setattr(matrix_runner, "_run_condition", fake_run_condition)
    monkeypatch.setattr(
        matrix_runner, "_run_condition_with_control", fake_run_condition_with_control
    )
    args = argparse.Namespace(
        root_dir=root_dir,
        blocks=len(matrix_runner.ROOT_CAUSE_BLOCK_SCHEDULE),
        seconds=matrix_runner.ROOT_CAUSE_CAPTURE_S,
        inter_run_rest_s=0.0,
        connection_settle_s=matrix_runner.ROOT_CAUSE_SETUP_SETTLE_S,
        completion_driven_tx=True,
        firmware_source_commit=source_commit,
        plan_path=plan_path,
        firmware_node_a_image=image_a,
        firmware_node_b_image=image_b,
        preflash_record_path=preflash_path,
        node_a_address="A-address",
        node_b_address="B-address",
        expected_node_a_device_id=0xA,
        expected_node_b_device_id=0xB,
    )

    result = asyncio.run(matrix_runner._run_matrix(args))

    assert attempted == list(matrix_runner.matrix_order(4))[:expected_attempted_count]
    assert result["schedule_attempted_count"] == expected_attempted_count
    assert result["all_scheduled_runs_attempted"] is (expected_attempted_count == 16)
    run_results = result["run_results"]
    assert isinstance(run_results, list)
    assert run_results[0]["error"] == "synthetic BLE acquisition failure"
    if expected_attempted_count == 16:
        assert result["stop_reason"] is None
        assert result["control_gate_error"] is None
    else:
        assert result["stop_reason"] == "synthetic BLE acquisition failure"
        assert result["control_gate_error"] == (
            "synthetic BLE acquisition failure" if control_failure else None
        )
