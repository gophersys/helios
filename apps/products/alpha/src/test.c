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
#include <corekinect/sensor/pah8151/PAH8151/pah_factory_test/pah_815x_factory_test_v1.h>
#include <corekinect/sensor/pah8151/pah8151.h>

LOG_MODULE_REGISTER(alpha, 4);

int main(void) {
    int rc;
    rc = pah8151_init(DEVICE_DT_GET(DT_NODELABEL(pah8151)));
    if (rc != 0) {
        LOG_ERR("Failed to initialize PPG sensor: %s", strerror(-rc));
        return -1;
    }

    // Ensure the devices are ready
    if (!device_is_ready(DEVICE_DT_GET(DT_NODELABEL(pah8151)))) {
        LOG_ERR("PPG device not ready");
        return -1;
    }

    uint8_t sensor_pid = 0;
    pah_815x_read_id(&sensor_pid);

    if (sensor_pid == 0x51) {
        LOG_INF("ID Check Success. Sensor_pid = 0x%x \n\n", sensor_pid);
    } else {
        LOG_ERR("ID Check Fail.    Sensor_pid = 0x%x \n\n", sensor_pid);
    }

    // // INT_TEST
    // demo_factory_mode(INT_TEST, 0, 0, 0, 0);
    // // Check_Brightness_FPC_Only
    // demo_factory_mode(Check_Brightness_FPC_Only, 0, 0, 0, 0);

    // Light_Leak_Test
    while (1) {
        demo_factory_mode(Light_Leak_Test, 0, 0, 0, 0);
        k_msleep(500);
    }

    // // Check_Brightness_with_mechanical_cover
    // demo_factory_mode(Check_Brightness_with_mechanical_cover, 0x45, 0x45, 0x45, 0x45);

    // // Check_Power Noise
    // demo_factory_mode(Power_Noise_Test, 0, 0, 0, 0);
    // k_msleep(5000);

    // // Stop Factory Test
    // demo_factory_mode(Factory_Test_Stop, 0, 0, 0, 0);

    // Cap Full Channel &SNR Test //
    // Full_Channel_SNR_Test();

    return 0;
}
