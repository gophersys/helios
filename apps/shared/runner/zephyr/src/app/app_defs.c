// std include 
#include <stdint.h>

// zephyr includes
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>

#include <digital_pot_mcp4017_drv.h>
#include <eeprom_m24c08_drv.h>



#include "app_defs.h"

LOG_MODULE_REGISTER(app_defs);

#define DUT_PWR_EN_NODE DT_NODELABEL(power_en)
#define DUt_CHG_EN_NODE DT_NODELABEL(charger_en)

#define ON 1
#define OFF 0

// get DTS devices that are app specific and not for a specific driver
static const struct device *ina219_dev;
static const struct gpio_dt_spec _dut_power_enable = GPIO_DT_SPEC_GET(DUT_PWR_EN_NODE, gpios);
static const struct gpio_dt_spec _dut_charge_enable = GPIO_DT_SPEC_GET(DUt_CHG_EN_NODE, gpios);

typedef struct
{
    uint32_t feedback;     // Feedback value from the device
    uint8_t wiperValue;  // Corresponding wiper value
} __attribute__((packed)) FeedbackWiperPair;

static FeedbackWiperPair Feedback_pairs[33];
static uint32_t voltage_values[] = {1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500,
                                    2600, 2700, 2800, 2900, 3000, 3100, 3200, 3300,
                                    3400, 3500, 3600, 3700, 3800, 3900, 4000, 4100,
                                    4200, 4300, 4400, 4500, 4600, 4700, 4800, 4900, 5000
                                   };

void calibrate_potentiometer(app_info_t *app)
{
    double tol1 = 0, tol2 = 0;

    for (int i = 127; i >= 0; i--)
    {
        // set the new pot value and wait 100ms to settle
        digital_pot_set_resitance(i);
        k_msleep(500);

        // fetch the voltage value
        int rc = sensor_sample_fetch(ina219_dev);
        if (rc)
        {
            LOG_ERR("Could not fetch sensor data.\n");
        }
        // store the voltage value in app struct for ina219
        sensor_channel_get(ina219_dev, SENSOR_CHAN_VOLTAGE, &app->ina219_dev.bus_voltage);

        double value = (double)app->ina219_dev.bus_voltage.val1 + (double)app->ina219_dev.bus_voltage.val2 / 1000000;
        int32_t vallue = (int32_t)(value * 1000);
        for (size_t j = 0; j < 33; j++)
        {
            tol1 = voltage_values[j] - 50;
            tol2 = voltage_values[j] + 30;
            if ((vallue > tol1) && (vallue <= tol2))
            {
                Feedback_pairs[j].feedback = voltage_values[j];
                Feedback_pairs[j].wiperValue = (uint8_t)i;
                break;
            }
        }
    }

    // move array of wiper values into new array
    uint8_t wiperValues[33];
    for (size_t i = 0; i < 33; i++)
    {
        wiperValues[i] = Feedback_pairs[i].wiperValue;
    }

    // write wiper values to eeprom bank 3
    int bank_size = 1024 / 4;
    int start_address = 3 * bank_size;
    size_t len = sizeof(wiperValues);
    if (len > bank_size)
    {
        LOG_ERR("wiperValues array is too large to fit in eeprom bank 3");
        return;
    }
    int rett = eeprom_write((uint16_t)start_address, wiperValues, len);
    if (rett != 0)
    {
        LOG_ERR("could not write wiperValues array to eeprom bank 3");
        return;
    }
    LOG_INF("Calibration complete");
}

void read_calibrated_pot_values(void)
{
    // read wiper values from eeprom bank 3
    int bank_size = 1024 / 4;
    int start_address = 3 * bank_size;
    uint8_t wiperValues[33];
    size_t len = sizeof(wiperValues);
    if (len > bank_size)
    {
        LOG_ERR("Feedback_pairs array is too large to fit in eeprom bank 3");
        return;
    }
    int rett = eeprom_read((uint16_t)start_address, wiperValues, len);
    if (rett != 0)
    {
        LOG_ERR("could not read Feedback_pairs array from eeprom bank 3");
        return;
    }

    for (size_t i = 0; i < 33; i++)
    {
        Feedback_pairs[i].wiperValue = wiperValues[i];
        Feedback_pairs[i].feedback = voltage_values[i];
    }
}

void set_desired_volatge(uint32_t desired_voltage)
{
    if (desired_voltage > 5000 || desired_voltage < 1800)
    {
        LOG_ERR("desired voltage is too high or too low, must be between 1800mV and 5000mV");
        return;
    }
    uint8_t wiper_value = 0;
    for (size_t i = 0; i < 33; i++)
    {
        if (Feedback_pairs[i].feedback == desired_voltage)
        {
            wiper_value = Feedback_pairs[i].wiperValue;
            break;
        }
    }
    digital_pot_set_resitance(wiper_value);
}

