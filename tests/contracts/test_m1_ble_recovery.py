"""Regression contracts for BLE advertising and recovery boundaries."""

from __future__ import annotations

from pathlib import Path

from experiments.m1_transport_audit import _parse_cdc

FIRMWARE_SERVICE = Path(
    "firmware/xiao_nrf52840_sense/node_a_bringup/src/m1_ble_service.c"
)
FIRMWARE_WORK = Path(
    "firmware/xiao_nrf52840_sense/node_a_bringup/src/m1_ble_advertising.c"
)


def test_peripheral_restarts_advertising_from_a_work_item_on_link_loss() -> None:
    service_source = FIRMWARE_SERVICE.read_text(encoding="utf-8")
    work_source = FIRMWARE_WORK.read_text(encoding="utf-8")

    assert "k_work_schedule" in work_source
    assert "k_work_reschedule" in work_source
    assert "static void connected(" in service_source
    assert "static void disconnected(" in service_source
    assert service_source.count("request_advertising_restart") >= 3


def test_cdc_audit_parses_link_parameters_and_notify_timing(tmp_path: Path) -> None:
    cdc_log = tmp_path / "node-a.cdc.log"
    cdc_log.write_text(
        "Node A: BLE link event=connected info_rc=0 interval_us=7500 latency=0 "
        "supervision_timeout_us=4000000 phy_valid=1 phy_tx=1 phy_rx=1 "
        "dle_valid=1 dle_tx_max_len=251 dle_tx_max_time_us=2120 "
        "dle_rx_max_len=251 dle_rx_max_time_us=2120\n"
        "Node A: acquisition trace callback=1 prestart=0 timestamp_ok=1 timestamp_miss=0 "
        "raw_try=1 raw_ok=1 raw_fail=0 raw_rc=0 tx_queue_high_water=4 "
        "tx_enqueue_drops=0 tx_disconnect_drops=0 tx_stop_drops=0 notify_calls=1 "
        "notify_failures=0 notify_last_duration=17 notify_max_duration=17 "
        "notify_total_duration=17 saturated=0\n",
        encoding="utf-8",
    )

    parsed = _parse_cdc(cdc_log, "A")

    assert parsed["link_snapshot_count"] == 1
    assert parsed["link_snapshots"][0]["fields"]["interval_us"] == 7500
    assert parsed["link_snapshots"][0]["fields"]["dle_tx_max_len"] == 251
    assert parsed["maxima"]["notify_last_duration"] == 17
    assert parsed["maxima"]["notify_total_duration"] == 17
