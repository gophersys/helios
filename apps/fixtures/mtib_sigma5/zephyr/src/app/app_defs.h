#ifndef APP_DEFS_H
#define APP_DEFS_H

#include <zephyr/kernel.h>

#define APP_THREAD_STACK_SIZE 1024
#define EVENTS_HEAP_SIZE 1024
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

} app_info_t;

typedef enum
{
    PWR_GPIO = 0,
    CHG_GPIO
}dut_gpio_e;


void calibrate_potentiometer(app_info_t *app);
void read_calibrated_pot_values(void);
void set_desired_volatge(uint32_t desired_voltage);


// app INA219 functions
void init_ina219(app_info_t *app);
void ina219_get_current(app_info_t *app);
void ina219_get_voltage(app_info_t *app);
void ina219_get_power(app_info_t *app);

// DUT functions
void init_dut_gpios(void);
uint8_t is_enabled(dut_gpio_e pin);
bool is_correct_voltage(app_info_t *app, uint32_t desired_voltage);


// power management functions
void power_on(void);
void power_off(void);
void charge_on(void);
void charge_off(void);
void turn_on_mtib(app_info_t *app, uint32_t desired_voltage);


#endif // APP_DEFS_H
