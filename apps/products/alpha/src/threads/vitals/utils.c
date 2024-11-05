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

LOG_MODULE_DECLARE(vitals, LOG_LEVEL_DBG);

/*----------------------------------------------------------------------------------------
 *                                                                         General Helpers
 *--------------------------------------------------------------------------------------*/
bool _check_config(const vitals_thread_config_t *p_config) {
    if (p_config == NULL) {
        LOG_ERR("Invalid configuration");
        return false;
    }

    if (p_config->p_ppg_dev == NULL) {
        LOG_ERR("Invalid PPG device");
        return false;
    }

    if (p_config->p_imu_dev == NULL) {
        LOG_ERR("Invalid IMU device");
        return false;
    }

    return true;
}

/*----------------------------------------------------------------------------------------
 *                                                                           PSP Algorithm
 *--------------------------------------------------------------------------------------*/
const char *_psp_error_string(PSP_ERROR err) {
    switch (err) {
        case PSP_ERROR_NONE:
            return "No error";
        case PSP_ERROR_NOT_ENOUGH_MEMORY:
            return "Not enough memory provided";
        case PSP_ERROR_INITIALISATION_FAILED:
            return "Initialisation failed";
        case PSP_ERROR_SIZE_CONFLICT:
            return "Metric data conflicts with size definition";
        case PSP_ERROR_METRIC_NOT_SUPPORTED:
            return "Undefined metric ID used";
        case PSP_ERROR_MODULE_NOT_INITIALISED:
            return "Module not initialised";
        case PSP_ERROR_MEMORY_CORRUPTED:
            return "Memory corrupted";
        case PSP_ERROR_INVALID_PARAMS:
            return "Invalid parameters provided";
        case PSP_ERROR_MULTIPLE_SET:
            return "Attempting to set metric multiple times";
        case PSP_ERROR_DATA_INCOMPLETE:
            return "Metric data is incomplete";
        default:
            return "Unknown error code";
    }
}

const char *_psp_metric_string(PSP_METRIC_ID metric) {
    switch (metric) {
        /* Input metrics */
        case PSP_METRIC_ID_AGE:
            return "Age";
        case PSP_METRIC_ID_PROFILE:
            return "Profile";
        case PSP_METRIC_ID_HEIGHT:
            return "Height";
        case PSP_METRIC_ID_WEIGHT:
            return "Weight";
        case PSP_METRIC_ID_SLEEPPREFERENCE:
            return "Sleep Preference";
        case PSP_METRIC_ID_TIME:
            return "Time";
        case PSP_METRIC_ID_ACCELERATION:
            return "Acceleration";
        case PSP_METRIC_ID_SKINCONDUCTANCE:
            return "Skin Conductance";
        case PSP_METRIC_ID_GYRO:
            return "Gyroscope";
        case PSP_METRIC_ID_PRESSURE:
            return "Pressure";
        case PSP_METRIC_ID_PPG_INFRARED:
            return "PPG Infrared";
        case PSP_METRIC_ID_PPG_RED:
            return "PPG Red";
        case PSP_METRIC_ID_PPG_MOTION:
            return "PPG Motion";
        case PSP_METRIC_ID_PPG_GREEN:
            return "PPG Green";
        case PSP_METRIC_ID_PPG_AMBIENT:
            return "PPG Ambient";

        /* Extracted metrics */
        case PSP_METRIC_ID_HEARTRATE:
            return "Heart Rate";
        case PSP_METRIC_ID_RESTINGHEARTRATE:
            return "Resting Heart Rate";
        case PSP_METRIC_ID_SKINPROXIMITY:
            return "Skin Proximity";
        case PSP_METRIC_ID_ENERGYEXPENDITURE:
            return "Energy Expenditure";
        case PSP_METRIC_ID_SPEED:
            return "Speed";
        case PSP_METRIC_ID_MOTIONCADENCE:
            return "Motion Cadence";
        case PSP_METRIC_ID_ACTIVITYTYPE:
            return "Activity Type";
        case PSP_METRIC_ID_HEARTBEATS:
            return "Heart Beats";
        case PSP_METRIC_ID_VO2MAX:
            return "VO2 Max";
        case PSP_METRIC_ID_FITNESSINDEX:
            return "Fitness Index";
        case PSP_METRIC_ID_RESPIRATIONRATE:
            return "Respiration Rate";
        case PSP_METRIC_ID_LOWPOWERHEARTRATE:
            return "Low Power Heart Rate";
        case PSP_METRIC_ID_ACTIVITYCOUNT:
            return "Activity Count";
        case PSP_METRIC_ID_PRIVATEDATA:
            return "Private Data";
        case PSP_METRIC_ID_SLEEPSTAGES:
            return "Sleep Stages";
        case PSP_METRIC_ID_COMPRESSED_ACCELERATION:
            return "Compressed Acceleration";
        case PSP_METRIC_ID_COMPRESSED_PPG:
            return "Compressed PPG";
        case PSP_METRIC_ID_HEARTRHYTHMTYPE:
            return "Heart Rhythm Type";
        case PSP_METRIC_ID_LOWPOWERENERGYEXPENDITURE:
            return "Low Power Energy Expenditure";
        case PSP_METRIC_ID_STRESSLEVELSKINCONDUCTANCE:
            return "Stress Level (Skin Conductance)";
        case PSP_METRIC_ID_COGNITIVEZONE:
            return "Cognitive Zone";
        case PSP_METRIC_ID_STRESSLEVELHEARTRATE:
            return "Stress Level (Heart Rate)";
        case PSP_METRIC_ID_SPO2:
            return "SpO2";
        case PSP_METRIC_ID_FALL:
            return "Fall";
        default:
            return "Unknown Metric";
    }
}

