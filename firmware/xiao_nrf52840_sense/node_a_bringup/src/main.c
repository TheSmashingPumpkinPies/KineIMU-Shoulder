/*
 * Copyright (c) 2026 KineIMU Shoulder contributors
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <hal/nrf_ficr.h>

#include "acquisition.h"
#include "counters.h"
#include "identity.h"
#include "lsm6dsl_fifo.h"
#include "lsm6dsl_raw.h"
#include "node_config.h"
#include "packet.h"
#include "sample_queue.h"
#include "timestamp.h"

#define IMU_NODE DT_NODELABEL(lsm6ds3tr_c)
#define IMU_POWER_UP_DELAY K_MSEC(50)
#define LSM6DS3TR_C_REG_INT1_CTRL 0x0d
#define LSM6DS3TR_C_REG_WHO_AM_I 0x0f
#define LSM6DS3TR_C_REG_CTRL1_XL 0x10
#define LSM6DS3TR_C_REG_CTRL2_G 0x11
#define NODE_A_PACKET_BATCH_SIZE NODE_A_PACKET_MAX_SAMPLES
#define NODE_A_PACKET_GATHER_TIMEOUT K_MSEC(20)

BUILD_ASSERT(DT_NODE_HAS_COMPAT(DT_CHOSEN(zephyr_console),
				zephyr_cdc_acm_uart),
		     "bring-up console must be CDC ACM UART");

static const struct device *const imu = DEVICE_DT_GET(IMU_NODE);
static const struct i2c_dt_spec imu_i2c = I2C_DT_SPEC_GET(IMU_NODE);
static const struct gpio_dt_spec imu_drdy_gpio =
	GPIO_DT_SPEC_GET(IMU_NODE, irq_gpios);
static const struct device *const console =
	DEVICE_DT_GET(DT_CHOSEN(zephyr_console));
static struct node_a_drdy_timestamp drdy_timestamp;
static struct node_a_stream_counters stream_counters;
static struct node_a_sample_queue sample_queue;
static struct node_a_lsm6dsl_fifo_observer fifo_observer;
static struct node_a_lsm6dsl_fifo_status last_fifo_status;
static bool have_fifo_status;
static volatile bool binary_streaming;
static bool first_valid_sample_pending = true;

static bool fifo_status_changed(
	const struct node_a_lsm6dsl_fifo_status *first,
	const struct node_a_lsm6dsl_fifo_status *second)
{
	return (first->status1_raw != second->status1_raw) ||
		(first->status2_raw != second->status2_raw) ||
		(first->unread_words != second->unread_words) ||
		(first->watermark != second->watermark) ||
		(first->overrun != second->overrun) ||
		(first->full != second->full) ||
		(first->empty != second->empty);
}

static void data_ready_handler(const struct device *dev,
			       const struct sensor_trigger *trigger)
{
	struct node_a_imu_sample sample = {0};
	int rc;

	ARG_UNUSED(dev);
	ARG_UNUSED(trigger);

	/* The GPIO callback captured this event's monotonic uptime ticks before the
	 * LSM6DSL driver deferred sample I/O to its global work queue.
	 */
	if (!node_a_drdy_timestamp_take(&drdy_timestamp,
					&sample.timestamp_us)) {
		if (!binary_streaming) {
			printk("Node %s: data-ready event missing ISR timestamp\n",
			       KINEIMU_NODE_LABEL);
		}
		return;
	}

	rc = node_a_lsm6dsl_read_raw(&imu_i2c, i2c_burst_read_dt, &sample);
	if (rc < 0) {
		if (!binary_streaming) {
			printk("Node %s: data-ready sample read failed rc=%d\n",
			       KINEIMU_NODE_LABEL, rc);
		}
		return;
	}

	struct node_a_lsm6dsl_fifo_status fifo_status;
	uint32_t overruns_before = fifo_observer.sensor_fifo_overruns;

	rc = node_a_lsm6dsl_read_fifo_status(
		&imu_i2c, i2c_burst_read_dt, &fifo_status);
	if (rc < 0) {
		/* FIFO diagnostics must not turn a coherent direct-register sample into
		 * a dropped sample. The status read error remains visible on the CDC
		 * console for the later transport/error accounting slice.
		 */
		if (!binary_streaming) {
			printk("Node %s: sensor FIFO status read failed rc=%d\n",
			       KINEIMU_NODE_LABEL, rc);
		}
	} else {
		node_a_lsm6dsl_fifo_observe(&fifo_observer, &fifo_status);
		if (!have_fifo_status ||
		    fifo_status_changed(&fifo_status, &last_fifo_status) ||
		    (fifo_observer.sensor_fifo_overruns != overruns_before)) {
			if (!binary_streaming) {
				printk("Node %s: sensor FIFO status FIFO_STATUS1=0x%02x "
				       "FIFO_STATUS2=0x%02x unread_words=%u watermark=%d "
				       "overrun=%d full=%d empty=%d overrun_count=%u "
				       "saturated=%d\n", KINEIMU_NODE_LABEL,
				       fifo_status.status1_raw, fifo_status.status2_raw,
				       fifo_status.unread_words, fifo_status.watermark,
				       fifo_status.overrun, fifo_status.full, fifo_status.empty,
				       fifo_observer.sensor_fifo_overruns,
				       fifo_observer.counters_saturated);
			}
			last_fifo_status = fifo_status;
			have_fifo_status = true;
		}
	}

	if (!node_a_imu_startup_sample_should_publish(
			&first_valid_sample_pending)) {
		return;
	}

	sample.clock_epoch = stream_counters.clock_epoch;
	sample.sample_sequence =
		node_a_counters_take_sample(&stream_counters);

	/* Drop the newest sample when the fixed queue is full. Its already-issued
	 * sequence makes the loss visible to the later packet/host sequence audit.
	 */
	node_a_sample_queue_put(&sample_queue, &sample);
}

