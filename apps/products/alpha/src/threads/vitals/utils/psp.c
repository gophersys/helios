#include "api.h"

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
#include "../../../../lib/inc/fx_datatypes.h"
#include "../../../../lib/inc/psp.h"

// Thread includes
#include "../types.h"

// App includes
#include "../../bluetooth/thread.h"
#include "../../bluetooth/types.h"

LOG_MODULE_DECLARE(vitals_t, LOG_LEVEL_INF);

typedef enum {
    PSP_UPDATE_TYPE_PPG_IR,
    PSP_UPDATE_TYPE_PPG_GREEN,
    PSP_UPDATE_TYPE_PPG_RED,
    PSP_UPDATE_TYPE_PPG_AMBIENT,
} psp_ppg_type_t;

enum {
    PREAMBLE_SIZE = 5,                                                                   // Preamble
    BPI_SIZE = 1,                                                                        // Body Position Index
    PF_SIZE = 1,                                                                         // PPG Sample format
    AF_SIZE = 1,                                                                         // Accelerometer Sample format
    SI_SIZE = 1,                                                                         // Stream Identifier
    PPG_OFFSET_SIZE = 1,                                                                 // PPG Offset
    PPG_EXP_SIZE = 1,                                                                    // PPG Exponent
    LED_POWER_SIZE = 4,                                                                  // LED Power
    ADC_GAIN_SIZE = 4,                                                                   // ADC Gain
    PPG_SAMPLES_SIZE = CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND * sizeof(uint16_t),       // PPG Samples
    ACCEL_SAMPLES_SIZE = CONFIG_PSP_ALGORITHM_SAMPLES_PER_SECOND * sizeof(int16_t) * 3,  // Accelerometer Samples
} psp_metric_sizes_t;

// Define offsets for clearer array indexing
enum {
    OFFSET_BPI = 5,
    OFFSET_PF = 6,
    OFFSET_AF = 6,
    OFFSET_ACCEL_SAMPLES = 7,
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

static const char *_psp_error_string(PSP_ERROR err);
static const char *_psp_metric_string(PSP_METRIC_ID metric);

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
    p_thread->psp_required_metrics_count = CONFIG_PSP_NUM_INPUT_METRICS;
    err = PSP_ListRequiredMetrics(p_thread->psp_inst, p_thread->psp_required_metrics, &p_thread->psp_required_metrics_count);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Could not list required metrics for Phillips library: %s", _psp_error_string(err));
        return false;
    }

    for (size_t i = 0; i < p_thread->psp_required_metrics_count; i++) {
        LOG_INF("Required metric %d: %s", i, _psp_metric_string(p_thread->psp_required_metrics[i]));
    }

    p_thread->sequence_number = 1;

    return true;
}

bool _psp_process(vitals_thread_t *p_thread) {
    // Process the PSP algorithm
    PSP_ERROR err = PSP_Process(p_thread->psp_inst);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Failed to process PSP algorithm: %s", _psp_error_string(err));
        return false;
    }

    return true;
}

