/**
 * @file bq35100.c
 * @brief BQ35100 Primary Battery Fuel Gauge Driver Implementation
 *
 * Copyright (c) 2024 CoreKinect Inc.
 *
 * Implements the Zephyr sensor driver for the Texas Instruments BQ35100
 * primary battery fuel gauge with impedance tracking capability.
 */

#define DT_DRV_COMPAT ti_bq35100

#include "bq35100.h"

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#ifdef CONFIG_CK_BQ35100_SHELL
#include <zephyr/shell/shell.h>
#endif

LOG_MODULE_REGISTER(bq35100, CONFIG_CK_BQ35100_LOG_LEVEL);

/* ------------------------------------------------------------------ */
/* Low-level I2C helpers                                               */
/* ------------------------------------------------------------------ */

static int bq35100_read_reg8(const struct device *dev, uint8_t reg, uint8_t *val)
{
	const struct bq35100_config *cfg = dev->config;

	return i2c_burst_read_dt(&cfg->i2c, reg, val, 1);
}

static int bq35100_read_reg16(const struct device *dev, uint8_t reg, uint16_t *val)
{
	const struct bq35100_config *cfg = dev->config;
	uint8_t buf[2];
	int rc;

	rc = i2c_burst_read_dt(&cfg->i2c, reg, buf, 2);
	if (rc == 0) {
		*val = (uint16_t)buf[0] | ((uint16_t)buf[1] << 8);
	}
	return rc;
}

static int bq35100_read_reg32(const struct device *dev, uint8_t reg, uint32_t *val)
{
	const struct bq35100_config *cfg = dev->config;
	uint8_t buf[4];
	int rc;

	rc = i2c_burst_read_dt(&cfg->i2c, reg, buf, 4);
	if (rc == 0) {
		*val = (uint32_t)buf[0] | ((uint32_t)buf[1] << 8) |
		       ((uint32_t)buf[2] << 16) | ((uint32_t)buf[3] << 24);
	}
	return rc;
}

static int bq35100_write_reg16(const struct device *dev, uint8_t reg, uint16_t val)
{
	const struct bq35100_config *cfg = dev->config;
	uint8_t buf[3] = { reg, val & 0xFF, val >> 8 };

	return i2c_write_dt(&cfg->i2c, buf, 3);
}

/* ------------------------------------------------------------------ */
/* Control subcommand interface                                        */
/* ------------------------------------------------------------------ */

int bq35100_control_cmd(const struct device *dev, uint16_t subcmd)
{
	return bq35100_write_reg16(dev, BQ35100_REG_CONTROL, subcmd);
}

int bq35100_control_read(const struct device *dev, uint16_t subcmd, uint16_t *result)
{
	int rc;

	rc = bq35100_control_cmd(dev, subcmd);
	if (rc != 0) {
		return rc;
	}

	k_msleep(10);
	return bq35100_read_reg16(dev, BQ35100_REG_CONTROL, result);
}

int bq35100_get_control_status(const struct device *dev, uint16_t *status)
{
	return bq35100_control_read(dev, BQ35100_CNTL_CONTROL_STATUS, status);
}

/* ------------------------------------------------------------------ */
/* GE (Gauge Enable) pin control                                       */
/* ------------------------------------------------------------------ */

int bq35100_enable(const struct device *dev)
{
	const struct bq35100_config *cfg = dev->config;
	struct bq35100_data *data = dev->data;
	int rc;

	if (data->enabled) {
		return 0;
	}

	rc = gpio_pin_set_dt(&cfg->enable_gpio, 1);
	if (rc != 0) {
		LOG_ERR("Failed to assert GE pin: %d", rc);
		return rc;
	}

	data->enabled = true;
	k_msleep(cfg->power_up_delay_ms);

	LOG_DBG("GE enabled, waited %u ms", cfg->power_up_delay_ms);
	return 0;
}

int bq35100_disable(const struct device *dev)
{
	const struct bq35100_config *cfg = dev->config;
	struct bq35100_data *data = dev->data;
	int rc;

	if (!data->enabled) {
		return 0;
	}

	rc = gpio_pin_set_dt(&cfg->enable_gpio, 0);
	if (rc != 0) {
		LOG_ERR("Failed to deassert GE pin: %d", rc);
		return rc;
	}

	data->enabled = false;
	data->gauge_active = false;

	LOG_DBG("GE disabled");
	return 0;
}

/* ------------------------------------------------------------------ */
/* Gauge Start / Stop                                                  */
/* ------------------------------------------------------------------ */

int bq35100_gauge_start(const struct device *dev)
{
	struct bq35100_data *data = dev->data;
	int rc;

	rc = bq35100_enable(dev);
	if (rc != 0) {
		return rc;
	}

	rc = bq35100_control_cmd(dev, BQ35100_CNTL_GAUGE_START);
	if (rc != 0) {
		LOG_ERR("GAUGE_START failed: %d", rc);
		return rc;
	}

	data->gauge_active = true;
	LOG_INF("Gauge started (ACTIVE mode)");
	return 0;
}

