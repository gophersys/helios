#ifndef MTIB_ZEPHYR_APP_H
#define MTIB_ZEPHYR_APP_H

#include <stdbool.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>

#define APP_THREAD_PRIORITY 10
#define APP_CURRENT_THREAD_PRIORITY 11
#define APP_THREAD_STACK_SIZE 5000
#define EVENTS_HEAP_SIZE 1024
#define SET_FREQUENCY_Hz(X) (1000 / (X))

#define ON 1
#define OFF 0
#define VOLTAGE_TOLERANCE_mV 50
/**
 * @struct bmp390_info_t
 * @brief Structure to hold BMP390 sensor data and synchronization semaphore.
 */
typedef struct
{
    double pressure;             /**< Pressure reading */
    double temperature;          /**< Temperature reading */
    double altitude;             /**< Altitude reading */

    double fixture_altitude_ft;  /**< Current altitude in feet */

    struct k_sem await_sem;      /**< Semaphore for synchronization */
} bmp390_info_t;

/**
 * @struct lis2de12_info_t
 * @brief Structure to hold LIS2DE12 sensor data and synchronization semaphore.
 */
typedef struct
{
    const struct device *lis2de12_device; /**< I2C device pointer */

    double acc_x;                /**< Acceleration data in X direction */
    double acc_y;                /**< Acceleration data in Y direction */
    double acc_z;                /**< Acceleration data in Z direction */
    double avg_force;            /**< Accelerameter data avg force */
    double max_force;            /**< Accelerameter data max force */

    struct k_sem await_sem;      /**< Semaphore for synchronization */
} lis2de12_info_t;

/**
 * @struct ina219_info_t
 * @brief Structure to hold INA219 sensor data, configuration settings, and synchronization semaphore.
 */
typedef struct
{
    const struct device *ina219_device; /**< I2C device pointer */

    struct sensor_value bus_voltage; /**< Bus voltage data */
    struct sensor_value current;     /**< Current data */
    struct sensor_value power;       /**< Power data */

    struct k_sem ina219_sem;          /**< Semaphore for synchronization */
} ina219_info_t;

/**
 * @struct m24c08_info_t
 * @brief Structure to hold M24C08 EEPROM data and synchronization semaphore.
 */
typedef struct
{
    const struct device *m24c08_device; /**< I2C device pointer for communication with the EEPROM */

    uint16_t eeprom_address; /**< EEPROM-specific information like address */
    uint16_t page_size;      /**< EEPROM page size */
    uint16_t max_size;       /**< Maximum size of EEPROM */

    struct k_sem await_sem;  /**< Semaphore for synchronization */
} m24c08_info_t;

/**
 * @struct mcp4017_info_t
 * @brief Structure to hold MCP4017 potentiometer data and synchronization semaphore.
 */
typedef struct
{
    const struct device *i2c_device; /**< I2C device pointer for communication */

    uint8_t potentiometer_value; /**< Current value of the potentiometer (0-127) */
    float voltage_value;         /**< Voltage value */

    struct k_sem await_sem;      /**< Semaphore for synchronization */
} mcp4017_info_t;

/**
 * @struct mux_device_info_t
 * @brief Structure to hold MUX device ADC value.
 */
typedef struct
{
    int32_t mux_adc_value;       /**< int32 value */
} mux_device_info_t;

/**
 * @struct eeprom_info_t
 * @brief Structure to hold EEPROM data.
 */
typedef struct
{
    uint8_t *data; /**< Pointer to EEPROM data */
} eeprom_info_t;

/**
 * @struct gpio_info_t
 * @brief Structure to hold GPIO pin and state.
 */
typedef struct
{
    uint8_t pin; /**< GPIO pin */
    uint8_t state; /**< GPIO state */
} gpio_info_t;

/**
 * @enum mux_channel_t
 * @brief Enumeration for MUX channel identifiers.
 */
typedef enum
{
    CHANNEL_0,
    CHANNEL_1,
    CHANNEL_2,
    CHANNEL_3,
    CHANNEL_4,
    CHANNEL_5,
    CHANNEL_6,
    CHANNEL_7,
    CHANNEL_MAX
} mux_channel_t;

/**
 * @enum event_type_t
 * @brief Enumeration for different types of events.
 */