bool _psp_input_ppg_data(vitals_thread_t *p_thread, psp_ppg_type_t update_type) {
    // Calculate the actual data size (excluding preamble)
    const uint16_t data_size = BPI_SIZE + PF_SIZE + SI_SIZE + PPG_OFFSET_SIZE +
                               PPG_EXP_SIZE + LED_POWER_SIZE + ADC_GAIN_SIZE +
                               PPG_SAMPLES_SIZE;

    // Total size including preamble (ID + NL + NH + IX + Q)
    const uint16_t total_size = PREAMBLE_SIZE + data_size;
    uint8_t data[total_size];

    // Set up preamble
    uint8_t metric_id;
    switch (update_type) {
        case PSP_UPDATE_TYPE_PPG_IR:
            metric_id = PSP_METRIC_ID_PPG_INFRARED;
            break;
        case PSP_UPDATE_TYPE_PPG_GREEN:
            metric_id = PSP_METRIC_ID_PPG_GREEN;
            break;
        case PSP_UPDATE_TYPE_PPG_RED:
            metric_id = PSP_METRIC_ID_PPG_RED;
            break;
        case PSP_UPDATE_TYPE_PPG_AMBIENT:
            metric_id = PSP_METRIC_ID_PPG_AMBIENT;
            break;
        default:
            LOG_ERR("Invalid PPG update type");
            return false;
    }

    // Preamble
    data[0] = metric_id;                               // ID
    data[1] = (total_size - 3) & 0xFF;                 // NL (size of remaining data, excluding preamble)
    data[2] = (total_size - 3) >> 8;                   // NH
    data[3] = p_thread->sequence_number;               // IX
    data[4] = p_thread->calibration_complete ? 4 : 0;  // Q (quality)

    // Body position index
    data[OFFSET_BPI] = BPI_INDEX_RIGHT_WRIST;

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
        if (metric_id == PSP_METRIC_ID_PPG_AMBIENT) {
            data[OFFSET_LED_POWER + i] = 0;
        } else {
            // Use the actual LED DAC value from the sensor for each channel
            uint8_t led_power = 0;

            // Use the first sample's LED DAC value as representative
            switch (update_type) {
                case PSP_UPDATE_TYPE_PPG_RED:
                    led_power = p_thread->raw_samples_32Hz[0].ppg.red_dac;
                    break;
                case PSP_UPDATE_TYPE_PPG_GREEN:
                    led_power = p_thread->raw_samples_32Hz[0].ppg.green_dac;
                    break;
                case PSP_UPDATE_TYPE_PPG_IR:
                    led_power = p_thread->raw_samples_32Hz[0].ppg.ir_dac;
                    break;
                default:
                    led_power = 25;  // Fallback to default if type is unknown
            }
            data[OFFSET_LED_POWER + i] = led_power;
        }
    }

    // ADC gain - use our calibration state's gain values which are adjusted based on signal levels
    for (size_t i = 0; i < ADC_GAIN_SIZE; i++) {
        uint8_t adc_gain = 1;  // Default gain

        // Map the calibration gain to each channel
        if (p_thread->calibration_complete) {
            switch (update_type) {
                case PSP_UPDATE_TYPE_PPG_RED:
                    adc_gain = p_thread->ppg_cal_state.red.adc_gain;
                    break;
                case PSP_UPDATE_TYPE_PPG_GREEN:
                    adc_gain = p_thread->ppg_cal_state.green.adc_gain;
                    break;
                case PSP_UPDATE_TYPE_PPG_IR:
                    adc_gain = p_thread->ppg_cal_state.ir.adc_gain;
                    break;
                default:
                    adc_gain = 1;  // Default gain for ambient
            }
        }
        data[OFFSET_ADC_GAIN + i] = adc_gain;
    }

    // PPG samples
    for (size_t i = 0; i < PPG_SAMPLES_SIZE / 2; i++) {
        uint16_t ppg_sample;
        switch (update_type) {
            case PSP_UPDATE_TYPE_PPG_IR:
                ppg_sample = p_thread->psp_input_samples_32Hz[i].ppg_ir;
                break;
            case PSP_UPDATE_TYPE_PPG_GREEN:
                ppg_sample = p_thread->psp_input_samples_32Hz[i].ppg_green;
                break;
            case PSP_UPDATE_TYPE_PPG_RED:
                ppg_sample = p_thread->psp_input_samples_32Hz[i].ppg_red;
                break;
            case PSP_UPDATE_TYPE_PPG_AMBIENT:
                ppg_sample = p_thread->psp_input_samples_32Hz[i].ppg_ambient;
                break;
            default:
                LOG_ERR("Invalid PPG update type");
                return false;
        }

        uint16_t offset = OFFSET_PPG_SAMPLES + (i * 2);

        data[offset] = (uint8_t)(ppg_sample & 0xFF);    // LSB
        data[offset + 1] = (uint8_t)(ppg_sample >> 8);  // MSB
    }

    PSP_ERROR err = PSP_SetMetric(p_thread->psp_inst, metric_id, data, total_size);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Failed to set PPG metric %s: %s", _psp_metric_string(metric_id), _psp_error_string(err));
        return false;
    }

    // Extract and log the preamble information
    LOG_DBG("%s Metric Updated, index %d, quality %d, length 0x%02x",
            _psp_metric_string(metric_id),
            data[3],
            data[4],
            (data[1] & 0xFF) + ((data[2] & 0xFF) << 8));

    return true;
}

