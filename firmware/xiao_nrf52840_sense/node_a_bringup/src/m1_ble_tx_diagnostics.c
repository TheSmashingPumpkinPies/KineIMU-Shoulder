/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/spinlock.h>
#include <zephyr/sys/util.h>

#include "m1_ble_tx_diagnostics.h"

#define NODE_A_BLE_TX_DIAG_US_PER_SECOND 1000000ULL

static void saturating_add_u32(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t *counter,
	uint32_t amount)
{
	if (amount == 0U) {
		return;
	}

	if (*counter > (UINT32_MAX - amount)) {
		*counter = UINT32_MAX;
		diagnostics->totals.counters_saturated = true;
		return;
	}

	*counter += amount;
	if (*counter == UINT32_MAX) {
		diagnostics->totals.counters_saturated = true;
	}
}

static void saturating_increment(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t *counter)
{
	saturating_add_u32(diagnostics, counter, 1U);
}

static void saturating_add_u64(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint64_t *counter,
	uint64_t amount)
{
	if (amount == 0U) {
		return;
	}

	if (*counter > (UINT64_MAX - amount)) {
		*counter = UINT64_MAX;
		diagnostics->totals.counters_saturated = true;
		return;
	}

	*counter += amount;
	if (*counter == UINT64_MAX) {
		diagnostics->totals.counters_saturated = true;
	}
}

static uint64_t cycles_to_us(
	const struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t cycles)
{
	if (diagnostics->cycle_frequency_hz == 0U) {
		return 0U;
	}

	return ((uint64_t)cycles * NODE_A_BLE_TX_DIAG_US_PER_SECOND) /
		diagnostics->cycle_frequency_hz;
}

static uint32_t cycles_to_us_u32(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t cycles)
{
	const uint64_t duration_us = cycles_to_us(diagnostics, cycles);

	if (duration_us > UINT32_MAX) {
		diagnostics->totals.counters_saturated = true;
		return UINT32_MAX;
	}
	return (uint32_t)duration_us;
}

static void update_return_code_count(
	struct node_a_ble_tx_diagnostics *diagnostics,
	int return_code)
{
	struct node_a_ble_tx_diagnostics_snapshot *totals =
		&diagnostics->totals;
	size_t free_slot = NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS;

	for (size_t index = 0U;
	     index < NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS; index++) {
		struct node_a_ble_tx_diag_return_code *slot =
			&totals->notify_return_codes[index];

		if (!slot->occupied) {
			if (free_slot == NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS) {
				free_slot = index;
			}
			continue;
		}
		if (slot->code == (int32_t)return_code) {
			saturating_increment(diagnostics, &slot->count);
			return;
		}
	}

	if (free_slot < NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS) {
		struct node_a_ble_tx_diag_return_code *slot =
			&totals->notify_return_codes[free_slot];

		slot->occupied = true;
		slot->code = (int32_t)return_code;
		slot->count = 1U;
		return;
	}

	saturating_increment(diagnostics,
			     &totals->notify_return_code_overflow);
}

static size_t latency_bucket(uint32_t duration_us)
{
	if (duration_us < 1000U) {
		return 0U;
	}
	if (duration_us < 2500U) {
		return 1U;
	}
	if (duration_us < 5000U) {
		return 2U;
	}
	if (duration_us < 10000U) {
		return 3U;
	}
	if (duration_us < 25000U) {
		return 4U;
	}
	if (duration_us < 50000U) {
		return 5U;
	}
	if (duration_us < 100000U) {
		return 6U;
	}
	return 7U;
}

static void note_completion_age(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t duration_us)
{
	struct node_a_ble_tx_diag_latency_stats *age =
		&diagnostics->totals.completion_age;
	const bool first = age->count == 0U;

	saturating_increment(diagnostics, &age->count);
	age->last_us = duration_us;
	if (first || (duration_us < age->min_us)) {
		age->min_us = duration_us;
	}
	if (first || (duration_us > age->max_us)) {
		age->max_us = duration_us;
	}
	saturating_add_u64(diagnostics, &age->total_us, duration_us);
	saturating_increment(diagnostics,
			     &age->buckets[latency_bucket(duration_us)]);
}

