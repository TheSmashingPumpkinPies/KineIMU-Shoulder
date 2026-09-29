/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <hal/nrf_ficr.h>
#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/random/random.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/util.h>

#include "acquisition.h"
#include "acquisition_trace.h"
#include "counters.h"
#include "identity.h"
#include "lsm6dsl_fifo.h"
#include "lsm6dsl_raw.h"
#include "m1_ble_codec.h"
#include "m1_ble_identity.h"
#include "m1_ble_service.h"
#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
#include "m1_conn_param_control.h"
#include "m1_conn_param_experiment.h"
#endif
#include "node_config.h"
#include "packet.h"
#include "sample_queue.h"
#include "timestamp.h"

#define IMU_NODE DT_NODELABEL(lsm6ds3tr_c)
#define IMU_POWER_UP_DELAY K_MSEC(50)
#define LSM6DS3TR_C_REG_INT1_CTRL 0x0dU
#define LSM6DS3TR_C_REG_WHO_AM_I 0x0fU
#define LSM6DS3TR_C_REG_CTRL1_XL 0x10U
#define LSM6DS3TR_C_REG_CTRL2_G 0x11U
#define NODE_A_PACKET_BATCH_SIZE NODE_A_PACKET_MAX_SAMPLES
#define NODE_A_PACKET_GATHER_TIMEOUT K_MSEC(20)
#define NODE_A_STATUS_PERIOD_MS 1000
#define NODE_A_DATA_READY_QUIET_TIMEOUT_MS 50U
#define NODE_A_DATA_READY_REARM_MAX_ATTEMPTS 3U

BUILD_ASSERT(NODE_A_PACKET_MAX_SIZE <= 124U,
	     "v1 telemetry packets must fit the BLE ATT payload contract");

#ifndef KINEIMU_FIRMWARE_GIT_COMMIT_HEX
#error "m1_ble must provide KINEIMU_FIRMWARE_GIT_COMMIT_HEX"
#endif

#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
BUILD_ASSERT(DT_NODE_HAS_STATUS(DT_CHOSEN(zephyr_console), okay),
	     "connection-parameter experiment requires a ready CDC console");

static const struct device *const conn_param_control_uart =
	DEVICE_DT_GET(DT_CHOSEN(zephyr_console));
static struct node_a_conn_param_control_rx conn_param_control_rx;
static struct node_a_conn_param_control_session conn_param_control_session;

static void process_conn_param_control_line(const char *line, size_t length,
					    bool overflow, void *context)
{
	struct node_a_conn_param_experiment_request request = {0};
	enum node_a_conn_param_request_mode selected_mode;
	int rc = -EINVAL;

	ARG_UNUSED(context);

	if (overflow) {
		printk("ERROR node_id=%u rc=%d\n", KINEIMU_NODE_ID, -EMSGSIZE);
		return;
	}

	rc = node_a_conn_param_experiment_accept_hello(
		&conn_param_control_session, line, length);
	if (rc == 0) {
		printk("READY node_id=%u session=%s\n", KINEIMU_NODE_ID,
		       conn_param_control_session.nonce);
		return;
	}

	rc = node_a_conn_param_experiment_parse_session_command(
		line, length, &request);
	if (rc < 0) {
		printk("ERROR node_id=%u rc=%d\n", KINEIMU_NODE_ID, rc);
		return;
	}
	if (!node_a_conn_param_experiment_session_matches(
		    &conn_param_control_session, &request)) {
		rc = -EACCES;
		selected_mode = node_a_ble_service_conn_param_request_mode_get();
		printk("ERR node_id=%u session=%s tx=%u requested=%s "
		       "selected=%s rc=%d\n",
		       KINEIMU_NODE_ID, request.session_nonce,
		       request.transaction_id,
		       node_a_conn_param_experiment_mode_name(request.mode),
		       node_a_conn_param_experiment_mode_name(selected_mode), rc);
		return;
	}
	if (request.transaction_id <=
	    conn_param_control_session.last_transaction_id) {
		rc = -ESTALE;
	} else {
		conn_param_control_session.last_transaction_id =
			request.transaction_id;
		rc = node_a_ble_service_set_conn_param_request_mode(request.mode);
	}
	selected_mode = node_a_ble_service_conn_param_request_mode_get();
	printk("ACK node_id=%u session=%s tx=%u requested=%s "
	       "selected=%s rc=%d\n",
	       KINEIMU_NODE_ID, request.session_nonce, request.transaction_id,
	       node_a_conn_param_experiment_mode_name(request.mode),
	       node_a_conn_param_experiment_mode_name(selected_mode), rc);
}

