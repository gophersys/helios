/*
 * Example usage of the MLX90614 IR temperature sensor driver
 */

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/sensor/mlx90614/mlx90614.h>

LOG_MODULE_REGISTER(mlx90614_example, CONFIG_SENSOR_LOG_LEVEL);

/* Device tree node for the MLX90614 sensor */
#define MLX90614_DEVICE DT_NODELABEL(mlx90614)

void mlx90614_example(void) {
    const struct device *dev = DEVICE_DT_GET(MLX90614_DEVICE);
    struct sensor_value temp_ambient, temp_object;
    int ret;

    if (!device_is_ready(dev)) {
        LOG_ERR("MLX90614 device not ready");
        return;
    }

    LOG_INF("MLX90614 IR Temperature Sensor Example");
    LOG_INF("======================================");

    while (1) {
        uint32_t start_time = k_uptime_get();

        /* Fetch temperature data */
        ret = sensor_sample_fetch(dev);
        if (ret < 0) {
            LOG_ERR("Failed to fetch sensor data: %d", ret);
            k_sleep(K_MSEC(1000));
            continue;
        }

        /* Get ambient temperature */
        ret = sensor_channel_get(dev, SENSOR_CHAN_AMBIENT_TEMP, &temp_ambient);
        if (ret < 0) {
            LOG_ERR("Failed to get ambient temperature: %d", ret);
        } else {
            LOG_INF("Ambient Temperature: %d.%06d°C",
                    temp_ambient.val1, temp_ambient.val2);
        }

        /* Get object temperature */
        ret = sensor_channel_get(dev, SENSOR_CHAN_OBJECT_TEMP, &temp_object);
        if (ret < 0) {
            LOG_ERR("Failed to get object temperature: %d", ret);
        } else {
            LOG_INF("Object Temperature: %d.%06d°C",
                    temp_object.val1, temp_object.val2);
        }

        uint32_t end_time = k_uptime_get();
        LOG_INF("Time taken: %d ms", (end_time - start_time));

        LOG_INF("---");
        k_sleep(K_MSEC(1000)); /* Read every 1 second */
    }
}

/* Example of setting emissivity */
void mlx90614_set_emissivity_example(void) {
    const struct device *dev = DEVICE_DT_GET(MLX90614_DEVICE);
    struct sensor_value emissivity;
    int ret;

    if (!device_is_ready(dev)) {
        LOG_ERR("MLX90614 device not ready");
        return;
    }

    /* Set emissivity to 0.95 (95%) */
    sensor_value_from_double(&emissivity, 0.95);

    ret = sensor_attr_set(dev, SENSOR_CHAN_OBJECT_TEMP,
                          SENSOR_ATTR_CALIBEMISSIVITY, &emissivity);
    if (ret < 0) {
        LOG_ERR("Failed to set emissivity: %d", ret);
    } else {
        LOG_INF("Emissivity set to 0.95");
    }

    /* Read back the emissivity setting */
    ret = sensor_attr_get(dev, SENSOR_CHAN_OBJECT_TEMP,
                          SENSOR_ATTR_CALIBEMISSIVITY, &emissivity);
    if (ret < 0) {
        LOG_ERR("Failed to get emissivity: %d", ret);
    } else {
        LOG_INF("Current emissivity: %d.%06d",
                emissivity.val1, emissivity.val2);
    }
}

int main(void) {
    // mlx90614_set_emissivity_example();
    mlx90614_example();
    return 0;
}