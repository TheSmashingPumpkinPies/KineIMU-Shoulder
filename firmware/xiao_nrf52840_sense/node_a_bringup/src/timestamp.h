/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_TIMESTAMP_H_
#define KINEIMU_NODE_A_TIMESTAMP_H_

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/spinlock.h>

struct node_a_drdy_timestamp {
	struct gpio_callback callback;
	struct k_spinlock lock;
	int64_t latest_ticks;
	bool pending;
};

int node_a_drdy_timestamp_attach(struct node_a_drdy_timestamp *timestamp,
				 const struct gpio_dt_spec *drdy_gpio);

/* Drop any timestamp captured before the active stream boundary. */
void node_a_drdy_timestamp_reset(struct node_a_drdy_timestamp *timestamp);

bool node_a_drdy_timestamp_take(struct node_a_drdy_timestamp *timestamp,
				uint64_t *timestamp_us);

#endif /* KINEIMU_NODE_A_TIMESTAMP_H_ */
