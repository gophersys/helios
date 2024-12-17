#ifndef THREADS_VITALS_UTILS_H_
#define THREADS_VITALS_UTILS_H_

// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>

// Application includes
#include "../types.h"

/**
 * @brief Check the validity of the configuration
 *
 * @param p_config Configuration to check
 * @return true if valid, false otherwise
 */
bool _check_config(const vitals_thread_config_t *p_config);

/**
 * @brief Prepare the sensor samples for use in the PSP library
 *
 * @param p_thread Thread data
 */
void _prepare_sensor_samples(vitals_thread_t *p_thread);
/**
 * @brief Print the sensor samples
 *
 * @param p_thread Thread data
 */
void _send_ble_sensor_samples(vitals_thread_t *p_thread);

/**
 * @brief Initialize the Phillips Biosensing Platform library
 *
 * @param p_thread Thread data
 * @return true if successful, false otherwise
 */
bool _psp_init(vitals_thread_t *p_thread);

/**
 * @brief Update the input metrics for the Phillips Biosensing Platform library
 *
 * @param p_thread Thread data
 * @return true if successful, false otherwise
 */
bool _psp_update_input_metrics(vitals_thread_t *p_thread);

/**
 * @brief Process the input metrics for the Phillips Biosensing Platform library
 *
 * @param p_thread Thread data
 * @return true if successful, false otherwise
 */
bool _psp_process(vitals_thread_t *p_thread);

/**
 * @brief Get the output metrics from the Phillips Biosensing Platform library
 *
 * @param p_thread Thread data
 * @return true if successful, false otherwise
 */
bool _psp_get_output_metrics(vitals_thread_t *p_thread);

#endif  // THREADS_VITALS_UTILS_H_