bool _psp_init(vitals_thread_t *p_thread) {
    // The library will tell us how much memory it needs to use
    PSP_ERROR err = PSP_GetDefaultParams(&p_thread->psp_inst_params);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Could not get the default parameters for Phillips library: %s", _psp_error_string(err));
        return false;
    }

    // Allocate memory to call the library
    p_thread->psp_inst_params.pMem = k_heap_alloc(&p_thread->psp_heap, p_thread->psp_inst_params.memorySize, K_NO_WAIT);
    if (p_thread->psp_inst_params.pMem == NULL) {
        LOG_ERR("Could not allocated %d bytes of memory for instance needed by Phillips library", p_thread->psp_inst_params.memorySize);
        return false;
    }

    p_thread->psp_inst_params.pSourceID = k_heap_alloc(&p_thread->psp_heap, p_thread->psp_inst_params.sourceIDSize, K_NO_WAIT);
    if (p_thread->psp_inst_params.pSourceID == NULL) {
        LOG_ERR("Could not allocated %d bytes of memory for source ID needed by Phillips library", p_thread->psp_inst_params.sourceIDSize);
        return false;
    }

    // Create a new library instance
    err = PSP_Initialise(&p_thread->psp_inst_params, &p_thread->psp_inst);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Could not initialize Phillips library: %s", _psp_error_string(err));
        return false;
    }

    // Enable output metrics
    PSP_METRIC_ID psp_enabled_metrics[] = {
        PSP_METRIC_ID_HEARTRATE,
        PSP_METRIC_ID_SPO2,
    };

    err = PSP_EnableMetrics(p_thread->psp_inst, sizeof(psp_enabled_metrics), psp_enabled_metrics);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Could not enable metrics for Phillips library: %s", _psp_error_string(err));
        return false;
    }

    for (size_t i = 0; i < sizeof(psp_enabled_metrics); i++) {
        LOG_INF("Enabled metric %d: %s", i, _psp_metric_string(psp_enabled_metrics[i]));
    }

    // Read required input metrics
    p_thread->psp_required_metrics_count = CONFIG_PSP_MAX_METRICS;
    err = PSP_ListRequiredMetrics(p_thread->psp_inst, p_thread->psp_required_metrics, &p_thread->psp_required_metrics_count);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Could not list required metrics for Phillips library: %s", _psp_error_string(err));
        return false;
    }

    for (size_t i = 0; i < p_thread->psp_required_metrics_count; i++) {
        LOG_INF("Required metric %d: %s", i, _psp_metric_string(p_thread->psp_required_metrics[i]));
    }

    return true;
}

