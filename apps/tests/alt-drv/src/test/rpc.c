#include <alt_drv.h>

#include "test.h"

// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include "daemon/api.h"
#include "utils/err.h"

// App includes
#include "../config/config.h"   // Network configuration of cluster
#include "alt-drv-test-srvc.h"  // We offer this service to the runner
#include "alt-sim-srvc.h"       // We consume this service from the icle

LOG_MODULE_DECLARE(app);

static bool set_desired_altitude(double altitude_ft);
static bool compare_readings(void);

test_response_t alt_drv_test_rpc_begin_test_handler(test_request_t request) {

    test_response_t response = {0};

    if (!set_desired_altitude(3000)) {
        WARN("Could not set desired altitude");
        response.success = false;
        response.err = ALT_TEST_ERR_FIXTURE;
        return response;
    }

    if (!compare_readings()) {
        WARN("Results comparison not succesful");
        response.success = false;
        response.err = ALT_TEST_ERR_RESULTS;
        return response;
    }

    return response;
}

static bool set_desired_altitude(double altitude_ft) {

    alt_setting_request_t request = {
        .desired_altitude_ft = altitude_ft,
        .setting = _1000_FT_PER_5_SEC,
    };

    cipher_rpc_user_info_t info = {
        .device_id = CONFIG_CIPHER_ANY_ADDR,  // Ask any device that offers this service
        .timeout_ms = 20000,                  // 20 seconds
    };

    uint32_t start_time = k_uptime_get_32();
    alt_setting_response_t response = alt_sim_rpc_set_altitude(get_app_daemon(), &info, request);
    if (info.error != CIPHER_RPC_ERR_OK) {
        WARN("RPC internal error: %d", info.error);
        return false;
    }

    if (!response.success) {
        WARN("RPC host error: %d", response.err);
        return false;
    }

    int alt_int = (int)altitude_ft;
    int alt_frac = (int)((altitude_ft - alt_int) * 1000);  // 3 decimal places
    LOG("Altitude set to %d:%d in %d ms", alt_int, alt_frac, k_uptime_get_32() - start_time);
    return true;
}

static bool compare_readings(void) {
    readings_request_t request = {0};

    cipher_rpc_user_info_t info = {
        .device_id = CONFIG_CIPHER_ANY_ADDR,  // Ask any device that offers this service
        .timeout_ms = 200,                    // Readings is a fast operation
    };

    uint32_t start_time = k_uptime_get_32();
    readings_response_t response = alt_sim_rpc_get_readings(get_app_daemon(), &info, request);
    if (info.error != CIPHER_RPC_ERR_OK) {
        WARN("RPC %s internal error: %d", info.error);
        return false;
    }

    test_app_info_t* app_info = get_app_info();
    LOG("Local readings:");
    print_readings(&app_info->temperature, &app_info->pressure, &app_info->altitude);
    LOG("Remote readings:");
    print_readings(&response.temperature_c, &response.pressure_inhg, &response.altitude_m);

    return true;  // TODO: Do an actually reasonable comparison
}

#ifdef LOCAL_TEST_ENABLED
void run_manual_test(void) {
    if (!set_desired_altitude(3000)) {
        WARN("Could not set desired altitude");
    }

    if (!compare_readings()) {
        WARN("Results comparison not succesful");
    }
}
#endif