int bq35100_gauge_stop(const struct device *dev)
{
	struct bq35100_data *data = dev->data;
	uint16_t cs;
	int rc;

	rc = bq35100_control_cmd(dev, BQ35100_CNTL_GAUGE_STOP);
	if (rc != 0) {
		LOG_ERR("GAUGE_STOP failed: %d", rc);
		return rc;
	}

	/* Wait for G_DONE (up to 5 seconds) */
	for (int i = 0; i < 50; i++) {
		k_msleep(100);
		rc = bq35100_get_control_status(dev, &cs);
		if (rc != 0) {
			continue;
		}
		if (cs & BQ35100_CS_G_DONE) {
			data->gauge_active = false;
			LOG_INF("Gauge stopped (G_DONE set)");
			return 0;
		}
	}

	LOG_WRN("GAUGE_STOP: G_DONE timeout after 5s");
	data->gauge_active = false;
	return 0;
}

/* ------------------------------------------------------------------ */
/* Security: Seal / Unseal                                             */
/* ------------------------------------------------------------------ */

int bq35100_unseal(const struct device *dev)
{
	int rc;
	uint16_t cs;

	/* Send two-part unseal key with no intervening writes */
	rc = bq35100_control_cmd(dev, BQ35100_UNSEAL_KEY1);
	if (rc != 0) {
		return rc;
	}

	k_msleep(5);

	rc = bq35100_control_cmd(dev, BQ35100_UNSEAL_KEY2);
	if (rc != 0) {
		return rc;
	}

	k_msleep(50);

	/* Verify we are unsealed */
	rc = bq35100_get_control_status(dev, &cs);
	if (rc != 0) {
		return rc;
	}

	if ((cs & BQ35100_CS_SEC_MASK) == BQ35100_CS_SEC_UNSEALED) {
		LOG_INF("Device unsealed");
		return 0;
	}

	LOG_ERR("Unseal failed, CONTROL_STATUS=0x%04X", cs);
	return -EACCES;
}

int bq35100_seal(const struct device *dev)
{
	return bq35100_control_cmd(dev, BQ35100_CNTL_SEALED);
}

/* ------------------------------------------------------------------ */
/* New Battery                                                         */
/* ------------------------------------------------------------------ */

int bq35100_new_battery(const struct device *dev)
{
	return bq35100_control_cmd(dev, BQ35100_CNTL_NEW_BATTERY);
}

/* ------------------------------------------------------------------ */
/* Data Flash Access                                                   */
/* ------------------------------------------------------------------ */

int bq35100_df_read(const struct device *dev, uint16_t addr, uint8_t *buf, uint8_t len)
{
	const struct bq35100_config *cfg = dev->config;
	uint8_t mac_buf[36]; /* 2 addr + 32 data + 1 checksum + 1 length */
	int rc;

	if (len == 0 || len > 32) {
		return -EINVAL;
	}

	/* Write DF address to MAC (0x3E/0x3F) */
	rc = bq35100_write_reg16(dev, BQ35100_REG_MAC, addr);
	if (rc != 0) {
		return rc;
	}

	k_msleep(10);

	/* Read back MAC address + data + checksum + length (36 bytes from 0x3E) */
	rc = i2c_burst_read_dt(&cfg->i2c, BQ35100_REG_MAC, mac_buf, 4 + len);
	if (rc != 0) {
		return rc;
	}

	/* Verify address echo */
	uint16_t echo_addr = (uint16_t)mac_buf[0] | ((uint16_t)mac_buf[1] << 8);
	if (echo_addr != addr) {
		LOG_ERR("DF read addr mismatch: expected 0x%04X, got 0x%04X", addr, echo_addr);
		return -EIO;
	}

	memcpy(buf, &mac_buf[2], len);
	return 0;
}

int bq35100_df_write(const struct device *dev, uint16_t addr, const uint8_t *data, uint8_t len)
{
	const struct bq35100_config *cfg = dev->config;
	uint8_t buf[36]; /* reg + 2 addr + 32 data */
	uint8_t checksum;
	int rc;

	if (len == 0 || len > 32) {
		return -EINVAL;
	}

	/* Write address + data to MAC registers */
	buf[0] = BQ35100_REG_MAC;
	buf[1] = addr & 0xFF;
	buf[2] = addr >> 8;
	memcpy(&buf[3], data, len);

	rc = i2c_write_dt(&cfg->i2c, buf, 3 + len);
	if (rc != 0) {
		return rc;
	}

	/* Calculate checksum: complement of (addr_lo + addr_hi + data bytes) */
	checksum = (addr & 0xFF) + (addr >> 8);
	for (uint8_t i = 0; i < len; i++) {
		checksum += data[i];
	}
	checksum = ~checksum;

	/* Write checksum and length to trigger the flash write */
	uint8_t tail[3] = { BQ35100_REG_MAC_DATA_SUM, checksum, (uint8_t)(4 + len) };
	rc = i2c_write_dt(&cfg->i2c, tail, 3);
	if (rc != 0) {
		return rc;
	}

	/* Flash write takes up to 5ms */
	k_msleep(10);

	return 0;
}

