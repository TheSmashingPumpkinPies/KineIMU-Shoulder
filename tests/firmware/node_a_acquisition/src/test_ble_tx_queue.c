/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/ztest.h>

#include "m1_ble_tx_queue.h"

static void fill_packet(uint8_t *packet, size_t size, uint8_t marker)
{
	for (size_t index = 0U; index < size; ++index) {
		packet[index] = (uint8_t)(marker + index);
	}
}

static int enqueue_marker(struct node_a_ble_tx_queue *queue,
			  uint32_t packet_sequence, uint8_t marker)
{
	uint8_t packet[NODE_A_PACKET_MAX_SIZE];

	fill_packet(packet, sizeof(packet), marker);
	return node_a_ble_tx_queue_enqueue(queue, packet, sizeof(packet),
					   packet_sequence);
}

ZTEST(node_a_ble_tx_queue, test_enqueue_copies_owned_bytes_before_source_changes)
{
	struct node_a_ble_tx_queue queue;
	struct node_a_ble_tx_packet received;
	uint8_t source[NODE_A_PACKET_MAX_SIZE];
	uint8_t expected[NODE_A_PACKET_MAX_SIZE];

	node_a_ble_tx_queue_init(&queue);
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	fill_packet(source, sizeof(source), 0x20U);
	memcpy(expected, source, sizeof(expected));

	zassert_ok(node_a_ble_tx_queue_enqueue(&queue, source, sizeof(source),
					       17U));
	memset(source, 0xa5, sizeof(source));

	zassert_true(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
	zassert_equal(received.size, sizeof(expected));
	zassert_equal(received.packet_sequence, 17U);
	/* The queue owns a fixed byte copy; it must not retain the producer's
	 * stack buffer after enqueue returns. */
	zassert_mem_equal(received.data, expected, sizeof(expected));
}

ZTEST(node_a_ble_tx_queue, test_accepted_packets_leave_in_fifo_sequence)
{
	struct node_a_ble_tx_queue queue;
	struct node_a_ble_tx_packet received;

	node_a_ble_tx_queue_init(&queue);
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	for (uint32_t sequence = 10U; sequence < 13U; ++sequence) {
		zassert_ok(enqueue_marker(&queue, sequence, (uint8_t)sequence));
	}

	for (uint32_t sequence = 10U; sequence < 13U; ++sequence) {
		zassert_true(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
		zassert_equal(received.packet_sequence, sequence);
		zassert_equal(received.data[0], (uint8_t)sequence);
	}
	zassert_false(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
}

ZTEST(node_a_ble_tx_queue, test_full_queue_rejects_newest_and_preserves_fifo)
{
	struct node_a_ble_tx_queue queue;
	struct node_a_ble_tx_packet received;
	struct node_a_ble_tx_queue_stats stats;

	node_a_ble_tx_queue_init(&queue);
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	for (uint32_t sequence = 0U;
	     sequence < NODE_A_BLE_TX_QUEUE_CAPACITY; ++sequence) {
		zassert_ok(enqueue_marker(&queue, sequence, (uint8_t)sequence));
	}

	zassert_equal(enqueue_marker(&queue, NODE_A_BLE_TX_QUEUE_CAPACITY,
				     0xeeU), -ENOSPC);
	node_a_ble_tx_queue_stats_get(&queue, &stats);
	zassert_equal(stats.enqueue_drops, 1U);
	zassert_equal(stats.high_water_packets,
		      NODE_A_BLE_TX_QUEUE_CAPACITY);
	zassert_equal(node_a_ble_tx_queue_take_packet_flags(&queue),
		      NODE_A_PACKET_FLAG_TRANSPORT_BACKPRESSURE);

	for (uint32_t sequence = 0U;
	     sequence < NODE_A_BLE_TX_QUEUE_CAPACITY; ++sequence) {
		zassert_true(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
		/* Reject-newest policy preserves every packet already accepted. */
		zassert_equal(received.packet_sequence, sequence);
	}
}

ZTEST(node_a_ble_tx_queue, test_dequeue_then_enqueue_reuses_slot_without_reordering)
{
	struct node_a_ble_tx_queue queue;
	struct node_a_ble_tx_packet received;

	node_a_ble_tx_queue_init(&queue);
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	for (uint32_t sequence = 0U;
	     sequence < NODE_A_BLE_TX_QUEUE_CAPACITY; ++sequence) {
		zassert_ok(enqueue_marker(&queue, sequence, (uint8_t)sequence));
	}
	zassert_equal(enqueue_marker(&queue, 99U, 0x99U), -ENOSPC);
	zassert_true(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
	zassert_equal(received.packet_sequence, 0U);
	zassert_ok(enqueue_marker(&queue, 100U, 0x64U));

	for (uint32_t sequence = 1U;
	     sequence < NODE_A_BLE_TX_QUEUE_CAPACITY; ++sequence) {
		zassert_true(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
		zassert_equal(received.packet_sequence, sequence);
	}
	zassert_true(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
	zassert_equal(received.packet_sequence, 100U);
}

ZTEST(node_a_ble_tx_queue, test_disconnect_flushes_queued_packets_and_reopens_clean)
{
	struct node_a_ble_tx_queue queue;
	struct node_a_ble_tx_packet received;
	struct node_a_ble_tx_queue_stats stats;
	uint8_t rejected_data[NODE_A_PACKET_MAX_SIZE] = {0};

	node_a_ble_tx_queue_init(&queue);
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	zassert_ok(enqueue_marker(&queue, 1U, 1U));
	zassert_ok(enqueue_marker(&queue, 2U, 2U));

	node_a_ble_tx_queue_disconnect(&queue);
	zassert_false(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
	zassert_equal(node_a_ble_tx_queue_enqueue(
			&queue, rejected_data, sizeof(rejected_data), 3U), -ENOTCONN);
	node_a_ble_tx_queue_stats_get(&queue, &stats);
	/* Two queued packets are flushed and the post-disconnect enqueue is
	 * rejected under the same disconnect-loss accounting. */
	zassert_equal(stats.disconnect_drops, 3U);
	zassert_equal(node_a_ble_tx_queue_take_packet_flags(&queue),
		      NODE_A_PACKET_FLAG_TRANSPORT_BACKPRESSURE);

	zassert_ok(node_a_ble_tx_queue_open(&queue));
	zassert_ok(enqueue_marker(&queue, 4U, 4U));
	zassert_true(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
	zassert_equal(received.packet_sequence, 4U);
	zassert_false(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
}

ZTEST(node_a_ble_tx_queue, test_disconnect_invalidates_dequeued_packet_generation)
{
	struct node_a_ble_tx_queue queue;
	struct node_a_ble_tx_packet received;
	struct node_a_ble_tx_queue_stats stats;

	node_a_ble_tx_queue_init(&queue);
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	zassert_ok(enqueue_marker(&queue, 7U, 7U));
	zassert_true(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
	zassert_true(node_a_ble_tx_queue_packet_is_current(&queue, &received));

	node_a_ble_tx_queue_disconnect(&queue);
	zassert_false(node_a_ble_tx_queue_packet_is_current(&queue, &received));
	node_a_ble_tx_queue_note_packet_discarded(&queue, &received);
	node_a_ble_tx_queue_stats_get(&queue, &stats);
	/* A worker that already dequeued a packet must discard it after the
	 * connection generation changes; it must not retry it on reconnect. */
	zassert_equal(stats.disconnect_drops, 1U);

	zassert_ok(node_a_ble_tx_queue_open(&queue));
	zassert_ok(enqueue_marker(&queue, 8U, 8U));
	zassert_true(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
	zassert_equal(received.packet_sequence, 8U);
}

ZTEST(node_a_ble_tx_queue, test_stop_flushes_and_rejects_future_packets)
{
	struct node_a_ble_tx_queue queue;
	struct node_a_ble_tx_packet received;
	struct node_a_ble_tx_queue_stats stats;

	node_a_ble_tx_queue_init(&queue);
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	zassert_ok(enqueue_marker(&queue, 1U, 1U));
	node_a_ble_tx_queue_stop(&queue);

	zassert_true(node_a_ble_tx_queue_is_stopped(&queue));
	zassert_false(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));
	zassert_equal(enqueue_marker(&queue, 2U, 2U), -ESHUTDOWN);
	node_a_ble_tx_queue_stats_get(&queue, &stats);
	zassert_equal(stats.stop_drops, 2U);
	zassert_equal(node_a_ble_tx_queue_open(&queue), -ESHUTDOWN);
}

ZTEST(node_a_ble_tx_queue, test_high_water_remains_peak_after_drain)
{
	struct node_a_ble_tx_queue queue;
	struct node_a_ble_tx_packet received;
	struct node_a_ble_tx_queue_stats stats;

	node_a_ble_tx_queue_init(&queue);
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	for (uint32_t sequence = 0U;
	     sequence < NODE_A_BLE_TX_QUEUE_CAPACITY; ++sequence) {
		zassert_ok(enqueue_marker(&queue, sequence, (uint8_t)sequence));
	}
	while (node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT)) {
	}
	zassert_ok(enqueue_marker(&queue, 20U, 20U));
	node_a_ble_tx_queue_stats_get(&queue, &stats);
	zassert_equal(stats.high_water_packets,
		      NODE_A_BLE_TX_QUEUE_CAPACITY);
}

ZTEST(node_a_ble_tx_queue, test_loss_counters_saturate_without_wrap)
{
	struct node_a_ble_tx_queue queue;
	struct node_a_ble_tx_queue_stats stats;

	node_a_ble_tx_queue_init(&queue);
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	queue.stats.enqueue_drops = UINT32_MAX - 1U;
	for (uint32_t sequence = 0U;
	     sequence < NODE_A_BLE_TX_QUEUE_CAPACITY; ++sequence) {
		zassert_ok(enqueue_marker(&queue, sequence, (uint8_t)sequence));
	}
	zassert_equal(enqueue_marker(&queue, 4U, 4U), -ENOSPC);
	zassert_equal(enqueue_marker(&queue, 5U, 5U), -ENOSPC);

	node_a_ble_tx_queue_disconnect(&queue);
	node_a_ble_tx_queue_stats_get(&queue, &stats);
	zassert_equal(stats.enqueue_drops, UINT32_MAX);
	zassert_equal(stats.disconnect_drops, NODE_A_BLE_TX_QUEUE_CAPACITY);
	zassert_true(stats.counters_saturated);

	/* The terminal-stop accounting has its own saturation path. */
	node_a_ble_tx_queue_init(&queue);
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	queue.stats.stop_drops = UINT32_MAX - 1U;
	zassert_ok(enqueue_marker(&queue, 8U, 8U));
	zassert_ok(enqueue_marker(&queue, 9U, 9U));
	node_a_ble_tx_queue_stop(&queue);
	node_a_ble_tx_queue_stats_get(&queue, &stats);
	zassert_equal(stats.stop_drops, UINT32_MAX);
	zassert_true(stats.counters_saturated);
}

ZTEST(node_a_ble_tx_queue, test_generation_saturation_stops_reuse)
{
	struct node_a_ble_tx_queue queue;
	struct node_a_ble_tx_packet received;
	struct node_a_ble_tx_queue_stats stats;

	node_a_ble_tx_queue_init(&queue);
	queue.connection_generation = UINT32_MAX;
	zassert_ok(node_a_ble_tx_queue_open(&queue));
	zassert_ok(enqueue_marker(&queue, 41U, 0x41U));
	zassert_true(node_a_ble_tx_queue_get(&queue, &received, K_NO_WAIT));

	node_a_ble_tx_queue_disconnect(&queue);
	zassert_true(node_a_ble_tx_queue_is_stopped(&queue));
	zassert_false(node_a_ble_tx_queue_packet_is_current(&queue, &received));
	zassert_equal(node_a_ble_tx_queue_open(&queue), -ESHUTDOWN);
	node_a_ble_tx_queue_stats_get(&queue, &stats);
	zassert_true(stats.counters_saturated);
}

ZTEST_SUITE(node_a_ble_tx_queue, NULL, NULL, NULL, NULL, NULL);