static void conn_param_control_uart_irq(const struct device *device,
					void *user_data)
{
	struct node_a_conn_param_control_rx *rx = user_data;
	uint8_t bytes[16];

	if (!uart_irq_update(device)) {
		return;
	}
	while (uart_irq_rx_ready(device)) {
		int count = uart_fifo_read(device, bytes, sizeof(bytes));

		if (count <= 0) {
			break;
		}
		(void)node_a_conn_param_control_rx_push(rx, bytes, (size_t)count);
	}
}

static int conn_param_control_start(void)
{
	int rc;

	if (!device_is_ready(conn_param_control_uart)) {
		return -ENODEV;
	}
	node_a_conn_param_control_rx_init(&conn_param_control_rx);
	rc = uart_irq_callback_user_data_set(conn_param_control_uart,
					     conn_param_control_uart_irq,
					     &conn_param_control_rx);
	if (rc < 0) {
		return rc;
	}
	uart_irq_rx_enable(conn_param_control_uart);
	return 0;
}

static void process_conn_param_experiment_control(void)
{
	if (node_a_conn_param_control_rx_take_overflow(
		    &conn_param_control_rx)) {
		printk("conn_param_control_error node_id=%u rc=%d\n",
		       KINEIMU_NODE_ID, -ENOBUFS);
	}
	(void)node_a_conn_param_control_rx_drain(
		&conn_param_control_rx, process_conn_param_control_line, NULL);
}
#endif

static const struct device *const imu = DEVICE_DT_GET(IMU_NODE);
static const struct i2c_dt_spec imu_i2c = I2C_DT_SPEC_GET(IMU_NODE);
static const struct gpio_dt_spec imu_drdy_gpio =
	GPIO_DT_SPEC_GET(IMU_NODE, irq_gpios);

static struct node_a_drdy_timestamp drdy_timestamp;
static struct node_a_stream_counters stream_counters;
static struct node_a_sample_queue sample_queue;
static struct node_a_lsm6dsl_fifo_observer fifo_observer;
static struct node_a_acquisition_trace acquisition_trace;
static volatile bool acquisition_enabled;
static atomic_t data_ready_rearm_requested;
static uint64_t active_boot_id;

struct node_a_m1_runtime {
	struct k_spinlock lock;
	uint64_t samples_acquired;
	uint64_t packets_generated;
	uint32_t status_sequence;
	uint32_t last_error_code;
	uint32_t last_sample_sequence;
	uint32_t last_packet_sequence;
	bool counters_saturated;
	bool fatal_latched;
};

struct node_a_m1_runtime_snapshot {
	uint64_t samples_acquired;
	uint64_t packets_generated;
	uint32_t status_sequence;
	uint32_t last_error_code;
	uint32_t last_sample_sequence;
	uint32_t last_packet_sequence;
	bool counters_saturated;
	bool fatal_latched;
};

static struct node_a_m1_runtime runtime;
static int64_t last_status_update_ms;

static void saturating_add_u32(uint32_t *counter, uint32_t amount,
				       bool *saturated)
{
	if (amount == 0U) {
		return;
	}
	if (*counter > UINT32_MAX - amount) {
		*counter = UINT32_MAX;
		*saturated = true;
		return;
	}
	*counter += amount;
	if (*counter == UINT32_MAX) {
		*saturated = true;
	}
}

static void saturating_increment_u64(uint64_t *counter, bool *saturated)
{
	if (*counter < UINT64_MAX) {
		(*counter)++;
	}
	if (*counter == UINT64_MAX) {
		*saturated = true;
	}
}

static void runtime_init(void)
{
	runtime.last_sample_sequence = UINT32_MAX;
	runtime.last_packet_sequence = UINT32_MAX;
	atomic_clear(&data_ready_rearm_requested);
}

static void runtime_note_sample(uint32_t sample_sequence)
{
	k_spinlock_key_t key = k_spin_lock(&runtime.lock);

	saturating_increment_u64(&runtime.samples_acquired,
					 &runtime.counters_saturated);
	runtime.last_sample_sequence = sample_sequence;
	k_spin_unlock(&runtime.lock, key);
}

static void runtime_note_packet(uint32_t packet_sequence)
{
	k_spinlock_key_t key = k_spin_lock(&runtime.lock);

	saturating_increment_u64(&runtime.packets_generated,
					 &runtime.counters_saturated);
	runtime.last_packet_sequence = packet_sequence;
	k_spin_unlock(&runtime.lock, key);
}

