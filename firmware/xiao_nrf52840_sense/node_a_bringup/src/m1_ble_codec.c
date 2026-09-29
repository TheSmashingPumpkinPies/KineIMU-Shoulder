/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdbool.h>
#include <string.h>

#include "m1_ble_codec.h"
#include "packet.h"

static void put_u16_le(uint8_t *destination, uint16_t value)
{
	destination[0] = (uint8_t)value;
	destination[1] = (uint8_t)(value >> 8);
}

static void put_u32_le(uint8_t *destination, uint32_t value)
{
	destination[0] = (uint8_t)value;
	destination[1] = (uint8_t)(value >> 8);
	destination[2] = (uint8_t)(value >> 16);
	destination[3] = (uint8_t)(value >> 24);
}

static void put_u64_le(uint8_t *destination, uint64_t value)
{
	put_u32_le(destination, (uint32_t)value);
	put_u32_le(&destination[4], (uint32_t)(value >> 32));
}

static uint16_t get_u16_le(const uint8_t *source)
{
	return (uint16_t)source[0] | ((uint16_t)source[1] << 8);
}

static uint32_t get_u32_le(const uint8_t *source)
{
	return (uint32_t)source[0] |
		((uint32_t)source[1] << 8) |
		((uint32_t)source[2] << 16) |
		((uint32_t)source[3] << 24);
}

static uint64_t get_u64_le(const uint8_t *source)
{
	return (uint64_t)get_u32_le(source) |
		((uint64_t)get_u32_le(&source[4]) << 32);
}

static bool valid_node_id(uint8_t node_id)
{
	return (node_id == 1U) || (node_id == 2U);
}

static bool valid_header(const uint8_t *buffer, uint8_t message_type)
{
	return (get_u16_le(&buffer[0]) == NODE_A_BLE_MAGIC) &&
		(buffer[2] == NODE_A_BLE_PROTOCOL_VERSION) &&
		(buffer[3] == message_type);
}

static bool valid_crc(const uint8_t *buffer, size_t payload_size)
{
	return node_a_packet_crc32c(buffer, payload_size) ==
		get_u32_le(&buffer[payload_size]);
}

static void append_crc(uint8_t *buffer, size_t payload_size)
{
	put_u32_le(&buffer[payload_size],
		   node_a_packet_crc32c(buffer, payload_size));
}

int node_a_ble_encode_identity_config(
	const struct node_a_ble_identity_config *config,
	uint8_t *buffer, size_t buffer_size, size_t *encoded_size)
{
	if ((config == NULL) || (buffer == NULL) || (encoded_size == NULL)) {
		return -EINVAL;
	}
	if (!valid_node_id(config->node_id) ||
	    (config->timestamp_source <
	     NODE_A_BLE_TIMESTAMP_SOURCE_MCU_DRDY_ISR) ||
	    (config->timestamp_source > NODE_A_BLE_TIMESTAMP_SOURCE_RECONSTRUCTED) ||
	    (config->batch_size < NODE_A_BLE_BATCH_SIZE_MIN) ||
	    (config->batch_size > NODE_A_BLE_BATCH_SIZE_MAX) ||
	    (config->boot_id == 0U) || (config->hardware_device_id == 0U)) {
		return -EINVAL;
	}
	if (buffer_size < NODE_A_BLE_IDENTITY_CONFIG_SIZE) {
		return -ENOSPC;
	}

	put_u16_le(&buffer[0], NODE_A_BLE_MAGIC);
	buffer[2] = NODE_A_BLE_PROTOCOL_VERSION;
	buffer[3] = NODE_A_BLE_IDENTITY_CONFIG_TYPE;
	buffer[4] = config->node_id;
	buffer[5] = config->timestamp_source;
	memcpy(&buffer[6], config->firmware_version,
	       sizeof(config->firmware_version));
	buffer[9] = config->batch_size;
	put_u32_le(&buffer[10], config->config_generation);
	put_u32_le(&buffer[14], config->clock_epoch);
	put_u64_le(&buffer[18], config->boot_id);
	put_u64_le(&buffer[26], config->hardware_device_id);
	memcpy(&buffer[34], config->firmware_git_commit,
	       sizeof(config->firmware_git_commit));
	put_u32_le(&buffer[54], config->timer_frequency_hz);
	put_u32_le(&buffer[58], config->accel_odr_millihz);
	put_u32_le(&buffer[62], config->gyro_odr_millihz);
	put_u32_le(&buffer[66], config->accel_range_mg);
	put_u32_le(&buffer[70], config->gyro_range_mdps);
	memcpy(&buffer[74], config->sensor_registers,
	       sizeof(config->sensor_registers));
	append_crc(buffer, NODE_A_BLE_IDENTITY_CONFIG_SIZE - sizeof(uint32_t));
	*encoded_size = NODE_A_BLE_IDENTITY_CONFIG_SIZE;
	return 0;
}

