// SPDX-License-Identifier: Apache-2.0
/*
 * ICLE GPIO Control Driver
 *
 * Controls MUX lines, power FET gate, ADC inhibit, and LEDs
 */

#ifndef ICLE_HAL_GPIO_H_
#define ICLE_HAL_GPIO_H_

#include <zephyr/kernel.h>
#include <stdbool.h>
#include "icle/types.h"

#ifdef __cplusplus
extern "C" {
#endif

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

#endif /* ICLE_HAL_GPIO_H_ */
