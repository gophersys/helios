#include "api.h"

// Standard includes
#include <math.h>
#include <stdbool.h>
#include <stdint.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Thread includes
#include "../types.h"

LOG_MODULE_DECLARE(vitals_t);

static void _interpolate_sensors_to_25Hz(vitals_thread_t *p_thread);
static void _interpolate_25Hz_to_32Hz(vitals_thread_t *p_thread);
static void _convert_raw_samples_for_psp(vitals_thread_t *p_thread);

void _prepare_sensor_samples(vitals_thread_t *p_thread) {
    // The accelerometer samples are at 26Hz, and the PPG samples are at 25Hz
    // So first we need to interpolate the accelerometer samples to 25Hz
    _interpolate_sensors_to_25Hz(p_thread);

    // Then we need to interpolate the PPG samples to 32Hz as the PSP algorithm requires 32Hz samples
    _interpolate_25Hz_to_32Hz(p_thread);

    // Finally, convert the PPG samples to the format required by the PSP algorithm
    _convert_raw_samples_for_psp(p_thread);
}

static void _interpolate_25Hz_to_32Hz(vitals_thread_t *p_thread) {
    sensors_sample_t *src = p_thread->raw_samples_25Hz;
    sensors_sample_t *dst = p_thread->raw_samples_32Hz;

    uint64_t t_start = src[0].ppg.timestamp;
    uint64_t t_span = src[CONFIG_PPG_SAMPLES_PER_BATCH - 1].ppg.timestamp - t_start;
    float t_step = (float)t_span / (CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND - 1);

    for (int i = 0; i < CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND; i++) {
        uint64_t t_target = t_start + (uint64_t)(i * t_step);
        int lower_idx = -1;

        // Find bracketing samples
        for (int j = 0; j < CONFIG_PPG_SAMPLES_PER_BATCH - 1; j++) {
            if (src[j].ppg.timestamp <= t_target && src[j + 1].ppg.timestamp >= t_target) {
                lower_idx = j;
                break;
            }
        }

        if (lower_idx >= 0) {
            float t = (float)(t_target - src[lower_idx].ppg.timestamp) /
                      (float)(src[lower_idx + 1].ppg.timestamp - src[lower_idx].ppg.timestamp);

// Helper macro for linear interpolation
#define LERP(field) (src[lower_idx].field + t * (src[lower_idx + 1].field - src[lower_idx].field))

            // Timestamp
            dst[i].ppg.timestamp = t_target;

            // Intensities
            dst[i].ppg.red_intensity = (int32_t)LERP(ppg.red_intensity);
            dst[i].ppg.green_intensity = (int32_t)LERP(ppg.green_intensity);
            dst[i].ppg.ir_intensity = (int32_t)LERP(ppg.ir_intensity);

            // Exposure times
            dst[i].ppg.red_expo_us = LERP(ppg.red_expo_us);
            dst[i].ppg.green_expo_us = LERP(ppg.green_expo_us);
            dst[i].ppg.ir_expo_us = LERP(ppg.ir_expo_us);

            // DAC values (use nearest neighbor for discrete values)
            dst[i].ppg.red_dac = t < 0.5f ? src[lower_idx].ppg.red_dac : src[lower_idx + 1].ppg.red_dac;
            dst[i].ppg.green_dac = t < 0.5f ? src[lower_idx].ppg.green_dac : src[lower_idx + 1].ppg.green_dac;
            dst[i].ppg.ir_dac = t < 0.5f ? src[lower_idx].ppg.ir_dac : src[lower_idx + 1].ppg.ir_dac;

            // Current values (use nearest neighbor for discrete values)
            dst[i].ppg.red_curr_ma = t < 0.5f ? src[lower_idx].ppg.red_curr_ma : src[lower_idx + 1].ppg.red_curr_ma;
            dst[i].ppg.green_curr_ma = t < 0.5f ? src[lower_idx].ppg.green_curr_ma : src[lower_idx + 1].ppg.green_curr_ma;
            dst[i].ppg.ir_curr_ma = t < 0.5f ? src[lower_idx].ppg.ir_curr_ma : src[lower_idx + 1].ppg.ir_curr_ma;

            // Accelerometer values
            dst[i].accel_x = LERP(accel_x);
            dst[i].accel_y = LERP(accel_y);
            dst[i].accel_z = LERP(accel_z);

#undef LERP
        } else {
            // Edge case: use nearest neighbor
            int nearest = (t_target < src[0].ppg.timestamp) ? 0 : CONFIG_PPG_SAMPLES_PER_BATCH - 1;
            memcpy(&dst[i], &src[nearest], sizeof(sensors_sample_t));
            dst[i].ppg.timestamp = t_target;
        }
    }
}