int node_a_ble_decode_clock_request(
	const uint8_t *buffer, size_t buffer_size,
	struct node_a_ble_clock_request *request)
{
	struct node_a_ble_clock_request decoded;

	if ((buffer == NULL) || (request == NULL)) {
		return -EINVAL;
	}
	if (buffer_size != NODE_A_BLE_CLOCK_REQUEST_SIZE) {
		return -EMSGSIZE;
	}
	if (!valid_header(buffer, NODE_A_BLE_CLOCK_REQUEST_TYPE) ||
	    !valid_crc(buffer,
		       NODE_A_BLE_CLOCK_REQUEST_SIZE - sizeof(uint32_t))) {
		return -EBADMSG;
	}

	decoded.transaction_id = get_u32_le(&buffer[4]);
	decoded.host_send_ns = get_u64_le(&buffer[8]);
	*request = decoded;
	return 0;
}

int node_a_ble_encode_clock_response(
	const struct node_a_ble_clock_response *response,
	uint8_t *buffer, size_t buffer_size, size_t *encoded_size)
{
	if ((response == NULL) || (buffer == NULL) || (encoded_size == NULL)) {
		return -EINVAL;
	}
	if ((response->boot_id == 0U) ||
	    (response->device_indication_queued_us <
	     response->device_receive_us)) {
		return -EINVAL;
	}
	if (buffer_size < NODE_A_BLE_CLOCK_RESPONSE_SIZE) {
		return -ENOSPC;
	}

	put_u16_le(&buffer[0], NODE_A_BLE_MAGIC);
	buffer[2] = NODE_A_BLE_PROTOCOL_VERSION;
	buffer[3] = NODE_A_BLE_CLOCK_RESPONSE_TYPE;
	put_u32_le(&buffer[4], response->transaction_id);
	put_u64_le(&buffer[8], response->host_send_ns);
	put_u64_le(&buffer[16], response->boot_id);
	put_u32_le(&buffer[24], response->clock_epoch);
	put_u64_le(&buffer[28], response->device_receive_us);
	put_u64_le(&buffer[36], response->device_indication_queued_us);
	append_crc(buffer, NODE_A_BLE_CLOCK_RESPONSE_SIZE - sizeof(uint32_t));
	*encoded_size = NODE_A_BLE_CLOCK_RESPONSE_SIZE;
	return 0;
}

int node_a_ble_encode_status(const struct node_a_ble_status *status,
				     uint8_t *buffer, size_t buffer_size,
				     size_t *encoded_size)
{
	if ((status == NULL) || (buffer == NULL) || (encoded_size == NULL)) {
		return -EINVAL;
	}
	if (!valid_node_id(status->node_id) ||
	    (status->acquisition_state > NODE_A_BLE_ACQUISITION_ERROR) ||
	    ((status->flags & (uint16_t)~NODE_A_BLE_STATUS_KNOWN_FLAGS) != 0U) ||
	    (status->boot_id == 0U)) {
		return -EINVAL;
	}
	if (buffer_size < NODE_A_BLE_STATUS_SIZE) {
		return -ENOSPC;
	}

	put_u16_le(&buffer[0], NODE_A_BLE_MAGIC);
	buffer[2] = NODE_A_BLE_PROTOCOL_VERSION;
	buffer[3] = NODE_A_BLE_STATUS_TYPE;
	buffer[4] = status->node_id;
	buffer[5] = status->acquisition_state;
	put_u16_le(&buffer[6], status->flags);
	put_u64_le(&buffer[8], status->boot_id);
	put_u32_le(&buffer[16], status->clock_epoch);
	put_u32_le(&buffer[20], status->status_sequence);
	put_u32_le(&buffer[24], status->last_sample_sequence);
	put_u32_le(&buffer[28], status->last_packet_sequence);
	put_u64_le(&buffer[32], status->samples_acquired);
	put_u64_le(&buffer[40], status->packets_generated);
	put_u32_le(&buffer[48], status->sensor_fifo_overruns);
	put_u32_le(&buffer[52], status->firmware_queue_overruns);
	put_u32_le(&buffer[56], status->transport_backpressure_events);
	put_u32_le(&buffer[60], status->samples_dropped_before_packetization);
	put_u32_le(&buffer[64], status->acquisition_buffer_high_water_samples);
	put_u32_le(&buffer[68], status->transport_queue_high_water_packets);
	put_u32_le(&buffer[72], status->last_error_code);
	append_crc(buffer, NODE_A_BLE_STATUS_SIZE - sizeof(uint32_t));
	*encoded_size = NODE_A_BLE_STATUS_SIZE;
	return 0;
}