bool _psp_input_imu_data(vitals_thread_t *p_thread) {
    const uint16_t accel_metric_size = PREAMBLE_SIZE + BPI_SIZE + AF_SIZE + ACCEL_SAMPLES_SIZE;
    uint8_t data[accel_metric_size];

    // Preamble (5 bytes: ID, NL, NH, IX, Q)
    data[0] = PSP_METRIC_ID_ACCELERATION;              // ID
    data[1] = (accel_metric_size - 3) & 0xFF;          // NL (low byte of remaining size)
    data[2] = (accel_metric_size - 3) >> 8;            // NH (high byte of remaining size)
    data[3] = p_thread->sequence_number;               // IX (increment index each update)
    data[4] = p_thread->calibration_complete ? 4 : 0;  // Q (quality)

    // Body position index
    data[OFFSET_BPI] = BPI_INDEX_UNSPECIFIED;

    // PPG sample format
    data[OFFSET_AF] = 0x6E;  // 32 Hz, +/- 8G, 13-bits signed, 1/512 g/unit resolution

    // PPG samples - handle as 16-bit values
    for (size_t i = 0; i < 32; i++) {
        const size_t sample_offset = OFFSET_ACCEL_SAMPLES + (i * 6);  // 6 bytes per XYZ sample

        // X-axis
        uint16_t accel_sample = p_thread->psp_input_samples_32Hz[i].accel_x;
        data[sample_offset + 0] = (uint8_t)(accel_sample & 0xFF);  // X0,L
        data[sample_offset + 1] = (uint8_t)(accel_sample >> 8);    // X0,H

        // Y-axis
        accel_sample = p_thread->psp_input_samples_32Hz[i].accel_y;
        data[sample_offset + 2] = (uint8_t)(accel_sample & 0xFF);  // Y0,L
        data[sample_offset + 3] = (uint8_t)(accel_sample >> 8);    // Y0,H

        // Z-axis
        accel_sample = p_thread->psp_input_samples_32Hz[i].accel_z;
        data[sample_offset + 4] = (uint8_t)(accel_sample & 0xFF);  // Z0,L
        data[sample_offset + 5] = (uint8_t)(accel_sample >> 8);    // Z0,H
    }

    PSP_ERROR err = PSP_SetMetric(p_thread->psp_inst, PSP_METRIC_ID_ACCELERATION, data, accel_metric_size);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Failed to set Accelerometer metric %s: %s", _psp_metric_string(PSP_METRIC_ID_ACCELERATION), _psp_error_string(err));
        return false;
    }

    // Extract and log the preamble information
    LOG_DBG("%s Metric Updated, index %d, quality %d, length 0x%02x",
            _psp_metric_string(PSP_METRIC_ID_ACCELERATION),
            data[3],
            data[4],
            (data[1] & 0xFF) + ((data[2] & 0xFF) << 8));

    return true;
}

bool _psp_update_input_metrics(vitals_thread_t *p_thread) {
    // Enable clean up after 4 seconds
    static uint32_t cleanup_timer = 0;
    if (cleanup_timer == 0) {
        cleanup_timer = k_uptime_get_32();
    } else if (k_uptime_get_32() - cleanup_timer > 4000) {
        p_thread->calibration_complete = true;
    }

    // Now update PSP metrics with the same upsampled data
    if (!_psp_input_ppg_data(p_thread, PSP_UPDATE_TYPE_PPG_IR)) {
        LOG_ERR("Failed to update PPG IR metric");
        return false;
    }

    if (!_psp_input_ppg_data(p_thread, PSP_UPDATE_TYPE_PPG_GREEN)) {
        LOG_ERR("Failed to update PPG Green metric");
        return false;
    }

    if (!_psp_input_ppg_data(p_thread, PSP_UPDATE_TYPE_PPG_RED)) {
        LOG_ERR("Failed to update PPG Red metric");
        return false;
    }

    if (!_psp_input_ppg_data(p_thread, PSP_UPDATE_TYPE_PPG_AMBIENT)) {
        LOG_ERR("Failed to update PPG Ambient metric");
        return false;
    }

    if (!_psp_input_imu_data(p_thread)) {
        LOG_ERR("Failed to update Accelerometer metric");
        return false;
    }

    p_thread->sequence_number++;
    return true;
}

