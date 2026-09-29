/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stddef.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/gpio/gpio_emul.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>
#include <zephyr/ztest.h>

#include "acquisition.h"
#include "acquisition_trace.h"
#include "counters.h"
#include "lsm6dsl_fifo.h"
#include "lsm6dsl_raw.h"
#include "packet.h"
#include "sample_queue.h"
#include "timestamp.h"

#define FAKE_SENSOR_NAME "node_a_fake_imu"
#define MAX_CALLS 8

enum fake_call_kind {
	FAKE_CALL_ATTR_SET,
	FAKE_CALL_TRIGGER_SET,
};

struct fake_call {
	enum fake_call_kind kind;
	enum sensor_channel channel;
	enum sensor_attribute attribute;
	struct sensor_value value;
	struct sensor_trigger trigger;
	sensor_trigger_handler_t handler;
};

struct fake_sensor_state {
	struct fake_call calls[MAX_CALLS];
	size_t call_count;
	int fail_call;
};

static struct fake_sensor_state fake_state;
static uint8_t fake_raw_registers[12];
static int fake_raw_read_result;
static uint8_t fake_raw_start_addr;
static uint32_t fake_raw_num_bytes;
static bool fake_drain_clears_drdy;
static uint8_t fake_arm_races_remaining;
static sensor_trigger_handler_t fake_data_ready_handler;
static uint8_t fake_trigger_arm_calls;
static uint8_t fake_trigger_disarm_calls;
static struct node_a_drdy_timestamp test_stream_timestamp;
static uint32_t test_missing_timestamp_callbacks;
static uint32_t test_published_samples;
static uint64_t test_last_timestamp_us;
static uint8_t fake_fifo_status_registers[2];
static int fake_fifo_status_read_result;
static uint8_t fake_fifo_status_start_addr;
static uint32_t fake_fifo_status_num_bytes;
static const struct gpio_dt_spec test_drdy_gpio = {
	.port = DEVICE_DT_GET(DT_NODELABEL(node_a_test_gpio)),
	.pin = 0,
	.dt_flags = GPIO_ACTIVE_HIGH,
};

static int fake_record_call(const struct fake_call *call)
{
	size_t index = fake_state.call_count;

	zassert_true(index < ARRAY_SIZE(fake_state.calls),
		     "fake call log overflow at index %zu", index);
	fake_state.calls[index] = *call;
	fake_state.call_count++;

	return (fake_state.fail_call == (int)index) ? -EIO : 0;
}

static int fake_attr_set(const struct device *dev, enum sensor_channel channel,
			 enum sensor_attribute attribute,
			 const struct sensor_value *value)
{
	ARG_UNUSED(dev);
	return fake_record_call(&(struct fake_call){
		.kind = FAKE_CALL_ATTR_SET,
		.channel = channel,
		.attribute = attribute,
		.value = *value,
	});
}

static int fake_trigger_set(const struct device *dev,
			    const struct sensor_trigger *trigger,
			    sensor_trigger_handler_t handler)
{
	int rc;

	ARG_UNUSED(dev);
	rc = fake_record_call(&(struct fake_call){
		.kind = FAKE_CALL_TRIGGER_SET,
		.channel = trigger->chan,
		.trigger = *trigger,
		.handler = handler,
	});
	if (rc < 0) {
		return rc;
	}

	fake_data_ready_handler = handler;
	if (handler == NULL) {
		fake_trigger_disarm_calls++;
	} else {
		fake_trigger_arm_calls++;
	}
	if ((handler != NULL) && (fake_arm_races_remaining > 0U)) {
		/* This is the Zephyr LSM6DSL trigger driver's level path: the
		 * line becomes active while sensor_trigger_set() is arming, so
		 * the driver submits a deferred callback without a GPIO edge. */
		fake_arm_races_remaining--;
		zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 1));
		handler(device_get_binding(FAKE_SENSOR_NAME), trigger);
	}

	return 0;
}

static DEVICE_API(sensor, fake_sensor_api) = {
	.attr_set = fake_attr_set,
	.trigger_set = fake_trigger_set,
};

DEVICE_DEFINE(node_a_fake_imu, FAKE_SENSOR_NAME, NULL, NULL, NULL, NULL,
	      POST_KERNEL, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &fake_sensor_api);

