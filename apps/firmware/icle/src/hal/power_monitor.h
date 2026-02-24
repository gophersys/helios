/*
 * SPDX-License-Identifier: Apache-2.0
 * ICLE Power Monitor Driver (INA209)
 */

#ifndef ICLE_HAL_POWER_MONITOR_H_
#define ICLE_HAL_POWER_MONITOR_H_

#include <zephyr/kernel.h>
#include "icle/types.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize power monitor
 *
 * @return 0 on success, negative errno on failure
 */
int icle_power_init(void);

/**
 * @brief Read power measurements
 *
 * @param data Pointer to store measurement data
 * @return 0 on success, negative errno on failure
 */
int icle_power_read(struct icle_power_data *data);

/**
 * @brief Get bus voltage
 *
 * @return Bus voltage in microvolts, or negative errno on failure
 */
int32_t icle_power_get_voltage_uv(void);

/**
 * @brief Get current
 *
 * @return Current in microamps, or INT32_MIN on failure
 */
int32_t icle_power_get_current_ua(void);

#ifdef __cplusplus
}
#endif

#endif /* ICLE_HAL_POWER_MONITOR_H_ */
