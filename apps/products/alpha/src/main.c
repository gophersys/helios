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
#include <zephyr/pm/pm.h>

// Application includes
#include <corekinect/module/vsm/vsm.h>

LOG_MODULE_REGISTER(alpha, 4);

// Forward declarations for helper functions
static void handle_vsm_callback(const vitals_thread_callback_data_t *data, void *user_data);
static void process_vitals_metrics(const vitals_output_metrics_t *metrics);

// Global variables
static vsm_t g_vsm = {0};

static void handle_vsm_callback(const vitals_thread_callback_data_t *data, void *user_data) {
    // Process based on event type
    switch (data->event) {
        case VITALS_EVENT_STATE_CHANGED:
            // Handle state transitions
            switch (data->state) {
                case VITALS_STATE_IDLE:
                    // Idle state, do nothing
                    break;

                case VITALS_STATE_TOUCH_DETECTED:
                    // Touch detected, do nothing
                    LOG_WRN("Touch detected, beginning skin detection");
                    break;

                case VITALS_STATE_SKIN_CONFIRMED:
                    // Skin contact confirmed, activate full monitoring
                    LOG_WRN("Skin contact confirmed, activating monitoring");
                    vsm_activate_monitoring(&g_vsm);
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
                    // vsm_deactivate_monitoring(&g_vsm);
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
}

int main(void) {
    // Configure vitals thread with callback and detection parameters
    static const vsm_config_t vsm_cfg = {
        // Hardware devices
        .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
        .p_imu_dev = DEVICE_DT_GET(DT_NODELABEL(lsm6dso0)),
        .p_temp_dev = DEVICE_DT_GET(DT_NODELABEL(mlx90614)),
        .p_ppg_enable_gpio = GPIO_DT_SPEC_GET(DT_ALIAS(vsm_enable), gpios),

        // Application callback
        .callback = handle_vsm_callback,
        .callback_user_data = NULL,

        // Skin detection parameters
        .skin_temp_min_threshold_f = 70.0f,
        .skin_temp_max_threshold_f = 100.0f,
        .skin_detection_period_ms = 1000,
        .deskin_detection_period_ms = 6000,
    };

    // Initialize vitals thread
    if (!vsm_init(&vsm_cfg, &g_vsm)) {
        LOG_ERR("Failed to initialize vitals thread");
        return -1;
    }

    // Main application loop
    while (1) {
        // // Initialize vitals thread
        // if (!vsm_init(&vsm_cfg, &g_vsm)) {
        //     LOG_ERR("Failed to initialize vitals thread");
        //     return -1;
        // }

        // LOG_INF("VSM module is ready to use");
        // k_sleep(K_SECONDS(20));
        // LOG_INF("Shutting down VSM module");

        // if (!vsm_deinit(&g_vsm)) {
        //     LOG_ERR("Failed to deinitialize vitals thread");
        //     return -1;
        // }

        k_sleep(K_SECONDS(20));
    }

    return 0;
}