typedef enum
{
    /* BMP ENUMS */
    EVENT_BMP_GET_ALTITUDE,
    EVENT_BMP_GET_TEMPERATURE,
    EVENT_BMP_GET_PRESSURE,
    EVENT_BMP_PRINT_ALL_MEASUREMENTS,
    /* ACCEL ENUMS */
    EVENT_ACCEL_GET_AVG_FORCE,
    EVENT_ACCEL_GET_MAX_FORCE,
    EVENT_ACCEL_GET_XYZ_FORCES,
    EVENT_ACCEL_PRINT_FORCES,
    /* INA209 ENUMS */
    EVENT_INA219_GET_VOLTAGE_V,
    EVENT_INA219_GET_POWER_W,
    EVENT_INA219_GET_CURRENT_A,
    EVENT_INA219_PRINT_ALL_MEASUREMENTS,
    /* EEPROM ENUMS*/
    EVENT_WRITE_TO_EEPROM,
    EVENT_READ_FROM_EEPROM,
    EVENT_CLEAR_EEPROM,
    /* MUX NUMS*/
    EVENT_MUX_READ_ALL_CHANNELS,
    EVENT_MUX_READ_CHANNEL,
    /* DIGITAL POT ENUMS*/
    EVENT_POWER_RAIL_SET_VOLTAGE,
    EVENT_POWER_RAIL_READ_VOLTAGE,
    EVENT_POWER_RAIL_PRINT_DATA,
    /* DUT POWER MANAGAMENT */
    EVENT_DUT_POWER_ENABLE,
    EVENT_DUT_CHARGE_ENABLE,
    /* GPIO ENUMS */
    EVENT_GPIO_CONFIGURE,
    EVENT_GPIO_SET,
    EVENT_GPIO_READ,

    EVENT_MAX
} event_type_t;

/**
 * @struct event_t
 * @brief Structure used for linked list in event handling.
 */
typedef struct
{
    uintptr_t __k_reserved;      /**< Reserved field */
    event_type_t type;           /**< Type of the event */
    void *options;               /**< Pointer to event options */
    size_t options_size;         /**< Size of options */
    struct k_sem sem;            /**< Semaphore for synchronization */
} event_t;

/**
 * @struct event_opt_ina219_set_power_t
 * @brief Structure for INA219 set power event options.
 */
typedef struct
{
    double desired_power;        /**< Desired power value */
} event_opt_ina219_set_power_t;

/**
 * @struct event_opt_digital_pot_set_voltage_t
 * @brief Structure for digital potentiometer set voltage event options.
 */
typedef struct
{
    uint32_t desired_voltage;      /**< Desired voltage value in mV */
} event_opt_digital_pot_set_voltage_t;

/**
 * @struct event_opt_mux_data_t
 * @brief Structure for MUX data event options.
 */
typedef struct
{
    int32_t *adc_array;          /**< Array of ADC values */
    int32_t *mux_adc_value;       /**< MUX ADC value */
    mux_channel_t mux_channel;   /**< MUX channel */
    uint32_t delay_ms;           /**< Delay in milliseconds */
} event_opt_mux_data_t;

/**
 * @struct event_opt_eeprom_t
 * @brief Structure for EEPROM event options.
 */
typedef struct
{
    uint16_t memory_address;     /**< Memory address */
    uint8_t *data;               /**< Pointer to data */
    size_t len;                  /**< Length of data */
} event_opt_eeprom_t;

/**
 * @struct event_opt_lis2de12_t
 * @brief Structure for LIS2DE12 event options.
 */
typedef struct
{
    bool reset_value;     /**< Flag to reset event value */
} event_opt_lis2de12_t;

/**
 * @struct event_opt_power_en_t
 * @brief Structure for power enable event options.
 */
typedef struct
{
    bool enable; /**< Flag to enable or disable power */
} event_opt_power_en_t;

/**
 * @struct event_opt_charger_en_t
 * @brief Structure for charger enable event options.
 */
typedef struct
{
    bool enable; /**< Flag to enable or disable charger */
} event_opt_charger_en_t;

/**
 * @struct event_opt_gpio_t
 * @brief Structure for GPIO event options.
 */
typedef struct
{
    gpio_flags_t flag; /**< GPIO flag to configure the GPIO  */
    uint8_t pin; /**< GPIO pin */
    uint8_t *state; /**< GPIO state */
} event_opt_gpio_t;


/**
 * @struct thread_info_t
 * @brief Thread information structure.
 */
typedef struct
{
    /*-----------------------------------------------
     *                                        Threads
     *---------------------------------------------*/
    k_tid_t t_id;                  /**< Thread ID */
    struct k_thread t_data;       /**< Thread data */
    /*-----------------------------------------------
     *                                   Thread stack
     *---------------------------------------------*/
    K_THREAD_STACK_MEMBER(t_stack, APP_THREAD_STACK_SIZE); /**< Thread stack */
} thread_info_t;


/**
 * @struct app_info_t
 * @brief Application information structure.
 */