static void _interpolate_sensors_to_25Hz(vitals_thread_t *p_thread) {
    // For each PPG sample, interpolate matching accelerometer value
    for (int i = 0; i < CONFIG_PPG_SAMPLES_PER_BATCH; i++) {
        uint64_t ppg_timestamp = p_thread->ppg_interrupt_samples[i].timestamp;

        // Copy PPG data directly
        memcpy(&p_thread->raw_samples_25Hz[i].ppg, &p_thread->ppg_interrupt_samples[i], sizeof(struct pah8151_ppg_sample));

        // Find accelerometer samples that bracket this timestamp
        int lower_idx = -1;
        for (int j = 0; j < CONFIG_ACCEL_RING_BUF_COUNT - 1; j++) {
            if (p_thread->accel_interrupt_samples[j].timestamp <= ppg_timestamp &&
                p_thread->accel_interrupt_samples[j + 1].timestamp >= ppg_timestamp) {
                lower_idx = j;
                break;
            }
        }

        if (lower_idx >= 0) {
            // Linear interpolation
            float t = (float)(ppg_timestamp - p_thread->accel_interrupt_samples[lower_idx].timestamp) /
                      (float)(p_thread->accel_interrupt_samples[lower_idx + 1].timestamp -
                              p_thread->accel_interrupt_samples[lower_idx].timestamp);

            p_thread->raw_samples_25Hz[i].accel_x =
                p_thread->accel_interrupt_samples[lower_idx].x +
                t * (p_thread->accel_interrupt_samples[lower_idx + 1].x -
                     p_thread->accel_interrupt_samples[lower_idx].x);

            p_thread->raw_samples_25Hz[i].accel_y =
                p_thread->accel_interrupt_samples[lower_idx].y +
                t * (p_thread->accel_interrupt_samples[lower_idx + 1].y -
                     p_thread->accel_interrupt_samples[lower_idx].y);

            p_thread->raw_samples_25Hz[i].accel_z =
                p_thread->accel_interrupt_samples[lower_idx].z +
                t * (p_thread->accel_interrupt_samples[lower_idx + 1].z -
                     p_thread->accel_interrupt_samples[lower_idx].z);
        } else {
            // If no bracketing samples found, use nearest neighbor
            int nearest = 0;
            uint64_t min_diff = UINT64_MAX;
            for (int j = 0; j < CONFIG_ACCEL_RING_BUF_COUNT; j++) {
                uint64_t diff = llabs((int64_t)ppg_timestamp -
                                      (int64_t)p_thread->accel_interrupt_samples[j].timestamp);
                if (diff < min_diff) {
                    min_diff = diff;
                    nearest = j;
                }
            }

            p_thread->raw_samples_25Hz[i].accel_x = p_thread->accel_interrupt_samples[nearest].x;
            p_thread->raw_samples_25Hz[i].accel_y = p_thread->accel_interrupt_samples[nearest].y;
            p_thread->raw_samples_25Hz[i].accel_z = p_thread->accel_interrupt_samples[nearest].z;
        }
    }
}

// Constants for PPG normalization
#define PPG_MAX_THRESHOLD_PERCENT 0.90f  // 90% of max range
#define PPG_MIN_THRESHOLD_PERCENT 0.20f  // 20% of max range
#define PPG_MAX_VALUE 65535.0f           // 16-bit unsigned max
#define DEFAULT_SF0 32768.0f             // Default scaling factor (middle of range)
#define CALIBRATION_PERIOD_SEC 3         // N seconds for initial calibration
#define DEFAULT_ADC_GAIN 2               // Start with gain = 2 as specified
#define MIN_ADC_GAIN 1
#define MAX_ADC_GAIN 3
#define ACCEL_G_TO_PSP_SCALE 512.0f  // Convert g to PSP units (1/512 g/unit)
#define ACCEL_PSP_MAX 4095           // Max value for 13-bit signed
#define ACCEL_PSP_MIN -4096          // Min value for 13-bit signed

// Structure to track calibration state for each LED
typedef struct {
    float scaling_factor;
    uint8_t adc_gain;
    float max_value;
    bool cal_complete;
    uint32_t sample_count;
    float last_max_ppg;  // Track max PPG in last calibration period
} led_calibration_t;

// Add this to vitals_thread_t in types.h
typedef struct {
    led_calibration_t red;
    led_calibration_t ir;
    led_calibration_t green;
    uint32_t cal_timer;
} ppg_calibration_state_t;

static void init_led_calibration(led_calibration_t *cal) {
    cal->scaling_factor = DEFAULT_SF0;
    cal->adc_gain = DEFAULT_ADC_GAIN;  // Start at gain = 2
    cal->max_value = 0.0f;
    cal->cal_complete = false;
    cal->sample_count = 0;
    cal->last_max_ppg = 0.0f;
}