typedef enum {
    PSP_UPDATE_TYPE_PPG_IR,
    PSP_UPDATE_TYPE_PPG_GREEN,
    PSP_UPDATE_TYPE_PPG_RED,
} psp_ppg_type_t;

enum {
    PREAMBLE_SIZE = 5,                                                              // Preamble
    BPI_SIZE = 1,                                                                   // Body Position Index
    PF_SIZE = 1,                                                                    // PPG Sample format
    SI_SIZE = 1,                                                                    // Stream Identifier
    PPG_OFFSET_SIZE = 1,                                                            // PPG Offset
    PPG_EXP_SIZE = 1,                                                               // PPG Exponent
    LED_POWER_SIZE = 4,                                                             // LED Power
    ADC_GAIN_SIZE = 4,                                                              // ADC Gain
    PPG_SAMPLES_SIZE = CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND * sizeof(uint16_t),  // PPG Samples
} psp_ppg_metric_sizes_t;

// Define offsets for clearer array indexing
enum {
    OFFSET_BPI = 5,
    OFFSET_PF = 6,
    OFFSET_SI = 7,
    OFFSET_PPG_OFFSET = 8,
    OFFSET_PPG_EXP = 9,
    OFFSET_LED_POWER = 10,
    OFFSET_ADC_GAIN = 14,
    OFFSET_PPG_SAMPLES = OFFSET_ADC_GAIN + ADC_GAIN_SIZE
} psp_ppg_metric_offsets_t;

enum {
    BPI_INDEX_UNSPECIFIED = 0,
    BPI_INDEX_LEFT_WRIST = 1,
    BPI_INDEX_RIGHT_WRIST = 2,
    BPI_INDEX_UNSPECIFIED_WRIST = 3,
} psp_ppg_metric_bpi_index_t;

bool _psp_update_ppg_data(vitals_thread_t *p_thread, psp_ppg_type_t update_type) {
    const uint16_t ppg_metric_size = PREAMBLE_SIZE + BPI_SIZE + PF_SIZE + SI_SIZE + PPG_OFFSET_SIZE + PPG_EXP_SIZE + LED_POWER_SIZE + ADC_GAIN_SIZE + PPG_SAMPLES_SIZE;
    uint8_t data[ppg_metric_size];
    static uint8_t sequence_number = 0;

    // Preamble (5 bytes: ID, NL, NH, IX, Q)
    data[0] = PSP_METRIC_ID_PPG_INFRARED;    // ID
    data[1] = (ppg_metric_size - 3) & 0xFF;  // NL (low byte of remaining size)
    data[2] = (ppg_metric_size - 3) >> 8;    // NH (high byte of remaining size)
    data[3] = sequence_number++;             // IX (increment index each update)
    data[4] = 4;                             // Q (quality, set to maximum reliability)

    // Body position index
    data[OFFSET_BPI] = BPI_INDEX_UNSPECIFIED;

    // PPG sample format
    data[OFFSET_PF] = 0x60;  // Only 0x60 is supported

    // Stream identifier
    data[OFFSET_SI] = 0x00;  // No index for LED or PD are used

    // PPG offset
    data[OFFSET_PPG_OFFSET] = 0x00;  // No offset is used or supported

    // PPG exponent
    data[OFFSET_PPG_EXP] = 0x00;  // No exponent is used or supported

    // LED power
    for (size_t i = 0; i < LED_POWER_SIZE; i++) {
        data[OFFSET_LED_POWER + i] = 50;
    }

    // ADC gain
    for (size_t i = 0; i < ADC_GAIN_SIZE; i++) {
        data[OFFSET_ADC_GAIN + i] = 1;
    }

    uint16_t ppg_ir_u16[CONFIG_PPG_SAMPLES_PER_BATCH];
    uint32_t ppg_ir_samples[CONFIG_PPG_SAMPLES_PER_BATCH];

    // Create array of samples
    for (size_t i = 0; i < CONFIG_PPG_SAMPLES_PER_BATCH; i++) {
        ppg_ir_samples[i] = p_thread->combined_samples[i].ppg.ir_intensity;
    }

    _scale_ppg_to_uint16(ppg_ir_samples, CONFIG_PPG_SAMPLES_PER_BATCH, ppg_ir_u16);

    // Upsample the PPG signals to the required rate of 32 Hz
    uint16_t ppg_ir_u16_upsampled[CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND];
    _upsample_uint16(ppg_ir_u16, CONFIG_PPG_SAMPLES_PER_BATCH,
                     ppg_ir_u16_upsampled, CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND);

    // PPG samples - handle as 16-bit values
    for (size_t i = 0; i < PPG_SAMPLES_SIZE / 2; i++) {                       // Divide by 2 if PPG_SAMPLES_SIZE is in bytes
        uint16_t ppg_sample = ppg_ir_u16_upsampled[i];                        // Replace with actual sample data
        data[OFFSET_PPG_SAMPLES + (i * 2)] = (uint8_t)(ppg_sample & 0xFF);    // LSB
        data[OFFSET_PPG_SAMPLES + (i * 2) + 1] = (uint8_t)(ppg_sample >> 8);  // MSB
    }

    LOG_HEXDUMP_INF(data, ppg_metric_size, "PPG metric");

    PSP_ERROR err = PSP_SetMetric(p_thread->psp_inst, PSP_METRIC_ID_PPG_INFRARED, data, ppg_metric_size);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Failed to set PPG metric: %s", _psp_error_string(err));
        return false;
    }

    LOG_WRN("Set PPG metric with sequence number %d", sequence_number);

    return true;
}

