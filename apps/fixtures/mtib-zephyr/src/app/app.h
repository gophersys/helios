#ifndef MTIB_ZEPHYR_APP_H
#define MTIB_ZEPHYR_APP_H

#include <stdbool.h>
#include <stdint.h>
#include <zephyr/device.h>
#include <zephyr/kernel.h>

#define APP_THREAD_PRIORITY 10
#define APP_THREAD_STACK_SIZE 1024
#define EVENTS_HEAP_SIZE 1024


typedef struct {
    // Readings
    double pressure;
    double temperature;
    double altitude;

    // Current altitude
    double fixture_altitude_ft;

    // Semaphore for syncronization
    struct k_sem await_sem;

} bmp390_info_t;

typedef struct {
    // I2C device pointer
    const struct device *lis2de12_device;

    // Readings
    // Acceleration data
    double acc_x;
    double acc_y;
    double acc_z;

    // Semaphore for syncronization
    struct k_sem await_sem;

} lis2de12_info_t;

typedef struct {
    // I2C device pointer
    const struct device *ina219_device;

    // INA219 specific data
    double bus_voltage;
    double shunt_voltage;
    double current;
    double power;

    // Configuration settings
    // You can add fields for specific configuration settings like voltage range,
    // gain, bus and shunt ADC resolution, etc.

    // Semaphore for syncronization
    struct k_sem await_sem;

} ina219_info_t;

typedef struct {
    // I2C device pointer for communication with the EEPROM
    const struct device *m24c08_device;

    // EEPROM-specific information, like address, page size, etc.
    uint16_t eeprom_address;
    uint16_t page_size;

    // Semaphore for syncronization
    struct k_sem await_sem;

} m24c08_info_t;

typedef struct {

    // I2C device pointer for communication
    const struct device *i2c_device;

    // MCP4017 specific information
    uint8_t potentiometer_value;  // Current value of the potentiometer (0-127)

    // Semaphore for syncronization
    struct k_sem await_sem;

} mcp4017_info_t;

typedef enum {
    CHANNEL_0 = 0,
    CHANNEL_1,
    CHANNEL_2,
    CHANNEL_3,
    CHANNEL_4,
    CHANNEL_5,
    CHANNEL_6,
    CHANNEL_7,
    MAX_NUM_CHANNELS
} mux_channel_t;



// creating the command type for the even loop 
typedef enum
{
    EVENT_CMD_READ = 0, 
    EVENT_CMD_WRITE
} command_t;

typedef enum {
    DEVICE_TYPE_BMP390 = 0,
    DEVICE_TYPE_LIS2DE12,
    DEVICE_TYPE_INA219,
    DEVICE_TYPE_MC24C08,
    DEVICE_TYPE_MCP4017
} device_Type_t;

typedef struct {

    /*-----------------------------------------------
     *                                   device types
     *---------------------------------------------*/
    device_Type_t type;
    /*-----------------------------------------------
     *                                 device structs
     *---------------------------------------------*/
    bmp390_info_t bmp390_dev;
    lis2de12_info_t lis2de12_dev;
    ina219_info_t ina219_dev;
    m24c08_info_t m24c08_dev;
    mcp4017_info_t mcp4017_dev;
    
} device_t;

// create an event handler type
typedef struct
{
    void *fifo_reserved; // used internally by k_fifo
    command_t command;
    device_t *device;
}Event_t;


typedef struct 
{
    /*-----------------------------------------------
     *                                        Threads
     *---------------------------------------------*/
    k_tid_t t_id;
    struct k_thread t_data;

    /*-----------------------------------------------
     *                                         Queues
     *---------------------------------------------*/
    struct k_fifo command_event_queue;

    /*-----------------------------------------------
     *                                          Heaps
     *---------------------------------------------*/

    /**
     * @brief Heap pool to send events to thread
     */
    struct k_heap app_events_heap;
    uint8_t __aligned(8) app_events_heap_mem[EVENTS_HEAP_SIZE];

}app_info_t;


/*-----------------------------------------------------------------------------------------------------
 *                                                                                Application Functions
 *---------------------------------------------------------------------------------------------------*/
void app_sim_start(app_info_t *app);
void app_init_devices(void);
void app_init_threads(app_info_t *app);
void app_process_event(Event_t *event);
void app_heap_init(app_info_t *app);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                       FIFO Functions
 *---------------------------------------------------------------------------------------------------*/
void app_add_event_to_fifo(app_info_t *app, device_t *device,  command_t command);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                   lis2de12 Functions
 *---------------------------------------------------------------------------------------------------*/
lis2de12_info_t *app_get_lis2de12_info(void);

void app_print_lis2de12_data(double *accel_x, double *accel_y, double *accel_z);
bool app_set_lis2de12_direction(lis2de12_info_t *app, double accel_x, double accel_y, double accel_z);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    bmp390 Functions
 *---------------------------------------------------------------------------------------------------*/
bmp390_info_t *app_get_bmp390_info(void);
void app_print_bmp390_data(double *temperature, double *pressure, double *altitude);
bool app_set_bmp390_altitude(bmp390_info_t *app, double alt);
bool app_set_bmp390_pressure(bmp390_info_t *app, double pres);
bool app_set_bmp390_temperature(bmp390_info_t *app, double temp);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     ina290 Functions
 *---------------------------------------------------------------------------------------------------*/
ina219_info_t *app_get_ina219_info(void);
void app_print_ina219_data(double *bus_voltage, double *shunt_voltage, double *current, double *power);
bool app_set_ina219_power(ina219_info_t *app, double pow);
bool app_set_ina219_current(ina219_info_t *app, double cur);
bool app_set_ina219_bus_voltage(ina219_info_t *app, double bv);
bool app_set_ina219_shunt_voltage(ina219_info_t *app, double sv);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                     m2c08 Functions
 *---------------------------------------------------------------------------------------------------*/
m24c08_info_t *app_get_eeprom_info(void);
void app_write_to_eeprom(const struct device *dev, uint16_t address);
void app_read_from_eeprom(const struct device *dev, uint16_t address);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    mcp4017 Functions
 *---------------------------------------------------------------------------------------------------*/
mcp4017_info_t *app_get_mcp4017_info(void);
void app_print_mcp4017_data(uint8_t *value);
void app_set_mcp4017_voltage_output(uint32_t voltage);
uint32_t app_read_mcp4017_voltage(const struct device *dev);

/*-----------------------------------------------------------------------------------------------------
 *                                                                                    mux Functions
 *---------------------------------------------------------------------------------------------------*/
void app_read_sn74lv4051a_all_channels(uint32_t *AdcValues);
uint32_t app_read_sn74lv4051a_channel(mux_channel_t channel);
#endif /* MTIB_ZEPHYR_APP_H */