/*---------------------------------------------------------------------------
*  INA specific functions
*---------------------------------------------------------------------------*/
/**
 * @brief Initializes the INA290 sensor.
 *
 * This function prepares the INA290 sensor for operation, checking its readiness.
 * It is part of the application's device initialization process.
 */
void init_ina219(app_info_t *app)
{
    // get the ina29 device here
    ina219_dev = DEVICE_DT_GET_ONE(ti_ina219);
    if (device_is_ready(ina219_dev))
    {
        LOG_INF("INA219 Dev Ready To use");
    }

    // initlalize the ina219 mutex
    // k_mutex_init(&app->ina219_dev.ina219_mutex);
    k_sem_init(&app->ina219_dev.ina219_sem, 1, 1);
}
void ina219_get_current(app_info_t *app)
{
    int rc = sensor_sample_fetch(ina219_dev);
    if (rc)
    {
        LOG_ERR("Could not fetch sensor data.\n");
        return;
    }
    sensor_channel_get(ina219_dev, SENSOR_CHAN_CURRENT, &app->ina219_dev.current);

}
void ina219_get_voltage(app_info_t *app)
{
    int rc = sensor_sample_fetch(ina219_dev);
    if (rc)
    {
        LOG_ERR("Could not fetch sensor data.\n");
        return;
    }
    sensor_channel_get(ina219_dev, SENSOR_CHAN_VOLTAGE, &app->ina219_dev.bus_voltage);

}
void ina219_get_power(app_info_t *app)
{
    int rc = sensor_sample_fetch(ina219_dev);
    if (rc)
    {
        LOG_ERR("Could not fetch sensor data.\n");
        return;
    }
    sensor_channel_get(ina219_dev, SENSOR_CHAN_POWER, &app->ina219_dev.power);

}



/*---------------------------------------------------------------------------
*  DUT gpio functions 
*---------------------------------------------------------------------------*/

void init_dut_gpios(void)
{
    if(!gpio_is_ready_dt(&_dut_charge_enable))
    {
        LOG_ERR("CHG GPIO DEV NOT READY ");
    }
    if(!gpio_is_ready_dt(&_dut_power_enable))
    {
        LOG_ERR("PWR GPIO DEV NOT READY ");
    }

    int ret = gpio_pin_configure(_dut_charge_enable.port, _dut_charge_enable.pin, GPIO_OUTPUT_LOW); // config pin low
    if(ret != 0)
    {
        LOG_ERR(" CHG GPIO CONFIG FAILED");
    }

    ret = gpio_pin_configure(_dut_power_enable.port, _dut_power_enable.pin, GPIO_OUTPUT_LOW); // config pin low
    if(ret != 0)
    {
        LOG_ERR(" PWR GPIO CONFIG FAILED");
    }

}

uint8_t is_enabled(dut_gpio_e pin)
{
    switch(pin)
    {
        case PWR_GPIO:
            return (uint8_t)gpio_pin_get(_dut_power_enable.port, _dut_power_enable.pin);
        break;
        case CHG_GPIO:
            return (uint8_t)gpio_pin_get(_dut_charge_enable.port, _dut_charge_enable.pin);
        break;

        default:
            LOG_ERR("NOT DUT GPIO FOUND");
            return -ERROR;
        break;
    }
    return -ERROR;
}

/*---------------------------------------------------------------------------
*                                               * power management functions
*---------------------------------------------------------------------------*/
void power_on(void)
{
    gpio_pin_set(_dut_power_enable.port, _dut_power_enable.pin, ON);
}

void power_off(void)
{
    gpio_pin_set(_dut_power_enable.port, _dut_power_enable.pin, OFF);
}

void charge_on(void)
{
    gpio_pin_set(_dut_charge_enable.port, _dut_charge_enable.pin, ON);
}

void charge_off(void)
{
    gpio_pin_set(_dut_charge_enable.port, _dut_charge_enable.pin, OFF);
}

bool is_correct_voltage(app_info_t *app, uint32_t desired_voltage)
{
    ina219_get_voltage(app);

    double value = (double)app->ina219_dev.bus_voltage.val1 + (double)app->ina219_dev.bus_voltage.val2 / 1000000;
    int32_t value_mv = (int32_t)(value * 1000);

    double tol1 = desired_voltage - VOLTAGE_TOLERANCE_mV;
    double tol2 = desired_voltage + VOLTAGE_TOLERANCE_mV;

    if (value_mv >= tol1 && value_mv <= tol2)
    {
        return true;
    }
    return false;
}

void turn_on_mtib(app_info_t *app, uint32_t desired_voltage)
{
    if (is_correct_voltage(app, desired_voltage))
    {
        LOG_WRN("Voltage is correct, turning on MTIB");
        power_on();
        // charge_on();
    }
    else
    {
        LOG_ERR("Voltage is not correct, cannot turn on MTIB");
        power_off();
        // charge_off();
    }
}