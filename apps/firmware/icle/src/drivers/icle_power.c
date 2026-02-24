/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE Power Monitor Driver (INA209)
 */

#include "icle_power.h"

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_power, CONFIG_LOG_DEFAULT_LEVEL);

#include <zephyr/drivers/sensor.h>

/* INA209 device from DTS */
#define INA209_NODE DT_NODELABEL(ina209)

#if DT_NODE_HAS_STATUS(INA209_NODE, okay)
static const struct device *ina209_dev = DEVICE_DT_GET(INA209_NODE);
static bool initialized;

int icle_power_init(void)
{
	if (initialized) {
		return 0;
	}

	if (!device_is_ready(ina209_dev)) {
		LOG_ERR("INA209 device not ready");
		return -ENODEV;
	}

	initialized = true;
	LOG_INF("INA209 power monitor initialized");
	return 0;
}

int icle_power_read(struct icle_power_data *data)
{
	struct sensor_value voltage, current, power;
	int ret;

	if (!initialized) {
		return -ENODEV;
	}

	if (data == NULL) {
		return -EINVAL;
	}

	ret = sensor_sample_fetch(ina209_dev);
	if (ret < 0) {
		LOG_ERR("Failed to fetch INA209 sample: %d", ret);
		return ret;
	}

	ret = sensor_channel_get(ina209_dev, SENSOR_CHAN_VOLTAGE, &voltage);
	if (ret < 0) {
		LOG_ERR("Failed to get voltage: %d", ret);
		return ret;
	}

	ret = sensor_channel_get(ina209_dev, SENSOR_CHAN_CURRENT, &current);
	if (ret < 0) {
		LOG_ERR("Failed to get current: %d", ret);
		return ret;
	}

	ret = sensor_channel_get(ina209_dev, SENSOR_CHAN_POWER, &power);
	if (ret < 0) {
		LOG_ERR("Failed to get power: %d", ret);
		return ret;
	}

	/* Convert to microunits */
	data->voltage_uv = sensor_value_to_micro(&voltage);
	data->current_ua = sensor_value_to_micro(&current);
	data->power_uw = sensor_value_to_micro(&power);

	LOG_DBG("V: %d.%06d V, I: %d.%06d A, P: %d.%06d W",
		voltage.val1, voltage.val2,
		current.val1, current.val2,
		power.val1, power.val2);

	return 0;
}

int32_t icle_power_get_voltage_uv(void)
{
	struct icle_power_data data;
	int ret;

	ret = icle_power_read(&data);
	if (ret < 0) {
		return ret;
	}

	return data.voltage_uv;
}

int32_t icle_power_get_current_ua(void)
{
	struct icle_power_data data;
	int ret;

	ret = icle_power_read(&data);
	if (ret < 0) {
		return INT32_MIN;
	}

	return data.current_ua;
}

#else
/* Stub implementation when INA209 is not enabled */

int icle_power_init(void)
{
	LOG_WRN("INA209 not enabled in device tree");
	return -ENOTSUP;
}

int icle_power_read(struct icle_power_data *data)
{
	return -ENOTSUP;
}

int32_t icle_power_get_voltage_uv(void)
{
	return -ENOTSUP;
}

int32_t icle_power_get_current_ua(void)
{
	return INT32_MIN;
}

#endif /* DT_NODE_HAS_STATUS(INA209_NODE, okay) */
