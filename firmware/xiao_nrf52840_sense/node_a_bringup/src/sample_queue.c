/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include "packet.h"
#include "sample_queue.h"

static void node_a_saturating_increment(
	uint32_t *counter, struct node_a_sample_queue_stats *stats)
{
	if (*counter < UINT32_MAX) {
		(*counter)++;
	}
	if (*counter == UINT32_MAX) {
		stats->counters_saturated = true;
	}
}

void node_a_sample_queue_init(struct node_a_sample_queue *queue)
{
	k_msgq_init(&queue->messages, (char *)queue->storage,
		    sizeof(queue->storage[0]), NODE_A_SAMPLE_QUEUE_CAPACITY);
	k_mutex_init(&queue->lock);
	k_sem_init(&queue->available, 0U, NODE_A_SAMPLE_QUEUE_CAPACITY);
	memset(&queue->stats, 0, sizeof(queue->stats));
	queue->pending_packet_flags = 0U;
}

bool node_a_sample_queue_put(struct node_a_sample_queue *queue,
			     const struct node_a_imu_sample *sample)
{
	uint32_t used;
	bool stored;

	k_mutex_lock(&queue->lock, K_FOREVER);
	stored = k_msgq_put(&queue->messages, sample, K_NO_WAIT) == 0;
	if (stored) {
		used = k_msgq_num_used_get(&queue->messages);
		if (used > queue->stats.high_water_samples) {
			queue->stats.high_water_samples = used;
		}
	} else {
		queue->pending_packet_flags |=
			NODE_A_PACKET_FLAG_FIRMWARE_QUEUE_OVERRUN;
		node_a_saturating_increment(
			&queue->stats.firmware_queue_overruns, &queue->stats);
		node_a_saturating_increment(
			&queue->stats.samples_dropped_before_packetization,
			&queue->stats);
	}
	k_mutex_unlock(&queue->lock);

	if (stored) {
		k_sem_give(&queue->available);
	}
	return stored;
}

uint16_t node_a_sample_queue_take_packet_flags(
	struct node_a_sample_queue *queue)
{
	uint16_t flags;

	if (queue == NULL) {
		return 0U;
	}

	k_mutex_lock(&queue->lock, K_FOREVER);
	flags = queue->pending_packet_flags;
	queue->pending_packet_flags = 0U;
	k_mutex_unlock(&queue->lock);
	return flags;
}

bool node_a_sample_queue_get(struct node_a_sample_queue *queue,
			     struct node_a_imu_sample *sample,
			     k_timeout_t timeout)
{
	bool received;

	if (k_sem_take(&queue->available, timeout) != 0) {
		return false;
	}

	k_mutex_lock(&queue->lock, K_FOREVER);
	received = k_msgq_get(&queue->messages, sample, K_NO_WAIT) == 0;
	k_mutex_unlock(&queue->lock);

	return received;
}

void node_a_sample_queue_stats_get(
	struct node_a_sample_queue *queue,
	struct node_a_sample_queue_stats *stats)
{
	k_mutex_lock(&queue->lock, K_FOREVER);
	*stats = queue->stats;
	k_mutex_unlock(&queue->lock);
}
