/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>

#include "packet.h"

#define NODE_A_PACKET_KNOWN_FLAGS 0x000fU
#define NODE_A_SAMPLE_KNOWN_FLAGS 0x0007U
#define NODE_A_PACKET_CRC32C_POLY 0x82f63b78U

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

static void put_i16_le(uint8_t *destination, int16_t value)
{
	put_u16_le(destination, (uint16_t)value);
}

uint32_t node_a_packet_crc32c(const uint8_t *data, size_t length)
{
	uint32_t crc = UINT32_MAX;

	if ((data == NULL) && (length != 0U)) {
		return 0U;
	}

	for (size_t index = 0U; index < length; ++index) {
		crc ^= data[index];
		for (uint8_t bit = 0U; bit < 8U; ++bit) {
			crc = (crc >> 1) ^
				((crc & 1U) ? NODE_A_PACKET_CRC32C_POLY : 0U);
		}
	}

	return crc ^ UINT32_MAX;
}

int node_a_packet_encode(const struct node_a_sample_packet *packet,
				 uint8_t *buffer, size_t buffer_size,
				 size_t *encoded_size)
{
	size_t payload_size;
	size_t offset;

	if ((packet == NULL) || (buffer == NULL) || (encoded_size == NULL)) {
		return -EINVAL;
	}
	if ((packet->node_id != 1U) && (packet->node_id != 2U)) {
		return -EINVAL;
	}
	if ((packet->sample_count < 1U) ||
	    (packet->sample_count > NODE_A_PACKET_MAX_SAMPLES) ||
	    (packet->samples == NULL)) {
		return -EINVAL;
	}
	if ((packet->flags & (uint16_t)~NODE_A_PACKET_KNOWN_FLAGS) != 0U) {
		return -EINVAL;
	}

	payload_size = NODE_A_PACKET_HEADER_SIZE +
		packet->sample_count * NODE_A_PACKET_SAMPLE_SIZE;
	if (buffer_size < payload_size + NODE_A_PACKET_CRC_SIZE) {
		return -ENOSPC;
	}

	put_u16_le(&buffer[0], NODE_A_PACKET_MAGIC);
	buffer[2] = NODE_A_PACKET_PROTOCOL_VERSION;
	buffer[3] = NODE_A_PACKET_SAMPLE_BATCH_TYPE;
	buffer[4] = packet->node_id;
	buffer[5] = (uint8_t)packet->sample_count;
	put_u16_le(&buffer[6], packet->flags);
	put_u32_le(&buffer[8], packet->packet_sequence);
	put_u32_le(&buffer[12], packet->clock_epoch);

	offset = NODE_A_PACKET_HEADER_SIZE;
	for (size_t index = 0U; index < packet->sample_count; ++index) {
		const struct node_a_imu_sample *sample = &packet->samples[index];

		if (sample->clock_epoch != packet->clock_epoch) {
			return -EINVAL;
		}
		if ((sample->flags & (uint16_t)~NODE_A_SAMPLE_KNOWN_FLAGS) != 0U) {
			return -EINVAL;
		}

		put_u32_le(&buffer[offset], sample->sample_sequence);
		put_u64_le(&buffer[offset + 4], sample->timestamp_us);
		put_u16_le(&buffer[offset + 12], sample->flags);
		for (size_t axis = 0U; axis < 3U; ++axis) {
			put_i16_le(&buffer[offset + 14U + axis * 2U],
				   sample->accel_raw[axis]);
			put_i16_le(&buffer[offset + 20U + axis * 2U],
				   sample->gyro_raw[axis]);
		}
		offset += NODE_A_PACKET_SAMPLE_SIZE;
	}

	put_u32_le(&buffer[payload_size],
		   node_a_packet_crc32c(buffer, payload_size));
	*encoded_size = payload_size + NODE_A_PACKET_CRC_SIZE;
	return 0;
}

bool node_a_packet_samples_have_discontinuity(
	const struct node_a_imu_sample *samples, size_t sample_count,
	bool have_previous_sample, uint32_t previous_sample_sequence)
{
	if ((samples == NULL) || (sample_count == 0U)) {
		return false;
	}

	if (have_previous_sample &&
	    (samples[0].sample_sequence != previous_sample_sequence + 1U)) {
		return true;
	}

	for (size_t index = 1U; index < sample_count; ++index) {
		if (samples[index].sample_sequence !=
		    samples[index - 1U].sample_sequence + 1U) {
			return true;
		}
	}

	return false;
}
