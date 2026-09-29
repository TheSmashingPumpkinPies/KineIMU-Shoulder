/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <string.h>

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/hci.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/bluetooth/att.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys_clock.h>
#include <zephyr/sys/time_units.h>
#include <zephyr/sys/util.h>

#include "m1_ble_advertising.h"
#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
#include "m1_conn_param_experiment.h"
#endif
#include "m1_ble_service.h"
#include "m1_ble_tx_completion.h"
#include "m1_ble_tx_diagnostics.h"
#include "m1_ble_tx_queue.h"
#include "m1_ble_transport_policy.h"
#include "node_config.h"

#define NODE_A_BLE_SERVICE_UUID_VAL \
	BT_UUID_128_ENCODE(0xf7d20001, 0x4b49, 0x4e45, 0x494d, 0x552d53484c44)
#define NODE_A_BLE_IDENTITY_UUID_VAL \
	BT_UUID_128_ENCODE(0xf7d20002, 0x4b49, 0x4e45, 0x494d, 0x552d53484c44)
#define NODE_A_BLE_TELEMETRY_UUID_VAL \
	BT_UUID_128_ENCODE(0xf7d20003, 0x4b49, 0x4e45, 0x494d, 0x552d53484c44)
#define NODE_A_BLE_CLOCK_UUID_VAL \
	BT_UUID_128_ENCODE(0xf7d20004, 0x4b49, 0x4e45, 0x494d, 0x552d53484c44)
#define NODE_A_BLE_STATUS_UUID_VAL \
	BT_UUID_128_ENCODE(0xf7d20005, 0x4b49, 0x4e45, 0x494d, 0x552d53484c44)

#define NODE_A_BLE_IDENTITY_ATTR_INDEX 2U
#define NODE_A_BLE_TELEMETRY_ATTR_INDEX 5U
#define NODE_A_BLE_CLOCK_ATTR_INDEX 8U
#define NODE_A_BLE_STATUS_ATTR_INDEX 11U
#define NODE_A_BLE_TX_WORKER_STACK_SIZE 1536U
#define NODE_A_BLE_TX_WORKER_PRIORITY 5

static const struct bt_uuid_128 service_uuid = BT_UUID_INIT_128(
	NODE_A_BLE_SERVICE_UUID_VAL);
static const struct bt_uuid_128 identity_uuid = BT_UUID_INIT_128(
	NODE_A_BLE_IDENTITY_UUID_VAL);
static const struct bt_uuid_128 telemetry_uuid = BT_UUID_INIT_128(
	NODE_A_BLE_TELEMETRY_UUID_VAL);
static const struct bt_uuid_128 clock_uuid = BT_UUID_INIT_128(
	NODE_A_BLE_CLOCK_UUID_VAL);
static const struct bt_uuid_128 status_uuid = BT_UUID_INIT_128(
	NODE_A_BLE_STATUS_UUID_VAL);

static uint8_t identity_value[NODE_A_BLE_IDENTITY_CONFIG_SIZE];
static uint8_t status_value[NODE_A_BLE_STATUS_SIZE];
static uint8_t indication_value[NODE_A_BLE_IDENTITY_CONFIG_SIZE];
static struct node_a_ble_identity_config identity_config;
K_MUTEX_DEFINE(value_lock);
static atomic_t link_connected;
static atomic_t telemetry_notifications_enabled;
static atomic_t identity_indications_enabled;
static atomic_t clock_indications_enabled;
static atomic_t status_indications_enabled;
static atomic_t link_att_mtu;
static atomic_t indication_in_flight;
K_SEM_DEFINE(bluetooth_ready_sem, 0, 1);
static int bluetooth_start_error;
static bool callbacks_registered;
static struct bt_gatt_indicate_params indication_params;
static struct node_a_ble_tx_queue tx_queue;
static struct node_a_ble_service_tx_stats tx_stats;
static struct node_a_ble_tx_diagnostics tx_diagnostics;
static struct k_spinlock tx_stats_lock;
#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
static struct k_spinlock conn_param_request_lock;
static enum node_a_conn_param_request_mode conn_param_request_mode =
	NODE_A_CONN_PARAM_REQUEST_OFF;
static bool conn_param_request_connection_active;
#endif
static bool tx_queue_initialized;
#define NODE_A_BLE_TX_SUBMISSION_COUNT CONFIG_BT_ATT_TX_COUNT
#define NODE_A_BLE_TX_RETRY_DELAY K_MSEC(5)

BUILD_ASSERT(NODE_A_BLE_TX_SUBMISSION_COUNT > 0,
	     "BLE TX completion window must be non-zero");

struct node_a_ble_tx_submission {
	struct node_a_ble_tx_completion completion;
	struct node_a_ble_tx_diag_submission diagnostics;
	struct node_a_ble_tx_packet packet;
	struct bt_gatt_notify_params params;
	struct k_work_delayable submit_work;
};
static struct node_a_ble_tx_submission tx_submissions[
	NODE_A_BLE_TX_SUBMISSION_COUNT];
K_SEM_DEFINE(tx_notify_slot_available, NODE_A_BLE_TX_SUBMISSION_COUNT,
	     NODE_A_BLE_TX_SUBMISSION_COUNT);
static struct k_work tx_notify_reclaim_work;
static atomic_t tx_stopping;
static struct node_a_ble_advertising_restart advertising_restart;
K_THREAD_STACK_DEFINE(tx_worker_stack, NODE_A_BLE_TX_WORKER_STACK_SIZE);
static struct k_thread tx_worker_thread;

#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
int node_a_ble_service_set_conn_param_request_mode(
	enum node_a_conn_param_request_mode mode)
{
	enum node_a_conn_param_request_mode updated_mode;
	k_spinlock_key_t key = k_spin_lock(&conn_param_request_lock);
	int rc;

	updated_mode = conn_param_request_mode;
	rc = node_a_conn_param_experiment_set_mode(
		&updated_mode, mode, conn_param_request_connection_active);
	if (rc == 0) {
		conn_param_request_mode = updated_mode;
	}
	k_spin_unlock(&conn_param_request_lock, key);
	return rc;
}

