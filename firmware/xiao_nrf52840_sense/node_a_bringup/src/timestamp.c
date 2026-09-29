/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>

#include "timestamp.h"

static void node_a_drdy_gpio_callback(const struct device *port,
				      struct gpio_callback *callback,
				      gpio_port_pins_t pins)
{
	const int64_t ticks = k_uptime_ticks();
	struct node_a_drdy_timestamp *timestamp = CONTAINER_OF(
		callback, struct node_a_drdy_timestamp, callback);
	k_spinlock_key_t key;

	ARG_UNUSED(port);
	ARG_UNUSED(pins);

	key = k_spin_lock(&timestamp->lock);
	timestamp->latest_ticks = ticks;
	timestamp->pending = true;
	k_spin_unlock(&timestamp->lock, key);
}

int node_a_drdy_timestamp_attach(struct node_a_drdy_timestamp *timestamp,
				 const struct gpio_dt_spec *drdy_gpio)
{
	if ((timestamp == NULL) || (drdy_gpio == NULL)) {
		return -EINVAL;
	}
	if ((drdy_gpio->port == NULL) || !gpio_is_ready_dt(drdy_gpio)) {
		return -ENODEV;
	}

	node_a_drdy_timestamp_reset(timestamp);
	gpio_init_callback(&timestamp->callback, node_a_drdy_gpio_callback,
			   BIT(drdy_gpio->pin));

	/* The LSM6DSL driver owns pin configuration and interrupt enable/disable.
	 * This callback only shares its GPIO callback list to capture the same edge.
	 */
	return gpio_add_callback(drdy_gpio->port, &timestamp->callback);
}

void node_a_drdy_timestamp_reset(struct node_a_drdy_timestamp *timestamp)
{
	k_spinlock_key_t key;

	if (timestamp == NULL) {
		return;
	}

	key = k_spin_lock(&timestamp->lock);
	timestamp->latest_ticks = 0;
	timestamp->pending = false;
	k_spin_unlock(&timestamp->lock, key);
}

bool node_a_drdy_timestamp_take(struct node_a_drdy_timestamp *timestamp,
				uint64_t *timestamp_us)
{
	k_spinlock_key_t key;
	int64_t ticks;

	if ((timestamp == NULL) || (timestamp_us == NULL)) {
		return false;
	}

	key = k_spin_lock(&timestamp->lock);
	if (!timestamp->pending) {
		k_spin_unlock(&timestamp->lock, key);
		return false;
	}
	ticks = timestamp->latest_ticks;
	timestamp->pending = false;
	k_spin_unlock(&timestamp->lock, key);

	*timestamp_us = k_ticks_to_us_floor64((uint64_t)ticks);
	return true;
}
