/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_LSM6DSL_FIFO_H_
#define KINEIMU_NODE_A_LSM6DSL_FIFO_H_

#include <stdbool.h>
#include <stdint.h>

#include "lsm6dsl_raw.h"

#include <zephyr/spinlock.h>

#define NODE_A_LSM6DSL_FIFO_STATUS_START 0x3aU

struct node_a_lsm6dsl_fifo_status {
	uint8_t status1_raw;
	uint8_t status2_raw;
	uint16_t unread_words;
	bool watermark;
	bool overrun;
	bool full;
	bool empty;
};

struct node_a_lsm6dsl_fifo_observer {
	struct k_spinlock lock;
	uint32_t sensor_fifo_overruns;
	bool overrun_asserted;
	bool counters_saturated;
	uint16_t pending_packet_flags;
};

struct node_a_lsm6dsl_fifo_stats {
	uint32_t sensor_fifo_overruns;
	bool counters_saturated;
};

int node_a_lsm6dsl_read_fifo_status(
	const struct i2c_dt_spec *spec,
	node_a_lsm6dsl_burst_read_fn burst_read,
	struct node_a_lsm6dsl_fifo_status *status);

void node_a_lsm6dsl_fifo_observer_init(
	struct node_a_lsm6dsl_fifo_observer *observer);

void node_a_lsm6dsl_fifo_observe(
	struct node_a_lsm6dsl_fifo_observer *observer,
	const struct node_a_lsm6dsl_fifo_status *status);

uint16_t node_a_lsm6dsl_fifo_take_packet_flags(
	struct node_a_lsm6dsl_fifo_observer *observer);

void node_a_lsm6dsl_fifo_stats_get(
	struct node_a_lsm6dsl_fifo_observer *observer,
	struct node_a_lsm6dsl_fifo_stats *stats);

#endif /* KINEIMU_NODE_A_LSM6DSL_FIFO_H_ */