enum node_a_conn_param_request_mode
node_a_ble_service_conn_param_request_mode_get(void)
{
	enum node_a_conn_param_request_mode mode;
	k_spinlock_key_t key = k_spin_lock(&conn_param_request_lock);

	mode = conn_param_request_mode;
	k_spin_unlock(&conn_param_request_lock, key);
	return mode;
}

static int request_root_cause_connection_parameters(void *connection,
							   void *context)
{
	const struct bt_le_conn_param parameters = {
		.interval_min = BT_GAP_MS_TO_CONN_INTERVAL(15),
		.interval_max = BT_GAP_MS_TO_CONN_INTERVAL(15),
		.latency = 0U,
		.timeout = BT_GAP_MS_TO_CONN_TIMEOUT(420),
	};

	ARG_UNUSED(context);
	return bt_conn_le_param_update(connection, &parameters);
}
#endif

static uint64_t now_us(void)
{
	return k_ticks_to_us_floor64(k_uptime_ticks());
}

static void tx_saturating_increment(uint32_t *counter, bool *saturated)
{
	if (*counter < UINT32_MAX) {
		(*counter)++;
	}
	if (*counter == UINT32_MAX) {
		*saturated = true;
	}
}

static void tx_note_notify(uint32_t duration_us, int ret)
{
	k_spinlock_key_t key = k_spin_lock(&tx_stats_lock);

	tx_saturating_increment(&tx_stats.notify_calls,
					&tx_stats.counters_saturated);
	if (ret < 0) {
		tx_saturating_increment(&tx_stats.notify_failures,
						&tx_stats.counters_saturated);
	}
	tx_stats.notify_last_duration_us = duration_us;
	if (duration_us > tx_stats.notify_max_duration_us) {
		tx_stats.notify_max_duration_us = duration_us;
	}
	if (UINT64_MAX - tx_stats.notify_total_duration_us < duration_us) {
		tx_stats.notify_total_duration_us = UINT64_MAX;
		tx_stats.counters_saturated = true;
	} else {
		tx_stats.notify_total_duration_us += duration_us;
	}
	k_spin_unlock(&tx_stats_lock, key);
}

static void tx_update_completion_window_wait(void)
{
	if (!tx_queue_initialized) {
		return;
	}

	/* Recheck after the update so enqueue and dequeue cannot leave a stale
	 * wait episode active when the last queued packet has just been removed.
	 */
	for (uint32_t attempt = 0U; attempt < 2U; attempt++) {
		const bool queued_work_pending =
			node_a_ble_tx_queue_pending_count_get(&tx_queue) > 0U;

		node_a_ble_tx_diagnostics_window_wait_update(
			&tx_diagnostics, queued_work_pending, k_cycle_get_32());
		if ((node_a_ble_tx_queue_pending_count_get(&tx_queue) > 0U) ==
		    queued_work_pending) {
			return;
		}
	}
	node_a_ble_tx_diagnostics_window_wait_update(
		&tx_diagnostics,
		node_a_ble_tx_queue_pending_count_get(&tx_queue) > 0U,
		k_cycle_get_32());
}

static int tx_submit_notify(struct node_a_ble_tx_submission *submission);

static bool tx_finish_submission(struct node_a_ble_tx_submission *submission,
				 int ret)
{
	uint32_t elapsed_cycles = 0U;
	const uint32_t generation = node_a_ble_tx_completion_generation_get(
		&submission->completion);

	if (!node_a_ble_tx_completion_complete(&submission->completion,
						      generation, k_cycle_get_32(),
						      &elapsed_cycles)) {
		return false;
	}
	if (!node_a_ble_tx_diagnostics_submission_fail(
		    &tx_diagnostics, &submission->diagnostics, generation)) {
		printk("KineIMU BLE TX diagnostic failure ownership mismatch\n");
	}

	tx_note_notify(k_cyc_to_us_floor32(elapsed_cycles), ret);
	if (ret < 0) {
		node_a_ble_tx_queue_note_transport_loss(&tx_queue);
	}
	tx_update_completion_window_wait();
	k_sem_give(&tx_notify_slot_available);
	return true;
}

static void tx_notify_complete(struct bt_conn *conn, void *user_data)
{
	struct node_a_ble_tx_submission *submission = user_data;
	uint32_t elapsed_cycles = 0U;
	uint32_t generation;
	uint32_t completion_cycles;
	enum node_a_ble_tx_diag_callback_result diagnostic_result;

	ARG_UNUSED(conn);
	if (submission == NULL) {
		return;
	}

	generation = node_a_ble_tx_completion_generation_get(
		&submission->completion);
	completion_cycles = k_cycle_get_32();
	if (!node_a_ble_tx_completion_complete(&submission->completion,
						      generation, completion_cycles,
						      &elapsed_cycles)) {
		const bool completion_was_cancelled =
			node_a_ble_tx_completion_state_get(&submission->completion) ==
			NODE_A_BLE_TX_COMPLETION_CANCELED;

		node_a_ble_tx_diagnostics_note_callback_rejected(
			&tx_diagnostics, &submission->diagnostics, generation,
			completion_was_cancelled);
		/* Disconnect cancellation or an already-consumed completion owns the
		 * slot. The callback has no context to release. */
		return;
	}
	diagnostic_result = node_a_ble_tx_diagnostics_complete(
		&tx_diagnostics, &submission->diagnostics, generation,
		completion_cycles);
	if (diagnostic_result == NODE_A_BLE_TX_DIAG_CALLBACK_REJECTED) {
		printk("KineIMU BLE TX diagnostic completion ownership mismatch\n");
	}

	tx_note_notify(k_cyc_to_us_floor32(elapsed_cycles), 0);
	tx_update_completion_window_wait();
	if (diagnostic_result == NODE_A_BLE_TX_DIAG_CALLBACK_DEFERRED) {
		/* The submitter still owns the context until it records the API return. */
		return;
	}
	/* Keep this last: the worker may overwrite the packet after the slot is
	 * released, but the callback must not touch the containing object again. */
	k_sem_give(&tx_notify_slot_available);
}

