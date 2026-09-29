/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_M1_BLE_CODEC_H_
#define KINEIMU_NODE_A_M1_BLE_CODEC_H_

#include <stddef.h>
#include <stdint.h>

#define NODE_A_BLE_MAGIC 0x494bU
#define NODE_A_BLE_PROTOCOL_VERSION 1U

#define NODE_A_BLE_IDENTITY_CONFIG_TYPE 2U
#define NODE_A_BLE_CLOCK_REQUEST_TYPE 3U
#define NODE_A_BLE_CLOCK_RESPONSE_TYPE 4U
#define NODE_A_BLE_STATUS_TYPE 5U

#define NODE_A_BLE_IDENTITY_CONFIG_SIZE 97U
#define NODE_A_BLE_CLOCK_REQUEST_SIZE 20U
#define NODE_A_BLE_CLOCK_RESPONSE_SIZE 48U
#define NODE_A_BLE_STATUS_SIZE 80U

#define NODE_A_BLE_TIMESTAMP_SOURCE_MCU_DRDY_ISR 1U
#define NODE_A_BLE_TIMESTAMP_SOURCE_SENSOR_INTERNAL 2U
#define NODE_A_BLE_TIMESTAMP_SOURCE_RECONSTRUCTED 3U

#define NODE_A_BLE_BATCH_SIZE_MIN 1U
#define NODE_A_BLE_BATCH_SIZE_MAX 4U

#define NODE_A_BLE_ACQUISITION_IDLE 0U
#define NODE_A_BLE_ACQUISITION_ARMED 1U
#define NODE_A_BLE_ACQUISITION_STREAMING 2U
#define NODE_A_BLE_ACQUISITION_ERROR 3U

#define NODE_A_BLE_STATUS_FLAG_SENSOR_READY (1U << 0)
#define NODE_A_BLE_STATUS_FLAG_SAMPLING_ACTIVE (1U << 1)
#define NODE_A_BLE_STATUS_FLAG_FATAL_LATCHED (1U << 2)
#define NODE_A_BLE_STATUS_FLAG_COUNTERS_SATURATED (1U << 3)
#define NODE_A_BLE_STATUS_KNOWN_FLAGS 0x000fU

struct node_a_ble_identity_config {
	uint8_t node_id;
	uint8_t timestamp_source;
	uint8_t firmware_version[3];
	uint8_t batch_size;
	uint32_t config_generation;
	uint32_t clock_epoch;
	uint64_t boot_id;
	uint64_t hardware_device_id;
	uint8_t firmware_git_commit[20];
	uint32_t timer_frequency_hz;
	uint32_t accel_odr_millihz;
	uint32_t gyro_odr_millihz;
	uint32_t accel_range_mg;
	uint32_t gyro_range_mdps;
	uint8_t sensor_registers[19];
};

struct node_a_ble_clock_request {
	uint32_t transaction_id;
	uint64_t host_send_ns;
};

struct node_a_ble_clock_response {
	uint32_t transaction_id;
	uint64_t host_send_ns;
	uint64_t boot_id;
	uint32_t clock_epoch;
	uint64_t device_receive_us;
	uint64_t device_indication_queued_us;
};

struct node_a_ble_status {
	uint8_t node_id;
	uint8_t acquisition_state;
	uint16_t flags;
	uint64_t boot_id;
	uint32_t clock_epoch;
	uint32_t status_sequence;
	uint32_t last_sample_sequence;
	uint32_t last_packet_sequence;
	uint64_t samples_acquired;
	uint64_t packets_generated;
	uint32_t sensor_fifo_overruns;
	uint32_t firmware_queue_overruns;
	uint32_t transport_backpressure_events;
	uint32_t samples_dropped_before_packetization;
	uint32_t acquisition_buffer_high_water_samples;
	uint32_t transport_queue_high_water_packets;
	uint32_t last_error_code;
};

int node_a_ble_encode_identity_config(
	const struct node_a_ble_identity_config *config,
	uint8_t *buffer, size_t buffer_size, size_t *encoded_size);

int node_a_ble_decode_clock_request(
	const uint8_t *buffer, size_t buffer_size,
	struct node_a_ble_clock_request *request);

int node_a_ble_encode_clock_response(
	const struct node_a_ble_clock_response *response,
	uint8_t *buffer, size_t buffer_size, size_t *encoded_size);

int node_a_ble_encode_status(const struct node_a_ble_status *status,
				     uint8_t *buffer, size_t buffer_size,
				     size_t *encoded_size);

#endif /* KINEIMU_NODE_A_M1_BLE_CODEC_H_ */
