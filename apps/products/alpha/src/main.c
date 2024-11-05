// Standard includes
#include <stdbool.h>
#include <stdio.h>

// Zephyr includes
#include <corekinect/sensor/pah8151.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Application includes
#include "threads/vitals/thread.h"

// PSP library includes
#include "../lib/inc/fx_datatypes.h"
#include "../lib/inc/psp.h"

LOG_MODULE_REGISTER(app, 4);

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

    LOG_INF("Alpha application started!");

    return 0;
}
