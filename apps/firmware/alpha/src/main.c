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

/*---------------------------------------------------------------------------
 * Motion Detection Thread
 *---------------------------------------------------------------------------*/

#define MOTION_THREAD_STACK_SIZE 1024
#define MOTION_THREAD_PRIORITY 7

static K_THREAD_STACK_DEFINE(motion_thread_stack, MOTION_THREAD_STACK_SIZE);
static struct k_thread motion_thread_data;
static struct k_sem motion_sem;
static const struct device* imu_dev;

// Forward declarations for helper functions
static void handle_vsm_callback(const vitals_thread_callback_data_t* data, void* user_data);
static void process_vitals_metrics(const vitals_output_metrics_t* metrics);
static void motion_trigger_handler(const struct device* dev, const struct sensor_trigger* trig);
static void motion_thread_entry(void* p1, void* p2, void* p3);

// Global variables
static vsm_t g_vsm = {0};
static struct k_sem g_vsm_hw_error_sem;

static void handle_vsm_callback(const vitals_thread_callback_data_t* data, void* user_data) {
    // Process based on event type
    switch (data->event) {
        case VITALS_EVENT_HW_ERROR:
            // Handle hardware error
            LOG_ERR("PPG Sensor Error: %d", data->hw_error.ppg_sensor_error);
            LOG_ERR("PPG Watchdog Timeout: %d", data->hw_error.ppg_watchdog_timeout);
            LOG_ERR("IMU Sensor Error: %d", data->hw_error.imu_sensor_error);
            LOG_ERR("Temp Sensor Error: %d", data->hw_error.temp_sensor_error);

            k_sem_give(&g_vsm_hw_error_sem);
            break;

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

                case VITALS_STATE_SHUTDOWN:
                    // Shutdown state, do nothing
                    LOG_WRN("Shutting down");
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

static void process_vitals_metrics(const vitals_output_metrics_t* metrics) {
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

/*---------------------------------------------------------------------------
 * Motion Detection
 *---------------------------------------------------------------------------*/

/**
 * @brief Motion trigger callback - called from driver context
 *
 * This callback is invoked by the LSM6DSO driver when motion is detected.
 * It signals the motion thread to wake up and process the event.
 */
static void motion_trigger_handler(const struct device* dev, const struct sensor_trigger* trig) {
    ARG_UNUSED(dev);
    ARG_UNUSED(trig);

    k_sem_give(&motion_sem);
}

/**
 * @brief Motion detection thread entry point
 *
 * Waits for motion events from the IMU sensor and logs them.
 * This thread demonstrates how to use the sensor trigger API
 * for motion-based wake-up detection.
 */
static void motion_thread_entry(void* p1, void* p2, void* p3) {
    ARG_UNUSED(p1);
    ARG_UNUSED(p2);
    ARG_UNUSED(p3);

    uint32_t motion_count = 0;

    LOG_INF("Motion detection thread started");

    while (1) {
        /* Wait for motion event */
        k_sem_take(&motion_sem, K_FOREVER);

        motion_count++;
        LOG_INF("Motion detected! (count: %u)", motion_count);

        /*
         * Application can perform actions here such as:
         * - Wake up from low power mode
         * - Start or stop monitoring
         * - Log activity data
         * - Send notification over BLE
         */
    }
}

/**
 * @brief Initialize motion detection
 *
 * Sets up the IMU sensor for motion detection and starts the motion thread.
 *
 * Motion detection parameters:
 *   - Threshold (SENSOR_ATTR_SLOPE_TH): Sensitivity in milli-g
 *     Lower = more sensitive (e.g., 100mg detects subtle movement)
 *     Higher = less sensitive (e.g., 500mg requires strong shake)
 *     The driver auto-scales based on current accelerometer range setting.
 *
 *   - Duration (SENSOR_ATTR_SLOPE_DUR): Minimum motion duration in milliseconds
 *     Filters out brief vibrations/noise. Set to 0 for instant detection.
 *     The driver converts to ODR cycles based on current sampling rate.
 *     Hardware limit: ~60ms max at 52Hz ODR (3 cycles).
 *
 * @return 0 on success, negative errno on failure
 */
static int init_motion_detection(void) {
    int ret;
    struct sensor_trigger trig = {
        .type = SENSOR_TRIG_MOTION,
        .chan = SENSOR_CHAN_ACCEL_XYZ,
    };

    /* Get the IMU device */
    imu_dev = DEVICE_DT_GET(DT_NODELABEL(lsm6dso0));
    if (!device_is_ready(imu_dev)) {
        LOG_ERR("IMU device not ready for motion detection");
        return -ENODEV;
    }

    /* Initialize semaphore */
    k_sem_init(&motion_sem, 0, K_SEM_MAX_LIMIT);

    /*
     * Configure motion detection sensitivity (threshold in milli-g).
     * The driver internally handles different accelerometer range settings.
     * Typical values: 100-500 mg depending on application sensitivity needs.
     */
    struct sensor_value threshold = {.val1 = 200, .val2 = 0}; /* 200 mg */
    ret = sensor_attr_set(imu_dev, SENSOR_CHAN_ACCEL_XYZ,
                          SENSOR_ATTR_SLOPE_TH, &threshold);
    if (ret < 0) {
        LOG_WRN("Failed to set motion threshold: %d (using default)", ret);
    }

    /*
     * Configure motion detection duration (minimum time above threshold in ms).
     * The driver internally converts to ODR cycles based on current sampling rate.
     * Typical values: 0 (instant), 20-60 ms to filter noise.
     */
    struct sensor_value duration = {.val1 = 40, .val2 = 0}; /* 40 ms */
    ret = sensor_attr_set(imu_dev, SENSOR_CHAN_ACCEL_XYZ,
                          SENSOR_ATTR_SLOPE_DUR, &duration);
    if (ret < 0) {
        LOG_WRN("Failed to set motion duration: %d (using default)", ret);
    }

    /* Set motion trigger handler */
    ret = sensor_trigger_set(imu_dev, &trig, motion_trigger_handler);
    if (ret < 0) {
        LOG_ERR("Failed to set motion trigger: %d", ret);
        return ret;
    }

    /* Start motion thread */
    k_thread_create(&motion_thread_data, motion_thread_stack,
                    MOTION_THREAD_STACK_SIZE,
                    motion_thread_entry, NULL, NULL, NULL,
                    MOTION_THREAD_PRIORITY, 0, K_NO_WAIT);
    k_thread_name_set(&motion_thread_data, "motion");

    LOG_INF("Motion detection initialized (threshold: %d mg, duration: %d ms)",
            threshold.val1, duration.val1);
    return 0;
}

int main(void) {
    static const vsm_config_t vsm_cfg = {
        .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
        .p_imu_dev = DEVICE_DT_GET(DT_NODELABEL(lsm6dso0)),
        .p_temp_dev = DEVICE_DT_GET(DT_NODELABEL(mlx90614)),
        .p_ppg_enable_gpio = GPIO_DT_SPEC_GET(DT_ALIAS(vsm_enable), gpios),
        .callback = handle_vsm_callback,
        .callback_user_data = NULL,
        .skin_temp_min_threshold_f = 80.0f,
        .skin_temp_max_threshold_f = 100.0f,
        .skin_detection_period_ms = 1000,
        .deskin_detection_period_ms = 6000,
    };

    k_sem_init(&g_vsm_hw_error_sem, 0, 1);

    if (!vsm_init(&vsm_cfg, &g_vsm)) {
        LOG_ERR("VSM init failed - halting");
        while (1) {
            k_sleep(K_FOREVER);
        }
    }

    LOG_INF("VSM ready");

    /* Initialize motion detection */
    int motion_ret = init_motion_detection();
    if (motion_ret < 0) {
        LOG_WRN("Motion detection init failed: %d (continuing without it)", motion_ret);
    }

    // Wait for hardware error
    k_sem_take(&g_vsm_hw_error_sem, K_FOREVER);
    LOG_ERR("HW error - halting");
    vsm_deinit(&g_vsm);

    while (1) {
        k_sleep(K_FOREVER);
    }

    return 0;
}