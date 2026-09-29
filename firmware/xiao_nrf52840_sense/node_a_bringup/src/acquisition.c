/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <string.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>

#include "acquisition.h"
#include "lsm6dsl_raw.h"
#include "node_config.h"
#define NODE_A_ODR_HZ 104

#define NODE_A_WHO_AM_I 0x6a
#define NODE_A_INT1_DRDY_MASK 0x03
#define NODE_A_CTRL1_XL_CONFIG_MASK 0xfc
#define NODE_A_CTRL1_XL_CONFIG 0x48
#define NODE_A_CTRL2_G_CONFIG_MASK 0xfe
#define NODE_A_CTRL2_G_CONFIG 0x44

struct node_a_register_snapshot_segment {
	uint8_t start_addr;
	uint8_t length;
};

static const struct node_a_register_snapshot_segment
	node_a_register_snapshot_segments[] = {
	{.start_addr = 0x06U, .length = 5U},
	{.start_addr = 0x0dU, .length = 2U},
	{.start_addr = 0x10U, .length = 10U},
	{.start_addr = 0x5eU, .length = 2U},
};

/* The Zephyr LSM6DSL driver retains this pointer after sensor_trigger_set(). */
static const struct sensor_trigger node_a_data_ready_trigger = {
	.type = SENSOR_TRIG_DATA_READY,
	.chan = SENSOR_CHAN_ACCEL_XYZ,
};

bool node_a_imu_startup_sample_should_publish(bool *first_valid_sample_pending)
{
	if (*first_valid_sample_pending) {
		*first_valid_sample_pending = false;
		return false;
	}
	return true;
}

int node_a_imu_arm_data_ready(const struct device *imu,
				 sensor_trigger_handler_t data_ready_handler)
{
	if ((imu == NULL) || (data_ready_handler == NULL)) {
		return -EINVAL;
	}

	return sensor_trigger_set(imu, &node_a_data_ready_trigger,
					 data_ready_handler);
}

int node_a_imu_disarm_data_ready(const struct device *imu)
{
	if (imu == NULL) {
		return -EINVAL;
	}

	return sensor_trigger_set(imu, &node_a_data_ready_trigger, NULL);
}

int node_a_imu_wait_data_ready_inactive(
	const struct gpio_dt_spec *drdy_gpio, uint32_t timeout_ms)
{
	const int64_t deadline_ms = k_uptime_get() + (int64_t)timeout_ms;

	if ((drdy_gpio == NULL) || (drdy_gpio->port == NULL)) {
		return -EINVAL;
	}
	if (!gpio_is_ready_dt(drdy_gpio)) {
		return -ENODEV;
	}

	while (true) {
		const int active = gpio_pin_get_dt(drdy_gpio);

		if (active < 0) {
			return active;
		}
		if (active == 0) {
			return 0;
		}
		if (k_uptime_get() >= deadline_ms) {
			return -ETIMEDOUT;
		}

		k_sleep(K_MSEC(1));
	}
}

int node_a_imu_drain_data_ready(
	const struct i2c_dt_spec *spec,
	node_a_imu_register_burst_read_fn burst_read)
{
	struct node_a_imu_sample discarded_sample = {0};

	if ((spec == NULL) || (burst_read == NULL)) {
		return -EINVAL;
	}

	/* Reading the output frame clears a pending level without publishing a
	 * pre-stream sample. The next trigger can then be a real DRDY edge with an
	 * ISR timestamp.
	 */
	return node_a_lsm6dsl_read_raw(spec, burst_read, &discarded_sample);
}

static void node_a_imu_rearm_set_state(
	struct node_a_imu_rearm_result *result,
	enum node_a_imu_rearm_state state)
{
	if (result != NULL) {
		result->state = state;
	}
}

int node_a_imu_quiesce_and_arm_data_ready(
	const struct device *imu,
	const struct gpio_dt_spec *drdy_gpio,
	const struct i2c_dt_spec *spec,
	node_a_imu_register_burst_read_fn burst_read,
	sensor_trigger_handler_t data_ready_handler,
	void (*reset_pending_timestamp)(void *context),
	void *reset_context,
	uint32_t quiet_timeout_ms,
	uint8_t max_attempts,
	struct node_a_imu_rearm_result *result)
{
	int rc = -ETIMEDOUT;

	if (result != NULL) {
		result->state = NODE_A_IMU_REARM_IDLE;
		result->attempts = 0U;
		result->race_retries = 0U;
	}

	if ((imu == NULL) || (drdy_gpio == NULL) || (spec == NULL) ||
	    (burst_read == NULL) || (data_ready_handler == NULL) ||
	    (reset_pending_timestamp == NULL) || (max_attempts == 0U)) {
		node_a_imu_rearm_set_state(result, NODE_A_IMU_REARM_FATAL);
		return -EINVAL;
	}