bool _psp_get_updated_psp_data(vitals_thread_t *p_thread) {
    // Calculate size needed for the full PPG data
    const uint16_t ppg_metric_size = PREAMBLE_SIZE + BPI_SIZE + PF_SIZE + SI_SIZE +
                                     PPG_OFFSET_SIZE + PPG_EXP_SIZE + LED_POWER_SIZE +
                                     ADC_GAIN_SIZE + PPG_SAMPLES_SIZE;

    // Update types
    psp_ppg_type_t update_types[4] = {
        PSP_UPDATE_TYPE_PPG_IR,
        PSP_UPDATE_TYPE_PPG_GREEN,
        PSP_UPDATE_TYPE_PPG_RED,
        PSP_UPDATE_TYPE_PPG_AMBIENT,
    };

    // Allocated buffers for each PPG type
    uint8_t read_data[ARRAY_SIZE(update_types)][ppg_metric_size];

    // Loop for each metric and store the data
    for (int i = 0; i < ARRAY_SIZE(update_types); i++) {
        // Determine which metric ID to request based on update type
        PSP_METRIC_ID metric_id;
        switch (update_types[i]) {
            case PSP_UPDATE_TYPE_PPG_IR:
                metric_id = PSP_METRIC_ID_PPG_INFRARED;
                break;
            case PSP_UPDATE_TYPE_PPG_GREEN:
                metric_id = PSP_METRIC_ID_PPG_GREEN;
                break;
            case PSP_UPDATE_TYPE_PPG_RED:
                metric_id = PSP_METRIC_ID_PPG_RED;
                break;
            case PSP_UPDATE_TYPE_PPG_AMBIENT:
                metric_id = PSP_METRIC_ID_PPG_AMBIENT;
                break;
            default:
                LOG_ERR("Invalid PPG update type");
                return false;
        }

        uint16_t metric_size = ppg_metric_size;

        // Get the metric data
        PSP_ERROR err = PSP_GetMetric(p_thread->psp_inst, metric_id, read_data[i], &metric_size);
        if (err != PSP_ERROR_NONE) {
            LOG_ERR("Failed to get PPG metric %s: %s", _psp_metric_string(metric_id), _psp_error_string(err));
            return false;
        }

        // Extract and log the preamble information
        LOG_DBG("%s Metric, index %d, quality %d, length 0x%02x",
                _psp_metric_string(metric_id),
                read_data[i][3],
                read_data[i][4],
                (read_data[i][1] & 0xFF) + ((read_data[i][2] & 0xFF) << 8));
    }

    // Get accelerometer data
    const uint16_t accel_metric_size = PREAMBLE_SIZE + BPI_SIZE + AF_SIZE + ACCEL_SAMPLES_SIZE;
    uint8_t accel_data[accel_metric_size];
    uint16_t metric_size = accel_metric_size;

    // Get the metric data
    PSP_ERROR err = PSP_GetMetric(p_thread->psp_inst, PSP_METRIC_ID_ACCELERATION, accel_data, &metric_size);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Failed to get Accelerometer metric: %s", _psp_error_string(err));
        return false;
    }

    // Extract and log the preamble information
    LOG_DBG("%s Metric, index %d, quality %d, length 0x%02x",
            _psp_metric_string(PSP_METRIC_ID_ACCELERATION),
            accel_data[3],
            accel_data[4],
            (accel_data[1] & 0xFF) + ((accel_data[2] & 0xFF) << 8));

    // If propagated PPG is enabled, <EXP> field is removed at output
    const uint16_t SAMPLES_START_OFFSET = OFFSET_PPG_SAMPLES - 1;

    for (int i = 0; i < 32; i++) {
        // Extract PPG intensities
        uint16_t red_ppg_intensity = ((uint16_t)read_data[PSP_UPDATE_TYPE_PPG_RED][SAMPLES_START_OFFSET + (i * 2) + 1] << 8) |
                                     (uint16_t)read_data[PSP_UPDATE_TYPE_PPG_RED][SAMPLES_START_OFFSET + (i * 2)];
        uint16_t ir_ppg_intensity = ((uint16_t)read_data[PSP_UPDATE_TYPE_PPG_IR][SAMPLES_START_OFFSET + (i * 2) + 1] << 8) |
                                    (uint16_t)read_data[PSP_UPDATE_TYPE_PPG_IR][SAMPLES_START_OFFSET + (i * 2)];
        uint16_t green_ppg_intensity = ((uint16_t)read_data[PSP_UPDATE_TYPE_PPG_GREEN][SAMPLES_START_OFFSET + (i * 2) + 1] << 8) |
                                       (uint16_t)read_data[PSP_UPDATE_TYPE_PPG_GREEN][SAMPLES_START_OFFSET + (i * 2)];
        uint16_t ambient_ppg_intensity = ((uint16_t)read_data[PSP_UPDATE_TYPE_PPG_AMBIENT][SAMPLES_START_OFFSET + (i * 2) + 1] << 8) |
                                         (uint16_t)read_data[PSP_UPDATE_TYPE_PPG_AMBIENT][SAMPLES_START_OFFSET + (i * 2)];

        // Extract accelerometer data
        int16_t x = accel_data[OFFSET_ACCEL_SAMPLES + (i * 6)] | (accel_data[OFFSET_ACCEL_SAMPLES + (i * 6) + 1] << 8);
        int16_t y = accel_data[OFFSET_ACCEL_SAMPLES + (i * 6) + 2] | (accel_data[OFFSET_ACCEL_SAMPLES + (i * 6) + 3] << 8);
        int16_t z = accel_data[OFFSET_ACCEL_SAMPLES + (i * 6) + 4] | (accel_data[OFFSET_ACCEL_SAMPLES + (i * 6) + 5] << 8);

        // Add PSP data to BLE thread
        psp_input_data_t psp_data = {
            .accelerometer = {
                .x = x,
                .y = y,
                .z = z,
            },
            .ppg_intensity = {
                .ambient_intensity = ambient_ppg_intensity,
                .green_intensity = green_ppg_intensity,
                .red_intensity = red_ppg_intensity,
                .ir_intensity = ir_ppg_intensity,
            },
        };

        if (!bluetooth_send_sensor_data(BLUETOOTH_THREAD_DATA_TYPE_PSP_READ_INPUT_DATA_32HZ,
                                        (uint8_t *)&psp_data,
                                        sizeof(psp_data))) {
            LOG_ERR("Failed to send PSP input data to bluetooth thread");
        }
    }

    return true;
}

