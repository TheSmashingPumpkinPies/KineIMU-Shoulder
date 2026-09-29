/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_ACQUISITION_H_
#define KINEIMU_NODE_A_ACQUISITION_H_

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>

typedef int (*node_a_imu_register_burst_read_fn)(
	const struct i2c_dt_spec *spec, uint8_t start_addr, uint8_t *buf,
	uint32_t num_bytes);

struct node_a_imu_registers {
	uint8_t who_am_i;
	uint8_t int1_ctrl;
	uint8_t ctrl1_xl;
	uint8_t ctrl2_g;
};

struct node_a_imu_sample {
	uint32_t clock_epoch;
	uint32_t sample_sequence;
	uint64_t timestamp_us;
	uint16_t flags;
	int16_t accel_raw[3];
	int16_t gyro_raw[3];
};

enum node_a_imu_rearm_state {
	NODE_A_IMU_REARM_IDLE,
	NODE_A_IMU_REARM_DISARMING,
	NODE_A_IMU_REARM_DRAINING,
	NODE_A_IMU_REARM_WAITING_INACTIVE,
	NODE_A_IMU_REARM_ARMING,
	NODE_A_IMU_REARM_VERIFYING,
	NODE_A_IMU_REARM_ARMED,
	NODE_A_IMU_REARM_FATAL,
};

struct node_a_imu_rearm_result {
	enum node_a_imu_rearm_state state;
	uint8_t attempts;
	uint8_t race_retries;
};

int node_a_imu_configure(const struct device *imu,
			 sensor_trigger_handler_t data_ready_handler);

int node_a_imu_arm_data_ready(const struct device *imu,
				 sensor_trigger_handler_t data_ready_handler);

/* Disable the driver's deferred data-ready callback before clearing a
 * pending level at the stream boundary. */
int node_a_imu_disarm_data_ready(const struct device *imu);

/* The in-tree LSM6DSL driver may synchronously notice an already-active INT1
 * level while arming. Do not arm until the level has returned inactive. */
int node_a_imu_wait_data_ready_inactive(
	const struct gpio_dt_spec *drdy_gpio, uint32_t timeout_ms);

/* Read and discard one output frame to release a pending DRDY level. */
int node_a_imu_drain_data_ready(
	const struct i2c_dt_spec *spec,
	node_a_imu_register_burst_read_fn burst_read);

/* Quiesce, drain, arm, and verify the DRDY line as one bounded operation.
 * The caller supplies the timestamp reset so the acquisition boundary can
 * discard stale GPIO events without coupling this module to stream state. */
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
	struct node_a_imu_rearm_result *result);

int node_a_imu_read_register_snapshot(
	const struct i2c_dt_spec *spec,
	node_a_imu_register_burst_read_fn burst_read,
	uint8_t snapshot[19]);

bool node_a_imu_registers_match_config(
	const struct node_a_imu_registers *registers);

/* The first valid DRDY frame can follow a partial ODR interval after arming.
 * Drain it before issuing sample sequence zero for the USB bench stream. */
bool node_a_imu_startup_sample_should_publish(bool *first_valid_sample_pending);

#endif /* KINEIMU_NODE_A_ACQUISITION_H_ */
