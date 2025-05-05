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

// Forward declaration for vitals callback
static void vitals_callback(const vitals_thread_callback_data_t *data, void *user_data);

int main(void) {
    // Configure vitals thread with callback and detection parameters
    static const vitals_thread_config_t vitals_config = {
        .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
        .p_imu_dev = DEVICE_DT_GET(DT_NODELABEL(lsm6dso0)),
        .p_temp_dev = DEVICE_DT_GET(DT_NODELABEL(paf9615)),

        // Add callback functionality
        .callback = vitals_callback,
        .callback_user_data = NULL,

        // Configure skin detection parameters
        .skin_temp_min_threshold_f = 90.0f,
        .skin_temp_max_threshold_f = 102.0f,
        .skin_detection_period_ms = 2000,
        .deskin_detection_period_ms = 3000,
    };

    // Allocate vitals thread
    static vitals_thread_t vitals_thread = {0};

    // Initialize vitals thread
    if (!vitals_thread_init(&vitals_config, &vitals_thread)) {
        LOG_ERR("Failed to initialize vitals thread");
        return -1;
    }

    // Configure bluetooth thread
    static const bluetooth_thread_config_t bluetooth_config = {
        .sensor_data_25hz_enabled = false,
        .sensor_data_32hz_enabled = true,
        .psp_input_data_32hz_enabled = false,
        .psp_read_input_data_32hz_enabled = true,
        .vitals_1hz_enabled = true,
    };

    // Allocate bluetooth thread
    static bluetooth_thread_t bluetooth_thread = {0};

    // Initialize bluetooth thread
    if (!bluetooth_thread_init(&bluetooth_config, &bluetooth_thread)) {
        LOG_ERR("Failed to initialize bluetooth thread");
        return -1;
    }

    LOG_INF("Alpha application started!");

    return 0;
}

/**
 * @brief Callback function for vitals thread events
 */
static void vitals_callback(const vitals_thread_callback_data_t *data, void *user_data) {
    // Handle state change events
    if (data->event == VITALS_EVENT_STATE_CHANGED) {
        LOG_INF("Vitals state changed to: %d", data->state);

        // React to state changes
        switch (data->state) {
            case VITALS_STATE_SKIN_CONFIRMED:
                LOG_INF("Skin contact confirmed");
                // Application can perform any necessary operations here
                break;

            case VITALS_STATE_ACTIVE_MONITORING:
                LOG_INF("Active monitoring started");
                break;

            case VITALS_STATE_DESKIN_CONFIRMED:
                LOG_INF("Skin contact lost");
                break;

            default:
                // Handle other states as needed
                break;
        }
    }

    // Handle metrics update events
    if (data->event == VITALS_EVENT_METRICS_UPDATED) {
        const vitals_output_metrics_t *metrics = &data->metrics;

        // Process updated metrics
        if (metrics->heart_rate_updated) {
            LOG_INF("Heart rate: %d bpm (quality: %d)",
                    metrics->heart_rate, metrics->heart_rate_quality);
        }

        if (metrics->spo2_updated) {
            LOG_INF("SpO2: %d%% (quality: %d)",
                    metrics->spo2, metrics->spo2_quality);
        }

        if (metrics->temperature_updated) {
            LOG_INF("Temperature: %.1f°F", metrics->temperature_f);
        }
    }
}