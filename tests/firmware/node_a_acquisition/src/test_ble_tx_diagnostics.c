/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/spinlock.h>
#include <zephyr/sys/util.h>
#include <zephyr/ztest.h>

#include "m1_ble_tx_diagnostics.h"

#define TEST_CYCLE_FREQUENCY_HZ 1000000U

static void diagnostics_init(struct node_a_ble_tx_diagnostics *diagnostics)
{
	node_a_ble_tx_diagnostics_init(diagnostics, 0x123456789abcdef0ULL, 1U,
				      TEST_CYCLE_FREQUENCY_HZ, 8U);
}

static uint32_t return_code_count(
	const struct node_a_ble_tx_diagnostics_snapshot *snapshot,
	int32_t code)
{
	for (size_t index = 0U;
	     index < NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS; index++) {
		if (snapshot->notify_return_codes[index].occupied &&
		    (snapshot->notify_return_codes[index].code == code)) {
			return snapshot->notify_return_codes[index].count;
		}
	}
	return 0U;
}

ZTEST(node_a_ble_tx_diagnostics,
      test_accepted_submission_counts_call_and_completion_age)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 1U));
	zassert_true(node_a_ble_tx_diagnostics_notify_call_begin(
		&diagnostics, &submission));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, 0, 100U);
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);

	zassert_equal(snapshot.notify_submit_calls, 1U);
	zassert_equal(snapshot.notify_accepted, 1U);
	zassert_equal(snapshot.notify_last_return_code, 0);
	zassert_equal(return_code_count(&snapshot, 0), 1U);
	zassert_equal(snapshot.in_flight_current, 1U);
	zassert_equal(snapshot.in_flight_peak, 1U);
	zassert_equal(snapshot.completion_window_owned_current, 1U);
	zassert_equal(snapshot.notify_final_failures, 0U);
	zassert_equal(snapshot.notify_packet_drops, 0U);

	zassert_true(node_a_ble_tx_diagnostics_complete(
		&diagnostics, &submission, 1U, 1100U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);
	zassert_equal(snapshot.notify_completed, 1U);
	zassert_equal(snapshot.in_flight_current, 0U);
	zassert_equal(snapshot.completion_window_owned_current, 0U);
	zassert_equal(snapshot.completion_age.count, 1U);
	zassert_equal(snapshot.completion_age.last_us, 1000U);
	zassert_equal(snapshot.completion_age.min_us, 1000U);
	zassert_equal(snapshot.completion_age.max_us, 1000U);
	zassert_equal(snapshot.completion_age.total_us, 1000U);
	zassert_equal(snapshot.completion_age.buckets[1], 1U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_callback_before_return_recording_defers_slot_release)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;
	enum node_a_ble_tx_diag_callback_result callback_result;
	bool released_by_submitter;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 1U));
	zassert_true(node_a_ble_tx_diagnostics_notify_call_begin(
		&diagnostics, &submission));
	callback_result = node_a_ble_tx_diagnostics_complete(
		&diagnostics, &submission, 1U, 210U);
	zassert_equal(callback_result, NODE_A_BLE_TX_DIAG_CALLBACK_DEFERRED);
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);
	zassert_equal(snapshot.notify_completed, 0U);
	zassert_equal(snapshot.in_flight_current, 0U);
	zassert_equal(snapshot.completion_window_owned_current, 1U);

	released_by_submitter = node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, 0, 200U);
	zassert_true(released_by_submitter);
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);
	zassert_equal(snapshot.notify_submit_calls, 1U);
	zassert_equal(snapshot.notify_accepted, 1U);
	zassert_equal(snapshot.notify_completed, 1U);
	zassert_equal(snapshot.in_flight_current, 0U);
	zassert_equal(snapshot.in_flight_peak, 1U);
	zassert_equal(snapshot.completion_window_owned_current, 0U);
	zassert_equal(snapshot.completion_age.count, 1U);
	zassert_equal(snapshot.completion_age.last_us, 10U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_cancel_during_notify_call_keeps_acceptance_out_of_drop_count)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 6U));
	zassert_true(node_a_ble_tx_diagnostics_notify_call_begin(
		&diagnostics, &submission));
	zassert_true(node_a_ble_tx_diagnostics_cancel(
		&diagnostics, &submission, 6U));
	zassert_false(node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, 0, 100U));
	zassert_true(node_a_ble_tx_diagnostics_reclaim(
		&diagnostics, &submission, 6U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);

	zassert_equal(snapshot.notify_submit_calls, 1U);
	zassert_equal(snapshot.notify_accepted, 1U);
	zassert_equal(snapshot.notify_cancelled, 1U);
	zassert_equal(snapshot.notify_final_failures, 0U);
	zassert_equal(snapshot.notify_packet_drops, 0U);
	zassert_equal(snapshot.in_flight_current, 0U);
	zassert_equal(snapshot.completion_window_owned_current, 0U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_enomem_and_eagain_retries_are_distinct_and_counted)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 3U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, -ENOMEM, 100U);
	node_a_ble_tx_diagnostics_note_schedule_result(
		&diagnostics, &submission, true, 0);
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, -EAGAIN, 200U);
	node_a_ble_tx_diagnostics_note_schedule_result(
		&diagnostics, &submission, true, 0);
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, 0, 300U);
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);

	zassert_equal(snapshot.notify_submit_calls, 3U);
	zassert_equal(snapshot.notify_accepted, 1U);
	zassert_equal(snapshot.notify_ret_enomem, 1U);
	zassert_equal(snapshot.notify_ret_eagain, 1U);
	zassert_equal(snapshot.retry_attempts, 2U);
	zassert_equal(return_code_count(&snapshot, -ENOMEM), 1U);
	zassert_equal(return_code_count(&snapshot, -EAGAIN), 1U);
	zassert_equal(return_code_count(&snapshot, 0), 1U);
	zassert_equal(snapshot.retry_schedule_failures, 0U);
	zassert_equal(snapshot.in_flight_current, 1U);
	zassert_equal(snapshot.notify_final_failures, 0U);
	zassert_equal(snapshot.notify_packet_drops, 0U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_nontransient_errors_keep_exact_codes_and_are_not_accepted)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission first = {0};
	struct node_a_ble_tx_diag_submission second = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &first, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &first, -EINVAL, 100U);
	zassert_true(node_a_ble_tx_diagnostics_submission_fail(
		&diagnostics, &first, 1U));
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &second, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &second, -EIO, 200U);
	zassert_true(node_a_ble_tx_diagnostics_submission_fail(
		&diagnostics, &second, 1U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);

	zassert_equal(snapshot.notify_submit_calls, 2U);
	zassert_equal(snapshot.notify_accepted, 0U);
	zassert_equal(snapshot.notify_last_return_code, -EIO);
	zassert_equal(return_code_count(&snapshot, -EINVAL), 1U);
	zassert_equal(return_code_count(&snapshot, -EIO), 1U);
	zassert_equal(snapshot.retry_attempts, 0U);
	zassert_equal(snapshot.in_flight_current, 0U);
	zassert_equal(snapshot.notify_final_failures, 2U);
	zassert_equal(snapshot.notify_packet_drops, 2U);
	zassert_equal(snapshot.completion_window_owned_current, 0U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_return_code_table_retains_exact_codes_and_marks_capacity_overflow)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	for (uint32_t index = 0U;
	     index < NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS; index++) {
		zassert_true(node_a_ble_tx_diagnostics_submission_begin(
			&diagnostics, &submission, 1U));
		node_a_ble_tx_diagnostics_note_notify_result(
			&diagnostics, &submission, -200 - (int32_t)index, index);
		zassert_true(node_a_ble_tx_diagnostics_submission_fail(
			&diagnostics, &submission, 1U));
	}
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, -9999, 100U);
	zassert_true(node_a_ble_tx_diagnostics_submission_fail(
		&diagnostics, &submission, 1U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);

	for (uint32_t index = 0U;
	     index < NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS; index++) {
		zassert_equal(return_code_count(&snapshot,
						-(200 + (int32_t)index)), 1U);
	}
	zassert_equal(snapshot.notify_return_code_overflow, 1U);
	zassert_equal(snapshot.notify_last_return_code, -9999);
	zassert_equal(snapshot.notify_submit_calls,
		      NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS + 1U);
	zassert_equal(snapshot.notify_final_failures,
		      NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS + 1U);
	zassert_equal(snapshot.notify_packet_drops,
		      NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS + 1U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_schedule_failures_are_not_reported_as_notify_calls_or_retries)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission initial = {0};
	struct node_a_ble_tx_diag_submission retry = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &initial, 1U));
	node_a_ble_tx_diagnostics_note_schedule_result(
		&diagnostics, &initial, false, -EIO);
	zassert_true(node_a_ble_tx_diagnostics_submission_fail(
		&diagnostics, &initial, 1U));
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &retry, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &retry, -ENOMEM, 100U);
	node_a_ble_tx_diagnostics_note_schedule_result(
		&diagnostics, &retry, true, -EAGAIN);
	zassert_true(node_a_ble_tx_diagnostics_submission_fail(
		&diagnostics, &retry, 1U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);

	zassert_equal(snapshot.initial_schedule_failures, 1U);
	zassert_equal(snapshot.retry_schedule_failures, 1U);
	zassert_equal(snapshot.last_initial_schedule_rc, -EIO);
	zassert_equal(snapshot.last_retry_schedule_rc, -EAGAIN);
	zassert_equal(snapshot.notify_submit_calls, 1U);
	zassert_equal(return_code_count(&snapshot, -ENOMEM), 1U);
	zassert_equal(return_code_count(&snapshot, -EAGAIN), 0U);
	zassert_equal(snapshot.retry_attempts, 0U);
	zassert_equal(snapshot.notify_accepted, 0U);
	zassert_equal(snapshot.notify_final_failures, 2U);
	zassert_equal(snapshot.notify_packet_drops, 2U);
	zassert_equal(snapshot.completion_window_owned_current, 0U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_preflight_rejection_counts_final_failure_and_packet_drop_without_gatt_call)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 1U));
	zassert_true(node_a_ble_tx_diagnostics_submission_fail(
		&diagnostics, &submission, 1U));
	zassert_false(node_a_ble_tx_diagnostics_submission_fail(
		&diagnostics, &submission, 1U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);

	zassert_equal(snapshot.notify_submit_calls, 0U);
	zassert_equal(snapshot.notify_accepted, 0U);
	zassert_equal(snapshot.notify_final_failures, 1U);
	zassert_equal(snapshot.notify_packet_drops, 1U);
	zassert_equal(snapshot.in_flight_current, 0U);
	zassert_equal(snapshot.completion_window_owned_current, 0U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_cancel_reconnect_and_stale_generation_callback_are_isolated)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 7U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, 0, 100U);
	zassert_true(node_a_ble_tx_diagnostics_cancel(
		&diagnostics, &submission, 7U));
	zassert_equal(diagnostics.totals.completion_window_owned_current, 1U);
	zassert_false(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 8U));
	zassert_true(node_a_ble_tx_diagnostics_reclaim(
		&diagnostics, &submission, 7U));
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 8U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, 0, 200U);

	zassert_false(node_a_ble_tx_diagnostics_complete(
		&diagnostics, &submission, 7U, 250U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);
	zassert_equal(snapshot.callbacks_stale_generation, 1U);
	zassert_equal(snapshot.in_flight_current, 1U);
	zassert_equal(snapshot.completion_age.count, 0U);

	zassert_true(node_a_ble_tx_diagnostics_complete(
		&diagnostics, &submission, 8U, 300U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);
	zassert_equal(snapshot.notify_accepted, 2U);
	zassert_equal(snapshot.notify_cancelled, 1U);
	zassert_equal(snapshot.notify_completed, 1U);
	zassert_equal(snapshot.notify_final_failures, 0U);
	zassert_equal(snapshot.notify_packet_drops, 0U);
	zassert_equal(snapshot.completion_window_owned_current, 0U);
	zassert_equal(snapshot.in_flight_current, 0U);
	zassert_equal(snapshot.in_flight_peak, 1U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_callback_after_cancel_does_not_complete_or_decrement_twice)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 4U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, 0, 100U);
	zassert_true(node_a_ble_tx_diagnostics_cancel(
		&diagnostics, &submission, 4U));
	node_a_ble_tx_diagnostics_note_callback_rejected(
		&diagnostics, &submission, 4U, true);
	zassert_false(node_a_ble_tx_diagnostics_complete(
		&diagnostics, &submission, 4U, 200U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);

	zassert_equal(snapshot.callbacks_after_cancel, 2U);
	zassert_equal(snapshot.notify_completed, 0U);
	zassert_equal(snapshot.completion_age.count, 0U);
	zassert_equal(snapshot.in_flight_current, 0U);
	zassert_equal(snapshot.notify_cancelled, 1U);
	zassert_equal(snapshot.notify_final_failures, 0U);
	zassert_equal(snapshot.notify_packet_drops, 0U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_preaccept_cancel_counts_packet_drop_only_after_reclaim)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 5U));
	zassert_true(node_a_ble_tx_diagnostics_cancel(
		&diagnostics, &submission, 5U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);
	zassert_equal(snapshot.notify_packet_drops, 0U);
	zassert_equal(snapshot.notify_final_failures, 0U);
	zassert_equal(snapshot.completion_window_owned_current, 1U);

	zassert_true(node_a_ble_tx_diagnostics_reclaim(
		&diagnostics, &submission, 5U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);
	zassert_equal(snapshot.notify_submit_calls, 0U);
	zassert_equal(snapshot.notify_accepted, 0U);
	zassert_equal(snapshot.notify_cancelled, 1U);
	zassert_equal(snapshot.notify_final_failures, 0U);
	zassert_equal(snapshot.notify_packet_drops, 1U);
	zassert_equal(snapshot.completion_window_owned_current, 0U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_completion_age_uses_wrapping_cycles_and_fixed_histogram_edges)
{
	static const uint32_t ages_us[] = {
		0U, 999U, 1000U, 2499U, 2500U,
		5000U, 10000U, 25000U, 50000U, 100000U,
	};
	static const uint32_t expected_buckets[NODE_A_BLE_TX_DIAG_LATENCY_BUCKETS] = {
		2U, 2U, 1U, 1U, 1U, 1U, 1U, 1U,
	};
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;
	const uint32_t accepted_cycles = UINT32_MAX - 50U;

	diagnostics_init(&diagnostics);
	for (size_t index = 0U; index < ARRAY_SIZE(ages_us); index++) {
		zassert_true(node_a_ble_tx_diagnostics_submission_begin(
			&diagnostics, &submission, 1U));
		node_a_ble_tx_diagnostics_note_notify_result(
			&diagnostics, &submission, 0, accepted_cycles);
		zassert_true(node_a_ble_tx_diagnostics_complete(
			&diagnostics, &submission, 1U,
			(uint32_t)(accepted_cycles + ages_us[index])));
	}
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);

	zassert_equal(snapshot.completion_age.count, ARRAY_SIZE(ages_us));
	zassert_equal(snapshot.completion_age.last_us, 100000U);
	zassert_equal(snapshot.completion_age.min_us, 0U);
	zassert_equal(snapshot.completion_age.max_us, 100000U);
	zassert_equal(snapshot.completion_age.total_us, 196998U);
	for (size_t index = 0U; index < ARRAY_SIZE(expected_buckets); index++) {
		zassert_equal(snapshot.completion_age.buckets[index],
			      expected_buckets[index]);
	}
}

ZTEST(node_a_ble_tx_diagnostics,
      test_eight_contexts_are_independent_and_window_wait_is_cumulative)
{
	enum { CONTEXT_COUNT = 8U };
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submissions[CONTEXT_COUNT] = {0};
	struct node_a_ble_tx_diag_submission overflow = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	for (uint32_t index = 0U; index < CONTEXT_COUNT; index++) {
		zassert_true(node_a_ble_tx_diagnostics_submission_begin(
			&diagnostics, &submissions[index], index + 1U));
		node_a_ble_tx_diagnostics_note_notify_result(
			&diagnostics, &submissions[index], 0,
			(uint32_t)(UINT32_MAX - 20U + index));
	}
	zassert_false(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &overflow, 9U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);
	zassert_equal(snapshot.in_flight_current, CONTEXT_COUNT);
	zassert_equal(snapshot.in_flight_peak, CONTEXT_COUNT);
	zassert_equal(snapshot.completion_window_owned_current, CONTEXT_COUNT);

	zassert_true(node_a_ble_tx_diagnostics_window_wait_begin(
		&diagnostics, UINT32_MAX - 5U));
	zassert_false(node_a_ble_tx_diagnostics_window_wait_begin(
		&diagnostics, UINT32_MAX - 4U));
	zassert_true(node_a_ble_tx_diagnostics_complete(
		&diagnostics, &submissions[0], 1U, 6U));
	zassert_true(node_a_ble_tx_diagnostics_window_wait_end(
		&diagnostics, 6U));
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);
	zassert_equal(snapshot.completion_window_full_count, 1U);
	zassert_equal(snapshot.completion_window_wait_total_us, 12U);
	zassert_equal(snapshot.in_flight_current, 7U);
	zassert_equal(snapshot.completion_window_owned_current, 7U);
	zassert_equal(submissions[1].state,
		      NODE_A_BLE_TX_DIAG_CONTEXT_ACCEPTED);
	zassert_equal(submissions[7].state,
		      NODE_A_BLE_TX_DIAG_CONTEXT_ACCEPTED);

	for (uint32_t index = 1U; index < CONTEXT_COUNT; index++) {
		zassert_true(node_a_ble_tx_diagnostics_complete(
			&diagnostics, &submissions[index], index + 1U, 250U));
	}
	for (uint32_t index = 0U; index < CONTEXT_COUNT; index++) {
		zassert_true(node_a_ble_tx_diagnostics_submission_begin(
			&diagnostics, &submissions[index], index + 1U));
		node_a_ble_tx_diagnostics_note_notify_result(
			&diagnostics, &submissions[index], 0, 300U);
	}
	zassert_true(node_a_ble_tx_diagnostics_window_wait_begin(
		&diagnostics, 400U));
	zassert_true(node_a_ble_tx_diagnostics_complete(
		&diagnostics, &submissions[0], 1U, 405U));
	zassert_true(node_a_ble_tx_diagnostics_window_wait_end(
		&diagnostics, 405U));
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submissions[0], 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submissions[0], 0, 406U);
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);
	zassert_equal(snapshot.completion_window_full_count, 2U);
	zassert_equal(snapshot.completion_window_wait_total_us, 17U);
	zassert_equal(snapshot.in_flight_current, CONTEXT_COUNT);
	zassert_equal(snapshot.in_flight_peak, CONTEXT_COUNT);
	zassert_equal(snapshot.completion_window_owned_current, CONTEXT_COUNT);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_counters_saturate_and_empty_completion_cannot_underflow)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diag_submission submission = {0};
	struct node_a_ble_tx_diagnostics_snapshot snapshot;

	diagnostics_init(&diagnostics);
	zassert_false(node_a_ble_tx_diagnostics_complete(
		&diagnostics, &submission, 1U, 1U));
	zassert_false(node_a_ble_tx_diagnostics_cancel(
		&diagnostics, &submission, 1U));
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, -EIO, 10U);
	zassert_true(node_a_ble_tx_diagnostics_submission_fail(
		&diagnostics, &submission, 1U));

	for (size_t index = 0U;
	     index < NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS; index++) {
		if (diagnostics.totals.notify_return_codes[index].occupied &&
		    (diagnostics.totals.notify_return_codes[index].code == -EIO)) {
			diagnostics.totals.notify_return_codes[index].count =
				UINT32_MAX - 1U;
		}
	}
	diagnostics.totals.notify_submit_calls = UINT32_MAX - 1U;
	diagnostics.totals.notify_final_failures = UINT32_MAX - 1U;
	diagnostics.totals.notify_packet_drops = UINT32_MAX - 1U;
	diagnostics.totals.completion_age.total_us = UINT64_MAX - 3U;

	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, -EIO, 20U);
	zassert_true(node_a_ble_tx_diagnostics_submission_fail(
		&diagnostics, &submission, 1U));
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, -EIO, 30U);
	zassert_true(node_a_ble_tx_diagnostics_submission_fail(
		&diagnostics, &submission, 1U));
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, 0, 40U);
	zassert_true(node_a_ble_tx_diagnostics_complete(
		&diagnostics, &submission, 1U, 45U));
	diagnostics.totals.retry_attempts = UINT32_MAX - 1U;
	diagnostics.totals.notify_ret_enomem = UINT32_MAX - 1U;
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &submission, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, -ENOMEM, 50U);
	node_a_ble_tx_diagnostics_note_schedule_result(
		&diagnostics, &submission, true, 0);
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, -ENOMEM, 60U);
	node_a_ble_tx_diagnostics_note_schedule_result(
		&diagnostics, &submission, true, 0);
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &submission, -ENOMEM, 70U);
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &snapshot);

	zassert_equal(snapshot.notify_submit_calls, UINT32_MAX);
	zassert_equal(return_code_count(&snapshot, -EIO), UINT32_MAX);
	zassert_equal(snapshot.notify_final_failures, UINT32_MAX);
	zassert_equal(snapshot.notify_packet_drops, UINT32_MAX);
	zassert_equal(snapshot.completion_age.total_us, UINT64_MAX);
	zassert_equal(snapshot.retry_attempts, UINT32_MAX);
	zassert_equal(snapshot.notify_ret_enomem, UINT32_MAX);
	zassert_true(snapshot.counters_saturated);
	zassert_equal(snapshot.in_flight_current, 0U);
}

