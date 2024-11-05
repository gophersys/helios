#include "thread.h"

// Private thread includes
#include "types.h"
#include "utils.h"

// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/spinlock.h>
#include <zephyr/sys/ring_buffer.h>

// Corekinect includes
#include <corekinect/sensor/pah8151.h>

// Phillips Biosensing Platform Library includes
#include "../../../lib/inc/fx_datatypes.h"
#include "../../../lib/inc/psp.h"

LOG_MODULE_REGISTER(vitals, LOG_LEVEL_DBG);

/*----------------------------------------------------------------------------------------
 *                                                                            Configuration
 *--------------------------------------------------------------------------------------*/

/*----------------------------------------------------------------------------------------
 *                                                                         Static Storage
 *--------------------------------------------------------------------------------------*/
#define MAX_VITALS_THREADS 4  // Adjust based on your needs

static vitals_thread_t *s_vitals_threads[MAX_VITALS_THREADS] = {0};
static size_t s_num_threads = 0;

/*----------------------------------------------------------------------------------------
 *                                                                       Private Functions
 *--------------------------------------------------------------------------------------*/
static void _vitals_thread_entry(void *p_arg0, void *p_arg1, void *p_arg2);

vitals_thread_t *_get_thread_from_dev(const struct device *p_dev) {
    for (size_t i = 0; i < s_num_threads; i++) {
        if (s_vitals_threads[i]->config->p_ppg_dev == p_dev ||
            s_vitals_threads[i]->config->p_imu_dev == p_dev) {
            return s_vitals_threads[i];
        }
    }
    LOG_ERR("No thread found for device %p", (void *)p_dev);
    return NULL;
}

// Sensor trigger handlers
static void _ppg_data_ready_handler(const struct device *p_dev, const struct sensor_trigger *p_trig);
static void _ppg_touch_handler(const struct device *p_dev, const struct sensor_trigger *p_trig);
static void _imu_acc_trig_handler(const struct device *dev, const struct sensor_trigger *trig);
static void _imu_gyro_trig_handler(const struct device *dev, const struct sensor_trigger *trig);

/*----------------------------------------------------------------------------------------
 *                                                                                   Init
 *--------------------------------------------------------------------------------------*/
bool vitals_thread_init(const vitals_thread_config_t *p_config, vitals_thread_t *p_thread) {
    LOG_INF("Initializing vitals thread");

    // Check the configuration
    if (!_check_config(p_config)) {
        LOG_ERR("Failed to check vitals thread configuration");
        return false;
    }

    // Get the devices used by this thread
    p_thread->config = p_config;

    // Ensure the devices are ready
    if (!device_is_ready(p_thread->config->p_ppg_dev)) {
        LOG_ERR("PPG device not ready");
        return false;
    }

    if (!device_is_ready(p_thread->config->p_imu_dev)) {
        LOG_ERR("IMU device not ready");
        return false;
    }

    // Initialize thread objects
    ring_buf_init(&p_thread->accel_interrupt_samples_buf, sizeof(p_thread->accel_interrupt_buf_data), p_thread->accel_interrupt_buf_data);
    k_sem_init(&p_thread->ppg_data_ready_sem, 0, 1);
    k_sem_init(&p_thread->ppg_touch_sem, 0, 1);
    k_heap_init(&p_thread->psp_heap, p_thread->psp_heap_mem, sizeof(p_thread->psp_heap_mem));

    // Create the thread
    p_thread->tid = k_thread_create(&p_thread->thread,
                                    p_thread->stack,
                                    CONFIG_VITALS_THREAD_STACK_SIZE,
                                    (k_thread_entry_t)_vitals_thread_entry,
                                    p_thread,
                                    NULL,
                                    NULL,
                                    K_PRIO_COOP(120),
                                    0,
                                    K_NO_WAIT);

    k_thread_name_set(p_thread->tid, "vitals_thread");

    if (s_num_threads >= MAX_VITALS_THREADS) {
        LOG_ERR("Maximum number of vitals threads reached");
        return false;
    }

    s_vitals_threads[s_num_threads++] = p_thread;

    // Register PPG sensor touch handler
    struct sensor_trigger touch_trig = {
        .type = SENSOR_TRIG_PAH8151_TOUCH,
        .chan = SENSOR_CHAN_ALL,
    };
    if (sensor_trigger_set(p_thread->config->p_ppg_dev, &touch_trig, _ppg_touch_handler) != 0) {
        LOG_ERR("Failed to set PPG sensor trigger");
        return false;
    }

    // Register PPG sensor data handler
    struct sensor_trigger ppg_trig = {
        .type = SENSOR_TRIG_PAH8151_PPG_READY,
        .chan = SENSOR_CHAN_ALL,
    };
    if (sensor_trigger_set(p_thread->config->p_ppg_dev, &ppg_trig, _ppg_data_ready_handler) != 0) {
        LOG_ERR("Failed to set PPG sensor trigger");
        return false;
    }

    // Register IMU sensor data handler
    struct sensor_trigger acc_trig = {
        .type = SENSOR_TRIG_DATA_READY,
        .chan = SENSOR_CHAN_ACCEL_XYZ,
    };
    if (sensor_trigger_set(p_thread->config->p_imu_dev, &acc_trig, _imu_acc_trig_handler) != 0) {
        LOG_ERR("Failed to set IMU accelerometer trigger");
        return false;
    }

    // Register IMU sensor data handler
    struct sensor_trigger gyro_trig = {
        .type = SENSOR_TRIG_DATA_READY,
        .chan = SENSOR_CHAN_GYRO_XYZ,
    };
    if (sensor_trigger_set(p_thread->config->p_imu_dev, &gyro_trig, _imu_gyro_trig_handler) != 0) {
        LOG_ERR("Failed to set IMU gyroscope trigger");
        return false;
    }

    // Initialize PSP algorithm
    if (!_psp_init(p_thread)) {
        LOG_ERR("Failed to initialize PSP algorithm");
        return false;
    }

    return true;
}

