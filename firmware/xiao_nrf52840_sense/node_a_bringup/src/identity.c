/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include "identity.h"

uint64_t node_a_ficr_device_id_from_words(uint32_t deviceid0,
						  uint32_t deviceid1)
{
	return ((uint64_t)deviceid1 << 32) | (uint64_t)deviceid0;
}