static void test_data_ready_handler(const struct device *dev,
				    const struct sensor_trigger *trigger)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(trigger);
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak int node_a_imu_configure(const struct device *imu,
				sensor_trigger_handler_t data_ready_handler)
{
	ARG_UNUSED(imu);
	ARG_UNUSED(data_ready_handler);
	return -ENOSYS;
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak int node_a_imu_arm_data_ready(const struct device *imu,
					     sensor_trigger_handler_t data_ready_handler)
{
	ARG_UNUSED(imu);
	ARG_UNUSED(data_ready_handler);
	return -ENOSYS;
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak int node_a_imu_disarm_data_ready(const struct device *imu)
{
	ARG_UNUSED(imu);
	return -ENOSYS;
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak int node_a_imu_wait_data_ready_inactive(
	const struct gpio_dt_spec *drdy_gpio, uint32_t timeout_ms)
{
	ARG_UNUSED(drdy_gpio);
	ARG_UNUSED(timeout_ms);
	return -ENOSYS;
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak bool node_a_imu_registers_match_config(
	const struct node_a_imu_registers *registers)
{
	ARG_UNUSED(registers);
	return false;
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak int node_a_lsm6dsl_read_raw(
	const struct i2c_dt_spec *spec,
	node_a_lsm6dsl_burst_read_fn burst_read,
	struct node_a_imu_sample *sample)
{
	ARG_UNUSED(spec);
	ARG_UNUSED(burst_read);
	ARG_UNUSED(sample);
	return -ENOSYS;
}

/* RED-phase fallbacks. Production strong definitions replace these symbols. */
__weak int node_a_lsm6dsl_read_fifo_status(
	const struct i2c_dt_spec *spec,
	node_a_lsm6dsl_burst_read_fn burst_read,
	struct node_a_lsm6dsl_fifo_status *status)
{
	ARG_UNUSED(spec);
	ARG_UNUSED(burst_read);
	ARG_UNUSED(status);
	return -ENOSYS;
}

/* RED-phase fallbacks. Production strong definitions replace these symbols. */
__weak void node_a_lsm6dsl_fifo_observer_init(
	struct node_a_lsm6dsl_fifo_observer *observer)
{
	memset(observer, 0, sizeof(*observer));
}

/* RED-phase fallbacks. Production strong definitions replace these symbols. */
__weak void node_a_lsm6dsl_fifo_observe(
	struct node_a_lsm6dsl_fifo_observer *observer,
	const struct node_a_lsm6dsl_fifo_status *status)
{
	ARG_UNUSED(observer);
	ARG_UNUSED(status);
}

/* RED-phase fallbacks. Production strong definitions replace these symbols. */
__weak uint16_t node_a_lsm6dsl_fifo_take_packet_flags(
	struct node_a_lsm6dsl_fifo_observer *observer)
{
	ARG_UNUSED(observer);
	return 0U;
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak void node_a_lsm6dsl_fifo_stats_get(
	struct node_a_lsm6dsl_fifo_observer *observer,
	struct node_a_lsm6dsl_fifo_stats *stats)
{
	ARG_UNUSED(observer);
	memset(stats, 0, sizeof(*stats));
}

static int fake_raw_burst_read(const struct i2c_dt_spec *spec,
			       uint8_t start_addr, uint8_t *buf,
			       uint32_t num_bytes)
{
	ARG_UNUSED(spec);
	fake_raw_start_addr = start_addr;
	fake_raw_num_bytes = num_bytes;
	if (fake_raw_read_result < 0) {
		return fake_raw_read_result;
	}
	if (fake_drain_clears_drdy && (start_addr == 0x22U) &&
	    (num_bytes == 12U)) {
		/* A successful pre-stream output read releases the emulated
		 * level, just as the sensor's output-register read does. */
		zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 0));
	}
	memcpy(buf, fake_raw_registers, num_bytes);
	return 0;
}

static void set_fake_raw_counts(const int16_t gyro[3],
				const int16_t accel[3])
{
	for (size_t axis = 0U; axis < 3U; ++axis) {
		fake_raw_registers[axis * 2U] = (uint8_t)gyro[axis];
		fake_raw_registers[axis * 2U + 1U] =
			(uint8_t)((uint16_t)gyro[axis] >> 8);
		fake_raw_registers[6U + axis * 2U] = (uint8_t)accel[axis];
		fake_raw_registers[6U + axis * 2U + 1U] =
			(uint8_t)((uint16_t)accel[axis] >> 8);
	}
}

static int fake_fifo_status_burst_read(const struct i2c_dt_spec *spec,
				       uint8_t start_addr, uint8_t *buf,
				       uint32_t num_bytes)
{
	ARG_UNUSED(spec);
	fake_fifo_status_start_addr = start_addr;
	fake_fifo_status_num_bytes = num_bytes;
	if (fake_fifo_status_read_result < 0) {
		return fake_fifo_status_read_result;
	}
	memcpy(buf, fake_fifo_status_registers, num_bytes);
	return 0;
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak int node_a_drdy_timestamp_attach(
	struct node_a_drdy_timestamp *timestamp,
	const struct gpio_dt_spec *drdy_gpio)
{
	ARG_UNUSED(timestamp);
	ARG_UNUSED(drdy_gpio);
	return -ENOSYS;
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak bool node_a_drdy_timestamp_take(
	struct node_a_drdy_timestamp *timestamp, uint64_t *timestamp_us)
{
	ARG_UNUSED(timestamp);
	ARG_UNUSED(timestamp_us);
	return false;
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak void node_a_drdy_timestamp_reset(struct node_a_drdy_timestamp *timestamp)
{
	ARG_UNUSED(timestamp);
}

/* RED-phase fallbacks. Production strong definitions replace these symbols. */
__weak void node_a_counters_start(struct node_a_stream_counters *counters,
				  uint32_t clock_epoch)
{
	ARG_UNUSED(counters);
	ARG_UNUSED(clock_epoch);
}

__weak uint32_t node_a_counters_take_sample(
	struct node_a_stream_counters *counters)
{
	ARG_UNUSED(counters);
	return UINT32_MAX;
}

__weak uint32_t node_a_counters_take_packet(
	struct node_a_stream_counters *counters)
{
	ARG_UNUSED(counters);
	return UINT32_MAX;
}

__weak void node_a_counters_reset_clock(
	struct node_a_stream_counters *counters)
{
	ARG_UNUSED(counters);
}

/* RED-phase fallbacks. Production strong definitions replace these symbols. */
__weak void node_a_sample_queue_init(struct node_a_sample_queue *queue)
{
	memset(queue, 0, sizeof(*queue));
}

__weak bool node_a_sample_queue_put(
	struct node_a_sample_queue *queue,
	const struct node_a_imu_sample *sample)
{
	ARG_UNUSED(queue);
	ARG_UNUSED(sample);
	return false;
}

__weak bool node_a_sample_queue_get(struct node_a_sample_queue *queue,
				    struct node_a_imu_sample *sample,
				    k_timeout_t timeout)
{
	ARG_UNUSED(queue);
	ARG_UNUSED(sample);
	ARG_UNUSED(timeout);
	return false;
}

__weak void node_a_sample_queue_stats_get(
	struct node_a_sample_queue *queue,
	struct node_a_sample_queue_stats *stats)
{
	ARG_UNUSED(queue);
	memset(stats, 0, sizeof(*stats));
}

/* RED-phase fallbacks. Production strong definitions replace these symbols. */
__weak uint16_t node_a_sample_queue_take_packet_flags(
	struct node_a_sample_queue *queue)
{
	ARG_UNUSED(queue);
	return 0U;
}

/* RED-phase fallbacks. Production strong definitions replace these symbols. */
__weak uint32_t node_a_packet_crc32c(const uint8_t *data, size_t length)
{
	ARG_UNUSED(data);
	ARG_UNUSED(length);
	return 0U;
}

/* RED-phase fallbacks. Production strong definitions replace these symbols. */
__weak int node_a_packet_encode(const struct node_a_sample_packet *packet,
				uint8_t *buffer, size_t buffer_size,
				size_t *encoded_size)
{
	ARG_UNUSED(packet);
	ARG_UNUSED(buffer);
	ARG_UNUSED(buffer_size);
	ARG_UNUSED(encoded_size);
	return -ENOSYS;
}

/* RED-phase fallbacks. Production strong definitions replace these symbols. */
__weak bool node_a_packet_samples_have_discontinuity(
	const struct node_a_imu_sample *samples, size_t sample_count,
	bool have_previous_sample, uint32_t previous_sample_sequence)
{
	ARG_UNUSED(samples);
	ARG_UNUSED(sample_count);
	ARG_UNUSED(have_previous_sample);
	ARG_UNUSED(previous_sample_sequence);
	return false;
}

/* RED-phase fallback. A production strong definition replaces this symbol. */
__weak uint64_t node_a_ficr_device_id_from_words(uint32_t deviceid0,
							uint32_t deviceid1)
{
	ARG_UNUSED(deviceid0);
	ARG_UNUSED(deviceid1);
	return 0U;
}

static void reset_fake(void *fixture)
{
	ARG_UNUSED(fixture);
	memset(&fake_state, 0, sizeof(fake_state));
	fake_state.fail_call = -1;
	memset(fake_raw_registers, 0, sizeof(fake_raw_registers));
	fake_raw_read_result = 0;
	fake_raw_start_addr = 0U;
	fake_raw_num_bytes = 0U;
	fake_drain_clears_drdy = false;
	fake_arm_races_remaining = 0U;
	fake_data_ready_handler = NULL;
	fake_trigger_arm_calls = 0U;
	fake_trigger_disarm_calls = 0U;
	memset(&test_stream_timestamp, 0, sizeof(test_stream_timestamp));
	test_missing_timestamp_callbacks = 0U;
	test_published_samples = 0U;
	test_last_timestamp_us = 0U;
	memset(fake_fifo_status_registers, 0, sizeof(fake_fifo_status_registers));
	fake_fifo_status_read_result = 0;
	fake_fifo_status_start_addr = 0U;
	fake_fifo_status_num_bytes = 0U;
}

static void reset_test_stream_timestamp(void *context)
{
	node_a_drdy_timestamp_reset(context);
}

static void test_stream_data_ready_handler(const struct device *dev,
					   const struct sensor_trigger *trigger)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(trigger);
	if (!node_a_drdy_timestamp_take(&test_stream_timestamp,
					&test_last_timestamp_us)) {
		test_missing_timestamp_callbacks++;
		return;
	}
	test_published_samples++;
}

ZTEST(node_a_acquisition, test_acquisition_trace_covers_callback_gates_and_raw_result)
{
	struct node_a_acquisition_trace trace;
	struct node_a_acquisition_trace_snapshot snapshot;

	node_a_acquisition_trace_init(&trace);
	node_a_acquisition_trace_note_callback_entry(&trace);
	node_a_acquisition_trace_note_pre_acquisition(&trace);
	node_a_acquisition_trace_note_timestamp_result(&trace, false);

	node_a_acquisition_trace_note_callback_entry(&trace);
	node_a_acquisition_trace_note_timestamp_result(&trace, true);
	node_a_acquisition_trace_note_raw_read_result(&trace, 0);
	node_a_acquisition_trace_note_callback_entry(&trace);
	node_a_acquisition_trace_note_timestamp_result(&trace, true);
	node_a_acquisition_trace_note_raw_read_result(&trace, -EIO);

	node_a_acquisition_trace_snapshot_get(&trace, &snapshot);

	zassert_equal(snapshot.callback_entries, 3U);
	zassert_equal(snapshot.pre_acquisition_callbacks, 1U);
	zassert_equal(snapshot.timestamp_available, 2U);
	zassert_equal(snapshot.timestamp_missing, 1U);
	zassert_equal(snapshot.raw_read_attempts, 2U);
	zassert_equal(snapshot.raw_read_successes, 1U);
	zassert_equal(snapshot.raw_read_failures, 1U);
	zassert_equal(snapshot.last_raw_read_rc, -EIO);
	zassert_false(snapshot.counters_saturated);
}

ZTEST(node_a_acquisition, test_acquisition_trace_tracks_notify_calls_and_max_duration)
{
	struct node_a_acquisition_trace trace;
	struct node_a_acquisition_trace_snapshot snapshot;

	node_a_acquisition_trace_init(&trace);
	node_a_acquisition_trace_note_notify_duration(&trace, 12U);
	node_a_acquisition_trace_note_notify_duration(&trace, 7U);
	node_a_acquisition_trace_note_notify_duration(&trace, 25U);

	node_a_acquisition_trace_snapshot_get(&trace, &snapshot);

	/* Durations are measured in microseconds; the maximum must not be lowered
	 * by a later notification that completes more quickly.
	 */
	zassert_equal(snapshot.notify_calls, 3U);
	zassert_equal(snapshot.notify_max_duration, 25U);
}

ZTEST(node_a_acquisition, test_drains_one_raw_frame_before_data_ready_rearm)
{
	const struct i2c_dt_spec spec = {0};
	int rc = node_a_imu_drain_data_ready(&spec, fake_raw_burst_read);

	zassert_ok(rc, "data-ready drain returned %d", rc);
	zassert_equal(fake_raw_start_addr, 0x22U);
	zassert_equal(fake_raw_num_bytes, 12U);
}

ZTEST(node_a_acquisition, test_configures_ranges_odrs_then_data_ready)
{
	const struct device *imu = device_get_binding(FAKE_SENSOR_NAME);
	int rc = node_a_imu_configure(imu, test_data_ready_handler);

	zassert_ok(rc, "configuration returned %d", rc);
	zassert_equal(fake_state.call_count, 5U,
		      "configuration made %zu calls, expected 5",
		      fake_state.call_count);

	struct fake_call *accel_range = &fake_state.calls[0];
	zassert_equal(accel_range->kind, FAKE_CALL_ATTR_SET);
	zassert_equal(accel_range->channel, SENSOR_CHAN_ACCEL_XYZ);
	zassert_equal(accel_range->attribute, SENSOR_ATTR_FULL_SCALE);
	/* Source: M1 contract v0.1 specifies +/-4 g; Zephyr sensor API encodes
	 * accelerometer full scale as SI acceleration before driver conversion.
	 */
	zassert_equal(sensor_ms2_to_g(&accel_range->value), 4,
		      "accel range was %d g, expected 4 g",
		      sensor_ms2_to_g(&accel_range->value));

	struct fake_call *gyro_range = &fake_state.calls[1];
	zassert_equal(gyro_range->kind, FAKE_CALL_ATTR_SET);
	zassert_equal(gyro_range->channel, SENSOR_CHAN_GYRO_XYZ);
	zassert_equal(gyro_range->attribute, SENSOR_ATTR_FULL_SCALE);
	/* Source: M1 contract v0.1 specifies +/-500 degrees/s; Zephyr sensor API
	 * encodes gyroscope full scale as rad/s before driver conversion.
	 */
	zassert_equal(sensor_rad_to_degrees(&gyro_range->value), 500,
		      "gyro range was %d dps, expected 500 dps",
		      sensor_rad_to_degrees(&gyro_range->value));

	for (size_t index = 2; index < 4; ++index) {
		struct fake_call *odr = &fake_state.calls[index];

		zassert_equal(odr->kind, FAKE_CALL_ATTR_SET);
		zassert_equal(odr->attribute, SENSOR_ATTR_SAMPLING_FREQUENCY);
		/* Source: LSM6DS3TR-C hardware profile selects the 104 Hz ODR. */
		zassert_equal(odr->value.val1, 104,
			      "ODR call %zu was %d Hz, expected 104 Hz", index,
			      odr->value.val1);
		zassert_equal(odr->value.val2, 0);
	}
	zassert_equal(fake_state.calls[2].channel, SENSOR_CHAN_ACCEL_XYZ);
	zassert_equal(fake_state.calls[3].channel, SENSOR_CHAN_GYRO_XYZ);

	struct fake_call *trigger = &fake_state.calls[4];
	zassert_equal(trigger->kind, FAKE_CALL_TRIGGER_SET);
	zassert_equal(trigger->trigger.type, SENSOR_TRIG_DATA_READY);
	zassert_equal(trigger->trigger.chan, SENSOR_CHAN_ACCEL_XYZ);
	zassert_equal_ptr(trigger->handler, test_data_ready_handler);
}

ZTEST(node_a_acquisition, test_arms_data_ready_trigger_on_explicit_request)
{
	const struct device *imu = device_get_binding(FAKE_SENSOR_NAME);
	int rc = node_a_imu_arm_data_ready(imu, test_data_ready_handler);

	zassert_ok(rc, "trigger arming returned %d", rc);
	zassert_equal(fake_state.call_count, 1U,
		      "trigger arming made %zu calls, expected 1",
		      fake_state.call_count);
	zassert_equal(fake_state.calls[0].kind, FAKE_CALL_TRIGGER_SET);
	zassert_equal(fake_state.calls[0].trigger.type, SENSOR_TRIG_DATA_READY);
	zassert_equal(fake_state.calls[0].trigger.chan, SENSOR_CHAN_ACCEL_XYZ);
	zassert_equal_ptr(fake_state.calls[0].handler, test_data_ready_handler);
}

ZTEST(node_a_acquisition, test_disarms_data_ready_trigger_on_explicit_request)
{
	const struct device *imu = device_get_binding(FAKE_SENSOR_NAME);
	int rc = node_a_imu_disarm_data_ready(imu);

	zassert_ok(rc, "trigger disarming returned %d", rc);
	zassert_equal(fake_state.call_count, 1U,
		      "trigger disarming made %zu calls, expected 1",
		      fake_state.call_count);
	zassert_equal(fake_state.calls[0].kind, FAKE_CALL_TRIGGER_SET);
	zassert_equal(fake_state.calls[0].trigger.type, SENSOR_TRIG_DATA_READY);
	zassert_equal(fake_state.calls[0].trigger.chan, SENSOR_CHAN_ACCEL_XYZ);
	zassert_is_null(fake_state.calls[0].handler);
}

ZTEST(node_a_acquisition, test_data_ready_rearm_requires_inactive_gpio_level)
{
	zassert_true(gpio_is_ready_dt(&test_drdy_gpio),
		     "test data-ready GPIO is not ready");
	zassert_ok(gpio_pin_configure_dt(&test_drdy_gpio, GPIO_INPUT));
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 0));
	zassert_ok(node_a_imu_wait_data_ready_inactive(&test_drdy_gpio, 0U));

	/* A level still asserted at the driver's arm boundary must not be treated
	 * as a timestamped edge; the production boundary waits it out. */
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 1));
	zassert_equal(node_a_imu_wait_data_ready_inactive(&test_drdy_gpio, 0U),
		      -ETIMEDOUT);
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 0));
}

