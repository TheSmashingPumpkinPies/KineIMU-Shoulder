/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_COUNTERS_H_
#define KINEIMU_NODE_A_COUNTERS_H_

#include <stdint.h>

/* One writer owns each next-sequence field. Clock resets occur only while
 * acquisition and packet generation are stopped.
 */
struct node_a_stream_counters {
	uint32_t clock_epoch;
	uint32_t sample_counter;
	uint32_t packet_counter;
};

void node_a_counters_start(struct node_a_stream_counters *counters,
			   uint32_t clock_epoch);

uint32_t node_a_counters_take_sample(struct node_a_stream_counters *counters);

uint32_t node_a_counters_take_packet(struct node_a_stream_counters *counters);

void node_a_counters_reset_clock(struct node_a_stream_counters *counters);

#endif /* KINEIMU_NODE_A_COUNTERS_H_ */
