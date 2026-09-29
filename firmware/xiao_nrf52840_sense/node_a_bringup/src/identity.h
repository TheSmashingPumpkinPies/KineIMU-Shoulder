/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_IDENTITY_H_
#define KINEIMU_NODE_IDENTITY_H_

#include <stdint.h>

/* M1 identity/config encodes (DEVICEID[1] << 32) | DEVICEID[0]. */
uint64_t node_a_ficr_device_id_from_words(uint32_t deviceid0,
						  uint32_t deviceid1);

#endif /* KINEIMU_NODE_IDENTITY_H_ */
