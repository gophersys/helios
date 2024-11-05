#ifndef THREADS_VITALS_UTILS_H_
#define THREADS_VITALS_UTILS_H_

// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>

// Application includes
#include "types.h"

/**
 * @brief Check the validity of the configuration
 *
 * @param p_config Configuration to check
 * @return true if valid, false otherwise
 */
bool _check_config(const vitals_thread_config_t *p_config);

void _interpolate_sensor_samples(vitals_thread_t *p_thread);
void _print_sensor_samples(vitals_thread_t *p_thread);

// Linear Interpolation Helpers
void _scale_ppg_to_uint16(const uint32_t *input_samples,
                          size_t input_count,
                          uint16_t *output_samples);
void _upsample_uint16(const uint16_t *input_samples, size_t input_count, uint16_t *output_samples, size_t output_count);
void _upsample_int16(const int16_t *input_samples, size_t input_count, int16_t *output_samples, size_t output_count);

// PSP Algorithm Helpers
bool _psp_init(vitals_thread_t *p_thread);
bool _psp_update_input_metrics(vitals_thread_t *p_thread);
bool _psp_process(vitals_thread_t *p_thread);
const char *_psp_error_string(PSP_ERROR err);
const char *_psp_metric_string(PSP_METRIC_ID metric);

#endif  // THREADS_VITALS_UTILS_H_
