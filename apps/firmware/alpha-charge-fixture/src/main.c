#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(charge_fixture, LOG_LEVEL_INF);

/* Current limits in milliamps */
#define CURRENT_MIN_MA 180
#define CURRENT_MAX_MA 250

/* LED flash period in ms */
#define FLASH_PERIOD_MS 300

/* Sensor read interval in ms */
#define READ_INTERVAL_MS 500

static const struct gpio_dt_spec green_led = GPIO_DT_SPEC_GET(DT_ALIAS(green_led), gpios);
static const struct gpio_dt_spec red_led = GPIO_DT_SPEC_GET(DT_ALIAS(red_led), gpios);
static const struct device* ina219 = DEVICE_DT_GET(DT_NODELABEL(ina219));

enum fixture_state {
    STATE_IN_RANGE,
    STATE_OUT_OF_RANGE,
    STATE_ERROR,
};

static void leds_off(void) {
    gpio_pin_set_dt(&green_led, 0);
    gpio_pin_set_dt(&red_led, 0);
}

static void flash_leds(enum fixture_state state) {
    switch (state) {
        case STATE_IN_RANGE:
            gpio_pin_set_dt(&green_led, 1);
            gpio_pin_set_dt(&red_led, 0);
            break;
        case STATE_OUT_OF_RANGE:
            gpio_pin_set_dt(&green_led, 0);
            gpio_pin_set_dt(&red_led, 1);
            break;
        case STATE_ERROR:
            gpio_pin_set_dt(&green_led, 1);
            gpio_pin_set_dt(&red_led, 1);
            break;
    }

    k_msleep(FLASH_PERIOD_MS);
    leds_off();
    k_msleep(FLASH_PERIOD_MS);
}

static void error_loop(void) {
    LOG_ERR("Entering error state - reset to recover");
    while (1) {
        flash_leds(STATE_ERROR);
    }
}

int main(void) {
    int ret;
    struct sensor_value current_val;
    double current_ma;

    LOG_INF("Alpha Charge Fixture starting");
    LOG_INF("Limits: %d mA - %d mA", CURRENT_MIN_MA, CURRENT_MAX_MA);

    /* Configure LEDs */
    if (!gpio_is_ready_dt(&green_led) || !gpio_is_ready_dt(&red_led)) {
        LOG_ERR("LED device not ready");
        return -1;
    }

    ret = gpio_pin_configure_dt(&green_led, GPIO_OUTPUT_INACTIVE);
    if (ret < 0) {
        LOG_ERR("Failed to configure green LED: %d", ret);
        return -1;
    }

    ret = gpio_pin_configure_dt(&red_led, GPIO_OUTPUT_INACTIVE);
    if (ret < 0) {
        LOG_ERR("Failed to configure red LED: %d", ret);
        return -1;
    }

    /* Check INA219 */
    if (!device_is_ready(ina219)) {
        LOG_ERR("INA219 device not ready");
        error_loop();
    }

    LOG_INF("All devices ready, starting measurement loop");

    while (1) {
        ret = sensor_sample_fetch(ina219);
        if (ret < 0) {
            LOG_ERR("Failed to fetch sensor data: %d", ret);
            error_loop();
        }

        ret = sensor_channel_get(ina219, SENSOR_CHAN_CURRENT, &current_val);
        if (ret < 0) {
            LOG_ERR("Failed to get current channel: %d", ret);
            error_loop();
        }

        current_ma = sensor_value_to_double(&current_val) * 1000.0;

        if (current_ma >= CURRENT_MIN_MA && current_ma <= CURRENT_MAX_MA) {
            LOG_INF("Current: %.1f mA [OK]", current_ma);
            gpio_pin_set_dt(&green_led, 1);
            gpio_pin_set_dt(&red_led, 0);
        } else {
            LOG_WRN("Current: %.1f mA [OUT OF RANGE]", current_ma);
            flash_leds(STATE_OUT_OF_RANGE);
        }

        k_msleep(READ_INTERVAL_MS);
    }

    return 0;
}
