/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/ztest.h>

typedef int (*node_a_register_burst_read_fn)(
	const struct i2c_dt_spec *spec, uint8_t start_addr, uint8_t *buf,
	uint32_t num_bytes);

int node_a_imu_read_register_snapshot(
	const struct i2c_dt_spec *spec, node_a_register_burst_read_fn burst_read,
	uint8_t snapshot[19]);

static const uint8_t expected_start_addresses[] = {
	0x06U, 0x0dU, 0x10U, 0x5eU,
};
static const uint32_t expected_lengths[] = {5U, 2U, 10U, 2U};
static size_t call_count;
static size_t fail_call;
static int read_error;

static int fake_register_burst_read(const struct i2c_dt_spec *spec,
					uint8_t start_addr, uint8_t *buf,
					uint32_t num_bytes)
{
	ARG_UNUSED(spec);
	if (call_count >= ARRAY_SIZE(expected_start_addresses)) {
		return -EOVERFLOW;
	}
	if ((start_addr != expected_start_addresses[call_count]) ||
	    (num_bytes != expected_lengths[call_count])) {
		return -EINVAL;
	}
	if (call_count == fail_call) {
		call_count++;
		return read_error;
	}

	for (uint32_t index = 0U; index < num_bytes; ++index) {
		buf[index] = (uint8_t)(10U * call_count + index);
	}
	call_count++;
	return 0;
}

/* RED-phase fallback. The production acquisition adapter replaces this. */
__weak int node_a_imu_read_register_snapshot(
	const struct i2c_dt_spec *spec, node_a_register_burst_read_fn burst_read,
	uint8_t snapshot[19])
{
	ARG_UNUSED(spec);
	ARG_UNUSED(burst_read);
	ARG_UNUSED(snapshot);
	return -ENOSYS;
}

static void reset_fake(void)
{
	call_count = 0U;
	fail_call = SIZE_MAX;
	read_error = -EIO;
}

ZTEST(node_a_register_snapshot, test_reads_snapshot_in_contract_order)
{
	const struct i2c_dt_spec spec = {0};
	uint8_t snapshot[19];

	reset_fake();
	memset(snapshot, 0U, sizeof(snapshot));
	zassert_ok(node_a_imu_read_register_snapshot(
		&spec, fake_register_burst_read, snapshot), NULL);
	zassert_equal(call_count, ARRAY_SIZE(expected_start_addresses), NULL);
	zassert_equal(snapshot[0], 0U, NULL);
	zassert_equal(snapshot[4], 4U, NULL);
	zassert_equal(snapshot[5], 10U, NULL);
	zassert_equal(snapshot[6], 11U, NULL);
	zassert_equal(snapshot[7], 20U, NULL);
	zassert_equal(snapshot[16], 29U, NULL);
	zassert_equal(snapshot[17], 30U, NULL);
	zassert_equal(snapshot[18], 31U, NULL);
}

ZTEST(node_a_register_snapshot, test_read_error_preserves_snapshot)
{
	const struct i2c_dt_spec spec = {0};
	uint8_t snapshot[19];
	uint8_t expected[19];

	reset_fake();
	fail_call = 2U;
	memset(snapshot, 0xa5, sizeof(snapshot));
	memset(expected, 0xa5, sizeof(expected));
	zassert_equal(node_a_imu_read_register_snapshot(
		&spec, fake_register_burst_read, snapshot), -EIO, NULL);
	zassert_mem_equal(snapshot, expected, sizeof(snapshot), NULL);
	zassert_equal(call_count, 3U, NULL);
}

ZTEST_SUITE(node_a_register_snapshot, NULL, NULL, NULL, NULL, NULL);
