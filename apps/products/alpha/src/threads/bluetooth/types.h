#ifndef THREAD_BLUETOOTH_TYPES_H
#define THREAD_BLUETOOTH_TYPES_H

// Standard includes
#include <stdbool.h>
#include <stdint.h>

// Zephyr includes
#include <zephyr/bluetooth/conn.h>
#include <zephyr/kernel.h>

/**
 * @brief The priority for the bluetooth thread
 */
#define CONFIG_BLUETOOTH_THREAD_PRIORITY 118

/**
 * @brief Configuration constants for the bluetooth thread
 *
 */
#define CONFIG_BLUETOOTH_THREAD_STACK_SIZE 4096

/**
 * @brief The size of the heap for the accel data
 */
#define CONFIG_BLUETOOTH_THREAD_DATA_HEAP_SIZE 10240 * 2

/**
 * @brief The events for the bluetooth thread
 */
typedef enum {
    BLUETOOTH_THREAD_EVENT_CONNECTED,
    BLUETOOTH_THREAD_EVENT_DISCONNECTED,
    BLUETOOTH_THREAD_EVENT_TIMER_25HZ,
    BLUETOOTH_THREAD_EVENT_TIMER_32HZ,

    // Total number of events
    BLUETOOTH_THREAD_EVENT_COUNT,
} bluetooth_thread_event_t;

typedef enum {
    BLUETOOTH_THREAD_DATA_TYPE_SENSOR_DATA_25HZ,
    BLUETOOTH_THREAD_DATA_TYPE_SENSOR_DATA_32HZ,
    BLUETOOTH_THREAD_DATA_TYPE_PSP_INPUT_DATA_32HZ,
    BLUETOOTH_THREAD_DATA_TYPE_PSP_READ_INPUT_DATA_32HZ,

    BLUETOOTH_THREAD_DATA_TYPE_COUNT,
} bluetooth_thread_data_type_t;

typedef struct {
    uintptr_t __k_reserved;
    bluetooth_thread_data_type_t type;
    uint8_t *data;
} bluetooth_thread_data_t;

typedef struct {
    float x;
    float y;
    float z;
} accelerometer_data_t;

typedef struct {
    uint32_t red_intensity;
    uint32_t green_intensity;
    uint32_t ir_intensity;
} ppg_intensity_data_t;

typedef struct {
    uintptr_t __k_reserved;
    accelerometer_data_t accelerometer;
    ppg_intensity_data_t ppg_intensity;
} sensor_data_t;

typedef struct {
    int32_t dummy;
    int16_t dummy2;
    int16_t x;
    int16_t y;
    int16_t z;
} psp_input_accelerometer_data_t;

typedef struct {
    int32_t dummy;
    uint16_t ambient_intensity;
    uint16_t red_intensity;
    uint16_t green_intensity;
    uint16_t ir_intensity;
} psp_input_ppg_intensity_data_t;

typedef struct {
    uintptr_t __k_reserved;
    psp_input_accelerometer_data_t accelerometer;
    psp_input_ppg_intensity_data_t ppg_intensity;
} psp_input_data_t;

/**
 * @brief Configuration structure for the bluetooth thread
 */
typedef struct {
    bool ppg_data_enabled;
    bool accel_data_enabled;
} bluetooth_thread_config_t;

/**
 * @brief Structure for the bluetooth thread
 */
typedef struct {
    // Configuration
    const bluetooth_thread_config_t *config;

    // Thread info
    k_tid_t tid;
    struct k_thread thread;
    K_THREAD_STACK_MEMBER(stack, CONFIG_BLUETOOTH_THREAD_STACK_SIZE);

    // Bluetooth connection
    struct bt_conn *current_conn;
    bool notify_25hz_ppg_intensity_enabled;
    bool notify_32hz_ppg_intensity_enabled;
    bool notify_25hz_accel_enabled;
    bool notify_32hz_accel_enabled;
    bool notify_32hz_psp_ppg_intensity_enabled;
    bool notify_32hz_psp_accel_enabled;
    bool notify_32hz_psp_read_ppg_intensity_enabled;
    bool notify_32hz_psp_read_accel_enabled;

    // Events
    struct k_poll_event events[BLUETOOTH_THREAD_EVENT_COUNT];
    struct k_sem connected_sem;
    struct k_sem disconnected_sem;
    struct k_sem timer_sem_25hz;
    struct k_sem timer_sem_32hz;

    // Timer
    struct k_timer timer_25hz;
    struct k_timer timer_32hz;

    // Queues
    struct k_fifo data_fifo_25hz;
    struct k_fifo data_fifo_32hz;
    struct k_fifo data_fifo_psp_32hz;
    struct k_fifo data_fifo_psp_read_32hz;

    // Heap for data
    struct k_heap data_heap;
    uint8_t __aligned(8) data_heap_mem[CONFIG_BLUETOOTH_THREAD_DATA_HEAP_SIZE];
} bluetooth_thread_t;

#endif