	for (uint8_t attempt = 0U; attempt < max_attempts; ++attempt) {
		if (result != NULL) {
			result->attempts = (uint8_t)(attempt + 1U);
		}

		node_a_imu_rearm_set_state(result, NODE_A_IMU_REARM_DISARMING);
		rc = node_a_imu_disarm_data_ready(imu);
		if (rc < 0) {
			goto fatal;
		}

		node_a_imu_rearm_set_state(result, NODE_A_IMU_REARM_DRAINING);
		rc = node_a_imu_drain_data_ready(spec, burst_read);
		if (rc < 0) {
			goto fatal;
		}

		node_a_imu_rearm_set_state(
			result, NODE_A_IMU_REARM_WAITING_INACTIVE);
		rc = node_a_imu_wait_data_ready_inactive(
			drdy_gpio, quiet_timeout_ms);
		if (rc < 0) {
			/* A line that remained active is retryable. Other failures are
			 * configuration or GPIO errors and are immediately fatal. */
			if (rc == -ETIMEDOUT) {
				continue;
			}
			goto fatal;
		}

		/* Only clear timestamp state after the line is observed inactive. Any
		 * event before this point belongs to the quiescing boundary. */
		reset_pending_timestamp(reset_context);

		node_a_imu_rearm_set_state(result, NODE_A_IMU_REARM_ARMING);
		rc = node_a_imu_arm_data_ready(imu, data_ready_handler);
		if (rc < 0) {
			goto fatal;
		}

		/* The in-tree LSM6DSL driver checks the level while enabling its GPIO
		 * interrupt. A high result means that the check-to-arm interval won
		 * the race and the arm must be retried from a disarmed state. */
		node_a_imu_rearm_set_state(result, NODE_A_IMU_REARM_VERIFYING);
		rc = node_a_imu_wait_data_ready_inactive(drdy_gpio, 0U);
		if (rc == 0) {
			node_a_imu_rearm_set_state(result, NODE_A_IMU_REARM_ARMED);
			return 0;
		}
		if (rc != -ETIMEDOUT) {
			goto fatal;
		}
		if (result != NULL) {
			result->race_retries++;
		}
	}

	rc = -ETIMEDOUT;

fatal:
	node_a_imu_rearm_set_state(result, NODE_A_IMU_REARM_FATAL);
	return rc;
}

int node_a_imu_configure(const struct device *imu,
			 sensor_trigger_handler_t data_ready_handler)
{
	struct sensor_value accel_range;
	struct sensor_value gyro_range;
	const struct sensor_value odr = {
		.val1 = NODE_A_ODR_HZ,
		.val2 = 0,
	};
	int rc;

	if ((imu == NULL) || (data_ready_handler == NULL)) {
		return -EINVAL;
	}

	/* sensor_attr_set() requires SI values at the Zephyr boundary. */
	sensor_g_to_ms2(NODE_A_ACCEL_RANGE_G, &accel_range);
	sensor_degrees_to_rad(NODE_A_GYRO_RANGE_DPS, &gyro_range);

	rc = sensor_attr_set(imu, SENSOR_CHAN_ACCEL_XYZ,
			     SENSOR_ATTR_FULL_SCALE, &accel_range);
	if (rc < 0) {
		return rc;
	}

	rc = sensor_attr_set(imu, SENSOR_CHAN_GYRO_XYZ,
			     SENSOR_ATTR_FULL_SCALE, &gyro_range);
	if (rc < 0) {
		return rc;
	}

	rc = sensor_attr_set(imu, SENSOR_CHAN_ACCEL_XYZ,
			     SENSOR_ATTR_SAMPLING_FREQUENCY, &odr);
	if (rc < 0) {
		return rc;
	}

	rc = sensor_attr_set(imu, SENSOR_CHAN_GYRO_XYZ,
			     SENSOR_ATTR_SAMPLING_FREQUENCY, &odr);
	if (rc < 0) {
		return rc;
	}

	return node_a_imu_arm_data_ready(imu, data_ready_handler);
}

int node_a_imu_read_register_snapshot(
	const struct i2c_dt_spec *spec,
	node_a_imu_register_burst_read_fn burst_read,
	uint8_t snapshot[19])
{
	uint8_t staged[19];
	size_t offset = 0U;

	if ((spec == NULL) || (burst_read == NULL) || (snapshot == NULL)) {
		return -EINVAL;
	}

	for (size_t index = 0U;
	     index < ARRAY_SIZE(node_a_register_snapshot_segments); ++index) {
		const struct node_a_register_snapshot_segment *segment =
			&node_a_register_snapshot_segments[index];
		int rc = burst_read(spec, segment->start_addr, &staged[offset],
					segment->length);

		if (rc < 0) {
			return rc;
		}
		offset += segment->length;
	}

	memcpy(snapshot, staged, sizeof(staged));
	return 0;
}

bool node_a_imu_registers_match_config(
	const struct node_a_imu_registers *registers)
{
	if (registers == NULL) {
		return false;
	}

	return (registers->who_am_i == NODE_A_WHO_AM_I) &&
	       ((registers->int1_ctrl & NODE_A_INT1_DRDY_MASK) ==
		NODE_A_INT1_DRDY_MASK) &&
	       ((registers->ctrl1_xl & NODE_A_CTRL1_XL_CONFIG_MASK) ==
		NODE_A_CTRL1_XL_CONFIG) &&
	       ((registers->ctrl2_g & NODE_A_CTRL2_G_CONFIG_MASK) ==
		NODE_A_CTRL2_G_CONFIG);
}
