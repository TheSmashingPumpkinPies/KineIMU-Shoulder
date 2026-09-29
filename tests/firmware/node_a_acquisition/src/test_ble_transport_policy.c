/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>

#include <zephyr/ztest.h>

#include "m1_ble_transport_policy.h"

ZTEST(node_a_ble_transport_policy, test_accepts_required_mtu)
{
	zassert_ok(node_a_ble_transport_validate_att_mtu(127U), NULL);
}

ZTEST(node_a_ble_transport_policy, test_rejects_mtu_below_v1_requirement)
{
	zassert_equal(node_a_ble_transport_validate_att_mtu(126U), -EMSGSIZE,
		      NULL);
}

ZTEST(node_a_ble_transport_policy, test_allows_maximum_packet_at_required_mtu)
{
	const struct node_a_ble_link_state state = {
		.connected = true,
		.telemetry_notifications_enabled = true,
		.att_mtu = 127U,
	};

	zassert_true(node_a_ble_transport_can_notify(&state, 124U), NULL);
}

ZTEST(node_a_ble_transport_policy, test_rejects_payload_larger_than_mtu)
{
	const struct node_a_ble_link_state state = {
		.connected = true,
		.telemetry_notifications_enabled = true,
		.att_mtu = 127U,
	};

	zassert_false(node_a_ble_transport_can_notify(&state, 125U), NULL);
}

ZTEST(node_a_ble_transport_policy, test_rejects_unready_link)
{
	const struct node_a_ble_link_state disconnected = {
		.connected = false,
		.telemetry_notifications_enabled = true,
		.att_mtu = 127U,
	};
	const struct node_a_ble_link_state unsubscribed = {
		.connected = true,
		.telemetry_notifications_enabled = false,
		.att_mtu = 127U,
	};
	const struct node_a_ble_link_state small_mtu = {
		.connected = true,
		.telemetry_notifications_enabled = true,
		.att_mtu = 126U,
	};

	zassert_false(node_a_ble_transport_can_notify(&disconnected, 124U), NULL);
	zassert_false(node_a_ble_transport_can_notify(&unsubscribed, 124U), NULL);
	zassert_false(node_a_ble_transport_can_notify(&small_mtu, 124U), NULL);
}

ZTEST(node_a_ble_transport_policy, test_rejects_empty_payload)
{
	const struct node_a_ble_link_state state = {
		.connected = true,
		.telemetry_notifications_enabled = true,
		.att_mtu = 127U,
	};

	zassert_false(node_a_ble_transport_can_notify(&state, 0U), NULL);
}

ZTEST_SUITE(node_a_ble_transport_policy, NULL, NULL, NULL, NULL, NULL);
