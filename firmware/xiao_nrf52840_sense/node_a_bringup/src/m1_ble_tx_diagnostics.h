/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_M1_BLE_TX_DIAGNOSTICS_H_
#define KINEIMU_NODE_A_M1_BLE_TX_DIAGNOSTICS_H_

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/spinlock.h>

#define NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS 16U
#define NODE_A_BLE_TX_DIAG_LATENCY_BUCKETS 8U

enum node_a_ble_tx_diag_context_state {
	NODE_A_BLE_TX_DIAG_CONTEXT_FREE = 0,
	NODE_A_BLE_TX_DIAG_CONTEXT_PRE_ACCEPT,
	NODE_A_BLE_TX_DIAG_CONTEXT_CALLBACK_PENDING,
	NODE_A_BLE_TX_DIAG_CONTEXT_ACCEPTED,
	NODE_A_BLE_TX_DIAG_CONTEXT_COMPLETED,
	NODE_A_BLE_TX_DIAG_CONTEXT_CANCELED,
	NODE_A_BLE_TX_DIAG_CONTEXT_REJECTED,
};

enum node_a_ble_tx_diag_callback_result {
	NODE_A_BLE_TX_DIAG_CALLBACK_REJECTED = 0,
	NODE_A_BLE_TX_DIAG_CALLBACK_COMPLETED,
	/* The submitter records the API return and then releases the owned slot. */
	NODE_A_BLE_TX_DIAG_CALLBACK_DEFERRED,
};

struct node_a_ble_tx_diag_return_code {
	int32_t code;
	uint32_t count;
	bool occupied;
};

struct node_a_ble_tx_diag_latency_stats {
	uint32_t count;
	uint32_t last_us;
	uint32_t min_us;
	uint32_t max_us;
	uint64_t total_us;
	/* <1, 1-<2.5, 2.5-<5, 5-<10, 10-<25, 25-<50, 50-<100, >=100 ms */
	uint32_t buckets[NODE_A_BLE_TX_DIAG_LATENCY_BUCKETS];
};

struct node_a_ble_tx_diagnostics_snapshot {
	/* Boot scope: cumulative until reboot; generation labels the current stream. */
	uint64_t boot_id;
	uint32_t connection_generation;
	uint32_t notify_submit_calls;
	uint32_t notify_accepted;
	/* Terminal service failures and definite post-dequeue packet losses. */
	uint32_t notify_final_failures;
	uint32_t notify_packet_drops;
	int32_t notify_last_return_code;
	struct node_a_ble_tx_diag_return_code
		notify_return_codes[NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS];
	uint32_t notify_return_code_overflow;
	uint32_t notify_ret_enomem;
	uint32_t notify_ret_eagain;
	/* Actual GATT invocations after the first attempt of a context. */
	uint32_t retry_attempts;
	uint32_t initial_schedule_failures;
	uint32_t retry_schedule_failures;
	int32_t last_initial_schedule_rc;
	int32_t last_retry_schedule_rc;
	uint32_t notify_completed;
	uint32_t notify_cancelled;
	uint32_t callbacks_stale_generation;
	uint32_t callbacks_after_cancel;
	uint32_t callbacks_unexpected;
	uint32_t completion_window_owned_current;
	uint32_t in_flight_current;
	uint32_t in_flight_peak;
	uint32_t completion_window_full_count;
	uint64_t completion_window_wait_total_us;
	struct node_a_ble_tx_diag_latency_stats completion_age;
	bool counters_saturated;
};

/* One instance follows each fixed completion-window slot. */
struct node_a_ble_tx_diag_submission {
	enum node_a_ble_tx_diag_context_state state;
	uint32_t connection_generation;
	uint32_t accepted_generation;
	uint32_t notify_attempts;
	uint32_t accepted_at_cycles;
	uint32_t callback_pending_cycles;
	bool notify_call_active;
};

struct node_a_ble_tx_diagnostics {
	struct k_spinlock lock;
	struct node_a_ble_tx_diagnostics_snapshot totals;
	uint32_t cycle_frequency_hz;
	uint32_t completion_window_capacity;
	uint32_t completion_window_owned_current;
	uint32_t completion_window_wait_started_cycles;
	bool completion_window_wait_active;
};

void node_a_ble_tx_diagnostics_init(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint64_t boot_id,
	uint32_t connection_generation,
	uint32_t cycle_frequency_hz,
	uint32_t completion_window_capacity);

bool node_a_ble_tx_diagnostics_submission_begin(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t connection_generation);

/* Call before bt_gatt_notify_cb(); rejects stale or no-longer-owned contexts. */
bool node_a_ble_tx_diagnostics_notify_call_begin(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission);

/* Call after bt_gatt_notify_cb() returns. Returns true when it resolves an
 * early callback and the submitter must release the completion slot.
 */
bool node_a_ble_tx_diagnostics_note_notify_result(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	int return_code,
	uint32_t returned_at_cycles);

/* retry_schedule selects the delayed retry path; preserve the exact work rc. */
void node_a_ble_tx_diagnostics_note_schedule_result(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	bool retry_schedule,
	int return_code);

/* Call when a pre-accept submission reaches a terminal failure and releases its slot. */
bool node_a_ble_tx_diagnostics_submission_fail(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t connection_generation);

/* callback_generation is captured for that accepted call, never re-read from a reused slot. */
enum node_a_ble_tx_diag_callback_result
node_a_ble_tx_diagnostics_complete(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t callback_generation,
	uint32_t completion_cycles);

/* Record a callback rejected by the completion owner without changing ownership. */
void node_a_ble_tx_diagnostics_note_callback_rejected(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t callback_generation,
	bool completion_was_cancelled);

/* Record a packet discarded after dequeue without entering the notify API. */
void node_a_ble_tx_diagnostics_note_packet_drop(
	struct node_a_ble_tx_diagnostics *diagnostics);

bool node_a_ble_tx_diagnostics_cancel(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t connection_generation);

bool node_a_ble_tx_diagnostics_reclaim(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diag_submission *submission,
	uint32_t connection_generation);

void node_a_ble_tx_diagnostics_set_connection_generation(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t connection_generation);

/* One begin/end pair represents a single contiguous wait for a free slot. */
bool node_a_ble_tx_diagnostics_window_wait_begin(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t start_cycles);
bool node_a_ble_tx_diagnostics_window_wait_end(
	struct node_a_ble_tx_diagnostics *diagnostics,
	uint32_t end_cycles);
/* Update the active wait episode from the current queue-pending state. */
void node_a_ble_tx_diagnostics_window_wait_update(
	struct node_a_ble_tx_diagnostics *diagnostics,
	bool queued_work_pending,
	uint32_t now_cycles);

void node_a_ble_tx_diagnostics_snapshot_get(
	struct node_a_ble_tx_diagnostics *diagnostics,
	struct node_a_ble_tx_diagnostics_snapshot *snapshot);

#endif /* KINEIMU_NODE_A_M1_BLE_TX_DIAGNOSTICS_H_ */
