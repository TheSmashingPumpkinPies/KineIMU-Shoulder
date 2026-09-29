/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <string.h>

#include "m1_ble_tx_queue.h"

BUILD_ASSERT(NODE_A_BLE_TX_QUEUE_CAPACITY > 0U,
	     "BLE TX queue capacity must be non-zero");
BUILD_ASSERT(NODE_A_BLE_TX_QUEUE_CAPACITY <= UINT8_MAX,
	     "BLE TX queue indices must fit in uint8_t");

static void saturating_add(uint32_t *counter,
			   uint32_t amount,
			   bool *counters_saturated)
{
	if (amount == 0U) {
		return;
	}
	if (*counter > UINT32_MAX - amount) {
		*counter = UINT32_MAX;
		*counters_saturated = true;
		return;
	}
	*counter += amount;
	if (*counter == UINT32_MAX) {
		*counters_saturated = true;
	}
}

static void note_transport_loss_locked(struct node_a_ble_tx_queue *queue)
{
	queue->pending_packet_flags |= NODE_A_PACKET_FLAG_TRANSPORT_BACKPRESSURE;
}

static void reset_ring_locked(struct node_a_ble_tx_queue *queue)
{
	queue->head = 0U;
	queue->tail = 0U;
	queue->count = 0U;
	/* Resetting the item semaphore is part of the flush transaction. New puts
	 * cannot race it because they take the same queue mutex first. */
	k_sem_reset(&queue->available);
}

static void advance_connection_generation_locked(
	struct node_a_ble_tx_queue *queue)
{
	if (queue->connection_generation < UINT32_MAX) {
		queue->connection_generation++;
	} else {
		/* A saturated generation cannot safely distinguish a packet from the
		 * previous connection. Make the queue terminal rather than reusing the
		 * same generation and risking stale data after a reconnect. */
		queue->stopped = true;
		queue->stats.counters_saturated = true;
	}
}

void node_a_ble_tx_queue_init(struct node_a_ble_tx_queue *queue)
{
	if (queue == NULL) {
		return;
	}

	memset(queue, 0, sizeof(*queue));
	k_mutex_init(&queue->lock);
	k_sem_init(&queue->available, 0U, NODE_A_BLE_TX_QUEUE_CAPACITY);
	queue->connection_generation = 1U;
	/* The service opens the queue only for a current connected/CCC-enabled
	 * generation. Keeping it closed until then makes startup ownership clear. */
	queue->accepting = false;
	queue->stopped = false;
}

int node_a_ble_tx_queue_open(struct node_a_ble_tx_queue *queue)
{
	if (queue == NULL) {
		return -EINVAL;
	}

	k_mutex_lock(&queue->lock, K_FOREVER);
	if (queue->stopped) {
		k_mutex_unlock(&queue->lock);
		return -ESHUTDOWN;
	}
	queue->accepting = true;
	k_mutex_unlock(&queue->lock);
	return 0;
}

int node_a_ble_tx_queue_enqueue(struct node_a_ble_tx_queue *queue,
				const uint8_t *data, size_t size,
				uint32_t packet_sequence)
{
	struct node_a_ble_tx_packet *slot;

	if ((queue == NULL) || (data == NULL) || (size == 0U)) {
		return -EINVAL;
	}
	if (size > NODE_A_PACKET_MAX_SIZE) {
		return -EMSGSIZE;
	}

	k_mutex_lock(&queue->lock, K_FOREVER);
	if (queue->stopped) {
		saturating_add(&queue->stats.stop_drops, 1U,
				       &queue->stats.counters_saturated);
		note_transport_loss_locked(queue);
		k_mutex_unlock(&queue->lock);
		return -ESHUTDOWN;
	}
	if (!queue->accepting) {
		saturating_add(&queue->stats.disconnect_drops, 1U,
				       &queue->stats.counters_saturated);
		note_transport_loss_locked(queue);
		k_mutex_unlock(&queue->lock);
		return -ENOTCONN;
	}
	if (queue->count == NODE_A_BLE_TX_QUEUE_CAPACITY) {
		/* Reject newest: every item already accepted retains its FIFO place. */
		saturating_add(&queue->stats.enqueue_drops, 1U,
				       &queue->stats.counters_saturated);
		note_transport_loss_locked(queue);
		k_mutex_unlock(&queue->lock);
		return -ENOSPC;
	}

	slot = &queue->storage[queue->head];
	slot->size = (uint16_t)size;
	slot->packet_sequence = packet_sequence;
	slot->connection_generation = queue->connection_generation;
	/* Copy before returning. The producer may reuse or leave its encoded
	 * buffer immediately after this function returns. */
	memcpy(slot->data, data, size);
	queue->head = (uint8_t)((queue->head + 1U) %
				       NODE_A_BLE_TX_QUEUE_CAPACITY);
	queue->count++;
	if (queue->count > queue->stats.high_water_packets) {
		queue->stats.high_water_packets = queue->count;
	}
	k_mutex_unlock(&queue->lock);

	k_sem_give(&queue->available);
	return 0;
}