ZTEST(node_a_ble_tx_diagnostics,
      test_generation_change_keeps_boot_counters_cumulative_and_run_delta_is_snapshot_difference)
{
	struct node_a_ble_tx_diagnostics diagnostics;
	struct node_a_ble_tx_diagnostics next_boot;
	struct node_a_ble_tx_diag_submission first = {0};
	struct node_a_ble_tx_diag_submission second = {0};
	struct node_a_ble_tx_diagnostics_snapshot run_start;
	struct node_a_ble_tx_diagnostics_snapshot run_end;
	struct node_a_ble_tx_diagnostics_snapshot after_generation;
	struct node_a_ble_tx_diagnostics_snapshot after_reboot;

	diagnostics_init(&diagnostics);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &first, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &first, -ENOMEM, 100U);
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &run_start);
	zassert_true(node_a_ble_tx_diagnostics_submission_begin(
		&diagnostics, &second, 1U));
	node_a_ble_tx_diagnostics_note_notify_result(
		&diagnostics, &second, -EAGAIN, 200U);
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &run_end);

	zassert_equal(run_end.notify_submit_calls - run_start.notify_submit_calls,
		      1U);
	zassert_equal(run_end.notify_ret_eagain - run_start.notify_ret_eagain,
		      1U);
	node_a_ble_tx_diagnostics_set_connection_generation(&diagnostics, 2U);
	node_a_ble_tx_diagnostics_snapshot_get(&diagnostics, &after_generation);
	zassert_equal(after_generation.boot_id, 0x123456789abcdef0ULL);
	zassert_equal(after_generation.connection_generation, 2U);
	zassert_equal(after_generation.notify_submit_calls,
		      run_end.notify_submit_calls);
	zassert_equal(after_generation.notify_ret_enomem,
		      run_end.notify_ret_enomem);
	zassert_equal(after_generation.notify_ret_eagain,
		      run_end.notify_ret_eagain);

	node_a_ble_tx_diagnostics_init(&next_boot, 0xfedcba9876543210ULL, 1U,
				       TEST_CYCLE_FREQUENCY_HZ, 8U);
	node_a_ble_tx_diagnostics_snapshot_get(&next_boot, &after_reboot);
	zassert_equal(after_reboot.boot_id, 0xfedcba9876543210ULL);
	zassert_equal(after_reboot.connection_generation, 1U);
	zassert_equal(after_reboot.notify_submit_calls, 0U);
	zassert_equal(after_reboot.notify_ret_enomem, 0U);
	zassert_equal(after_reboot.notify_ret_eagain, 0U);
}

ZTEST_SUITE(node_a_ble_tx_diagnostics, NULL, NULL, NULL, NULL, NULL);
