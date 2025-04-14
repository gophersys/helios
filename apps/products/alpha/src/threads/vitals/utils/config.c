#include "api.h"

// Standard includes
#include <stdbool.h>

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Thread includes
#include "../types.h"

LOG_MODULE_DECLARE(vitals_t, LOG_LEVEL_INF);

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

    if (p_config->p_temp_dev == NULL) {
        LOG_ERR("Invalid temperature device");
        return false;
    }

    return true;
}
