/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_ACQUISITION_TRACE_H_
#define KINEIMU_NODE_A_ACQUISITION_TRACE_H_

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/spinlock.h>

struct node_a_acquisition_trace {
	struct k_spinlock lock;
	uint32_t callback_entries;
	uint32_t pre_acquisition_callbacks;
	uint32_t timestamp_available;
	uint32_t timestamp_missing;
	uint32_t raw_read_attempts;
	uint32_t raw_read_successes;
	uint32_t raw_read_failures;
	uint32_t notify_calls;
	uint32_t notify_max_duration;
	int32_t last_raw_read_rc;
	bool counters_saturated;
};

struct node_a_acquisition_trace_snapshot {
	uint32_t callback_entries;
	uint32_t pre_acquisition_callbacks;
	uint32_t timestamp_available;
	uint32_t timestamp_missing;
	uint32_t raw_read_attempts;
	uint32_t raw_read_successes;
	uint32_t raw_read_failures;
	uint32_t notify_calls;
	uint32_t notify_max_duration;
	int32_t last_raw_read_rc;
	bool counters_saturated;
};

void node_a_acquisition_trace_init(struct node_a_acquisition_trace *trace);

void node_a_acquisition_trace_note_callback_entry(
	struct node_a_acquisition_trace *trace);

void node_a_acquisition_trace_note_pre_acquisition(
	struct node_a_acquisition_trace *trace);

void node_a_acquisition_trace_note_timestamp_result(
	struct node_a_acquisition_trace *trace, bool available);

void node_a_acquisition_trace_note_raw_read_result(
	struct node_a_acquisition_trace *trace, int rc);

void node_a_acquisition_trace_note_notify_duration(
	struct node_a_acquisition_trace *trace, uint32_t duration_us);

void node_a_acquisition_trace_snapshot_get(
	struct node_a_acquisition_trace *trace,
	struct node_a_acquisition_trace_snapshot *snapshot);

#endif /* KINEIMU_NODE_A_ACQUISITION_TRACE_H_ */