bool _psp_update_input_metrics(vitals_thread_t *p_thread) {
    /**
     * @brief Requirements for PPG signal:
     *
     * The AFE provides the PPG signals with ambient light cancelled and sends the raw data
     * to main MCU over I2C. However, the PPG signal may not match with the input requirements
     * for the PSP library and may be necessary to convert before feeding to library.
     *
     * The ambient channel is required and will improve the sensing of Skin Proximity. If it
     * is not available, set the value to 0, but this metric is still required to feed to the
     * PSP library.
     *
     * The PPG input requirements to the library are:
     *   - 32 Hz Sampling Rate
     *   - Dynamic range 0 .. (2^16 - 1)
     *   - 16-bits unsigned resolution
     *   - >80dB SNR for green channel (heart rate)
     *   - >85dB SNR for IR and infrared channels (SpO2)
     *   - PPG signal with ambient light cancelled
     *
     */

    if (!_psp_update_ppg_data(p_thread, PSP_UPDATE_TYPE_PPG_IR)) {
        LOG_ERR("Failed to update PPG Green metric");
        return false;
    }

    // // Convert the PPG signals to the required resolution of 16-bits unsigned
    // uint16_t ppg_green_u16[p_thread->ppg_sample_count];
    // uint16_t ppg_red_u16[p_thread->ppg_sample_count];
    // uint16_t ppg_ir_u16[p_thread->ppg_sample_count];
    // _scale_ppg_to_uint16(p_thread->ppg_samples->green, p_thread->ppg_sample_count, ppg_green_u16);
    // _scale_ppg_to_uint16(p_thread->ppg_samples->red_intensity, p_thread->ppg_sample_count, ppg_red_u16);
    // _scale_ppg_to_uint16(p_thread->ppg_samples->ir, p_thread->ppg_sample_count, ppg_ir_u16);

    // // Upsample the PPG signals to the required rate of 32 Hz
    // _vitals_thread_upsample_uint16(ppg_green_u16, p_thread->ppg_sample_count, p_thread->psp_input_metrics->ppg_green, PSP_ALGORITHM_SAMPLES_PER_SECOND);
    // _vitals_thread_upsample_uint16(ppg_red_u16, p_thread->ppg_sample_count, p_thread->psp_input_metrics->ppg_red, PSP_ALGORITHM_SAMPLES_PER_SECOND);
    // _vitals_thread_upsample_uint16(ppg_ir_u16, p_thread->ppg_sample_count, p_thread->psp_input_metrics->ppg_ir, PSP_ALGORITHM_SAMPLES_PER_SECOND);

    // // Prepare PSP metric data buffer
    // const uint16_t metricSize = (PSP_NUMBER_OF_PPG_SAMPLES * 2) + 15;
    // uint8_t data[metricSize];
    // uint16_t index = 0;

    // // Set metric header information
    // data[index++] = p_thread->sequence_number++;  // Increment sequence number
    // data[index++] = 4;                            // Quality fixed to 4
    // data[index++] = p_thread->body_position;      // Body position
    // data[index++] = 0x60;                         // PF fixed for 32 samples
    // data[index++] = 0x03;                         // SI stream identifier
    // data[index++] = 0x00;                         // PPG offset
    // data[index++] = 0x00;                         // PPG exponent

    // // LED power and ADC gain settings
    // for (int i = 0; i < 4; i++) {
    //     data[index++] = p_thread->led_power[i];  // LED power for each quarter second
    // }
    // for (int i = 0; i < 4; i++) {
    //     data[index++] = p_thread->adc_gain[i];  // ADC gain for each quarter second
    // }

    // // Copy PPG samples in little-endian format
    // for (int i = 0; i < PSP_NUMBER_OF_PPG_SAMPLES; i++) {
    //     uint16_t ppg_sample = p_thread->psp_input_metrics->ppg_green[i];
    //     data[index++] = (uint8_t)(ppg_sample & 0xFF);         // LSB
    //     data[index++] = (uint8_t)((ppg_sample >> 8) & 0xFF);  // MSB
    // }

    // // Set the metric in PSP library
    // psp_status_t status = PSP_SetMetric(p_thread->psp_instance,
    //                                     PSP_METRIC_ID_PPG_GREEN,
    //                                     data,
    //                                     index);

    // // Repeat similar process for RED and IR channels if needed
    // // ...

    // return (status == PSP_STATUS_OK);
}