bool _psp_get_output_metrics(vitals_thread_t *p_thread) {
    // List the updated metrics
    PSP_METRIC_ID updated_metrics[CONFIG_PSP_NUM_OUTPUT_METRICS];
    uint8_t updated_metrics_count = CONFIG_PSP_NUM_OUTPUT_METRICS;
    PSP_ERROR err = PSP_ListUpdatedMetrics(p_thread->psp_inst, updated_metrics, &updated_metrics_count);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Failed to list updated metrics: %s", _psp_error_string(err));
        return false;
    }

    for (size_t i = 0; i < updated_metrics_count; i++) {
        // LOG_INF("Updated metric %d: %s", i, _psp_metric_string(updated_metrics[i]));
    }

    // Get the heart rate metric
    uint8_t heartrate_data[6] = {0};
    uint16_t metric_size = sizeof(heartrate_data);
    err = PSP_GetMetric(p_thread->psp_inst, PSP_METRIC_ID_HEARTRATE, heartrate_data, &metric_size);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Failed to get Heart Rate metric: %s", _psp_error_string(err));
        return false;
    }

    // Extract and log the preamble information
    LOG_INF("Heart Rate Metric, index %d, quality %d, length 0x%02x, value %d BPM",
            heartrate_data[3],
            heartrate_data[4],
            (heartrate_data[1] & 0xFF) + ((heartrate_data[2] & 0xFF) << 8),
            heartrate_data[5]);

    p_thread->vitals_output_metrics.heart_rate = heartrate_data[5];
    p_thread->vitals_output_metrics.heart_rate_quality = heartrate_data[4];
    p_thread->vitals_output_metrics.heart_rate_index = heartrate_data[3];

    // Get SpO2 value
    uint8_t spo2_data[6];
    metric_size = sizeof(spo2_data);
    err = PSP_GetMetric(p_thread->psp_inst, PSP_METRIC_ID_SPO2, spo2_data, &metric_size);
    if (err != PSP_ERROR_NONE) {
        LOG_ERR("Failed to get SpO2 metric: %s", _psp_error_string(err));
        return false;
    }

    // Extract and log the preamble information
    LOG_INF("SpO2 Metric, index %d, quality %d, length 0x%02x, value %d",
            spo2_data[3],
            spo2_data[4],
            (spo2_data[1] & 0xFF) + ((spo2_data[2] & 0xFF) << 8),
            spo2_data[5]);

    p_thread->vitals_output_metrics.spo2 = spo2_data[5];
    p_thread->vitals_output_metrics.spo2_quality = spo2_data[4];
    p_thread->vitals_output_metrics.spo2_index = spo2_data[3];

    // Get the data we had previously inputted in this processing cycle
    if (!_psp_get_updated_psp_data(p_thread)) {
        LOG_ERR("Failed to get PSP data");
        return false;
    }

    // Print the last temperature value
    LOG_INF("Subject temperature, %0.2f F", (double)p_thread->vitals_output_metrics.temperature_f);

    return true;
}

static const char *_psp_error_string(PSP_ERROR err) {
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

static const char *_psp_metric_string(PSP_METRIC_ID metric) {
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