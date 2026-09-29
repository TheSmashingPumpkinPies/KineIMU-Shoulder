/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_M1_CONN_PARAM_CONTROL_H_
#define KINEIMU_NODE_A_M1_CONN_PARAM_CONTROL_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/sys/atomic.h>
#include <zephyr/sys/ring_buffer.h>

#define NODE_A_CONN_PARAM_CONTROL_LINE_CAPACITY 64U
#define NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY 128U
#define NODE_A_CONN_PARAM_CONTROL_MAX_PUSH_CAPACITY \
	(NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY + \
	 NODE_A_CONN_PARAM_CONTROL_LINE_CAPACITY)

typedef void (*node_a_conn_param_control_line_fn)(
	const char *line, size_t length, bool overflow, void *context);

struct node_a_conn_param_control_rx {
	struct ring_buf ring;
	uint8_t storage[NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY];
	atomic_t overflow;
	bool last_queued_byte_valid;
	uint8_t last_queued_byte;
	char line[NODE_A_CONN_PARAM_CONTROL_LINE_CAPACITY];
	size_t line_length;
	bool line_overflow;
	bool discard_until_newline;
	bool recovery_active;
	bool recovery_complete;
	uint32_t recovery_generation;
	uint32_t consumer_generation;
	char recovery_line[NODE_A_CONN_PARAM_CONTROL_LINE_CAPACITY];
	size_t recovery_line_length;
	bool recovery_line_overflow;
};

void node_a_conn_param_control_rx_init(
	struct node_a_conn_param_control_rx *rx);

size_t node_a_conn_param_control_rx_push(
	struct node_a_conn_param_control_rx *rx,
	const uint8_t *bytes, size_t length);

bool node_a_conn_param_control_rx_take_overflow(
	struct node_a_conn_param_control_rx *rx);

size_t node_a_conn_param_control_rx_drain(
	struct node_a_conn_param_control_rx *rx,
	node_a_conn_param_control_line_fn on_line, void *context);

#endif /* KINEIMU_NODE_A_M1_CONN_PARAM_CONTROL_H_ */