ZTEST(node_a_acquisition,
	test_rearm_retries_arm_toctou_and_next_edge_publishes_timestamped_sample)
{
	const struct device *imu = device_get_binding(FAKE_SENSOR_NAME);
	const struct i2c_dt_spec spec = {0};
	struct node_a_imu_rearm_result result = {0};
	int rc;

	zassert_true(gpio_is_ready_dt(&test_drdy_gpio),
		     "test data-ready GPIO is not ready");
	zassert_ok(gpio_pin_configure_dt(&test_drdy_gpio, GPIO_INPUT));
	zassert_ok(gpio_pin_interrupt_configure_dt(
		&test_drdy_gpio, GPIO_INT_DISABLE));
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 0));
	zassert_ok(node_a_drdy_timestamp_attach(&test_stream_timestamp,
						&test_drdy_gpio));

	/* The first arm deterministically raises INT1 inside the fake driver's
	 * sensor_trigger_set() call. Its callback is deliberately delivered
	 * without running the GPIO timestamp callback, matching the in-tree
	 * LSM6DSL level path. The next drain releases that level. */
	fake_drain_clears_drdy = true;
	fake_arm_races_remaining = 1U;
	rc = node_a_imu_quiesce_and_arm_data_ready(
		imu, &test_drdy_gpio, &spec, fake_raw_burst_read,
		test_stream_data_ready_handler, reset_test_stream_timestamp,
		&test_stream_timestamp, 5U, 2U, &result);

	zassert_ok(rc, "quiesce/re-arm returned %d", rc);
	zassert_equal(result.state, NODE_A_IMU_REARM_ARMED);
	zassert_equal(result.attempts, 2U,
		      "arm race was not retried within the bound");
	zassert_equal(result.race_retries, 1U,
		      "arm race was not recorded exactly once");
	zassert_equal(fake_trigger_arm_calls, 2U,
		      "expected one retry arm after the level-path callback");
	zassert_equal(fake_trigger_disarm_calls, 2U,
		      "each arm attempt must be preceded by a disarm");
	zassert_equal(gpio_pin_get_dt(&test_drdy_gpio), 0,
		      "successful re-arm returned with INT1 asserted");

	/* The deferred callback caused by the arm race has no ISR timestamp and
	 * therefore must not publish a sample or be repaired with handler time. */
	zassert_equal(test_missing_timestamp_callbacks, 1U,
		      "the missing-timestamp callback was not observed");
	zassert_equal(test_published_samples, 0U,
		      "an un-timestamped callback published a sample");

	/* A later real rising edge passes through the GPIO timestamp callback and
	 * then the driver's deferred callback. This is the liveness assertion: a
	 * recovered first arm cannot leave the stream permanently dead. */
	zassert_ok(gpio_pin_interrupt_configure_dt(
		&test_drdy_gpio, GPIO_INT_EDGE_TO_ACTIVE));
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 0));
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 1));
	zassert_not_null(fake_data_ready_handler,
			"successful arm did not retain the data-ready handler");
	fake_data_ready_handler(imu, NULL);
	zassert_equal(test_published_samples, 1U,
		      "next real edge did not publish one timestamped sample");
	zassert_true(test_last_timestamp_us > 0U,
		     "next real edge did not provide an ISR timestamp");
	zassert_equal(test_missing_timestamp_callbacks, 1U,
		      "real edge was treated as missing an ISR timestamp");

	zassert_ok(gpio_pin_interrupt_configure_dt(
		&test_drdy_gpio, GPIO_INT_DISABLE));
	zassert_ok(gpio_remove_callback(test_drdy_gpio.port,
					&test_stream_timestamp.callback));
}

