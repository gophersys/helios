/**
 * @file main.c
 * @brief BQ35100 Fuel Gauge Sample Application
 *
 * Copyright (c) 2024 CoreKinect Inc.
 *
 * Demonstrates all BQ35100 driver capabilities:
 * - Sensor API (sample_fetch / channel_get)
 * - Gauge start/stop lifecycle
 * - ALERT interrupt handling
 * - Device identification
 * - Periodic measurement polling
 */

#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <corekinect/gauges/bq35100/bq35100.h>

LOG_MODULE_REGISTER(bq35100_sample, LOG_LEVEL_INF);

static const struct device *gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));

static volatile bool alert_fired;

static void alert_handler(const struct device *dev, const struct sensor_trigger *trig)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(trig);

	alert_fired = true;
	LOG_INF("ALERT interrupt received");
}

static void print_device_info(void)
{
	uint16_t devtype, fw_ver, hw_ver, chem_id, cs;

	bq35100_control_read(gauge, BQ35100_CNTL_DEVICE_TYPE, &devtype);
	bq35100_control_read(gauge, BQ35100_CNTL_FW_VERSION, &fw_ver);
	bq35100_control_read(gauge, BQ35100_CNTL_HW_VERSION, &hw_ver);
	bq35100_control_read(gauge, BQ35100_CNTL_CHEM_ID, &chem_id);
	bq35100_get_control_status(gauge, &cs);

	printk("\n=== BQ35100 Device Information ===\n");
	printk("  Device Type:   0x%04X %s\n", devtype,
	       devtype == BQ35100_DEVICE_TYPE ? "(BQ35100)" : "(unknown)");
	printk("  FW Version:    0x%04X\n", fw_ver);
	printk("  HW Version:    0x%04X\n", hw_ver);
	printk("  Chemistry ID:  0x%04X\n", chem_id);
	printk("  CONTROL_STATUS: 0x%04X\n", cs);
	printk("  Security:      %s\n",
	       (cs & BQ35100_CS_SEC_MASK) == BQ35100_CS_SEC_SEALED ? "SEALED" :
	       (cs & BQ35100_CS_SEC_MASK) == BQ35100_CS_SEC_UNSEALED ? "UNSEALED" :
	       "FULL_ACCESS");
	printk("  INITCOMP:      %s\n", (cs & BQ35100_CS_INITCOMP) ? "yes" : "no");
}

static void print_measurements(void)
{
	struct sensor_value val;
	int rc;

	rc = sensor_sample_fetch(gauge);
	if (rc != 0) {
		LOG_ERR("sample_fetch failed: %d", rc);
		return;
	}

	printk("\n--- Measurements ---\n");

	sensor_channel_get(gauge, SENSOR_CHAN_GAUGE_VOLTAGE, &val);
	printk("  Voltage:       %d.%03d V\n", val.val1, val.val2 / 1000);

	sensor_channel_get(gauge, SENSOR_CHAN_GAUGE_AVG_CURRENT, &val);
	printk("  Current:       %d mA\n", val.val1);

	sensor_channel_get(gauge, SENSOR_CHAN_GAUGE_TEMP, &val);
	printk("  Ext Temp:      %d.%02d C (NTC)%s\n",
	       val.val1, (val.val2 < 0 ? -val.val2 : val.val2) / 10000,
	       (val.val1 < -30) ? " [no NTC?]" : "");

	sensor_channel_get(gauge, (enum sensor_channel)SENSOR_CHAN_BQ35100_INTERNAL_TEMP, &val);
	printk("  Die Temp:      %d.%02d C\n", val.val1, val.val2 / 10000);

	sensor_channel_get(gauge, (enum sensor_channel)SENSOR_CHAN_BQ35100_SOH, &val);
	printk("  SOH:           %d %%\n", val.val1);

	sensor_channel_get(gauge, SENSOR_CHAN_GAUGE_REMAINING_CHARGE_CAPACITY, &val);
	printk("  Accum Cap:     %d.%06d Ah\n", val.val1, val.val2);

	sensor_channel_get(gauge, (enum sensor_channel)SENSOR_CHAN_BQ35100_IMPEDANCE, &val);
	printk("  Impedance:     %d mohm\n", val.val1);

	sensor_channel_get(gauge, (enum sensor_channel)SENSOR_CHAN_BQ35100_DESIGN_CAP, &val);
	printk("  Design Cap:    %d mAh\n", val.val1);

	sensor_channel_get(gauge, (enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_STATUS, &val);
	uint8_t bstat = (uint8_t)val.val1;
	printk("  BattStatus:    0x%02X [GA=%d DSG=%d ALERT=%d]\n",
	       bstat, !!(bstat & BQ35100_BSTAT_DSG), !!(bstat & BQ35100_BSTAT_DSG),
	       !!(bstat & BQ35100_BSTAT_ALERT));

	sensor_channel_get(gauge, (enum sensor_channel)SENSOR_CHAN_BQ35100_CONTROL_STATUS, &val);
	uint16_t cs = (uint16_t)val.val1;
	printk("  CtrlStatus:    0x%04X [GA=%d G_DONE=%d]\n",
	       cs, !!(cs & BQ35100_CS_GA), !!(cs & BQ35100_CS_G_DONE));
}

int main(void)
{
	printk("\n\n========================================\n");
	printk("  BQ35100 Fuel Gauge Sample Application\n");
	printk("========================================\n");

	if (!device_is_ready(gauge)) {
		LOG_ERR("BQ35100 device not ready");
		return -1;
	}

	LOG_INF("BQ35100 device ready");

	/* Print device info */
	print_device_info();

	/* Register alert trigger */
	struct sensor_trigger trig = {
		.type = (enum sensor_trigger_type)SENSOR_TRIG_BQ35100_ALERT,
		.chan = SENSOR_CHAN_ALL,
	};

	int rc = sensor_trigger_set(gauge, &trig, alert_handler);
	if (rc == 0) {
		LOG_INF("Alert trigger registered");
	} else {
		LOG_WRN("Alert trigger not available: %d", rc);
	}

	/* Start gauging */
	struct sensor_value dummy = {0};
	sensor_attr_set(gauge, SENSOR_CHAN_ALL,
			(enum sensor_attribute)SENSOR_ATTR_BQ35100_GAUGE_START, &dummy);

	/* Periodic measurement loop */
	printk("\nStarting periodic measurements (every 5s)...\n");
	for (int i = 0; i < 60; i++) {
		print_measurements();

		if (alert_fired) {
			alert_fired = false;
			printk("  ** ALERT was triggered **\n");
		}

		k_sleep(K_SECONDS(5));
	}

	/* Stop gauging */
	sensor_attr_set(gauge, SENSOR_CHAN_ALL,
			(enum sensor_attribute)SENSOR_ATTR_BQ35100_GAUGE_STOP, &dummy);

	printk("\nSample complete. Use shell commands for interactive control.\n");
	return 0;
}
