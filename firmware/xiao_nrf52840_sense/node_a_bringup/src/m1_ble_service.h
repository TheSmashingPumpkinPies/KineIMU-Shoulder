/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_M1_BLE_SERVICE_H_
#define KINEIMU_NODE_A_M1_BLE_SERVICE_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/kernel.h>

#include "m1_ble_codec.h"
#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
#include "m1_conn_param_experiment.h"
#endif
#include "m1_ble_tx_diagnostics.h"

int node_a_ble_service_set_identity(
	const struct node_a_ble_identity_config *config);

int node_a_ble_service_update_status(const struct node_a_ble_status *status);

int node_a_ble_service_start(void);

int node_a_ble_service_wait_ready(k_timeout_t timeout);

#if defined(KINEIMU_CONN_PARAM_EXPERIMENT)
int node_a_ble_service_set_conn_param_request_mode(
	enum node_a_conn_param_request_mode mode);

enum node_a_conn_param_request_mode
node_a_ble_service_conn_param_request_mode_get(void);
#endif

bool node_a_ble_service_is_stream_ready(void);

uint16_t node_a_ble_service_att_mtu(void);

struct node_a_ble_service_tx_stats {
	uint32_t queue_high_water_packets;
	uint32_t enqueue_drops;
	uint32_t disconnect_drops;
	uint32_t stop_drops;
	/* Legacy terminal-context count; not actual GATT API invocation count. */
	uint32_t notify_calls;
	uint32_t notify_failures;
	/* Starts at context claim and includes scheduling/retry delay. */
	uint32_t notify_last_duration_us;
	uint32_t notify_max_duration_us;
	uint64_t notify_total_duration_us;
	bool counters_saturated;
	struct node_a_ble_tx_diagnostics_snapshot diagnostics;
};

/* Packetizer-facing API: enqueue owns a copy; it never calls GATT directly. */
int node_a_ble_service_enqueue_packet(const uint8_t *packet, size_t packet_size,
					      uint32_t packet_sequence);

uint16_t node_a_ble_service_take_tx_packet_flags(void);

void node_a_ble_service_tx_stats_get(
	struct node_a_ble_service_tx_stats *stats);

/* Terminal shutdown used when the acquisition application enters fatal state. */
void node_a_ble_service_stop_tx(void);

int node_a_ble_service_indicate_identity(void);

int node_a_ble_service_indicate_status(void);

#endif /* KINEIMU_NODE_A_M1_BLE_SERVICE_H_ */
