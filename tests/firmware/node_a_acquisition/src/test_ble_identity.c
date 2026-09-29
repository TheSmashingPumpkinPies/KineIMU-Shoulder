/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/ztest.h>

#include "m1_ble_identity.h"

ZTEST(node_a_ble_identity, test_parses_exactly_40_hex_digits)
{
	const char *hex = "00112233445566778899aabbccddeeff00112233";
	const uint8_t expected[20] = {
		0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99,
		0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff, 0x00, 0x11, 0x22, 0x33,
	};
	uint8_t commit[20];

	zassert_ok(node_a_ble_parse_git_commit(hex, commit), NULL);
	zassert_mem_equal(commit, expected, sizeof(commit), NULL);
}

ZTEST(node_a_ble_identity, test_rejects_invalid_length_or_digit)
{
	uint8_t commit[20];

	zassert_equal(node_a_ble_parse_git_commit(
		"00112233445566778899aabbccddeeff0011223", commit), -EINVAL, NULL);
	zassert_equal(node_a_ble_parse_git_commit(
		"00112233445566778899aabbccddeeff0011223g", commit), -EINVAL, NULL);
}

ZTEST(node_a_ble_identity, test_rejects_all_zero_commit)
{
	uint8_t commit[20];

	zassert_equal(node_a_ble_parse_git_commit(
		"0000000000000000000000000000000000000000", commit), -EINVAL, NULL);
}

ZTEST_SUITE(node_a_ble_identity, NULL, NULL, NULL, NULL, NULL);