ZTEST(node_a_acquisition,
	test_rearm_enters_explicit_fatal_after_bounded_quiet_attempts)
{
	const struct device *imu = device_get_binding(FAKE_SENSOR_NAME);
	const struct i2c_dt_spec spec = {0};
	struct node_a_imu_rearm_result result = {0};
	int rc;

	zassert_true(gpio_is_ready_dt(&test_drdy_gpio),
		     "test data-ready GPIO is not ready");
	zassert_ok(gpio_pin_configure_dt(&test_drdy_gpio, GPIO_INPUT));
	zassert_ok(gpio_pin_interrupt_configure_dt(
		&test_drdy_gpio, GPIO_INT_DISABLE));
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 1));

	/* The emulated sensor never releases INT1. Each attempt has a finite
	 * quiet wait, and the state machine must expose fatal rather than spin
	 * forever or arm a callback against a permanently active line. */
	rc = node_a_imu_quiesce_and_arm_data_ready(
		imu, &test_drdy_gpio, &spec, fake_raw_burst_read,
		test_stream_data_ready_handler, reset_test_stream_timestamp,
		&test_stream_timestamp, 1U, 3U, &result);

	zassert_equal(rc, -ETIMEDOUT,
		      "permanently active INT1 returned %d instead of timeout", rc);
	zassert_equal(result.state, NODE_A_IMU_REARM_FATAL,
		      "permanently active INT1 did not enter fatal state");
	zassert_equal(result.attempts, 3U,
		      "fatal transition exceeded or ignored the retry bound");
	zassert_equal(result.race_retries, 0U,
		      "no arm occurred while quieting was impossible");
	zassert_equal(fake_trigger_arm_calls, 0U,
		      "fatal quiet failure nevertheless armed the trigger");
	zassert_equal(fake_trigger_disarm_calls, 3U,
		      "fatal path did not perform bounded disarm attempts");
}

ZTEST(node_a_acquisition, test_physical_image_selects_node_b_identity)
{
	/* The physical Node B image must not inherit the Node A packet identity. */
	zassert_equal(NODE_A_PACKET_NODE_ID, 2U,
		      "Node-B test image selected node ID %u",
		      NODE_A_PACKET_NODE_ID);
}

ZTEST(node_a_acquisition, test_combines_ficr_device_id_words_in_contract_order)
{
	/* M1 encodes (DEVICEID[1] << 32) | DEVICEID[0]. */
	zassert_equal(node_a_ficr_device_id_from_words(0x89abcdefU,
							0x01234567U),
		      0x0123456789abcdefULL);
}

ZTEST(node_a_acquisition, test_stops_configuration_at_first_driver_error)
{
	const struct device *imu = device_get_binding(FAKE_SENSOR_NAME);

	for (int fail_call = 0; fail_call < 5; ++fail_call) {
		reset_fake(NULL);
		fake_state.fail_call = fail_call;

		int rc = node_a_imu_configure(imu, test_data_ready_handler);

		zassert_equal(rc, -EIO,
			      "failure at call %d returned %d, expected -EIO",
			      fail_call, rc);
		zassert_equal(fake_state.call_count, (size_t)fail_call + 1U,
			      "failure at call %d made %zu calls", fail_call,
			      fake_state.call_count);
	}
}

ZTEST(node_a_acquisition, test_reads_lsm6dsl_raw_counts_in_register_order)
{
	const struct i2c_dt_spec spec = {0};
	struct node_a_imu_sample sample = {0};
	const uint8_t raw_registers[12] = {
		0x34, 0x12, 0x00, 0x80, 0xff, 0x7f,
		0x01, 0xff, 0xfe, 0x00, 0x00, 0x40,
	};

	memcpy(fake_raw_registers, raw_registers, sizeof(raw_registers));
	int rc = node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read,
					 &sample);

	zassert_ok(rc, "raw sample read returned %d", rc);
	/* Source: LSM6DS3TR-C register map places gyro OUTX_L_G at 0x22,
	 * followed by three little-endian gyro axes and three little-endian
	 * accelerometer axes through OUTZ_H_XL at 0x2d.
	 */
	zassert_equal(fake_raw_start_addr, 0x22U);
	zassert_equal(fake_raw_num_bytes, 12U);
	zassert_equal(sample.gyro_raw[0], 0x1234);
	zassert_equal(sample.gyro_raw[1], INT16_MIN);
	zassert_equal(sample.gyro_raw[2], INT16_MAX);
	zassert_equal(sample.accel_raw[0], -255);
	zassert_equal(sample.accel_raw[1], 254);
	zassert_equal(sample.accel_raw[2], 0x4000);
}

ZTEST(node_a_acquisition, test_raw_read_error_preserves_sample)
{
	const struct i2c_dt_spec spec = {0};
	struct node_a_imu_sample sample = {
		.accel_raw = {101, 102, 103},
		.gyro_raw = {-101, -102, -103},
	};
	const int16_t expected_accel[3] = {101, 102, 103};
	const int16_t expected_gyro[3] = {-101, -102, -103};

	fake_raw_read_result = -EIO;
	int rc = node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read,
					 &sample);

	zassert_equal(rc, -EIO, "raw bus error changed to %d", rc);
	/* Source: the literal pre-read sample above. A failed bus transaction
	 * must not publish a partially updated raw sample.
	 */
	zassert_mem_equal(sample.accel_raw, expected_accel,
			  sizeof(expected_accel));
	zassert_mem_equal(sample.gyro_raw, expected_gyro,
			  sizeof(expected_gyro));
}

ZTEST(node_a_acquisition,
	test_raw_counts_mark_accel_clipping_only_at_int16_endpoints)
{
	const struct i2c_dt_spec spec = {0};
	const int16_t normal_gyro[3] = {0, 0, 0};
	const int16_t accel_inside_positive[3] = {INT16_MAX - 1, 0, 0};
	const int16_t accel_inside_negative[3] = {INT16_MIN + 1, 0, 0};
	const int16_t accel_positive_saturation[3] = {INT16_MAX, 0, 0};
	const int16_t accel_negative_saturation[3] = {INT16_MIN, 0, 0};
	struct node_a_imu_sample sample;

	/* The LSM6DS3TR-C declares 16-bit two's-complement output and 0.122 mg/LSB
	 * at the configured +/-4 g. 4,000 mg / 0.122 mg/LSB is 32,786.9 counts,
	 * beyond the positive int16 limit. Therefore the auditable acceleration
	 * code criterion is the two representable int16 endpoints (+32767/-32768),
	 * not an arbitrary "near full-scale" margin. */
	set_fake_raw_counts(normal_gyro, accel_inside_positive);
	sample = (struct node_a_imu_sample){0};
	zassert_ok(node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read, &sample));
	zassert_equal(sample.flags, 0U,
		      "one code inside positive int16 endpoint was clipped");

	set_fake_raw_counts(normal_gyro, accel_inside_negative);
	sample = (struct node_a_imu_sample){0};
	zassert_ok(node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read, &sample));
	zassert_equal(sample.flags, 0U,
		      "one code inside negative int16 endpoint was clipped");

	set_fake_raw_counts(normal_gyro, accel_positive_saturation);
	sample = (struct node_a_imu_sample){0};
	zassert_ok(node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read, &sample));
	zassert_true((sample.flags & NODE_A_SAMPLE_FLAG_ACCEL_CLIPPED) != 0U,
		     "positive int16 endpoint did not set ACCEL_CLIPPED");
	zassert_equal(sample.flags & NODE_A_SAMPLE_FLAG_GYRO_CLIPPED, 0U);

	set_fake_raw_counts(normal_gyro, accel_negative_saturation);
	sample = (struct node_a_imu_sample){0};
	zassert_ok(node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read, &sample));
	zassert_true((sample.flags & NODE_A_SAMPLE_FLAG_ACCEL_CLIPPED) != 0U,
		     "negative int16 endpoint did not set ACCEL_CLIPPED");
	zassert_equal(sample.flags & NODE_A_SAMPLE_FLAG_GYRO_CLIPPED, 0U);
}

