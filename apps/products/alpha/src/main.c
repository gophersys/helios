// Standard includes
#include <stdbool.h>
#include <stdio.h>

// Zephyr includes
#include <corekinect/sensor/pah8151.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>       `
#include <zephyr/logging/log.h>

// Application includes
#include "threads/bluetooth/thread.h"
#include "threads/vitals/thread.h"

// Add after other includes
#include <zephyr/kernel.h>

LOG_MODULE_REGISTER(alpha, 4);

int main(void) {
    // Configure vitals thread
    static const vitals_thread_config_t vitals_config = {
        .p_ppg_dev = DEVICE_DT_GET(DT_NODELABEL(pah8151)),
        .p_imu_dev = DEVICE_DT_GET(DT_NODELABEL(lsm6dso0)),
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
        .ppg_data_enabled = false,
        .accel_data_enabled = false,
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