static void update_owned_count(
	struct node_a_ble_tx_diagnostics *diagnostics,
	bool acquire)
{
	if (acquire) {
		diagnostics->completion_window_owned_current++;
	} else if (diagnostics->completion_window_owned_current > 0U) {
		diagnostics->completion_window_owned_current--;
	}
	diagnostics->totals.completion_window_owned_current =
		diagnostics->completion_window_owned_current;
}

static void window_wait_end_locked(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t end_cycles)
{
	const uint32_t elapsed_cycles =
		end_cycles - diagnostics->completion_window_wait_started_cycles;

	if (!diagnostics->completion_window_wait_active) {
		return;
	}

	diagnostics->completion_window_wait_active = false;
	saturating_add_u64(
		diagnostics,
		&diagnostics->totals.completion_window_wait_total_us,
		cycles_to_us(diagnostics, elapsed_cycles));
}

static void window_wait_begin_locked(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t start_cycles)
{
	if (diagnostics->completion_window_wait_active ||
	    (diagnostics->completion_window_capacity == 0U) ||
	    (diagnostics->completion_window_owned_current !=
	     diagnostics->completion_window_capacity)) {
		return;
	}

	diagnostics->completion_window_wait_active = true;
	diagnostics->completion_window_wait_started_cycles = start_cycles;
	saturating_increment(diagnostics,
			     &diagnostics->totals.completion_window_full_count);
}

void node_a_ble_tx_diagnostics_init(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint64_t boot_id,
	uint32_t connection_generation,
	uint32_t cycle_frequency_hz,
	uint32_t completion_window_capacity)
{
	if (diagnostics == NULL) {
		return;
	}

	memset(diagnostics, 0, sizeof(*diagnostics));
	diagnostics->totals.boot_id = boot_id;
	diagnostics->totals.connection_generation = connection_generation;
	diagnostics->cycle_frequency_hz = cycle_frequency_hz;
	diagnostics->completion_window_capacity = completion_window_capacity;
}

bool node_a_ble_tx_diagnostics_submission_begin(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t connection_generation)
{
	k_spinlock_key_t key;
	bool began = false;

	if ((diagnostics == NULL) || (submission == NULL)) {
		return false;
	}

	key = k_spin_lock(&diagnostics->lock);
	if ((diagnostics->completion_window_capacity > 0U) &&
	    (diagnostics->completion_window_owned_current <
	     diagnostics->completion_window_capacity) &&
		((submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_FREE) ||
		 (submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_COMPLETED) ||
		 (submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_REJECTED))) {
		submission->state = NODE_A_BLE_TX_DIAG_CONTEXT_PRE_ACCEPT;
		submission->connection_generation = connection_generation;
		submission->accepted_generation = 0U;
		submission->notify_attempts = 0U;
		submission->accepted_at_cycles = 0U;
		submission->callback_pending_cycles = 0U;
		submission->notify_call_active = false;
		update_owned_count(diagnostics, true);
		began = true;
	}
	k_spin_unlock(&diagnostics->lock, key);
	return began;
}

bool node_a_ble_tx_diagnostics_notify_call_begin(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission)
{
	k_spinlock_key_t key;
	bool began = false;

	if ((diagnostics == NULL) || (submission == NULL)) {
		return false;
	}

	key = k_spin_lock(&diagnostics->lock);
	if ((submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_PRE_ACCEPT) &&
	    !submission->notify_call_active) {
		submission->notify_call_active = true;
		began = true;
	}
	k_spin_unlock(&diagnostics->lock, key);
	return began;
}

