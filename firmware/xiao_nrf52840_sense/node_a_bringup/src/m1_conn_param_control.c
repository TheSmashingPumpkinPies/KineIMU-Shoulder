/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/ring_buffer.h>

#include "m1_conn_param_control.h"

static struct k_spinlock rx_lock;

static void start_recovery(struct node_a_conn_param_control_rx *rx,
			   bool discard_until_newline)
{
	ring_buf_reset(&rx->ring);
	rx->recovery_generation++;
	rx->recovery_active = true;
	rx->recovery_complete = false;
	rx->recovery_line_length = 0U;
	rx->recovery_line_overflow = false;
	rx->discard_until_newline = discard_until_newline;
	rx->last_queued_byte_valid = false;
}

static void append_recovery_bytes(struct node_a_conn_param_control_rx *rx,
				  const uint8_t *bytes, size_t length)
{
	size_t index = 0U;

	while (index < length) {
		uint8_t byte = bytes[index++];

		if (rx->recovery_complete) {
			return;
		}
		if (rx->discard_until_newline) {
			if (byte == '\n') {
				rx->discard_until_newline = false;
			}
			continue;
		}
		if (byte == '\r') {
			continue;
		}
		if (byte == '\n') {
			if (!rx->recovery_line_overflow &&
			    (rx->recovery_line_length > 0U)) {
				uint8_t newline = '\n';
				uint32_t line_bytes = ring_buf_put(
					&rx->ring,
					(const uint8_t *)rx->recovery_line,
					(uint32_t)rx->recovery_line_length);
				uint32_t newline_bytes = 0U;

				if (line_bytes == rx->recovery_line_length) {
					newline_bytes = ring_buf_put(&rx->ring, &newline, 1U);
				}
				if (line_bytes == rx->recovery_line_length &&
				    newline_bytes == 1U) {
					rx->last_queued_byte = '\n';
					rx->last_queued_byte_valid = true;
					rx->recovery_active = false;
					rx->recovery_complete = true;
				} else {
					ring_buf_reset(&rx->ring);
					rx->discard_until_newline = true;
				}
			}
			rx->recovery_line_length = 0U;
			rx->recovery_line_overflow = false;
			continue;
		}
		if (rx->recovery_line_overflow) {
			continue;
		}
		if (rx->recovery_line_length >=
		    sizeof(rx->recovery_line) - 1U) {
			rx->recovery_line_length = 0U;
			rx->recovery_line_overflow = true;
			continue;
		}
		rx->recovery_line[rx->recovery_line_length++] = (char)byte;
	}
}

void node_a_conn_param_control_rx_init(
	struct node_a_conn_param_control_rx *rx)
{
	if (rx == NULL) {
		return;
	}

	memset(rx, 0, sizeof(*rx));
	ring_buf_init(&rx->ring, sizeof(rx->storage), rx->storage);
}

size_t node_a_conn_param_control_rx_push(
	struct node_a_conn_param_control_rx *rx,
	const uint8_t *bytes, size_t length)
{
	k_spinlock_key_t key;
	uint32_t accepted;

	if ((rx == NULL) || ((bytes == NULL) && (length > 0U))) {
		return 0U;
	}
	if (length == 0U) {
		return 0U;
	}
	if (length > NODE_A_CONN_PARAM_CONTROL_MAX_PUSH_CAPACITY) {
		key = k_spin_lock(&rx_lock);
		atomic_set(&rx->overflow, 1);
		start_recovery(rx, true);
		k_spin_unlock(&rx_lock, key);
		return 0U;
	}

	key = k_spin_lock(&rx_lock);
	if (rx->recovery_active || rx->recovery_complete) {
		append_recovery_bytes(rx, bytes, length);
		k_spin_unlock(&rx_lock, key);
		return length;
	}
	accepted = ring_buf_put(&rx->ring, bytes, (uint32_t)length);
	if (accepted > 0U) {
		rx->last_queued_byte = bytes[accepted - 1U];
		rx->last_queued_byte_valid = true;
	}
	if (accepted != length) {
		atomic_set(&rx->overflow, 1);
		bool at_line_boundary = accepted > 0U
			? bytes[accepted - 1U] == '\n'
			: (rx->last_queued_byte_valid &&
			   rx->last_queued_byte == '\n');

		start_recovery(rx, !at_line_boundary);
		if ((size_t)accepted < length) {
			append_recovery_bytes(rx, &bytes[accepted],
					     length - (size_t)accepted);
		}
	}
	k_spin_unlock(&rx_lock, key);
	return (size_t)accepted;
}

bool node_a_conn_param_control_rx_take_overflow(
	struct node_a_conn_param_control_rx *rx)
{
	k_spinlock_key_t key;
	bool overflowed;

	if (rx == NULL) {
		return false;
	}

	key = k_spin_lock(&rx_lock);
	overflowed = atomic_cas(&rx->overflow, 1, 0);
	if (overflowed) {
		rx->line_length = 0U;
		rx->line_overflow = false;
		rx->consumer_generation = rx->recovery_generation;
	}
	if (overflowed || rx->recovery_complete) {
		rx->recovery_complete = false;
	}
	k_spin_unlock(&rx_lock, key);
	return overflowed;
}

size_t node_a_conn_param_control_rx_drain(
	struct node_a_conn_param_control_rx *rx,
	node_a_conn_param_control_line_fn on_line, void *context)
{
	size_t lines = 0U;
	uint8_t byte;

	if ((rx == NULL) || (on_line == NULL)) {
		return 0U;
	}

	for (;;) {
		k_spinlock_key_t key = k_spin_lock(&rx_lock);
		uint32_t count = ring_buf_get(&rx->ring, &byte, 1U);
		uint32_t generation = rx->recovery_generation;
		bool discard = rx->discard_until_newline;

		if ((count > 0U) && discard && (byte == '\n')) {
			rx->discard_until_newline = false;
		}

		k_spin_unlock(&rx_lock, key);
		if (generation != rx->consumer_generation) {
			rx->line_length = 0U;
			rx->line_overflow = false;
			rx->consumer_generation = generation;
		}
		if (count == 0U) {
			break;
		}

		if (discard) {
			continue;
		}
		if (byte == '\r') {
			continue;
		}
		if (byte == '\n') {
			if ((rx->line_length > 0U) || rx->line_overflow) {
				rx->line[rx->line_length] = '\0';
				on_line(rx->line, rx->line_length,
					rx->line_overflow, context);
				lines++;
			}
			rx->line_length = 0U;
			rx->line_overflow = false;
			continue;
		}
		if (rx->line_overflow) {
			continue;
		}
		if (rx->line_length >= sizeof(rx->line) - 1U) {
			rx->line_overflow = true;
			continue;
		}
		rx->line[rx->line_length++] = (char)byte;
	}

	return lines;
}
