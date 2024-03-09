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

Ina219ReadCurrentResponse MtibPiStm_Ina219ReadCurrentHandler(Ina219ReadCurrentRequest request)
{
    uint32_t start_time = k_uptime_get_32();
    Ina219ReadCurrentResponse response =
    {
        .success = true
    };

    app_info_t *app = app_get_ptr();
    app_print_ina219_data(app);
    double value = (double)app->ina219_dev.current.val1 + (double)app->ina219_dev.current.val2 / 1000000;
    response.current_value_ma = value * 1000;

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}

Ina219ReadVoltageResponse MtibPiStm_Ina219ReadVoltageHandler(Ina219ReadVoltageRequest request)
{
    uint32_t start_time = k_uptime_get_32();
    Ina219ReadVoltageResponse response =
    {
        .success = true
    };

    app_info_t *app = app_get_ptr();
    app_print_ina219_data(app);
    double value = (double)app->ina219_dev.bus_voltage.val1 + (double)app->ina219_dev.bus_voltage.val2 / 1000000;
    response.voltage_value_mv = value * 1000;

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}

Ina219ReadPowerResponse MtibPiStm_Ina219ReadPowerHandler(Ina219ReadPowerRequest request)
{
    uint32_t start_time = k_uptime_get_32();
    Ina219ReadPowerResponse response =
    {
        .success = true
    };

    app_info_t *app = app_get_ptr();
    app_print_ina219_data(app);
    response.power_value_mw = app->ina219_dev.power.val1;

    LOG_INF("%s executed in %ums", __func__, k_uptime_get_32() - start_time);
    return response;
}