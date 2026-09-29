/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_M1_BLE_TRANSPORT_POLICY_H_
#define KINEIMU_NODE_A_M1_BLE_TRANSPORT_POLICY_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define NODE_A_BLE_REQUIRED_ATT_MTU 127U
#define NODE_A_BLE_ATT_VALUE_OVERHEAD 3U
#define NODE_A_BLE_MIN_PACKET_SIZE 46U
#define NODE_A_BLE_MAX_PACKET_SIZE 124U

struct node_a_ble_link_state {
	bool connected;
	bool telemetry_notifications_enabled;
	uint16_t att_mtu;
};

int node_a_ble_transport_validate_att_mtu(uint16_t att_mtu);

bool node_a_ble_transport_can_notify(
	const struct node_a_ble_link_state *state, size_t payload_size);

#endif /* KINEIMU_NODE_A_M1_BLE_TRANSPORT_POLICY_H_ */
