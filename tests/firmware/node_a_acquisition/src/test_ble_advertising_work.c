/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>
#include <zephyr/ztest.h>

#include "m1_ble_advertising.h"

struct advertising_probe {
	struct k_sem called;
	uint32_t calls;
	int return_code;
	int return_codes[2];
	size_t return_code_count;
	bool ran_in_isr;
};

static int probe_start(void *context)
{
	struct advertising_probe *probe = context;

	probe->calls++;
	probe->ran_in_isr = k_is_in_isr();
	k_sem_give(&probe->called);
	if (probe->return_code_count > 0U) {
		const size_t index = MIN(probe->calls - 1U, probe->return_code_count - 1U);
		return probe->return_codes[index];
	}
	return probe->return_code;
}

ZTEST(node_a_ble_advertising_work,
	test_restart_request_runs_start_on_system_workqueue)
{
	struct advertising_probe probe = {
		.return_code = 0,
	};
	struct node_a_ble_advertising_restart restart;

	k_sem_init(&probe.called, 0, 1);
	node_a_ble_advertising_restart_init(&restart, probe_start, &probe);
	zassert_true(node_a_ble_advertising_restart_request(&restart) >= 0);
	zassert_ok(k_sem_take(&probe.called, K_MSEC(1000)));
	zassert_equal(probe.calls, 1U);
	zassert_false(probe.ran_in_isr);
}

ZTEST(node_a_ble_advertising_work,
	test_already_advertising_is_an_acceptable_restart_result)
{
	struct advertising_probe probe = {
		.return_code = -EALREADY,
	};
	struct node_a_ble_advertising_restart restart;

	k_sem_init(&probe.called, 0, 1);
	node_a_ble_advertising_restart_init(&restart, probe_start, &probe);
	zassert_true(node_a_ble_advertising_restart_request(&restart) >= 0);
	zassert_ok(k_sem_take(&probe.called, K_MSEC(1000)));
	zassert_equal(probe.calls, 1U);
}

ZTEST(node_a_ble_advertising_work,
	test_transient_start_failure_is_retried_on_system_workqueue)
{
	struct advertising_probe probe = {
		.return_codes = {-ENOMEM, 0},
		.return_code_count = 2U,
	};
	struct node_a_ble_advertising_restart restart;

	k_sem_init(&probe.called, 0, 1);
	node_a_ble_advertising_restart_init(&restart, probe_start, &probe);
	zassert_true(node_a_ble_advertising_restart_request(&restart) >= 0);
	zassert_ok(k_sem_take(&probe.called, K_MSEC(1000)));
	zassert_ok(k_sem_take(&probe.called, K_MSEC(1000)));
	zassert_equal(probe.calls, 2U);
	zassert_false(probe.ran_in_isr);
}

ZTEST_SUITE(node_a_ble_advertising_work, NULL, NULL, NULL, NULL, NULL);
