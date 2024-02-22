// Standard includes
#include <stdio.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>

// CoreKinect includes
#include <corekinect/wifi/wifi.h>

LOG_MODULE_REGISTER(app);

#define SSID "CoreKinect_Guest"
#define PSK  "Core_Kinect_8436"

static struct wifi_connect_req_params conn_params =
{
    .ssid = SSID,
    .ssid_length = strlen(SSID),
    .psk = PSK,
    .psk_length = strlen(PSK),
};

const struct device *inas[] =
{
    DEVICE_DT_GET(DT_NODELABEL(ina219_41)),
    DEVICE_DT_GET(DT_NODELABEL(ina219_44)),
    DEVICE_DT_GET(DT_NODELABEL(ina219_45))
};

void read_ina219_data(const struct device *ina)
{
    struct sensor_value v_bus, power, current;
    int rc = sensor_sample_fetch(ina);
    if (rc)
    {
        LOG_ERR("Could not fetch sensor data from %s.\n", ina->name);
        return;
    }

    sensor_channel_get(ina, SENSOR_CHAN_VOLTAGE, &v_bus);
    sensor_channel_get(ina, SENSOR_CHAN_POWER, &power);
    sensor_channel_get(ina, SENSOR_CHAN_CURRENT, &current);

    LOG_INF("Device %s -- Bus: %d.%06d V -- Power: %d.%06d W -- Current: %d.%06d A",
            ina->name, v_bus.val1, v_bus.val2, power.val1, power.val2, current.val1, current.val2);
}

int main(void)
{
    if (!wifi_init())
    {
        LOG_ERR("Could not initialize Wi-Fi interface for %s", CONFIG_BOARD);
        k_fatal_halt(0);
    }

    if (!wifi_connect(&conn_params))
    {
        LOG_ERR("Could not connect to Wi-Fi");
        k_fatal_halt(0);
    }

    for (int i = 0; i < sizeof(inas) / sizeof(inas[0]); i++)
    {
        if (!device_is_ready(inas[i]))
        {
            LOG_ERR("Device %s is not ready.\n", inas[i]->name);
            return 0;
        }
    }

    while (true)
    {
        for (int i = 0; i < sizeof(inas) / sizeof(inas[0]); i++)
        {
            read_ina219_data(inas[i]);
        }
        k_sleep(K_MSEC(1000));
    }

    return 0;
}