static void runtime_note_error(int rc, bool fatal)
{
	uint32_t error_code;
	k_spinlock_key_t key;

	if (rc >= 0) {
		return;
	}
	error_code = (uint32_t)(-(int64_t)rc);
	key = k_spin_lock(&runtime.lock);
	runtime.last_error_code = error_code;
	runtime.fatal_latched = runtime.fatal_latched || fatal;
	k_spin_unlock(&runtime.lock, key);
}

static void runtime_snapshot_get(struct node_a_m1_runtime_snapshot *snapshot)
{
	k_spinlock_key_t key;

	key = k_spin_lock(&runtime.lock);
	snapshot->status_sequence = runtime.status_sequence;
	if (runtime.status_sequence < UINT32_MAX) {
		runtime.status_sequence++;
		if (runtime.status_sequence == UINT32_MAX) {
			runtime.counters_saturated = true;
		}
	} else {
		runtime.counters_saturated = true;
	}
	snapshot->samples_acquired = runtime.samples_acquired;
	snapshot->packets_generated = runtime.packets_generated;
	snapshot->last_error_code = runtime.last_error_code;
	snapshot->last_sample_sequence = runtime.last_sample_sequence;
	snapshot->last_packet_sequence = runtime.last_packet_sequence;
	snapshot->counters_saturated = runtime.counters_saturated;
	snapshot->fatal_latched = runtime.fatal_latched;
	k_spin_unlock(&runtime.lock, key);
}

static int generate_boot_id(uint64_t *boot_id)
{
	for (size_t attempt = 0U; attempt < 2U; ++attempt) {
		int rc = sys_csrand_get(boot_id, sizeof(*boot_id));

		if (rc < 0) {
			return rc;
		}
		if (*boot_id != 0U) {
			return 0;
		}
	}

	return -EIO;
}

static int read_sensor_identity_registers(
	struct node_a_imu_registers *registers, uint8_t snapshot[19])
{
	int rc;

	rc = i2c_reg_read_byte_dt(&imu_i2c, LSM6DS3TR_C_REG_WHO_AM_I,
				 &registers->who_am_i);
	if (rc == 0) {
		rc = i2c_reg_read_byte_dt(&imu_i2c,
					   LSM6DS3TR_C_REG_INT1_CTRL,
					   &registers->int1_ctrl);
	}
	if (rc == 0) {
		rc = i2c_reg_read_byte_dt(&imu_i2c,
					   LSM6DS3TR_C_REG_CTRL1_XL,
					   &registers->ctrl1_xl);
	}
	if (rc == 0) {
		rc = i2c_reg_read_byte_dt(&imu_i2c,
					   LSM6DS3TR_C_REG_CTRL2_G,
					   &registers->ctrl2_g);
	}
	if (rc < 0) {
		return rc;
	}

	return node_a_imu_read_register_snapshot(
		&imu_i2c, i2c_burst_read_dt, snapshot);
}

static void reset_drdy_timestamp_context(void *context)
{
	node_a_drdy_timestamp_reset(context);
}

static void data_ready_handler(const struct device *dev,
				       const struct sensor_trigger *trigger)
{
	struct node_a_imu_sample sample = {0};
	struct node_a_lsm6dsl_fifo_status fifo_status;
	bool timestamp_available;
	int rc;

	ARG_UNUSED(dev);
	ARG_UNUSED(trigger);
	node_a_acquisition_trace_note_callback_entry(&acquisition_trace);

	/* Discard an event captured before the host completed identity and
	 * telemetry setup. The first published sample must belong to the active
	 * BLE stream, not to the arming interval.
	 */
	if (!acquisition_enabled) {
		uint64_t discarded_timestamp;

		node_a_acquisition_trace_note_pre_acquisition(&acquisition_trace);
		timestamp_available = node_a_drdy_timestamp_take(
			&drdy_timestamp, &discarded_timestamp);
		node_a_acquisition_trace_note_timestamp_result(
			&acquisition_trace, timestamp_available);
		return;
	}

	/* The GPIO callback captured this edge before the sensor driver's deferred
	 * work item entered this handler.
	 */
	timestamp_available = node_a_drdy_timestamp_take(
		&drdy_timestamp, &sample.timestamp_us);
	node_a_acquisition_trace_note_timestamp_result(
		&acquisition_trace, timestamp_available);
	if (!timestamp_available) {
		/* A callback without a GPIO ISR timestamp is never a sample. Request a
		 * bounded re-arm so a callback queued by the driver's level check cannot
		 * leave the data-ready interrupt disabled indefinitely. */
		atomic_set(&data_ready_rearm_requested, 1);
		return;
	}

	rc = node_a_lsm6dsl_read_raw(&imu_i2c, i2c_burst_read_dt, &sample);
	node_a_acquisition_trace_note_raw_read_result(&acquisition_trace, rc);
	if (rc < 0) {
		runtime_note_error(rc, false);
		return;
	}

	rc = node_a_lsm6dsl_read_fifo_status(
		&imu_i2c, i2c_burst_read_dt, &fifo_status);
	if (rc < 0) {
		/* A FIFO diagnostic failure must not discard an otherwise coherent raw
		 * sample. The error remains visible through the status characteristic.
		 */
		runtime_note_error(rc, false);
	} else {
		node_a_lsm6dsl_fifo_observe(&fifo_observer, &fifo_status);
	}

	sample.clock_epoch = stream_counters.clock_epoch;
	sample.sample_sequence =
		node_a_counters_take_sample(&stream_counters);
	runtime_note_sample(sample.sample_sequence);

	/* Drop newest on overflow. The queue owns the loss counters and packet
	 * flag, while the already-issued sample sequence exposes the gap.
	 */
	(void)node_a_sample_queue_put(&sample_queue, &sample);
}

