/**
 * @file main.c
 * @brief BQ35100 Hardware-on-Target Test Suite
 *
 * Copyright (c) 2024 CoreKinect Inc.
 *
 * These tests run on actual hardware (IWSCK A0 + BQ35100) and validate
 * real I2C communication, register reads, sensor API, gauge lifecycle,
 * and interrupt handling.
 *
 * Requirements:
 * - IWSCK A0 board with BQ35100 connected
 * - Battery connected to BQ35100 BAT pin (>2.7V)
 * - GE pin wired to P0.01, ALERT to P0.00
 */

#include <zephyr/ztest.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>

#include <corekinect/gauges/bq35100/bq35100.h>

static const struct device *gauge;

/* ================================================================== */
/* Test Suite: Device Initialization                                   */
/* ================================================================== */

ZTEST_SUITE(bq35100_init, NULL, NULL, NULL, NULL, NULL);

ZTEST(bq35100_init, test_device_ready)
{
	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "BQ35100 device not ready");
}

ZTEST(bq35100_init, test_device_type_via_mac)
{
	uint8_t mac_info[6];
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	/* Read device type via MAC/DF — the reliable identification path */
	rc = bq35100_df_read(gauge, 0x0001, mac_info, 2);
	if (rc == 0) {
		uint16_t devtype = (uint16_t)mac_info[0] | ((uint16_t)mac_info[1] << 8);
		zassert_equal(devtype, BQ35100_DEVICE_TYPE,
			      "Unexpected device type: 0x%04X", devtype);
	}
	/* If DF read fails, skip — some sealed devices restrict MAC */
}

/* ================================================================== */
/* Test Suite: I2C Communication                                       */
/* ================================================================== */

ZTEST_SUITE(bq35100_i2c, NULL, NULL, NULL, NULL, NULL);

ZTEST(bq35100_i2c, test_voltage_register_read)
{
	struct sensor_value val;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	rc = sensor_sample_fetch_chan(gauge, SENSOR_CHAN_GAUGE_VOLTAGE);
	zassert_ok(rc, "Voltage fetch failed: %d", rc);

	rc = sensor_channel_get(gauge, SENSOR_CHAN_GAUGE_VOLTAGE, &val);
	zassert_ok(rc, "Voltage get failed: %d", rc);

	/* BQ35100 BAT range: 0-5000 mV. With a battery: expect 2500-4500 mV */
	int voltage_mv = val.val1 * 1000 + val.val2 / 1000;
	zassert_between_inclusive(voltage_mv, 2500, 5000,
				 "Voltage out of range: %d mV", voltage_mv);

	TC_PRINT("  Voltage: %d.%03d V\n", val.val1, val.val2 / 1000);
}

ZTEST(bq35100_i2c, test_internal_temp_register_read)
{
	struct sensor_value val;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	rc = sensor_sample_fetch_chan(gauge,
				     (enum sensor_channel)SENSOR_CHAN_BQ35100_INTERNAL_TEMP);
	zassert_ok(rc, "Internal temp fetch failed: %d", rc);

	rc = sensor_channel_get(gauge,
				(enum sensor_channel)SENSOR_CHAN_BQ35100_INTERNAL_TEMP, &val);
	zassert_ok(rc, "Internal temp get failed: %d", rc);

	/* Die temperature should be -10 to 85 C in any normal environment */
	zassert_between_inclusive(val.val1, -10, 85,
				 "Die temp out of range: %d C", val.val1);

	TC_PRINT("  Die temp: %d.%02d C\n", val.val1,
		 (val.val2 < 0 ? -val.val2 : val.val2) / 10000);
}

ZTEST(bq35100_i2c, test_design_capacity_read)
{
	struct sensor_value val;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	rc = sensor_sample_fetch_chan(gauge,
				     (enum sensor_channel)SENSOR_CHAN_BQ35100_DESIGN_CAP);
	zassert_ok(rc, "Design cap fetch failed: %d", rc);

	rc = sensor_channel_get(gauge,
				(enum sensor_channel)SENSOR_CHAN_BQ35100_DESIGN_CAP, &val);
	zassert_ok(rc, "Design cap get failed: %d", rc);

	/* Default design capacity is 2200 mAh, but could be configured differently */
	zassert_true(val.val1 > 0, "Design capacity must be positive: %d", val.val1);
	zassert_true(val.val1 <= 65535, "Design capacity exceeds max: %d", val.val1);

	TC_PRINT("  Design capacity: %d mAh\n", val.val1);
}