bool node_a_ble_tx_diagnostics_note_notify_result(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	int return_code,
	uint32_t returned_at_cycles)
{
	k_spinlock_key_t key;
	bool release_deferred_completion = false;

	if ((diagnostics == NULL) || (submission == NULL)) {
		return false;
	}

	key = k_spin_lock(&diagnostics->lock);
	saturating_increment(diagnostics,
			     &diagnostics->totals.notify_submit_calls);
	if (submission->notify_attempts > 0U) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.retry_attempts);
	}
	if (submission->notify_attempts < UINT32_MAX) {
		submission->notify_attempts++;
	} else {
		diagnostics->totals.counters_saturated = true;
	}
	diagnostics->totals.notify_last_return_code = (int32_t)return_code;
	update_return_code_count(diagnostics, return_code);

	if (return_code == -ENOMEM) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.notify_ret_enomem);
	} else if (return_code == -EAGAIN) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.notify_ret_eagain);
	}

	if (return_code == 0) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.notify_accepted);
		submission->accepted_generation =
			submission->connection_generation;
		submission->accepted_at_cycles = returned_at_cycles;
		if (submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_PRE_ACCEPT) {
			submission->state = NODE_A_BLE_TX_DIAG_CONTEXT_ACCEPTED;
			saturating_increment(diagnostics,
					     &diagnostics->totals.in_flight_current);
			if (diagnostics->totals.in_flight_current >
			    diagnostics->totals.in_flight_peak) {
				diagnostics->totals.in_flight_peak =
					diagnostics->totals.in_flight_current;
			}
		}
	}
	submission->notify_call_active = false;
	if (submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_CALLBACK_PENDING) {
		uint32_t age_cycles = 0U;

		if (return_code == 0) {
			/* The callback may have preempted immediately after the API return,
			 * before this thread sampled returned_at_cycles. Account for the
			 * accepted in-flight transition even though it was very brief.
			 */
			saturating_increment(diagnostics,
					     &diagnostics->totals.in_flight_current);
			if (diagnostics->totals.in_flight_current >
			    diagnostics->totals.in_flight_peak) {
				diagnostics->totals.in_flight_peak =
					diagnostics->totals.in_flight_current;
			}
			if (diagnostics->totals.in_flight_current > 0U) {
				diagnostics->totals.in_flight_current--;
			}
		} else {
			/* A completion callback paired with a rejected return violates the
			 * backend contract, but it still owns and completes this slot.
			 */
			saturating_increment(
				diagnostics,
				&diagnostics->totals.callbacks_unexpected);
		}

		age_cycles = submission->callback_pending_cycles - returned_at_cycles;
		if ((int32_t)age_cycles < 0) {
			/* The callback ran before the return timestamp was sampled. */
			age_cycles = 0U;
		}
		submission->state = NODE_A_BLE_TX_DIAG_CONTEXT_COMPLETED;
		saturating_increment(diagnostics,
				     &diagnostics->totals.notify_completed);
		note_completion_age(diagnostics,
				    cycles_to_us_u32(diagnostics, age_cycles));
		update_owned_count(diagnostics, false);
		release_deferred_completion = true;
	}
	k_spin_unlock(&diagnostics->lock, key);
	return release_deferred_completion;
}

void node_a_ble_tx_diagnostics_note_schedule_result(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	bool retry_schedule,
	int return_code)
{
	k_spinlock_key_t key;

	if ((diagnostics == NULL) || (submission == NULL) || (return_code >= 0)) {
		return;
	}

	key = k_spin_lock(&diagnostics->lock);
	if (retry_schedule) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.retry_schedule_failures);
		diagnostics->totals.last_retry_schedule_rc = (int32_t)return_code;
	} else {
		saturating_increment(diagnostics,
				     &diagnostics->totals.initial_schedule_failures);
		diagnostics->totals.last_initial_schedule_rc = (int32_t)return_code;
	}
	k_spin_unlock(&diagnostics->lock, key);
}

bool node_a_ble_tx_diagnostics_submission_fail(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t connection_generation)
{
	k_spinlock_key_t key;
	bool failed = false;

	if ((diagnostics == NULL) || (submission == NULL)) {
		return false;
	}

	key = k_spin_lock(&diagnostics->lock);
	if ((submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_PRE_ACCEPT) &&
	    (submission->connection_generation == connection_generation)) {
		submission->state = NODE_A_BLE_TX_DIAG_CONTEXT_REJECTED;
		saturating_increment(diagnostics,
				     &diagnostics->totals.notify_final_failures);
		saturating_increment(diagnostics,
				     &diagnostics->totals.notify_packet_drops);
		update_owned_count(diagnostics, false);
		failed = true;
	}
	k_spin_unlock(&diagnostics->lock, key);
	return failed;
}