ZTEST(node_a_acquisition,
	test_raw_counts_mark_gyro_clipping_at_configured_full_scale_code)
{
	const struct i2c_dt_spec spec = {0};
	const int16_t normal_accel[3] = {0, 0, 0};
	const int16_t gyro_inside_positive[3] = {28571, 0, 0};
	const int16_t gyro_inside_negative[3] = {-28571, 0, 0};
	const int16_t gyro_full_scale_positive[3] = {28572, 0, 0};
	const int16_t gyro_full_scale_negative[3] = {-28572, 0, 0};
	struct node_a_imu_sample sample;

	/* At +/-500 dps the datasheet nominal sensitivity is 17.50 mdps/LSB.
	 * The first integer code whose nominal magnitude reaches the configured
	 * range is ceil(500,000 mdps / 17.50 mdps/LSB) = 28,572. The test uses
	 * the hand-derived boundary: 28,571 is inside and +/-28,572 is flagged.
	 * This is a raw-code full-scale criterion, not a claim of analog hardware
	 * saturation and not a near-full-scale heuristic. */
	set_fake_raw_counts(gyro_inside_positive, normal_accel);
	sample = (struct node_a_imu_sample){0};
	zassert_ok(node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read, &sample));
	zassert_equal(sample.flags, 0U,
		      "gyro code immediately inside configured range was clipped");

	set_fake_raw_counts(gyro_inside_negative, normal_accel);
	sample = (struct node_a_imu_sample){0};
	zassert_ok(node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read, &sample));
	zassert_equal(sample.flags, 0U,
		      "negative gyro code immediately inside configured range was clipped");

	set_fake_raw_counts(gyro_full_scale_positive, normal_accel);
	sample = (struct node_a_imu_sample){0};
	zassert_ok(node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read, &sample));
	zassert_true((sample.flags & NODE_A_SAMPLE_FLAG_GYRO_CLIPPED) != 0U,
		     "positive configured full-scale code did not set GYRO_CLIPPED");
	zassert_equal(sample.flags & NODE_A_SAMPLE_FLAG_ACCEL_CLIPPED, 0U);

	set_fake_raw_counts(gyro_full_scale_negative, normal_accel);
	sample = (struct node_a_imu_sample){0};
	zassert_ok(node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read, &sample));
	zassert_true((sample.flags & NODE_A_SAMPLE_FLAG_GYRO_CLIPPED) != 0U,
		     "negative configured full-scale code did not set GYRO_CLIPPED");
	zassert_equal(sample.flags & NODE_A_SAMPLE_FLAG_ACCEL_CLIPPED, 0U);
}

ZTEST(node_a_acquisition, test_raw_counts_mark_clipping_when_any_axis_triggers)
{
	const struct i2c_dt_spec spec = {0};
	const int16_t normal_accel[3] = {0, 0, 0};
	const int16_t normal_gyro[3] = {0, 0, 0};
	struct node_a_imu_sample sample;

	/* Each axis is checked independently; clipping on one axis is sufficient
	 * to mark the complete sample while all raw counts remain transmitted. */
	for (size_t axis = 0U; axis < 3U; ++axis) {
		int16_t accel[3] = {0, 0, 0};

		accel[axis] = INT16_MAX;
		set_fake_raw_counts(normal_gyro, accel);
		sample = (struct node_a_imu_sample){0};
		zassert_ok(node_a_lsm6dsl_read_raw(
			&spec, fake_raw_burst_read, &sample));
		zassert_true((sample.flags & NODE_A_SAMPLE_FLAG_ACCEL_CLIPPED) != 0U,
			     "accel axis %zu did not trigger clipping", axis);
	}

	for (size_t axis = 0U; axis < 3U; ++axis) {
		int16_t gyro[3] = {0, 0, 0};

		gyro[axis] = 28572;
		set_fake_raw_counts(gyro, normal_accel);
		sample = (struct node_a_imu_sample){0};
		zassert_ok(node_a_lsm6dsl_read_raw(
			&spec, fake_raw_burst_read, &sample));
		zassert_true((sample.flags & NODE_A_SAMPLE_FLAG_GYRO_CLIPPED) != 0U,
			     "gyro axis %zu did not trigger clipping", axis);
	}
}

ZTEST(node_a_acquisition, test_raw_counts_keep_normal_sample_unclipped)
{
	const struct i2c_dt_spec spec = {0};
	const int16_t accel[3] = {123, -456, 16384};
	const int16_t gyro[3] = {100, -200, 1000};
	struct node_a_imu_sample sample = {0};

	set_fake_raw_counts(gyro, accel);
	zassert_ok(node_a_lsm6dsl_read_raw(&spec, fake_raw_burst_read, &sample));
	zassert_equal(sample.flags, 0U,
		      "normal raw counts unexpectedly set a clipping flag");
}

ZTEST(node_a_acquisition, test_reads_fifo_status_register_pair)
{
	const struct i2c_dt_spec spec = {0};
	struct node_a_lsm6dsl_fifo_status status = {0};

	/* FIFO_STATUS1/2: DIFF_FIFO=0x534, watermark, overrun and full set. */
	fake_fifo_status_registers[0] = 0x34;
	fake_fifo_status_registers[1] = 0xe5;

	int rc = node_a_lsm6dsl_read_fifo_status(
		&spec, fake_fifo_status_burst_read, &status);

	zassert_ok(rc, "FIFO status read returned %d", rc);
	/* Source: LSM6DS3TR-C FIFO_STATUS1 is the low byte of DIFF_FIFO;
	 * FIFO_STATUS2 carries DIFF_FIFO[10:8] in bits 2:0 and the level flags
	 * in bits 7:4. The adapter preserves both raw bytes for auditability.
	 */
	zassert_equal(fake_fifo_status_start_addr, 0x3aU);
	zassert_equal(fake_fifo_status_num_bytes, 2U);
	zassert_equal(status.status1_raw, 0x34U);
	zassert_equal(status.status2_raw, 0xe5U);
	zassert_equal(status.unread_words, 0x534U);
	zassert_true(status.watermark);
	zassert_true(status.overrun);
	zassert_true(status.full);
	zassert_false(status.empty);
}

ZTEST(node_a_acquisition, test_fifo_status_read_error_preserves_snapshot)
{
	const struct i2c_dt_spec spec = {0};
	const struct node_a_lsm6dsl_fifo_status expected = {
		.status1_raw = 0x12,
		.status2_raw = 0x65,
		.unread_words = 0x512,
		.watermark = true,
		.overrun = true,
		.full = true,
		.empty = false,
	};
	struct node_a_lsm6dsl_fifo_status status = expected;

	fake_fifo_status_read_result = -EIO;
	int rc = node_a_lsm6dsl_read_fifo_status(
		&spec, fake_fifo_status_burst_read, &status);

	zassert_equal(rc, -EIO, "FIFO status bus error changed to %d", rc);
	/* A status transaction is staged just like the raw sample transaction:
	 * a failed read must not publish a partially decoded snapshot.
	 */
	zassert_mem_equal(&status, &expected, sizeof(status));
}

