/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/ztest.h>

#include "m1_conn_param_control.h"

#define TEST_CAPTURED_LINES 4U

struct captured_lines {
	char values[TEST_CAPTURED_LINES]
		[NODE_A_CONN_PARAM_CONTROL_LINE_CAPACITY];
	size_t lengths[TEST_CAPTURED_LINES];
	bool overflow[TEST_CAPTURED_LINES];
	size_t count;
};

static void capture_line(const char *line, size_t length, bool overflow,
			 void *context)
{
	struct captured_lines *captured = context;
	size_t index = captured->count;

	if (index >= TEST_CAPTURED_LINES) {
		return;
	}
	if (length >= NODE_A_CONN_PARAM_CONTROL_LINE_CAPACITY) {
		length = NODE_A_CONN_PARAM_CONTROL_LINE_CAPACITY - 1U;
	}
	memcpy(captured->values[index], line, length);
	captured->values[index][length] = '\0';
	captured->lengths[index] = length;
	captured->overflow[index] = overflow;
	captured->count++;
}

ZTEST(node_a_conn_param_control, test_rx_reassembles_a_fragmented_command)
{
	static const uint8_t first[] = "conn_param_request tx=17 ";
	static const uint8_t second[] = "mode=ON\r\n";
	struct node_a_conn_param_control_rx rx;
	struct captured_lines captured = {0};

	node_a_conn_param_control_rx_init(&rx);
	zassert_equal(node_a_conn_param_control_rx_push(
		&rx, first, sizeof(first) - 1U), sizeof(first) - 1U);
	zassert_equal(node_a_conn_param_control_rx_drain(
		&rx, capture_line, &captured), 0U);
	zassert_equal(node_a_conn_param_control_rx_push(
		&rx, second, sizeof(second) - 1U), sizeof(second) - 1U);
	zassert_equal(node_a_conn_param_control_rx_drain(
		&rx, capture_line, &captured), 1U);
	zassert_equal(captured.count, 1U);
	zassert_equal(captured.lengths[0],
		strlen("conn_param_request tx=17 mode=ON"));
	zassert_str_equal(captured.values[0],
		"conn_param_request tx=17 mode=ON");
	zassert_false(captured.overflow[0]);
}

ZTEST(node_a_conn_param_control, test_rx_delivers_multiple_complete_commands)
{
	static const uint8_t commands[] =
		"conn_param_request tx=1 mode=OFF\n"
		"conn_param_request tx=2 mode=ON\n";
	struct node_a_conn_param_control_rx rx;
	struct captured_lines captured = {0};

	node_a_conn_param_control_rx_init(&rx);
	zassert_equal(node_a_conn_param_control_rx_push(
		&rx, commands, sizeof(commands) - 1U), sizeof(commands) - 1U);
	zassert_equal(node_a_conn_param_control_rx_drain(
		&rx, capture_line, &captured), 2U);
	zassert_equal(captured.count, 2U);
	zassert_str_equal(captured.values[0],
		"conn_param_request tx=1 mode=OFF");
	zassert_str_equal(captured.values[1],
		"conn_param_request tx=2 mode=ON");
}

ZTEST(node_a_conn_param_control, test_rx_reports_a_line_overflow)
{
	uint8_t oversized[NODE_A_CONN_PARAM_CONTROL_LINE_CAPACITY + 8U];
	struct node_a_conn_param_control_rx rx;
	struct captured_lines captured = {0};

	memset(oversized, 'x', sizeof(oversized) - 1U);
	oversized[sizeof(oversized) - 1U] = '\n';
	node_a_conn_param_control_rx_init(&rx);
	zassert_equal(node_a_conn_param_control_rx_push(
		&rx, oversized, sizeof(oversized)), sizeof(oversized));
	zassert_equal(node_a_conn_param_control_rx_drain(
		&rx, capture_line, &captured), 1U);
	zassert_equal(captured.count, 1U);
	zassert_true(captured.overflow[0]);
}

ZTEST(node_a_conn_param_control, test_rx_reports_application_ring_overflow)
{
	uint8_t oversized[NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY + 8U];
	struct node_a_conn_param_control_rx rx;
	struct captured_lines captured = {0};

	memset(oversized, 'x', sizeof(oversized));
	node_a_conn_param_control_rx_init(&rx);
	zassert_equal(node_a_conn_param_control_rx_push(
		&rx, oversized, sizeof(oversized)),
		NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY);
	zassert_true(node_a_conn_param_control_rx_take_overflow(&rx));
	zassert_false(node_a_conn_param_control_rx_take_overflow(&rx));
	zassert_equal(node_a_conn_param_control_rx_drain(
		&rx, capture_line, &captured), 0U);
}

