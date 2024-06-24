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

Lis2de12ReadValuesResponse MtibRunnerZephyr_Lis2de12ReadValuesHandler(Lis2de12ReadValuesRequest request)
{
    uint32_t start_time = k_uptime_get_32();
    Lis2de12ReadValuesResponse response =
    {
        .success = false,
    };

    app_info_t *app = app_get_ptr();

    app_get_lis2de12_xyz_forces(app);

    response.success = true;
    response.x_value = app->lis2de12_dev.acc_x;
    response.y_value = app->lis2de12_dev.acc_y;
    response.z_value = app->lis2de12_dev.acc_z;

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}

Lis2de12ReadMaxForceResponse MtibRunnerZephyr_Lis2de12ReadMaxForceHandler(Lis2de12ReadMaxForceRequest request)
{
    uint32_t start_time = k_uptime_get_32();
    Lis2de12ReadMaxForceResponse response =
    {
        .success = false,
    };

    app_info_t *app = app_get_ptr();

    if (!app_get_lis2de12_max_force(app, false))
    {
        char err[] = "app_get_lis2de12_max_force failed";
        memcpy(response.error, err, sizeof(err) + 1);
        LOG_WRN("%s", response.error);
    }

    response.success = true;
    response.max_force = app->lis2de12_dev.max_force;

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}