typedef struct
{

    /*-----------------------------------------------
     *                                        Threads
     *---------------------------------------------*/
    thread_info_t event_handler_thread; /**< Event handler thread */
    thread_info_t over_current_thread;  /**< Over current thread */

    /*-----------------------------------------------
     *                                         Queues
     *---------------------------------------------*/
    struct k_fifo command_event_queue;  /**< Command event queue */

    /*-----------------------------------------------
     *                                          Heaps
     *---------------------------------------------*/

    /**
     * @brief Heap pool to send events to thread
     */
    struct k_heap app_events_heap; /**< Heap pool for events */
    uint8_t __aligned(8) app_events_heap_mem[EVENTS_HEAP_SIZE]; /**< Heap memory alignment */

    /*-----------------------------------------------
     *                                        Devices
     *---------------------------------------------*/
    bmp390_info_t bmp390_dev;                /**< BMP390 device information */
    eeprom_info_t eeprom_dev;                /**< EEPROM device information */
    ina219_info_t ina219_dev;                /**< INA219 device information */
    lis2de12_info_t lis2de12_dev;            /**< LIS2DE12 device information */
    m24c08_info_t m24c08_dev;                /**< M24C08 device information */
    mcp4017_info_t mcp4017_dev;              /**< MCP4017 device information */
    mux_device_info_t mux_dev;               /**< MUX device information */
    gpio_info_t gpio_dev;                    /**< GPIO device information */

} app_info_t;

/*-----------------------------------------------------------------------------------------------------
 *                                                                                Application Functions
 *---------------------------------------------------------------------------------------------------*/
void app_mtib_init(app_info_t *app);
app_info_t *app_get_ptr(void);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                   lis2de12 Functions
 *---------------------------------------------------------------------------------------------------*/
lis2de12_info_t *app_get_lis2de12_info(void);
/**
 * @brief prints the xyz forces from the LIS2DE12 accelerometer
 *
 * @param app  pointer to app_info_t struct
 */
void app_print_lis2de12_data(app_info_t *app);

/**
 * @brief gets the average force from the LIS2DE12 accelerometer
 *
 * @param app  pointer to app_info_t struct
 * @param reset_value  flag to reset the value
 * @return true  if successful
 * @return false  if unsuccessful
 */
bool app_get_lis2de12_avg_force(app_info_t *app, bool reset_value);

/**
 * @brief gets the max force from the LIS2DE12 accelerometer
 *
 * @param app  pointer to app_info_t struct
 * @param reset_value  flag to reset the value
 * @return true  if successful
 * @return false  if unsuccessful
 */
bool app_get_lis2de12_max_force(app_info_t *app, bool reset_value);

/**
 * @brief gets the xyz forces from the LIS2DE12 accelerometer
 *
 * @param app  pointer to app_info_t struct
 */
void app_get_lis2de12_xyz_forces(app_info_t *app);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     bmp390 Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief returns a pointer to the bmp390_info_t struct
 *
 * @return bmp390_info_t*
 */
bmp390_info_t *app_get_bmp390_info(void);

/**
 * @brief prints the temperature, pressure, and altitude from the BMP390 altimeter
 *
 * @param temperature  pointer to temperature variable
 * @param pressure  pointer to pressure variable
 * @param altitude  pointer to altitude variable
 */
void app_print_bmp390_data(double *temperature, double *pressure, double *altitude);

/**
 * @brief gets the altitude from the BMP390 altimeter
 *
 * @param app  pointer to app_info_t struct
 * @return true  if successful
 * @return false  if unsuccessful
 */
bool app_get_bmp390_altitude(app_info_t *app);

/**
 * @brief gets the temperature from the BMP390 altimeter
 *
 * @param app  pointer to app_info_t struct
 * @return true  if successful
 * @return false  if unsuccessful
 */
bool app_get_bmp390_pressure(app_info_t *app);

/**
 * @brief gets the pressure from the BMP390 altimeter
 *
 * @param app  pointer to app_info_t struct
 * @return true  if successful
 * @return false  if unsuccessful
 */
bool app_get_bmp390_temperature(app_info_t *app);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     ina290 Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief returns a pointer to the ina219_info_t struct
 *
 * @return ina219_info_t*
 */
ina219_info_t *app_get_ina219_info(void);

/**
 * @brief prints the voltage, power, and current from the INA219 sensor
 *
 * @param app  pointer to app_info_t struct
 */
void app_print_ina219_data(app_info_t *app);


/*-----------------------------------------------------------------------------------------------------
 *                                                                                     m24c08 Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief returns a pointer to the m24c08_info_t struct
 *
 * @return m24c08_info_t*
 */