ZTEST(node_a_conn_param_control,
	test_first_complete_line_after_ring_overflow_is_delivered)
{
	uint8_t damaged[NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY + 8U];
	static const uint8_t recovered[] = "HELLO session=0123456789abcdef\n";
	struct node_a_conn_param_control_rx rx;
	struct captured_lines captured = {0};

	/* The received overflow fragment ends at a line boundary; all bytes before
	 * it belong to the damaged line and may be dropped as one unit. */
	memset(damaged, 'x', sizeof(damaged));
	damaged[sizeof(damaged) - 1U] = '\n';
	node_a_conn_param_control_rx_init(&rx);
	zassert_equal(node_a_conn_param_control_rx_push(
		&rx, damaged, sizeof(damaged)),
		NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY);
	zassert_true(node_a_conn_param_control_rx_take_overflow(&rx));
	zassert_equal(node_a_conn_param_control_rx_drain(
		&rx, capture_line, &captured), 0U);

	/* The next intact line must survive recovery instead of being consumed by
	 * the overflow resynchronizer. */
	zassert_equal(node_a_conn_param_control_rx_push(
		&rx, recovered, sizeof(recovered) - 1U), sizeof(recovered) - 1U);
	zassert_equal(node_a_conn_param_control_rx_drain(
		&rx, capture_line, &captured), 1U);
	zassert_equal(captured.count, 1U);
	zassert_str_equal(captured.values[0], "HELLO session=0123456789abcdef");
	zassert_false(captured.overflow[0]);
}

ZTEST(node_a_conn_param_control,
	test_complete_command_after_overflow_boundary_in_same_rx_chunk_is_delivered)
{
	static const uint8_t recovered[] = "HELLO session=0123456789abcdef\n";
	uint8_t damaged[NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY + 8U +
			sizeof(recovered) - 1U];
	struct node_a_conn_param_control_rx rx;
	struct captured_lines captured = {0};
	size_t boundary = NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY + 7U;

	memset(damaged, 'x', sizeof(damaged));
	damaged[boundary] = '\n';
	memcpy(&damaged[boundary + 1U], recovered, sizeof(recovered) - 1U);
	node_a_conn_param_control_rx_init(&rx);
	zassert_equal(node_a_conn_param_control_rx_push(
		&rx, damaged, sizeof(damaged)),
		NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY);
	zassert_true(node_a_conn_param_control_rx_take_overflow(&rx));
	zassert_equal(node_a_conn_param_control_rx_drain(
		&rx, capture_line, &captured), 1U);
	zassert_equal(captured.count, 1U);
	zassert_str_equal(captured.values[0], "HELLO session=0123456789abcdef");
	zassert_false(captured.overflow[0]);
}

ZTEST(node_a_conn_param_control,
	test_overflow_recovery_discards_partial_consumer_line_before_next_command)
{
	static const uint8_t partial[] = "damaged-prefix";
	static const uint8_t recovered[] = "HELLO session=0123456789abcdef\n";
	uint8_t damaged[NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY + 8U +
			sizeof(recovered) - 1U];
	struct node_a_conn_param_control_rx rx;
	struct captured_lines captured = {0};
	size_t boundary = NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY + 7U;

	memset(damaged, 'x', sizeof(damaged));
	damaged[boundary] = '\n';
	memcpy(&damaged[boundary + 1U], recovered, sizeof(recovered) - 1U);
	node_a_conn_param_control_rx_init(&rx);
	zassert_equal(node_a_conn_param_control_rx_push(
		&rx, partial, sizeof(partial) - 1U), sizeof(partial) - 1U);
	zassert_equal(node_a_conn_param_control_rx_drain(
		&rx, capture_line, &captured), 0U);

	/* Model an RX ISR overflowing while the consumer retains an incomplete
	 * line. The overflow latch is intentionally not consumed before drain. */
	zassert_equal(node_a_conn_param_control_rx_push(
		&rx, damaged, sizeof(damaged)), NODE_A_CONN_PARAM_CONTROL_RX_CAPACITY);
	zassert_equal(node_a_conn_param_control_rx_drain(
		&rx, capture_line, &captured), 1U);
	zassert_equal(captured.count, 1U);
	zassert_str_equal(captured.values[0], "HELLO session=0123456789abcdef");
	zassert_false(captured.overflow[0]);
}

ZTEST_SUITE(node_a_conn_param_control, NULL, NULL, NULL, NULL, NULL);
