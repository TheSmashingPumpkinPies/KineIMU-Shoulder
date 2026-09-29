/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef KINEIMU_M1_BLE_ADVERTISING_H_
#define KINEIMU_M1_BLE_ADVERTISING_H_

#include <zephyr/kernel.h>

typedef int (*node_a_ble_advertising_start_fn)(void *context);

struct node_a_ble_advertising_restart {
	struct k_work_delayable work;
	node_a_ble_advertising_start_fn start;
	void *context;
};

/* Initialize the work item before Bluetooth callbacks can be delivered. */
void node_a_ble_advertising_restart_init(
	struct node_a_ble_advertising_restart *restart,
	node_a_ble_advertising_start_fn start, void *context);

/* Schedule the start callback on Zephyr's system workqueue. Transient
 * resource failures are retried asynchronously by the same work item. */
int node_a_ble_advertising_restart_request(
	struct node_a_ble_advertising_restart *restart);

#endif /* KINEIMU_M1_BLE_ADVERTISING_H_ */