ZTEST(node_a_acquisition, test_fifo_overrun_observer_counts_assertion_edges)
{
	struct node_a_lsm6dsl_fifo_observer observer;
	const struct node_a_lsm6dsl_fifo_status clear = {0};
	const struct node_a_lsm6dsl_fifo_status overrun = {
		.overrun = true,
	};

	node_a_lsm6dsl_fifo_observer_init(&observer);
	node_a_lsm6dsl_fifo_observe(&observer, &clear);
	zassert_equal(observer.sensor_fifo_overruns, 0U);

	node_a_lsm6dsl_fifo_observe(&observer, &overrun);
	zassert_equal(observer.sensor_fifo_overruns, 1U);
	/* The sensor flag is level-like until FIFO state is reset; repeated status
	 * reads while it remains asserted are one hardware event, not many.
	 */
	node_a_lsm6dsl_fifo_observe(&observer, &overrun);
	zassert_equal(observer.sensor_fifo_overruns, 1U);

	node_a_lsm6dsl_fifo_observe(&observer, &clear);
	node_a_lsm6dsl_fifo_observe(&observer, &overrun);
	zassert_equal(observer.sensor_fifo_overruns, 2U);
}

ZTEST(node_a_acquisition, test_fifo_overrun_counter_saturates)
{
	struct node_a_lsm6dsl_fifo_observer observer = {
		.sensor_fifo_overruns = UINT32_MAX - 1U,
	};
	const struct node_a_lsm6dsl_fifo_status clear = {0};
	const struct node_a_lsm6dsl_fifo_status overrun = {
		.overrun = true,
	};

	node_a_lsm6dsl_fifo_observe(&observer, &overrun);
	zassert_equal(observer.sensor_fifo_overruns, UINT32_MAX);
	zassert_true(observer.counters_saturated);

	node_a_lsm6dsl_fifo_observe(&observer, &clear);
	node_a_lsm6dsl_fifo_observe(&observer, &overrun);
	zassert_equal(observer.sensor_fifo_overruns, UINT32_MAX);
	zassert_true(observer.counters_saturated);
}

ZTEST(node_a_acquisition, test_fifo_overrun_event_becomes_one_packet_flag)
{
	struct node_a_lsm6dsl_fifo_observer observer;
	const struct node_a_lsm6dsl_fifo_status overrun = {
		.overrun = true,
	};

	node_a_lsm6dsl_fifo_observer_init(&observer);
	node_a_lsm6dsl_fifo_observe(&observer, &overrun);

	zassert_equal(node_a_lsm6dsl_fifo_take_packet_flags(&observer),
		      NODE_A_PACKET_FLAG_SENSOR_FIFO_OVERRUN);
	zassert_equal(node_a_lsm6dsl_fifo_take_packet_flags(&observer), 0U);
}

ZTEST(node_a_acquisition, test_fifo_stats_snapshot_is_copied)
{
	struct node_a_lsm6dsl_fifo_observer observer = {
		.sensor_fifo_overruns = 17U,
		.counters_saturated = true,
	};
	struct node_a_lsm6dsl_fifo_stats stats = {0};

	node_a_lsm6dsl_fifo_stats_get(&observer, &stats);

	zassert_equal(stats.sensor_fifo_overruns, 17U);
	zassert_true(stats.counters_saturated);
}

ZTEST(node_a_acquisition, test_accepts_requested_register_configuration)
{
	/* Hand-derived from the LSM6DS3TR-C register map: WHO_AM_I=0x6a,
	 * CTRL1_XL ODR=0b0100 and FS_XL=0b10, CTRL2_G ODR=0b0100 and
	 * FS_G=0b01, and both INT1 data-ready routing bits set.
	 */
	const struct node_a_imu_registers registers = {
		.who_am_i = 0x6a,
		.int1_ctrl = 0x03,
		.ctrl1_xl = 0x48,
		.ctrl2_g = 0x44,
	};

	zassert_true(node_a_imu_registers_match_config(&registers),
		     "requested register configuration was rejected");
}

ZTEST(node_a_acquisition, test_rejects_wrong_requested_register_fields)
{
	static const struct node_a_imu_registers wrong_registers[] = {
		{.who_am_i = 0x00, .int1_ctrl = 0x03, .ctrl1_xl = 0x48,
		 .ctrl2_g = 0x44},
		{.who_am_i = 0x6a, .int1_ctrl = 0x01, .ctrl1_xl = 0x48,
		 .ctrl2_g = 0x44},
		{.who_am_i = 0x6a, .int1_ctrl = 0x03, .ctrl1_xl = 0x38,
		 .ctrl2_g = 0x44},
		{.who_am_i = 0x6a, .int1_ctrl = 0x03, .ctrl1_xl = 0x44,
		 .ctrl2_g = 0x44},
		{.who_am_i = 0x6a, .int1_ctrl = 0x03, .ctrl1_xl = 0x48,
		 .ctrl2_g = 0x34},
		{.who_am_i = 0x6a, .int1_ctrl = 0x03, .ctrl1_xl = 0x48,
		 .ctrl2_g = 0x48},
	};

	for (size_t index = 0; index < ARRAY_SIZE(wrong_registers); ++index) {
		zassert_false(node_a_imu_registers_match_config(
			      &wrong_registers[index]),
			      "wrong register case %zu was accepted", index);
	}
	zassert_false(node_a_imu_registers_match_config(NULL),
		      "NULL register snapshot was accepted");
}

ZTEST(node_a_acquisition, test_captures_monotonic_time_at_drdy_gpio_callback)
{
	struct node_a_drdy_timestamp timestamp = {0};
	uint64_t first_timestamp_us;
	uint64_t second_timestamp_us;
	uint64_t before_us;
	uint64_t after_us;

	zassert_true(gpio_is_ready_dt(&test_drdy_gpio),
		     "test data-ready GPIO is not ready");
	zassert_ok(gpio_pin_configure_dt(&test_drdy_gpio, GPIO_INPUT));
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 0));
	zassert_ok(gpio_pin_interrupt_configure_dt(
		&test_drdy_gpio, GPIO_INT_EDGE_TO_ACTIVE));

	zassert_ok(node_a_drdy_timestamp_attach(&timestamp, &test_drdy_gpio));
	zassert_false(node_a_drdy_timestamp_take(&timestamp,
						 &first_timestamp_us),
		      "timestamp was available before a data-ready edge");

	before_us = k_ticks_to_us_floor64((uint64_t)k_uptime_ticks());
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 1));
	after_us = k_ticks_to_us_floor64((uint64_t)k_uptime_ticks());
	zassert_true(node_a_drdy_timestamp_take(&timestamp,
						&first_timestamp_us),
		     "first data-ready edge did not publish a timestamp");
	/* Source: the callback and these bounds use the same Zephyr monotonic
	 * uptime-tick clock; a callback-entry capture must lie between them.
	 */
	zassert_true(first_timestamp_us >= before_us,
		     "ISR timestamp %llu us preceded lower bound %llu us",
		     first_timestamp_us, before_us);
	zassert_true(first_timestamp_us <= after_us,
		     "ISR timestamp %llu us exceeded upper bound %llu us",
		     first_timestamp_us, after_us);
	zassert_false(node_a_drdy_timestamp_take(&timestamp,
						 &second_timestamp_us),
		      "one edge produced more than one consumable timestamp");

	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 0));
	k_sleep(K_MSEC(20));
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 1));
	zassert_true(node_a_drdy_timestamp_take(&timestamp,
						&second_timestamp_us),
		     "second data-ready edge did not publish a timestamp");
	/* Source: DATA_FORMAT.md requires monotonically increasing per-sample
	 * timestamps; the two rising edges are separated by a 20 ms kernel delay,
	 * exceeding this QEMU target's 10 ms tick period.
	 */
	zassert_true(second_timestamp_us > first_timestamp_us,
		     "timestamps were not strictly monotonic: %llu then %llu us",
		     first_timestamp_us, second_timestamp_us);

	zassert_ok(gpio_remove_callback(test_drdy_gpio.port,
					&timestamp.callback));
}

ZTEST(node_a_acquisition, test_discards_pending_drdy_timestamp_at_stream_boundary)
{
	struct node_a_drdy_timestamp timestamp = {0};
	uint64_t timestamp_us;

	zassert_true(gpio_is_ready_dt(&test_drdy_gpio),
		     "test data-ready GPIO is not ready");
	zassert_ok(gpio_pin_configure_dt(&test_drdy_gpio, GPIO_INPUT));
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 0));
	zassert_ok(gpio_pin_interrupt_configure_dt(
		&test_drdy_gpio, GPIO_INT_EDGE_TO_ACTIVE));
	zassert_ok(node_a_drdy_timestamp_attach(&timestamp, &test_drdy_gpio));
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 1));
	zassert_true(node_a_drdy_timestamp_take(&timestamp, &timestamp_us));

	/* Recreate a pre-stream edge that arrived after the last deferred callback
	 * drained its timestamp. The boundary reset must make it unconsumable. */
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 0));
	zassert_ok(gpio_emul_input_set_dt(&test_drdy_gpio, 1));
	node_a_drdy_timestamp_reset(&timestamp);
	zassert_false(node_a_drdy_timestamp_take(&timestamp, &timestamp_us));

	zassert_ok(gpio_remove_callback(test_drdy_gpio.port,
					&timestamp.callback));
}