enum node_a_ble_tx_diag_callback_result
node_a_ble_tx_diagnostics_complete(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t callback_generation,
	uint32_t completion_cycles)
{
	k_spinlock_key_t key;
	enum node_a_ble_tx_diag_callback_result result =
		NODE_A_BLE_TX_DIAG_CALLBACK_REJECTED;

	if ((diagnostics == NULL) || (submission == NULL)) {
		return NODE_A_BLE_TX_DIAG_CALLBACK_REJECTED;
	}

	key = k_spin_lock(&diagnostics->lock);
	if ((submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_PRE_ACCEPT) &&
	    submission->notify_call_active &&
	    (submission->connection_generation == callback_generation)) {
		/* Keep the callback's user_data slot owned until the submitter has
		 * recorded bt_gatt_notify_cb()'s return code.
		 */
		submission->state = NODE_A_BLE_TX_DIAG_CONTEXT_CALLBACK_PENDING;
		submission->callback_pending_cycles = completion_cycles;
		result = NODE_A_BLE_TX_DIAG_CALLBACK_DEFERRED;
	} else if ((submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_FREE) ||
	    (submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_REJECTED) ||
	    (submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_COMPLETED)) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.callbacks_unexpected);
	} else if ((submission->connection_generation != callback_generation) ||
		   ((submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_ACCEPTED) &&
		    (submission->accepted_generation != callback_generation))) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.callbacks_stale_generation);
	} else if (submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_CANCELED) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.callbacks_after_cancel);
	} else if (submission->state != NODE_A_BLE_TX_DIAG_CONTEXT_ACCEPTED) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.callbacks_unexpected);
	} else if (diagnostics->totals.in_flight_current == 0U) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.callbacks_unexpected);
	} else {
		const uint32_t age_cycles =
			completion_cycles - submission->accepted_at_cycles;

		submission->state = NODE_A_BLE_TX_DIAG_CONTEXT_COMPLETED;
		diagnostics->totals.in_flight_current--;
			saturating_increment(diagnostics,
					     &diagnostics->totals.notify_completed);
		note_completion_age(diagnostics,
				    cycles_to_us_u32(diagnostics,
						     age_cycles));
		update_owned_count(diagnostics, false);
		result = NODE_A_BLE_TX_DIAG_CALLBACK_COMPLETED;
	}
	k_spin_unlock(&diagnostics->lock, key);
	return result;
}

void node_a_ble_tx_diagnostics_note_callback_rejected(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t callback_generation,
	bool completion_was_cancelled)
{
	k_spinlock_key_t key;

	if ((diagnostics == NULL) || (submission == NULL)) {
		return;
	}

	key = k_spin_lock(&diagnostics->lock);
	if (callback_generation != submission->connection_generation) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.callbacks_stale_generation);
	} else if (completion_was_cancelled ||
		   (submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_CANCELED)) {
		saturating_increment(diagnostics,
				     &diagnostics->totals.callbacks_after_cancel);
	} else {
		saturating_increment(diagnostics,
				     &diagnostics->totals.callbacks_unexpected);
	}
	k_spin_unlock(&diagnostics->lock, key);
}

void node_a_ble_tx_diagnostics_note_packet_drop(
	struct node_a_ble_tx_diagnostics *diagnostics)
{
	k_spinlock_key_t key;

	if (diagnostics == NULL) {
		return;
	}

	key = k_spin_lock(&diagnostics->lock);
	saturating_increment(diagnostics,
			     &diagnostics->totals.notify_packet_drops);
	k_spin_unlock(&diagnostics->lock, key);
}

