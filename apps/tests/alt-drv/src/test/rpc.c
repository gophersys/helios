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
    uint32_t start_time = k_uptime_get_32();

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

    LOG("RPC %s called, total execution time: %d", __func__, k_uptime_get_32() - start_time);

    return response;
}

static bool set_desired_altitude(double altitude_ft) {

    alt_setting_request_t request = {
        .desired_altitude_ft = altitude_ft,
        .setting = _1000_FT_PER_5_SEC,
    };

    cipher_rpc_user_info_t info = {
        .device_id = 124,     // Ask any device that offers this service
        .timeout_ms = 20000,  // 20 seconds
    };

    uint32_t start_time = k_uptime_get_32();
    alt_setting_response_t response = alt_sim_rpc_set_altitude(get_app_daemon(), &info, request);
    if (info.error != CIPHER_RPC_ERR_OK) {
        WARN("RPC internal error: %d", info.error);
        return false;
    }

    LOG("RPC alt_sim_rpc_set_altitude succeeded! (%dms)", k_uptime_get_32() - start_time);

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

    // Consume the altimeter bench service
    readings_request_t request;
    cipher_rpc_user_info_t info = {
        .device_id = 124,    // Ask any device that offers this service
        .timeout_ms = 1000,  // Readings is a fast operation
    };

    uint32_t start_time = k_uptime_get_32();
    cipher_daemon_t* d = get_app_daemon();
    readings_response_t response = alt_sim_rpc_get_readings(d, &info, request);  // auto-gen rpc
    if (info.error != CIPHER_RPC_ERR_OK) {
        WARN("RPC internal error: %s:%d", __func__, info.error);
        return false;
    }
    LOG("RPC alt_sim_rpc_get_readings succeeded! (%dms)", k_uptime_get_32() - start_time);

    // For now, just print both readings
    test_app_info_t* app = get_app_info();
    LOG("Local readings:");
    print_readings(&app->temperature, &app->pressure, &app->altitude);

    LOG("Remote readings:");
    double temp_local = response.temperature_c;  // save to local vars due to __attribute__((packed))
    double pressure_local = response.pressure_inhg;
    double altitude_local = response.altitude_m;
    print_readings(&temp_local, &pressure_local, &altitude_local);

    return true;
}

#ifdef LOCAL_TEST_ENABLED
void run_manual_test(void) {

    k_msleep(1000);  // TODO: Await for succesful service discovery

    while (true) {
        k_msleep(500);

        if (!set_desired_altitude(3000)) {
            WARN("Could not set desired altitude");
            return;
        }

        if (!compare_readings()) {
            WARN("Results comparison not succesful");
        }
    }
}
#endif