/*----------------------------------------------------------------------------------------
 *                                                                         Sensor Triggers
 *--------------------------------------------------------------------------------------*/
static void _ppg_data_ready_handler(const struct device *p_dev, const struct sensor_trigger *p_trig) {
    vitals_thread_t *p_thread = _get_thread_from_dev(p_dev);
    if (p_thread == NULL) {
        return;
    }

    // Get how many samples to get
    struct sensor_value count_val;
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_SAMPLE_COUNT, &count_val);
    int count = count_val.val1;

    // Get the samples for the past minute (PPG data at 25Hz)
    struct sensor_value timestamp[count];
    struct sensor_value red_intensity[count], green_intensity[count], ir_intensity[count];
    struct sensor_value red_expo_us[count], green_expo_us[count], ir_expo_us[count];
    struct sensor_value red_dac[count], green_dac[count], ir_dac[count];
    struct sensor_value red_curr_ma[count], green_curr_ma[count], ir_curr_ma[count];

    // Get intensity values
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_RED_INTENSITY, red_intensity);
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_GREEN_INTENSITY, green_intensity);
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_IR_INTENSITY, ir_intensity);

    // Get exposure time values
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_RED_EXPO_US, red_expo_us);
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_GREEN_EXPO_US, green_expo_us);
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_IR_EXPO_US, ir_expo_us);

    // Get LED DAC values
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_RED_DAC, red_dac);
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_GREEN_DAC, green_dac);
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_IR_DAC, ir_dac);

    // Get current values
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_RED_CURR_MA, red_curr_ma);
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_GREEN_CURR_MA, green_curr_ma);
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_IR_CURR_MA, ir_curr_ma);

    // Get timestamps
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_TIMESTAMP, timestamp);

    // After collecting all the sensor data, prepare PSP batch
    for (int i = 0; i < count; i++) {
        p_thread->ppg_interrupt_samples[i].timestamp = ((uint64_t)timestamp[i].val2 << 32) | (uint64_t)timestamp[i].val1;

        // Get PPG data
        p_thread->ppg_interrupt_samples[i].red_intensity = red_intensity[i].val1;
        p_thread->ppg_interrupt_samples[i].green_intensity = green_intensity[i].val1;
        p_thread->ppg_interrupt_samples[i].ir_intensity = ir_intensity[i].val1;

        // Get exposure time
        p_thread->ppg_interrupt_samples[i].red_expo_us = red_expo_us[i].val1;
        p_thread->ppg_interrupt_samples[i].green_expo_us = green_expo_us[i].val1;
        p_thread->ppg_interrupt_samples[i].ir_expo_us = ir_expo_us[i].val1;

        // Get LED DAC values
        p_thread->ppg_interrupt_samples[i].red_dac = red_dac[i].val1;
        p_thread->ppg_interrupt_samples[i].green_dac = green_dac[i].val1;
        p_thread->ppg_interrupt_samples[i].ir_dac = ir_dac[i].val1;

        // Get current values
        p_thread->ppg_interrupt_samples[i].red_curr_ma = red_curr_ma[i].val1;
        p_thread->ppg_interrupt_samples[i].green_curr_ma = green_curr_ma[i].val1;
        p_thread->ppg_interrupt_samples[i].ir_curr_ma = ir_curr_ma[i].val1;
    }

    // Wake up thread
    k_sem_give(&p_thread->ppg_data_ready_sem);
}