bool node_a_ble_tx_diagnostics_cancel(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t connection_generation)
{
	k_spinlock_key_t key;
	bool canceled = false;

	if ((diagnostics == NULL) || (submission == NULL)) {
		return false;
	}

	key = k_spin_lock(&diagnostics->lock);
	if (((submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_PRE_ACCEPT) ||
	     (submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_ACCEPTED)) &&
	    (submission->connection_generation == connection_generation)) {
		if ((submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_ACCEPTED) &&
		    (diagnostics->totals.in_flight_current > 0U)) {
			diagnostics->totals.in_flight_current--;
		}
		submission->state = NODE_A_BLE_TX_DIAG_CONTEXT_CANCELED;
		saturating_increment(diagnostics,
				     &diagnostics->totals.notify_cancelled);
		canceled = true;
	}
	k_spin_unlock(&diagnostics->lock, key);
	return canceled;
}

bool node_a_ble_tx_diagnostics_reclaim(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t connection_generation)
{
	k_spinlock_key_t key;
	bool reclaimed = false;

	if ((diagnostics == NULL) || (submission == NULL)) {
		return false;
	}

	key = k_spin_lock(&diagnostics->lock);
	if ((submission->state == NODE_A_BLE_TX_DIAG_CONTEXT_CANCELED) &&
	    (submission->connection_generation == connection_generation)) {
		/* Reclaim runs only after delayed submit work has drained. If no
		 * successful GATT return was observed, this dequeued packet was never
		 * accepted and its loss is now definite. An accepted cancellation has
		 * an unknown delivery outcome and remains cancellation-only.
		 */
		if (submission->accepted_generation != connection_generation) {
			saturating_increment(
				diagnostics,
				&diagnostics->totals.notify_packet_drops);
		}
		submission->state = NODE_A_BLE_TX_DIAG_CONTEXT_FREE;
		update_owned_count(diagnostics, false);
		reclaimed = true;
	}
	k_spin_unlock(&diagnostics->lock, key);
	return reclaimed;
}

void node_a_ble_tx_diagnostics_set_connection_generation(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t connection_generation)
{
	k_spinlock_key_t key;

	if (diagnostics == NULL) {
		return;
	}

	key = k_spin_lock(&diagnostics->lock);
	diagnostics->totals.connection_generation = connection_generation;
	k_spin_unlock(&diagnostics->lock, key);
}

bool node_a_ble_tx_diagnostics_window_wait_begin(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t start_cycles)
{
	k_spinlock_key_t key;
	bool began;

	if (diagnostics == NULL) {
		return false;
	}

	key = k_spin_lock(&diagnostics->lock);
	const bool was_active = diagnostics->completion_window_wait_active;

	window_wait_begin_locked(diagnostics, start_cycles);
	began = !was_active && diagnostics->completion_window_wait_active;
	k_spin_unlock(&diagnostics->lock, key);
	return began;
}

bool node_a_ble_tx_diagnostics_window_wait_end(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t end_cycles)
{
	k_spinlock_key_t key;
	bool active;

	if (diagnostics == NULL) {
		return false;
	}

	key = k_spin_lock(&diagnostics->lock);
	active = diagnostics->completion_window_wait_active;
	window_wait_end_locked(diagnostics, end_cycles);
	k_spin_unlock(&diagnostics->lock, key);
	return active;
}

void node_a_ble_tx_diagnostics_window_wait_update(
	struct node_a_ble_tx_diagnostics *diagnostics,
	bool queued_work_pending,
	uint32_t now_cycles)
{
	k_spinlock_key_t key;

	if (diagnostics == NULL) {
		return;
	}

	key = k_spin_lock(&diagnostics->lock);
	if (queued_work_pending &&
	    (diagnostics->completion_window_owned_current ==
	     diagnostics->completion_window_capacity)) {
		window_wait_begin_locked(diagnostics, now_cycles);
	} else {
		window_wait_end_locked(diagnostics, now_cycles);
	}
	k_spin_unlock(&diagnostics->lock, key);
}

void node_a_ble_tx_diagnostics_snapshot_get(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diagnostics_snapshot *snapshot)
{
	k_spinlock_key_t key;

	if ((diagnostics == NULL) || (snapshot == NULL)) {
		return;
	}

	key = k_spin_lock(&diagnostics->lock);
	*snapshot = diagnostics->totals;
	snapshot->completion_window_owned_current =
		diagnostics->completion_window_owned_current;
	k_spin_unlock(&diagnostics->lock, key);
}
