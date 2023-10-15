// Zephyr includes
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

// Cipher includes
#include "daemon/api.h"

// App includes
#include "alt-drv-test-srvc.h"  // We consume this service from the test app
#include "config/config.h"      // Network configuration of cluster

LOG_MODULE_REGISTER(app);

int main(void) {
    LOG_RAW("%s", "********** Alt Drv Runner App **********");

    // Create a new daemon instance
    cipher_daemon_config_t* cfg = get_app_config();
    cipher_daemon_t* d = get_app_daemon();
    cipher_daemon_init(cfg, d);

    size_t num_remote_services = 0;
    cipher_service_entry_t* remote_services = alt_drv_test_get_services(&num_remote_services);
    cipher_register_remote_services(d, remote_services, num_remote_services);  // Services we consume

    // Start
    cipher_daemon_start(d);

    k_msleep(1000);  // Await for service discovery

    while (true) {

        cipher_rpc_user_info_t info = {
            .device_id = 123,
            .timeout_ms = 5000,
        };

        test_request_t request = {};

        uint32_t start_time = k_uptime_get_32();
        test_response_t response = alt_drv_test_rpc_begin_test(d, &info, request);
        if (info.error != CIPHER_RPC_ERR_OK) {
            ERROR("Could not execute test RPC: %d", info.error);
        }
        LOG("RPC alt_drv_test_rpc_begin_test succeeded! (%dms)", k_uptime_get_32() - start_time);

        if (response.success) {
            LOG("Test Passed!");
        }

        k_msleep(500);
    }
}