static int publish_status(uint8_t requested_state, bool sampling_active)
{
	struct node_a_m1_runtime_snapshot runtime_snapshot;
	struct node_a_sample_queue_stats queue_stats;
	struct node_a_lsm6dsl_fifo_stats fifo_stats;
	struct node_a_ble_service_tx_stats tx_stats;
	uint32_t transport_backpressure_events = 0U;
	bool counters_saturated;
	uint16_t flags = NODE_A_BLE_STATUS_FLAG_SENSOR_READY;
	struct node_a_ble_status status;

	runtime_snapshot_get(&runtime_snapshot);
	node_a_sample_queue_stats_get(&sample_queue, &queue_stats);
	node_a_lsm6dsl_fifo_stats_get(&fifo_observer, &fifo_stats);
	node_a_ble_service_tx_stats_get(&tx_stats);
	counters_saturated = runtime_snapshot.counters_saturated ||
		queue_stats.counters_saturated || fifo_stats.counters_saturated ||
		tx_stats.counters_saturated;
	saturating_add_u32(&transport_backpressure_events,
				   tx_stats.enqueue_drops, &counters_saturated);
	saturating_add_u32(&transport_backpressure_events,
				   tx_stats.disconnect_drops, &counters_saturated);
	saturating_add_u32(&transport_backpressure_events,
				   tx_stats.stop_drops, &counters_saturated);
	saturating_add_u32(&transport_backpressure_events,
				   tx_stats.notify_failures, &counters_saturated);

	if (sampling_active && !runtime_snapshot.fatal_latched) {
		flags |= NODE_A_BLE_STATUS_FLAG_SAMPLING_ACTIVE;
	}
	if (runtime_snapshot.fatal_latched) {
		flags |= NODE_A_BLE_STATUS_FLAG_FATAL_LATCHED;
		requested_state = NODE_A_BLE_ACQUISITION_ERROR;
	}
	if (counters_saturated) {
		flags |= NODE_A_BLE_STATUS_FLAG_COUNTERS_SATURATED;
	}

	status = (struct node_a_ble_status){
		.node_id = KINEIMU_NODE_ID,
		.acquisition_state = requested_state,
		.flags = flags,
		.boot_id = active_boot_id,
		.clock_epoch = stream_counters.clock_epoch,
		.status_sequence = runtime_snapshot.status_sequence,
		.last_sample_sequence = runtime_snapshot.last_sample_sequence,
		.last_packet_sequence = runtime_snapshot.last_packet_sequence,
		.samples_acquired = runtime_snapshot.samples_acquired,
		.packets_generated = runtime_snapshot.packets_generated,
		.sensor_fifo_overruns = fifo_stats.sensor_fifo_overruns,
		.firmware_queue_overruns = queue_stats.firmware_queue_overruns,
		.transport_backpressure_events = transport_backpressure_events,
		.samples_dropped_before_packetization =
			queue_stats.samples_dropped_before_packetization,
		/* There is no additional acquisition ring between the DRDY callback and
		 * the bounded firmware queue in this image.
		 */
		.acquisition_buffer_high_water_samples = 0U,
		.transport_queue_high_water_packets =
			tx_stats.queue_high_water_packets,
		.last_error_code = runtime_snapshot.last_error_code,
	};

	/* Status indications are best-effort. The readable status value remains
	 * authoritative when the CCC is not enabled or another indication is in
	 * flight.
	 */
	const int ret = node_a_ble_service_update_status(&status);
	if (ret == 0) {
		(void)node_a_ble_service_indicate_status();
	}
	return ret;
}

