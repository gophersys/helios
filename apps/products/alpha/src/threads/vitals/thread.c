#include "thread.h"

// Private thread includes
#include "types.h"
#include "utils/api.h"

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
#include <corekinect/sensor/paf9615.h>
#include <corekinect/sensor/pah8151.h>

// App includes
#include "../bluetooth/thread.h"
#include "../bluetooth/types.h"

LOG_MODULE_REGISTER(vitals_t, LOG_LEVEL_INF);

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
            s_vitals_threads[i]->config->p_imu_dev == p_dev ||
            s_vitals_threads[i]->config->p_temp_dev == p_dev) {
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
static void _temp_data_ready_handler(const struct device *p_dev, const struct sensor_trigger *p_trig);

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

    if (!device_is_ready(p_thread->config->p_temp_dev)) {
        LOG_ERR("Temperature device not ready");
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
                                    CONFIG_VITALS_THREAD_PRIORITY,
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

    // Register temperature sensor data handler
    struct sensor_trigger temp_trig = {
        .type = SENSOR_TRIG_DATA_READY,
        .chan = SENSOR_CHAN_OBJECT_TEMP,
    };
    if (sensor_trigger_set(p_thread->config->p_temp_dev, &temp_trig, _temp_data_ready_handler) != 0) {
        LOG_ERR("Failed to set temperature sensor trigger");
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

/**
 * @brief PPG data ready handler
 *
 * This function is called when the PPG sensor has new data ready. This happens every second.
 * It will collect all the samples from the past second and prepare them for the PSP algorithm.
 *
 * @param p_dev
 * @param p_trig
 */
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
    if (p_thread == NULL || !p_thread->is_touched) {
        return;
    }

    struct sensor_value accel_samples[3];
    sensor_channel_get(dev, SENSOR_CHAN_ACCEL_XYZ, accel_samples);

    int64_t current_time = k_uptime_get();

    accel_interrupt_sample_t sample = {
        .timestamp = current_time,
        .x = sensor_value_to_float(&accel_samples[0]),
        .y = sensor_value_to_float(&accel_samples[1]),
        .z = sensor_value_to_float(&accel_samples[2])};

    k_spinlock_key_t key = k_spin_lock(&p_thread->accel_buf_lock);

    // Only add if we have space and buffer isn't being processed
    if (ring_buf_space_get(&p_thread->accel_interrupt_samples_buf) >= sizeof(sample)) {
        ring_buf_put(&p_thread->accel_interrupt_samples_buf, (uint8_t *)&sample, sizeof(sample));
    } else {
        LOG_WRN("Accelerometer buffer is full, dropping sample");
    }

    k_spin_unlock(&p_thread->accel_buf_lock, key);
}

static void _imu_gyro_trig_handler(const struct device *dev, const struct sensor_trigger *trig) {
    sensor_sample_fetch_chan(dev, SENSOR_CHAN_GYRO_XYZ);
    vitals_thread_t *p_thread = _get_thread_from_dev(dev);
    if (p_thread == NULL) {
        return;
    }
}

static void _temp_data_ready_handler(const struct device *p_dev, const struct sensor_trigger *p_trig) {
    sensor_sample_fetch_chan(p_dev, SENSOR_CHAN_OBJECT_TEMP);
    vitals_thread_t *p_thread = _get_thread_from_dev(p_dev);
    if (p_thread == NULL) {
        return;
    }

    struct sensor_value temp;
    sensor_channel_get(p_dev, SENSOR_CHAN_OBJECT_TEMP, &temp);
    p_thread->vitals_output_metrics.temperature_f = sensor_value_to_float(&temp);
}

/*----------------------------------------------------------------------------------------
 *                                                                                   Thread
 *--------------------------------------------------------------------------------------*/
static void _vitals_thread_entry(void *p_arg0, void *p_arg1, void *p_arg2) {
    LOG_INF("Vitals thread started");

    vitals_thread_t *p_thread = (vitals_thread_t *)p_arg0;
    int64_t touch_start_time = 0;     // Track when touch started
    bool is_warmup_period = false;    // Track if we're in the 5-second warmup period
    bool is_first_processing = true;  // Track the first processing cycle

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
            if (p_thread->events[VITALS_THREAD_EVENT_PPG_TOUCH].state == K_POLL_STATE_SEM_AVAILABLE) {
                k_sem_take(&p_thread->ppg_touch_sem, K_NO_WAIT);
                LOG_INF("PPG touch state changed: %s", p_thread->is_touched ? "Touched" : "Released");

                if (p_thread->is_touched) {
                    // Start warmup period when touched
                    touch_start_time = k_uptime_get();
                    is_warmup_period = true;
                    is_first_processing = true;
                    LOG_INF("Starting %d-second warmup period", CONFIG_VITALS_WARMUP_PERIOD / 1000);

                    // Clear all buffers to start fresh
                    ring_buf_reset(&p_thread->accel_interrupt_samples_buf);
                    memset(p_thread->accel_interrupt_samples, 0, sizeof(p_thread->accel_interrupt_samples));
                    memset(p_thread->ppg_interrupt_samples, 0, sizeof(p_thread->ppg_interrupt_samples));

                    // Reset PSP algorithm state
                    p_thread->data_ready_for_psp = false;
                    p_thread->calibration_complete = false;
                } else {
                    // Reset warmup state when released
                    is_warmup_period = false;
                    touch_start_time = 0;
                    is_first_processing = true;

                    LOG_INF("Device removed - resetting calibration state");
                }
            }

            if (p_thread->events[VITALS_THREAD_EVENT_PPG_DATA_READY].state == K_POLL_STATE_SEM_AVAILABLE) {
                k_sem_take(&p_thread->ppg_data_ready_sem, K_NO_WAIT);

                // Check if we're in warmup period
                if (is_warmup_period) {
                    int64_t current_time = k_uptime_get();
                    if (current_time - touch_start_time < CONFIG_VITALS_WARMUP_PERIOD) {
                        LOG_DBG("Skipping samples during warmup period (%lld ms elapsed)",
                                current_time - touch_start_time);
                        continue;  // Skip processing during warmup
                    } else {
                        is_warmup_period = false;
                        LOG_INF("Warmup period complete, starting normal processing");
                    }
                }

                // Add retry logic with timeout
                uint32_t start_time = k_uptime_get_32();
                bool samples_acquired = false;

                while ((k_uptime_get_32() - start_time) < 100) {  // 100ms timeout
                    // Take spinlock before accessing ring buffer
                    k_spinlock_key_t key = k_spin_lock(&p_thread->accel_buf_lock);

                    uint32_t accel_samples = ring_buf_size_get(&p_thread->accel_interrupt_samples_buf) /
                                             sizeof(accel_interrupt_sample_t);

                    if (accel_samples >= CONFIG_ACCEL_RING_BUF_COUNT) {
                        // Create a temporary buffer to ensure proper memory alignment
                        accel_interrupt_sample_t temp_samples[CONFIG_ACCEL_RING_BUF_COUNT];
                        memset(temp_samples, 0, sizeof(temp_samples));

                        uint32_t bytes_read = ring_buf_get(&p_thread->accel_interrupt_samples_buf,
                                                           (uint8_t *)temp_samples,
                                                           sizeof(accel_interrupt_sample_t) * CONFIG_ACCEL_RING_BUF_COUNT);

                        if (bytes_read == sizeof(accel_interrupt_sample_t) * CONFIG_ACCEL_RING_BUF_COUNT) {
                            // Copy verified samples to thread structure
                            memcpy(p_thread->accel_interrupt_samples, temp_samples, sizeof(accel_interrupt_sample_t) * CONFIG_ACCEL_RING_BUF_COUNT);

                            // Clear the buffer
                            ring_buf_reset(&p_thread->accel_interrupt_samples_buf);
                            k_spin_unlock(&p_thread->accel_buf_lock, key);

                            // Process the data
                            _prepare_sensor_samples(p_thread);

                            // Send raw sensor data to BLE (useful for debugging/analysis)
                            _send_ble_sensor_samples(p_thread);

                            // Only process with PSP if calibration is complete or on first sample set
                            if (p_thread->data_ready_for_psp) {
                                // Call the PSP algorithm
                                if (!_psp_update_input_metrics(p_thread)) {
                                    LOG_ERR("Failed to update input metrics");
                                }

                                if (!_psp_process(p_thread)) {
                                    LOG_ERR("Failed to process PPG data with PSP algorithm");
                                }

                                if (!_psp_get_output_metrics(p_thread)) {
                                    LOG_ERR("Failed to get output metrics");
                                }
                            } else if (is_first_processing) {
                                // Just log first processing cycle
                                LOG_INF("First PPG data received, starting calibration and stabilization");
                                is_first_processing = false;
                            } else {
                                LOG_DBG("Waiting for signal stabilization and calibration to complete");
                            }

                            samples_acquired = true;
                            break;  // Exit the retry loop
                        } else {
                            LOG_ERR("Failed to read correct number of samples: got %d bytes, expected %d",
                                    bytes_read, sizeof(accel_interrupt_sample_t) * CONFIG_ACCEL_RING_BUF_COUNT);
                            ring_buf_reset(&p_thread->accel_interrupt_samples_buf);
                            k_spin_unlock(&p_thread->accel_buf_lock, key);
                        }
                    } else {
                        k_spin_unlock(&p_thread->accel_buf_lock, key);
                        LOG_DBG("Waiting for samples: %d/%d", accel_samples, CONFIG_ACCEL_RING_BUF_COUNT);
                        k_sleep(K_MSEC(10));  // Wait 10ms before next attempt
                        continue;
                    }
                }

                if (!samples_acquired) {
                    LOG_WRN("Timeout waiting for accelerometer samples after 100ms: %d/%d",
                            ring_buf_size_get(&p_thread->accel_interrupt_samples_buf) / sizeof(accel_interrupt_sample_t),
                            CONFIG_ACCEL_RING_BUF_COUNT);
                }
            }
        }

        // Reset events so that they trigger again
        for (size_t i = 0; i < ARRAY_SIZE(p_thread->events); i++) {
            p_thread->events[i].state = K_POLL_STATE_NOT_READY;
        }
    }
}