ZTEST(node_a_acquisition, test_assigns_sample_and_packet_sequences_independently)
{
	struct node_a_stream_counters counters;

	node_a_counters_start(&counters, 7U);

	/* Source: the frozen M1 contract requires independent uint32 sample and
	 * packet counters, with the first item in an epoch numbered zero.
	 */
	zassert_equal(node_a_counters_take_sample(&counters), 0U);
	zassert_equal(node_a_counters_take_sample(&counters), 1U);
	zassert_equal(node_a_counters_take_packet(&counters), 0U);
	zassert_equal(node_a_counters_take_sample(&counters), 2U);
	zassert_equal(node_a_counters_take_packet(&counters), 1U);
	zassert_equal(counters.clock_epoch, 7U);
}

ZTEST(node_a_acquisition, test_wraps_each_sequence_modulo_uint32)
{
	struct node_a_stream_counters counters = {
		.clock_epoch = 3U,
		.sample_counter = UINT32_MAX,
		.packet_counter = UINT32_MAX,
	};

	/* Source: the frozen M1 contract defines both sequence counters as
	 * unsigned 32-bit values and treats modulo wrap as continuity.
	 */
	zassert_equal(node_a_counters_take_sample(&counters), UINT32_MAX);
	zassert_equal(node_a_counters_take_sample(&counters), 0U);
	zassert_equal(node_a_counters_take_packet(&counters), UINT32_MAX);
	zassert_equal(node_a_counters_take_packet(&counters), 0U);
	zassert_equal(counters.clock_epoch, 3U);
}

ZTEST(node_a_acquisition, test_new_boot_epoch_clears_both_sequences)
{
	struct node_a_stream_counters counters = {
		.clock_epoch = 9U,
		.sample_counter = 123U,
		.packet_counter = 45U,
	};

	/* A reboot supplies its new epoch; initialization must not leak sequence
	 * state from the previous boot into that epoch.
	 */
	node_a_counters_start(&counters, 10U);

	zassert_equal(counters.clock_epoch, 10U);
	zassert_equal(node_a_counters_take_sample(&counters), 0U);
	zassert_equal(node_a_counters_take_packet(&counters), 0U);
}

ZTEST(node_a_acquisition, test_clock_reset_advances_epoch_and_restarts_sequences)
{
	struct node_a_stream_counters counters;

	node_a_counters_start(&counters, 41U);
	(void)node_a_counters_take_sample(&counters);
	(void)node_a_counters_take_sample(&counters);
	(void)node_a_counters_take_packet(&counters);

	/* Source: the frozen M1 contract requires a clock/acquisition reset to
	 * advance clock_epoch before the next sample. Sequence audit restarts at
	 * that epoch boundary.
	 */
	node_a_counters_reset_clock(&counters);

	zassert_equal(counters.clock_epoch, 42U);
	zassert_equal(node_a_counters_take_sample(&counters), 0U);
	zassert_equal(node_a_counters_take_packet(&counters), 0U);
}

ZTEST(node_a_acquisition, test_sample_queue_preserves_fifo_values_and_metadata)
{
	struct node_a_sample_queue queue;
	const struct node_a_imu_sample first = {
		.clock_epoch = 7U,
		.sample_sequence = 41U,
		.timestamp_us = 123456U,
		.accel_raw = {101, -202, 303},
		.gyro_raw = {-404, 505, -606},
	};
	const struct node_a_imu_sample second = {
		.clock_epoch = 7U,
		.sample_sequence = 42U,
		.timestamp_us = 133071U,
		.accel_raw = {-111, 222, -333},
		.gyro_raw = {444, -555, 666},
	};
	struct node_a_imu_sample actual;

	node_a_sample_queue_init(&queue);
	zassert_true(node_a_sample_queue_put(&queue, &first));
	zassert_true(node_a_sample_queue_put(&queue, &second));
	zassert_true(node_a_sample_queue_get(&queue, &actual, K_NO_WAIT));
	/* Source: the literal structures above represent two distinct acquired
	 * samples; the acquisition queue must preserve every field byte-for-byte.
	 */
	zassert_mem_equal(&actual, &first, sizeof(actual));
	zassert_true(node_a_sample_queue_get(&queue, &actual, K_NO_WAIT));
	zassert_mem_equal(&actual, &second, sizeof(actual));
}

ZTEST(node_a_acquisition, test_sample_queue_reuses_slots_without_reordering)
{
	struct node_a_sample_queue queue;
	struct node_a_imu_sample sample = {0};
	struct node_a_imu_sample actual;

	node_a_sample_queue_init(&queue);
	for (uint32_t sequence = 0U;
	     sequence < NODE_A_SAMPLE_QUEUE_CAPACITY; ++sequence) {
		sample.sample_sequence = sequence;
		zassert_true(node_a_sample_queue_put(&queue, &sample));
	}
	for (uint32_t sequence = 0U; sequence < 2U; ++sequence) {
		zassert_true(node_a_sample_queue_get(&queue, &actual,
						 K_NO_WAIT));
		zassert_equal(actual.sample_sequence, sequence);
	}
	for (uint32_t sequence = NODE_A_SAMPLE_QUEUE_CAPACITY;
	     sequence < NODE_A_SAMPLE_QUEUE_CAPACITY + 2U; ++sequence) {
		sample.sample_sequence = sequence;
		zassert_true(node_a_sample_queue_put(&queue, &sample));
	}
	for (uint32_t sequence = 2U;
	     sequence < NODE_A_SAMPLE_QUEUE_CAPACITY + 2U; ++sequence) {
		zassert_true(node_a_sample_queue_get(&queue, &actual,
						 K_NO_WAIT));
		/* Source: literal enqueue order is 0..17 with 0 and 1 removed
		 * before 16 and 17 are appended; FIFO output must therefore be 2..17.
		 */
		zassert_equal(actual.sample_sequence, sequence);
	}
}

ZTEST(node_a_acquisition, test_sample_queue_reports_empty_and_full_boundaries)
{
	struct node_a_sample_queue queue;
	struct node_a_imu_sample sample = {0};
	struct node_a_sample_queue_stats stats;

	node_a_sample_queue_init(&queue);
	zassert_false(node_a_sample_queue_get(&queue, &sample, K_NO_WAIT));
	for (uint32_t index = 0U; index < NODE_A_SAMPLE_QUEUE_CAPACITY;
	     ++index) {
		zassert_true(node_a_sample_queue_put(&queue, &sample));
	}
	zassert_false(node_a_sample_queue_put(&queue, &sample));
	node_a_sample_queue_stats_get(&queue, &stats);

	/* Source: the frozen status contract separately exposes firmware queue
	 * overruns, samples dropped before packetization and acquisition high-water.
	 * One rejected single-sample enqueue contributes one to each loss counter.
	 */
	zassert_equal(stats.firmware_queue_overruns, 1U);
	zassert_equal(stats.samples_dropped_before_packetization, 1U);
	zassert_equal(stats.high_water_samples,
		      NODE_A_SAMPLE_QUEUE_CAPACITY);
	zassert_false(stats.counters_saturated);
}

ZTEST(node_a_acquisition, test_sample_queue_loss_counters_saturate)
{
	struct node_a_sample_queue queue;
	struct node_a_imu_sample sample = {0};
	struct node_a_sample_queue_stats stats;

	node_a_sample_queue_init(&queue);
	for (uint32_t index = 0U; index < NODE_A_SAMPLE_QUEUE_CAPACITY;
	     ++index) {
		zassert_true(node_a_sample_queue_put(&queue, &sample));
	}
	queue.stats.firmware_queue_overruns = UINT32_MAX - 1U;
	queue.stats.samples_dropped_before_packetization = UINT32_MAX - 1U;
	zassert_false(node_a_sample_queue_put(&queue, &sample));
	zassert_false(node_a_sample_queue_put(&queue, &sample));
	node_a_sample_queue_stats_get(&queue, &stats);

	/* Source: the frozen status contract requires cumulative status counters
	 * to saturate rather than wrap and to expose that saturation occurred.
	 */
	zassert_equal(stats.firmware_queue_overruns, UINT32_MAX);
	zassert_equal(stats.samples_dropped_before_packetization, UINT32_MAX);
	zassert_true(stats.counters_saturated);
}