static void format_tx_return_code_counts(
	const struct node_a_ble_tx_diagnostics_snapshot *diagnostics,
	char *buffer,
	size_t buffer_size)
{
	size_t used = 0U;

	if ((diagnostics == NULL) || (buffer == NULL) || (buffer_size == 0U)) {
		return;
	}

	buffer[0] = '\0';
	for (size_t index = 0U;
	     index < NODE_A_BLE_TX_DIAG_RETURN_CODE_SLOTS; index++) {
		const struct node_a_ble_tx_diag_return_code *slot =
			&diagnostics->notify_return_codes[index];
		int written;

		if (!slot->occupied || (used >= buffer_size)) {
			continue;
		}
		written = snprintk(&buffer[used], buffer_size - used,
				   "%s%d:%u", (used == 0U) ? "" : ",",
				   slot->code, slot->count);
		if ((written < 0) || ((size_t)written >= buffer_size - used)) {
			buffer[buffer_size - 1U] = '\0';
			return;
		}
		used += (size_t)written;
	}
	if (used == 0U) {
		(void)snprintk(buffer, buffer_size, "none");
	}
}

static int publish_status_if_due(uint8_t state, bool sampling_active)
{
	const int64_t now_ms = k_uptime_get();
	struct node_a_acquisition_trace_snapshot trace_snapshot;
	struct node_a_ble_service_tx_stats tx_stats;
	char tx_return_code_counts[384];

	if (acquisition_enabled &&
	    (now_ms - last_status_update_ms >= NODE_A_STATUS_PERIOD_MS)) {
		node_a_acquisition_trace_snapshot_get(&acquisition_trace,
						      &trace_snapshot);
		node_a_ble_service_tx_stats_get(&tx_stats);
		format_tx_return_code_counts(&tx_stats.diagnostics,
					     tx_return_code_counts,
					     sizeof(tx_return_code_counts));
		printk("Node %s: acquisition trace callback=%u prestart=%u "
		       "timestamp_ok=%u timestamp_miss=%u raw_try=%u raw_ok=%u "
		       "raw_fail=%u raw_rc=%d tx_queue_high_water=%u "
		       "tx_enqueue_drops=%u tx_disconnect_drops=%u tx_stop_drops=%u "
		       "notify_calls=%u notify_failures=%u "
		       "notify_last_duration=%u notify_max_duration=%u "
		       "notify_total_duration=%llu saturated=%d\n",
		       KINEIMU_NODE_LABEL, trace_snapshot.callback_entries,
		       trace_snapshot.pre_acquisition_callbacks,
		       trace_snapshot.timestamp_available,
		       trace_snapshot.timestamp_missing,
		       trace_snapshot.raw_read_attempts,
		       trace_snapshot.raw_read_successes,
		       trace_snapshot.raw_read_failures,
		       trace_snapshot.last_raw_read_rc,
		       tx_stats.queue_high_water_packets,
		       tx_stats.enqueue_drops,
		       tx_stats.disconnect_drops,
		       tx_stats.stop_drops,
		       tx_stats.notify_calls,
		       tx_stats.notify_failures,
		       tx_stats.notify_last_duration_us,
		       tx_stats.notify_max_duration_us,
		       (unsigned long long)tx_stats.notify_total_duration_us,
		       trace_snapshot.counters_saturated ||
		       tx_stats.counters_saturated);
		printk("Node %s: tx_diag boot=%llu generation=%u calls=%u "
		       "accepted=%u final_fail=%u packet_drops=%u "
		       "return_last=%d return_counts=%s enomem=%u eagain=%u "
		       "retries=%u schedule_fail=%u/%u schedule_last=%d/%d "
		       "window_owned=%u inflight=%u/%u window_full=%u wait_us=%llu "
		       "completed=%u cancelled=%u callbacks_stale=%u "
		       "callbacks_cancelled=%u callbacks_unexpected=%u "
		       "age_count=%u age_us=%u/%u/%u/%llu "
		       "age_bins=%u,%u,%u,%u,%u,%u,%u,%u saturated=%d\n",
		       KINEIMU_NODE_LABEL,
		       (unsigned long long)tx_stats.diagnostics.boot_id,
		       tx_stats.diagnostics.connection_generation,
		       tx_stats.diagnostics.notify_submit_calls,
		       tx_stats.diagnostics.notify_accepted,
		       tx_stats.diagnostics.notify_final_failures,
		       tx_stats.diagnostics.notify_packet_drops,
		       tx_stats.diagnostics.notify_last_return_code,
		       tx_return_code_counts,
		       tx_stats.diagnostics.notify_ret_enomem,
		       tx_stats.diagnostics.notify_ret_eagain,
		       tx_stats.diagnostics.retry_attempts,
		       tx_stats.diagnostics.initial_schedule_failures,
		       tx_stats.diagnostics.retry_schedule_failures,
		       tx_stats.diagnostics.last_initial_schedule_rc,
		       tx_stats.diagnostics.last_retry_schedule_rc,
		       tx_stats.diagnostics.completion_window_owned_current,
		       tx_stats.diagnostics.in_flight_current,
		       tx_stats.diagnostics.in_flight_peak,
		       tx_stats.diagnostics.completion_window_full_count,
		       (unsigned long long)
			       tx_stats.diagnostics.completion_window_wait_total_us,
		       tx_stats.diagnostics.notify_completed,
		       tx_stats.diagnostics.notify_cancelled,
		       tx_stats.diagnostics.callbacks_stale_generation,
		       tx_stats.diagnostics.callbacks_after_cancel,
		       tx_stats.diagnostics.callbacks_unexpected,
		       tx_stats.diagnostics.completion_age.count,
		       tx_stats.diagnostics.completion_age.last_us,
		       tx_stats.diagnostics.completion_age.min_us,
		       tx_stats.diagnostics.completion_age.max_us,
		       (unsigned long long)
			       tx_stats.diagnostics.completion_age.total_us,
		       tx_stats.diagnostics.completion_age.buckets[0],
		       tx_stats.diagnostics.completion_age.buckets[1],
		       tx_stats.diagnostics.completion_age.buckets[2],
		       tx_stats.diagnostics.completion_age.buckets[3],
		       tx_stats.diagnostics.completion_age.buckets[4],
		       tx_stats.diagnostics.completion_age.buckets[5],
		       tx_stats.diagnostics.completion_age.buckets[6],
		       tx_stats.diagnostics.completion_age.buckets[7],
		       tx_stats.diagnostics.counters_saturated);
	}

	if ((now_ms - last_status_update_ms) < NODE_A_STATUS_PERIOD_MS) {
		return 0;
	}
	last_status_update_ms = now_ms;
	return publish_status(state, sampling_active);
}

