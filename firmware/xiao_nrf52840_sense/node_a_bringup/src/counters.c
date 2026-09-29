/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include "counters.h"

void node_a_counters_start(struct node_a_stream_counters *counters,
			   uint32_t clock_epoch)
{
	counters->clock_epoch = clock_epoch;
	counters->sample_counter = 0U;
	counters->packet_counter = 0U;
}

uint32_t node_a_counters_take_sample(struct node_a_stream_counters *counters)
{
	return counters->sample_counter++;
}

uint32_t node_a_counters_take_packet(struct node_a_stream_counters *counters)
{
	return counters->packet_counter++;
}

void node_a_counters_reset_clock(struct node_a_stream_counters *counters)
{
	node_a_counters_start(counters, counters->clock_epoch + 1U);
}
