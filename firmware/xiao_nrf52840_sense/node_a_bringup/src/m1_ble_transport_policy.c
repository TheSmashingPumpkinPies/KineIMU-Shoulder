/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>

#include "m1_ble_transport_policy.h"

int node_a_ble_transport_validate_att_mtu(uint16_t att_mtu)
{
	return (att_mtu < NODE_A_BLE_REQUIRED_ATT_MTU) ? -EMSGSIZE : 0;
}

bool node_a_ble_transport_can_notify(
	const struct node_a_ble_link_state *state, size_t payload_size)
{
	if ((state == NULL) || !state->connected ||
	    !state->telemetry_notifications_enabled ||
	    (node_a_ble_transport_validate_att_mtu(state->att_mtu) < 0)) {
		return false;
	}
	if ((payload_size < NODE_A_BLE_MIN_PACKET_SIZE) ||
	    (payload_size > NODE_A_BLE_MAX_PACKET_SIZE)) {
		return false;
	}

	return payload_size <=
		(size_t)(state->att_mtu - NODE_A_BLE_ATT_VALUE_OVERHEAD);
}
