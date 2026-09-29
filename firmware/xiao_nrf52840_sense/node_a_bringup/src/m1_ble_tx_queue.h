/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_M1_BLE_TX_QUEUE_H_
#define KINEIMU_NODE_A_M1_BLE_TX_QUEUE_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/kernel.h>

#include "packet.h"

#define NODE_A_BLE_TX_QUEUE_CAPACITY 4U

/*
 * The producer owns its input buffer only for the duration of enqueue().
 * enqueue() copies a complete encoded packet into one of these fixed slots;
 * the consumer receives a by-value copy and may pass that copy to the
 * synchronous BLE API. No producer stack address is retained.
 */
struct node_a_ble_tx_packet {
	uint16_t size;
	uint32_t packet_sequence;
	uint32_t connection_generation;
	uint8_t data[NODE_A_PACKET_MAX_SIZE];
};

struct node_a_ble_tx_queue_stats {
	uint32_t high_water_packets;
	uint32_t enqueue_drops;
	uint32_t disconnect_drops;
	uint32_t stop_drops;
	bool counters_saturated;
};

struct node_a_ble_tx_queue {
	struct k_mutex lock;
	struct k_sem available;
	struct node_a_ble_tx_packet storage[NODE_A_BLE_TX_QUEUE_CAPACITY];
	struct node_a_ble_tx_queue_stats stats;
	uint16_t pending_packet_flags;
	uint32_t connection_generation;
	uint8_t head;
	uint8_t tail;
	uint8_t count;
	bool accepting;
	bool stopped;
};

/*
 * Queue policy:
 * - exactly NODE_A_BLE_TX_QUEUE_CAPACITY fixed-size packet slots;
 * - reject the newest packet with -ENOSPC when full, preserving accepted FIFO;
 * - disconnect closes and flushes the queue, and advances its generation so a
 *   packet already dequeued by the worker cannot cross a reconnect boundary;
 * - stop is terminal, flushes the queue, rejects future packets and wakes the
 *   worker so it can exit.
 *
 * Loss counters saturate at UINT32_MAX and the high-water value is a retained
 * peak, not the current queue depth. Transport loss sets the pending v1
 * transport-backpressure packet flag for the next packet that can be built.
 */
void node_a_ble_tx_queue_init(struct node_a_ble_tx_queue *queue);

int node_a_ble_tx_queue_open(struct node_a_ble_tx_queue *queue);

int node_a_ble_tx_queue_enqueue(struct node_a_ble_tx_queue *queue,
				const uint8_t *data, size_t size,
				uint32_t packet_sequence);

bool node_a_ble_tx_queue_get(struct node_a_ble_tx_queue *queue,
				     struct node_a_ble_tx_packet *packet,
				     k_timeout_t timeout);

void node_a_ble_tx_queue_disconnect(struct node_a_ble_tx_queue *queue);

void node_a_ble_tx_queue_stop(struct node_a_ble_tx_queue *queue);

bool node_a_ble_tx_queue_is_stopped(struct node_a_ble_tx_queue *queue);

uint8_t node_a_ble_tx_queue_pending_count_get(
	struct node_a_ble_tx_queue *queue);

uint32_t node_a_ble_tx_queue_connection_generation_get(
	struct node_a_ble_tx_queue *queue);

bool node_a_ble_tx_queue_packet_is_current(
	struct node_a_ble_tx_queue *queue,
	const struct node_a_ble_tx_packet *packet);

void node_a_ble_tx_queue_note_packet_discarded(
	struct node_a_ble_tx_queue *queue,
	const struct node_a_ble_tx_packet *packet);

void node_a_ble_tx_queue_note_transport_loss(
	struct node_a_ble_tx_queue *queue);

uint16_t node_a_ble_tx_queue_take_packet_flags(
	struct node_a_ble_tx_queue *queue);

void node_a_ble_tx_queue_stats_get(
	struct node_a_ble_tx_queue *queue,
	struct node_a_ble_tx_queue_stats *stats);

#endif /* KINEIMU_NODE_A_M1_BLE_TX_QUEUE_H_ */
