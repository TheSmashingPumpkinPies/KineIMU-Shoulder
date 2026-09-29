/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_SAMPLE_QUEUE_H_
#define KINEIMU_NODE_A_SAMPLE_QUEUE_H_

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/kernel.h>

#include "acquisition.h"

#define NODE_A_SAMPLE_QUEUE_CAPACITY 16U

struct node_a_sample_queue_stats {
	uint32_t firmware_queue_overruns;
	uint32_t samples_dropped_before_packetization;
	uint32_t high_water_samples;
	bool counters_saturated;
};

struct node_a_sample_queue {
	struct k_msgq messages;
	struct k_mutex lock;
	struct k_sem available;
	struct node_a_sample_queue_stats stats;
	uint16_t pending_packet_flags;
	struct node_a_imu_sample storage[NODE_A_SAMPLE_QUEUE_CAPACITY];
};

void node_a_sample_queue_init(struct node_a_sample_queue *queue);

bool node_a_sample_queue_put(struct node_a_sample_queue *queue,
			     const struct node_a_imu_sample *sample);

bool node_a_sample_queue_get(struct node_a_sample_queue *queue,
			     struct node_a_imu_sample *sample,
			     k_timeout_t timeout);

void node_a_sample_queue_stats_get(
	struct node_a_sample_queue *queue,
	struct node_a_sample_queue_stats *stats);

uint16_t node_a_sample_queue_take_packet_flags(
	struct node_a_sample_queue *queue);

#endif /* KINEIMU_NODE_A_SAMPLE_QUEUE_H_ */