static void adjust_led_gain(led_calibration_t *cal, float raw_value, float normalized_value) {
    // Track maximum raw value
    cal->last_max_ppg = fmaxf(cal->last_max_ppg, fabsf(raw_value));

    if (normalized_value > PPG_MAX_VALUE * PPG_MAX_THRESHOLD_PERCENT) {
        if (cal->adc_gain > MIN_ADC_GAIN) {
            cal->scaling_factor /= 2.0f;
            cal->adc_gain--;
        } else {
            // Recalibrate if we can't decrease gain further
            cal->cal_complete = false;
            cal->max_value = 0.0f;
            cal->last_max_ppg = 0.0f;
            cal->sample_count = 0;
        }
    } else if (normalized_value < PPG_MAX_VALUE * PPG_MIN_THRESHOLD_PERCENT) {
        if (cal->adc_gain < MAX_ADC_GAIN) {
            cal->scaling_factor *= 2.0f;
            cal->adc_gain++;
        } else {
            // Recalibrate if we can't increase gain further
            cal->cal_complete = false;
            cal->max_value = 0.0f;
            cal->last_max_ppg = 0.0f;
            cal->sample_count = 0;
        }
    }
}

static void _convert_raw_samples_for_psp(vitals_thread_t *p_thread) {
    static ppg_calibration_state_t cal_state = {0};

    // Initialize calibration state if needed
    if (cal_state.cal_timer == 0) {
        init_led_calibration(&cal_state.red);
        init_led_calibration(&cal_state.ir);
        init_led_calibration(&cal_state.green);
    }

    for (int i = 0; i < CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND; i++) {
        sensors_sample_t *raw = &p_thread->raw_samples_32Hz[i];
        psp_algorithm_input_metrics_t *psp = &p_thread->psp_input_samples_32Hz[i];

        // Initial calibration period
        if (!cal_state.red.cal_complete) {
            cal_state.red.max_value = fmaxf(cal_state.red.max_value, fabsf(raw->ppg.red_intensity));
            cal_state.red.sample_count++;

            if (cal_state.red.sample_count >= CALIBRATION_PERIOD_SEC * CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND) {
                // Calculate SF1 based on max value during calibration period
                cal_state.red.scaling_factor = (PPG_MAX_VALUE / 2.0f) / cal_state.red.max_value;
                cal_state.red.cal_complete = true;
                cal_state.red.last_max_ppg = cal_state.red.max_value;

                // IR must use same scaling factor as red for SpO2, but divided by 2
                cal_state.ir.scaling_factor = cal_state.red.scaling_factor / 2.0f;
                cal_state.ir.cal_complete = true;
                cal_state.ir.adc_gain = cal_state.red.adc_gain;
            }
        }

        // Green channel calibration
        if (!cal_state.green.cal_complete) {
            cal_state.green.max_value = fmaxf(cal_state.green.max_value, fabsf(raw->ppg.green_intensity));
            cal_state.green.sample_count++;

            if (cal_state.green.sample_count >= CALIBRATION_PERIOD_SEC * CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND) {
                cal_state.green.scaling_factor = (PPG_MAX_VALUE / 2.0f) / cal_state.green.max_value;
                cal_state.green.cal_complete = true;
                p_thread->data_ready_for_psp = true;
                cal_state.green.last_max_ppg = cal_state.green.max_value;
            }
        }

        // Scale and normalize the PPG signals
        float scaled_red = raw->ppg.red_intensity * cal_state.red.scaling_factor;
        float scaled_ir = raw->ppg.ir_intensity * cal_state.ir.scaling_factor;  // Already includes /2
        float scaled_green = raw->ppg.green_intensity * cal_state.green.scaling_factor;

        // Dynamic gain adjustment if calibration is complete
        if (cal_state.red.cal_complete) {
            adjust_led_gain(&cal_state.red, raw->ppg.red_intensity, scaled_red);
            // IR uses same scaling as red for SpO2, but divided by 2
            cal_state.ir.scaling_factor = cal_state.red.scaling_factor / 2.0f;
            cal_state.ir.adc_gain = cal_state.red.adc_gain;
        }

        if (cal_state.green.cal_complete) {
            adjust_led_gain(&cal_state.green, raw->ppg.green_intensity, scaled_green);
        }

        // Store normalized values
        psp->ppg_red = (uint16_t)CLAMP(scaled_red, 0.0f, PPG_MAX_VALUE);
        psp->ppg_ir = (uint16_t)CLAMP(scaled_ir, 0.0f, PPG_MAX_VALUE);
        psp->ppg_green = (uint16_t)CLAMP(scaled_green, 0.0f, PPG_MAX_VALUE);

        // Convert accelerometer values (unchanged)
        float accel_x_psp = raw->accel_x * ACCEL_G_TO_PSP_SCALE;
        float accel_y_psp = raw->accel_y * ACCEL_G_TO_PSP_SCALE;
        float accel_z_psp = raw->accel_z * ACCEL_G_TO_PSP_SCALE;

        psp->accel_x = (int16_t)CLAMP(accel_x_psp, ACCEL_PSP_MIN, ACCEL_PSP_MAX);
        psp->accel_y = (int16_t)CLAMP(accel_y_psp, ACCEL_PSP_MIN, ACCEL_PSP_MAX);
        psp->accel_z = (int16_t)CLAMP(accel_z_psp, ACCEL_PSP_MIN, ACCEL_PSP_MAX);

        // TODO: add a log here to print the psp values
    }

    cal_state.cal_timer++;
}