m24c08_info_t *app_get_eeprom_info(void);

/**
 * @brief writes data to the EEPROM
 *
 * @param app  pointer to app_info_t struct
 * @param memory_address memory address to write to
 * @param data pointer to data to write
 * @param len length of data to write
 *
 * This function will create a new event and add it to the event queue given eeprom address, data, and length.
 */

void app_write_to_eeprom(app_info_t *app, uint16_t memory_address, uint8_t *data, size_t len);

/**
 * @brief reads data from the EEPROM
 *
 * @param app  pointer to app_info_t struct
 * @param memory_address memory address to read from
 * @param data pointer to data to read
 * @param len length of data to read
 *
 * This function will create a new event and add it to the event queue given eeprom address, data, and length.
 */
void app_read_from_eeprom(app_info_t *app, uint16_t memory_address, uint8_t *data, size_t len);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    mcp4017 Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief returns a pointer to the mcp4017_info_t struct
 *
 * @return mcp4017_info_t*
 */
mcp4017_info_t *app_get_mcp4017_info(void);

/**
 * @brief prints the sensor data from the MCP4017 digital potentiometer
 *
 * @param app  pointer to app_info_t struct
 */
void app_print_mcp4017_data(app_info_t *app);

/**
 * @brief sets the voltage output of the MCP4017 digital potentiometer
 *
 * @param app  pointer to app_info_t struct
 * @param voltage  voltage value to set
 */
void app_set_mcp4017_voltage_output(app_info_t *app, uint32_t voltage);

/**
 * @brief reads the voltage output of the MCP4017 digital potentiometer
 *
 * @param app  pointer to app_info_t struct
 */
void app_read_mcp4017_voltage(app_info_t *app);

/*-----------------------------------------------------------------------------------------------------
 *                                                                   multiplexer sn74lv4051a Functions
 *---------------------------------------------------------------------------------------------------*/

/**
* @brief reads all channels of the SN74LV4051A multiplexer
*
* @param app pointer to app_info_t struct
* @param adc_values pointer to ADC values
* @param delay_ms delay in milliseconds
*
* @return true if successful
* @return false if unsuccessful
*/
void app_read_sn74lv4051a_all_channels(app_info_t *app, int32_t *adc_values, uint32_t delay_ms);

/**
 * @brief reads a single channel of the SN74LV4051A multiplexer
 *
 * @param app pointer to app_info_t struct
 * @param channel channel to read
 * @param adc_value pointer to ADC value
 * @param delay_ms delay in milliseconds
 *
 * @return true if successful
 * @return false if unsuccessful
 */
bool app_read_sn74lv4051a_channel(app_info_t *app, mux_channel_t channel, int32_t *adc_value, uint32_t delay_ms);

/*-----------------------------------------------------------------------------------------------------
 *                                                                       MTIB power managment Functions
 *---------------------------------------------------------------------------------------------------*/
/**
 * @brief Enables or disables power to the DUT (Device Under Test).
 *
 * @param app Pointer to app_info_t struct providing context for the operation.
 * @param enable A uint8_t value where 1 enables power and 0 disables it.
 */
bool app_power_enable(app_info_t *app, uint8_t enable);

/**
 * @brief Enables or disables the charger functionality.
 *
 * @param app Pointer to app_info_t struct providing context for the operation.
 * @param enable A uint8_t value where 1 enables the charger and 0 disables it.
 */
bool app_charger_enable(app_info_t *app, uint8_t enable);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       GPIO Functions
 *---------------------------------------------------------------------------------------------------*/

/**
 * @brief Configures a GPIO pin.
 *
 * @param app pointer to app_info_t struct
 * @param pin  GPIO pin
 * @param state  GPIO state
 *
 * @return true if successful
 * @return false if unsuccessful
 */
bool app_gpio_configure(app_info_t *app, uint8_t pin, gpio_flags_t direction);

/**
 * @brief Sets the state of a GPIO pin.
 *
 * @param app Pointer to app_info_t struct providing context for the operation.
 * @param pin The pin number to set the state of.
 * @param state The state to set the pin to.
 *
 * @return true if successful
 * @return false if unsuccessful
 */
bool app_gpio_set(app_info_t *app, uint8_t pin, uint8_t state);

/**
 * @brief Reads the state of a GPIO pin.
 *
 * @param app Pointer to app_info_t struct providing context for the operation.
 * @param pin The pin number to read the state of.
 *
 * @return true if the pin is high
 * @return false if the pin is low
 */
bool app_gpio_read(app_info_t *app, uint8_t pin);

#endif /* MTIB_ZEPHYR_APP_H */