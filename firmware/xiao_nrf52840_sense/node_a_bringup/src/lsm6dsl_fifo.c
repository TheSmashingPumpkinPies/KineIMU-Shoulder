/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <string.h>

#include <zephyr/sys/util.h>

#include "lsm6dsl_fifo.h"
#include "packet.h"

#define LSM6DSL_FIFO_STATUS_BYTES 2U
#define LSM6DSL_FIFO_STATUS2_WATERMARK BIT(7)
#define LSM6DSL_FIFO_STATUS2_OVERRUN BIT(6)
#define LSM6DSL_FIFO_STATUS2_FULL BIT(5)
#define LSM6DSL_FIFO_STATUS2_EMPTY BIT(4)
#define LSM6DSL_FIFO_STATUS2_DIFF_HIGH_MASK 0x07U

static void saturating_increment(uint32_t *counter, bool *saturated)
{
	if (*counter < UINT32_MAX) {
		(*counter)++;
	}
	if (*counter == UINT32_MAX) {
		*saturated = true;
	}
}

int node_a_lsm6dsl_read_fifo_status(
	const struct i2c_dt_spec *spec,
	node_a_lsm6dsl_burst_read_fn burst_read,
	struct node_a_lsm6dsl_fifo_status *status)
{
	uint8_t registers[LSM6DSL_FIFO_STATUS_BYTES];
	struct node_a_lsm6dsl_fifo_status decoded;
	int rc;

	if ((spec == NULL) || (burst_read == NULL) || (status == NULL)) {
		return -EINVAL;
	}

	/* Zephyr's st,lsm6dsl sensor API does not expose FIFO status. Keep this
	 * direct register read in the LSM6DS3TR-C adapter so no backend convention
	 * leaks into the acquisition record or silently changes the raw boundary.
	 */
	rc = burst_read(spec, NODE_A_LSM6DSL_FIFO_STATUS_START, registers,
			LSM6DSL_FIFO_STATUS_BYTES);
	if (rc < 0) {
		return rc;
	}

	decoded.status1_raw = registers[0];
	decoded.status2_raw = registers[1];
	decoded.unread_words = (uint16_t)registers[0] |
		((uint16_t)(registers[1] & LSM6DSL_FIFO_STATUS2_DIFF_HIGH_MASK)
		 << 8);
	decoded.watermark = (registers[1] & LSM6DSL_FIFO_STATUS2_WATERMARK) != 0U;
	decoded.overrun = (registers[1] & LSM6DSL_FIFO_STATUS2_OVERRUN) != 0U;
	decoded.full = (registers[1] & LSM6DSL_FIFO_STATUS2_FULL) != 0U;
	decoded.empty = (registers[1] & LSM6DSL_FIFO_STATUS2_EMPTY) != 0U;

	/* Commit only after the complete two-register snapshot decoded. */
	*status = decoded;
	return 0;
}

void node_a_lsm6dsl_fifo_observer_init(
	struct node_a_lsm6dsl_fifo_observer *observer)
{
	if (observer != NULL) {
		memset(observer, 0, sizeof(*observer));
	}
}

void node_a_lsm6dsl_fifo_observe(
	struct node_a_lsm6dsl_fifo_observer *observer,
	const struct node_a_lsm6dsl_fifo_status *status)
{
	k_spinlock_key_t key;

	if ((observer == NULL) || (status == NULL)) {
		return;
	}
	key = k_spin_lock(&observer->lock);

	/* OVER_RUN is a status level, not a per-read event. Count only a new
	 * assertion; a later clear followed by an assertion is a new event.
	 */
	if (status->overrun && !observer->overrun_asserted) {
		saturating_increment(&observer->sensor_fifo_overruns,
				     &observer->counters_saturated);
		observer->pending_packet_flags |=
			NODE_A_PACKET_FLAG_SENSOR_FIFO_OVERRUN;
	}
	observer->overrun_asserted = status->overrun;
	k_spin_unlock(&observer->lock, key);
}

uint16_t node_a_lsm6dsl_fifo_take_packet_flags(
	struct node_a_lsm6dsl_fifo_observer *observer)
{
	k_spinlock_key_t key;
	uint16_t flags;

	if (observer == NULL) {
		return 0U;
	}

	key = k_spin_lock(&observer->lock);
	flags = observer->pending_packet_flags;
	observer->pending_packet_flags = 0U;
	k_spin_unlock(&observer->lock, key);
	return flags;
}

void node_a_lsm6dsl_fifo_stats_get(
	struct node_a_lsm6dsl_fifo_observer *observer,
	struct node_a_lsm6dsl_fifo_stats *stats)
{
	k_spinlock_key_t key;

	if ((observer == NULL) || (stats == NULL)) {
		return;
	}

	key = k_spin_lock(&observer->lock);
	stats->sensor_fifo_overruns = observer->sensor_fifo_overruns;
	stats->counters_saturated = observer->counters_saturated;
	k_spin_unlock(&observer->lock, key);
}
