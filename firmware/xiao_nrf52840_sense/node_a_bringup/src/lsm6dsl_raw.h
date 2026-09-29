/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_LSM6DSL_RAW_H_
#define KINEIMU_NODE_A_LSM6DSL_RAW_H_

#include <stdint.h>

#include <zephyr/drivers/i2c.h>

#include "acquisition.h"

typedef int (*node_a_lsm6dsl_burst_read_fn)(
	const struct i2c_dt_spec *spec, uint8_t start_addr, uint8_t *buf,
	uint32_t num_bytes);

int node_a_lsm6dsl_read_raw(
	const struct i2c_dt_spec *spec,
	node_a_lsm6dsl_burst_read_fn burst_read,
	struct node_a_imu_sample *sample);

#endif /* KINEIMU_NODE_A_LSM6DSL_RAW_H_ */
