// Standard includes
#include <stdbool.h>
#include <stdio.h>

// Zephyr includes
#include <corekinect/sensor/pah8151.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Application includes
#include "threads/bluetooth/thread.h"
#include "threads/vitals/thread.h"

LOG_MODULE_REGISTER(alpha, 4);

static void scan_i2c_bus(const struct device *dev) {
    uint8_t error_count = 0;
    uint8_t addr;
    uint8_t dummy_data = 0;

    /* Skip addresses reserved for 10-bit addressing */
    for (addr = 0x08; addr < 0x78; addr++) {
        int result = i2c_write(dev, &dummy_data, 1, addr);

        if (result == 0) {
            LOG_INF("I2C device found at address 0x%02x", addr);
        } else {
            error_count++;
        }
    }

    LOG_INF("I2C scan completed, %d addresses responded", (0x78 - 0x08) - error_count);
}

int main(void) {
    // Dump all devices on the I2C bus
    const struct device *i2c_dev = DEVICE_DT_GET(DT_NODELABEL(i2c1));
    scan_i2c_bus(i2c_dev);

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