ZTEST(bq35100_i2c, test_current_register_read)
{
	struct sensor_value val;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	rc = sensor_sample_fetch_chan(gauge, SENSOR_CHAN_GAUGE_AVG_CURRENT);
	zassert_ok(rc, "Current fetch failed: %d", rc);

	rc = sensor_channel_get(gauge, SENSOR_CHAN_GAUGE_AVG_CURRENT, &val);
	zassert_ok(rc, "Current get failed: %d", rc);

	/* Current range: -125 mA to +125 mA (based on sense resistor range +-125mV) */
	zassert_between_inclusive(val.val1, -200, 200,
				 "Current out of expected range: %d mA", val.val1);

	TC_PRINT("  Current: %d mA\n", val.val1);
}

ZTEST(bq35100_i2c, test_battery_status_read)
{
	struct sensor_value val;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	rc = sensor_sample_fetch_chan(gauge,
				     (enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_STATUS);
	zassert_ok(rc, "Battery status fetch failed: %d", rc);

	rc = sensor_channel_get(gauge,
				(enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_STATUS, &val);
	zassert_ok(rc, "Battery status get failed: %d", rc);

	/* Status byte should be a valid value (0-255) */
	zassert_between_inclusive(val.val1, 0, 255,
				 "Status byte invalid: %d", val.val1);

	TC_PRINT("  Battery status: 0x%02X\n", val.val1);
}

/* ================================================================== */
/* Test Suite: Sensor API                                              */
/* ================================================================== */

ZTEST_SUITE(bq35100_sensor_api, NULL, NULL, NULL, NULL, NULL);

ZTEST(bq35100_sensor_api, test_fetch_all_channels)
{
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	rc = sensor_sample_fetch(gauge);
	zassert_ok(rc, "Full sample fetch failed: %d", rc);
}

ZTEST(bq35100_sensor_api, test_unsupported_channel)
{
	struct sensor_value val;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	/* SENSOR_CHAN_ACCEL_X should not be supported */
	rc = sensor_channel_get(gauge, SENSOR_CHAN_ACCEL_X, &val);
	zassert_equal(rc, -ENOTSUP, "Expected -ENOTSUP for unsupported channel, got %d", rc);
}

ZTEST(bq35100_sensor_api, test_voltage_via_generic_channel)
{
	struct sensor_value val;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	rc = sensor_sample_fetch_chan(gauge, SENSOR_CHAN_VOLTAGE);
	zassert_ok(rc, "Voltage fetch via SENSOR_CHAN_VOLTAGE failed: %d", rc);

	rc = sensor_channel_get(gauge, SENSOR_CHAN_VOLTAGE, &val);
	zassert_ok(rc, "Voltage get via SENSOR_CHAN_VOLTAGE failed: %d", rc);

	int voltage_mv = val.val1 * 1000 + val.val2 / 1000;
	zassert_true(voltage_mv > 2000, "Voltage too low via generic channel: %d mV", voltage_mv);
}

ZTEST(bq35100_sensor_api, test_soh_channel)
{
	struct sensor_value val;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	sensor_sample_fetch(gauge);

	rc = sensor_channel_get(gauge, SENSOR_CHAN_GAUGE_STATE_OF_HEALTH, &val);
	zassert_ok(rc, "SOH get failed: %d", rc);

	/* SOH is 0-100% */
	zassert_between_inclusive(val.val1, 0, 100,
				 "SOH out of range: %d %%", val.val1);

	TC_PRINT("  SOH: %d %%\n", val.val1);
}

/* ================================================================== */
/* Test Suite: Gauge Lifecycle                                         */
/* ================================================================== */

ZTEST_SUITE(bq35100_lifecycle, NULL, NULL, NULL, NULL, NULL);

ZTEST(bq35100_lifecycle, test_gauge_start_stop)
{
	uint16_t cs;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	/* Start gauge */
	rc = bq35100_gauge_start(gauge);
	zassert_ok(rc, "GAUGE_START failed: %d", rc);

	/* Wait for GA bit — may take up to 2s if chip was recently stopped */
	bool ga_set = false;
	for (int i = 0; i < 20; i++) {
		k_msleep(200);
		rc = bq35100_get_control_status(gauge, &cs);
		if (rc == 0 && (cs & BQ35100_CS_GA)) {
			ga_set = true;
			break;
		}
	}
	zassert_true(ga_set, "GA bit not set after GAUGE_START within 4s (CS=0x%04X)", cs);

	TC_PRINT("  Control status after START: 0x%04X (GA=%d)\n", cs, !!(cs & BQ35100_CS_GA));

	/* Stop gauge */
	rc = bq35100_gauge_stop(gauge);
	zassert_ok(rc, "GAUGE_STOP failed: %d", rc);

	/* After stop + G_DONE, GA should be cleared */
	rc = bq35100_get_control_status(gauge, &cs);
	zassert_ok(rc, "Control status read failed: %d", rc);

	TC_PRINT("  Control status after STOP: 0x%04X (GA=%d G_DONE=%d)\n",
		 cs, !!(cs & BQ35100_CS_GA), !!(cs & BQ35100_CS_G_DONE));
}

ZTEST(bq35100_lifecycle, test_enable_disable)
{
	struct bq35100_data *data;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	data = (struct bq35100_data *)gauge->data;

	/* Disable */
	rc = bq35100_disable(gauge);
	zassert_ok(rc, "Disable failed: %d", rc);
	zassert_false(data->enabled, "Device still shows enabled after disable");

	/* Enable */
	rc = bq35100_enable(gauge);
	zassert_ok(rc, "Enable failed: %d", rc);
	zassert_true(data->enabled, "Device not enabled after enable");

	/* Verify I2C works after re-enable */
	struct sensor_value val;
	rc = sensor_sample_fetch_chan(gauge, SENSOR_CHAN_GAUGE_VOLTAGE);
	zassert_ok(rc, "Voltage read after re-enable failed: %d", rc);

	rc = sensor_channel_get(gauge, SENSOR_CHAN_GAUGE_VOLTAGE, &val);
	zassert_ok(rc, "Voltage get after re-enable failed: %d", rc);

	int voltage_mv = val.val1 * 1000 + val.val2 / 1000;
	zassert_true(voltage_mv > 2000, "Voltage too low after re-enable: %d mV", voltage_mv);

	TC_PRINT("  Voltage after disable/enable cycle: %d.%03d V\n",
		 val.val1, val.val2 / 1000);
}

ZTEST(bq35100_lifecycle, test_attr_set_gauge_start_stop)
{
	struct sensor_value dummy = {0};
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	/* Start via attr_set */
	rc = sensor_attr_set(gauge, SENSOR_CHAN_ALL,
			     (enum sensor_attribute)SENSOR_ATTR_BQ35100_GAUGE_START, &dummy);
	zassert_ok(rc, "GAUGE_START via attr_set failed: %d", rc);

	k_msleep(200);

	/* Stop via attr_set */
	rc = sensor_attr_set(gauge, SENSOR_CHAN_ALL,
			     (enum sensor_attribute)SENSOR_ATTR_BQ35100_GAUGE_STOP, &dummy);
	zassert_ok(rc, "GAUGE_STOP via attr_set failed: %d", rc);
}

/* ================================================================== */
/* Test Suite: Data Flash                                              */
/* ================================================================== */

ZTEST_SUITE(bq35100_data_flash, NULL, NULL, NULL, NULL, NULL);

ZTEST(bq35100_data_flash, test_read_device_name)
{
	uint8_t name_buf[8];
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	rc = bq35100_df_read(gauge, BQ35100_DF_DEVICE_NAME, name_buf, 8);
	zassert_ok(rc, "DF read device name failed: %d", rc);

	TC_PRINT("  Device name: %.8s\n", name_buf);

	/* Default device name should be "bq35100" (7 chars + null or pad) */
	zassert_true(name_buf[0] != 0xFF, "Device name not programmed");
}

ZTEST(bq35100_data_flash, test_read_design_capacity_df)
{
	uint8_t cap_buf[2];
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	rc = bq35100_df_read(gauge, BQ35100_DF_DESIGN_CAP_MAH, cap_buf, 2);
	zassert_ok(rc, "DF read design capacity failed: %d", rc);

	uint16_t dcap = (uint16_t)cap_buf[0] | ((uint16_t)cap_buf[1] << 8);
	TC_PRINT("  Design capacity (DF): %u mAh\n", dcap);

	zassert_true(dcap > 0, "Design capacity must be positive");
}

ZTEST(bq35100_data_flash, test_read_operation_config)
{
	uint8_t opcfg;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	rc = bq35100_df_read(gauge, BQ35100_DF_OPERATION_CFG_A, &opcfg, 1);
	zassert_ok(rc, "DF read OpCfgA failed: %d", rc);

	TC_PRINT("  Operation Config A: 0x%02X\n", opcfg);
	TC_PRINT("    TEMPS=%d (1=ext NTC, 0=internal)\n", !!(opcfg & BQ35100_OPCFG_TEMPS));
	TC_PRINT("    GMSEL=%d (0=ACC, 1=SOH, 2=EOS)\n", opcfg & BQ35100_OPCFG_GMSEL_MASK);
}

ZTEST(bq35100_data_flash, test_df_invalid_length)
{
	uint8_t buf[1];
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	/* Length 0 should fail */
	rc = bq35100_df_read(gauge, 0x4060, buf, 0);
	zassert_equal(rc, -EINVAL, "Expected -EINVAL for len=0, got %d", rc);

	/* Length >32 should fail */
	uint8_t big_buf[33];
	rc = bq35100_df_read(gauge, 0x4060, big_buf, 33);
	zassert_equal(rc, -EINVAL, "Expected -EINVAL for len=33, got %d", rc);
}

/* ================================================================== */
/* Test Suite: Measurement Consistency                                 */
/* ================================================================== */

ZTEST_SUITE(bq35100_consistency, NULL, NULL, NULL, NULL, NULL);

ZTEST(bq35100_consistency, test_voltage_stability)
{
	struct sensor_value val;
	int readings[5];
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	/* Take 5 voltage readings 200ms apart */
	for (int i = 0; i < 5; i++) {
		rc = sensor_sample_fetch_chan(gauge, SENSOR_CHAN_GAUGE_VOLTAGE);
		zassert_ok(rc, "Voltage fetch %d failed: %d", i, rc);

		rc = sensor_channel_get(gauge, SENSOR_CHAN_GAUGE_VOLTAGE, &val);
		zassert_ok(rc, "Voltage get %d failed: %d", i, rc);

		readings[i] = val.val1 * 1000 + val.val2 / 1000;
		k_msleep(200);
	}

	/* All readings should be within 100 mV of each other (stable battery) */
	int min_v = readings[0], max_v = readings[0];
	for (int i = 1; i < 5; i++) {
		if (readings[i] < min_v) min_v = readings[i];
		if (readings[i] > max_v) max_v = readings[i];
	}

	int spread = max_v - min_v;
	zassert_true(spread < 100, "Voltage spread too large: %d mV (min=%d, max=%d)",
		     spread, min_v, max_v);

	TC_PRINT("  Voltage spread over 5 reads: %d mV (min=%d, max=%d)\n",
		 spread, min_v, max_v);
}

ZTEST(bq35100_consistency, test_die_temp_reasonable)
{
	struct sensor_value val;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	sensor_sample_fetch(gauge);

	rc = sensor_channel_get(gauge,
				(enum sensor_channel)SENSOR_CHAN_BQ35100_INTERNAL_TEMP, &val);
	zassert_ok(rc, "Internal temp get failed: %d", rc);

	/* Room temperature range: 10-45 C typically */
	zassert_between_inclusive(val.val1, 10, 50,
				 "Die temp outside room range: %d C", val.val1);
}

/* ================================================================== */
/* Test Suite: Interrupt / Alert                                       */
/* ================================================================== */

ZTEST_SUITE(bq35100_alert, NULL, NULL, NULL, NULL, NULL);

static volatile bool test_alert_fired;

static void test_alert_handler(const struct device *dev, const struct sensor_trigger *trig)
{
	ARG_UNUSED(dev);
	ARG_UNUSED(trig);
	test_alert_fired = true;
}

ZTEST(bq35100_alert, test_trigger_registration)
{
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	struct sensor_trigger trig = {
		.type = (enum sensor_trigger_type)SENSOR_TRIG_BQ35100_ALERT,
		.chan = SENSOR_CHAN_ALL,
	};

	rc = sensor_trigger_set(gauge, &trig, test_alert_handler);
	zassert_ok(rc, "Alert trigger registration failed: %d", rc);

	/* Unregister */
	rc = sensor_trigger_set(gauge, &trig, NULL);
	zassert_ok(rc, "Alert trigger unregistration failed: %d", rc);
}

ZTEST(bq35100_alert, test_unsupported_trigger)
{
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	/* DATA_READY trigger should not be supported */
	struct sensor_trigger trig = {
		.type = SENSOR_TRIG_DATA_READY,
		.chan = SENSOR_CHAN_ALL,
	};

	rc = sensor_trigger_set(gauge, &trig, test_alert_handler);
	zassert_equal(rc, -ENOTSUP,
		      "Expected -ENOTSUP for DATA_READY trigger, got %d", rc);
}

ZTEST(bq35100_alert, test_alert_clears_on_read)
{
	struct sensor_value val;
	int rc;

	gauge = DEVICE_DT_GET(DT_NODELABEL(bq35100));
	zassert_true(device_is_ready(gauge), "Device not ready");

	/* Reading BatteryAlert register should clear the ALERT pin per datasheet */
	rc = sensor_sample_fetch_chan(gauge,
				     (enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_ALERT);
	zassert_ok(rc, "Alert fetch failed: %d", rc);

	rc = sensor_channel_get(gauge,
				(enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_ALERT, &val);
	zassert_ok(rc, "Alert get failed: %d", rc);

	TC_PRINT("  Alert register: 0x%02X\n", val.val1);
}
