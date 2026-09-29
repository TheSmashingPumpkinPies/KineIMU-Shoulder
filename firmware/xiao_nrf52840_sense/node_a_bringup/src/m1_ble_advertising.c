/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/util.h>

#include "m1_ble_advertising.h"

#define ADVERTISING_RETRY_DELAY K_MSEC(100)

static bool advertising_start_error_is_transient(int ret)
{
	return (ret == -EAGAIN) || (ret == -ENOMEM) ||
	       (ret == -ECONNREFUSED) || (ret == -EBUSY);
}

static void advertising_restart_work_handler(struct k_work *work)
{
	struct k_work_delayable *dwork = k_work_delayable_from_work(work);
	struct node_a_ble_advertising_restart *restart = CONTAINER_OF(
		dwork, struct node_a_ble_advertising_restart, work);
	const int ret = restart->start(restart->context);

	/* A callback may have left advertising active. That is already the desired
	 * state and is not a restart failure. */
	if ((ret < 0) && (ret != -EALREADY)) {
		printk("KineIMU BLE advertising restart failed rc=%d\n", ret);
		if (advertising_start_error_is_transient(ret)) {
			const int schedule_ret = k_work_reschedule(
				&restart->work, ADVERTISING_RETRY_DELAY);

			if (schedule_ret < 0) {
				printk("KineIMU BLE advertising retry schedule failed rc=%d\n",
				       schedule_ret);
			}
		}
	}
}

void node_a_ble_advertising_restart_init(
	struct node_a_ble_advertising_restart *restart,
	node_a_ble_advertising_start_fn start, void *context)
{
	__ASSERT_NO_MSG(restart != NULL);
	__ASSERT_NO_MSG(start != NULL);
	restart->start = start;
	restart->context = context;
	k_work_init_delayable(&restart->work, advertising_restart_work_handler);
}

int node_a_ble_advertising_restart_request(
	struct node_a_ble_advertising_restart *restart)
{
	if ((restart == NULL) || (restart->start == NULL)) {
		return -EINVAL;
	}

	return k_work_schedule(&restart->work, K_NO_WAIT);
}
