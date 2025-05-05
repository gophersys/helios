// Standard includes
#include <stdbool.h>
#include <stdio.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Application includes
#include <corekinect/module/vsm/vsm.h>

LOG_MODULE_REGISTER(alpha, 4);

// Forward declarations for helper functions
static void handle_vitals_callback(const vitals_thread_callback_data_t *data, void *user_data);
static void process_vitals_metrics(const vitals_output_metrics_t *metrics);

// Global variables
static vitals_thread_t g_vitals_thread = {0};

/**
 * @brief Handler for vitals thread callback events
 */
static void handle_vitals_callback(const vitals_thread_callback_data_t *data, void *user_data) {
    // Process based on event type
    switch (data->event) {
        case VITALS_EVENT_STATE_CHANGED:
            // Handle state transitions
            switch (data->state) {
                case VITALS_STATE_IDLE:
                    // Idle state, do nothing
                    LOG_WRN("Vitals thread is idle");
                    break;

                case VITALS_STATE_TOUCH_DETECTED:
                    // Touch detected, do nothing
                    LOG_WRN("Touch detected, beginning skin detection");
                    break;

                case VITALS_STATE_SKIN_CONFIRMED:
                    // Skin contact confirmed, activate full monitoring
                    LOG_WRN("Skin contact confirmed, activating monitoring");
                    vitals_thread_activate_monitoring(&g_vitals_thread);
                    break;

                case VITALS_STATE_ACTIVE_MONITORING:
                    // Active monitoring, do nothing
                    LOG_WRN("Active monitoring");
                    break;

                case VITALS_STATE_TOUCH_LOST:
                    // Touch lost, do nothing
                    LOG_WRN("Touch lost, beginning deskin detection");
                    break;

                case VITALS_STATE_DESKIN_CONFIRMED:
                    // Skin contact lost, deactivate monitoring
                    LOG_WRN("Skin contact lost, deactivating monitoring");
                    // vitals_thread_deactivate_monitoring(&g_vitals_thread);
                    break;

                default:
                    LOG_ERR("Unknown vitals thread state: %d", data->state);
                    break;
            }
            break;

        case VITALS_EVENT_METRICS_UPDATED:
            // Process updated metrics
            process_vitals_metrics(&data->metrics);
            break;

        default:
            LOG_WRN("Unknown vitals event: %d", data->event);
            break;
    }
}

/**
 * @brief Process updated vitals metrics
 */
static void process_vitals_metrics(const vitals_output_metrics_t *metrics) {
    // Check which metrics were updated and process them
    if (metrics->heart_rate_updated) {
        LOG_INF("Heart rate updated: %d bpm (quality: %d)", metrics->heart_rate, metrics->heart_rate_quality);
    }

    if (metrics->spo2_updated) {
        LOG_INF("SpO2 updated: %d%% (quality: %d)", metrics->spo2, metrics->spo2_quality);
    }

    if (metrics->temperature_updated) {
        LOG_INF("Temperature updated: %.1f°F", (double)metrics->temperature_f);
    }

    // Send metrics to other subsystems as needed
    // ...
}

int main(void) {
    // Configure vitals thread with callback and detection parameters
    static const vitals_thread_config_t vitals_config = {
        // Hardware devices
        .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
        .p_imu_dev = DEVICE_DT_GET(DT_NODELABEL(lsm6dso0)),
        .p_temp_dev = DEVICE_DT_GET(DT_NODELABEL(paf9615)),

        // Application callback
        .callback = handle_vitals_callback,
        .callback_user_data = NULL,  // No user data needed in this example

        // Skin detection parameters
        .skin_temp_min_threshold_f = 70.0f,
        .skin_temp_max_threshold_f = 100.0f,
        .skin_detection_period_ms = 1000,
        .deskin_detection_period_ms = 6000,
    };

    // Initialize vitals thread
    if (!vitals_thread_init(&vitals_config, &g_vitals_thread)) {
        LOG_ERR("Failed to initialize vitals thread");
        return -1;
    }

    // // Configure bluetooth thread
    // static const bluetooth_thread_config_t bluetooth_config = {
    //     .sensor_data_25hz_enabled = false,
    //     .sensor_data_32hz_enabled = true,
    //     .psp_input_data_32hz_enabled = false,
    //     .psp_read_input_data_32hz_enabled = true,
    //     .vitals_1hz_enabled = true,

    // };

    // // Allocate bluetooth thread
    // static bluetooth_thread_t bluetooth_thread = {0};

    // // Initialize bluetooth thread
    // if (!bluetooth_thread_init(&bluetooth_config, &bluetooth_thread)) {
    //     LOG_ERR("Failed to initialize bluetooth thread");
    //     return -1;
    // }

    // LOG_INF("Alpha application started!");

    // Main application loop
    while (1) {
        // Application logic
        k_sleep(K_MSEC(100));
    }

    return 0;
}