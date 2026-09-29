/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_PACKET_H_
#define KINEIMU_NODE_A_PACKET_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "acquisition.h"
#include "node_config.h"

#define NODE_A_PACKET_MAGIC 0x494bU
#define NODE_A_PACKET_PROTOCOL_VERSION 1U
#define NODE_A_PACKET_SAMPLE_BATCH_TYPE 1U
#define NODE_A_PACKET_NODE_ID KINEIMU_NODE_ID

#define NODE_A_PACKET_HEADER_SIZE 16U
#define NODE_A_PACKET_SAMPLE_SIZE 26U
#define NODE_A_PACKET_CRC_SIZE 4U
#define NODE_A_PACKET_MAX_SAMPLES 4U
#define NODE_A_PACKET_MAX_SIZE 124U

#define NODE_A_PACKET_FLAG_SENSOR_FIFO_OVERRUN (1U << 0)
#define NODE_A_PACKET_FLAG_FIRMWARE_QUEUE_OVERRUN (1U << 1)
#define NODE_A_PACKET_FLAG_TRANSPORT_BACKPRESSURE (1U << 2)
#define NODE_A_PACKET_FLAG_DISCONTINUITY (1U << 3)

#define NODE_A_SAMPLE_FLAG_ACCEL_CLIPPED (1U << 0)
#define NODE_A_SAMPLE_FLAG_GYRO_CLIPPED (1U << 1)
#define NODE_A_SAMPLE_FLAG_TIMESTAMP_RECONSTRUCTED (1U << 2)

struct node_a_sample_packet {
	uint8_t node_id;
	uint32_t packet_sequence;
	uint32_t clock_epoch;
	uint16_t flags;
	const struct node_a_imu_sample *samples;
	size_t sample_count;
};

uint32_t node_a_packet_crc32c(const uint8_t *data, size_t length);

int node_a_packet_encode(const struct node_a_sample_packet *packet,
			 uint8_t *buffer, size_t buffer_size,
			 size_t *encoded_size);

bool node_a_packet_samples_have_discontinuity(
	const struct node_a_imu_sample *samples, size_t sample_count,
	bool have_previous_sample, uint32_t previous_sample_sequence);

#endif /* KINEIMU_NODE_A_PACKET_H_ */