static void node_a_usb_write(const uint8_t *buffer, size_t size)
{
	for (size_t index = 0U; index < size; ++index) {
		uart_poll_out(console, buffer[index]);
	}
}

int main(void)
{
	struct node_a_imu_registers registers;
	uint32_t dtr = 0;
	int ret;

	/* USB CDC drops early console output before the host opens the port. The
	 * bring-up probe waits so its one-shot configuration audit is observable.
	 */
	while (!dtr) {
		uart_line_ctrl_get(console, UART_LINE_CTRL_DTR, &dtr);
		k_sleep(K_MSEC(100));
	}

	const uint32_t ficr_deviceid0 =
		nrf_ficr_deviceid_get(NRF_FICR, 0U);
	const uint32_t ficr_deviceid1 =
		nrf_ficr_deviceid_get(NRF_FICR, 1U);
	const uint64_t hardware_device_id =
		node_a_ficr_device_id_from_words(ficr_deviceid0, ficr_deviceid1);
	printk("Node %s: nRF52840 FICR DEVICEID[0]=0x%08x "
	       "DEVICEID[1]=0x%08x hardware_device_id=0x%08x%08x\n",
	       KINEIMU_NODE_LABEL, ficr_deviceid0, ficr_deviceid1,
	       (uint32_t)(hardware_device_id >> 32),
	       (uint32_t)hardware_device_id);

	k_sleep(IMU_POWER_UP_DELAY);
	ret = device_init(imu);
	printk("KineIMU Shoulder Node %s: IMU init rc=%d ready=%d\n",
	       KINEIMU_NODE_LABEL, ret, device_is_ready(imu));
	if ((ret < 0) || !device_is_ready(imu)) {
		return ret;
	}

	ret = node_a_drdy_timestamp_attach(&drdy_timestamp, &imu_drdy_gpio);
	if (ret < 0) {
		printk("Node %s: data-ready timestamp setup failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}
	node_a_counters_start(&stream_counters, 0U);
	node_a_sample_queue_init(&sample_queue);
	node_a_lsm6dsl_fifo_observer_init(&fifo_observer);

	ret = node_a_imu_configure(imu, data_ready_handler);
	if (ret < 0) {
		printk("Node %s: IMU acquisition setup failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}

	ret = i2c_reg_read_byte_dt(&imu_i2c, LSM6DS3TR_C_REG_WHO_AM_I,
				   &registers.who_am_i);
	if (ret == 0) {
		ret = i2c_reg_read_byte_dt(&imu_i2c,
					   LSM6DS3TR_C_REG_INT1_CTRL,
					   &registers.int1_ctrl);
	}
	if (ret == 0) {
		ret = i2c_reg_read_byte_dt(&imu_i2c,
					   LSM6DS3TR_C_REG_CTRL1_XL,
					   &registers.ctrl1_xl);
	}
	if (ret == 0) {
		ret = i2c_reg_read_byte_dt(&imu_i2c,
					   LSM6DS3TR_C_REG_CTRL2_G,
					   &registers.ctrl2_g);
	}
	if (ret < 0) {
		printk("Node %s: IMU register audit read failed rc=%d\n",
		       KINEIMU_NODE_LABEL, ret);
		return ret;
	}

	printk("Node %s: IMU registers WHO_AM_I=0x%02x INT1_CTRL=0x%02x "
	       "CTRL1_XL=0x%02x CTRL2_G=0x%02x match=%d\n",
	       KINEIMU_NODE_LABEL, registers.who_am_i, registers.int1_ctrl,
	       registers.ctrl1_xl,
	       registers.ctrl2_g,
	       node_a_imu_registers_match_config(&registers));
	if (!node_a_imu_registers_match_config(&registers)) {
		return -EIO;
	}

	printk("Node %s: data-ready acquisition armed at 104 Hz, +/-4 g, +/-500 dps\n",
	       KINEIMU_NODE_LABEL);
	printk("Node %s: v1 USB packet stream node_id=%u batch_max=%u\n",
	       KINEIMU_NODE_LABEL, NODE_A_PACKET_NODE_ID,
	       NODE_A_PACKET_MAX_SAMPLES);
	printk("Node %s: first valid startup DRDY frame drained before sequence zero\n",
	       KINEIMU_NODE_LABEL);
	binary_streaming = true;

	bool have_previous_sample = false;
	uint32_t previous_sample_sequence = 0U;
	while (true) {
		struct node_a_imu_sample samples[NODE_A_PACKET_BATCH_SIZE];
		uint8_t encoded[NODE_A_PACKET_MAX_SIZE];
		size_t sample_count = 1U;
		size_t encoded_size = 0U;
		uint16_t packet_flags;
		int encode_rc;

		if (!node_a_sample_queue_get(&sample_queue, &samples[0], K_FOREVER)) {
			continue;
		}
		while (sample_count < NODE_A_PACKET_BATCH_SIZE &&
		       node_a_sample_queue_get(&sample_queue,
						&samples[sample_count],
						NODE_A_PACKET_GATHER_TIMEOUT)) {
			sample_count++;
		}

		packet_flags = node_a_lsm6dsl_fifo_take_packet_flags(&fifo_observer) |
			node_a_sample_queue_take_packet_flags(&sample_queue);
		if (node_a_packet_samples_have_discontinuity(
				samples, sample_count, have_previous_sample,
				previous_sample_sequence)) {
			packet_flags |= NODE_A_PACKET_FLAG_DISCONTINUITY;
		}

		const struct node_a_sample_packet packet = {
			.node_id = NODE_A_PACKET_NODE_ID,
			.packet_sequence = node_a_counters_take_packet(&stream_counters),
			.clock_epoch = samples[0].clock_epoch,
			.flags = packet_flags,
			.samples = samples,
			.sample_count = sample_count,
		};
		encode_rc = node_a_packet_encode(&packet, encoded,
						sizeof(encoded), &encoded_size);
		if (encode_rc < 0) {
			/* A valid queue item should always satisfy the packet contract. Do
			 * not append text after binary streaming has started if that invariant
			 * is ever violated.
			 */
			return encode_rc;
		}
		node_a_usb_write(encoded, encoded_size);
		have_previous_sample = true;
		previous_sample_sequence =
			samples[sample_count - 1U].sample_sequence;
	}

	return 0;
}
