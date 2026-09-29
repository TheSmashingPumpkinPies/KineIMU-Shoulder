/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdint.h>

#include <zephyr/ztest.h>

#include "m1_ble_tx_completion.h"

ZTEST(node_a_ble_tx_completion, test_completion_releases_only_matching_generation)
{
	struct node_a_ble_tx_completion completion;
	uint32_t elapsed_cycles = 0U;

	node_a_ble_tx_completion_init(&completion);
	zassert_true(node_a_ble_tx_completion_begin(&completion, 7U, 100U));
	zassert_equal(node_a_ble_tx_completion_state_get(&completion),
		      NODE_A_BLE_TX_COMPLETION_IN_FLIGHT);

	zassert_false(node_a_ble_tx_completion_complete(
		&completion, 8U, 150U, &elapsed_cycles));
	zassert_equal(node_a_ble_tx_completion_state_get(&completion),
		      NODE_A_BLE_TX_COMPLETION_IN_FLIGHT);
	zassert_true(node_a_ble_tx_completion_complete(
		&completion, 7U, 150U, &elapsed_cycles));
	zassert_equal(elapsed_cycles, 50U);
	zassert_equal(node_a_ble_tx_completion_state_get(&completion),
		      NODE_A_BLE_TX_COMPLETION_AVAILABLE);
	zassert_false(node_a_ble_tx_completion_complete(
		&completion, 7U, 160U, &elapsed_cycles));
}

ZTEST(node_a_ble_tx_completion, test_cancel_holds_context_until_reclaim)
{
	struct node_a_ble_tx_completion completion;
	uint32_t elapsed_cycles = 0U;

	node_a_ble_tx_completion_init(&completion);
	zassert_true(node_a_ble_tx_completion_begin(&completion, 4U, 1000U));
	zassert_true(node_a_ble_tx_completion_cancel(
		&completion, 4U, 1020U, &elapsed_cycles));
	zassert_equal(elapsed_cycles, 20U);
	zassert_equal(node_a_ble_tx_completion_state_get(&completion),
		      NODE_A_BLE_TX_COMPLETION_CANCELED);

	/* A new connection generation cannot reuse the callback context while
	 * the old ATT buffer may still own its user_data pointer. */
	zassert_false(node_a_ble_tx_completion_begin(&completion, 5U, 2000U));
	zassert_false(node_a_ble_tx_completion_reclaim(&completion, 5U));
	zassert_true(node_a_ble_tx_completion_reclaim(&completion, 4U));
	zassert_true(node_a_ble_tx_completion_begin(&completion, 5U, 2000U));
}

ZTEST(node_a_ble_tx_completion, test_elapsed_cycles_wrap_uint32)
{
	struct node_a_ble_tx_completion completion;
	uint32_t elapsed_cycles = 0U;

	node_a_ble_tx_completion_init(&completion);
	zassert_true(node_a_ble_tx_completion_begin(
		&completion, 1U, UINT32_MAX - 5U));
	zassert_true(node_a_ble_tx_completion_complete(
		&completion, 1U, 7U, &elapsed_cycles));
	zassert_equal(elapsed_cycles, 13U);
}

ZTEST(node_a_ble_tx_completion, test_completion_contexts_are_independent)
{
	enum { TEST_CONTEXT_COUNT = 8 };
	struct node_a_ble_tx_completion completions[TEST_CONTEXT_COUNT];

	for (uint32_t index = 0U; index < TEST_CONTEXT_COUNT; index++) {
		node_a_ble_tx_completion_init(&completions[index]);
		zassert_true(node_a_ble_tx_completion_begin(
			&completions[index], index + 1U, index * 100U));
	}

	for (uint32_t index = 0U; index < TEST_CONTEXT_COUNT; index++) {
		uint32_t elapsed_cycles = 0U;

		zassert_true(node_a_ble_tx_completion_complete(
			&completions[index], index + 1U, index * 100U + 10U,
			&elapsed_cycles));
		zassert_equal(elapsed_cycles, 10U);
		zassert_equal(node_a_ble_tx_completion_state_get(&completions[index]),
			      NODE_A_BLE_TX_COMPLETION_AVAILABLE);
	}
}

ZTEST_SUITE(node_a_ble_tx_completion, NULL, NULL, NULL, NULL, NULL);