static void tx_notify_reclaim_work_handler(struct k_work *work)
{
	struct k_work_sync sync;
	uint32_t generation;

	ARG_UNUSED(work);
	for (size_t index = 0U; index < ARRAY_SIZE(tx_submissions); index++) {
		struct node_a_ble_tx_submission *submission = &tx_submissions[index];

		if (node_a_ble_tx_completion_state_get(&submission->completion) !=
		    NODE_A_BLE_TX_COMPLETION_CANCELED) {
			continue;
		}
		(void)k_work_cancel_delayable_sync(&submission->submit_work, &sync);
		generation = node_a_ble_tx_completion_generation_get(
			&submission->completion);
		if (node_a_ble_tx_completion_reclaim(&submission->completion,
						    generation)) {
			if (!node_a_ble_tx_diagnostics_reclaim(
				    &tx_diagnostics, &submission->diagnostics,
				    generation)) {
				printk("KineIMU BLE TX diagnostic reclaim mismatch\n");
			}
			/* This work is submitted after the disconnect path has released
			 * ATT buffers. Canceling the slot work first prevents a delayed
			 * resource retry from being carried into a new generation. */
			tx_update_completion_window_wait();
			k_sem_give(&tx_notify_slot_available);
		}
	}
}

static void tx_cancel_inflight(void)
{
	bool reclaim_needed = false;

	for (size_t index = 0U; index < ARRAY_SIZE(tx_submissions); index++) {
		struct node_a_ble_tx_submission *submission = &tx_submissions[index];
		uint32_t elapsed_cycles = 0U;
		const uint32_t generation =
			node_a_ble_tx_completion_generation_get(
				&submission->completion);

		if (!node_a_ble_tx_completion_cancel(&submission->completion,
						    generation, k_cycle_get_32(),
						    &elapsed_cycles)) {
			continue;
		}
		if (!node_a_ble_tx_diagnostics_cancel(
			    &tx_diagnostics, &submission->diagnostics,
			    generation)) {
			printk("KineIMU BLE TX diagnostic cancel mismatch\n");
		}

		tx_note_notify(k_cyc_to_us_floor32(elapsed_cycles), -ENOTCONN);
		if (tx_queue_initialized) {
			node_a_ble_tx_queue_note_transport_loss(&tx_queue);
		}
		/* The callback may be suppressed when ATT tears down its bearer. The
		 * slot is retained until reclaim work drains the old callback owner. */
		reclaim_needed = true;
	}

	if (reclaim_needed && k_work_submit(&tx_notify_reclaim_work) < 0) {
		printk("KineIMU BLE TX reclaim schedule failed\n");
	}
}

static void tx_notify_submit_work_handler(struct k_work *work)
{
	struct node_a_ble_tx_submission *submission = CONTAINER_OF(
		work, struct node_a_ble_tx_submission, submit_work.work);
	int ret;

	if (node_a_ble_tx_completion_state_get(&submission->completion) !=
	    NODE_A_BLE_TX_COMPLETION_IN_FLIGHT) {
		return;
	}
	if (atomic_get(&tx_stopping) ||
	    !node_a_ble_tx_queue_packet_is_current(&tx_queue,
						&submission->packet) ||
	    !node_a_ble_service_is_stream_ready()) {
		(void)tx_finish_submission(submission, -ENOTCONN);
		return;
	}

	/* This handler runs on Zephyr's system workqueue. The pinned ATT host
	 * therefore uses K_NO_WAIT for its TX buffer allocation. A full ATT TX
	 * pool is retried later while other completion-owned slots continue to
	 * feed the stack. */
	ret = tx_submit_notify(submission);
	if ((ret == -ENOMEM) || (ret == -EAGAIN)) {
		if (node_a_ble_tx_completion_state_get(&submission->completion) !=
		    NODE_A_BLE_TX_COMPLETION_IN_FLIGHT) {
			return;
		}
		node_a_ble_tx_queue_note_transport_loss(&tx_queue);
		ret = k_work_reschedule(&submission->submit_work,
					NODE_A_BLE_TX_RETRY_DELAY);
		node_a_ble_tx_diagnostics_note_schedule_result(
			&tx_diagnostics, &submission->diagnostics, true, ret);
		if (ret < 0) {
			(void)tx_finish_submission(submission, -EIO);
		}
		return;
	}
	if (ret < 0) {
		(void)tx_finish_submission(submission, ret);
	}
}

static void tx_queue_sync_connection_state(void)
{
	if (!tx_queue_initialized) {
		return;
	}

	if (atomic_get(&link_connected) &&
	    atomic_get(&telemetry_notifications_enabled)) {
		(void)node_a_ble_tx_queue_open(&tx_queue);
	} else {
		node_a_ble_tx_queue_disconnect(&tx_queue);
	}
	node_a_ble_tx_diagnostics_set_connection_generation(
		&tx_diagnostics,
		node_a_ble_tx_queue_connection_generation_get(&tx_queue));
	tx_update_completion_window_wait();
}