bool _psp_process(vitals_thread_t *p_thread) {
    PSP_ERROR err = PSP_Process(p_thread->psp_inst);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Failed to process PSP algorithm: %s", _psp_error_string(err));
        return false;
    }

    /**
     * @brief Requirements for PPG signal:
     *
     * The AFE provides the PPG signals with ambient light cancelled and sends the raw data
     * to main MCU over I2C. However, the PPG signal may not match with the input requirements
     * for the PSP library and may be necessary to convert before feeding to library.
     *
     * The ambient channel is required and will improve the sensing of Skin Proximity. If it
     * is not available, set the value to 0, but this metric is still required to feed to the
     * PSP library.
     *
     * The PPG input requirements to the library are:
     *   - 32 Hz Sampling Rate
     *   - Dynamic range 0 .. (2^16 - 1)
     *   - 16-bits unsigned resolution
     *   - >80dB SNR for green channel (heart rate)
     *   - >85dB SNR for IR and infrared channels (SpO2)
     *   - PPG signal with ambient light cancelled
     *
     * @brief Requirements for Accelerometer signal:
     *
     * The accelerometer input requirements to the library are:
     *   - 32 Hz Sampling Rate
     *   - +/- 8g Dynamic Range
     *   - 13-bits signed, 1/512 g/unit resolution (-4096 to +4095)
     *   - Sensor noise <6mg RMS
     *   - Allowed 0g Offset <150mg on any axis
     *
     * @brief Requirements for Gyroscope signal:
     *   - 50 Hz Sampling Rate
     *   - +/- 2000 deg/s Dynamic Range
     *   - 16-bits signed, 1/8192 deg/s/unit resolution (-32768 to +32767)
     *   - Sensor noise <0.1125 deg/s RMS
     *   - Allowed 0 deg/s Offset <0.75 deg/s on any axis
     *
     * @brief Requirements for Barometric Pressure signal:
     *   - 4 Hz Sampling Rate
     *   - 16-bit unsigned resolution, 1 Pa/unit
     *   - 70000 .. 135535 Pa Dynamic Range
     *   - Sensor noise <1.5 Pa RMS
     *
     * @brief PSP Library
     *
     * The library is called to process after feeding one set of all sensor data. Then,
     * the library provides output of the enabled metrics for specified time period.
     *
     * The PSP library requires all required sensor signals to be synchronized. For instance,
     * for metrics in Biosensing by PPG, PPG and ACC signals are synchronized and simultaneously
     * fed to the library at a constant number of samples per second.
     *
     * The library processes one set input with 32 PPG samples, and 32 accelerometer samples every
     * second.
     *
     *
     */
    return true;
}

