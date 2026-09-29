/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_NODE_A_M1_BLE_IDENTITY_H_
#define KINEIMU_NODE_A_M1_BLE_IDENTITY_H_

#include <stdint.h>

#define NODE_A_BLE_GIT_COMMIT_HEX_LENGTH 40U
#define NODE_A_BLE_GIT_COMMIT_BYTE_LENGTH 20U

/* Parse a 40-character Git SHA-1 string without accepting an all-zero value. */
int node_a_ble_parse_git_commit(
	const char *hex, uint8_t commit[NODE_A_BLE_GIT_COMMIT_BYTE_LENGTH]);

#endif /* KINEIMU_NODE_A_M1_BLE_IDENTITY_H_ */