static void tx_worker(void *arg1, void *arg2, void *arg3)
{
	struct node_a_ble_tx_queue *queue = arg1;
	struct node_a_ble_tx_packet packet;
	struct node_a_ble_tx_submission *submission;
	int submit_ret;

	ARG_UNUSED(arg2);
	ARG_UNUSED(arg3);

	while (true) {
		if (k_sem_take(&tx_notify_slot_available, K_FOREVER) != 0) {
			continue;
		}
		if (!node_a_ble_tx_queue_get(queue, &packet, K_FOREVER)) {
			k_sem_give(&tx_notify_slot_available);
			if (node_a_ble_tx_queue_is_stopped(queue)) {
				return;
			}
			continue;
		}

		/* The queue copies the packet into this worker-owned object. A packet
		 * dequeued before disconnect is rejected by generation, so it cannot
		 * cross into a later connection. */
		if (atomic_get(&tx_stopping) ||
		    !node_a_ble_tx_queue_packet_is_current(queue, &packet) ||
		    !node_a_ble_service_is_stream_ready()) {
			node_a_ble_tx_queue_note_packet_discarded(queue, &packet);
			node_a_ble_tx_diagnostics_note_packet_drop(&tx_diagnostics);
			k_sem_give(&tx_notify_slot_available);
			tx_update_completion_window_wait();
			continue;
		}

		/* Keep packet bytes and callback metadata alive until the ATT completion
		 * callback. The fixed completion window is separate from the existing
		 * four-slot acquisition queue, so several ATT PDUs can be queued without
		 * blocking this worker on one slow completion. */
		submission = NULL;
		for (size_t index = 0U; index < ARRAY_SIZE(tx_submissions); index++) {
			struct node_a_ble_tx_submission *candidate =
				&tx_submissions[index];

			if (!node_a_ble_tx_completion_begin(
					&candidate->completion,
					packet.connection_generation, k_cycle_get_32())) {
				continue;
			}
			submission = candidate;
			break;
		}
		if (submission == NULL) {
			node_a_ble_tx_queue_note_packet_discarded(queue, &packet);
			node_a_ble_tx_diagnostics_note_packet_drop(&tx_diagnostics);
			k_sem_give(&tx_notify_slot_available);
			tx_update_completion_window_wait();
			continue;
		}
		if (!node_a_ble_tx_diagnostics_submission_begin(
			    &tx_diagnostics, &submission->diagnostics,
			    packet.connection_generation)) {
			(void)node_a_ble_tx_completion_complete(
				&submission->completion,
				packet.connection_generation, k_cycle_get_32(), NULL);
			node_a_ble_tx_queue_note_packet_discarded(queue, &packet);
			node_a_ble_tx_diagnostics_note_packet_drop(&tx_diagnostics);
			k_sem_give(&tx_notify_slot_available);
			tx_update_completion_window_wait();
			continue;
		}

		submission->packet = packet;
		memset(&submission->params, 0, sizeof(submission->params));
		submission->params.data = submission->packet.data;
		submission->params.len = submission->packet.size;
		submission->params.func = tx_notify_complete;
		submission->params.user_data = submission;
		submit_ret = k_work_reschedule(&submission->submit_work, K_NO_WAIT);
		if (submit_ret < 0) {
			node_a_ble_tx_diagnostics_note_schedule_result(
				&tx_diagnostics, &submission->diagnostics, false,
				submit_ret);
			(void)tx_finish_submission(submission, submit_ret);
		} else {
			tx_update_completion_window_wait();
		}
	}
}

static ssize_t read_identity(struct bt_conn *conn,
			     const struct bt_gatt_attr *attr, void *buf,
			     uint16_t len, uint16_t offset)
{
	ssize_t ret;

	ARG_UNUSED(attr);
	k_mutex_lock(&value_lock, K_FOREVER);
	ret = bt_gatt_attr_read(conn, attr, buf, len, offset,
				identity_value, sizeof(identity_value));
	k_mutex_unlock(&value_lock);
	return ret;
}

static ssize_t read_status(struct bt_conn *conn,
			   const struct bt_gatt_attr *attr, void *buf,
			   uint16_t len, uint16_t offset)
{
	ssize_t ret;

	k_mutex_lock(&value_lock, K_FOREVER);
	ret = bt_gatt_attr_read(conn, attr, buf, len, offset,
				status_value, sizeof(status_value));
	k_mutex_unlock(&value_lock);
	return ret;
}

static void identity_ccc_changed(const struct bt_gatt_attr *attr,
				 uint16_t value)
{
	ARG_UNUSED(attr);
	atomic_set(&identity_indications_enabled,
		   (value == BT_GATT_CCC_INDICATE) ? 1 : 0);
}

static void telemetry_ccc_changed(const struct bt_gatt_attr *attr,
				  uint16_t value)
{
	ARG_UNUSED(attr);
	atomic_set(&telemetry_notifications_enabled,
		   (value == BT_GATT_CCC_NOTIFY) ? 1 : 0);
	tx_queue_sync_connection_state();
}

static void clock_ccc_changed(const struct bt_gatt_attr *attr,
				      uint16_t value)
{
	ARG_UNUSED(attr);
	atomic_set(&clock_indications_enabled,
		   (value == BT_GATT_CCC_INDICATE) ? 1 : 0);
}

static void status_ccc_changed(const struct bt_gatt_attr *attr,
				       uint16_t value)
{
	ARG_UNUSED(attr);
	atomic_set(&status_indications_enabled,
		   (value == BT_GATT_CCC_INDICATE) ? 1 : 0);
}

static void indication_complete(struct bt_conn *conn,
				struct bt_gatt_indicate_params *params,
				uint8_t err)
{
	ARG_UNUSED(conn);
	ARG_UNUSED(params);
	if (err != 0U) {
		printk("KineIMU BLE indication failed ATT error=0x%02x\n", err);
	}
}

static void indication_destroy(struct bt_gatt_indicate_params *params)
{
	ARG_UNUSED(params);
	atomic_clear(&indication_in_flight);
}

static int begin_indication(const struct bt_gatt_attr *attr,
				const uint8_t *value, size_t value_size)
{
	int ret;

	if ((value == NULL) || (value_size == 0U) ||
	    (value_size > sizeof(indication_value))) {
		return -EINVAL;
	}
	if (!atomic_cas(&indication_in_flight, 0, 1)) {
		return -EBUSY;
	}

	k_mutex_lock(&value_lock, K_FOREVER);
	memcpy(indication_value, value, value_size);
	k_mutex_unlock(&value_lock);

	memset(&indication_params, 0, sizeof(indication_params));
	indication_params.attr = attr;
	indication_params.func = indication_complete;
	indication_params.destroy = indication_destroy;
	indication_params.data = indication_value;
	indication_params.len = (uint16_t)value_size;
	ret = bt_gatt_indicate(NULL, &indication_params);
	if (ret < 0) {
		atomic_clear(&indication_in_flight);
	}
	return ret;
}

