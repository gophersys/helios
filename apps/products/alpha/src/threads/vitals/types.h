#ifndef THREADS_VITALS_TYPES_H_
#define THREADS_VITALS_TYPES_H_

// Standard includes
#include <stdbool.h>
#include <stdint.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/sys/ring_buffer.h>
// Corekinect includes
#include <corekinect/sensor/pah8151.h>

// Phillips Biosensing Platform Library includes
#include "../../../lib/inc/fx_datatypes.h"
#include "../../../lib/inc/psp.h"

/**
 * @brief Configuration constants for the vitals thread
 *
 */
#define CONFIG_VITALS_THREAD_STACK_SIZE 4096

/**
 * @brief The size of the PSP algorithm heap
 */
#define CONFIG_PSP_MEMORY_SIZE 27000

/**
 * @brief The number of events for the vitals thread
 */
#define CONFIG_VITALS_THREAD_NUM_EVENTS 2

/**
 * @brief The accelerometer number of samples per second
 */
#define CONFIG_ACCEL_RING_BUF_COUNT 26

/**
 * @brief The number of PPG samples per second
 */
#define CONFIG_PPG_SAMPLES_PER_BATCH 25

/**
 * @brief The number of samples per second for the PSP algorithm
 */
#define CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND 32

/**
 * @brief The maximum number of metrics for the PSP algorithm
 */
#define CONFIG_PSP_MAX_METRICS 15

/**
 * @brief The events for the vitals thread
 */
typedef enum {
    VITALS_THREAD_EVENT_PPG_DATA_READY,
    VITALS_THREAD_EVENT_PPG_TOUCH,
} vitals_thread_event_t;

/**
 * @brief Configuration structure for the vitals thread
 */
typedef struct {
    // Devices used by this thread
    const struct device *p_ppg_dev;
    const struct device *p_imu_dev;
} vitals_thread_config_t;

/**
 * @brief Accelerometer sample structure
 *
 * This struct is used to "buffer" the accelerometer samples, as
 * the interrupts are triggered every time a new sample is available.
 *
 * Once the PPG sensor triggers, the samples stored in this buffer
 * are processed and the buffer is cleared.
 */
typedef struct {
    int64_t timestamp;
    float x;
    float y;
    float z;
} accel_interrupt_sample_t;

/**
 * @brief Combined sample structure
 *
 * This struct is used to store the PPG samples and the interpolated
 * accelerometer samples to 25Hz.
 */
typedef struct {
    pah8151_ppg_sample_t ppg;  // Direct copy of PPG sample
    float accel_x;             // Interpolated accelerometer values
    float accel_y;
    float accel_z;
} sensors_sample_t;

typedef struct {
    // PPG Signal
    uint16_t ppg_ir;
    uint16_t ppg_red;
    uint16_t ppg_green;
    uint16_t ppg_ambient;

    // Accelerometer Signal
    int16_t accel_x;
    int16_t accel_y;
    int16_t accel_z;
} psp_algorithm_input_metrics_t;

/**
 * @brief Thread structure for the vitals thread
 */
typedef struct {
    // Configuration
    const vitals_thread_config_t *config;

    // Thread info
    k_tid_t tid;
    struct k_thread thread;
    K_THREAD_STACK_MEMBER(stack, CONFIG_VITALS_THREAD_STACK_SIZE);

    // Events
    struct k_poll_event events[CONFIG_VITALS_THREAD_NUM_EVENTS];
    struct k_sem ppg_data_ready_sem;
    struct k_sem ppg_touch_sem;

    // Buffer for accelerometer samples
    // This buffer is used to store the accelerometer samples until the PPG samples are ready
    struct ring_buf accel_interrupt_samples_buf;
    uint8_t accel_interrupt_buf_data[CONFIG_ACCEL_RING_BUF_COUNT * sizeof(accel_interrupt_sample_t)];

    // Buffer for PPG samples
    pah8151_ppg_sample_t ppg_interrupt_samples[CONFIG_PPG_SAMPLES_PER_BATCH];

    // Combined samples buffer for raw sensor data interpolated at 25Hz
    sensors_sample_t combined_samples[CONFIG_PPG_SAMPLES_PER_BATCH];

    // PSP algorithm input metrics
    psp_algorithm_input_metrics_t psp_input_metrics[CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND];

    // Touch state
    bool is_touched;

    // PSP algorithm
    PPSP_INST psp_inst;
    PSP_INST_PARAMS psp_inst_params;
    PSP_METRIC_ID psp_required_metrics[CONFIG_PSP_MAX_METRICS];
    uint8_t psp_required_metrics_count;
    struct k_heap psp_heap;
    uint8_t __aligned(8) psp_heap_mem[CONFIG_PSP_MEMORY_SIZE];
} vitals_thread_t;

#endif  // THREADS_VITALS_TYPES_H_
