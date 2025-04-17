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

// Constants for PPG normalization

// Thresholds as per Philips PSP requirements
#define PPG_MAX_THRESHOLD_PERCENT 0.90  // 90% of max range
#define PPG_MIN_THRESHOLD_PERCENT 0.45  // 45% of max range
#define PPG_MAX_VALUE 65535.0           // 16-bit unsigned max (2^16 - 1)
#define DEFAULT_SF0 32768.0             // Default scaling factor (middle of range)
#define CALIBRATION_PERIOD_SEC 3        // N seconds for initial calibration

// Signal stabilization parameters
#define STABILIZATION_MAX_VARIATION 0.30  // 30% max variation during stabilization period
#define STABILIZATION_WINDOW_SIZE 8       // Number of samples to check for stability
#define MIN_SIGNAL_INTENSITY 1000.0       // Minimum expected signal level when properly attached

// ADC gain settings as per Philips requirements
#define DEFAULT_ADC_GAIN 2  // Start with gain = 2
#define MIN_ADC_GAIN 1
#define MAX_ADC_GAIN 3

// Accelerometer conversion constants - converts g-force to PSP algorithm units
#define ACCEL_G_TO_PSP_SCALE 512.0f  // Conversion factor from g-force to PSP units (1/512 g/unit)
#define ACCEL_PSP_MAX 4095           // Maximum value for 13-bit signed accelerometer data
#define ACCEL_PSP_MIN -4096          // Minimum value for 13-bit signed accelerometer data

// Private functions
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

// Structure to track calibration state for each LED
typedef struct {
    float scaling_factor;
    uint8_t adc_gain;
    float max_value;
    bool cal_complete;
    uint32_t sample_count;
    float last_max_ppg;  // Track max PPG in last calibration period

    // Signal stabilization tracking
    float recent_values[STABILIZATION_WINDOW_SIZE];
    uint8_t value_index;
    bool is_stable;
} led_calibration_t;

// Add this to vitals_thread_t in types.h
typedef struct {
    led_calibration_t red;
    led_calibration_t ir;
    led_calibration_t green;
    uint32_t cal_timer;
    bool stabilization_period_complete;
    uint32_t stable_reading_count;
} ppg_calibration_state_t;

static void _init_led_calibration(led_calibration_t *cal) {
    cal->scaling_factor = DEFAULT_SF0;
    cal->adc_gain = DEFAULT_ADC_GAIN;  // Start at gain = 2
    cal->max_value = 0.0f;
    cal->cal_complete = false;
    cal->sample_count = 0;
    cal->last_max_ppg = 0.0f;

    // Initialize stabilization tracking
    memset(cal->recent_values, 0, sizeof(cal->recent_values));
    cal->value_index = 0;
    cal->is_stable = false;
}

// Check if signal is stable by examining variation in recent readings
static bool _is_signal_stable(led_calibration_t *cal, double new_value) {
    // Update the circular buffer of recent values
    cal->recent_values[cal->value_index] = new_value;
    cal->value_index = (cal->value_index + 1) % STABILIZATION_WINDOW_SIZE;

    // Only check for stability after we have enough samples
    if (cal->sample_count < STABILIZATION_WINDOW_SIZE) {
        return false;
    }

    // Find min and max values in the recent readings
    float min_val = cal->recent_values[0];
    float max_val = cal->recent_values[0];

    for (int i = 1; i < STABILIZATION_WINDOW_SIZE; i++) {
        if (cal->recent_values[i] < min_val) min_val = cal->recent_values[i];
        if (cal->recent_values[i] > max_val) max_val = cal->recent_values[i];
    }

    // Signal is considered stable if:
    // 1. Max variation is within threshold
    // 2. Signal level is above minimum threshold (meaning device is properly attached)
    bool intensity_ok = max_val > MIN_SIGNAL_INTENSITY;
    bool variation_ok = (max_val - min_val) / max_val < STABILIZATION_MAX_VARIATION;

    cal->is_stable = intensity_ok && variation_ok;
    return cal->is_stable;
}