bool node_a_ble_tx_queue_get(struct node_a_ble_tx_queue *queue,
				     struct node_a_ble_tx_packet *packet,
				     k_timeout_t timeout)
{
	if ((queue == NULL) || (packet == NULL)) {
		return false;
	}
	if (k_sem_take(&queue->available, timeout) != 0) {
		return false;
	}

	k_mutex_lock(&queue->lock, K_FOREVER);
	if (queue->count == 0U) {
		/* A disconnect/stop flush can reset the semaphore while a worker is
		 * between taking its wake token and taking the mutex. */
		k_mutex_unlock(&queue->lock);
		return false;
	}
	*packet = queue->storage[queue->tail];
	queue->tail = (uint8_t)((queue->tail + 1U) %
				       NODE_A_BLE_TX_QUEUE_CAPACITY);
	queue->count--;
	k_mutex_unlock(&queue->lock);
	return true;
}

void node_a_ble_tx_queue_disconnect(struct node_a_ble_tx_queue *queue)
{
	uint32_t dropped;

	if (queue == NULL) {
		return;
	}

	k_mutex_lock(&queue->lock, K_FOREVER);
	dropped = queue->count;
	queue->accepting = false;
	advance_connection_generation_locked(queue);
	reset_ring_locked(queue);
	saturating_add(&queue->stats.disconnect_drops, dropped,
			       &queue->stats.counters_saturated);
	if (dropped != 0U) {
		note_transport_loss_locked(queue);
	}
	k_mutex_unlock(&queue->lock);
}

void node_a_ble_tx_queue_stop(struct node_a_ble_tx_queue *queue)
{
	uint32_t dropped;

	if (queue == NULL) {
		return;
	}

	k_mutex_lock(&queue->lock, K_FOREVER);
	dropped = queue->count;
	queue->accepting = false;
	queue->stopped = true;
	reset_ring_locked(queue);
	saturating_add(&queue->stats.stop_drops, dropped,
			       &queue->stats.counters_saturated);
	if (dropped != 0U) {
		note_transport_loss_locked(queue);
	}
	k_mutex_unlock(&queue->lock);

	/* Wake a worker blocked on an empty queue so the terminal stop is observed. */
	(void)k_sem_give(&queue->available);
}

bool node_a_ble_tx_queue_is_stopped(struct node_a_ble_tx_queue *queue)
{
	bool stopped;

	if (queue == NULL) {
		return true;
	}
	k_mutex_lock(&queue->lock, K_FOREVER);
	stopped = queue->stopped;
	k_mutex_unlock(&queue->lock);
	return stopped;
}

uint8_t node_a_ble_tx_queue_pending_count_get(
	struct node_a_ble_tx_queue *queue)
{
	uint8_t pending_count;

	if (queue == NULL) {
		return 0U;
	}

	k_mutex_lock(&queue->lock, K_FOREVER);
	pending_count = queue->count;
	k_mutex_unlock(&queue->lock);
	return pending_count;
}

uint32_t node_a_ble_tx_queue_connection_generation_get(
	struct node_a_ble_tx_queue *queue)
{
	uint32_t connection_generation;

	if (queue == NULL) {
		return 0U;
	}

	k_mutex_lock(&queue->lock, K_FOREVER);
	connection_generation = queue->connection_generation;
	k_mutex_unlock(&queue->lock);
	return connection_generation;
}

bool node_a_ble_tx_queue_packet_is_current(
	struct node_a_ble_tx_queue *queue,
	const struct node_a_ble_tx_packet *packet)
{
	bool current;

	if ((queue == NULL) || (packet == NULL)) {
		return false;
	}
	k_mutex_lock(&queue->lock, K_FOREVER);
	current = !queue->stopped && queue->accepting &&
		(packet->connection_generation == queue->connection_generation);
	k_mutex_unlock(&queue->lock);
	return current;
}

void node_a_ble_tx_queue_note_packet_discarded(
	struct node_a_ble_tx_queue *queue,
	const struct node_a_ble_tx_packet *packet)
{
	if ((queue == NULL) || (packet == NULL)) {
		return;
	}

	k_mutex_lock(&queue->lock, K_FOREVER);
	if (queue->stopped) {
		saturating_add(&queue->stats.stop_drops, 1U,
				       &queue->stats.counters_saturated);
	} else {
		saturating_add(&queue->stats.disconnect_drops, 1U,
				       &queue->stats.counters_saturated);
	}
	note_transport_loss_locked(queue);
	k_mutex_unlock(&queue->lock);
}

void node_a_ble_tx_queue_note_transport_loss(
	struct node_a_ble_tx_queue *queue)
{
	if (queue == NULL) {
		return;
	}
	k_mutex_lock(&queue->lock, K_FOREVER);
	note_transport_loss_locked(queue);
	k_mutex_unlock(&queue->lock);
}

uint16_t node_a_ble_tx_queue_take_packet_flags(
	struct node_a_ble_tx_queue *queue)
{
	uint16_t flags;

	if (queue == NULL) {
		return 0U;
	}
	k_mutex_lock(&queue->lock, K_FOREVER);
	flags = queue->pending_packet_flags;
	queue->pending_packet_flags = 0U;
	k_mutex_unlock(&queue->lock);
	return flags;
}

void node_a_ble_tx_queue_stats_get(
	struct node_a_ble_tx_queue *queue,
	struct node_a_ble_tx_queue_stats *stats)
{
	if ((queue == NULL) || (stats == NULL)) {
		return;
	}
	k_mutex_lock(&queue->lock, K_FOREVER);
	*stats = queue->stats;
	k_mutex_unlock(&queue->lock);
}