static ssize_t write_clock_request(struct bt_conn *conn,
				   const struct bt_gatt_attr *attr,
				   const void *buf, uint16_t len,
				   uint16_t offset, uint8_t flags)
{
	const uint64_t device_receive_us = now_us();
	struct node_a_ble_clock_request request;
	struct node_a_ble_clock_response response;
	uint8_t encoded[NODE_A_BLE_CLOCK_RESPONSE_SIZE];
	size_t encoded_size;
	int ret;

	if ((flags & BT_GATT_WRITE_FLAG_PREPARE) != 0U) {
		return BT_GATT_ERR(BT_ATT_ERR_WRITE_REQ_REJECTED);
	}
	if (offset != 0U) {
		return BT_GATT_ERR(BT_ATT_ERR_INVALID_OFFSET);
	}
	if (len != NODE_A_BLE_CLOCK_REQUEST_SIZE) {
		return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
	}
	if (!atomic_get(&clock_indications_enabled)) {
		return BT_GATT_ERR(BT_ATT_ERR_CCC_IMPROPER_CONF);
	}
	if (!atomic_get(&link_connected)) {
		return BT_GATT_ERR(BT_ATT_ERR_UNLIKELY);
	}
	if (!atomic_cas(&indication_in_flight, 0, 1)) {
		return BT_GATT_ERR(BT_ATT_ERR_INSUFFICIENT_RESOURCES);
	}

	ret = node_a_ble_decode_clock_request(buf, len, &request);
	if (ret < 0) {
		atomic_clear(&indication_in_flight);
		return BT_GATT_ERR(BT_ATT_ERR_VALUE_NOT_ALLOWED);
	}

	response.transaction_id = request.transaction_id;
	response.host_send_ns = request.host_send_ns;
	k_mutex_lock(&value_lock, K_FOREVER);
	response.boot_id = identity_config.boot_id;
	response.clock_epoch = identity_config.clock_epoch;
	k_mutex_unlock(&value_lock);
	response.device_receive_us = device_receive_us;
	/* The final timestamp is captured immediately before the response is
	 * encoded and submitted. It is not a radio-air timestamp. */
	response.device_indication_queued_us = now_us();
	ret = node_a_ble_encode_clock_response(&response, encoded,
					       sizeof(encoded), &encoded_size);
	if (ret < 0) {
		atomic_clear(&indication_in_flight);
		return BT_GATT_ERR(BT_ATT_ERR_UNLIKELY);
	}

	/* The encoder needs an output length, but the response size is fixed. */
	k_mutex_lock(&value_lock, K_FOREVER);
	memcpy(indication_value, encoded, sizeof(encoded));
	k_mutex_unlock(&value_lock);
	memset(&indication_params, 0, sizeof(indication_params));
	indication_params.attr = attr;
	indication_params.func = indication_complete;
	indication_params.destroy = indication_destroy;
	indication_params.data = indication_value;
	indication_params.len = (uint16_t)encoded_size;
	ret = bt_gatt_indicate(conn, &indication_params);
	if (ret < 0) {
		atomic_clear(&indication_in_flight);
		return BT_GATT_ERR(BT_ATT_ERR_INSUFFICIENT_RESOURCES);
	}

	return len;
}

