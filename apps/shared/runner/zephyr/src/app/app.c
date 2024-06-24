
/**
 * @file app.c
 * @brief Application source file.
 *
 * This file contains the source code for the application.
 */

// standard includes
#include <math.h>

// aplicaation includes
#include "app.h"

// driver includes
#include <accel_drv.h>
#include <alt_drv.h>
#include <digital_pot_mcp4017_drv.h>
#include <dut_gpio_config_drv.h>
#include <eeprom_m24c08_drv.h>
#include <sn74lv4051a_drv.h>

// zephyr includes
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(mtib);

#define DEFAULT_MOTION_THS 0x04
#define DEFAULT_MOTION_DUR 0x03
#define DEFAULT_FREE_FALL_THS 0x07
#define DEFAULT_FREE_FALL_DUR 0x1d
#define CURRENT_THRESH 1.0f // 1A threshold for over current detection

#define EEPROM_SIZE 1024

// this is a test to see if i can access the usarts and comm_en
#define COMM_EN  DT_NODELABEL(comm_en)
#define USART_1_NODE DT_NODELABEL(usart1)
#define USART_6_NODE DT_NODELABEL(usart6)
#define DUT_PWR_EN_NODE DT_NODELABEL(power_en)
#define DUt_CHG_EN_NODE DT_NODELABEL(charger_en)


static const struct gpio_dt_spec comm_en = GPIO_DT_SPEC_GET(COMM_EN, gpios);
static const struct device *p_usart1_dev = DEVICE_DT_GET(USART_1_NODE);
static const struct device *p_usart6_dev = DEVICE_DT_GET(USART_6_NODE);

/**
 * @brief Accelerometer configuration parameters.
 *
 * This structure contains parameters used for configuring the accelerometer's
 * behavior with regards to motion detection and free fall detection.
 */
static accel_params_t _accel_params =
{
    .motion_threshold_2g_scale = DEFAULT_MOTION_THS,       /**< Motion detection threshold in 2g scale. */
    .motion_duration_10Hz = DEFAULT_MOTION_DUR,            /**< Duration for motion detection at 10Hz. */
    .free_fall_threshold_2g_scale = DEFAULT_FREE_FALL_THS, /**< Free fall detection threshold in 2g scale. */
    .free_fall_duration_10Hz = DEFAULT_FREE_FALL_DUR       /**< Duration for free fall detection at 10Hz. */
};

// define static functions here functions here
static void app_event_handler_thread(void *arg0, void *arg1, void *arg2);
static void app_over_current_check_thread(void *arg0, void *arg1, void *arg2);

static void altimeter_callback(void) {};
static double get_altitude_from_pressure(double *pressure);

static void app_init_devices(app_info_t *app);
static void app_init_threads(app_info_t *app);
static void app_process_event(const event_t *event, app_info_t *app);
static void app_heap_init(app_info_t *app);
static void init_ina290(app_info_t *app);

// get the ina29 device here, this is because we are using zephyr driver, not our own.
static const struct device *ina219_dev;
static const struct gpio_dt_spec _dut_power_enable = GPIO_DT_SPEC_GET(DUT_PWR_EN_NODE, gpios);
static const struct gpio_dt_spec _dut_charge_enable = GPIO_DT_SPEC_GET(DUt_CHG_EN_NODE, gpios);
int rc;

typedef struct
{
    uint32_t feedback;     // Feedback value from the device
    uint8_t wiperValue;  // Corresponding wiper value
}  FeedbackWiperPair;

static FeedbackWiperPair Feedback_pairs[33];
static uint32_t voltage_values[] = {1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500,
                                    2600, 2700, 2800, 2900, 3000, 3100, 3200, 3300,
                                    3400, 3500, 3600, 3700, 3800, 3900, 4000, 4100,
                                    4200, 4300, 4400, 4500, 4600, 4700, 4800, 4900, 5000
                                   };

