#include "api.h"

// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// App includes
#include "../../bluetooth/thread.h"
#include "../../bluetooth/types.h"

LOG_MODULE_DECLARE(vitals_t, LOG_LEVEL_INF);

/*----------------------------------------------------------------------------------------
 *                                                                           PSP Algorithm
 *--------------------------------------------------------------------------------------*/

/**
 * @brief Print the latest sensor samples
 *
 * @param p_thread Vitals thread instance
 */
void _send_ble_sensor_samples(vitals_thread_t *p_thread) {
    for (uint32_t i = 0; i < CONFIG_PPG_SAMPLES_PER_BATCH; i++) {
        // Add sensor samples to BLE thread
        sensor_data_t sensor_data = {
            .accelerometer = {
                .x = p_thread->raw_samples_25Hz[i].accel_x,
                .y = p_thread->raw_samples_25Hz[i].accel_y,
                .z = p_thread->raw_samples_25Hz[i].accel_z,
            },
            .ppg_intensity = {
                .red_intensity = p_thread->raw_samples_25Hz[i].ppg.red_intensity,
                .green_intensity = p_thread->raw_samples_25Hz[i].ppg.green_intensity,
                .ir_intensity = p_thread->raw_samples_25Hz[i].ppg.ir_intensity,
            },
        };

        if (!bluetooth_send_sensor_data(BLUETOOTH_THREAD_DATA_TYPE_SENSOR_DATA_25HZ,
                                        (uint8_t *)&sensor_data,
                                        sizeof(sensor_data))) {
            LOG_ERR("Failed to send sensor data to bluetooth thread");
        }
    }

    for (uint32_t i = 0; i < CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND; i++) {
        // LOG_INF(
        //     "Sample %2d [timestamp: %llu] - Red: %d (expo us: %f, dac: %u), "
        //     "Green: %d (expo us: %f, dac: %u), IR: %d (expo us: %f, dac: %u)",
        //     i,
        //     (uint64_t)p_thread->raw_samples_32Hz[i].ppg.timestamp,
        //     p_thread->raw_samples_32Hz[i].ppg.red_intensity, (double)p_thread->raw_samples_32Hz[i].ppg.red_expo_us, p_thread->raw_samples_32Hz[i].ppg.red_dac,
        //     p_thread->raw_samples_32Hz[i].ppg.green_intensity, (double)p_thread->raw_samples_32Hz[i].ppg.green_expo_us, p_thread->raw_samples_32Hz[i].ppg.green_dac,
        //     p_thread->raw_samples_32Hz[i].ppg.ir_intensity, (double)p_thread->raw_samples_32Hz[i].ppg.ir_expo_us, p_thread->raw_samples_32Hz[i].ppg.ir_dac);

        // Add sensor samples to BLE thread
        sensor_data_t sensor_data = {
            .accelerometer = {
                .x = p_thread->raw_samples_32Hz[i].accel_x,
                .y = p_thread->raw_samples_32Hz[i].accel_y,
                .z = p_thread->raw_samples_32Hz[i].accel_z,
            },
            .ppg_intensity = {
                .red_intensity = p_thread->raw_samples_32Hz[i].ppg.red_intensity,
                .green_intensity = p_thread->raw_samples_32Hz[i].ppg.green_intensity,
                .ir_intensity = p_thread->raw_samples_32Hz[i].ppg.ir_intensity,
            },
        };

        if (!bluetooth_send_sensor_data(BLUETOOTH_THREAD_DATA_TYPE_SENSOR_DATA_32HZ, (uint8_t *)&sensor_data, sizeof(sensor_data))) {
            LOG_ERR("Failed to send sensor data to bluetooth thread");
        }

        // Log PSP input metrics directly from the structure
        // LOG_INF("PSP[%2d] PPG(R:%u,IR:%u,G:%u,A:%u) ACC(X:%d,Y:%d,Z:%d)",
        //         i,
        //         p_thread->psp_input_samples_32Hz[i].ppg_red,
        //         p_thread->psp_input_samples_32Hz[i].ppg_ir,
        //         p_thread->psp_input_samples_32Hz[i].ppg_green,
        //         p_thread->psp_input_samples_32Hz[i].ppg_ambient,
        //         p_thread->psp_input_samples_32Hz[i].accel_x,
        //         p_thread->psp_input_samples_32Hz[i].accel_y,
        //         p_thread->psp_input_samples_32Hz[i].accel_z);

        // // Add PSP data to BLE thread
        // psp_input_data_t psp_data = {
        //     .accelerometer = {
        //         .x = p_thread->psp_input_samples_32Hz[i].accel_x,
        //         .y = p_thread->psp_input_samples_32Hz[i].accel_y,
        //         .z = p_thread->psp_input_samples_32Hz[i].accel_z,
        //     },
        //     .ppg_intensity = {
        //         .red_intensity = p_thread->psp_input_samples_32Hz[i].ppg_red,
        //         .green_intensity = p_thread->psp_input_samples_32Hz[i].ppg_green,
        //         .ir_intensity = p_thread->psp_input_samples_32Hz[i].ppg_ir,
        //     },
        // };

        // if (!bluetooth_send_sensor_data(BLUETOOTH_THREAD_DATA_TYPE_PSP_INPUT_DATA_32HZ,
        //                                 (uint8_t *)&psp_data,
        //                                 sizeof(psp_data))) {
        //     LOG_ERR("Failed to send PSP input data to bluetooth thread");
        // }
    }
}