BT_GATT_SERVICE_DEFINE(node_a_ble_svc,
	BT_GATT_PRIMARY_SERVICE(&service_uuid),
	BT_GATT_CHARACTERISTIC(&identity_uuid.uuid,
			       BT_GATT_CHRC_READ | BT_GATT_CHRC_INDICATE,
			       BT_GATT_PERM_READ, read_identity, NULL, NULL),
	BT_GATT_CCC(identity_ccc_changed,
		   BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
	BT_GATT_CHARACTERISTIC(&telemetry_uuid.uuid,
			       BT_GATT_CHRC_NOTIFY,
			       BT_GATT_PERM_NONE, NULL, NULL, NULL),
	BT_GATT_CCC(telemetry_ccc_changed,
		   BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
	BT_GATT_CHARACTERISTIC(&clock_uuid.uuid,
			       BT_GATT_CHRC_WRITE | BT_GATT_CHRC_INDICATE,
			       BT_GATT_PERM_WRITE, NULL, write_clock_request, NULL),
	BT_GATT_CCC(clock_ccc_changed,
		   BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
	BT_GATT_CHARACTERISTIC(&status_uuid.uuid,
			       BT_GATT_CHRC_READ | BT_GATT_CHRC_INDICATE,
			       BT_GATT_PERM_READ, read_status, NULL, NULL),
	BT_GATT_CCC(status_ccc_changed,
		   BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
);

static void att_mtu_updated(struct bt_conn *conn, uint16_t tx, uint16_t rx)
{
	ARG_UNUSED(conn);
	ARG_UNUSED(rx);
	atomic_set(&link_att_mtu, tx);
	printk("KineIMU BLE ATT MTU TX=%u RX=%u\n", tx, rx);
}

static struct bt_gatt_cb gatt_callbacks = {
	.att_mtu_updated = att_mtu_updated,
};

static void request_advertising_restart(const char *reason);

static void log_link_info(struct bt_conn *conn, const char *event,
			  uint32_t firmware_uptime_ms)
{
	struct bt_conn_info info = {0};
	int info_rc = bt_conn_get_info(conn, &info);
	uint32_t interval_us = 0U;
	uint32_t supervision_timeout_us = 0U;
	uint16_t latency = 0U;
	uint8_t phy_valid = 0U;
	uint8_t phy_tx = 0U;
	uint8_t phy_rx = 0U;
	uint8_t dle_valid = 0U;
	uint16_t dle_tx_max_len = 0U;
	uint16_t dle_tx_max_time_us = 0U;
	uint16_t dle_rx_max_len = 0U;
	uint16_t dle_rx_max_time_us = 0U;

	if (info_rc == 0 && info.type == BT_CONN_TYPE_LE) {
		interval_us = info.le.interval_us;
		latency = info.le.latency;
		/* The public Zephyr field is in 10 ms units; publish SI microseconds. */
		supervision_timeout_us = (uint32_t)info.le.timeout * 10000U;
#if defined(CONFIG_BT_USER_PHY_UPDATE)
		if (info.le.phy != NULL) {
			phy_valid = 1U;
			phy_tx = info.le.phy->tx_phy;
			phy_rx = info.le.phy->rx_phy;
		}
#endif
#if defined(CONFIG_BT_USER_DATA_LEN_UPDATE)
		if (info.le.data_len != NULL) {
			dle_valid = 1U;
			dle_tx_max_len = info.le.data_len->tx_max_len;
			dle_tx_max_time_us = info.le.data_len->tx_max_time;
			dle_rx_max_len = info.le.data_len->rx_max_len;
			dle_rx_max_time_us = info.le.data_len->rx_max_time;
		}
#endif
	}

	printk("Node %s: BLE link event=%s firmware_uptime_ms=%u info_rc=%d "
	       "interval_us=%u latency=%u "
	       "supervision_timeout_us=%u phy_valid=%u phy_tx=%u phy_rx=%u "
	       "dle_valid=%u dle_tx_max_len=%u dle_tx_max_time_us=%u "
	       "dle_rx_max_len=%u dle_rx_max_time_us=%u\n",
	       KINEIMU_NODE_LABEL, event, firmware_uptime_ms, info_rc, interval_us, latency,
	       supervision_timeout_us, phy_valid, phy_tx, phy_rx, dle_valid,
	       dle_tx_max_len, dle_tx_max_time_us, dle_rx_max_len,
	       dle_rx_max_time_us);
}

static void le_param_updated(struct bt_conn *conn, uint16_t interval,
				      uint16_t latency, uint16_t timeout)
{
	uint32_t firmware_uptime_ms = k_uptime_get_32();

	printk("Node %s: BLE link parameter callback interval_units=%u latency=%u "
	       "supervision_timeout_units=%u\n",
	       KINEIMU_NODE_LABEL, interval, latency, timeout);
	log_link_info(conn, "param_updated", firmware_uptime_ms);
}

#if defined(CONFIG_BT_USER_PHY_UPDATE)
static void le_phy_updated(struct bt_conn *conn,
				   struct bt_conn_le_phy_info *param)
{
	uint32_t firmware_uptime_ms = k_uptime_get_32();

	printk("Node %s: BLE link PHY callback tx=%u rx=%u\n",
	       KINEIMU_NODE_LABEL, param->tx_phy, param->rx_phy);
	log_link_info(conn, "phy_updated", firmware_uptime_ms);
}
#endif

#if defined(CONFIG_BT_USER_DATA_LEN_UPDATE)
static void le_data_len_updated(struct bt_conn *conn,
					struct bt_conn_le_data_len_info *info)
{
	uint32_t firmware_uptime_ms = k_uptime_get_32();

	printk("Node %s: BLE link DLE callback tx_max_len=%u tx_max_time_us=%u "
	       "rx_max_len=%u rx_max_time_us=%u\n",
	       KINEIMU_NODE_LABEL, info->tx_max_len, info->tx_max_time,
	       info->rx_max_len, info->rx_max_time);
	log_link_info(conn, "data_len_updated", firmware_uptime_ms);
}
#endif

static void connected(struct bt_conn *conn, uint8_t err)
{
	uint32_t firmware_uptime_ms = k_uptime_get_32();

#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
	enum node_a_conn_param_request_mode request_mode;
	k_spinlock_key_t key;
#endif

	if (err != 0U) {
		printk("KineIMU BLE connection failed error=0x%02x %s\n", err,
		       bt_hci_err_to_str(err));
		request_advertising_restart("connection failure");
		return;
	}

#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
	key = k_spin_lock(&conn_param_request_lock);
	conn_param_request_connection_active = true;
	request_mode = conn_param_request_mode;
	k_spin_unlock(&conn_param_request_lock, key);
#endif

	atomic_set(&link_connected, 1);
	atomic_set(&telemetry_notifications_enabled, 0);
	atomic_set(&identity_indications_enabled, 0);
	atomic_set(&clock_indications_enabled, 0);
	atomic_set(&status_indications_enabled, 0);
	atomic_set(&link_att_mtu, bt_gatt_get_uatt_mtu(conn));
	tx_queue_sync_connection_state();
	printk("KineIMU BLE connected ATT MTU=%u\n",
	       (uint16_t)atomic_get(&link_att_mtu));
	log_link_info(conn, "connected", firmware_uptime_ms);
#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
	bool request_invoked = false;
	int request_rc = node_a_conn_param_experiment_on_connect(
		request_mode, conn, request_root_cause_connection_parameters,
		NULL, &request_invoked);

	if (request_invoked) {
		printk("Node %s: conn_param_request node_id=%u mode=%s call=1 "
		       "interval_min_units=12 interval_max_units=12 latency=0 "
		       "timeout_units=42 api_rc=%d\n",
		       KINEIMU_NODE_LABEL, KINEIMU_NODE_ID,
		       node_a_conn_param_experiment_mode_name(request_mode),
		       request_rc);
	} else {
		printk("Node %s: conn_param_request node_id=%u mode=%s call=0 "
		       "api_rc=NA\n",
		       KINEIMU_NODE_LABEL, KINEIMU_NODE_ID,
	       node_a_conn_param_experiment_mode_name(request_mode));
	}
#endif
}

static void disconnected(struct bt_conn *conn, uint8_t reason)
{
	uint32_t firmware_uptime_ms = k_uptime_get_32();
#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
	k_spinlock_key_t key;
#endif

	ARG_UNUSED(conn);
#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
	key = k_spin_lock(&conn_param_request_lock);
	conn_param_request_connection_active = false;
	k_spin_unlock(&conn_param_request_lock, key);
#endif
	atomic_set(&link_connected, 0);
	atomic_set(&telemetry_notifications_enabled, 0);
	atomic_set(&identity_indications_enabled, 0);
	atomic_set(&clock_indications_enabled, 0);
	atomic_set(&status_indications_enabled, 0);
	atomic_set(&link_att_mtu, 0);
	atomic_clear(&indication_in_flight);
	tx_cancel_inflight();
	tx_queue_sync_connection_state();
	printk("KineIMU BLE disconnected reason=0x%02x %s\n", reason,
	       bt_hci_err_to_str(reason));
#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
	printk("Node %s: BLE link event=disconnected firmware_uptime_ms=%u "
	       "reason=0x%02x\n",
	       KINEIMU_NODE_LABEL, firmware_uptime_ms, reason);
#endif
	request_advertising_restart("disconnect");
}

BT_CONN_CB_DEFINE(node_a_ble_conn_callbacks) = {
	.connected = connected,
	.disconnected = disconnected,
	.le_param_updated = le_param_updated,
#if defined(CONFIG_BT_USER_PHY_UPDATE)
	.le_phy_updated = le_phy_updated,
#endif
#if defined(CONFIG_BT_USER_DATA_LEN_UPDATE)
	.le_data_len_updated = le_data_len_updated,
#endif
};

static const struct bt_data advertising_data[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
	BT_DATA_BYTES(BT_DATA_UUID128_ALL, NODE_A_BLE_SERVICE_UUID_VAL),
};

static const struct bt_data scan_response_data[] = {
	BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME,
		 sizeof(CONFIG_BT_DEVICE_NAME) - 1U),
};

static int start_advertising(void *context)
{
	ARG_UNUSED(context);
	return bt_le_adv_start(BT_LE_ADV_CONN_FAST_1,
				       advertising_data,
				       ARRAY_SIZE(advertising_data),
				       scan_response_data,
				       ARRAY_SIZE(scan_response_data));
}

static void request_advertising_restart(const char *reason)
{
	const int ret = node_a_ble_advertising_restart_request(
		&advertising_restart);

	if (ret < 0) {
		printk("KineIMU BLE advertising restart schedule failed reason=%s rc=%d\n",
		       reason, ret);
	}
}

static void bluetooth_ready(int err)
{
	if (err != 0) {
		bluetooth_start_error = err;
		k_sem_give(&bluetooth_ready_sem);
		return;
	}

	bluetooth_start_error = start_advertising(NULL);
	if (bluetooth_start_error != 0) {
		printk("KineIMU BLE advertising failed rc=%d\n",
		       bluetooth_start_error);
	} else {
		printk("KineIMU BLE advertising as %s\n", CONFIG_BT_DEVICE_NAME);
	}
	k_sem_give(&bluetooth_ready_sem);
}

int node_a_ble_service_set_identity(
	const struct node_a_ble_identity_config *config)
{
	uint8_t encoded[NODE_A_BLE_IDENTITY_CONFIG_SIZE];
	size_t encoded_size;
	int ret;

	if (atomic_get(&telemetry_notifications_enabled)) {
		return -EBUSY;
	}

	ret = node_a_ble_encode_identity_config(config, encoded, sizeof(encoded),
					       &encoded_size);
	if (ret < 0) {
		return ret;
	}
	k_mutex_lock(&value_lock, K_FOREVER);
	memcpy(identity_value, encoded, encoded_size);
	identity_config = *config;
	k_mutex_unlock(&value_lock);
	return 0;
}

int node_a_ble_service_update_status(const struct node_a_ble_status *status)
{
	uint8_t encoded[NODE_A_BLE_STATUS_SIZE];
	size_t encoded_size;
	int ret;

	ret = node_a_ble_encode_status(status, encoded, sizeof(encoded),
				       &encoded_size);
	if (ret < 0) {
		return ret;
	}
	k_mutex_lock(&value_lock, K_FOREVER);
	memcpy(status_value, encoded, encoded_size);
	k_mutex_unlock(&value_lock);
	return 0;
}

int node_a_ble_service_start(void)
{
	int ret;

	if (!callbacks_registered) {
		node_a_ble_advertising_restart_init(&advertising_restart,
						    start_advertising, NULL);
		for (size_t index = 0U; index < ARRAY_SIZE(tx_submissions); index++) {
			node_a_ble_tx_completion_init(
				&tx_submissions[index].completion);
			memset(&tx_submissions[index].diagnostics, 0,
			       sizeof(tx_submissions[index].diagnostics));
			k_work_init_delayable(&tx_submissions[index].submit_work,
					      tx_notify_submit_work_handler);
		}
		k_work_init(&tx_notify_reclaim_work,
			    tx_notify_reclaim_work_handler);
		node_a_ble_tx_queue_init(&tx_queue);
		node_a_ble_tx_diagnostics_init(
			&tx_diagnostics, identity_config.boot_id,
			node_a_ble_tx_queue_connection_generation_get(&tx_queue),
			sys_clock_hw_cycles_per_sec(),
			(uint32_t)ARRAY_SIZE(tx_submissions));
		memset(&tx_stats, 0, sizeof(tx_stats));
		tx_queue_initialized = true;
		(void)k_thread_create(&tx_worker_thread, tx_worker_stack,
				      K_THREAD_STACK_SIZEOF(tx_worker_stack),
				      tx_worker, &tx_queue, NULL, NULL,
				      NODE_A_BLE_TX_WORKER_PRIORITY, 0, K_NO_WAIT);
		atomic_set(&link_connected, 0);
		atomic_set(&telemetry_notifications_enabled, 0);
		atomic_set(&identity_indications_enabled, 0);
		atomic_set(&clock_indications_enabled, 0);
		atomic_set(&status_indications_enabled, 0);
		atomic_set(&link_att_mtu, 0);
		atomic_set(&indication_in_flight, 0);
		atomic_set(&tx_stopping, 0);
		bt_gatt_cb_register(&gatt_callbacks);
		callbacks_registered = true;
	}

	ret = bt_enable(bluetooth_ready);
	if (ret < 0) {
		return ret;
	}
	return 0;
}

int node_a_ble_service_wait_ready(k_timeout_t timeout)
{
	int ret = k_sem_take(&bluetooth_ready_sem, timeout);

	if (ret < 0) {
		return ret;
	}
	return bluetooth_start_error;
}

bool node_a_ble_service_is_stream_ready(void)
{
	const struct node_a_ble_link_state state = {
		.connected = atomic_get(&link_connected) != 0,
		.telemetry_notifications_enabled =
			atomic_get(&telemetry_notifications_enabled) != 0,
		.att_mtu = (uint16_t)atomic_get(&link_att_mtu),
	};

	return node_a_ble_transport_validate_att_mtu(state.att_mtu) == 0 &&
		state.connected && state.telemetry_notifications_enabled;
}

uint16_t node_a_ble_service_att_mtu(void)
{
	return (uint16_t)atomic_get(&link_att_mtu);
}

int node_a_ble_service_enqueue_packet(const uint8_t *packet, size_t packet_size,
				      uint32_t packet_sequence)
{
	int ret;

	if (!tx_queue_initialized) {
		return -ESHUTDOWN;
	}
	ret = node_a_ble_tx_queue_enqueue(&tx_queue, packet, packet_size,
					  packet_sequence);
	if (ret == 0) {
		tx_update_completion_window_wait();
	}
	return ret;
}

uint16_t node_a_ble_service_take_tx_packet_flags(void)
{
	if (!tx_queue_initialized) {
		return 0U;
	}
	return node_a_ble_tx_queue_take_packet_flags(&tx_queue);
}

void node_a_ble_service_tx_stats_get(
	struct node_a_ble_service_tx_stats *stats)
{
	struct node_a_ble_tx_queue_stats queue_stats;
	k_spinlock_key_t key;

	if (stats == NULL) {
		return;
	}
	memset(stats, 0, sizeof(*stats));
	if (!tx_queue_initialized) {
		return;
	}

	node_a_ble_tx_queue_stats_get(&tx_queue, &queue_stats);
	key = k_spin_lock(&tx_stats_lock);
	stats->notify_calls = tx_stats.notify_calls;
	stats->notify_failures = tx_stats.notify_failures;
	stats->notify_last_duration_us = tx_stats.notify_last_duration_us;
	stats->notify_max_duration_us = tx_stats.notify_max_duration_us;
	stats->notify_total_duration_us = tx_stats.notify_total_duration_us;
	stats->counters_saturated = tx_stats.counters_saturated;
	k_spin_unlock(&tx_stats_lock, key);
	stats->queue_high_water_packets = queue_stats.high_water_packets;
	stats->enqueue_drops = queue_stats.enqueue_drops;
	stats->disconnect_drops = queue_stats.disconnect_drops;
	stats->stop_drops = queue_stats.stop_drops;
	node_a_ble_tx_diagnostics_snapshot_get(&tx_diagnostics,
						       &stats->diagnostics);
	stats->counters_saturated = stats->counters_saturated ||
		queue_stats.counters_saturated ||
		stats->diagnostics.counters_saturated;
}

void node_a_ble_service_stop_tx(void)
{
	if (tx_queue_initialized) {
		atomic_set(&tx_stopping, 1);
		tx_cancel_inflight();
		node_a_ble_tx_queue_stop(&tx_queue);
		tx_update_completion_window_wait();
	}
}

static int tx_submit_notify(struct node_a_ble_tx_submission *submission)
{
	struct bt_gatt_notify_params *params = &submission->params;
	const struct node_a_ble_link_state state = {
		.connected = atomic_get(&link_connected) != 0,
		.telemetry_notifications_enabled =
			atomic_get(&telemetry_notifications_enabled) != 0,
		.att_mtu = (uint16_t)atomic_get(&link_att_mtu),
	};

	if ((params == NULL) ||
	    !node_a_ble_transport_can_notify(&state, params->len)) {
		if (!state.connected) {
			return -ENOTCONN;
		}
		if (!state.telemetry_notifications_enabled) {
			return -EACCES;
		}
		if (node_a_ble_transport_validate_att_mtu(state.att_mtu) < 0) {
			return -EMSGSIZE;
		}
		return -EINVAL;
	}

	params->attr = &node_a_ble_svc.attrs[NODE_A_BLE_TELEMETRY_ATTR_INDEX];
	if (!node_a_ble_tx_diagnostics_notify_call_begin(
		    &tx_diagnostics, &submission->diagnostics)) {
		return -ECANCELED;
	}
	const int ret = bt_gatt_notify_cb(NULL, params);
	const uint32_t returned_at_cycles = k_cycle_get_32();
	const bool release_deferred_completion =
		node_a_ble_tx_diagnostics_note_notify_result(
			&tx_diagnostics, &submission->diagnostics, ret,
			returned_at_cycles);

	if (release_deferred_completion) {
		tx_update_completion_window_wait();
		k_sem_give(&tx_notify_slot_available);
		/* The callback already consumed this submission. Hide an anomalous
		 * negative return from the retry/failure path so it cannot act on a
		 * context that the worker may already have reused.
		 */
		return 0;
	}
	return ret;
}

int node_a_ble_service_indicate_identity(void)
{
	int ret;

	if (!atomic_get(&identity_indications_enabled)) {
		return -EACCES;
	}
	ret = begin_indication(&node_a_ble_svc.attrs[
		NODE_A_BLE_IDENTITY_ATTR_INDEX], identity_value,
		NODE_A_BLE_IDENTITY_CONFIG_SIZE);
	return ret;
}

int node_a_ble_service_indicate_status(void)
{
	int ret;

	if (!atomic_get(&status_indications_enabled)) {
		return -EACCES;
	}
	ret = begin_indication(&node_a_ble_svc.attrs[
		NODE_A_BLE_STATUS_ATTR_INDEX], status_value,
		NODE_A_BLE_STATUS_SIZE);
	return ret;
}