static void calibrate_potentiometer(app_info_t *app)
{
    double tol1 = 0, tol2 = 0;

    for (int i = 127; i >= 0; i--)
    {
        // set the new pot value and wait 100ms to settle
        digital_pot_set_resitance(i);
        k_msleep(100);

        // fetch the voltage value
        rc = sensor_sample_fetch(ina219_dev);
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
            tol2 = voltage_values[j] + 20;
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

static void read_calibrated_pot_values(void)
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

static int32_t set_desired_volatge(uint32_t desired_voltage)
{
    if (desired_voltage > 5000 || desired_voltage < 1800)
    {
        LOG_ERR("desired voltage is too high or too low, must be between 1800mV and 5000mV");
        return -ERROR;
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

    return digital_pot_set_resitance(wiper_value);
}
/*---------------------------------------------------------------------------
*                                               * power management functions
*---------------------------------------------------------------------------*/
static bool power_on(void)
{
    int ret = gpio_pin_set(_dut_power_enable.port, _dut_power_enable.pin, ON);
    if (ret != 0)
    {
        LOG_ERR("could not set the power enable pin ERROR number: %d", ret);
        return false;
    }

    return true;

}

static bool power_off(void)
{
    int ret = gpio_pin_set(_dut_power_enable.port, _dut_power_enable.pin, OFF);
    if (ret != 0)
    {
        LOG_ERR("could not set the power enable pin ERROR number: %d", ret);
        return false;
    }

    return true;
}

static int charge_on(void)
{
    return gpio_pin_set(_dut_charge_enable.port, _dut_charge_enable.pin, ON);
}

static int charge_off(void)
{
    return gpio_pin_set(_dut_charge_enable.port, _dut_charge_enable.pin, OFF);
}

static bool dut_power_enable(uint8_t enable)
{
    bool ret = false;
    switch (enable)
    {
        case ON:
            ret  = power_on();
            break;
        case OFF:
            ret = power_off();
        default:
            return false;
            break;
    }

    return ret;
}

static bool dut_charger_enable(uint8_t enable)
{
    switch (enable)
    {
        case ON:
            charge_on();
            break;
        case OFF:
            charge_off();
        default:
            return false;
            break;
    }

    return true;
}



/**
 * @brief Processes an event and performs corresponding actions based on the event type.
 *
 * @param event Pointer to the event to be processed.
 * @param app Pointer to the application's information and state.
 *
 * This function processes various types of events such as reading sensor data,
 * writing to EEPROM, setting power rails, and more. It acts as an event dispatcher,
 * calling specific functions based on the event type.
 */
void app_process_event(const event_t *event, app_info_t *app)
{
    switch (event->type)
    {
        case EVENT_BMP_GET_ALTITUDE:
            measure_temp_and_pressure();
            app->bmp390_dev.temperature = alt_get_current_temperature();
            app->bmp390_dev.pressure = alt_get_current_pressure();
            app->bmp390_dev.altitude = get_altitude_from_pressure(&app->bmp390_dev.pressure);
            break;
        case EVENT_BMP_GET_TEMPERATURE:
            measure_temp_and_pressure();
            app->bmp390_dev.temperature = alt_get_current_temperature();
            break;
        case EVENT_BMP_GET_PRESSURE:
            measure_temp_and_pressure();
            app->bmp390_dev.pressure = alt_get_current_pressure();
            break;
        case EVENT_BMP_PRINT_ALL_MEASUREMENTS:
            measure_temp_and_pressure();
            app->bmp390_dev.temperature = alt_get_current_temperature();
            app->bmp390_dev.pressure = alt_get_current_pressure();
            app->bmp390_dev.altitude = get_altitude_from_pressure(&app->bmp390_dev.pressure);
            app_print_bmp390_data(&app->bmp390_dev.temperature, &app->bmp390_dev.pressure, &app->bmp390_dev.altitude);
            break;
        case EVENT_ACCEL_GET_AVG_FORCE:
            event_opt_lis2de12_t *opt_avg_force = (event_opt_lis2de12_t *)event->options;
            app->lis2de12_dev.avg_force = accel_get_avg_force(opt_avg_force->reset_value);
            break;
        case EVENT_ACCEL_GET_MAX_FORCE:
            event_opt_lis2de12_t *opt_max_force = (event_opt_lis2de12_t *)event->options;
            app->lis2de12_dev.max_force = accel_get_avg_force(opt_max_force->reset_value);
            break;
        case EVENT_ACCEL_GET_XYZ_FORCES:
            double forces[3];
            accel_get_xyz_forces(forces);
            app->lis2de12_dev.acc_x = forces[0];
            app->lis2de12_dev.acc_y = forces[1];
            app->lis2de12_dev.acc_z = forces[2];
            break;
        case EVENT_ACCEL_PRINT_FORCES:
            LOG_INF("Acceleramter Average Force :%d", (int)app->lis2de12_dev.avg_force);
            LOG_INF("Acceleramter Max Force :%d", (int)app->lis2de12_dev.max_force);
            LOG_INF("Acceleramter X direction :%d", (int)app->lis2de12_dev.acc_x);
            LOG_INF("Acceleramter y direction :%d", (int)app->lis2de12_dev.acc_y);
            LOG_INF("Acceleramter z direction :%d", (int)app->lis2de12_dev.acc_z);
            break;
        case EVENT_INA219_GET_VOLTAGE_V:
            k_sem_take(&app->ina219_dev.ina219_sem, K_FOREVER);
            rc = sensor_sample_fetch(ina219_dev);
            if (rc)
            {
                LOG_ERR("Could not fetch sensor data.\n");
            }
            else
            {
                sensor_channel_get(ina219_dev, SENSOR_CHAN_VOLTAGE, &app->ina219_dev.bus_voltage);
            }
            k_sem_give(&app->ina219_dev.ina219_sem);
            break;
        case EVENT_INA219_GET_POWER_W:
            k_sem_take(&app->ina219_dev.ina219_sem, K_FOREVER);
            rc = sensor_sample_fetch(ina219_dev);
            if (rc)
            {
                LOG_ERR("Could not fetch sensor data.\n");
            }
            else
            {
                sensor_channel_get(ina219_dev, SENSOR_CHAN_POWER, &app->ina219_dev.power);
            }
            k_sem_give(&app->ina219_dev.ina219_sem);
            break;
        case EVENT_INA219_GET_CURRENT_A:
            k_sem_take(&app->ina219_dev.ina219_sem, K_FOREVER);
            rc = sensor_sample_fetch(ina219_dev);
            if (rc)
            {
                LOG_ERR("Could not fetch sensor data.\n");
            }
            else
            {
                sensor_channel_get(ina219_dev, SENSOR_CHAN_CURRENT, &app->ina219_dev.current);
            }
            k_sem_give(&app->ina219_dev.ina219_sem);
            break;
        case EVENT_INA219_PRINT_ALL_MEASUREMENTS:
            k_sem_take(&app->ina219_dev.ina219_sem, K_FOREVER);
            app_print_ina219_data(app);
            k_sem_give(&app->ina219_dev.ina219_sem);
            break;
        case EVENT_WRITE_TO_EEPROM:
            event_opt_eeprom_t *eeprom_write_options = (event_opt_eeprom_t *)event->options;
            eeprom_write(eeprom_write_options->memory_address, eeprom_write_options->data, eeprom_write_options->len);
            break;
        case EVENT_READ_FROM_EEPROM:
            event_opt_eeprom_t *eeprom_read_options = (event_opt_eeprom_t *)event->options;
            eeprom_read(eeprom_read_options->memory_address, eeprom_read_options->data, eeprom_read_options->len);
            // copy the data into the apps eeprom device
            memcpy(app->eeprom_dev.data, eeprom_read_options->data, eeprom_read_options->len);
            break;
        case EVENT_MUX_READ_ALL_CHANNELS:
            event_opt_mux_data_t *mux_multi_channel_opt = (event_opt_mux_data_t *)event->options;
            for (size_t i = 0; (i < mux_multi_channel_opt->mux_channel) && (*mux_multi_channel_opt->status == 0); i++)
            {
                set_mux_channel(i, mux_multi_channel_opt->delay_ms, mux_multi_channel_opt->status);
                mux_multi_channel_opt->adc_array[i] = read_mux_data(mux_multi_channel_opt->status);
            }
            break;
        case EVENT_MUX_READ_CHANNEL:
            event_opt_mux_data_t *mux_single_channel_opt = (event_opt_mux_data_t *)event->options;
            set_mux_channel(mux_single_channel_opt->mux_channel, mux_single_channel_opt->delay_ms, mux_single_channel_opt->status);
            *(mux_single_channel_opt->mux_adc_value) = read_mux_data(mux_single_channel_opt->status);
            break;
        case EVENT_POWER_RAIL_READ_VOLTAGE:
            event_opt_digital_pot_data_t *digital_pot_read_opt = (event_opt_digital_pot_data_t *)event->options;
            *digital_pot_read_opt->status = digital_pot_read_feedback_voltage(digital_pot_read_opt->desired_voltage);
            break;
        case EVENT_POWER_RAIL_SET_VOLTAGE:
            event_opt_digital_pot_data_t *digital_pot_opts = (event_opt_digital_pot_data_t *)event->options;
            *digital_pot_opts->status = set_desired_volatge(*digital_pot_opts->desired_voltage);
            app->mcp4017_dev.potentiometer_value = digital_pot_get_current_resitance();
            *digital_pot_opts->status = digital_pot_read_feedback_voltage(digital_pot_opts->desired_voltage);
            break;
        case EVENT_POWER_RAIL_PRINT_DATA:
            LOG_INF("power rail voltage: %.2f", app->mcp4017_dev.voltage_value);
            break;
        case EVENT_DUT_POWER_ENABLE:
            event_opt_power_en_t *p_en_opt = (event_opt_power_en_t *)event->options;
            *p_en_opt->status = dut_power_enable(p_en_opt->enable);
            break;
        case EVENT_DUT_CHARGE_ENABLE:
            event_opt_charger_en_t *ch_en_opt = (event_opt_charger_en_t *)event->options;
            *ch_en_opt->status =  dut_charger_enable(ch_en_opt->enable);
            break;
        case EVENT_GPIO_CONFIGURE:
            event_opt_gpio_t *gpio_config_opt = (event_opt_gpio_t *)event->options;
            *gpio_config_opt->status = configure_dut_gpio(gpio_config_opt->pin, gpio_config_opt->flag);
            break;
        case EVENT_GPIO_SET:
            event_opt_gpio_t *gpio_set_opt = (event_opt_gpio_t *)event->options;
            *gpio_set_opt->status = set_pin_state(gpio_set_opt->pin, *gpio_set_opt->state);
            break;
        case EVENT_GPIO_READ:
            event_opt_gpio_t *gpio_read_opt = (event_opt_gpio_t *)event->options;
            *gpio_read_opt->status = get_pin_state(gpio_read_opt->pin, gpio_read_opt->state);
            break;
        default:
            LOG_INF("Event: %d",  event->type);
            break;
    }
}

/**
 * @brief Initializes threads for the application.
 *
 * @param app Pointer to the application's information and state.
 *
 * This function creates and initializes a thread for handling application events.
 */
void app_init_threads(app_info_t *app)
{
    app->event_handler_thread.t_id = k_thread_create(&app->event_handler_thread.t_data,
                                     app->event_handler_thread.t_stack,
                                     K_THREAD_STACK_SIZEOF(app->event_handler_thread.t_stack),
                                     app_event_handler_thread,
                                     (void *)app, NULL, NULL,
                                     APP_THREAD_PRIORITY,
                                     0,
                                     K_NO_WAIT);
    k_thread_name_set(app->event_handler_thread.t_id, "event_handler_thread");

    app->over_current_thread.t_id = k_thread_create(&app->over_current_thread.t_data,
                                    app->over_current_thread.t_stack,
                                    K_THREAD_STACK_SIZEOF(app->over_current_thread.t_stack),
                                    app_over_current_check_thread,
                                    (void *)app, NULL, NULL,
                                    APP_CURRENT_THREAD_PRIORITY,
                                    0,
                                    K_NO_WAIT);
    k_thread_name_set(app->over_current_thread.t_id, "over_current_thread");
}

/**
 * @brief Initializes the MTIB (Multithreaded Interrupt-Based) system for the application.
 *
 * @param app Pointer to the application's information and state.
 *
 * This function initializes the heap, devices, and threads required for the application's MTIB system.
 */
static app_info_t *the_app = NULL;
void app_mtib_init(app_info_t *app)
{
    if (!device_is_ready(p_usart1_dev))
    {
        LOG_ERR("USART1 device not ready");
    }
    if (!device_is_ready(p_usart6_dev))
    {
        LOG_ERR("USART6 device not ready");
    }
    if (!gpio_is_ready_dt(&comm_en))
    {
        LOG_ERR("COMM_EN GPIO device not ready");
    }
    if (!gpio_is_ready_dt(&_dut_power_enable))
    {
        LOG_ERR("Power enable pin not defined in device tree");
    }
    if (!gpio_is_ready_dt(&_dut_charge_enable))
    {
        LOG_ERR("charger enable pin not defined in device tree");
    }
    if (gpio_pin_configure(comm_en.port, comm_en.pin, GPIO_OUTPUT_HIGH))
    {
        LOG_ERR("COMM_EN GPIO pin configure failed");
    }
    if (gpio_pin_configure(_dut_power_enable.port, _dut_power_enable.pin, GPIO_OUTPUT_LOW))
    {
        LOG_ERR("PWR_EN pin configuration failed");
    }
    if (gpio_pin_configure(_dut_charge_enable.port, _dut_charge_enable.pin, GPIO_OUTPUT_LOW))
    {
        LOG_ERR("CHRGER_EN pin configuration failed");
    }

    gpio_pin_set(comm_en.port, comm_en.pin, 1);

    app_heap_init(app);
    app_init_devices(app);
    k_fifo_init(&app->command_event_queue);

    if (!eeprom_bank_is_empty(BANK3))
    {
        LOG_INF("EEPROM is not empty, skipping potentiometer calibration");
        read_calibrated_pot_values();
    }
    else
    {
        LOG_INF("EEPROM is empty, calibrating potentiometer");
        calibrate_potentiometer(app);
    }

    the_app = app;

    app_init_threads(app);
}

app_info_t *app_get_ptr(void)
{
    return the_app;
}

/**
 * @brief Thread function for handling application events.
 *
 * @param arg0 Pointer to the application's information and state.
 * @param arg1 Unused parameter.
 * @param arg2 Unused parameter.
 *
 * This function continuously checks for and processes incoming events.
 * It is intended to be run as a separate thread.
 */
static void app_event_handler_thread(void *arg0, void *arg1, void *arg2)
{
    app_info_t *app = (app_info_t *)arg0;
    while (true)
    {
        event_t *event = k_fifo_get(&app->command_event_queue, K_FOREVER);
        app_process_event(event, app);
        k_sem_give(&event->sem);
    }
}

/**
 * @brief  Thread function for checking for over current conditions.
 *
 * @param arg0 first argument to thread that holds the app info struct
 * @param arg1 second argument to thread NULL
 * @param arg2 third argument to thread NULL
 */
static void app_over_current_check_thread(void *arg0, void *arg1, void *arg2)
{
    app_info_t *app = (app_info_t *)arg0;
    while (1)
    {
        k_sem_take(&app->ina219_dev.ina219_sem, K_FOREVER);
        rc = sensor_sample_fetch(ina219_dev);
        if (rc)
        {
            LOG_ERR("Could not fetch sensor data.\n");
            break;
        }
        sensor_channel_get(ina219_dev, SENSOR_CHAN_CURRENT, &app->ina219_dev.current);

        if (app->ina219_dev.current.val1 > CURRENT_THRESH)
        {
            LOG_INF("over current detected");
        }

        k_sem_give(&app->ina219_dev.ina219_sem);
        k_msleep(SET_FREQUENCY_Hz(3000));
    }
}

/**
 * @brief Creates and queues an event in the application's event system.
 *
 * @param app Pointer to the application's information and state.
 * @param type The type of the event to be created.
 * @param option Pointer to additional options or data for the event.
 * @param option_size Size of the additional options or data.
 * @return bool True if the event was created successfully, false otherwise.
 *
 * This function allocates memory for an event, initializes it with provided data,
 * and queues it for processing. It also handles synchronization with semaphores.
 */
static bool create_event_entry(app_info_t *app, event_type_t type, void *option, size_t option_size)
{
    event_t *event = k_heap_aligned_alloc(&app->app_events_heap, 4, sizeof(event_t), K_NO_WAIT);
    memset(event, 0, sizeof(event_t));
    size_t actual_opt_size = 0;

    switch (type)
    {
        case EVENT_BMP_GET_ALTITUDE:
        case EVENT_BMP_GET_TEMPERATURE:
        case EVENT_BMP_GET_PRESSURE:
        case EVENT_BMP_PRINT_ALL_MEASUREMENTS:
            actual_opt_size = 0;
            break;
        case EVENT_ACCEL_GET_AVG_FORCE:
        case EVENT_ACCEL_GET_MAX_FORCE:
            actual_opt_size = sizeof(event_opt_lis2de12_t);
            break;
        case EVENT_ACCEL_GET_XYZ_FORCES:
        case EVENT_ACCEL_PRINT_FORCES:
            actual_opt_size = 0;
            break;
        case EVENT_INA219_GET_VOLTAGE_V:
        case EVENT_INA219_GET_POWER_W:
        case EVENT_INA219_GET_CURRENT_A:
        case EVENT_INA219_PRINT_ALL_MEASUREMENTS:
            actual_opt_size = 0;
            break;
        case EVENT_WRITE_TO_EEPROM:
        case EVENT_READ_FROM_EEPROM:
            actual_opt_size = sizeof(event_opt_eeprom_t);
            break;
        case EVENT_MUX_READ_ALL_CHANNELS:
        case EVENT_MUX_READ_CHANNEL:
            actual_opt_size = sizeof(event_opt_mux_data_t);
            break;
        case EVENT_POWER_RAIL_PRINT_DATA:
            actual_opt_size = 0;
            break;
        case EVENT_POWER_RAIL_SET_VOLTAGE:
        case EVENT_POWER_RAIL_READ_VOLTAGE:
            actual_opt_size = sizeof(event_opt_digital_pot_data_t);
            break;
        case EVENT_DUT_POWER_ENABLE:
            actual_opt_size = sizeof(event_opt_power_en_t);
            break;
        case EVENT_DUT_CHARGE_ENABLE:
            actual_opt_size = sizeof(event_opt_charger_en_t);
            break;
        case EVENT_GPIO_CONFIGURE:
        case EVENT_GPIO_SET:
        case EVENT_GPIO_READ:
            actual_opt_size = sizeof(event_opt_gpio_t);
            break;
        default:
            LOG_WRN("Incorrect event type");
            break;
    }

    if (actual_opt_size != option_size)
    {
        // TODO: Handle fatal error
        return false;
    }

    // Set the event fields
    event->type = type;
    event->options_size = option_size;

    if (actual_opt_size > 0)
    {
        event->options = k_heap_aligned_alloc(&app->app_events_heap, 4, option_size, K_NO_WAIT);
        memcpy(event->options, option, option_size);
    }

    // Initialize the semaphore
    k_sem_init(&event->sem, 0, 1);
    k_sem_take(&event->sem, K_NO_WAIT);

    // Add event to queue
    k_fifo_put(&app->command_event_queue, event);

    // Await on semaphore to be unblockewd by event loop
    k_sem_take(&event->sem, K_FOREVER);  // Ideally we should have a timeout here

    // Free memory
    if (event->options != NULL)
    {
        k_heap_free(&app->app_events_heap, event->options);
    }

    if (event != NULL)
    {
        k_heap_free(&app->app_events_heap, event);
    }
    return true;
}

/**
 * @brief Initializes the heap for application events.
 *
 * @param app Pointer to the application's information and state.
 *
 * This function sets up the heap memory used for dynamically allocating events.
 */
void app_heap_init(app_info_t *app)
{
    k_heap_init(&app->app_events_heap, app->app_events_heap_mem, EVENTS_HEAP_SIZE);
}

/**
 * @brief Initializes the devices required by the application.
 *
 * This function initializes various devices such as the altimeter, EEPROM, and INA290.
 * It is part of the application's startup routine.
 */
void app_init_devices(app_info_t *app)
{
    init_altimeter(altimeter_callback);
    (void)accel_get_avg_force(true);
    (void)accel_get_max_force(true);
    accel_config_params(_accel_params);
    accel_config_mode(motion_and_free_fall_2g);
    init_ina290(app);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                           Altimeter bmp390 Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Prints the BMP390 sensor data including temperature, pressure, and altitude.
 *
 * @param temperature Pointer to a double containing the temperature value.
 * @param pressure Pointer to a double containing the pressure value.
 * @param altitude Pointer to a double containing the altitude value.
 *
 * This function logs the BMP390 data in a human-readable format.
 */
void app_print_bmp390_data(double *temperature, double *pressure, double *altitude)
{
    int temp_int = (int) * temperature;
    int temp_frac = (int)((*temperature - temp_int) * 1000);  // 3 decimal places
    int pres_int = (int) * pressure;
    int pres_frac = (int)((*pressure - pres_int) * 1000);  // 3 decimal places
    int alt_int = (int) * altitude;
    int alt_frac = (int)((*altitude - alt_int) * 1000);  // 3 decimal places

    LOG_INF("Temp: %d.%03d C, Pres: %d.%03d inHg, Alti: %d.%03d meters",
            temp_int, temp_frac,
            pres_int, pres_frac,
            alt_int, alt_frac);
}

/**
 * @brief Calculates the altitude from the given pressure.
 *
 * @param pressure Pointer to a double containing the pressure value in inHg.
 * @return double The calculated altitude in meters.
 *
 * This function uses the standard atmospheric pressure model to calculate the altitude from a given pressure reading.
 */
static double get_altitude_from_pressure(double *pressure)
{

    double pressure_mbar = *pressure * 33.8639;
    double base = 1.0 - pow(pressure_mbar / 1013.25, 0.190284);

    return base * 145366.45;
}

/**
 * @brief Requests the altitude data from the BMP390 sensor.
 *
 * @param app Pointer to the application's information and state.
 * @return bool True if the request was successful, false otherwise.
 *
 * This function creates an event to fetch the altitude data from the BMP390 sensor.
 */
bool app_get_bmp390_altitude(app_info_t *app)
{
    if (!create_event_entry(app, EVENT_BMP_GET_ALTITUDE, NULL, 0))
    {
        LOG_ERR("Cannot get bmp altitude.");
        return false;
    }
    return true;
}

/**
 * @brief Requests the pressure data from the BMP390 sensor.
 *
 * @param app Pointer to the application's information and state.
 * @return bool True if the request was successful, false otherwise.
 *
 * This function creates an event to fetch the pressure data from the BMP390 sensor.
 */
bool app_get_bmp390_pressure(app_info_t *app)
{
    if (!create_event_entry(app, EVENT_BMP_GET_PRESSURE, NULL, 0))
    {
        LOG_ERR("Cannot get bmp altitude.");
        return false;
    }
    return true;
}

/**
 * @brief Requests the temperature data from the BMP390 sensor.
 *
 * @param app Pointer to the application's information and state.
 * @return bool True if the request was successful, false otherwise.
 *
 * This function creates an event to fetch the temperature data from the BMP390 sensor.
 */
bool app_get_bmp390_temperature(app_info_t *app)
{
    if (!create_event_entry(app, EVENT_BMP_GET_TEMPERATURE, NULL, 0))
    {
        LOG_ERR("Cannot get bmp altitude.");
        return false;
    }
    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                current/power sensor ina209 Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Sets the desired power value for the INA219 sensor.
 *
 * @param app Pointer to the application's information and state.
 * @param pow The desired power setting for the sensor.
 * @return bool True if the setting was successful, false otherwise.
 *
 * This function creates an event to set the power level of the INA219 sensor.
 */
bool app_set_ina219_power(app_info_t *app, double pow)
{
    event_opt_ina219_set_power_t opt =
    {
        .desired_power = pow,
    };

    if (!create_event_entry(app, EVENT_BMP_GET_ALTITUDE, &opt, sizeof(opt)))
    {
        // TOODO: handle fatal error
        return false;
    }

    return true;
}

/**
 * @brief Initializes the INA290 sensor.
 *
 * This function prepares the INA290 sensor for operation, checking its readiness.
 * It is part of the application's device initialization process.
 */
void init_ina290(app_info_t *app)
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

/**
 * @brief Prints the INA219 sensor data including voltage, current, and power.
 *
 * @param app Pointer to the application's information and state.
 *
 * This function logs the INA219 data in a human-readable format.
 */
void app_print_ina219_data(app_info_t *app)
{
    k_sem_take(&app->ina219_dev.ina219_sem, K_FOREVER);
    rc = sensor_sample_fetch(ina219_dev);
    if (rc)
    {
        LOG_ERR("Could not fetch sensor data.\n");
    }
    else
    {
        sensor_channel_get(ina219_dev, SENSOR_CHAN_VOLTAGE, &app->ina219_dev.bus_voltage);
        sensor_channel_get(ina219_dev, SENSOR_CHAN_CURRENT, &app->ina219_dev.current);
        sensor_channel_get(ina219_dev, SENSOR_CHAN_POWER, &app->ina219_dev.power);
    }
    k_sem_give(&app->ina219_dev.ina219_sem);

    double value = (double)app->ina219_dev.bus_voltage.val1 + (double)app->ina219_dev.bus_voltage.val2 / 1000000;
    int int_part = (int)value;
    int frac_part = (int)((value - int_part) * 1000);
    LOG_INF("Voltage [V]: %d.%03d", int_part, frac_part);

    value = (double)app->ina219_dev.current.val1 + (double)app->ina219_dev.current.val2 / 1000000;
    int_part = (int)value;
    frac_part = (int)((value - int_part) * 1000);
    LOG_INF("Current [A]: %d.%03d", int_part, frac_part);

    value = (double)app->ina219_dev.power.val1 + (double)app->ina219_dev.power.val2 / 1000000;
    int_part = (int)value;
    frac_part = (int)((value - int_part) * 1000);
    LOG_INF("Power [W]: %d.%03d", int_part, frac_part);
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                   acccelerameter lis2de12 Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Prints data obtained from the lis2de12 sensor.
 *
 * @param app Pointer to the application information structure.
 */
void app_print_lis2de12_data(app_info_t *app)
{
    if (!create_event_entry(app, EVENT_ACCEL_PRINT_FORCES, NULL, 0))
    {
        LOG_ERR("could to process EVENT_ACCEL_PRINT_FORCES event");
        return;
    }
}

/**
 * @brief Calculates and gets the average force from the lis2de12 sensor.
 *
 * @param app Pointer to the application information structure.
 * @param reset_value Boolean to reset the average value after reading.
 * @return Boolean indicating success or failure of the operation.
 */
bool app_get_lis2de12_avg_force(app_info_t *app, bool reset_value)
{
    event_opt_lis2de12_t opt =
    {
        .reset_value = reset_value
    };

    if (!create_event_entry(app, EVENT_ACCEL_GET_AVG_FORCE, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could to process EVENT_ACCEL_GET_AVG_FORCE event");
        return false;
    }

    return true;
}

/**
 * @brief Calculates and gets the maximum force from the lis2de12 sensor.
 *
 * @param app Pointer to the application information structure.
 * @param reset_value Boolean to reset the maximum value after reading.
 * @return Boolean indicating success or failure of the operation.
 */
bool app_get_lis2de12_max_force(app_info_t *app, bool reset_value)
{
    event_opt_lis2de12_t opt =
    {
        .reset_value = reset_value
    };

    if (!create_event_entry(app, EVENT_ACCEL_GET_MAX_FORCE, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could to process EVENT_ACCEL_GET_MAX_FORCE event");
        return false;
    }

    return true;
}

/**
 * @brief Gets the XYZ forces from the lis2de12 sensor.
 *
 * @param app Pointer to the application information structure.
 */
void app_get_lis2de12_xyz_forces(app_info_t *app)
{
    if (!create_event_entry(app, EVENT_ACCEL_GET_XYZ_FORCES, NULL, 0))
    {
        LOG_ERR("could to process EVENT_ACCEL_GET_XYZ_FORCES event");
        return;
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    eeprom functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Writes data to the EEPROM.
 *
 * @param app Pointer to the application's information and state.
 * @param memory_address The EEPROM memory address to write to.
 * @param data Pointer to the data to be written.
 * @param len Length of the data to be written.
 *
 * This function creates an event to write data to a specified EEPROM address.
 */
void app_write_to_eeprom(app_info_t *app, uint16_t memory_address, uint8_t *data, size_t len)
{
    if (data == NULL)
    {
        LOG_ERR("empty data buffer.");
        return;
    }

    if (len <= 0)
    {
        LOG_ERR("Len size is not correct");
        return;
    }

    event_opt_eeprom_t opt =
    {
        .memory_address = memory_address,
        .data = data,
        .len = len
    };

    if (!create_event_entry(app, EVENT_WRITE_TO_EEPROM, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could to process EVENT_WRITE_TO_EEPROM event");
    }
}

/**
 * @brief Reads data from the EEPROM.
 *
 * @param app Pointer to the application's information and state.
 * @param memory_address The EEPROM memory address to read from.
 * @param data Pointer to a buffer where the read data will be stored.
 * @param len Length of the data to be read.
 *
 * This function creates an event to read data from a specified EEPROM address.
 */
void app_read_from_eeprom(app_info_t *app, uint16_t memory_address, uint8_t *data, size_t len)
{

    if (len <= 0)
    {
        LOG_ERR("Len size is not correct");
        return;
    }
    event_opt_eeprom_t opt =
    {
        .memory_address = memory_address,
        .data = data,
        .len = len
    };
    if (!create_event_entry(app, EVENT_READ_FROM_EEPROM, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could to process EVENT_READ_FROM_EEPROM event");
    }
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                       digital pot mcp4017 Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Requests printing of the MCP4017 sensor data.
 *
 * @param app Pointer to the application's information and state.
 *
 * This function creates an event to log the MCP4017 sensor data.
 */
void app_print_mcp4017_data(app_info_t *app)
{
    if (!create_event_entry(app, EVENT_POWER_RAIL_PRINT_DATA, NULL, 0))
    {
        LOG_ERR("could to process EVENT_POWER_RAIL_PRINT_DATA event");
    }
}

/**
 * @brief Sets the voltage output for the MCP4017 digital potentiometer.
 *
 * @param app Pointer to the application's information and state.
 * @param voltage The desired voltage setting.
 * @param status Pointer to a variable where the status of the operation will be stored.
 *
 * @return bool True if the setting was successful, false otherwise.
 *
 * This function creates an event to set the voltage output of the MCP4017 digital potentiometer.
 */
bool app_set_mcp4017_voltage_output(app_info_t *app, uint32_t *voltage, int32_t *status)
{
    event_opt_digital_pot_data_t opt =
    {
        .desired_voltage = voltage,
        .status = status
    };
    if (!create_event_entry(app, EVENT_POWER_RAIL_SET_VOLTAGE, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could to process EVENT_POWER_RAIL_SET_VOLTAGE event");
        return false;
    }

    return true;
}

/**
 * @brief Requests the voltage value from the MCP4017 digital potentiometer.
 *
 * @param app Pointer to the application's information and state.
 * @param status Pointer to a variable where the status of the operation will be stored.
 *
 * @return bool True if the read operation was successful, false otherwise.
 *
 * This function creates an event to read the voltage value of the MCP4017 digital potentiometer.
 */
bool app_read_mcp4017_voltage(app_info_t *app, int32_t *status)
{
    event_opt_digital_pot_data_t opt =
    {
        .desired_voltage = 0,
        .status = status
    };

    if (!create_event_entry(app, EVENT_POWER_RAIL_READ_VOLTAGE, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could to process EVENT_POWER_RAIL_READ_VOLTAGE event");
        return false;
    }

    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                   multiplexer sn74lv4051a Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Reads all channels of the SN74LV4051A multiplexer.
 *
 * @param app Pointer to the application's information and state.
 * @param adc_values Pointer to an array where ADC values will be stored.
 *
 * This function creates an event to read all channels of the SN74LV4051A multiplexer and store the ADC values.
 */
bool app_read_sn74lv4051a_all_channels(app_info_t *app, int32_t *adc_values, uint32_t delay_ms, int32_t *status)
{
    event_opt_mux_data_t opt =
    {
        .adc_array = adc_values,
        .mux_adc_value = NULL,
        .mux_channel = CHANNEL_MAX,
        .delay_ms = delay_ms,
        .status = status
    };

    if (!create_event_entry(app, EVENT_MUX_READ_ALL_CHANNELS, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could to process EVENT_MUX_READ_ALL_CHANNELS event");
        return false;
    }

    return true;
}

/**
 * @brief Reads a specific channel of the SN74LV4051A multiplexer.
 *
 * @param app Pointer to the application's information and state.
 * @param mux_channel The channel to be read.
 * @param adc_value Pointer to a variable where the ADC value will be stored.
 * @param delay_ms The delay in milliseconds before reading the ADC value.
 * @param status Pointer to a variable where the status of the operation will be stored.
 *
 * @return bool True if the read operation was successful, false otherwise.
 *
 * This function creates an event to read a specific channel of the SN74LV4051A multiplexer.
 */
bool app_read_sn74lv4051a_channel(app_info_t *app, mux_channel_t mux_channel, int32_t *adc_value, uint32_t delay_ms, int32_t *status)
{
    event_opt_mux_data_t opt =
    {
        .adc_array = NULL,
        .mux_adc_value = adc_value,
        .mux_channel = mux_channel,
        .delay_ms = delay_ms,
        .status = status
    };

    if (!create_event_entry(app, EVENT_MUX_READ_CHANNEL, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could to process EVENT_MUX_READ_CHANNEL event");
        return false;
    }

    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                       MTIB power managment Functions
 *---------------------------------------------------------------------------------------------------*/

bool app_power_enable(app_info_t *app, uint8_t enable)
{
    event_opt_charger_en_t opt =
    {
        .enable = enable
    };
    if (!create_event_entry(app, EVENT_DUT_POWER_ENABLE, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could not create EVENT_DUT_POWER_ENABLE event");
        return false;
    }

    return true;
}

bool app_charger_enable(app_info_t *app, uint8_t enable)
{
    event_opt_power_en_t opt =
    {
        .enable = enable
    };
    if (!create_event_entry(app, EVENT_DUT_CHARGE_ENABLE, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could not create EVENT_DUT_CHARGE_ENABLE event");
        return false;
    }

    return true;
}

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       GPIO Functions
 *---------------------------------------------------------------------------------------------------*/

bool app_gpio_configure(app_info_t *the_app, uint8_t pin, gpio_flags_t direction, int32_t *status)
{
    event_opt_gpio_t opt =
    {
        .pin = pin,
        .state = 0x00, // does not matter here
        .flag = direction,
        .status = status
    };

    if (!create_event_entry(the_app, EVENT_GPIO_CONFIGURE, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could not create EVENT_GPIO_CONFIGURE event");
        return false;
    }

    return true;
}

bool app_gpio_set(app_info_t *the_app, uint8_t pin, uint8_t value, int32_t *status)
{
    event_opt_gpio_t opt =
    {
        .pin = pin,
        .state = &value,
        .flag = 0x00, // does not matter here
        .status = status
    };

    if (!create_event_entry(the_app, EVENT_GPIO_SET, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could not create EVENT_GPIO_SET event");
        return false;
    }

    return true;
}

bool app_gpio_read(app_info_t *the_app, uint8_t pin, int32_t *status)
{
    uint8_t reading = 0;

    event_opt_gpio_t opt =
    {
        .pin = pin,
        .state = &reading, // does not matter here
        .flag = 0x00, // does not matter here
        .status = status
    };

    if (!create_event_entry(the_app, EVENT_GPIO_READ, (void *)&opt, sizeof(opt)))
    {
        LOG_ERR("could not create EVENT_GPIO_READ event");
        return false; // False but function failedl
    }

    if (reading > 0)
    {
        return true;
    }

    return false; // This is false but fucntion success
}