ZTEST(node_a_acquisition, test_full_sample_queue_preserves_accepted_samples)
{
	struct node_a_sample_queue queue;
	struct node_a_imu_sample sample = {0};
	struct node_a_imu_sample actual;

	node_a_sample_queue_init(&queue);
	for (uint32_t sequence = 0U;
	     sequence < NODE_A_SAMPLE_QUEUE_CAPACITY; ++sequence) {
		sample.sample_sequence = sequence;
		zassert_true(node_a_sample_queue_put(&queue, &sample));
	}
	sample.sample_sequence = NODE_A_SAMPLE_QUEUE_CAPACITY;
	zassert_false(node_a_sample_queue_put(&queue, &sample));

	/* Source: the declared drop-newest policy preserves every sample already
	 * accepted by the queue. The oldest accepted sequence must remain zero.
	 */
	zassert_true(node_a_sample_queue_get(&queue, &actual, K_NO_WAIT));
	zassert_equal(actual.sample_sequence, 0U);
}

ZTEST(node_a_acquisition, test_queue_overrun_becomes_one_packet_flag)
{
	struct node_a_sample_queue queue;
	struct node_a_imu_sample sample = {0};

	node_a_sample_queue_init(&queue);
	for (uint32_t index = 0U; index < NODE_A_SAMPLE_QUEUE_CAPACITY;
	     ++index) {
		zassert_true(node_a_sample_queue_put(&queue, &sample));
	}
	zassert_false(node_a_sample_queue_put(&queue, &sample));

	zassert_equal(node_a_sample_queue_take_packet_flags(&queue),
		      NODE_A_PACKET_FLAG_FIRMWARE_QUEUE_OVERRUN);
	zassert_equal(node_a_sample_queue_take_packet_flags(&queue), 0U);
}

ZTEST(node_a_acquisition, test_packet_crc32c_matches_standard_check_value)
{
	/* CRC-32C/Castagnoli check value for ASCII "123456789". */
	zassert_equal(node_a_packet_crc32c((const uint8_t *)"123456789", 9U),
		      0xe3069283U);
}

ZTEST(node_a_acquisition, test_packet_encoder_matches_python_golden_vector)
{
	static const uint8_t expected[] = {
		0x4b, 0x49, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00,
		0x07, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00,
		0x64, 0x00, 0x00, 0x00, 0x4e, 0x61, 0xbc, 0x00,
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
		0x64, 0x00, 0x38, 0xff, 0x80, 0x3e, 0x0a, 0x00,
		0xec, 0xff, 0x1e, 0x00, 0xff, 0x63, 0x35, 0x86,
	};
	const struct node_a_imu_sample sample = {
		.clock_epoch = 2U,
		.sample_sequence = 100U,
		.timestamp_us = 12345678U,
		.accel_raw = {100, -200, 16000},
		.gyro_raw = {10, -20, 30},
	};
	const struct node_a_sample_packet packet = {
		.node_id = 1U,
		.packet_sequence = 7U,
		.clock_epoch = 2U,
		.flags = 0U,
		.samples = &sample,
		.sample_count = 1U,
	};
	uint8_t encoded[NODE_A_PACKET_MAX_SIZE];
	size_t encoded_size = 0U;

	zassert_ok(node_a_packet_encode(&packet, encoded, sizeof(encoded),
				       &encoded_size));
	zassert_equal(encoded_size, sizeof(expected));
	zassert_mem_equal(encoded, expected, sizeof(expected));
}

ZTEST(node_a_acquisition, test_packet_encoder_emits_four_sample_batch)
{
	const struct node_a_imu_sample samples[4] = {
		{.clock_epoch = 4U, .sample_sequence = 10U, .timestamp_us = 1000U},
		{.clock_epoch = 4U, .sample_sequence = 11U, .timestamp_us = 1100U,
		 .flags = NODE_A_SAMPLE_FLAG_GYRO_CLIPPED},
		{.clock_epoch = 4U, .sample_sequence = 12U, .timestamp_us = 1200U},
		{.clock_epoch = 4U, .sample_sequence = 13U, .timestamp_us = 1300U},
	};
	const struct node_a_sample_packet packet = {
		.node_id = 1U,
		.packet_sequence = 8U,
		.clock_epoch = 4U,
		.flags = NODE_A_PACKET_FLAG_SENSOR_FIFO_OVERRUN |
			NODE_A_PACKET_FLAG_FIRMWARE_QUEUE_OVERRUN,
		.samples = samples,
		.sample_count = ARRAY_SIZE(samples),
	};
	uint8_t encoded[NODE_A_PACKET_MAX_SIZE];
	size_t encoded_size = 0U;
	uint32_t encoded_crc;

	zassert_ok(node_a_packet_encode(&packet, encoded, sizeof(encoded),
				       &encoded_size));
	zassert_equal(encoded_size, NODE_A_PACKET_MAX_SIZE);
	zassert_equal(encoded[5], ARRAY_SIZE(samples));
	/* The second sample flag is at header + record offset + flag offset. */
	zassert_equal(encoded[NODE_A_PACKET_HEADER_SIZE + NODE_A_PACKET_SAMPLE_SIZE +
			      12U], NODE_A_SAMPLE_FLAG_GYRO_CLIPPED);
	encoded_crc = (uint32_t)encoded[NODE_A_PACKET_MAX_SIZE - 4U] |
		((uint32_t)encoded[NODE_A_PACKET_MAX_SIZE - 3U] << 8) |
		((uint32_t)encoded[NODE_A_PACKET_MAX_SIZE - 2U] << 16) |
		((uint32_t)encoded[NODE_A_PACKET_MAX_SIZE - 1U] << 24);
	zassert_equal(encoded_crc,
		      node_a_packet_crc32c(encoded,
					   NODE_A_PACKET_MAX_SIZE -
					   NODE_A_PACKET_CRC_SIZE));
}

ZTEST(node_a_acquisition, test_packet_encoder_rejects_mixed_clock_epochs)
{
	const struct node_a_imu_sample samples[2] = {
		{.clock_epoch = 2U},
		{.clock_epoch = 3U},
	};
	const struct node_a_sample_packet packet = {
		.node_id = 1U,
		.clock_epoch = 2U,
		.samples = samples,
		.sample_count = 2U,
	};
	uint8_t encoded[NODE_A_PACKET_MAX_SIZE];
	size_t encoded_size = 0U;

	zassert_equal(node_a_packet_encode(&packet, encoded, sizeof(encoded),
				   &encoded_size), -EINVAL);
}

ZTEST(node_a_acquisition, test_packet_discontinuity_detects_gap_and_wrap)
{
	const struct node_a_imu_sample contiguous[] = {
		{.sample_sequence = 0xfffffffeU},
		{.sample_sequence = 0xffffffffU},
		{.sample_sequence = 0U},
	};
	const struct node_a_imu_sample gap[] = {
		{.sample_sequence = 10U},
		{.sample_sequence = 12U},
	};

	zassert_false(node_a_packet_samples_have_discontinuity(
			contiguous, ARRAY_SIZE(contiguous), true, 0xfffffffdU));
	zassert_true(node_a_packet_samples_have_discontinuity(
			gap, ARRAY_SIZE(gap), true, 9U));
}

ZTEST(node_a_acquisition, test_startup_sample_boundary_preserves_first_sequence)
{
	bool first_valid_sample_pending = true;
	struct node_a_stream_counters counters;
	uint32_t published_sequence[2];
	size_t published_count = 0U;

	node_a_counters_start(&counters, 0U);
	for (size_t valid_event = 0U; valid_event < 3U; ++valid_event) {
		if (node_a_imu_startup_sample_should_publish(
				&first_valid_sample_pending)) {
			published_sequence[published_count++] =
				node_a_counters_take_sample(&counters);
		}
	}

	zassert_equal(published_count, 2U);
	zassert_equal(published_sequence[0], 0U);
	zassert_equal(published_sequence[1], 1U);
	zassert_false(first_valid_sample_pending);
}

ZTEST_SUITE(node_a_acquisition, NULL, NULL, reset_fake, NULL, NULL);
