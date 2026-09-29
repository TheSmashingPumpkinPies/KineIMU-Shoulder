/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stddef.h>
#include <string.h>

#include "lsm6dsl_raw.h"
#include "node_config.h"
#include "packet.h"

#define LSM6DSL_OUTX_L_G 0x22U
#define LSM6DSL_RAW_BURST_BYTES 12U
#define LSM6DSL_AXIS_BYTES 2U
#define LSM6DSL_AXIS_COUNT 3U
#define LSM6DSL_ACCEL_OFFSET 6U

/*
 * Raw-code clipping criterion for the configured M1 ranges.
 *
 * The LSM6DS3TR-C datasheet specifies two's-complement 16-bit output and
 * nominal sensitivities of 0.122 mg/LSB at +/-4 g and 17.50 mdps/LSB at
 * +/-500 dps. The first integer code at or above a configured full scale is
 * ceil(full_scale / sensitivity), evaluated below with integer sub-units:
 *
 *   accel: ceil(4,000 mg * 1,000 / 122 micro-mg/LSB) = 32,787 codes
 *   gyro:  ceil(500,000 mdps * 100 / 1,750 centi-mdps/LSB) = 28,572 codes
 *
 * The acceleration code is beyond the signed int16 representation. Its
 * auditable raw-code criterion is therefore exactly the two representable
 * int16 endpoints (+32767 and -32768). The gyro criterion is +/-28,572.
 * There is no extra near-full-scale margin in either criterion. These flags
 * report a code at or beyond the configured full-scale-equivalent boundary;
 * they do not prove that the analog sensing element itself saturated.
 */
#define NODE_A_ACCEL_FULL_SCALE_MG NODE_A_ACCEL_RANGE_MG
#define NODE_A_ACCEL_SENSITIVITY_UMG_PER_LSB 122U
#define NODE_A_ACCEL_FS_CODE_CEIL \
	((NODE_A_ACCEL_FULL_SCALE_MG * 1000U + \
	  NODE_A_ACCEL_SENSITIVITY_UMG_PER_LSB - 1U) / \
	 NODE_A_ACCEL_SENSITIVITY_UMG_PER_LSB)
#define NODE_A_GYRO_FULL_SCALE_MDPS NODE_A_GYRO_RANGE_MDPS
#define NODE_A_GYRO_SENSITIVITY_CENTI_MDPS_PER_LSB 1750U
#define NODE_A_GYRO_FS_CODE_CEIL \
	((NODE_A_GYRO_FULL_SCALE_MDPS * 100U + \
	  NODE_A_GYRO_SENSITIVITY_CENTI_MDPS_PER_LSB - 1U) / \
	 NODE_A_GYRO_SENSITIVITY_CENTI_MDPS_PER_LSB)

#define NODE_A_CLIP_POSITIVE_LIMIT(fs_code) \
	(((fs_code) < (uint32_t)INT16_MAX) ? \
	 (uint32_t)(fs_code) : (uint32_t)INT16_MAX)
#define NODE_A_CLIP_NEGATIVE_MAGNITUDE(fs_code) \
	(((fs_code) < ((uint32_t)INT16_MAX + 1U)) ? \
	 (uint32_t)(fs_code) : ((uint32_t)INT16_MAX + 1U))

static bool raw_count_reaches_limit(int16_t count,
				     uint32_t positive_limit,
				     uint32_t negative_magnitude)
{
	const int32_t signed_count = (int32_t)count;

	return (signed_count >= (int32_t)positive_limit) ||
		(signed_count <= -(int32_t)negative_magnitude);
}

static uint16_t detect_clipping_flags(const int16_t accel_raw[3],
				      const int16_t gyro_raw[3],
				      uint16_t existing_flags)
{
	uint16_t flags = existing_flags & (uint16_t)~(
		NODE_A_SAMPLE_FLAG_ACCEL_CLIPPED |
		NODE_A_SAMPLE_FLAG_GYRO_CLIPPED);
	const uint32_t accel_positive_limit =
		NODE_A_CLIP_POSITIVE_LIMIT(NODE_A_ACCEL_FS_CODE_CEIL);
	const uint32_t accel_negative_magnitude =
		NODE_A_CLIP_NEGATIVE_MAGNITUDE(NODE_A_ACCEL_FS_CODE_CEIL);
	const uint32_t gyro_limit =
		NODE_A_CLIP_POSITIVE_LIMIT(NODE_A_GYRO_FS_CODE_CEIL);

	for (size_t axis = 0U; axis < LSM6DSL_AXIS_COUNT; ++axis) {
		if (raw_count_reaches_limit(accel_raw[axis],
						    accel_positive_limit,
						    accel_negative_magnitude)) {
			flags |= NODE_A_SAMPLE_FLAG_ACCEL_CLIPPED;
		}
		if (raw_count_reaches_limit(gyro_raw[axis], gyro_limit,
						    gyro_limit)) {
			flags |= NODE_A_SAMPLE_FLAG_GYRO_CLIPPED;
		}
	}

	return flags;
}

static int16_t decode_le_i16(const uint8_t *bytes)
{
	return (int16_t)((uint16_t)bytes[0] |
			 ((uint16_t)bytes[1] << 8));
}

int node_a_lsm6dsl_read_raw(
	const struct i2c_dt_spec *spec,
	node_a_lsm6dsl_burst_read_fn burst_read,
	struct node_a_imu_sample *sample)
{
	uint8_t registers[LSM6DSL_RAW_BURST_BYTES];
	int16_t accel_raw[LSM6DSL_AXIS_COUNT];
	int16_t gyro_raw[LSM6DSL_AXIS_COUNT];
	int rc;

	if ((spec == NULL) || (burst_read == NULL) || (sample == NULL)) {
		return -EINVAL;
	}

	rc = burst_read(spec, LSM6DSL_OUTX_L_G, registers,
			LSM6DSL_RAW_BURST_BYTES);
	if (rc < 0) {
		return rc;
	}

	for (size_t axis = 0U; axis < LSM6DSL_AXIS_COUNT; ++axis) {
		gyro_raw[axis] =
			decode_le_i16(&registers[axis * LSM6DSL_AXIS_BYTES]);
		accel_raw[axis] = decode_le_i16(
			&registers[LSM6DSL_ACCEL_OFFSET +
				   axis * LSM6DSL_AXIS_BYTES]);
	}

	memcpy(sample->accel_raw, accel_raw, sizeof(accel_raw));
	memcpy(sample->gyro_raw, gyro_raw, sizeof(gyro_raw));
	sample->flags = detect_clipping_flags(
		accel_raw, gyro_raw, sample->flags);
	return 0;
}
