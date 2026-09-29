/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include "m1_ble_identity.h"

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>

static int hex_nibble(char value)
{
	if (value >= '0' && value <= '9') {
		return value - '0';
	}
	if (value >= 'a' && value <= 'f') {
		return value - 'a' + 10;
	}
	if (value >= 'A' && value <= 'F') {
		return value - 'A' + 10;
	}

	return -1;
}

int node_a_ble_parse_git_commit(
	const char *hex, uint8_t commit[NODE_A_BLE_GIT_COMMIT_BYTE_LENGTH])
{
	uint8_t staged[NODE_A_BLE_GIT_COMMIT_BYTE_LENGTH];
	bool nonzero = false;

	if (hex == NULL || commit == NULL ||
	    strlen(hex) != NODE_A_BLE_GIT_COMMIT_HEX_LENGTH) {
		return -EINVAL;
	}

	for (size_t index = 0U; index < NODE_A_BLE_GIT_COMMIT_BYTE_LENGTH; ++index) {
		const int high = hex_nibble(hex[index * 2U]);
		const int low = hex_nibble(hex[index * 2U + 1U]);

		if (high < 0 || low < 0) {
			return -EINVAL;
		}

		staged[index] = (uint8_t)((high << 4) | low);
		nonzero = nonzero || staged[index] != 0U;
	}

	if (!nonzero) {
		return -EINVAL;
	}

	memcpy(commit, staged, sizeof(staged));
	return 0;
}
