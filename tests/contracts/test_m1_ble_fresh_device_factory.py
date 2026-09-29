"""Contracts for the experiment runner's fresh-device Bleak boundary."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from kineimu_shoulder.io import m1_ble


def test_m1_scan_returns_the_exact_fresh_ble_device_for_the_requested_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = type("Device", (), {"address": "A-address", "name": "Node A"})()
    second = type("Device", (), {"address": "B-address", "name": "Node B"})()
    advertisement = object()

    class Scanner:
        @staticmethod
        async def discover(**kwargs: object) -> dict[str, tuple[object, object]]:
            assert kwargs == {
                "timeout": 1.0,
                "service_uuids": [m1_ble.M1_SERVICE_UUID],
                "return_adv": True,
            }
            return {
                "A-address": (first, advertisement),
                "B-address": (second, advertisement),
            }

    monkeypatch.setattr(
        m1_ble, "_load_bleak", lambda: type("Bleak", (), {"BleakScanner": Scanner})
    )

    observed = asyncio.run(
        m1_ble.discover_m1_ble_device("a-address", timeout_s=1.0)
    )

    assert observed is first


def test_m1_scan_watchdog_allows_bleak_scan_cleanup_after_scan_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device = type("Device", (), {"address": "A-address", "name": "Node A"})()

    class Scanner:
        @staticmethod
        async def discover(**kwargs: object) -> dict[str, tuple[object, object]]:
            timeout = float(kwargs["timeout"])
            assert kwargs["service_uuids"] == [m1_ble.M1_SERVICE_UUID]
            await asyncio.sleep(timeout + 0.02)
            return {"A-address": (device, object())}

    monkeypatch.setattr(
        m1_ble, "_load_bleak", lambda: type("Bleak", (), {"BleakScanner": Scanner})
    )

    observed = asyncio.run(
        m1_ble.discover_m1_ble_device("A-address", timeout_s=0.02)
    )

    assert observed is device


def test_bleak_factory_forwards_ble_device_service_filter_and_phase_timings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device = object()
    captured: dict[str, object] = {}

    class Backend:
        async def _get_services(self) -> str:
            return "services"

    Backend.__module__ = "bleak.backends.winrt.client"

    class BleakClient:
        def __init__(
            self,
            observed_device: object,
            *,
            disconnected_callback: Callable[[object], None],
            services: list[str],
        ) -> None:
            captured["device"] = observed_device
            captured["services"] = services
            captured["callback"] = disconnected_callback
            self._backend = Backend()
            self.is_connected = False
            self.mtu_size = 127

        async def connect(self) -> None:
            await self._backend._get_services()
            self.is_connected = True

    monkeypatch.setattr(
        m1_ble,
        "_load_bleak",
        lambda: type("Bleak", (), {"BleakClient": BleakClient}),
    )
    timings: list[dict[str, object]] = []
    client = m1_ble.create_bleak_client(
        device,
        lambda _client: None,
        services=[m1_ble.M1_SERVICE_UUID],
        operation_timing_sink=lambda event, **details: timings.append(
            {"event": event, **details}
        ),
    )

    asyncio.run(client.connect())

    assert captured["device"] is device
    assert captured["services"] == [m1_ble.M1_SERVICE_UUID]
    service_event = next(
        row for row in timings if row["event"] == "ble_gatt_service_discovery"
    )
    connect_event = next(row for row in timings if row["event"] == "ble_connect_total")
    assert int(service_event["duration_ns"]) >= 0
    assert int(service_event["setup_elapsed_ns_before_gatt"]) >= 0
    assert int(connect_event["duration_ns"]) >= int(service_event["duration_ns"])


def test_cancelled_winrt_connect_records_a_failed_connect_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Backend:
        async def _get_services(self) -> str:
            return "services"

    Backend.__module__ = "bleak.backends.winrt.client"

    class BleakClient:
        def __init__(self, _device: object, **_kwargs: object) -> None:
            self._backend = Backend()

        async def connect(self) -> None:
            await asyncio.Event().wait()

    monkeypatch.setattr(
        m1_ble, "_load_bleak", lambda: type("Bleak", (), {"BleakClient": BleakClient})
    )

    async def scenario() -> list[dict[str, object]]:
        timings: list[dict[str, object]] = []
        client = m1_ble.create_bleak_client(
            object(),
            lambda _client: None,
            services=[m1_ble.M1_SERVICE_UUID],
            operation_timing_sink=lambda event, **details: timings.append(
                {"event": event, **details}
            ),
        )
        task = asyncio.create_task(client.connect())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return timings

    timings = asyncio.run(scenario())

    connect_event = next(row for row in timings if row["event"] == "ble_connect_total")
    assert connect_event["succeeded"] is False
    assert connect_event["error"] == "CancelledError: connect was cancelled"