static int quiesce_and_arm_data_ready(void)
{
	struct node_a_imu_rearm_result result = {0};
	const int rc = node_a_imu_quiesce_and_arm_data_ready(
		imu, &imu_drdy_gpio, &imu_i2c, i2c_burst_read_dt,
		data_ready_handler, reset_drdy_timestamp_context, &drdy_timestamp,
		NODE_A_DATA_READY_QUIET_TIMEOUT_MS,
		NODE_A_DATA_READY_REARM_MAX_ATTEMPTS, &result);

	printk("Node %s: data-ready re-arm state=%d attempts=%u "
	       "race_retries=%u rc=%d\n",
	       KINEIMU_NODE_LABEL, result.state, result.attempts,
	       result.race_retries, rc);
	return rc;
}

static int enter_acquisition_fatal(int rc)
{
	acquisition_enabled = false;
	node_a_ble_service_stop_tx();
	runtime_note_error(rc, true);
	(void)publish_status(NODE_A_BLE_ACQUISITION_ERROR, false);
	return rc;
}

int main(void)
{
	struct node_a_imu_registers registers = {0};
	uint8_t sensor_registers[19] = {0};
	uint8_t firmware_git_commit[20];
	struct node_a_ble_identity_config identity;
	uint64_t boot_id;
	uint64_t hardware_device_id;
	int ret;

	runtime_init();
	node_a_acquisition_trace_init(&acquisition_trace);
#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
	ret = conn_param_control_start();
	if (ret < 0) {
		printk("Node %s: CDC control setup failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}
#endif

	ret = generate_boot_id(&boot_id);
	if (ret < 0) {
		printk("Node %s: boot ID generation failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}
	active_boot_id = boot_id;

	ret = node_a_ble_parse_git_commit(KINEIMU_FIRMWARE_GIT_COMMIT_HEX,
					  firmware_git_commit);
	if (ret < 0) {
		printk("Node %s: firmware Git commit parse failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}

	const uint32_t ficr_deviceid0 = nrf_ficr_deviceid_get(NRF_FICR, 0U);
	const uint32_t ficr_deviceid1 = nrf_ficr_deviceid_get(NRF_FICR, 1U);
	hardware_device_id = node_a_ficr_device_id_from_words(
		ficr_deviceid0, ficr_deviceid1);
	printk("Node %s: hardware_device_id=0x%08x%08x boot_id=0x%08x%08x\n",
	       KINEIMU_NODE_LABEL, (uint32_t)(hardware_device_id >> 32),
	       (uint32_t)hardware_device_id, (uint32_t)(boot_id >> 32),
	       (uint32_t)boot_id);

	k_sleep(IMU_POWER_UP_DELAY);
	ret = device_init(imu);
	if ((ret < 0) || !device_is_ready(imu)) {
		ret = (ret < 0) ? ret : -ENODEV;
		printk("Node %s: IMU init failed rc=%d ready=%d\n",
		       KINEIMU_NODE_LABEL, ret, device_is_ready(imu));
		return ret;
	}

	ret = node_a_drdy_timestamp_attach(&drdy_timestamp, &imu_drdy_gpio);
	if (ret < 0) {
		printk("Node %s: data-ready timestamp setup failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}
	node_a_counters_start(&stream_counters, 0U);
	node_a_sample_queue_init(&sample_queue);
	node_a_lsm6dsl_fifo_observer_init(&fifo_observer);

	ret = node_a_imu_configure(imu, data_ready_handler);
	if (ret < 0) {
		printk("Node %s: IMU acquisition setup failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}

	ret = read_sensor_identity_registers(&registers, sensor_registers);
	if (ret < 0) {
		printk("Node %s: IMU identity/register snapshot read failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}
	if (!node_a_imu_registers_match_config(&registers)) {
		printk("Node %s: IMU configuration audit failed WHO_AM_I=0x%02x "
		       "INT1_CTRL=0x%02x CTRL1_XL=0x%02x CTRL2_G=0x%02x\n",
		       KINEIMU_NODE_LABEL, registers.who_am_i, registers.int1_ctrl,
		       registers.ctrl1_xl, registers.ctrl2_g);
		return -EIO;
	}

	identity = (struct node_a_ble_identity_config){
		.node_id = KINEIMU_NODE_ID,
		.timestamp_source = NODE_A_BLE_TIMESTAMP_SOURCE_MCU_DRDY_ISR,
		.firmware_version = {0U, 1U, 0U},
		.batch_size = NODE_A_PACKET_BATCH_SIZE,
		.config_generation = 0U,
		.clock_epoch = stream_counters.clock_epoch,
		.boot_id = boot_id,
		.hardware_device_id = hardware_device_id,
		.timer_frequency_hz = CONFIG_SYS_CLOCK_TICKS_PER_SEC,
		.accel_odr_millihz = 104000U,
		.gyro_odr_millihz = 104000U,
		.accel_range_mg = NODE_A_ACCEL_RANGE_MG,
		.gyro_range_mdps = NODE_A_GYRO_RANGE_MDPS,
	};
	memcpy(identity.firmware_git_commit, firmware_git_commit,
	       sizeof(identity.firmware_git_commit));
	memcpy(identity.sensor_registers, sensor_registers,
	       sizeof(identity.sensor_registers));

	ret = node_a_ble_service_set_identity(&identity);
	if (ret < 0) {
		printk("Node %s: BLE identity setup failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}
	ret = publish_status(NODE_A_BLE_ACQUISITION_ARMED, false);
	if (ret < 0) {
		printk("Node %s: BLE status setup failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}
	ret = node_a_ble_service_start();
	if (ret < 0) {
		printk("Node %s: BLE start failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}
	ret = node_a_ble_service_wait_ready(K_SECONDS(5));
	if (ret < 0) {
		printk("Node %s: BLE ready wait failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}

	printk("KineIMU Shoulder Node %s BLE armed; waiting for host identity "
	       "read and telemetry notify enable\n", KINEIMU_NODE_LABEL);
	last_status_update_ms = k_uptime_get();

	bool acquisition_started = false;
	bool have_previous_sample = false;
	uint32_t previous_sample_sequence = 0U;

	while (true) {
#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
		process_conn_param_experiment_control();
#endif
		if (acquisition_started &&
		    atomic_cas(&data_ready_rearm_requested, 1, 0)) {
			/* A deferred callback can outlive the arm operation that queued it.
			 * Keep acquisition inactive while the same bounded quiesce/re-arm
			 * protocol drains that stale event and verifies the line again. */
			acquisition_enabled = false;
			ret = quiesce_and_arm_data_ready();
			if (ret < 0) {
				return enter_acquisition_fatal(ret);
			}
			acquisition_enabled = true;
			continue;
		}

		if (!acquisition_started) {
			if (node_a_ble_service_is_stream_ready()) {
				/* Do not make the stream active until the bounded protocol has
				 * completed its post-arm level check. */
				ret = quiesce_and_arm_data_ready();
				if (ret < 0) {
					return enter_acquisition_fatal(ret);
				}
				acquisition_started = true;
				acquisition_enabled = true;
				ret = publish_status(
					NODE_A_BLE_ACQUISITION_STREAMING, true);
				if (ret < 0) {
					return enter_acquisition_fatal(ret);
				}
				last_status_update_ms = k_uptime_get();
				printk("Node %s: BLE telemetry stream started ATT MTU=%u\n",
				       KINEIMU_NODE_LABEL,
				       node_a_ble_service_att_mtu());
			} else {
				ret = publish_status_if_due(
					NODE_A_BLE_ACQUISITION_ARMED, false);
				if (ret < 0) {
					runtime_note_error(ret, true);
					return ret;
				}
				k_sleep(K_MSEC(100));
				continue;
			}
		}

		if (!node_a_ble_service_is_stream_ready()) {
			/* Keep acquiring after a disconnect. The bounded sample queue records
			 * any loss while transport is unavailable, and the next packet carries
			 * the resulting sequence/overrun evidence.
			 */
			ret = publish_status_if_due(
				NODE_A_BLE_ACQUISITION_STREAMING, true);
			if (ret < 0) {
				runtime_note_error(ret, true);
				return ret;
			}
			k_sleep(K_MSEC(100));
			continue;
		}

		struct node_a_imu_sample samples[NODE_A_PACKET_BATCH_SIZE];
		uint8_t encoded[NODE_A_PACKET_MAX_SIZE];
		size_t sample_count = 1U;
		size_t encoded_size = 0U;
		uint16_t packet_flags;
		int encode_rc;

		if (!node_a_sample_queue_get(&sample_queue, &samples[0],
					     K_MSEC(100))) {
			ret = publish_status_if_due(
				NODE_A_BLE_ACQUISITION_STREAMING, true);
			if (ret < 0) {
				runtime_note_error(ret, true);
				return ret;
			}
			continue;
		}
		while (sample_count < NODE_A_PACKET_BATCH_SIZE &&
		       node_a_sample_queue_get(&sample_queue,
						&samples[sample_count],
						NODE_A_PACKET_GATHER_TIMEOUT)) {
			sample_count++;
		}

		packet_flags = node_a_lsm6dsl_fifo_take_packet_flags(&fifo_observer) |
			node_a_sample_queue_take_packet_flags(&sample_queue);
		packet_flags |= node_a_ble_service_take_tx_packet_flags();
		if (node_a_packet_samples_have_discontinuity(
				samples, sample_count, have_previous_sample,
				previous_sample_sequence)) {
			packet_flags |= NODE_A_PACKET_FLAG_DISCONTINUITY;
		}

		const struct node_a_sample_packet packet = {
			.node_id = NODE_A_PACKET_NODE_ID,
			.packet_sequence = node_a_counters_take_packet(&stream_counters),
			.clock_epoch = samples[0].clock_epoch,
			.flags = packet_flags,
			.samples = samples,
			.sample_count = sample_count,
		};
		encode_rc = node_a_packet_encode(&packet, encoded,
						 sizeof(encoded), &encoded_size);
		if (encode_rc < 0) {
			runtime_note_error(encode_rc, true);
			acquisition_enabled = false;
			(void)publish_status(NODE_A_BLE_ACQUISITION_ERROR, false);
			return encode_rc;
		}

		runtime_note_packet(packet.packet_sequence);
		/* The packetizer only transfers a complete copy into the bounded TX
		 * queue. The TX worker owns the later synchronous notify call. */
		ret = node_a_ble_service_enqueue_packet(encoded, encoded_size,
							 packet.packet_sequence);
		if ((ret < 0) && (ret != -ENOSPC) && (ret != -ENOTCONN) &&
		    (ret != -ESHUTDOWN)) {
			return enter_acquisition_fatal(ret);
		}

		have_previous_sample = true;
		previous_sample_sequence = samples[sample_count - 1U].sample_sequence;

		ret = publish_status_if_due(
			NODE_A_BLE_ACQUISITION_STREAMING, true);
		if (ret < 0) {
			runtime_note_error(ret, true);
			return ret;
		}
	}

	return 0;
}
