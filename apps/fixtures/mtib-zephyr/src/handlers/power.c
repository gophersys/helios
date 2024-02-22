// Standard includes

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/cipher/cipher.h>

// Protocol includes
#include "protos/mtib_pi_stm/mtib-pi-stm.cipher.h"

// App includes
#include "app/app.h"

LOG_MODULE_DECLARE(handlers);

DutEnablePowerResponse MtibPiStm_DutEnablePowerHandler(DutEnablePowerRequest request)
{
    uint32_t start_time = k_uptime_get_32();

    DutEnablePowerResponse response =
    {
        .success = false,
    };

    if (!app_power_enable(app_get_ptr(), request.enable))
    {
        char err[] = "Could not set device power state";
        memcpy(response.error, err, sizeof(response.error));
        LOG_WRN("%s", response.error);
    }
    else
    {
        response.success = true;
    }

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}

DutEnableChargerResponse MtibPiStm_DutEnableChargerHandler(DutEnableChargerRequest request)
{
    uint32_t start_time = k_uptime_get_32();

    DutEnableChargerResponse response =
    {
        .success = false,
    };

    if (!app_charger_enable(app_get_ptr(), request.enable))
    {
        char err[] = "Could not set device charge power state";
        memcpy(response.error, err, sizeof(response.error));
        LOG_WRN("%s", response.error);
    }
    else
    {
        response.success = true;
    }

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}