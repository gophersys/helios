/**
 * @file main_fail.c
 * @brief VSM + Cross-talk test cycle to verify PAH8151 re-init
 *
 * Scenario:
 * 1. VSM init and run for 10 seconds
 * 2. VSM deinit
 * 3. Run actual cross-talk test (like test_cross_talk.c)
 * 4. Return to VSM functionality
 */

#include <stdbool.h>
#include <stdio.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <corekinect/module/vsm/vsm.h>
#include <corekinect/sensors/pah8151/pah8151.h>

LOG_MODULE_REGISTER(main_fail, LOG_LEVEL_DBG);

// ANSI color codes for terminal output
#define ANSI_RED "\033[31m"
#define ANSI_GREEN "\033[32m"
#define ANSI_RESET "\033[0m"
#define ANSI_BOLD "\033[1m"

static vsm_t g_vsm = {0};
static volatile int g_cycle_count = 0;

static void handle_vsm_callback(const vitals_thread_callback_data_t *data, void *user_data) {
    switch (data->event) {
        case VITALS_EVENT_HW_ERROR:
            LOG_ERR("HW Error - PPG:%d IMU:%d Temp:%d Watchdog:%d",
                    data->hw_error.ppg_sensor_error,
                    data->hw_error.imu_sensor_error,
                    data->hw_error.temp_sensor_error,
                    data->hw_error.ppg_watchdog_timeout);
            break;

        case VITALS_EVENT_STATE_CHANGED:
            LOG_INF("State changed: %d", data->state);
            if (data->state == VITALS_STATE_SKIN_CONFIRMED) {
                LOG_INF("Skin confirmed - activating monitoring");
                vsm_activate_monitoring(&g_vsm);
            }
            break;

        case VITALS_EVENT_METRICS_UPDATED:
            if (data->metrics.heart_rate_updated) {
                LOG_INF("HR: %d bpm (quality: %d)",
                        data->metrics.heart_rate,
                        data->metrics.heart_rate_quality);
            }
            break;

        default:
            break;
    }
}

static void print_cross_talk_results(const vsm_test_cross_talk_result_t *result) {
    LOG_INF("=== Cross-Talk Test Results ===");
    if (result->passed) {
        LOG_INF("%s%sOverall: PASSED%s", ANSI_BOLD, ANSI_GREEN, ANSI_RESET);
    } else {
        LOG_ERR("%s%sOverall: FAILED%s", ANSI_BOLD, ANSI_RED, ANSI_RESET);
    }

    LOG_INF("Green: %ld (threshold: %ld) %s",
            (long)result->green.raw_count,
            (long)result->green.threshold,
            result->green.passed ? "PASS" : "FAIL");

    LOG_INF("Red: %ld (threshold: %ld) %s",
            (long)result->red.raw_count,
            (long)result->red.threshold,
            result->red.passed ? "PASS" : "FAIL");

    LOG_INF("IR: %ld (threshold: %ld) %s",
            (long)result->ir.raw_count,
            (long)result->ir.threshold,
            result->ir.passed ? "PASS" : "FAIL");
}

static bool run_vsm_cycle(int duration_sec) {
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

    LOG_INF("=== VSM INIT (cycle %d) ===", g_cycle_count);

    if (!vsm_init(&vsm_cfg, &g_vsm)) {
        LOG_ERR("VSM init FAILED");
        return false;
    }
    LOG_INF("VSM init OK");

    LOG_INF("Running VSM for %d seconds...", duration_sec);
    k_sleep(K_SECONDS(duration_sec));

    LOG_INF("=== VSM DEINIT ===");
    if (!vsm_deinit(&g_vsm)) {
        LOG_ERR("VSM deinit FAILED");
        return false;
    }
    LOG_INF("VSM deinit OK");

    k_sleep(K_MSEC(500));
    return true;
}

static bool run_cross_talk_test(void) {
    static const struct gpio_dt_spec ppg_enable = GPIO_DT_SPEC_GET(DT_ALIAS(vsm_enable), gpios);

    LOG_INF("=== CROSS-TALK TEST ===");

    /* Turn on PPG power (VSM deinit turned it off) */
    LOG_INF("Enabling PPG power GPIO...");
    int rc = gpio_pin_configure_dt(&ppg_enable, GPIO_OUTPUT_ACTIVE);
    if (rc != 0) {
        LOG_ERR("Failed to enable PPG power: %d", rc);
        return false;
    }
    k_sleep(K_MSEC(50));

    /* Run the actual cross-talk test */
    static const vsm_test_cross_talk_config_t cross_talk_config = {
        .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
    };

    LOG_INF("Running cross-talk test (cover sensor with black rubber)...");
    vsm_test_cross_talk_result_t result = vsm_test_cross_talk(&cross_talk_config);

    /* Print results */
    print_cross_talk_results(&result);

    /*
     * NOTE: No pah8151_deinit() call needed here.
     * The cross-talk test now uses direct register access without initializing
     * the driver, so the sensor is left in a clean powered-down state ready
     * for the next pah8151_init() call by VSM.
     */

    /* Keep power on for next VSM init */
    k_sleep(K_MSEC(500));

    return true;
}

int main(void) {
    LOG_INF("========================================");
    LOG_INF("  VSM + Cross-Talk Test Cycle");
    LOG_INF("========================================");

    while (1) {
        g_cycle_count++;
        LOG_INF("");
        LOG_INF("############### CYCLE %d ###############", g_cycle_count);

        /* Phase 1: VSM for 10 seconds */
        LOG_INF("--- Phase 1: VSM Operation (10s) ---");
        if (!run_vsm_cycle(10)) {
            LOG_ERR("VSM cycle failed at cycle %d", g_cycle_count);
            break;
        }

        /* Phase 2: Cross-talk test */
        LOG_INF("--- Phase 2: Cross-Talk Test ---");
        if (!run_cross_talk_test()) {
            LOG_ERR("Cross-talk test failed at cycle %d", g_cycle_count);
            break;
        }

        /* Phase 3: Back to VSM for 10 seconds */
        LOG_INF("--- Phase 3: Back to VSM (10s) ---");
        if (!run_vsm_cycle(10)) {
            LOG_ERR("Second VSM cycle failed at cycle %d", g_cycle_count);
            break;
        }

        LOG_INF("");
        LOG_INF("Cycle %d completed successfully!", g_cycle_count);
        LOG_INF("Waiting 2 seconds before next cycle...");
        k_sleep(K_SECONDS(2));
    }

    LOG_ERR("Test ended - stuck at cycle %d", g_cycle_count);
    while (1) {
        k_sleep(K_FOREVER);
    }

    return 0;
}
