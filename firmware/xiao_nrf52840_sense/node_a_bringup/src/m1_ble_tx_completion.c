/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>

#include "m1_ble_tx_completion.h"

void node_a_ble_tx_completion_init(
	struct node_a_ble_tx_completion *completion)
{
	if (completion == NULL) {
		return;
	}

	memset(completion, 0, sizeof(*completion));
	completion->state = NODE_A_BLE_TX_COMPLETION_AVAILABLE;
}

bool node_a_ble_tx_completion_begin(
	struct node_a_ble_tx_completion *completion,
	uint32_t generation,
	uint32_t start_cycles)
{
	k_spinlock_key_t key;
	bool acquired = false;

	if (completion == NULL) {
		return false;
	}

	key = k_spin_lock(&completion->lock);
	if (completion->state == NODE_A_BLE_TX_COMPLETION_AVAILABLE) {
		completion->generation = generation;
		completion->start_cycles = start_cycles;
		completion->state = NODE_A_BLE_TX_COMPLETION_IN_FLIGHT;
		acquired = true;
	}
	k_spin_unlock(&completion->lock, key);
	return acquired;
}

static bool finish_completion(
	struct node_a_ble_tx_completion *completion,
	uint32_t generation,
	uint32_t end_cycles,
	enum node_a_ble_tx_completion_state final_state,
	uint32_t *elapsed_cycles)
{
	k_spinlock_key_t key;
	bool finished = false;

	if (completion == NULL) {
		return false;
	}

	key = k_spin_lock(&completion->lock);
	if ((completion->state == NODE_A_BLE_TX_COMPLETION_IN_FLIGHT) &&
	    (completion->generation == generation)) {
		if (elapsed_cycles != NULL) {
			/* Unsigned subtraction deliberately preserves a 32-bit cycle wrap. */
			*elapsed_cycles = end_cycles - completion->start_cycles;
		}
		completion->state = final_state;
		finished = true;
	}
	k_spin_unlock(&completion->lock, key);
	return finished;
}

bool node_a_ble_tx_completion_complete(
	struct node_a_ble_tx_completion *completion,
	uint32_t generation,
	uint32_t end_cycles,
	uint32_t *elapsed_cycles)
{
	return finish_completion(completion, generation, end_cycles,
				 NODE_A_BLE_TX_COMPLETION_AVAILABLE, elapsed_cycles);
}

bool node_a_ble_tx_completion_cancel(
	struct node_a_ble_tx_completion *completion,
	uint32_t generation,
	uint32_t end_cycles,
	uint32_t *elapsed_cycles)
{
	return finish_completion(completion, generation, end_cycles,
				 NODE_A_BLE_TX_COMPLETION_CANCELED, elapsed_cycles);
}

bool node_a_ble_tx_completion_reclaim(
	struct node_a_ble_tx_completion *completion,
	uint32_t generation)
{
	k_spinlock_key_t key;
	bool reclaimed = false;

	if (completion == NULL) {
		return false;
	}

	key = k_spin_lock(&completion->lock);
	if ((completion->state == NODE_A_BLE_TX_COMPLETION_CANCELED) &&
	    (completion->generation == generation)) {
		completion->state = NODE_A_BLE_TX_COMPLETION_AVAILABLE;
		reclaimed = true;
	}
	k_spin_unlock(&completion->lock, key);
	return reclaimed;
}

enum node_a_ble_tx_completion_state node_a_ble_tx_completion_state_get(
	struct node_a_ble_tx_completion *completion)
{
	k_spinlock_key_t key;
	enum node_a_ble_tx_completion_state state;

	if (completion == NULL) {
		return NODE_A_BLE_TX_COMPLETION_CANCELED;
	}

	key = k_spin_lock(&completion->lock);
	state = completion->state;
	k_spin_unlock(&completion->lock, key);
	return state;
}

uint32_t node_a_ble_tx_completion_generation_get(
	struct node_a_ble_tx_completion *completion)
{
	k_spinlock_key_t key;
	uint32_t generation;

	if (completion == NULL) {
		return 0U;
	}

	key = k_spin_lock(&completion->lock);
	generation = completion->generation;
	k_spin_unlock(&completion->lock, key);
	return generation;
}
