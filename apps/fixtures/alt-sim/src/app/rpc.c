#include "app.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// App includes
#include "alt-sim-srvc.h"  // We offer this service to the test app

LOG_MODULE_DECLARE(app);

alt_setting_response_t alt_sim_rpc_set_altitude_handler(alt_setting_request_t request) {
    uint32_t start_time = k_uptime_get_32();

    alt_setting_response_t response = {0};

    test_app_info_t* app = get_app_info();
    if (!set_altitude(app, request.desired_altitude_ft, request.setting)) {
        WARN("Unable to set fixture's altitude");
        response.success = false;
        response.err = ALT_SIM_ERR_FATAL;
        return response;
    }

    response.success = true;

    LOG("RPC %s called, total execution time: %d", __func__, k_uptime_get_32() - start_time);

    return response;
}

readings_response_t alt_sim_rpc_get_readings_handler(readings_request_t request) {
    uint32_t start_time = k_uptime_get_32();

    readings_response_t response = {0};

    test_app_info_t* app = get_app_info();
    response.altitude_m = app->altitude;
    response.pressure_inhg = app->pressure;
    response.temperature_c = app->temperature;

    LOG("RPC %s called, total execution time: %d", __func__, k_uptime_get_32() - start_time);

    return response;
}