static void _convert_raw_samples_for_psp(vitals_thread_t *p_thread) {
    static ppg_calibration_state_t cal_state = {0};
    static uint32_t samples_since_last_check = 0;

    // Initialize calibration state if needed
    if (cal_state.cal_timer == 0) {
        _init_led_calibration(&cal_state.red);
        _init_led_calibration(&cal_state.ir);
        _init_led_calibration(&cal_state.green);

        // Start with default scaling factors
        cal_state.red.scaling_factor = DEFAULT_SF0;
        cal_state.ir.scaling_factor = DEFAULT_SF0;  // Same as red for SpO2
        cal_state.green.scaling_factor = DEFAULT_SF0;

        // Start with default gain
        cal_state.red.adc_gain = DEFAULT_ADC_GAIN;
        cal_state.ir.adc_gain = DEFAULT_ADC_GAIN;
        cal_state.green.adc_gain = DEFAULT_ADC_GAIN;

        // Initialize stabilization tracking
        cal_state.stabilization_period_complete = false;
        cal_state.stable_reading_count = 0;
    }

    for (int i = 0; i < CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND; i++) {
        sensors_sample_t *raw = &p_thread->raw_samples_32Hz[i];
        psp_algorithm_input_metrics_t *psp = &p_thread->psp_input_samples_32Hz[i];

        // Convert to double for calculations
        double raw_red = (double)raw->ppg.red_intensity;
        double raw_ir = (double)raw->ppg.ir_intensity;
        double raw_green = (double)raw->ppg.green_intensity;

        // Track signal stability
        bool red_stable = _is_signal_stable(&cal_state.red, raw_red);
        bool ir_stable = _is_signal_stable(&cal_state.ir, raw_ir);
        bool green_stable = _is_signal_stable(&cal_state.green, raw_green);

        // Initial calibration period
        if (!cal_state.red.cal_complete) {
            // Track maximum values during calibration
            cal_state.red.max_value = fmax(cal_state.red.max_value, raw_red);
            cal_state.ir.max_value = fmax(cal_state.ir.max_value, raw_ir);
            cal_state.green.max_value = fmax(cal_state.green.max_value, raw_green);

            cal_state.red.sample_count++;
            cal_state.ir.sample_count++;
            cal_state.green.sample_count++;

            // Check if all signals are stable to complete calibration
            if (!cal_state.stabilization_period_complete && red_stable && ir_stable && green_stable) {
                cal_state.stable_reading_count++;

                // Only consider calibration complete after stable readings for half a second
                if (cal_state.stable_reading_count >= CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND / 2) {
                    cal_state.stabilization_period_complete = true;
                    LOG_INF("Signal stabilization complete after %d samples", cal_state.red.sample_count);
                }
            }

            // Only complete calibration after stabilization AND minimum calibration period
            if (cal_state.stabilization_period_complete &&
                cal_state.red.sample_count >= CALIBRATION_PERIOD_SEC * CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND) {
                // Calculate SF1 based on calibration period
                double max_value = fmax(cal_state.red.max_value, cal_state.ir.max_value);
                cal_state.red.scaling_factor = (PPG_MAX_VALUE / 2.0) / max_value;
                cal_state.ir.scaling_factor = cal_state.red.scaling_factor;  // Same as red for SpO2
                cal_state.green.scaling_factor = (PPG_MAX_VALUE / 2.0) / cal_state.green.max_value;

                cal_state.red.cal_complete = true;
                cal_state.ir.cal_complete = true;
                cal_state.green.cal_complete = true;
                p_thread->data_ready_for_psp = true;

                LOG_INF("Calibration complete - Scaling factors: R/IR=%.2f, G=%.2f",
                        (double)cal_state.red.scaling_factor,
                        (double)cal_state.green.scaling_factor);
            }
        }

        // Scale the signals
        double scaled_red = raw_red * cal_state.red.scaling_factor;
        double scaled_ir = raw_ir * cal_state.ir.scaling_factor;
        double scaled_green = raw_green * cal_state.green.scaling_factor;

        // Check for gain adjustment every second (32 samples)
        samples_since_last_check++;
        if (samples_since_last_check >= CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND) {
            samples_since_last_check = 0;

            // Check red channel (IR follows red's gain)
            if (scaled_red > PPG_MAX_VALUE * PPG_MAX_THRESHOLD_PERCENT) {
                if (cal_state.red.adc_gain > MIN_ADC_GAIN) {
                    cal_state.red.scaling_factor /= 2.0;
                    cal_state.ir.scaling_factor = cal_state.red.scaling_factor;  // Keep same for SpO2
                    cal_state.red.adc_gain--;
                    cal_state.ir.adc_gain = cal_state.red.adc_gain;
                }
            } else if (scaled_red < PPG_MAX_VALUE * PPG_MIN_THRESHOLD_PERCENT) {
                if (cal_state.red.adc_gain < MAX_ADC_GAIN) {
                    cal_state.red.scaling_factor *= 2.0;
                    cal_state.ir.scaling_factor = cal_state.red.scaling_factor;  // Keep same for SpO2
                    cal_state.red.adc_gain++;
                    cal_state.ir.adc_gain = cal_state.red.adc_gain;
                }
            }

            // Check green channel independently
            if (scaled_green > PPG_MAX_VALUE * PPG_MAX_THRESHOLD_PERCENT) {
                if (cal_state.green.adc_gain > MIN_ADC_GAIN) {
                    cal_state.green.scaling_factor /= 2.0;
                    cal_state.green.adc_gain--;
                }
            } else if (scaled_green < PPG_MAX_VALUE * PPG_MIN_THRESHOLD_PERCENT) {
                if (cal_state.green.adc_gain < MAX_ADC_GAIN) {
                    cal_state.green.scaling_factor *= 2.0;
                    cal_state.green.adc_gain++;
                }
            }

            // If signal becomes unstable after calibration, log warning but continue
            if (cal_state.red.cal_complete && (!red_stable || !ir_stable || !green_stable)) {
                LOG_WRN("Signal instability detected after calibration");
            }
        }

        // Clamp and store final values
        psp->ppg_red = (uint16_t)CLAMP(scaled_red, 0.0, PPG_MAX_VALUE);
        psp->ppg_ir = (uint16_t)CLAMP(scaled_ir, 0.0, PPG_MAX_VALUE);
        psp->ppg_green = (uint16_t)CLAMP(scaled_green, 0.0, PPG_MAX_VALUE);

        // Convert accelerometer values (unchanged)
        float accel_x_psp = raw->accel_x * ACCEL_G_TO_PSP_SCALE;
        float accel_y_psp = raw->accel_y * ACCEL_G_TO_PSP_SCALE;
        float accel_z_psp = raw->accel_z * ACCEL_G_TO_PSP_SCALE;

        psp->accel_x = (int16_t)CLAMP(accel_x_psp, ACCEL_PSP_MIN, ACCEL_PSP_MAX);
        psp->accel_y = (int16_t)CLAMP(accel_y_psp, ACCEL_PSP_MIN, ACCEL_PSP_MAX);
        psp->accel_z = (int16_t)CLAMP(accel_z_psp, ACCEL_PSP_MIN, ACCEL_PSP_MAX);
    }

    cal_state.cal_timer++;
}