/* ------------------------------------------------------------------ */
/* Sensor API: sample_fetch                                            */
/* ------------------------------------------------------------------ */

static int bq35100_ensure_enabled(const struct device *dev)
{
	struct bq35100_data *data = dev->data;

	if (!data->enabled) {
		return bq35100_enable(dev);
	}
	return 0;
}

static int bq35100_sample_fetch(const struct device *dev, enum sensor_channel chan)
{
	struct bq35100_data *data = dev->data;
	int rc;

	rc = bq35100_ensure_enabled(dev);
	if (rc != 0) {
		return rc;
	}

	if (chan == SENSOR_CHAN_ALL || chan == SENSOR_CHAN_GAUGE_VOLTAGE ||
	    chan == SENSOR_CHAN_VOLTAGE) {
		rc = bq35100_read_reg16(dev, BQ35100_REG_VOLTAGE, &data->voltage_mv);
		if (rc != 0) {
			LOG_ERR("Failed to read voltage: %d", rc);
			return rc;
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == SENSOR_CHAN_GAUGE_AVG_CURRENT) {
		rc = bq35100_read_reg16(dev, BQ35100_REG_CURRENT, (uint16_t *)&data->current_ma);
		if (rc != 0) {
			LOG_ERR("Failed to read current: %d", rc);
			return rc;
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == SENSOR_CHAN_GAUGE_TEMP) {
		rc = bq35100_read_reg16(dev, BQ35100_REG_TEMPERATURE, &data->temperature_01k);
		if (rc != 0) {
			LOG_ERR("Failed to read temperature: %d", rc);
			return rc;
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == (enum sensor_channel)SENSOR_CHAN_BQ35100_INTERNAL_TEMP) {
		rc = bq35100_read_reg16(dev, BQ35100_REG_INTERNAL_TEMP, &data->internal_temp_01k);
		if (rc != 0) {
			LOG_DBG("Failed to read internal temp: %d", rc);
			/* Non-fatal: some modes may not have this */
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == (enum sensor_channel)SENSOR_CHAN_BQ35100_SOH) {
		uint16_t soh_raw;
		rc = bq35100_read_reg16(dev, BQ35100_REG_SOH, &soh_raw);
		if (rc == 0) {
			data->soh_pct = soh_raw & 0xFF;
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == SENSOR_CHAN_GAUGE_REMAINING_CHARGE_CAPACITY) {
		rc = bq35100_read_reg32(dev, BQ35100_REG_ACCUMULATED_CAP,
					&data->accumulated_cap_uah);
		if (rc != 0) {
			LOG_DBG("Failed to read accumulated capacity: %d", rc);
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == (enum sensor_channel)SENSOR_CHAN_BQ35100_IMPEDANCE) {
		rc = bq35100_read_reg16(dev, BQ35100_REG_MEASURED_Z, &data->impedance_mohm);
		if (rc != 0) {
			LOG_DBG("Failed to read impedance: %d", rc);
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == (enum sensor_channel)SENSOR_CHAN_BQ35100_SCALED_R) {
		rc = bq35100_read_reg16(dev, BQ35100_REG_SCALED_R, &data->scaled_r_mohm);
		if (rc != 0) {
			LOG_DBG("Failed to read scaled R: %d", rc);
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == (enum sensor_channel)SENSOR_CHAN_BQ35100_DESIGN_CAP) {
		rc = bq35100_read_reg16(dev, BQ35100_REG_DESIGN_CAPACITY, &data->design_cap_mah);
		if (rc != 0) {
			LOG_DBG("Failed to read design capacity: %d", rc);
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == (enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_STATUS) {
		rc = bq35100_read_reg8(dev, BQ35100_REG_BATTERY_STATUS, &data->battery_status);
		if (rc != 0) {
			LOG_DBG("Failed to read battery status: %d", rc);
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == (enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_ALERT) {
		rc = bq35100_read_reg8(dev, BQ35100_REG_BATTERY_ALERT, &data->battery_alert);
		if (rc != 0) {
			LOG_DBG("Failed to read battery alert: %d", rc);
		}
	}

	if (chan == SENSOR_CHAN_ALL || chan == (enum sensor_channel)SENSOR_CHAN_BQ35100_CONTROL_STATUS) {
		rc = bq35100_get_control_status(dev, &data->control_status);
		if (rc != 0) {
			LOG_DBG("Failed to read control status: %d", rc);
		}
	}

	return 0;
}

/* ------------------------------------------------------------------ */
/* Sensor API: channel_get                                             */
/* ------------------------------------------------------------------ */

/**
 * Convert BQ35100 temperature (0.1 K units) to sensor_value in Celsius.
 * Formula: C = (raw * 0.1) - 273.15
 */
static void temp_to_sensor_val(uint16_t raw_01k, struct sensor_value *val)
{
	/* raw is in 0.1 K, convert to Celsius.
	 * centideg_c = raw * 10 - 27315  (in 0.01 C units)
	 * sensor_value: val1 = integer C, val2 = fractional (10^-6 C)
	 */
	int32_t centideg_c = (int32_t)raw_01k * 10 - 27315;

	if (centideg_c >= 0) {
		val->val1 = centideg_c / 100;
		val->val2 = (centideg_c % 100) * 10000;
	} else {
		/* Handle negative: ensure val2 is positive, val1 carries the sign */
		val->val1 = -((-centideg_c) / 100);
		val->val2 = -((-centideg_c) % 100) * 10000;
		if (val->val2 != 0 && val->val1 == 0) {
			/* e.g., -0.15 C: val1=0, val2=-150000 → val1 stays 0, val2 negative */
		}
	}
}

static int bq35100_channel_get(const struct device *dev, enum sensor_channel chan,
			       struct sensor_value *val)
{
	struct bq35100_data *data = dev->data;

	switch ((int)chan) {
	case SENSOR_CHAN_GAUGE_VOLTAGE:
	case SENSOR_CHAN_VOLTAGE:
		/* Voltage in volts: val1 = whole volts, val2 = fractional (uV) */
		val->val1 = data->voltage_mv / 1000;
		val->val2 = (data->voltage_mv % 1000) * 1000;
		break;

	case SENSOR_CHAN_GAUGE_AVG_CURRENT:
	case SENSOR_CHAN_CURRENT:
		/* Current in mA: val1 = whole mA, val2 = 0 (BQ35100 resolution is 1mA) */
		val->val1 = data->current_ma;
		val->val2 = 0;
		break;

	case SENSOR_CHAN_GAUGE_TEMP:
		temp_to_sensor_val(data->temperature_01k, val);
		break;

	case SENSOR_CHAN_GAUGE_REMAINING_CHARGE_CAPACITY:
		/* Return in microamp-hours */
		val->val1 = (int32_t)(data->accumulated_cap_uah / 1000000);
		val->val2 = (int32_t)(data->accumulated_cap_uah % 1000000);
		break;

	case SENSOR_CHAN_GAUGE_STATE_OF_HEALTH:
		val->val1 = data->soh_pct;
		val->val2 = 0;
		break;

	case SENSOR_CHAN_BQ35100_SOH:
		val->val1 = data->soh_pct;
		val->val2 = 0;
		break;

	case SENSOR_CHAN_BQ35100_ACCUMULATED_CAP:
		val->val1 = (int32_t)(data->accumulated_cap_uah >> 16);
		val->val2 = (int32_t)(data->accumulated_cap_uah & 0xFFFF);
		break;

	case SENSOR_CHAN_BQ35100_IMPEDANCE:
		val->val1 = data->impedance_mohm;
		val->val2 = 0;
		break;

	case SENSOR_CHAN_BQ35100_SCALED_R:
		val->val1 = data->scaled_r_mohm;
		val->val2 = 0;
		break;

	case SENSOR_CHAN_BQ35100_INTERNAL_TEMP:
		temp_to_sensor_val(data->internal_temp_01k, val);
		break;

	case SENSOR_CHAN_BQ35100_DESIGN_CAP:
		val->val1 = data->design_cap_mah;
		val->val2 = 0;
		break;

	case SENSOR_CHAN_BQ35100_BATTERY_STATUS:
		val->val1 = data->battery_status;
		val->val2 = 0;
		break;

	case SENSOR_CHAN_BQ35100_BATTERY_ALERT:
		val->val1 = data->battery_alert;
		val->val2 = 0;
		break;

	case SENSOR_CHAN_BQ35100_CONTROL_STATUS:
		val->val1 = data->control_status;
		val->val2 = 0;
		break;

	default:
		return -ENOTSUP;
	}

	return 0;
}

/* ------------------------------------------------------------------ */
/* Sensor API: attr_set                                                */
/* ------------------------------------------------------------------ */

static int bq35100_attr_set(const struct device *dev, enum sensor_channel chan,
			    enum sensor_attribute attr, const struct sensor_value *val)
{
	ARG_UNUSED(chan);
	ARG_UNUSED(val);

	switch ((int)attr) {
	case SENSOR_ATTR_BQ35100_GAUGE_START:
		return bq35100_gauge_start(dev);

	case SENSOR_ATTR_BQ35100_GAUGE_STOP:
		return bq35100_gauge_stop(dev);

	case SENSOR_ATTR_BQ35100_ENABLE:
		return bq35100_enable(dev);

	case SENSOR_ATTR_BQ35100_DISABLE:
		return bq35100_disable(dev);

	case SENSOR_ATTR_BQ35100_UNSEAL:
		return bq35100_unseal(dev);

	case SENSOR_ATTR_BQ35100_SEAL:
		return bq35100_seal(dev);

	case SENSOR_ATTR_BQ35100_NEW_BATTERY:
		return bq35100_new_battery(dev);

	case SENSOR_ATTR_BQ35100_RESET:
		return bq35100_control_cmd(dev, BQ35100_CNTL_RESET);

	default:
		return -ENOTSUP;
	}
}

/* ------------------------------------------------------------------ */
/* Trigger / Interrupt support                                         */
/* ------------------------------------------------------------------ */

#ifdef CONFIG_CK_BQ35100_TRIGGER

static void bq35100_alert_work_handler(struct k_work *work)
{
	struct bq35100_data *data = CONTAINER_OF(work, struct bq35100_data, alert_work);
	const struct device *dev = data->dev;

	if (data->alert_handler != NULL) {
		data->alert_handler(dev, data->alert_trigger);
	}
}

static void bq35100_alert_isr(const struct device *port, struct gpio_callback *cb,
			      gpio_port_pins_t pins)
{
	ARG_UNUSED(port);
	ARG_UNUSED(pins);

	struct bq35100_data *data = CONTAINER_OF(cb, struct bq35100_data, alert_cb);

	k_work_submit(&data->alert_work);
}

static int bq35100_trigger_set(const struct device *dev, const struct sensor_trigger *trig,
			       sensor_trigger_handler_t handler)
{
	struct bq35100_data *data = dev->data;

	if ((int)trig->type != SENSOR_TRIG_BQ35100_ALERT) {
		return -ENOTSUP;
	}

	data->alert_trigger = trig;
	data->alert_handler = handler;

	return 0;
}

static int bq35100_init_trigger(const struct device *dev)
{
	const struct bq35100_config *cfg = dev->config;
	struct bq35100_data *data = dev->data;
	int rc;

	if (!cfg->alert_gpio.port) {
		return 0; /* No alert GPIO configured */
	}

	if (!gpio_is_ready_dt(&cfg->alert_gpio)) {
		LOG_ERR("Alert GPIO not ready");
		return -ENODEV;
	}

	k_work_init(&data->alert_work, bq35100_alert_work_handler);

	rc = gpio_pin_configure_dt(&cfg->alert_gpio, GPIO_INPUT);
	if (rc != 0) {
		LOG_ERR("Failed to configure alert pin: %d", rc);
		return rc;
	}

	rc = gpio_pin_interrupt_configure_dt(&cfg->alert_gpio, GPIO_INT_EDGE_TO_ACTIVE);
	if (rc != 0) {
		LOG_ERR("Failed to configure alert interrupt: %d", rc);
		return rc;
	}

	gpio_init_callback(&data->alert_cb, bq35100_alert_isr, BIT(cfg->alert_gpio.pin));
	rc = gpio_add_callback(cfg->alert_gpio.port, &data->alert_cb);
	if (rc != 0) {
		LOG_ERR("Failed to add alert callback: %d", rc);
		return rc;
	}

	LOG_DBG("Alert interrupt configured");
	return 0;
}

#endif /* CONFIG_CK_BQ35100_TRIGGER */

/* ------------------------------------------------------------------ */
/* Initialization                                                      */
/* ------------------------------------------------------------------ */

static int bq35100_init(const struct device *dev)
{
	const struct bq35100_config *cfg = dev->config;
	struct bq35100_data *data = dev->data;
	uint16_t device_type;
	int rc;

	data->dev = dev;

	/* Check I2C bus */
	if (!i2c_is_ready_dt(&cfg->i2c)) {
		LOG_ERR("I2C bus not ready");
		return -ENODEV;
	}

	/* Configure GE pin */
	if (!gpio_is_ready_dt(&cfg->enable_gpio)) {
		LOG_ERR("Enable GPIO not ready");
		return -ENODEV;
	}

	rc = gpio_pin_configure_dt(&cfg->enable_gpio, GPIO_OUTPUT_INACTIVE);
	if (rc != 0) {
		LOG_ERR("Failed to configure GE pin: %d", rc);
		return rc;
	}

	data->enabled = false;
	data->gauge_active = false;

	/* Power up and verify device identity */
	rc = bq35100_enable(dev);
	if (rc != 0) {
		return rc;
	}

	/* Wait for INITCOMP */
	uint16_t cs;
	for (int i = 0; i < 30; i++) {
		rc = bq35100_get_control_status(dev, &cs);
		if (rc == 0 && (cs & BQ35100_CS_INITCOMP)) {
			break;
		}
		k_msleep(100);
	}

	if (!(cs & BQ35100_CS_INITCOMP)) {
		LOG_WRN("INITCOMP not set after 3s, continuing anyway");
	}

	/* Verify chip presence by reading voltage (reliable, no subcommand timing issues) */
	uint16_t voltage_mv;
	rc = bq35100_read_reg16(dev, BQ35100_REG_VOLTAGE, &voltage_mv);
	if (rc != 0) {
		LOG_ERR("Failed to communicate with BQ35100: %d", rc);
		bq35100_disable(dev);
		return rc;
	}

	/* Read design capacity — should be factory-set */
	bq35100_read_reg16(dev, BQ35100_REG_DESIGN_CAPACITY, &data->design_cap_mah);

	/* Read chip info via MAC for reliable identification.
	 * DEVICE_TYPE via Control() returns CONTROL_STATUS on some firmware revisions.
	 * MAC read is the reliable path per TRM (SLUUBH1C §4.1).
	 */
	uint8_t mac_info[6];
	rc = bq35100_df_read(dev, 0x0001, mac_info, 6);
	if (rc == 0) {
		device_type = (uint16_t)mac_info[0] | ((uint16_t)mac_info[1] << 8);
	} else {
		/* Fallback: try Control() subcommand */
		bq35100_control_read(dev, BQ35100_CNTL_DEVICE_TYPE, &device_type);
	}

	uint16_t fw_ver = 0, hw_ver = 0, chem_id = 0;
	bq35100_control_read(dev, BQ35100_CNTL_FW_VERSION, &fw_ver);
	bq35100_control_read(dev, BQ35100_CNTL_HW_VERSION, &hw_ver);
	bq35100_control_read(dev, BQ35100_CNTL_CHEM_ID, &chem_id);

	LOG_INF("BQ35100 detected: type=0x%04X fw=0x%04X hw=0x%04X chem=0x%04X dcap=%umAh voltage=%umV",
		device_type, fw_ver, hw_ver, chem_id, data->design_cap_mah, voltage_mv);

	/* Clear any pending alerts */
	bq35100_read_reg8(dev, BQ35100_REG_BATTERY_STATUS, &data->battery_status);
	bq35100_read_reg8(dev, BQ35100_REG_BATTERY_ALERT, &data->battery_alert);

#ifdef CONFIG_CK_BQ35100_TRIGGER
	rc = bq35100_init_trigger(dev);
	if (rc != 0) {
		LOG_WRN("Trigger init failed: %d (non-fatal)", rc);
	}
#endif

	/* Leave device enabled after init for immediate use */
	LOG_INF("BQ35100 driver ready (security: %s)",
		(cs & BQ35100_CS_SEC_MASK) == BQ35100_CS_SEC_SEALED ? "sealed" :
		(cs & BQ35100_CS_SEC_MASK) == BQ35100_CS_SEC_UNSEALED ? "unsealed" :
		"full-access");

	return 0;
}

/* ------------------------------------------------------------------ */
/* Shell commands                                                      */
/* ------------------------------------------------------------------ */

#ifdef CONFIG_CK_BQ35100_SHELL

static const struct device *bq35100_shell_dev(void)
{
#if DT_HAS_COMPAT_STATUS_OKAY(ti_bq35100)
	return DEVICE_DT_GET(DT_INST(0, ti_bq35100));
#else
	return NULL;
#endif
}

static int cmd_bq35100_read(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	const struct device *dev = bq35100_shell_dev();
	struct sensor_value val;

	if (!dev || !device_is_ready(dev)) {
		shell_error(sh, "BQ35100 not available");
		return -ENODEV;
	}

	sensor_sample_fetch(dev);

	sensor_channel_get(dev, SENSOR_CHAN_GAUGE_VOLTAGE, &val);
	shell_print(sh, "Voltage:      %d.%03d V", val.val1, val.val2 / 1000);

	sensor_channel_get(dev, SENSOR_CHAN_GAUGE_TEMP, &val);
	shell_print(sh, "Temperature:  %d.%02d C", val.val1, val.val2 / 10000);

	sensor_channel_get(dev, SENSOR_CHAN_GAUGE_AVG_CURRENT, &val);
	shell_print(sh, "Current:      %d mA", val.val1);

	sensor_channel_get(dev, (enum sensor_channel)SENSOR_CHAN_BQ35100_SOH, &val);
	shell_print(sh, "SOH:          %d %%", val.val1);

	sensor_channel_get(dev, SENSOR_CHAN_GAUGE_REMAINING_CHARGE_CAPACITY, &val);
	shell_print(sh, "Accum Cap:    %d.%06d Ah", val.val1, val.val2);

	sensor_channel_get(dev, (enum sensor_channel)SENSOR_CHAN_BQ35100_IMPEDANCE, &val);
	shell_print(sh, "Impedance:    %d mohm", val.val1);

	sensor_channel_get(dev, (enum sensor_channel)SENSOR_CHAN_BQ35100_DESIGN_CAP, &val);
	shell_print(sh, "Design Cap:   %d mAh", val.val1);

	sensor_channel_get(dev, (enum sensor_channel)SENSOR_CHAN_BQ35100_INTERNAL_TEMP, &val);
	shell_print(sh, "Die Temp:     %d.%02d C", val.val1, val.val2 / 10000);

	return 0;
}

static int cmd_bq35100_status(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	const struct device *dev = bq35100_shell_dev();
	struct bq35100_data *data;
	struct sensor_value val;

	if (!dev || !device_is_ready(dev)) {
		shell_error(sh, "BQ35100 not available");
		return -ENODEV;
	}

	data = (struct bq35100_data *)dev->data;

	sensor_sample_fetch_chan(dev, (enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_STATUS);
	sensor_sample_fetch_chan(dev, (enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_ALERT);
	sensor_sample_fetch_chan(dev, (enum sensor_channel)SENSOR_CHAN_BQ35100_CONTROL_STATUS);

	sensor_channel_get(dev, (enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_STATUS, &val);
	shell_print(sh, "BatteryStatus: 0x%02X [DSG=%d ALERT=%d]",
		    val.val1, !!(val.val1 & BQ35100_BSTAT_DSG),
		    !!(val.val1 & BQ35100_BSTAT_ALERT));

	sensor_channel_get(dev, (enum sensor_channel)SENSOR_CHAN_BQ35100_BATTERY_ALERT, &val);
	shell_print(sh, "BatteryAlert:  0x%02X [BATLOW=%d TEMPHI=%d TEMPLO=%d SOH_LOW=%d EOS=%d]",
		    val.val1, !!(val.val1 & BQ35100_BALERT_BATLOW),
		    !!(val.val1 & BQ35100_BALERT_TEMPHIGH),
		    !!(val.val1 & BQ35100_BALERT_TEMPLOW),
		    !!(val.val1 & BQ35100_BALERT_SOH_LOW),
		    !!(val.val1 & BQ35100_BALERT_EOS));

	sensor_channel_get(dev, (enum sensor_channel)SENSOR_CHAN_BQ35100_CONTROL_STATUS, &val);
	uint16_t cs = (uint16_t)val.val1;
	shell_print(sh, "ControlStatus: 0x%04X [GA=%d G_DONE=%d INIT=%d CAL=%d]",
		    cs, !!(cs & BQ35100_CS_GA), !!(cs & BQ35100_CS_G_DONE),
		    !!(cs & BQ35100_CS_INITCOMP), !!(cs & BQ35100_CS_CALMODE));

	const char *sec_str = "unknown";
	switch (cs & BQ35100_CS_SEC_MASK) {
	case BQ35100_CS_SEC_SEALED:   sec_str = "SEALED"; break;
	case BQ35100_CS_SEC_UNSEALED: sec_str = "UNSEALED"; break;
	case BQ35100_CS_SEC_FULL:     sec_str = "FULL_ACCESS"; break;
	}
	shell_print(sh, "Security:      %s", sec_str);
	shell_print(sh, "GE pin:        %s", data->enabled ? "HIGH" : "LOW");
	shell_print(sh, "Gauge:         %s", data->gauge_active ? "ACTIVE" : "INACTIVE");

	return 0;
}

static int cmd_bq35100_info(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	const struct device *dev = bq35100_shell_dev();
	uint16_t devtype, fwver, hwver, chemid;

	if (!dev || !device_is_ready(dev)) {
		shell_error(sh, "BQ35100 not available");
		return -ENODEV;
	}

	bq35100_control_read(dev, BQ35100_CNTL_DEVICE_TYPE, &devtype);
	bq35100_control_read(dev, BQ35100_CNTL_FW_VERSION, &fwver);
	bq35100_control_read(dev, BQ35100_CNTL_HW_VERSION, &hwver);
	bq35100_control_read(dev, BQ35100_CNTL_CHEM_ID, &chemid);

	shell_print(sh, "Device Type:   0x%04X %s", devtype,
		    devtype == BQ35100_DEVICE_TYPE ? "(BQ35100)" : "(UNKNOWN)");
	shell_print(sh, "FW Version:    0x%04X", fwver);
	shell_print(sh, "HW Version:    0x%04X", hwver);
	shell_print(sh, "Chemistry ID:  0x%04X", chemid);

	return 0;
}

static int cmd_bq35100_start(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	const struct device *dev = bq35100_shell_dev();

	if (!dev || !device_is_ready(dev)) {
		shell_error(sh, "BQ35100 not available");
		return -ENODEV;
	}

	int rc = bq35100_gauge_start(dev);
	if (rc) {
		shell_error(sh, "GAUGE_START failed: %d", rc);
	} else {
		shell_print(sh, "Gauge ACTIVE");
	}
	return rc;
}

static int cmd_bq35100_stop(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	const struct device *dev = bq35100_shell_dev();

	if (!dev || !device_is_ready(dev)) {
		shell_error(sh, "BQ35100 not available");
		return -ENODEV;
	}

	int rc = bq35100_gauge_stop(dev);
	if (rc) {
		shell_error(sh, "GAUGE_STOP failed: %d", rc);
	} else {
		shell_print(sh, "Gauge STOPPED");
	}
	return rc;
}

static int cmd_bq35100_unseal(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	const struct device *dev = bq35100_shell_dev();

	if (!dev || !device_is_ready(dev)) {
		shell_error(sh, "BQ35100 not available");
		return -ENODEV;
	}

	int rc = bq35100_unseal(dev);
	shell_print(sh, rc == 0 ? "Device UNSEALED" : "Unseal FAILED (%d)", rc);
	return rc;
}

static int cmd_bq35100_seal(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	const struct device *dev = bq35100_shell_dev();

	if (!dev || !device_is_ready(dev)) {
		shell_error(sh, "BQ35100 not available");
		return -ENODEV;
	}

	bq35100_seal(dev);
	shell_print(sh, "Device SEALED");
	return 0;
}

static int cmd_bq35100_new_battery(const struct shell *sh, size_t argc, char **argv)
{
	ARG_UNUSED(argc); ARG_UNUSED(argv);
	const struct device *dev = bq35100_shell_dev();

	if (!dev || !device_is_ready(dev)) {
		shell_error(sh, "BQ35100 not available");
		return -ENODEV;
	}

	bq35100_new_battery(dev);
	shell_print(sh, "NEW_BATTERY sent — impedance data reset");
	return 0;
}

static int cmd_bq35100_df_read(const struct shell *sh, size_t argc, char **argv)
{
	const struct device *dev = bq35100_shell_dev();
	uint8_t buf[32];
	uint16_t addr;
	uint8_t len = 16;

	if (!dev || !device_is_ready(dev)) {
		shell_error(sh, "BQ35100 not available");
		return -ENODEV;
	}

	if (argc < 2) {
		shell_error(sh, "Usage: bq35100 df_read <hex_addr> [len]");
		return -EINVAL;
	}

	addr = (uint16_t)strtoul(argv[1], NULL, 16);
	if (argc >= 3) {
		len = (uint8_t)strtoul(argv[2], NULL, 10);
		if (len > 32) len = 32;
	}

	int rc = bq35100_df_read(dev, addr, buf, len);
	if (rc) {
		shell_error(sh, "DF read failed: %d", rc);
		return rc;
	}

	shell_print(sh, "DF 0x%04X (%u bytes):", addr, len);
	shell_hexdump(sh, buf, len);
	return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_bq35100,
	SHELL_CMD(read, NULL, "Read all sensor data", cmd_bq35100_read),
	SHELL_CMD(status, NULL, "Status flags + security state", cmd_bq35100_status),
	SHELL_CMD(info, NULL, "Device type, FW, HW, chemistry", cmd_bq35100_info),
	SHELL_CMD(start, NULL, "GAUGE_START (enter ACTIVE mode)", cmd_bq35100_start),
	SHELL_CMD(stop, NULL, "GAUGE_STOP (wait for G_DONE)", cmd_bq35100_stop),
	SHELL_CMD(unseal, NULL, "Unseal with default keys", cmd_bq35100_unseal),
	SHELL_CMD(seal, NULL, "Seal device", cmd_bq35100_seal),
	SHELL_CMD(new_battery, NULL, "Reset for new battery", cmd_bq35100_new_battery),
	SHELL_CMD(df_read, NULL, "Read data flash: df_read <addr> [len]", cmd_bq35100_df_read),
	SHELL_SUBCMD_SET_END
);
SHELL_CMD_REGISTER(bq35100, &sub_bq35100, "BQ35100 fuel gauge", NULL);

#endif /* CONFIG_CK_BQ35100_SHELL */

/* ------------------------------------------------------------------ */
/* Device driver API + instantiation                                   */
/* ------------------------------------------------------------------ */

static DEVICE_API(sensor, bq35100_api) = {
	.sample_fetch = bq35100_sample_fetch,
	.channel_get = bq35100_channel_get,
	.attr_set = bq35100_attr_set,
#ifdef CONFIG_CK_BQ35100_TRIGGER
	.trigger_set = bq35100_trigger_set,
#endif
};

/* Compile-time gauging mode resolution from DTS string property */
#define BQ35100_PARSE_MODE(mode_str)                                              \
	(COND_CODE_1(IS_EQ(mode_str, accumulator), (BQ35100_MODE_ACCUMULATOR),    \
	 (COND_CODE_1(IS_EQ(mode_str, soh), (BQ35100_MODE_SOH),                  \
	 (COND_CODE_1(IS_EQ(mode_str, eos), (BQ35100_MODE_EOS),                  \
	 (BQ35100_MODE_ACCUMULATOR)))))))

/* Use token-based comparison: DT_INST_STRING_TOKEN gives us a C token from the DTS string */
#define BQ35100_MODE_FROM_DT(inst)                                                \
	_CONCAT(BQ35100_MODE_DT_, DT_INST_STRING_UPPER_TOKEN(inst, gauging_mode))

#define BQ35100_MODE_DT_ACCUMULATOR BQ35100_MODE_ACCUMULATOR
#define BQ35100_MODE_DT_SOH         BQ35100_MODE_SOH
#define BQ35100_MODE_DT_EOS         BQ35100_MODE_EOS

#define BQ35100_INIT(inst)                                                                         \
	static struct bq35100_data bq35100_data_##inst;                                            \
	static const struct bq35100_config bq35100_config_##inst = {                               \
		.i2c = I2C_DT_SPEC_INST_GET(inst),                                                \
		.enable_gpio = GPIO_DT_SPEC_INST_GET(inst, enable_gpios),                          \
		IF_ENABLED(CONFIG_CK_BQ35100_TRIGGER,                                              \
			(.alert_gpio = GPIO_DT_SPEC_INST_GET_OR(inst, alert_gpios, {0}),))         \
		.design_capacity_mah = DT_INST_PROP(inst, design_capacity_mah),                    \
		.gauging_mode = BQ35100_MODE_FROM_DT(inst),                                        \
		.power_up_delay_ms = DT_INST_PROP(inst, power_up_delay_ms),                        \
	};                                                                                         \
	DEVICE_DT_INST_DEFINE(inst, bq35100_init, NULL, &bq35100_data_##inst,                      \
			      &bq35100_config_##inst, POST_KERNEL,                                 \
			      CONFIG_CK_BQ35100_INIT_PRIORITY, &bq35100_api);

DT_INST_FOREACH_STATUS_OKAY(BQ35100_INIT)
