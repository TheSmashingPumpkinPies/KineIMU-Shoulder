/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_CONFIG_H_
#define KINEIMU_NODE_CONFIG_H_

/* The application defaults to Node A so an unqualified build remains safe for
 * the existing Node A hardware record. Node B builds must opt in explicitly
 * with -DKINEIMU_NODE_ID=2.
 */
#ifndef KINEIMU_NODE_ID
#define KINEIMU_NODE_ID 1U
#endif

#if (KINEIMU_NODE_ID != 1U) && (KINEIMU_NODE_ID != 2U)
#error "KINEIMU_NODE_ID must be 1 (A) or 2 (B)"
#endif

#if KINEIMU_NODE_ID == 1U
#define KINEIMU_NODE_LABEL "A"
#else
#define KINEIMU_NODE_LABEL "B"
#endif

/* Frozen M1 sensor configuration shared by the driver setup, raw-code
 * clipping checks and identity/configuration metadata. */
#define NODE_A_ACCEL_RANGE_G 4
#define NODE_A_GYRO_RANGE_DPS 500
#define NODE_A_ACCEL_RANGE_MG (NODE_A_ACCEL_RANGE_G * 1000U)
#define NODE_A_GYRO_RANGE_MDPS (NODE_A_GYRO_RANGE_DPS * 1000U)

#endif /* KINEIMU_NODE_CONFIG_H_ */
