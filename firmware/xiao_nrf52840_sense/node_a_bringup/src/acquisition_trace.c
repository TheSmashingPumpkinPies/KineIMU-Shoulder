/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>

#include "acquisition_trace.h"

static void saturating_increment(uint32_t *counter, bool *saturated)
{
	if (*counter < UINT32_MAX) {
		(*counter)++;
	}
	if (*counter == UINT32_MAX) {
		*saturated = true;
	}
}

void node_a_acquisition_trace_init(struct node_a_acquisition_trace *trace)
{
	if (trace != NULL) {
		memset(trace, 0, sizeof(*trace));
	}
}

void node_a_acquisition_trace_note_callback_entry(
	struct node_a_acquisition_trace *trace)
{
	k_spinlock_key_t key;

	if (trace == NULL) {
		return;
	}
	key = k_spin_lock(&trace->lock);
	saturating_increment(&trace->callback_entries, &trace->counters_saturated);
	k_spin_unlock(&trace->lock, key);
}

void node_a_acquisition_trace_note_pre_acquisition(
	struct node_a_acquisition_trace *trace)
{
	k_spinlock_key_t key;

	if (trace == NULL) {
		return;
	}
	key = k_spin_lock(&trace->lock);
	saturating_increment(&trace->pre_acquisition_callbacks,
				     &trace->counters_saturated);
	k_spin_unlock(&trace->lock, key);
}

void node_a_acquisition_trace_note_timestamp_result(
	struct node_a_acquisition_trace *trace, bool available)
{
	k_spinlock_key_t key;

	if (trace == NULL) {
		return;
	}
	key = k_spin_lock(&trace->lock);
	if (available) {
		saturating_increment(&trace->timestamp_available,
				     &trace->counters_saturated);
	} else {
		saturating_increment(&trace->timestamp_missing,
				     &trace->counters_saturated);
	}
	k_spin_unlock(&trace->lock, key);
}

void node_a_acquisition_trace_note_raw_read_result(
	struct node_a_acquisition_trace *trace, int rc)
{
	k_spinlock_key_t key;

	if (trace == NULL) {
		return;
	}
	key = k_spin_lock(&trace->lock);
	saturating_increment(&trace->raw_read_attempts,
				     &trace->counters_saturated);
	if (rc < 0) {
		saturating_increment(&trace->raw_read_failures,
				     &trace->counters_saturated);
	} else {
		saturating_increment(&trace->raw_read_successes,
				     &trace->counters_saturated);
	}
	trace->last_raw_read_rc = (int32_t)rc;
	k_spin_unlock(&trace->lock, key);
}

void node_a_acquisition_trace_note_notify_duration(
	struct node_a_acquisition_trace *trace, uint32_t duration_us)
{
	k_spinlock_key_t key;

	if (trace == NULL) {
		return;
	}
	key = k_spin_lock(&trace->lock);
	saturating_increment(&trace->notify_calls,
				     &trace->counters_saturated);
	if (duration_us > trace->notify_max_duration) {
		trace->notify_max_duration = duration_us;
	}
	k_spin_unlock(&trace->lock, key);
}

void node_a_acquisition_trace_snapshot_get(
	struct node_a_acquisition_trace *trace,
	struct node_a_acquisition_trace_snapshot *snapshot)
{
	k_spinlock_key_t key;

	if ((trace == NULL) || (snapshot == NULL)) {
		return;
	}
	key = k_spin_lock(&trace->lock);
	*snapshot = (struct node_a_acquisition_trace_snapshot){
		.callback_entries = trace->callback_entries,
		.pre_acquisition_callbacks = trace->pre_acquisition_callbacks,
		.timestamp_available = trace->timestamp_available,
		.timestamp_missing = trace->timestamp_missing,
		.raw_read_attempts = trace->raw_read_attempts,
		.raw_read_successes = trace->raw_read_successes,
		.raw_read_failures = trace->raw_read_failures,
		.notify_calls = trace->notify_calls,
		.notify_max_duration = trace->notify_max_duration,
		.last_raw_read_rc = trace->last_raw_read_rc,
		.counters_saturated = trace->counters_saturated,
	};
	k_spin_unlock(&trace->lock, key);
}