/*----------------------------------------------------------------------------------------
 *                                                                          Sample Helpers
 *--------------------------------------------------------------------------------------*/
// For unsigned 16-bit values (PPG data)
void _upsample_uint16(const uint16_t *input_samples,
                      size_t input_count,
                      uint16_t *output_samples,
                      size_t output_count) {
    const float input_dt = 1.0f / 25.0f;
    const float output_dt = 1.0f / 32.0f;

    LOG_INF("Upsampling %d uint16 samples to %d samples", input_count, output_count);

    for (size_t i = 0; i < output_count; i++) {
        float target_time = i * output_dt;
        size_t lower_idx = (size_t)(target_time / input_dt);
        size_t upper_idx = lower_idx + 1;

        if (lower_idx >= input_count - 1) {
            output_samples[i] = input_samples[input_count - 1];
            LOG_DBG("Using last sample for output[%d]: %u", i, output_samples[i]);
            continue;
        }

        float lower_time = lower_idx * input_dt;
        float t = (target_time - lower_time) / input_dt;

        // Linear interpolation for unsigned values
        output_samples[i] = (uint16_t)((1.0f - t) * input_samples[lower_idx] +
                                       t * input_samples[upper_idx]);

        LOG_DBG("Output[%d] = %u (interpolated between %u and %u, t=%.3f)",
                i, output_samples[i], input_samples[lower_idx],
                input_samples[upper_idx], (double)t);
    }
}

// For signed 16-bit values (Accelerometer data)
void _upsample_int16(const int16_t *input_samples,
                     size_t input_count,
                     int16_t *output_samples,
                     size_t output_count) {
    const float input_dt = 1.0f / 25.0f;
    const float output_dt = 1.0f / 32.0f;

    LOG_INF("Upsampling %d int16 samples to %d samples", input_count, output_count);

    for (size_t i = 0; i < output_count; i++) {
        float target_time = i * output_dt;
        size_t lower_idx = (size_t)(target_time / input_dt);
        size_t upper_idx = lower_idx + 1;

        if (lower_idx >= input_count - 1) {
            output_samples[i] = input_samples[input_count - 1];
            LOG_DBG("Using last sample for output[%d]: %d", i, output_samples[i]);
            continue;
        }

        float lower_time = lower_idx * input_dt;
        float t = (target_time - lower_time) / input_dt;

        // Linear interpolation for signed values
        output_samples[i] = (int16_t)((1.0f - t) * input_samples[lower_idx] +
                                      t * input_samples[upper_idx]);

        LOG_DBG("Output[%d] = %d (interpolated between %d and %d, t=%.3f)",
                i, output_samples[i], input_samples[lower_idx],
                input_samples[upper_idx], (double)t);
    }
}

void _scale_ppg_to_uint16(const uint32_t *input_samples,
                          size_t input_count,
                          uint16_t *output_samples) {
    // Find min/max to determine scaling
    uint32_t min_val = UINT32_MAX;
    uint32_t max_val = 0;
    for (size_t i = 0; i < input_count; i++) {
        min_val = MIN(min_val, input_samples[i]);
        max_val = MAX(max_val, input_samples[i]);
    }

    // Calculate scaling factor to fit into uint16 range
    float scale = (float)UINT16_MAX / (float)(max_val - min_val);

    // Scale and offset values to fit uint16 range
    for (size_t i = 0; i < input_count; i++) {
        float scaled = (input_samples[i] - min_val) * scale;
        output_samples[i] = (uint16_t)scaled;
    }
}

