// Standard includes

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Corekinect includes
#include <corekinect/cipher/cipher.h>

// Protocol includes
#include "protos/mtib_runner_zephyr/mtib_runner_zephyr.cipher.h"

// App includes
#include "app/app.h"

LOG_MODULE_DECLARE(handlers);

Bmp390ReadValuesResponse MtibRunnerZephyr_Bmp390ReadValuesHandler(Bmp390ReadValuesRequest request)
{
    uint32_t start_time = k_uptime_get_32();
    Bmp390ReadValuesResponse response =
    {
        .success = false,
    };

    // We only do an altitude reading as this will trigger all readings to be updated
    if (!app_get_bmp390_altitude(app_get_ptr()))
    {
        char err[] = "app_get_bmp390_altitude failed";
        memcpy(response.error, err, sizeof(err) + 1);
        LOG_WRN("%s", response.error);
    }
    else
    {
        // We've read all readings, assign them to response
        response.success = true;

        app_info_t *app = app_get_ptr();
        response.temperature_f = app->bmp390_dev.temperature;
        response.pressure_hg = app->bmp390_dev.pressure;
        response.altitude_ft = app->bmp390_dev.altitude;
    }

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);

    return response;

}