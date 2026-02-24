/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE GPIO Control Driver
 *
 * Controls MUX lines, power FET gate, ADC inhibit, and LEDs
 */

#ifndef ICLE_GPIO_H_
#define ICLE_GPIO_H_

#include <zephyr/kernel.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief MUX channel selection
 */
enum icle_mux_channel {
	ICLE_MUX_CH0 = 0,
	ICLE_MUX_CH1 = 1,
	ICLE_MUX_CH2 = 2,
	ICLE_MUX_CH3 = 3,
	ICLE_MUX_CH4 = 4,
	ICLE_MUX_CH5 = 5,
	ICLE_MUX_CH6 = 6,
	ICLE_MUX_CH7 = 7,
};

/**
 * @brief LED identifiers
 */
enum icle_led {
	ICLE_LED_GREEN = 0,
	ICLE_LED_RED = 1,
};

/**
 * @brief Initialize ICLE GPIO subsystem
 *
 * @return 0 on success, negative errno on failure
 */
int icle_gpio_init(void);

/**
 * @brief Set MUX channel
 *
 * @param channel Channel to select (0-7)
 * @return 0 on success, negative errno on failure
 */
int icle_mux_select(enum icle_mux_channel channel);

/**
 * @brief Get current MUX channel
 *
 * @return Current MUX channel
 */
enum icle_mux_channel icle_mux_get(void);

/**
 * @brief Enable/disable power FET
 *
 * @param enable true to enable power output
 * @return 0 on success, negative errno on failure
 */
int icle_power_fet_enable(bool enable);

/**
 * @brief Check if power FET is enabled
 *
 * @return true if power FET is enabled
 */
bool icle_power_fet_is_enabled(void);

/**
 * @brief Set ADC inhibit state
 *
 * @param inhibit true to inhibit ADC
 * @return 0 on success, negative errno on failure
 */
int icle_adc_inhibit(bool inhibit);

/**
 * @brief Set LED state
 *
 * @param led LED to control
 * @param on true to turn on LED
 * @return 0 on success, negative errno on failure
 */
int icle_led_set(enum icle_led led, bool on);

/**
 * @brief Toggle LED state
 *
 * @param led LED to toggle
 * @return 0 on success, negative errno on failure
 */
int icle_led_toggle(enum icle_led led);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_GPIO_H_ */