/**
 * @brief Interpolate the accelerometer samples to match the PPG samples
 *
 * @param p_thread Vitals thread instance
 */
void _interpolate_sensor_samples(vitals_thread_t *p_thread) {
    accel_interrupt_sample_t accel_samples[CONFIG_ACCEL_RING_BUF_COUNT];
    uint8_t *data;
    size_t accel_count = ring_buf_get_claim(&p_thread->accel_interrupt_samples_buf, &data, sizeof(accel_samples));

    memcpy(accel_samples, data, accel_count);
    ring_buf_get_finish(&p_thread->accel_interrupt_samples_buf, accel_count);
    accel_count /= sizeof(sensors_sample_t);

    // For each PPG sample, find/interpolate matching accelerometer value
    for (int i = 0; i < CONFIG_PPG_SAMPLES_PER_BATCH; i++) {
        uint64_t ppg_timestamp = p_thread->ppg_interrupt_samples[i].timestamp;

        // Copy PPG data directly
        memcpy(&p_thread->combined_samples[i].ppg, &p_thread->ppg_interrupt_samples[i], sizeof(struct pah8151_ppg_sample));

        // Find accelerometer samples that bracket this timestamp
        int lower_idx = -1;
        for (int j = 0; j < accel_count - 1; j++) {
            if (accel_samples[j].timestamp <= ppg_timestamp &&
                accel_samples[j + 1].timestamp >= ppg_timestamp) {
                lower_idx = j;
                break;
            }
        }

        if (lower_idx >= 0) {
            // Linear interpolation
            float t = (float)(ppg_timestamp - accel_samples[lower_idx].timestamp) /
                      (float)(accel_samples[lower_idx + 1].timestamp - accel_samples[lower_idx].timestamp);

            p_thread->combined_samples[i].accel_x =
                accel_samples[lower_idx].x + t * (accel_samples[lower_idx + 1].x - accel_samples[lower_idx].x);
            p_thread->combined_samples[i].accel_y =
                accel_samples[lower_idx].y + t * (accel_samples[lower_idx + 1].y - accel_samples[lower_idx].y);
            p_thread->combined_samples[i].accel_z =
                accel_samples[lower_idx].z + t * (accel_samples[lower_idx + 1].z - accel_samples[lower_idx].z);
        } else {
            // If no bracketing samples found, use nearest neighbor
            int nearest = 0;
            uint64_t min_diff = UINT64_MAX;
            for (int j = 0; j < accel_count; j++) {
                uint64_t diff = llabs((int64_t)ppg_timestamp - (int64_t)accel_samples[j].timestamp);
                if (diff < min_diff) {
                    min_diff = diff;
                    nearest = j;
                }
            }
            p_thread->combined_samples[i].accel_x = accel_samples[nearest].x;
            p_thread->combined_samples[i].accel_y = accel_samples[nearest].y;
            p_thread->combined_samples[i].accel_z = accel_samples[nearest].z;
        }
    }
}

/**
 * @brief Print the latest sensor samples
 *
 * @param p_thread Vitals thread instance
 */
void _print_sensor_samples(vitals_thread_t *p_thread) {
    for (uint32_t i = 0; i < CONFIG_PPG_SAMPLES_PER_BATCH; i++) {
        LOG_INF("Sensor Sample [%2d] [%10lld ms] R: %d, G: %d, IR: %d, X: %.2f, Y: %.2f, Z: %.2f",
                i,
                p_thread->combined_samples[i].ppg.timestamp,
                p_thread->combined_samples[i].ppg.red_intensity,
                p_thread->combined_samples[i].ppg.green_intensity,
                p_thread->combined_samples[i].ppg.ir_intensity,
                (double)p_thread->combined_samples[i].accel_x,
                (double)p_thread->combined_samples[i].accel_y,
                (double)p_thread->combined_samples[i].accel_z);
    }
}