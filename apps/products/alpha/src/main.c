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

int main(void) {
    // Configure vitals thread
    static const vitals_thread_config_t vitals_config = {
        .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
        .p_imu_dev = DEVICE_DT_GET(DT_NODELABEL(lsm6dso0)),
        .p_temp_dev = DEVICE_DT_GET(DT_NODELABEL(paf9615)),
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