static void _ppg_touch_handler(const struct device *p_dev, const struct sensor_trigger *p_trig) {
    vitals_thread_t *p_thread = _get_thread_from_dev(p_dev);
    if (p_thread == NULL) {
        return;
    }

    struct sensor_value touch;
    sensor_channel_get(p_dev, SENSOR_CHAN_PAH8151_TOUCH, &touch);
    p_thread->is_touched = touch.val1 ? true : false;

    // Wake up thread
    k_sem_give(&p_thread->ppg_touch_sem);
}

static void _imu_acc_trig_handler(const struct device *dev, const struct sensor_trigger *trig) {
    sensor_sample_fetch_chan(dev, SENSOR_CHAN_ACCEL_XYZ);
    vitals_thread_t *p_thread = _get_thread_from_dev(dev);
    if (p_thread == NULL) {
        return;
    }

    struct sensor_value accel_samples[3];
    sensor_channel_get(dev, SENSOR_CHAN_ACCEL_XYZ, accel_samples);

    accel_interrupt_sample_t sample = {
        .timestamp = k_uptime_get(),
        .x = sensor_value_to_float(&accel_samples[0]),
        .y = sensor_value_to_float(&accel_samples[1]),
        .z = sensor_value_to_float(&accel_samples[2])};

    // If buffer is full, remove oldest sample
    if (ring_buf_space_get(&p_thread->accel_interrupt_samples_buf) < sizeof(sample)) {
        uint8_t dummy[sizeof(sample)];
        ring_buf_get(&p_thread->accel_interrupt_samples_buf, dummy, sizeof(sample));
    }

    ring_buf_put(&p_thread->accel_interrupt_samples_buf, (uint8_t *)&sample, sizeof(sample));
}

static void _imu_gyro_trig_handler(const struct device *dev, const struct sensor_trigger *trig) {
    sensor_sample_fetch_chan(dev, SENSOR_CHAN_GYRO_XYZ);
    vitals_thread_t *p_thread = _get_thread_from_dev(dev);
    if (p_thread == NULL) {
        return;
    }
}

/*----------------------------------------------------------------------------------------
 *                                                                                   Thread
 *--------------------------------------------------------------------------------------*/
static void _vitals_thread_entry(void *p_arg0, void *p_arg1, void *p_arg2) {
    LOG_INF("Vitals thread started");

    vitals_thread_t *p_thread = (vitals_thread_t *)p_arg0;

    // Initialize thread events
    k_poll_event_init(&p_thread->events[VITALS_THREAD_EVENT_PPG_DATA_READY],
                      K_POLL_TYPE_SEM_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &p_thread->ppg_data_ready_sem);

    k_poll_event_init(&p_thread->events[VITALS_THREAD_EVENT_PPG_TOUCH],
                      K_POLL_TYPE_SEM_AVAILABLE,
                      K_POLL_MODE_NOTIFY_ONLY,
                      &p_thread->ppg_touch_sem);

    while (true) {
        // Wait for any of the recv buffers to unblock
        int rc = k_poll(p_thread->events, ARRAY_SIZE(p_thread->events), K_FOREVER);
        if (rc != 0) {
            LOG_ERR("%s", "Unknown timeout in vitals thread");
        } else {
            if (p_thread->events[VITALS_THREAD_EVENT_PPG_DATA_READY].state == K_POLL_STATE_SEM_AVAILABLE) {
                k_sem_take(&p_thread->ppg_data_ready_sem, K_NO_WAIT);

                // Interpolate the PPG samples with the accelerometer samples (25Hz)
                _interpolate_sensor_samples(p_thread);

                // Print all the latest combined samples
                _print_sensor_samples(p_thread);

                // Update the PSP algorithm input metrics
                _psp_update_input_metrics(p_thread);

                // Process the PPG data with PSP algorithm
                if (!_psp_process(p_thread)) {
                    LOG_ERR("Failed to process PPG data with PSP algorithm");
                }
            }
            if (p_thread->events[VITALS_THREAD_EVENT_PPG_TOUCH].state == K_POLL_STATE_SEM_AVAILABLE) {
                k_sem_take(&p_thread->ppg_touch_sem, K_NO_WAIT);
                LOG_INF("PPG touch state changed: %s", p_thread->is_touched ? "Touched" : "Released");
            }
        }

        // Reset events so that they trigger again
        for (size_t i = 0; i < ARRAY_SIZE(p_thread->events); i++) {
            p_thread->events[i].state = K_POLL_STATE_NOT_READY;
        }
    }
}