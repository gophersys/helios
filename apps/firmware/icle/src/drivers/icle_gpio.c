/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE GPIO Control Driver
 */

#include "icle_gpio.h"

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(icle_gpio, CONFIG_LOG_DEFAULT_LEVEL);

#include <zephyr/drivers/gpio.h>

/* GPIO device tree nodes - defined in board DTS */
#define MUX0_NODE  DT_NODELABEL(mux0)
#define MUX1_NODE  DT_NODELABEL(mux1)
#define MUX2_NODE  DT_NODELABEL(mux2)
#define PFET_NODE  DT_NODELABEL(pfet_gate)
#define ADC_INH_NODE DT_NODELABEL(adc_inh)
#define LED_GREEN_NODE DT_ALIAS(led0)
#define LED_RED_NODE   DT_ALIAS(led1)

/* GPIO specs from DT */
static const struct gpio_dt_spec mux0 = GPIO_DT_SPEC_GET(MUX0_NODE, gpios);
static const struct gpio_dt_spec mux1 = GPIO_DT_SPEC_GET(MUX1_NODE, gpios);
static const struct gpio_dt_spec mux2 = GPIO_DT_SPEC_GET(MUX2_NODE, gpios);
static const struct gpio_dt_spec pfet_gate = GPIO_DT_SPEC_GET(PFET_NODE, gpios);
static const struct gpio_dt_spec adc_inh = GPIO_DT_SPEC_GET(ADC_INH_NODE, gpios);
static const struct gpio_dt_spec led_green = GPIO_DT_SPEC_GET(LED_GREEN_NODE, gpios);
static const struct gpio_dt_spec led_red = GPIO_DT_SPEC_GET(LED_RED_NODE, gpios);

static bool initialized;
static enum icle_mux_channel current_mux_channel;
static bool pfet_enabled;

int icle_gpio_init(void)
{
	int ret;

	if (initialized) {
		return 0;
	}

	/* Configure MUX control lines as outputs */
	if (!gpio_is_ready_dt(&mux0) || !gpio_is_ready_dt(&mux1) ||
	    !gpio_is_ready_dt(&mux2)) {
		LOG_ERR("MUX GPIO devices not ready");
		return -ENODEV;
	}

	ret = gpio_pin_configure_dt(&mux0, GPIO_OUTPUT_LOW);
	if (ret < 0) {
		LOG_ERR("Failed to configure MUX0: %d", ret);
		return ret;
	}

	ret = gpio_pin_configure_dt(&mux1, GPIO_OUTPUT_LOW);
	if (ret < 0) {
		LOG_ERR("Failed to configure MUX1: %d", ret);
		return ret;
	}

	ret = gpio_pin_configure_dt(&mux2, GPIO_OUTPUT_LOW);
	if (ret < 0) {
		LOG_ERR("Failed to configure MUX2: %d", ret);
		return ret;
	}

	/* Configure power FET gate (active low) */
	if (!gpio_is_ready_dt(&pfet_gate)) {
		LOG_ERR("PFET GPIO device not ready");
		return -ENODEV;
	}

	ret = gpio_pin_configure_dt(&pfet_gate, GPIO_OUTPUT_HIGH);  /* Start disabled */
	if (ret < 0) {
		LOG_ERR("Failed to configure PFET gate: %d", ret);
		return ret;
	}

	/* Configure ADC inhibit */
	if (!gpio_is_ready_dt(&adc_inh)) {
		LOG_ERR("ADC INH GPIO device not ready");
		return -ENODEV;
	}

	ret = gpio_pin_configure_dt(&adc_inh, GPIO_OUTPUT_LOW);
	if (ret < 0) {
		LOG_ERR("Failed to configure ADC INH: %d", ret);
		return ret;
	}

	/* Configure LEDs */
	if (!gpio_is_ready_dt(&led_green) || !gpio_is_ready_dt(&led_red)) {
		LOG_ERR("LED GPIO devices not ready");
		return -ENODEV;
	}

	ret = gpio_pin_configure_dt(&led_green, GPIO_OUTPUT_LOW);
	if (ret < 0) {
		LOG_ERR("Failed to configure green LED: %d", ret);
		return ret;
	}

	ret = gpio_pin_configure_dt(&led_red, GPIO_OUTPUT_LOW);
	if (ret < 0) {
		LOG_ERR("Failed to configure red LED: %d", ret);
		return ret;
	}

	current_mux_channel = ICLE_MUX_CH0;
	pfet_enabled = false;
	initialized = true;

	LOG_INF("ICLE GPIO initialized");
	return 0;
}

int icle_mux_select(enum icle_mux_channel channel)
{
	int ret;

	if (!initialized) {
		return -ENODEV;
	}

	if (channel > ICLE_MUX_CH7) {
		return -EINVAL;
	}

	ret = gpio_pin_set_dt(&mux0, (channel >> 0) & 0x01);
	if (ret < 0) return ret;

	ret = gpio_pin_set_dt(&mux1, (channel >> 1) & 0x01);
	if (ret < 0) return ret;

	ret = gpio_pin_set_dt(&mux2, (channel >> 2) & 0x01);
	if (ret < 0) return ret;

	current_mux_channel = channel;
	LOG_DBG("MUX channel set to %d", channel);

	return 0;
}

enum icle_mux_channel icle_mux_get(void)
{
	return current_mux_channel;
}

int icle_power_fet_enable(bool enable)
{
	int ret;

	if (!initialized) {
		return -ENODEV;
	}

	/* PFET gate is active low */
	ret = gpio_pin_set_dt(&pfet_gate, !enable);
	if (ret < 0) {
		LOG_ERR("Failed to set PFET gate: %d", ret);
		return ret;
	}

	pfet_enabled = enable;
	LOG_INF("Power FET %s", enable ? "enabled" : "disabled");

	return 0;
}

bool icle_power_fet_is_enabled(void)
{
	return pfet_enabled;
}

int icle_adc_inhibit(bool inhibit)
{
	int ret;

	if (!initialized) {
		return -ENODEV;
	}

	ret = gpio_pin_set_dt(&adc_inh, inhibit);
	if (ret < 0) {
		LOG_ERR("Failed to set ADC inhibit: %d", ret);
		return ret;
	}

	LOG_DBG("ADC inhibit %s", inhibit ? "enabled" : "disabled");
	return 0;
}

int icle_led_set(enum icle_led led, bool on)
{
	int ret;
	const struct gpio_dt_spec *led_spec;

	if (!initialized) {
		return -ENODEV;
	}

	switch (led) {
	case ICLE_LED_GREEN:
		led_spec = &led_green;
		break;
	case ICLE_LED_RED:
		led_spec = &led_red;
		break;
	default:
		return -EINVAL;
	}

	ret = gpio_pin_set_dt(led_spec, on);
	if (ret < 0) {
		LOG_ERR("Failed to set LED %d: %d", led, ret);
		return ret;
	}

	return 0;
}

int icle_led_toggle(enum icle_led led)
{
	int ret;
	const struct gpio_dt_spec *led_spec;

	if (!initialized) {
		return -ENODEV;
	}

	switch (led) {
	case ICLE_LED_GREEN:
		led_spec = &led_green;
		break;
	case ICLE_LED_RED:
		led_spec = &led_red;
		break;
	default:
		return -EINVAL;
	}

	ret = gpio_pin_toggle_dt(led_spec);
	if (ret < 0) {
		LOG_ERR("Failed to toggle LED %d: %d", led, ret);
		return ret;
	}

	return 0;
}
