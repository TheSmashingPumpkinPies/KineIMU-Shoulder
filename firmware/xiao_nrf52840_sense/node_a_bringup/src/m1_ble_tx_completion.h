/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_M1_BLE_TX_COMPLETION_H_
#define KINEIMU_NODE_A_M1_BLE_TX_COMPLETION_H_

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/spinlock.h>

enum node_a_ble_tx_completion_state {
	NODE_A_BLE_TX_COMPLETION_AVAILABLE = 0,
	NODE_A_BLE_TX_COMPLETION_IN_FLIGHT,
	NODE_A_BLE_TX_COMPLETION_CANCELED,
};

/*
 * Ownership state for one packet submitted to bt_gatt_notify_cb(). A service
 * owns one instance per completion-window slot. The callback user_data points
 * at the containing object, so a canceled object must remain unavailable until
 * the ATT destroy work has drained it.
 */
struct node_a_ble_tx_completion {
	struct k_spinlock lock;
	enum node_a_ble_tx_completion_state state;
	uint32_t generation;
	uint32_t start_cycles;
};

void node_a_ble_tx_completion_init(
	struct node_a_ble_tx_completion *completion);

bool node_a_ble_tx_completion_begin(
	struct node_a_ble_tx_completion *completion,
	uint32_t generation,
	uint32_t start_cycles);

bool node_a_ble_tx_completion_complete(
	struct node_a_ble_tx_completion *completion,
	uint32_t generation,
	uint32_t end_cycles,
	uint32_t *elapsed_cycles);

bool node_a_ble_tx_completion_cancel(
	struct node_a_ble_tx_completion *completion,
	uint32_t generation,
	uint32_t end_cycles,
	uint32_t *elapsed_cycles);

bool node_a_ble_tx_completion_reclaim(
	struct node_a_ble_tx_completion *completion,
	uint32_t generation);

enum node_a_ble_tx_completion_state node_a_ble_tx_completion_state_get(
	struct node_a_ble_tx_completion *completion);

uint32_t node_a_ble_tx_completion_generation_get(
	struct node_a_ble_tx_completion *completion);

#endif /* KINEIMU_NODE_A_M1_BLE_TX_COMPLETION_H_ */
